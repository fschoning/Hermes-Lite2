// SPDX-License-Identifier: GPL-2.0-or-later
// Copyright 2026 Franz Schöning, https://www.schoning.com
//
// Layer-1 register/memory bridge for the HL2 front-end images (no CPU involved)
//
// Etherbone-format register access (LiteX/LiteEth wire format) on the aux UDP port 1027,
// a small Wishbone register block, and the command-bus merge that lets the bridge set the
// RX gain through the existing openHPSDR command fan-out. See docs/rawfront/PROTOCOL.md.
//
//   ebbridge     Etherbone request receiver (Ethernet receive domain, request buffer RAM),
//                request executor as a Wishbone master and reply sender (Ethernet send domain,
//                shares the aux send slot with rtl/auxchan.v)
//   hl2bus_regs  Wishbone register slave: ID, version, scratch, capabilities, bridge counters,
//                slow ADC values, key/PTT/TX-inhibit inputs, transmit-safety status, RX gain
//   cmd_merge    Command-bus merge in the dsopenhpsdr1 domain: forwards PC commands at once and
//                inserts a bridge command only after the PC command stream has been quiet
//
// Etherbone subset (one record per packet, 32-bit addresses and data, big-endian):
//   bytes 0-1 magic 0x4E 0x6F; byte 2 version (bits 7:4 = 1), bit 0 probe flag; byte 3 0x44;
//   bytes 4-7 0; record header: byte 8 flags, byte 9 byte-enable, byte 10 write count W,
//   byte 11 read count R; if W > 0: base write address, then W values written to consecutive
//   32-bit words; if R > 0: base return address, then R read addresses.
//   Reply (only for records with R > 0, as LiteEth): packet header, record header with
//   W = R and R = 0, the base return address, then the R values read.
//   Probe (flag bit 0): 8-byte reply with the probe-reply flag (byte 2 = 0x12).
//   Addresses are byte addresses; registers sit on multiples of 4 (Wishbone word = address / 4).
//
// CPU_IO = 1 (hl2b5up_cpu): datagrams to the port whose first byte is neither 0x4E (Etherbone) nor
// 0x5B (aux channel) are for the soft CPU. The executor copies each one into the CPU receive ring
// of the shared packet buffer (rtl/hl2cpu.v pbuf_ram) as a 2-byte length plus the bytes, or drops it
// when the ring is full. It also sends the CPU's transmit buffer as a datagram when the CPU asks.
// Both use the same one-request-at-a-time path and the same aux send slot as bridge replies, so
// the CPU cannot hold the network sender any longer than a bridge reply can.

module ebbridge #(
  parameter PORT    = 16'd1027,
  parameter MAX_RW  = 64,                    // largest W or R accepted (reply buffer holds 64 words)
  parameter CPU_IO  = 0                      // 1: CPU datagrams and the shared packet buffer
) (
  // Ethernet receive domain
  input                clk_rx          ,
  input         [15:0] eth_port        ,
  input                eth_broadcast   ,
  input                eth_valid       ,
  input         [ 7:0] eth_data        ,
  // Ethernet send domain
  input                clk             ,
  input                dest_valid      ,     // network.v: aux destination known
  input         [15:0] room            ,     // rawstream.v: largest aux UDP payload that fits now
  output logic         ready = 1'b0    ,
  input                grant           ,
  output        [ 1:0] tx_request      ,
  output        [15:0] tx_length       ,
  output        [ 7:0] tx_data         ,
  input                tx_enable       ,
  output               busy            ,
  // Wishbone master (clk domain)
  output logic  [29:0] wb_adr   = 30'd0,
  output logic         wb_regs  = 1'b1 ,     // registered with wb_adr: address in 0x4000_0000-0x4000_FFFF
  output logic  [31:0] wb_dat_w = 32'd0,
  input         [31:0] wb_dat_r        ,
  output logic  [ 3:0] wb_sel   = 4'd0 ,
  output logic         wb_we    = 1'b0 ,
  output logic         wb_cyc   = 1'b0 ,
  output               wb_stb          ,
  input                wb_ack          ,
  input                wb_err          ,
  // counters (clk domain): requests executed, requests dropped, bus errors
  output        [95:0] stats           ,
  // CPU_IO = 1: packet buffer port B (clk) and the CPU packet interface
  output        [ 9:0] pb_adr          ,
  output               pb_we           ,
  output        [ 7:0] pb_wd           ,
  input         [ 7:0] pb_q            ,
  input                clk_cpu         ,
  output logic  [ 9:0] cpu_rx_wr = 10'd0,     // clk
  input         [ 9:0] cpu_rx_rd       ,     // clk_cpu
  input                cpu_tx_req      ,     // clk_cpu, level
  input         [ 8:0] cpu_tx_len      ,     // clk_cpu, stable while cpu_tx_req
  output logic         cpu_tx_done = 1'b0,   // clk
  output        [31:0] cpu_counts            // clk: {datagrams sent, datagrams dropped (ring full)}
);

//////////////////////////////////////////////////////////////////////////////
// Receive side (clk_rx): copy Etherbone packets into the request buffer

localparam RQ_AW = 9;                        // 512-byte request buffer

logic        v_r = 1'b0, v_p = 1'b0;
logic [ 7:0] d_r = 8'h00;
logic        port_ok = 1'b0;
always @(posedge clk_rx) begin
  v_r     <= eth_valid;
  v_p     <= v_r;
  d_r     <= eth_data;
  port_ok <= (eth_port == PORT) & ~eth_broadcast;
end

logic        ack = 1'b0;                     // clk domain
(* preserve *) logic [1:0] ack_rx_s = 2'b00;
wire         ack_rx = ack_rx_s[1];

logic        take      = 1'b0;
logic        skip      = 1'b0;               // packet arrives while a request is still pending
logic        ovr       = 1'b0;
logic [ 9:0] cnt       = 10'd0;
logic        pend      = 1'b0;
logic [ 9:0] len_hold  = 10'd0;
logic        kind      = 1'b0;               // 0 Etherbone, 1 CPU datagram
logic        kind_hold = 1'b0;
logic [31:0] drops_rx  = 32'd0;

logic             rq_we = 1'b0;
logic [RQ_AW-1:0] rq_wa = '0;
logic [7:0]       rq_wd = 8'h00;
logic [7:0]       rq_mem [0:(1<<RQ_AW)-1];

always @(posedge clk_rx) begin
  ack_rx_s <= {ack_rx_s[0], ack};
  rq_we    <= 1'b0;
  if (pend & ack_rx) pend <= 1'b0;

  if (~v_r) begin
    if (v_p) begin
      if (take & ~ovr & (kind ? (cnt >= 10'd1) : (cnt >= 10'd8))) begin
        pend      <= 1'b1;
        len_hold  <= cnt;
        kind_hold <= kind;
      end
      if (skip & ~&drops_rx) drops_rx <= drops_rx + 32'd1;
    end
    take <= port_ok & ~pend & ~ack_rx;
    skip <= port_ok & (pend | ack_rx);
    cnt  <= 10'd0;
    ovr  <= 1'b0;
    kind <= 1'b0;
  end else if (take) begin
    if (cnt == 10'd0) begin
      if (d_r == 8'h4e)                         kind <= 1'b0;
      else if ((CPU_IO != 0) & (d_r != 8'h5b)) kind <= 1'b1;
      else                                      take <= 1'b0;
    end
    if ((cnt == 10'd1) & ~kind & (d_r != 8'h6f)) take <= 1'b0;
    if (cnt[RQ_AW]) begin
      ovr <= 1'b1;
    end else begin
      rq_we <= 1'b1;
      rq_wa <= cnt[RQ_AW-1:0];
      rq_wd <= d_r;
      cnt   <= cnt + 10'd1;
    end
  end
end

always @(posedge clk_rx) if (rq_we) rq_mem[rq_wa] <= rq_wd;

//////////////////////////////////////////////////////////////////////////////
// Execute and reply (clk domain)

(* preserve *) logic [1:0] pend_s = 2'b00;
always @(posedge clk) pend_s <= {pend_s[0], pend};
wire pend_c = pend_s[1];

localparam S_IDLE  = 5'd0,  S_HDR   = 5'd1,  S_CHK8  = 5'd2,  S_HDR2  = 5'd3,  S_CHK12 = 5'd4,
           S_GET   = 5'd5,  S_WBASE = 5'd6,  S_WDATA = 5'd7,  S_WWAIT = 5'd8,  S_RBASE = 5'd9,
           S_RADDR = 5'd10, S_RWAIT = 5'd11, S_RSTOR = 5'd12, S_RDY   = 5'd13, S_REQ   = 5'd14,
           S_SEND  = 5'd15, S_DROP  = 5'd16, S_DONE  = 5'd17, S_ACK   = 5'd18, S_CRX   = 5'd19,
           S_CRX1  = 5'd20, S_CRX2  = 5'd21, S_CRX3  = 5'd22, S_CTX   = 5'd23, S_CTXD  = 5'd24;

logic [ 4:0] st      = S_IDLE;
logic [ 4:0] nxt     = S_IDLE;
logic [ 9:0] len     = 10'd0;
logic [ 3:0] k       = 4'd0;
logic [95:0] sh      = 96'd0;
logic [31:0] w       = 32'd0;
logic [ 7:0] be      = 8'd0;
logic [ 7:0] wn      = 8'd0;
logic [ 7:0] rn      = 8'd0;
logic [ 7:0] wi      = 8'd0;
logic [ 7:0] ri      = 8'd0;
logic [ 1:0] bi      = 2'd0;
logic [29:0] wadr    = 30'd0;
logic [31:0] ret     = 32'd0;
logic [31:0] rd      = 32'd0;
logic [11:0] to_cnt  = 12'd0;             // Wishbone timeout, 4,095 cycles (CPU-domain requests cross clocks)
logic [23:0] rto     = 24'd0;               // reply wait timeout, ~134 ms at 125 MHz
logic [11:0] need    = 12'd0;
logic        probe   = 1'b0;
logic [15:0] rlen    = 16'd0;
logic [127:0] hdr    = 128'd0;
logic [ 3:0] hleft   = 4'd0;
logic [15:0] left    = 16'd0;
logic [ 2:0] holdoff = 3'd0;
logic [ 7:0] tx_d    = 8'h00;

logic [31:0] n_req   = 32'd0;
logic [31:0] n_drop  = 32'd0;
logic [31:0] n_berr  = 32'd0;

// CPU packet interface state (CPU_IO = 1)
(* preserve *) logic [1:0] kind_s = 2'b00;
(* preserve *) logic [1:0] ctx_s  = 2'b00;
logic        ctx       = 1'b0;               // sending a CPU datagram
logic [ 9:0] rxw       = 10'd0;              // ring write position while copying
logic [ 9:0] rx_rd_c;
logic [ 9:0] ring_used = 10'd0;
logic [ 8:0] ctx_len_c;
logic [15:0] n_ctx     = 16'd0;
logic [15:0] n_crx_dr  = 16'd0;
always @(posedge clk) begin
  kind_s <= {kind_s[0], kind_hold};
  ctx_s  <= {ctx_s[0], cpu_tx_req & (CPU_IO != 0)};
end
// the transmit length is stable while cpu_tx_req is high; one synchroniser stage more than the request
(* preserve *) logic [8:0] ctx_len_s1 = 9'd0, ctx_len_s2 = 9'd0, ctx_len_s3 = 9'd0;
always @(posedge clk) begin
  ctx_len_s1 <= cpu_tx_len;
  ctx_len_s2 <= ctx_len_s1;
  ctx_len_s3 <= ctx_len_s2;
end
generate if (CPU_IO != 0) begin: CPU_SYNC
  cdc_word #(.W(10)) cdc_rxrd_i  (.clk_a(clk_cpu), .d_a(cpu_rx_rd),  .clk_b(clk), .q_b(rx_rd_c));
  assign ctx_len_c = ctx_len_s3;
end else begin: CPU_NOSYNC
  assign rx_rd_c   = 10'd0;
  assign ctx_len_c = 9'd0;
end endgenerate
assign cpu_counts = {n_ctx, n_crx_dr};

// request buffer read side, show-ahead: rq_q is always rq_mem[rq_ptr]
logic [RQ_AW-1:0] rq_ptr = '0;
logic [7:0]       rq_q   = 8'h00;
logic             rq_adv;
wire  [RQ_AW-1:0] rq_ra  = (st == S_IDLE) ? '0 : (rq_adv ? rq_ptr + 1'b1 : rq_ptr);
always @(posedge clk) begin
  rq_q   <= rq_mem[rq_ra];
  rq_ptr <= rq_ra;
end

// reply data buffer (read values), show-ahead on the send side. CPU_IO = 1: the shared packet
// buffer, also holding the CPU transmit buffer (256-511) and the CPU receive ring (512-1023).
logic       rp_we = 1'b0;
logic [9:0] rp_wa = 10'd0;
logic [7:0] rp_wd = 8'h00;
logic [9:0] rp_ptr = 10'd0;
logic [7:0] rp_q;
logic       rp_adv;
wire  [9:0] rp_ra  = ((st == S_REQ) & ~(ctx & tx_enable)) ? {1'b0, ctx, 8'd0} :
                     (rp_adv ? rp_ptr + 10'd1 : rp_ptr);
always @(posedge clk) rp_ptr <= rp_ra;

generate if (CPU_IO != 0) begin: RP_SHARED
  assign pb_adr = rp_we ? rp_wa : rp_ra;
  assign pb_we  = rp_we;
  assign pb_wd  = rp_wd;
  assign rp_q   = pb_q;
end else begin: RP_LOCAL
  logic [7:0] rp_mem [0:255];
  logic [7:0] rp_q_r = 8'h00;
  always @(posedge clk) begin
    if (rp_we) rp_mem[rp_wa[7:0]] <= rp_wd;
    rp_q_r <= rp_mem[rp_ra[7:0]];
  end
  assign rp_q   = rp_q_r;
  assign pb_adr = 10'd0;
  assign pb_we  = 1'b0;
  assign pb_wd  = 8'h00;
end endgenerate

always @* begin
  rq_adv = (st == S_HDR) | (st == S_HDR2) | (st == S_GET) | (st == S_CRX2);
  rp_adv = ((st == S_SEND) & (left != 16'd0) & (hleft == 4'd0)) | ((st == S_REQ) & ctx & tx_enable);
end

wire [7:0] max_rw = MAX_RW;

always @(posedge clk) begin
  rp_we <= 1'b0;
  if (holdoff != 3'd0) holdoff <= holdoff - 3'd1;
  ready <= (st == S_RDY) & dest_valid & (holdoff == 3'd0) & ~grant & (room >= rlen);

  if (~ctx_s[1]) cpu_tx_done <= 1'b0;
  ring_used <= cpu_rx_wr - rx_rd_c;

  case (st)
    S_IDLE: begin
      if (pend_c & ~ack) begin
        len <= len_hold;                     // stable while pend is set
        k   <= 4'd0;
        st  <= kind_s[1] ? S_CRX : S_HDR;
      end else if (ctx_s[1] & ~cpu_tx_done) begin
        st  <= S_CTX;
      end
    end

    // CPU datagram into the receive ring: 2-byte length (little-endian), then the bytes
    S_CRX: begin
      rxw <= cpu_rx_wr;
      if ({2'b00, len} + 12'd2 > 12'd512 - {2'b00, ring_used}) begin
        if (~&n_crx_dr) n_crx_dr <= n_crx_dr + 16'd1;
        st <= S_DONE;
      end else begin
        rp_we <= 1'b1;
        rp_wa <= {1'b1, cpu_rx_wr[8:0]};
        rp_wd <= len[7:0];
        st    <= S_CRX1;
      end
    end

    S_CRX1: begin
      rp_we <= 1'b1;
      rp_wa <= {1'b1, rxw[8:0] + 9'd1};
      rp_wd <= {6'd0, len[9:8]};
      rxw   <= rxw + 10'd2;
      need  <= 12'd0;
      st    <= S_CRX2;
    end

    S_CRX2: begin                            // one byte per cycle from the request buffer
      rp_we <= 1'b1;
      rp_wa <= {1'b1, rxw[8:0]};
      rp_wd <= rq_q;
      rxw   <= rxw + 10'd1;
      need  <= need + 12'd1;
      if (need + 12'd1 == {2'b00, len}) st <= S_CRX3;
    end

    S_CRX3: begin
      cpu_rx_wr <= rxw;
      n_req     <= n_req + 32'd1;
      st        <= S_DONE;
    end

    // CPU datagram out of the transmit buffer
    S_CTX: begin
      if (~dest_valid | (ctx_len_c == 9'd0)) begin
        st <= S_CTXD;
      end else begin
        ctx   <= 1'b1;
        probe <= 1'b0;
        rlen  <= {7'd0, ctx_len_c};
        rto   <= 24'd0;
        st    <= S_RDY;
      end
    end

    S_CTXD: begin
      if (ctx & ~&n_ctx) n_ctx <= n_ctx + 16'd1;
      ctx         <= 1'b0;
      cpu_tx_done <= 1'b1;
      st          <= S_IDLE;
    end

    S_HDR: begin                             // packet header, 8 bytes
      sh <= {sh[87:0], rq_q};
      k  <= k + 4'd1;
      if (k == 4'd7) st <= S_CHK8;
    end

    S_CHK8: begin
      if ((sh[63:48] != 16'h4e6f) | (sh[47:44] != 4'h1)) begin
        st <= S_DROP;
      end else if (sh[40]) begin             // probe
        n_req <= n_req + 32'd1;
        probe <= 1'b1;
        rlen  <= 16'd8;
        hdr   <= {16'h4e6f, 8'h12, 8'h44, 32'd0, 64'd0};
        rto   <= 24'd0;
        st    <= S_RDY;
      end else if (len < 10'd12) begin
        n_req <= n_req + 32'd1;              // header only: nothing to do
        st    <= S_DONE;
      end else begin
        k  <= 4'd0;
        st <= S_HDR2;
      end
    end

    S_HDR2: begin                            // record header, 4 bytes
      sh <= {sh[87:0], rq_q};
      k  <= k + 4'd1;
      if (k == 4'd3) st <= S_CHK12;
    end

    S_CHK12: begin
      be   <= sh[23:16];
      wn   <= sh[15:8];
      rn   <= sh[7:0];
      need <= 12'd12 + ((sh[15:8] != 8'd0) ? ({2'b00, sh[15:8], 2'b00} + 12'd4) : 12'd0)
                     + ((sh[7:0]  != 8'd0) ? ({2'b00, sh[7:0],  2'b00} + 12'd4) : 12'd0);
      k    <= 4'd0;
      if ((sh[15:8] > max_rw) | (sh[7:0] > max_rw)) st <= S_DROP;
      else                                           st <= S_WBASE;   // S_WBASE checks the length first
    end

    S_GET: begin                             // one big-endian 32-bit word into w, then nxt
      w <= {w[23:0], rq_q};
      k <= k + 4'd1;
      if (k == 4'd3) begin k <= 4'd0; st <= nxt; end
    end

    S_WBASE: begin
      if (nxt != S_WBASE) begin              // first entry: length check, then fetch the base address
        if ({2'b00, len} < need) begin
          st <= S_DROP;
        end else begin
          n_req <= n_req + 32'd1;
          wi    <= 8'd0;
          ri    <= 8'd0;
          if (wn != 8'd0)      begin nxt <= S_WBASE; st <= S_GET; end
          else if (rn != 8'd0) begin nxt <= S_RBASE; st <= S_GET; end
          else                 st <= S_DONE;
        end
      end else begin                         // w = base write address
        wadr <= w[31:2];
        nxt  <= S_WDATA;
        st   <= S_GET;
      end
    end

    S_WDATA: begin                           // w = value
      wb_adr   <= wadr;
      wb_regs  <= (wadr[29:14] == 16'h4000);
      wb_dat_w <= w;
      wb_sel   <= be[3:0];
      wb_we    <= 1'b1;
      wb_cyc   <= 1'b1;
      to_cnt   <= 12'd0;
      st       <= S_WWAIT;
    end

    S_WWAIT: begin
      to_cnt <= to_cnt + 12'd1;
      if (wb_ack | wb_err | (&to_cnt)) begin
        wb_cyc <= 1'b0;
        wb_we  <= 1'b0;
        if (~wb_ack & ~&n_berr) n_berr <= n_berr + 32'd1;
        wadr <= wadr + 30'd1;
        wi   <= wi + 8'd1;
        if (wi + 8'd1 == wn) begin
          if (rn != 8'd0) begin nxt <= S_RBASE; st <= S_GET; end
          else            st <= S_DONE;
        end else begin
          nxt <= S_WDATA;
          st  <= S_GET;
        end
      end
    end

    S_RBASE: begin                           // w = base return address
      ret <= w;
      nxt <= S_RADDR;
      st  <= S_GET;
    end

    S_RADDR: begin                           // w = read address
      wb_adr <= w[31:2];
      wb_regs <= (w[31:16] == 16'h4000);
      wb_sel <= be[3:0];
      wb_we  <= 1'b0;
      wb_cyc <= 1'b1;
      to_cnt <= 12'd0;
      st     <= S_RWAIT;
    end

    S_RWAIT: begin
      to_cnt <= to_cnt + 12'd1;
      if (wb_ack | wb_err | (&to_cnt)) begin
        wb_cyc <= 1'b0;
        if (wb_ack) begin
          rd <= wb_dat_r;
        end else begin
          rd <= 32'hffffffff;
          if (~&n_berr) n_berr <= n_berr + 32'd1;
        end
        bi <= 2'd0;
        st <= S_RSTOR;
      end
    end

    S_RSTOR: begin
      rp_we <= 1'b1;
      rp_wa <= {2'b00, ri[5:0], bi};
      rp_wd <= rd[31:24];
      rd    <= {rd[23:0], 8'h00};
      bi    <= bi + 2'd1;
      if (bi == 2'd3) begin
        ri <= ri + 8'd1;
        if (ri + 8'd1 == rn) begin
          probe <= 1'b0;
          rlen  <= 16'd16 + {6'd0, rn, 2'b00};
          hdr   <= {16'h4e6f, 8'h10, 8'h44, 32'd0, 8'h00, be, rn, 8'h00, ret};
          rto   <= 24'd0;
          st    <= S_RDY;
        end else begin
          nxt <= S_RADDR;
          st  <= S_GET;
        end
      end
    end

    S_RDY: begin
      rto <= rto + 24'd1;
      if (grant) begin
        st <= S_REQ;
      end else if (&rto) begin               // no send slot for a long time: give up
        if (~&n_drop) n_drop <= n_drop + 32'd1;
        st <= ctx ? S_CTXD : S_DONE;
      end
    end

    S_REQ: begin
      if (tx_enable) begin
        if (ctx) begin
          tx_d  <= rp_q;
          hleft <= 4'd0;
        end else begin
          tx_d  <= hdr[127:120];
          hdr   <= {hdr[119:0], 8'h00};
          hleft <= probe ? 4'd7 : 4'd15;
        end
        left  <= rlen - 16'd1;
        st    <= S_SEND;
      end
    end

    S_SEND: begin
      if (left == 16'd0) begin
        holdoff <= 3'd7;
        st      <= ctx ? S_CTXD : S_DONE;
      end else begin
        left <= left - 16'd1;
        if (hleft != 4'd0) begin
          tx_d  <= hdr[127:120];
          hdr   <= {hdr[119:0], 8'h00};
          hleft <= hleft - 4'd1;
        end else begin
          tx_d  <= rp_q;
        end
      end
    end

    S_DROP: begin
      if (~&n_drop) n_drop <= n_drop + 32'd1;
      st <= S_DONE;
    end

    S_DONE: begin
      nxt <= S_IDLE;
      ack <= 1'b1;
      st  <= S_ACK;
    end

    S_ACK: begin
      if (~pend_c) begin
        ack <= 1'b0;
        st  <= S_IDLE;
      end
    end

    default: st <= S_IDLE;
  endcase
end

assign wb_stb     = wb_cyc;
assign busy       = (st == S_REQ) | (st == S_SEND);
assign tx_request = (st == S_REQ) ? 2'b01 : 2'b00;
assign tx_length  = rlen;
assign tx_data    = tx_d;

logic [31:0] drops_c;
cdc_word #(.W(32)) cdc_drops_i (.clk_a(clk_rx), .d_a(drops_rx), .clk_b(clk), .q_b(drops_c));

assign stats = {n_req, n_drop + drops_c, n_berr};

endmodule


//////////////////////////////////////////////////////////////////////////////
// Register block (Wishbone slave, clk domain). Byte addresses; see docs/rawfront/PROTOCOL.md for the map.
// Unmapped addresses and writes to read-only registers answer with an error.

module hl2bus_regs #(
  parameter [7:0]  VERSION_MAJOR = 8'd0,
  parameter [7:0]  VERSION_MINOR = 8'd0,
  parameter [7:0]  DIAG_ID       = 8'd0,
  parameter [15:0] CAPS          = 16'd0
) (
  input                clk          ,
  input         [29:0] wb_adr       ,
  input         [31:0] wb_dat_w     ,
  output logic  [31:0] wb_dat_r = 32'd0,
  input         [ 3:0] wb_sel       ,
  input                wb_we        ,
  input                wb_cyc       ,
  input                wb_stb       ,
  output logic         wb_ack = 1'b0,
  output logic         wb_err = 1'b0,
  input         [95:0] bridge_stats ,
  input         [ 7:0] tx_status    ,     // clk domain
  input         [52:0] ctrl_status  ,     // clk domain: {inputs[4:0], temperature, fwd, rev, bias}
  input         [ 5:0] cmd_addr     ,     // command bus (clk domain)
  input         [31:0] cmd_data     ,
  input                cmd_rqst     ,
  output logic         inj_req  = 1'b0,
  output        [ 5:0] inj_addr     ,
  output logic  [31:0] inj_data = 32'd0,
  input                inj_ack          // synced to clk
);

localparam [31:0] ID = 32'h484c3242;      // "HL2B"
localparam [7:0]  MAP_VERSION = 8'h01;

// word addresses (byte address / 4)
localparam [29:0] A_ID      = 30'h1000_0000;   // 0x4000_0000
localparam [29:0] A_VERSION = 30'h1000_0001;   // 0x4000_0004
localparam [29:0] A_SCRATCH = 30'h1000_0002;   // 0x4000_0008
localparam [29:0] A_CAPS    = 30'h1000_0003;   // 0x4000_000C
localparam [29:0] A_EB_REQ  = 30'h1000_0004;   // 0x4000_0010
localparam [29:0] A_EB_DROP = 30'h1000_0005;   // 0x4000_0014
localparam [29:0] A_EB_BERR = 30'h1000_0006;   // 0x4000_0018
localparam [29:0] A_RXGAIN  = 30'h1000_0800;   // 0x4000_2000
localparam [29:0] A_TEMP    = 30'h1000_0c00;   // 0x4000_3000
localparam [29:0] A_FWD     = 30'h1000_0c01;   // 0x4000_3004
localparam [29:0] A_REV     = 30'h1000_0c02;   // 0x4000_3008
localparam [29:0] A_BIAS    = 30'h1000_0c03;   // 0x4000_300C
localparam [29:0] A_INPUTS  = 30'h1000_1000;   // 0x4000_4000
localparam [29:0] A_TXSTAT  = 30'h1000_1c00;   // 0x4000_7000

logic [31:0] scratch  = 32'h12345678;
logic [ 6:0] rxg_seen = 7'd0;
logic        rxg_valid = 1'b0;
logic [ 6:0] rxg_new  = 7'd0;
logic        inj_pend = 1'b0;

assign inj_addr = 6'h0a;

wire acc = wb_cyc & wb_stb & ~wb_ack & ~wb_err;

logic        hit;
logic        wr_ok;
logic [31:0] rdata;
always @* begin
  hit   = 1'b1;
  wr_ok = 1'b0;
  rdata = 32'd0;
  case (wb_adr)
    A_ID:      rdata = ID;
    A_VERSION: rdata = {VERSION_MAJOR, VERSION_MINOR, DIAG_ID, MAP_VERSION};
    A_SCRATCH: begin rdata = scratch; wr_ok = 1'b1; end
    A_CAPS:    rdata = {16'd0, CAPS};
    A_EB_REQ:  rdata = bridge_stats[95:64];
    A_EB_DROP: rdata = bridge_stats[63:32];
    A_EB_BERR: rdata = bridge_stats[31:0];
    A_RXGAIN:  begin rdata = {inj_req | inj_pend, 22'd0, rxg_valid, 1'b0, rxg_seen}; wr_ok = 1'b1; end
    A_TEMP:    rdata = {20'd0, ctrl_status[47:36]};
    A_FWD:     rdata = {20'd0, ctrl_status[35:24]};
    A_REV:     rdata = {20'd0, ctrl_status[23:12]};
    A_BIAS:    rdata = {20'd0, ctrl_status[11:0]};
    A_INPUTS:  rdata = {27'd0, ctrl_status[52:48]};
    A_TXSTAT:  rdata = {24'd0, tx_status};
    default:   hit = 1'b0;
  endcase
end

always @(posedge clk) begin
  wb_ack <= acc & hit & (~wb_we | wr_ok);
  wb_err <= acc & ~(hit & (~wb_we | wr_ok));
  if (acc) wb_dat_r <= rdata;

  if (cmd_rqst & (cmd_addr == 6'h0a)) begin
    rxg_seen  <= cmd_data[6:0];
    rxg_valid <= 1'b1;
  end

  // RX gain injection through cmd_merge (4-phase handshake, data stable while inj_req)
  if (inj_req & inj_ack) inj_req <= 1'b0;
  if (~inj_req & ~inj_ack & inj_pend) begin
    inj_data <= {25'd0, rxg_new};
    inj_req  <= 1'b1;
    inj_pend <= 1'b0;
  end

  if (acc & wb_we & wr_ok) begin
    case (wb_adr)
      A_SCRATCH: begin
        if (wb_sel[3]) scratch[31:24] <= wb_dat_w[31:24];
        if (wb_sel[2]) scratch[23:16] <= wb_dat_w[23:16];
        if (wb_sel[1]) scratch[15:8]  <= wb_dat_w[15:8];
        if (wb_sel[0]) scratch[7:0]   <= wb_dat_w[7:0];
      end
      A_RXGAIN: begin
        if (wb_sel[0]) begin
          rxg_new  <= wb_dat_w[6:0];
          inj_pend <= 1'b1;
        end
      end
      default: ;
    endcase
  end
end

endmodule


//////////////////////////////////////////////////////////////////////////////
// Command-bus merge (clk = the dsopenhpsdr1 domain, Ethernet receive clock).
// PC commands are forwarded at once, unchanged in order and spacing (one register stage).
// A bridge command is inserted only after QUIET cycles without a PC command. If a PC command
// follows within GUARD cycles (the slowest command consumer, clk_ctrl at 2.5 MHz, may not have
// read the bridge command's data yet) the bridge command is sent again later; it must be
// idempotent (RX gain is). The acknowledge returns only after a clean insertion.
// Two requesters: port 1 (hl2bus_regs, RX gain) and port 2 (rtl/hl2io.v command injector, raw
// front-end image; unconnected elsewhere). Port 1 goes first when both wait.

module cmd_merge #(
  parameter QUIET = 1024,
  parameter GUARD = 512
) (
  input                clk        ,
  input         [ 5:0] ds_addr    ,
  input         [31:0] ds_data    ,
  input                ds_cnt     ,
  input                ds_is_alt  ,
  input                ds_resprqst,
  input                inj_req    ,     // other domain, level
  input         [ 5:0] inj_addr   ,     // stable while inj_req
  input         [31:0] inj_data   ,
  output logic         inj_ack  = 1'b0,
  input                inj2_req   ,     // other domain, level (tie 0 when unused)
  input         [ 5:0] inj2_addr  ,
  input         [31:0] inj2_data  ,
  output logic         inj2_ack = 1'b0,
  output logic  [ 5:0] addr     = 6'd0,
  output logic  [31:0] data     = 32'd0,
  output logic         cnt      = 1'b0,
  output logic         is_alt   = 1'b0,
  output logic         resprqst = 1'b0
);

(* preserve *) logic [1:0] req_s = 2'b00;
(* preserve *) logic [1:0] req2_s = 2'b00;
logic        cur2     = 1'b0;               // the insertion being guarded is port 2's
logic        ds_seen  = 1'b0;
logic [10:0] quiet    = 11'd0;
logic [ 9:0] guard    = 10'd0;
logic        guarding = 1'b0;
logic        collide  = 1'b0;

always @(posedge clk) begin
  req_s  <= {req_s[0], inj_req};
  req2_s <= {req2_s[0], inj2_req === 1'b1};
  if (~req_s[1])  inj_ack  <= 1'b0;
  if (~req2_s[1]) inj2_ack <= 1'b0;

  if (guard != 10'd0) guard <= guard - 10'd1;
  else if (guarding) begin
    guarding <= 1'b0;
    collide  <= 1'b0;
    if (~collide) begin
      if (cur2) inj2_ack <= 1'b1;
      else      inj_ack  <= 1'b1;
    end
  end

  if (ds_cnt != ds_seen) begin
    ds_seen  <= ds_cnt;
    addr     <= ds_addr;
    data     <= ds_data;
    is_alt   <= ds_is_alt;
    resprqst <= ds_resprqst;
    cnt      <= ~cnt;
    quiet    <= 11'd0;
    if (guarding) collide <= 1'b1;
  end else begin
    if (quiet != QUIET[10:0]) quiet <= quiet + 11'd1;
    if (~guarding & (quiet == QUIET[10:0])) begin
      if (req_s[1] & ~inj_ack) begin
        addr     <= inj_addr;
        data     <= inj_data;
        cur2     <= 1'b0;
        is_alt   <= 1'b0;
        resprqst <= 1'b0;
        cnt      <= ~cnt;
        guard    <= GUARD[9:0];
        guarding <= 1'b1;
      end else if (req2_s[1] & ~inj2_ack) begin
        addr     <= inj2_addr;
        data     <= inj2_data;
        cur2     <= 1'b1;
        is_alt   <= 1'b0;
        resprqst <= 1'b0;
        cnt      <= ~cnt;
        guard    <= GUARD[9:0];
        guarding <= 1'b1;
      end
    end
  end
end

endmodule
