// SPDX-License-Identifier: GPL-2.0-or-later
// Copyright 2026 Franz Schöning, https://www.schoning.com
//
// Duplex raw stream: PC -> HL2 "TX sample" sink with a virtual DAC (test gateware)
//
// Receives TX frames (UDP port 1026) from the HL2 network receive path, writes the
// 12-bit samples into a dual-clock FIFO, and drains that FIFO at exactly one sample
// per AD9866 clock (76.8 MSPS) into a virtual DAC. Nothing is sent to the real AD9866
// transmit DAC, the PA or the T/R relay. See docs/rawfront/PROTOCOL.md.
//
// Clock domains
//   clk_rx  Ethernet receive clock (from the PHY): TX frame parser, FIFO write side,
//           frame / lost-frame / overflow counters
//   clk_ad  76.8 MHz AD9866 clock: FIFO read side, virtual DAC, pattern checker,
//           underflow counter
//   clk     125 MHz Ethernet TX clock: command register 0x31, status snapshot for the
//           raw stream frame header
//
// Checker
//   The PC sends the counter pattern: sample k of a frame whose header says first
//   index I is (I + k) mod 4096. Each FIFO word carries a resync bit. It is set on the
//   first sample written after start, after a sequence number gap, and after a FIFO
//   overflow dropped samples. At the DAC the expected value is loaded from a resync
//   sample and then advances by one per sample; every mismatch counts one bad sample.
//   After 4 mismatches in a row the checker re-locks to the received value, so an
//   unflagged jump costs 4 bad samples instead of all that follow.

// Raw front-end image (ECHO = 1, docs/rawfront/PROTOCOL.md)
//   Register 0x31 bit 1 "real DAC": the played samples go to the AD9866 transmit DAC (dac_out, zero when
//   nothing is played); hermeslite_core.v passes them on only while the transmit interlock enables the
//   DAC. Bit 2 "echo": the played samples go into the raw receive stream instead of the ADC
//   (rtl/rawstream.v), with their TX sample index, and the DAC is never driven (bit 1 is ignored).
//   TX index tracking: the receive side records the TX index of every sample written with the resync
//   bit (frame index + position) and passes (resync count, index) to the AD9866 domain; the DAC side
//   counts the resync samples it plays, loads the index when the counts match (also when the index
//   arrives a few samples later) and then counts up per played sample.

module txsink #(
  parameter FIFO_AW = 14,                    // FIFO depth = 2**FIFO_AW samples
  parameter PORT    = 16'd1026,
  parameter ECHO    = 0                      // 1 = real DAC output, echo mode, TX index tracking
) (
  // Ethernet RX domain (from network.v / udp_recv)
  input                clk_rx          ,
  input         [15:0] eth_port        ,
  input                eth_broadcast   ,
  input                eth_valid       ,
  input         [ 7:0] eth_data        ,
  // AD9866 domain
  input                clk_ad          ,
  // Ethernet TX domain
  input                clk             ,
  input                raw_mode        ,     // register 0x30 bit 0
  input                run             ,     // openHPSDR run, synced to clk
  input         [ 5:0] cmd_addr        ,
  input         [31:0] cmd_data        ,
  input                cmd_rqst        ,
  output logic         dup_on          ,     // register 0x31 bit 0
  output        [159:0] status          ,     // snapshot for the raw frame header
  // ECHO = 1
  output               mode_real       ,     // clk: register 0x31 bit 1 and not echo
  output               mode_echo       ,     // clk: register 0x31 bit 2
  output logic  [11:0] dac_out   = 12'd0,    // clk_ad: sample played this cycle, 0 when none (real mode only)
  output logic  [11:0] echo_data = 12'd0,    // clk_ad: sample played this cycle, 0 when none
  output logic  [47:0] echo_idx  = 48'd0,    // clk_ad: its TX sample index
  output logic         echo_ok   = 1'b0,     // clk_ad: a sample was played and its index is known
  output logic         echo_play = 1'b0      // clk_ad: a sample was played (index known or not)
);

localparam DEPTH    = 1 << FIFO_AW;
localparam CMD_ADDR = 6'h31;
localparam MAGIC    = 8'h5a;
localparam VERSION  = 8'h01;

//////////////////////////////////////////////////////////////////////////////
// Command register 0x31 (clk domain)

initial dup_on = 1'b0;
logic cfg_real = 1'b0, cfg_echo = 1'b0;
always @(posedge clk) begin
  if (cmd_rqst & (cmd_addr == CMD_ADDR)) begin
    dup_on   <= cmd_data[0];
    cfg_real <= cmd_data[1] & ~cmd_data[2] & (ECHO != 0);
    cfg_echo <= cmd_data[2] & (ECHO != 0);
  end
end
assign mode_real = cfg_real;
assign mode_echo = cfg_echo;

logic act = 1'b0;                            // TX sink active: duplex on while raw streaming
always @(posedge clk) act <= dup_on & raw_mode & run;

//////////////////////////////////////////////////////////////////////////////
// Receive side (clk_rx domain)

(* preserve *) logic [1:0] act_rx_s = 2'b00;
always @(posedge clk_rx) act_rx_s <= {act_rx_s[0], act};
wire act_rx = act_rx_s[1];

// Input pipeline: keeps the added load off the network receive path
logic        v_r      = 1'b0;
logic [ 7:0] d_r      = 8'h00;
logic        port_ok  = 1'b0;
always @(posedge clk_rx) begin
  v_r     <= eth_valid;
  d_r     <= eth_data;
  port_ok <= (eth_port == PORT) & ~eth_broadcast;
end

logic        take     = 1'b0;                // current packet is a TX frame
logic [ 3:0] hcnt     = 4'd0;                // header byte index 0..15
logic        in_pay   = 1'b0;
logic [ 1:0] ph       = 2'd0;
logic [ 7:0] b0       = 8'h00;
logic [ 3:0] lo4      = 4'h0;
logic [23:0] seq_hi   = 24'd0;
logic [31:0] seq_rx   = 32'd0;
logic        seq_stb  = 1'b0;
logic [31:0] exp_seq  = 32'd0;
logic        have_seq = 1'b0;
logic [31:0] diff     = 32'd0;
logic        diff_stb = 1'b0;

logic [47:0] frm_idx  = 48'd0;               // ECHO: TX index of the next sample written
logic [47:0] rs_idx   = 48'd0;               // ECHO: TX index of the last resync sample written
logic [15:0] rs_n     = 16'd0;               // ECHO: resync samples written (16 bits: a full FIFO that drops every
                                             // other sample writes thousands of resync samples per TX frame)

logic [31:0] rx_frames = 32'd0;
logic [31:0] rx_lost   = 32'd0;
logic [15:0] ovf_cnt   = 16'd0;
logic        ovf_act   = 1'b0;
logic        resync    = 1'b1;

logic        wr_en    = 1'b0;
logic [11:0] wr_d     = 12'h000;
logic        wr_full;
wire         wr_req   = wr_en & ~wr_full;

always @(posedge clk_rx) begin
  wr_en    <= 1'b0;
  seq_stb  <= 1'b0;
  diff_stb <= 1'b0;

  if (~v_r) begin
    take   <= act_rx & port_ok;
    hcnt   <= 4'd0;
    in_pay <= 1'b0;
    ph     <= 2'd0;
  end else if (take) begin
    if (~in_pay) begin
      hcnt <= hcnt + 4'd1;
      if (hcnt == 4'd15) in_pay <= 1'b1;
      case (hcnt)
        4'd0: if (d_r != MAGIC)   take <= 1'b0;
        4'd1: if (d_r != VERSION) take <= 1'b0;
        4'd4, 4'd5, 4'd6: seq_hi <= {seq_hi[15:0], d_r};
        4'd7: begin seq_rx <= {seq_hi, d_r}; seq_stb <= 1'b1; end
        4'd8, 4'd9, 4'd10, 4'd11, 4'd12, 4'd13: if (ECHO != 0) frm_idx <= {frm_idx[39:0], d_r};
        default: ;
      endcase
    end else begin
      case (ph)
        2'd0: begin b0 <= d_r; ph <= 2'd1; end
        2'd1: begin wr_d <= {b0, d_r[7:4]}; lo4 <= d_r[3:0]; wr_en <= 1'b1; ph <= 2'd2; end
        default: begin wr_d <= {lo4, d_r}; wr_en <= 1'b1; ph <= 2'd0; end
      endcase
    end
  end

  // FIFO write and overflow. A full FIFO drops samples. While it stays full the DAC frees
  // one slot per AD9866 clock, so drops and writes alternate: count one overflow event per
  // TX frame that lost samples (ovf_act is cleared between packets).
  if (~v_r) ovf_act <= 1'b0;
  if ((ECHO != 0) & wr_en) begin
    frm_idx <= frm_idx + 48'd1;
    if (~wr_full & resync) begin
      rs_idx <= frm_idx;
      rs_n   <= rs_n + 16'd1;
    end
  end

  if (wr_en) begin
    if (wr_full) begin
      resync  <= 1'b1;
      ovf_act <= 1'b1;
      if (~ovf_act & ~&ovf_cnt) ovf_cnt <= ovf_cnt + 16'd1;
    end else begin
      resync  <= 1'b0;
    end
  end

  // Sequence numbers (header byte 7 is long before the first sample write)
  if (seq_stb) begin
    rx_frames <= rx_frames + 32'd1;
    exp_seq   <= seq_rx + 32'd1;
    have_seq  <= 1'b1;
    diff      <= seq_rx - exp_seq;
    diff_stb  <= have_seq;
    if (~have_seq | (seq_rx != exp_seq)) resync <= 1'b1;
  end
  if (diff_stb & ~diff[31]) rx_lost <= rx_lost + diff;   // negative = reordered/duplicate

  if (~act_rx) begin
    rs_n      <= 16'd0;
    take      <= 1'b0;
    have_seq  <= 1'b0;
    rx_frames <= 32'd0;
    rx_lost   <= 32'd0;
    ovf_cnt   <= 16'd0;
    ovf_act   <= 1'b0;
    resync    <= 1'b1;
    diff_stb  <= 1'b0;
  end
end

//////////////////////////////////////////////////////////////////////////////
// FIFO

logic [12:0]      rd_q;
logic             rd_empty;
logic [FIFO_AW:0] rd_used;
logic             rd_req;

dcfifo #(
  .intended_device_family("Cyclone IV E"),
  .lpm_numwords          (DEPTH        ),
  .lpm_showahead         ("ON"         ),
  .lpm_type              ("dcfifo"     ),
  .lpm_width             (13           ),
  .lpm_widthu            (FIFO_AW+1    ),
  .add_usedw_msb_bit     ("ON"         ),
  .overflow_checking     ("ON"         ),
  .underflow_checking    ("ON"         ),
  .rdsync_delaypipe      (4            ),
  .wrsync_delaypipe      (4            ),
  .use_eab               ("ON"         )
) fifo_i (
  .aclr   (1'b0            ),
  .wrclk  (clk_rx          ),
  .wrreq  (wr_req          ),
  .data   ({resync, wr_d}  ),
  .wrfull (wr_full         ),
  .wrempty(                ),
  .wrusedw(                ),
  .rdclk  (clk_ad          ),
  .rdreq  (rd_req          ),
  .q      (rd_q            ),
  .rdempty(rd_empty        ),
  .rdfull (                ),
  .rdusedw(rd_used         )
);

//////////////////////////////////////////////////////////////////////////////
// Virtual DAC and checker (clk_ad domain)

(* preserve *) logic [1:0] act_ad_s = 2'b00;
always @(posedge clk_ad) act_ad_s <= {act_ad_s[0], act};
wire act_ad = act_ad_s[1];

localparam D_OFF = 2'd0, D_PRE = 2'd1, D_RUN = 2'd2;

logic [ 1:0] dstate    = D_OFF;
logic        half      = 1'b0;               // rd_used >= DEPTH/2
logic [15:0] fill      = 16'd0;
logic [11:0] dac       = 12'h000;            // virtual DAC output register
logic [11:0] expv      = 12'h000;
logic        have_exp  = 1'b0;
logic [ 1:0] miss      = 2'd0;
logic [31:0] bad_cnt   = 32'd0;
logic [15:0] unf_cnt   = 16'd0;

always @* begin
  case (dstate)
    D_OFF:   rd_req = ~rd_empty;             // drain what is left from the last run
    D_RUN:   rd_req = ~rd_empty;
    default: rd_req = 1'b0;
  endcase
end

wire take_sample = (dstate == D_RUN) & ~rd_empty;

// ECHO: TX index of the played samples
logic [63:0] rs_c;                           // {rs_n, rs_idx} in the AD9866 domain
logic [15:0] rs_seen = 16'd0;
logic [15:0] since   = 16'd0;                // samples played since the last resync sample, inclusive
logic [47:0] play_idx = 48'd0;               // TX index of the next sample played, while idx_ok
logic        idx_ok  = 1'b0;
logic        real_ad = 1'b0, echo_ad = 1'b0;
generate if (ECHO != 0) begin: ECHO_CDC
  cdc_word #(.W(64)) cdc_rs_i (.clk_a(clk_rx), .d_a({rs_n, rs_idx}), .clk_b(clk_ad), .q_b(rs_c));
  (* preserve *) logic [1:0] real_s = 2'b00, echo_s = 2'b00;
  always @(posedge clk_ad) begin
    real_s <= {real_s[0], cfg_real};
    echo_s <= {echo_s[0], cfg_echo};
    real_ad <= real_s[1];
    echo_ad <= echo_s[1];
  end

  always @(posedge clk_ad) begin
    echo_ok   <= 1'b0;
    echo_play <= take_sample & echo_ad;
    echo_data <= 12'd0;
    dac_out   <= 12'd0;
    if (take_sample) begin
      echo_data <= echo_ad ? rd_q[11:0] : 12'd0;
      dac_out   <= (real_ad & ~echo_ad) ? rd_q[11:0] : 12'd0;
    end

    if (dstate == D_OFF) begin
      rs_seen <= 16'd0;
      idx_ok  <= 1'b0;
    end else if (take_sample & rd_q[12]) begin
      // a resync sample: its index is rs_c when this is the resync sample the receive side counted last
      rs_seen <= rs_seen + 16'd1;
      since   <= 16'd1;
      if (rs_c[63:48] == rs_seen + 16'd1) begin
        echo_idx <= rs_c[47:0];
        echo_ok  <= 1'b1;
        play_idx <= rs_c[47:0] + 48'd1;
        idx_ok   <= 1'b1;
      end else begin
        idx_ok   <= 1'b0;
      end
    end else begin
      if (take_sample & ~&since) since <= since + 16'd1;
      if (idx_ok) begin
        if (take_sample) begin
          echo_idx <= play_idx;
          echo_ok  <= 1'b1;
          play_idx <= play_idx + 48'd1;
        end
      end else if ((rs_c[63:48] == rs_seen) & (rs_seen != 16'd0) & ~&since) begin
        // the index arrived after its sample was played: catch up
        play_idx <= rs_c[47:0] + {32'd0, since} + {47'd0, take_sample};
        idx_ok   <= 1'b1;
        if (take_sample) begin
          echo_idx <= rs_c[47:0] + {32'd0, since};
          echo_ok  <= 1'b1;
        end
      end
    end
  end
end else begin: NO_ECHO
  assign rs_c = 64'd0;
end endgenerate

always @(posedge clk_ad) begin
  half <= rd_used[FIFO_AW] | rd_used[FIFO_AW-1];
  fill <= {{(15-FIFO_AW){1'b0}}, rd_used};

  case (dstate)
    D_OFF: begin
      have_exp <= 1'b0;
      miss     <= 2'd0;
      bad_cnt  <= 32'd0;
      unf_cnt  <= 16'd0;
      if (act_ad) dstate <= D_PRE;
    end
    D_PRE: begin
      if (~act_ad)   dstate <= D_OFF;
      else if (half) dstate <= D_RUN;
    end
    D_RUN: begin
      if (~act_ad) begin
        dstate <= D_OFF;
      end else if (rd_empty) begin
        if (~&unf_cnt) unf_cnt <= unf_cnt + 16'd1;
        dstate <= D_PRE;                     // refill to half before playing again
      end
    end
    default: dstate <= D_OFF;
  endcase

  if (take_sample) begin
    dac <= rd_q[11:0];
    if (rd_q[12] | ~have_exp | (&miss & (rd_q[11:0] != expv))) begin
      expv     <= rd_q[11:0] + 12'd1;
      have_exp <= 1'b1;
      miss     <= 2'd0;
      if (have_exp & ~rd_q[12] & ~&bad_cnt) bad_cnt <= bad_cnt + 32'd1;
    end else begin
      expv <= expv + 12'd1;
      if (rd_q[11:0] != expv) begin
        miss <= miss + 2'd1;
        if (~&bad_cnt) bad_cnt <= bad_cnt + 32'd1;
      end else begin
        miss <= 2'd0;
      end
    end
  end
end

//////////////////////////////////////////////////////////////////////////////
// Status to the clk domain

logic [79:0] st_rx;
logic [64:0] st_ad;

cdc_word #(.W(80)) cdc_rx_i (
  .clk_a(clk_rx), .d_a({rx_frames, rx_lost, ovf_cnt}),
  .clk_b(clk),    .q_b(st_rx)
);

cdc_word #(.W(65)) cdc_ad_i (
  .clk_a(clk_ad), .d_a({bad_cnt, fill, unf_cnt, (dstate == D_RUN)}),
  .clk_b(clk),    .q_b(st_ad)
);

//   [159:128] TX frames received     [127:96] TX lost frames
//   [ 95: 64] TX bad samples         [ 63:48] TX FIFO fill
//   [ 47: 32] TX underflow events    [ 31:16] TX overflow events
//   [ 15:  8] status flags: bit 0 duplex active, bit 1 virtual DAC playing
//   [  7:  0] 0
assign status = {st_rx[79:48], st_rx[47:16], st_ad[64:33], st_ad[32:17], st_ad[16:1], st_rx[15:0],
                 4'b0000, cfg_echo, cfg_real, st_ad[0] & act, act, 8'h00};

endmodule


// Multi-bit clock domain crossing by request/acknowledge handshake. The source holds
// the word stable from the request toggle until the acknowledge returns, so the
// destination never samples a changing word. Updates every ~6 destination cycles.
module cdc_word #(
  parameter W = 8
) (
  input                clk_a,
  input        [W-1:0] d_a,
  input                clk_b,
  output logic [W-1:0] q_b
);

logic [W-1:0] hold = '0;
logic         req  = 1'b0;
logic         ack  = 1'b0;
(* preserve *) logic [1:0] ack_s = 2'b00;
(* preserve *) logic [1:0] req_s = 2'b00;

initial q_b = '0;

always @(posedge clk_a) begin
  ack_s <= {ack_s[0], ack};
  if (req == ack_s[1]) begin
    hold <= d_a;
    req  <= ~req;
  end
end

always @(posedge clk_b) begin
  req_s <= {req_s[0], req};
  if (req_s[1] != ack) begin
    q_b <= hold;
    ack <= req_s[1];
  end
end

endmodule
