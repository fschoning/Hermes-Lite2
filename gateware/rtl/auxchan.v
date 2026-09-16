// SPDX-License-Identifier: GPL-2.0-or-later
// Copyright 2026 Franz Schöning, https://www.schoning.com
//
// Aux data channel for the raw stream test image (test gateware)
//
// Bidirectional byte channel in its own UDP packets on port 1027, carried in the gaps of
// the raw sample stream. See docs/rawfront/PROTOCOL.md for the packet layouts.
//
//   PC -> radio  Aux packets (magic 0x5B) are parsed in the Ethernet receive domain. The
//                payload is checked against the aux byte pattern (lost packets, bad bytes)
//                and, while echo is on, written into a small dual-clock FIFO.
//   radio -> PC  Aux packets (magic 0xB5) carry the echo bytes read back out of that FIFO,
//                then bytes of a radio-generated counter stream at a commanded rate, behind a
//                44-byte header with the receive checker's counters.
//
// Clock domains
//   clk_rx  Ethernet receive clock: parser, checker, FIFO write side, receive counters
//   clk     125 MHz Ethernet send clock: command register 0x32, planner, packet builder,
//           FIFO read side
//
// Send priority (arbiter in rawstream.v)
//   Raw sample frames first, then openHPSDR replies (discovery, commands), aux last. The
//   arbiter grants aux only when no raw frame is due, and rawstream.v reports "room": the
//   largest aux UDP payload that can be on the wire before the next raw frame becomes due.
//   This module only plans packets that fit that room, so an aux packet does not delay a
//   raw frame (except by the few clock cycles of the hand-over).
//
// Aux byte pattern (both directions): the byte at stream offset o is byte (o mod 4) of the
// big-endian 32-bit word floor(o / 4). Any 8 consecutive bytes give their own offset, so a
// receiver can resynchronise after a gap.

module auxchan #(
  parameter FIFO_AW = 12,                    // echo FIFO depth = 2**FIFO_AW bytes
  parameter PORT    = 16'd1027,
  parameter MAX_PAY = 16'd1400,              // largest radio -> PC aux UDP payload, header included
  parameter MIN_PAY = 16'd256                // smallest full packet sent without waiting
) (
  // Ethernet receive domain (from network.v / udp_recv)
  input                clk_rx          ,
  input         [15:0] eth_port        ,
  input                eth_broadcast   ,
  input                eth_valid       ,
  input         [ 7:0] eth_data        ,
  // Ethernet send domain
  input                clk             ,
  input         [ 5:0] cmd_addr        ,
  input         [31:0] cmd_data        ,
  input                cmd_rqst        ,
  input                dest_valid      ,     // network.v: the PC's aux socket address is known
  input                raw_active      ,     // raw stream running (header flag only)
  input         [15:0] room            ,     // rawstream.v: largest aux UDP payload that fits now
  output logic         ready           ,     // a packet is planned; the arbiter may grant it
  input                grant           ,     // arbiter: aux owns the send path from the next cycle
  output        [ 1:0] tx_request      ,
  output        [15:0] tx_length       ,
  output        [ 7:0] tx_data         ,
  input                tx_enable       ,     // network.v udp2_tx_enable while aux owns the path
  output               busy                  // packet requested or on the wire
);

localparam CMD_ADDR = 6'h32;
localparam MAGIC_RX = 8'h5b;                 // PC -> radio
localparam MAGIC_TX = 8'hb5;                 // radio -> PC
localparam VERSION  = 8'h01;
localparam HDR_LEN  = 16'd44;

//////////////////////////////////////////////////////////////////////////////
// Command register 0x32 (clk domain)

logic        cfg_on   = 1'b0;
logic        cfg_echo = 1'b0;
logic        cfg_cnt  = 1'b0;
logic [15:0] cfg_rate = 16'd0;               // counter stream, bytes per millisecond

always @(posedge clk) begin
  if (cmd_rqst & (cmd_addr == CMD_ADDR)) begin
    cfg_on   <= cmd_data[0];
    cfg_echo <= cmd_data[1];
    cfg_cnt  <= cmd_data[2];
    cfg_rate <= cmd_data[31:16];
  end
end

logic act = 1'b0;
always @(posedge clk) act <= cfg_on;

//////////////////////////////////////////////////////////////////////////////
// Receive side (clk_rx domain)

(* preserve *) logic [1:0] act_rx_s  = 2'b00;
(* preserve *) logic [1:0] echo_rx_s = 2'b00;
always @(posedge clk_rx) begin
  act_rx_s  <= {act_rx_s[0],  act};
  echo_rx_s <= {echo_rx_s[0], act & cfg_echo};
end
wire act_rx  = act_rx_s[1];
wire echo_rx = echo_rx_s[1];

logic        v_r     = 1'b0;
logic [ 7:0] d_r     = 8'h00;
logic        port_ok = 1'b0;
always @(posedge clk_rx) begin
  v_r     <= eth_valid;
  d_r     <= eth_data;
  port_ok <= (eth_port == PORT) & ~eth_broadcast;
end

logic        take     = 1'b0;                // current packet is a PC aux packet
logic        hello    = 1'b0;                // flags bit 0: address announcement, not counted
logic [ 3:0] hcnt     = 4'd0;
logic        in_pay   = 1'b0;
logic [23:0] sh       = 24'd0;               // header field shift register
logic [31:0] seq_rx   = 32'd0;
logic        seq_stb  = 1'b0;
logic [15:0] pay_left = 16'd0;
logic        pay_nz   = 1'b0;
logic [29:0] pw       = 30'd0;               // pattern word of the next payload byte
logic [ 1:0] pp       = 2'd0;                // byte position in that word
logic [31:0] exp_seq  = 32'd0;
logic        have_seq = 1'b0;
logic [31:0] diff     = 32'd0;
logic        diff_stb = 1'b0;

logic [31:0] rx_pkts  = 32'd0;
logic [31:0] rx_lost  = 32'd0;
logic [31:0] rx_bad   = 32'd0;
logic [31:0] rx_bytes = 32'd0;
logic [15:0] rx_ovf   = 16'd0;
logic        ovf_act  = 1'b0;

logic        chk_stb  = 1'b0;                // payload byte to check (pipelined)
logic [ 7:0] chk_d    = 8'h00;
logic [ 7:0] chk_e    = 8'h00;

logic        wr_en    = 1'b0;
logic [ 7:0] wr_d     = 8'h00;
logic        wr_full;
wire         wr_req   = wr_en & ~wr_full;

logic [ 7:0] exp_byte;
always @* begin
  case (pp)
    2'd0:    exp_byte = {2'b00, pw[29:24]};
    2'd1:    exp_byte = pw[23:16];
    2'd2:    exp_byte = pw[15:8];
    default: exp_byte = pw[7:0];
  endcase
end

always @(posedge clk_rx) begin
  wr_en    <= 1'b0;
  seq_stb  <= 1'b0;
  diff_stb <= 1'b0;
  chk_stb  <= 1'b0;

  if (~v_r) begin
    take   <= act_rx & port_ok;
    hcnt   <= 4'd0;
    in_pay <= 1'b0;
  end else if (take) begin
    if (~in_pay) begin
      hcnt <= hcnt + 4'd1;
      sh   <= {sh[15:0], d_r};
      case (hcnt)
        4'd0:  if (d_r != MAGIC_RX) take <= 1'b0;
        4'd1:  if (d_r != VERSION)  take <= 1'b0;
        4'd2:  hello <= d_r[0];
        4'd7:  begin seq_rx <= {sh, d_r}; seq_stb <= ~hello; end
        4'd11: begin pw <= {sh[23:0], d_r[7:2]}; pp <= d_r[1:0]; end
        4'd13: begin pay_left <= {sh[7:0], d_r}; pay_nz <= ({sh[7:0], d_r} != 16'd0); end
        4'd15: in_pay <= 1'b1;
        default: ;
      endcase
    end else if (pay_nz & ~hello) begin
      pay_left <= pay_left - 16'd1;
      pay_nz   <= (pay_left != 16'd1);
      chk_stb  <= 1'b1;
      chk_d    <= d_r;
      chk_e    <= exp_byte;
      pp       <= pp + 2'd1;
      if (pp == 2'd3) pw <= pw + 30'd1;
      wr_en    <= echo_rx;
      wr_d     <= d_r;
    end
  end

  if (chk_stb) begin
    rx_bytes <= rx_bytes + 32'd1;
    if ((chk_d != chk_e) & ~&rx_bad) rx_bad <= rx_bad + 32'd1;
  end

  // Echo FIFO overflow: one event per aux packet that lost bytes
  if (~v_r) ovf_act <= 1'b0;
  if (wr_en & wr_full) begin
    ovf_act <= 1'b1;
    if (~ovf_act & ~&rx_ovf) rx_ovf <= rx_ovf + 16'd1;
  end

  // Sequence numbers: gaps are lost packets, a lower number only resynchronises
  if (seq_stb) begin
    rx_pkts  <= rx_pkts + 32'd1;
    exp_seq  <= seq_rx + 32'd1;
    have_seq <= 1'b1;
    diff     <= seq_rx - exp_seq;
    diff_stb <= have_seq;
  end
  if (diff_stb & ~diff[31]) rx_lost <= rx_lost + diff;

  if (~act_rx) begin
    take     <= 1'b0;
    have_seq <= 1'b0;
    diff_stb <= 1'b0;
    chk_stb  <= 1'b0;
    rx_pkts  <= 32'd0;
    rx_lost  <= 32'd0;
    rx_bad   <= 32'd0;
    rx_bytes <= 32'd0;
    rx_ovf   <= 16'd0;
    ovf_act  <= 1'b0;
  end
end

//////////////////////////////////////////////////////////////////////////////
// Echo FIFO

logic [7:0]       rd_q;
logic             rd_empty;
logic [FIFO_AW:0] rd_used;
logic             rd_req;

dcfifo #(
  .intended_device_family("Cyclone IV E"),
  .lpm_numwords          (1 << FIFO_AW ),
  .lpm_showahead         ("ON"         ),
  .lpm_type              ("dcfifo"     ),
  .lpm_width             (8            ),
  .lpm_widthu            (FIFO_AW+1    ),
  .add_usedw_msb_bit     ("ON"         ),
  .overflow_checking     ("ON"         ),
  .underflow_checking    ("ON"         ),
  .rdsync_delaypipe      (4            ),
  .wrsync_delaypipe      (4            ),
  .use_eab               ("ON"         )
) fifo_i (
  .aclr   (1'b0    ),
  .wrclk  (clk_rx  ),
  .wrreq  (wr_req  ),
  .data   (wr_d    ),
  .wrfull (wr_full ),
  .wrempty(        ),
  .wrusedw(        ),
  .rdclk  (clk     ),
  .rdreq  (rd_req  ),
  .q      (rd_q    ),
  .rdempty(rd_empty),
  .rdfull (        ),
  .rdusedw(rd_used )
);

//////////////////////////////////////////////////////////////////////////////
// Receive counters to the clk domain

logic [143:0] st_rx;
cdc_word #(.W(144)) cdc_rx_i (
  .clk_a(clk_rx), .d_a({rx_pkts, rx_lost, rx_bad, rx_bytes, rx_ovf}),
  .clk_b(clk),    .q_b(st_rx)
);

//////////////////////////////////////////////////////////////////////////////
// Send side (clk domain)

localparam A_IDLE = 2'd0, A_REQ = 2'd1, A_SEND = 2'd2;

logic [ 1:0] state    = A_IDLE;
logic [ 2:0] holdoff  = 3'd0;                // planner outputs are stale for a few cycles after a send

// 1 ms tick and counter stream credit
logic [16:0] tick_cnt = 17'd0;
logic        tick     = 1'b0;
logic [16:0] credit   = 17'd0;
localparam [16:0] CREDIT_CAP = 17'd65535;
logic        tick_pend = 1'b0;
wire  [17:0] cred_sum = {1'b0, credit} + {2'b00, cfg_rate};

// Waiting time of the oldest unsent byte, in microseconds
logic [ 6:0] us_cnt   = 7'd0;
logic        us_tick  = 1'b0;
logic [15:0] wait_us  = 16'd0;
logic [ 1:0] age_ms   = 2'd0;
logic [15:0] starve   = 16'd0;               // packets whose bytes waited 10 ms or more

// Planner pipeline
logic [15:0] p_avail  = 16'd0;               // stage A
logic [15:0] p_lim    = 16'd0;
logic [16:0] p_cred   = 17'd0;
logic [15:0] p_e      = 16'd0;               // stage B
logic [15:0] p_left   = 16'd0;
logic [16:0] p_cred2  = 17'd0;
logic [15:0] p_lim2   = 16'd0;
logic [15:0] p_lim3   = 16'd0;
logic [15:0] p_e2     = 16'd0;               // stage C
logic [15:0] p_c2     = 16'd0;
logic [15:0] p_tot    = 16'd0;
logic        pending  = 1'b0;                // bytes waiting (echo or credit)

logic [31:0] seq      = 32'd0;
logic [31:0] e_off    = 32'd0;
logic [31:0] c_off    = 32'd0;
logic [15:0] len_r    = 16'd0;
logic [351:0] hdr     = 352'd0;
logic [ 5:0] hleft    = 6'd0;
logic        h_nz     = 1'b0;
logic [15:0] e_left   = 16'd0;
logic        e_nz     = 1'b0;
logic [15:0] c_left   = 16'd0;
logic        c_nz     = 1'b0;
logic [29:0] cw       = 30'd0;
logic [ 1:0] cpos     = 2'd0;
logic [ 7:0] tx_d     = 8'h00;

logic [ 7:0] c_byte;
always @* begin
  case (cpos)
    2'd0:    c_byte = {2'b00, cw[29:24]};
    2'd1:    c_byte = cw[23:16];
    2'd2:    c_byte = cw[15:8];
    default: c_byte = cw[7:0];
  endcase
end

wire [15:0] lim_room = (room > MAX_PAY) ? MAX_PAY : room;

always @* begin
  if (state == A_SEND) rd_req = ~h_nz & e_nz;
  else                 rd_req = ~act & ~rd_empty;          // aux off: drain what is left
end

always @(posedge clk) begin
  // ---- time base ----
  tick <= 1'b0;
  if (tick_cnt == 17'd124999) begin tick_cnt <= 17'd0; tick <= 1'b1; end
  else tick_cnt <= tick_cnt + 17'd1;
  us_tick <= 1'b0;
  if (us_cnt == 7'd124) begin us_cnt <= 7'd0; us_tick <= 1'b1; end
  else us_cnt <= us_cnt + 7'd1;

  // ---- planner, stage A ----
  p_avail <= (act & cfg_echo) ? {{(15-FIFO_AW){1'b0}}, rd_used} : 16'd0;
  p_lim   <= (lim_room > HDR_LEN) ? (lim_room - HDR_LEN) : 16'd0;
  p_cred  <= (act & cfg_cnt) ? credit : 17'd0;
  // ---- stage B ----
  if (p_avail < p_lim) begin p_e <= p_avail; p_left <= p_lim - p_avail; end
  else                 begin p_e <= p_lim;   p_left <= 16'd0;           end
  p_cred2 <= p_cred;
  p_lim2  <= p_lim;
  pending <= (p_avail != 16'd0) | (p_cred != 17'd0);
  // ---- stage C ----
  p_e2   <= p_e;
  p_lim3 <= p_lim2;
  if (p_cred2 < {1'b0, p_left}) begin p_c2 <= p_cred2[15:0]; p_tot <= p_e + p_cred2[15:0]; end
  else                          begin p_c2 <= p_left;        p_tot <= p_e + p_left;        end

  // ---- waiting time ----
  if ((state == A_IDLE) & pending) begin
    if (us_tick & ~&wait_us) wait_us <= wait_us + 16'd1;
    if (tick & ~&age_ms)     age_ms  <= age_ms + 2'd1;
  end

  if (holdoff != 3'd0) holdoff <= holdoff - 3'd1;

  // Send a packet when it is full (as large as the room allows, at least MIN_PAY bytes), or
  // when bytes have waited 1-2 ms. Keeps the packet rate down when the link is idle.
  ready <= act & dest_valid & (state == A_IDLE) & (holdoff == 3'd0) & ~grant &
           (((p_tot >= MIN_PAY) & (p_tot == p_lim3)) | ((p_tot != 16'd0) & age_ms[1]));

  // ---- credit ----
  // A tick that coincides with a grant is applied one cycle later.
  if (tick) tick_pend <= 1'b1;
  if (~act | ~cfg_cnt) begin
    credit    <= 17'd0;
    tick_pend <= 1'b0;
  end else if (grant) begin
    credit <= credit - {1'b0, p_c2};
  end else if (tick_pend) begin
    tick_pend <= tick;
    credit    <= (cred_sum > {1'b0, CREDIT_CAP}) ? CREDIT_CAP : cred_sum[16:0];
  end

  case (state)
    A_IDLE: begin
      if (grant) begin
        hdr <= {MAGIC_TX, VERSION, 4'b0000, raw_active, cfg_cnt, cfg_echo, act, 8'h00,
                seq, e_off, p_e2, c_off, p_c2, st_rx[143:16], st_rx[15:0],
                {{(15-FIFO_AW){1'b0}}, rd_used}, wait_us, starve};
        len_r   <= HDR_LEN + p_tot;
        e_left  <= p_e2;
        e_nz    <= (p_e2 != 16'd0);
        c_left  <= p_c2;
        c_nz    <= (p_c2 != 16'd0);
        cw      <= c_off[31:2];
        cpos    <= c_off[1:0];
        seq     <= seq + 32'd1;
        e_off   <= e_off + {16'd0, p_e2};
        c_off   <= c_off + {16'd0, p_c2};
        if ((wait_us >= 16'd10000) & ~&starve) starve <= starve + 16'd1;
        wait_us <= 16'd0;
        age_ms  <= 2'd0;
        state   <= A_REQ;
      end
    end

    A_REQ: begin
      if (tx_enable) begin
        tx_d  <= hdr[351:344];
        hdr   <= {hdr[343:0], 8'h00};
        hleft <= 6'd43;
        h_nz  <= 1'b1;
        state <= A_SEND;
      end
    end

    A_SEND: begin
      if (h_nz) begin
        tx_d  <= hdr[351:344];
        hdr   <= {hdr[343:0], 8'h00};
        hleft <= hleft - 6'd1;
        h_nz  <= (hleft != 6'd1);
      end else if (e_nz) begin
        tx_d   <= rd_q;
        e_left <= e_left - 16'd1;
        e_nz   <= (e_left != 16'd1);
      end else if (c_nz) begin
        tx_d   <= c_byte;
        cpos   <= cpos + 2'd1;
        if (cpos == 2'd3) cw <= cw + 30'd1;
        c_left <= c_left - 16'd1;
        c_nz   <= (c_left != 16'd1);
      end else begin
        holdoff <= 3'd7;
        state   <= A_IDLE;
      end
    end

    default: state <= A_IDLE;
  endcase

  if (~act) begin
    seq     <= 32'd0;
    e_off   <= 32'd0;
    c_off   <= 32'd0;
    starve  <= 16'd0;
    wait_us <= 16'd0;
    age_ms  <= 2'd0;
  end
end

assign busy       = (state != A_IDLE);
assign tx_request = (state == A_REQ) ? 2'b01 : 2'b00;
assign tx_length  = len_r;
assign tx_data    = tx_d;

endmodule
