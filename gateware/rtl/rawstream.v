// SPDX-License-Identifier: GPL-2.0-or-later
// Copyright 2026 Franz Schöning, https://www.schoning.com
//
// Raw ADC stream sender (test gateware)
//
// Sends every 12-bit AD9866 sample, or a test pattern, as UDP frames through the
// existing HL2 network stack. See docs/rawfront/PROTOCOL.md for the
// command register and the frame layout.
//
// Clock domains
//   clk_ad  76.8 MHz AD9866 clock: pattern mux and FIFO write side
//   clk     125 MHz Ethernet TX clock: command decode, FIFO read side, frame
//           builder and the arbiter that shares the UDP send path with the
//           openHPSDR packer (usopenhpsdr1)
//
// Arbitration with the openHPSDR packer
//   The packer keeps its request asserted until it sees udp_tx_enable, so it can
//   wait for any time. The select register raw_sel only changes at a "safe" cycle:
//   the network is idle (no frame latched, starting or on the wire) and the
//   current owner is not requesting or sending. A packer request always wins,
//   so discovery, command responses and flash-programming replies still go out
//   between raw frames.
//
// Overflow handling
//   The write side never drops single samples. When the FIFO is full it stops
//   writing (hold) and keeps counting samples. The read side sends the complete
//   frames that are left, discards the remainder, then does a resync handshake:
//   the write side returns the index of the next sample it writes, so the
//   48-bit sample index in the frame header stays exact across every gap.
//   Quiet-capture mode uses the same mechanism on purpose: nothing is sent while
//   the FIFO fills, then the whole block is sent while writing is held.
//
// Duplex header (DUPLEX=1, docs/rawfront/PROTOCOL.md)
//   While dup_on is set, each frame carries version 0x02 and a 40-byte header: the
//   20 bytes above plus the 20-byte TX sink status word dup_status (rtl/txsink.v).
//
// Aux channel (AUX=1, docs/rawfront/PROTOCOL.md)
//   A third sender, rtl/auxchan.v, shares the send path at the lowest priority. It is
//   granted only while no raw frame is due, and aux_room tells it the largest UDP payload
//   that is on the wire before the next frame becomes due, so it never delays a raw frame
//   by more than the hand-over. With AUX=0 the aux inputs are ignored.
//
// Echo and 48-byte duplex header (ECHO=1, docs/rawfront/PROTOCOL.md)
//   While dup_on is set, frames carry version 0x03 and a 48-byte header: the 40 bytes above, then the
//   echo offset (TX sample index minus RX sample index of the echoed samples, 48-bit two's complement),
//   a flags byte (bit 0 offset valid) and the transmit interlock trip byte (ext_status). With echo on,
//   the samples written into the FIFO are the TX samples the duplex sink plays (rtl/txsink.v).
//
// Transmit-safety status (header byte 3, was 0)
//   tx_status is copied into every frame header when the frame is built, so the far side
//   sees transmit state and input changes within one frame even without any processor.

module rawstream #(
  parameter FIFO_AW = 14,                    // FIFO depth = 2**FIFO_AW samples
  parameter MAX_N_OVERRIDE = 0,              // 0 = largest N from the FIFO depth rule below
  parameter DUPLEX  = 0,                     // 1 = 40-byte header with TX sink status while dup_on
  parameter AUX     = 0,                     // 1 = share the send path with rtl/auxchan.v
  parameter ECHO    = 0                      // 1 = echo samples, 48-byte header while dup_on
) (
  // AD9866 domain
  input               clk_ad          ,
  input        [11:0] adc_data        ,
  // Ethernet TX domain
  input               clk             ,
  input               run             ,       // openHPSDR run, synced to clk
  input        [ 5:0] cmd_addr        ,
  input        [31:0] cmd_data        ,
  input               cmd_rqst        ,
  output              raw_mode        ,       // command 0x30 bit 0
  // openHPSDR packer side
  input        [ 1:0] pkt_tx_request  ,
  input        [15:0] pkt_tx_length   ,
  input        [ 7:0] pkt_tx_data     ,
  output              pkt_tx_enable   ,
  // network side
  output       [ 1:0] udp_tx_request  ,
  output       [15:0] udp_tx_length   ,
  output       [ 7:0] udp_tx_data     ,
  input               udp_tx_enable   ,
  input               udp0_tx_enable  ,
  input               udp_tx_busy     ,
  // duplex TX sink status (clk domain), unused when DUPLEX = 0
  input               dup_on          ,
  input       [159:0] dup_status      ,
  // transmit-safety status byte, header byte 3 (clk domain, quasi-static; docs/rawfront/PROTOCOL.md)
  input        [ 7:0] tx_status       ,
  // aux channel (clk domain), unused when AUX = 0
  output       [15:0] aux_room        ,       // largest aux UDP payload that fits before the next frame
  output              raw_run         ,       // raw streaming active
  input               aux_ready       ,
  output              aux_grant       ,
  input        [ 1:0] aux_tx_request  ,
  input        [15:0] aux_tx_length   ,
  input        [ 7:0] aux_tx_data     ,
  input               aux_busy        ,
  input               udp2_tx_enable  ,       // network.v: aux (port 1027) packet starts
  output              aux_enable      ,
  // echo (ECHO = 1)
  input               echo_on         ,       // clk: txsink register 0x31 bit 2
  input        [11:0] echo_data       ,       // clk_ad
  input        [47:0] echo_idx        ,       // clk_ad
  input               echo_ok         ,       // clk_ad
  input               echo_play       ,       // clk_ad: a TX sample was played (echo_ok: with a known index)
  input        [15:0] ext_status              // clk: header bytes 46 (bits 7:1) and 47
);

localparam DEPTH     = 1 << FIFO_AW;
// Largest frame: the FIFO must hold one frame plus the ~0.92 samples that arrive
// for every sample sent while that frame is on the wire.
localparam MAX_N     = (MAX_N_OVERRIDE != 0) ? MAX_N_OVERRIDE : (DEPTH * 15) / 32;
localparam DEFAULT_N = 968;                  // fits a 1500-byte IP MTU

localparam CMD_ADDR  = 6'h30;

//////////////////////////////////////////////////////////////////////////////
// Command register 0x30 (clk domain)

logic        cfg_mode    = 1'b0;
logic        cfg_pattern = 1'b0;
logic        cfg_quiet   = 1'b0;
logic [15:0] cfg_n       = DEFAULT_N;

logic [15:0] req_n;
always @* begin
  req_n = {cmd_data[31:17], 1'b0};           // even number of samples
  if (req_n == 16'd0)       req_n = DEFAULT_N;
  else if (req_n > MAX_N)   req_n = MAX_N[15:0];
end

always @(posedge clk) begin
  if (cmd_rqst & (cmd_addr == CMD_ADDR)) begin
    cfg_mode    <= cmd_data[0];
    cfg_pattern <= cmd_data[1];
    cfg_quiet   <= cmd_data[2];
    cfg_n       <= req_n;
  end
end

assign raw_mode = cfg_mode;

logic raw_active = 1'b0;
always @(posedge clk) raw_active <= cfg_mode & run;

//////////////////////////////////////////////////////////////////////////////
// Write side (clk_ad domain)

logic        rs_req = 1'b0;                  // resync request, clk domain

(* preserve *) logic [1:0] en_ad_s  = 2'b00;
(* preserve *) logic [1:0] pat_ad_s = 2'b00;
(* preserve *) logic [1:0] req_ad_s = 2'b00;
(* preserve *) logic [1:0] echo_ad_s = 2'b00;

always @(posedge clk_ad) begin
  en_ad_s  <= {en_ad_s[0],  raw_active };
  pat_ad_s <= {pat_ad_s[0], cfg_pattern};
  req_ad_s <= {req_ad_s[0], rs_req     };
  echo_ad_s <= {echo_ad_s[0], echo_on & (ECHO != 0)};
end
wire echo_ad = echo_ad_s[1];

wire en_ad  = en_ad_s[1];
wire pat_ad = pat_ad_s[1];
wire req_ad = req_ad_s[1];

logic [47:0] wr_idx     = 48'd0;
logic [47:0] resume_idx = 48'd0;
logic        wr_hold    = 1'b1;
logic        wr_ack     = 1'b0;
logic [11:0] wr_data;
logic        wr_full;
logic        wr_req;

always @(posedge clk_ad) begin
  if (~en_ad) begin
    wr_idx  <= 48'd0;
    wr_hold <= 1'b1;
    wr_ack  <= 1'b0;
  end else begin
    wr_idx <= wr_idx + 48'd1;
    if (req_ad & wr_hold & ~wr_ack) begin
      // Next cycle's sample is the first one written
      resume_idx <= wr_idx + 48'd1;
      wr_hold    <= 1'b0;
      wr_ack     <= 1'b1;
    end else begin
      if (~req_ad) wr_ack <= 1'b0;
      if (~wr_hold & wr_full) wr_hold <= 1'b1;
    end
  end
end

// Test pattern: the low 12 bits of the sample index, so a receiver can check
// every sample against the index in the frame header.
assign wr_data = echo_ad ? echo_data : pat_ad ? wr_idx[11:0] : adc_data;

// echo offset: TX index minus RX index of the sample written this cycle
logic [48:0] echo_off_ad = 49'd0;
logic [48:0] echo_off;                       // clk: {valid, offset}
generate if (ECHO != 0) begin: ECHO_OFF
  always @(posedge clk_ad) begin
    if (echo_ok & echo_ad & en_ad)  echo_off_ad <= {1'b1, echo_idx - wr_idx};
    else if (~echo_ad | ~en_ad)     echo_off_ad <= 49'd0;
    else if (echo_play & ~echo_ok)  echo_off_ad[48] <= 1'b0;     // played, index not known yet
  end
  cdc_word #(.W(49)) cdc_echo_off_i (.clk_a(clk_ad), .d_a(echo_off_ad), .clk_b(clk), .q_b(echo_off));
end else begin: NO_ECHO_OFF
  assign echo_off = 49'd0;
end endgenerate
assign wr_req  = en_ad & ~wr_hold & ~wr_full;

//////////////////////////////////////////////////////////////////////////////
// FIFO

logic [11:0]      rd_q;
logic             rd_empty;
logic [FIFO_AW:0] rd_used;
logic             rd_req;

dcfifo #(
  .intended_device_family("Cyclone IV E"),
  .lpm_numwords          (DEPTH        ),
  .lpm_showahead         ("ON"         ),
  .lpm_type              ("dcfifo"     ),
  .lpm_width             (12           ),
  .lpm_widthu            (FIFO_AW+1    ),
  .add_usedw_msb_bit     ("ON"         ),
  .overflow_checking     ("ON"         ),
  .underflow_checking    ("ON"         ),
  .rdsync_delaypipe      (4            ),
  .wrsync_delaypipe      (4            ),
  .use_eab               ("ON"         )
) fifo_i (
  .aclr   (1'b0    ),
  .wrclk  (clk_ad  ),
  .wrreq  (wr_req  ),
  .data   (wr_data ),
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
// Read side (clk domain)

(* preserve *) logic [1:0] hold_s = 2'b11;
(* preserve *) logic [1:0] ack_s  = 2'b00;

always @(posedge clk) begin
  hold_s <= {hold_s[0], wr_hold};
  ack_s  <= {ack_s[0],  wr_ack };
end

wire hold_rd = hold_s[1];
wire ack_rd  = ack_s[1];

localparam R_OFF   = 4'd0,
           R_SYNC  = 4'd1,
           R_SYNC2 = 4'd2,
           R_IDLE  = 4'd3,
           R_WAIT  = 4'd4,
           R_REQ   = 4'd5,
           R_SEND  = 4'd6,
           R_FLUSH = 4'd7;

logic [ 3:0] state      = R_OFF;
logic [ 4:0] empty_cnt  = 5'd0;              // consecutive cycles with FIFO empty
logic [ 1:0] settle     = 2'd0;
logic        fill_ge_n  = 1'b0;
logic        hold_prev  = 1'b1;

logic [31:0] seq        = 32'd0;
logic [47:0] idx        = 48'd0;
logic [15:0] ovf_cnt    = 16'd0;
logic [15:0] high_water = 16'd0;
logic        flag_ovf   = 1'b0;
logic        flag_first = 1'b0;
logic        flag_gap   = 1'b0;
logic        clip_acc   = 1'b0;              // clipped sample in the frame being sent
logic        clip_prev  = 1'b0;              // ... in the previous frame

logic [15:0] n_cur      = DEFAULT_N;
logic [15:0] raw_len    = 16'd0;
logic [383:0] hdr       = 384'd0;
logic [15:0] byte_left  = 16'd0;
logic        byte_nz    = 1'b0;              // byte_left != 0
logic [ 5:0] hdr_cnt    = 6'd0;
wire         dup_frame  = (DUPLEX != 0) & dup_on;
wire  [15:0] hdr_bytes  = ~dup_frame ? 16'd20 : (ECHO != 0) ? 16'd48 : 16'd40;
logic        in_samp    = 1'b0;              // hdr_cnt == 0
logic [ 1:0] phase      = 2'd0;
logic [ 7:0] tx_d       = 8'd0;
logic [ 3:0] lo4        = 4'd0;
logic [ 7:0] lo8        = 8'd0;

logic        hdr_last   = 1'b0;              // frame being built has the 40-byte header
// Send path owner
localparam O_PKT = 2'd0, O_RAW = 2'd1, O_AUX = 2'd2;
logic [ 1:0] own        = O_PKT;
wire         raw_sel    = (own == O_RAW);
wire         aux_sel    = (own == O_AUX);
logic        raw_enable;
logic        grant;
logic        grant_aux;
logic        safe;

wire drained = empty_cnt[4];
wire clip_q  = (rd_q == 12'h7ff) | (rd_q == 12'h800);

always @* begin
  case (state)
    R_OFF, R_FLUSH: rd_req = ~rd_empty;
    R_SEND:         rd_req = byte_nz & in_samp & (phase != 2'd2);
    default:        rd_req = 1'b0;
  endcase
end

always @(posedge clk) begin
  fill_ge_n <= (rd_used >= {1'b0, cfg_n[FIFO_AW-1:0]});
  hold_prev <= hold_rd;

  if (rd_empty) begin
    if (~drained) empty_cnt <= empty_cnt + 5'd1;
  end else begin
    empty_cnt <= 5'd0;
  end

  if (state != R_OFF) begin
    if (rd_used > high_water[FIFO_AW:0]) high_water <= {{(15-FIFO_AW){1'b0}}, rd_used};
  end

  // FIFO overflow events (quiet-capture mode fills the FIFO on purpose)
  if ((state >= R_IDLE) & hold_rd & ~hold_prev & ~cfg_quiet) begin
    flag_ovf <= 1'b1;
    if (~&ovf_cnt) ovf_cnt <= ovf_cnt + 16'd1;
  end

  case (state)
    R_OFF: begin
      rs_req <= 1'b0;
      if (raw_active & drained & hold_rd & ~ack_rd) begin
        seq        <= 32'd0;
        ovf_cnt    <= 16'd0;
        high_water <= 16'd0;
        flag_ovf   <= 1'b0;
        flag_first <= 1'b1;
        flag_gap   <= 1'b0;
        clip_acc   <= 1'b0;
        clip_prev  <= 1'b0;
        rs_req     <= 1'b1;
        state      <= R_SYNC;
      end
    end

    R_SYNC: begin
      if (~raw_active) begin
        rs_req <= 1'b0;
        state  <= R_OFF;
      end else if (ack_rd) begin
        // resume_idx was set together with wr_ack and is stable by now
        idx    <= resume_idx;
        rs_req <= 1'b0;
        state  <= R_SYNC2;
      end
    end

    R_SYNC2: begin
      if (~raw_active) begin
        state <= R_OFF;
      end else if (~ack_rd) begin
        settle <= 2'd0;
        state  <= R_IDLE;
      end
    end

    R_IDLE: begin
      if (~&settle) begin
        settle <= settle + 2'd1;             // let rd_used and fill_ge_n catch up
      end else if (~raw_active) begin
        state <= R_OFF;
      end else if ((~cfg_quiet | hold_rd) & fill_ge_n) begin
        n_cur   <= cfg_n;
        raw_len <= hdr_bytes + cfg_n + {1'b0, cfg_n[15:1]};
        hdr     <= {8'ha5, (~dup_frame ? 8'h01 : (ECHO != 0) ? 8'h03 : 8'h02),
                    2'b00, flag_gap, flag_first, (cfg_quiet & hold_rd), clip_prev, flag_ovf, cfg_pattern,
                    tx_status, seq, idx, cfg_n, ovf_cnt, high_water,
                    (dup_frame ? dup_status : 160'd0),
                    ((dup_frame & (ECHO != 0)) ? {echo_off[47:0], ext_status[15:9], echo_off[48], ext_status[7:0]} : 64'd0)};
        hdr_last <= dup_frame;
        state   <= R_WAIT;
      end else if (hold_rd) begin
        state   <= R_FLUSH;                  // overflow, or quiet block sent
      end
    end

    R_WAIT: begin
      if (grant) state <= R_REQ;
      else if (~raw_active) state <= R_OFF;
    end

    R_REQ: begin
      if (raw_enable) begin
        tx_d      <= hdr[383:376];
        hdr       <= {hdr[375:0], 8'h00};
        hdr_cnt   <= ~hdr_last ? 6'd19 : (ECHO != 0) ? 6'd47 : 6'd39;
        in_samp   <= 1'b0;
        byte_left <= raw_len - 16'd1;
        byte_nz   <= 1'b1;
        phase     <= 2'd0;
        state     <= R_SEND;
      end
    end

    R_SEND: begin
      if (~byte_nz) begin
        seq        <= seq + 32'd1;
        idx        <= idx + {32'd0, n_cur};
        flag_first <= 1'b0;
        flag_gap   <= 1'b0;
        clip_prev  <= clip_acc;
        clip_acc   <= 1'b0;
        settle     <= 2'd0;
        state      <= R_IDLE;
      end else begin
        byte_left <= byte_left - 16'd1;
        byte_nz   <= (byte_left != 16'd1);
        if (~in_samp) begin
          tx_d    <= hdr[383:376];
          hdr     <= {hdr[375:0], 8'h00};
          hdr_cnt <= hdr_cnt - 6'd1;
          in_samp <= (hdr_cnt == 6'd1);
        end else begin
          case (phase)
            2'd0: begin
              tx_d     <= rd_q[11:4];
              lo4      <= rd_q[3:0];
              clip_acc <= clip_acc | clip_q;
              phase    <= 2'd1;
            end
            2'd1: begin
              tx_d     <= {lo4, rd_q[11:8]};
              lo8      <= rd_q[7:0];
              clip_acc <= clip_acc | clip_q;
              phase    <= 2'd2;
            end
            default: begin
              tx_d     <= lo8;
              phase    <= 2'd0;
            end
          endcase
        end
      end
    end

    R_FLUSH: begin
      if (~raw_active) begin
        state <= R_OFF;
      end else if (drained) begin
        flag_gap <= 1'b1;
        rs_req   <= 1'b1;
        state    <= R_SYNC;
      end
    end

    default: state <= R_OFF;
  endcase
end

//////////////////////////////////////////////////////////////////////////////
// Aux room: the largest aux UDP payload that is completely on the wire before the next
// raw frame becomes due. While the sender waits for the FIFO to reach N samples, the
// remaining (N - fill) samples arrive in (N - fill) / 76.8 MSPS; one byte of line time is
// 8 ns = 0.6144 samples, so (N - fill) samples are 1.6276 bytes. Use 1.625 bytes, keep a
// 32-sample margin (the fill value, the aux planner and the hand-over lag by about 10 clock
// cycles = 6 samples), and subtract 80 bytes for the UDP, IP and Ethernet headers, CRC,
// preamble, inter-frame gap and hand-over (66 bytes plus a few cycles).

logic [16:0] rm_s   = 17'd0;
logic [16:0] rm_b   = 17'd0;
logic        rm_ok  = 1'b0;
logic [15:0] room_r = 16'd0;

always @(posedge clk) begin
  rm_s  <= {1'b0, cfg_n} - {{(16-FIFO_AW){1'b0}}, rd_used} - 17'd32;
  rm_ok <= (state == R_IDLE) & ~fill_ge_n & ~cfg_quiet;
  rm_b  <= rm_s[16] ? 17'd0 : ({1'b0, rm_s[15:0]} + {2'b00, rm_s[15:1]} + {4'b0000, rm_s[15:3]});
  if (state == R_OFF)                   room_r <= 16'hffff;   // no sample stream running
  else if (~rm_ok | (rm_b < 17'd81))    room_r <= 16'd0;
  else if (rm_b > 17'h1004f)            room_r <= 16'hffff;
  else                                  room_r <= rm_b[15:0] - 16'd80;
end

assign aux_room = (AUX != 0) ? room_r : 16'd0;
assign raw_run  = raw_active;

//////////////////////////////////////////////////////////////////////////////
// Arbiter and send path mux
//
// Priority at a safe cycle: openHPSDR packer, then raw frames, then aux. Aux is granted only
// when no raw frame is due (sender idle below N samples, or not streaming).

wire raw_busy = (state == R_REQ) | (state == R_SEND);
wire raw_quiet = (state == R_OFF) | ((state == R_IDLE) & ~fill_ge_n & (&settle));

assign safe      = ~udp_tx_busy & (raw_sel ? ~raw_busy :
                                   aux_sel ? ~aux_busy : (pkt_tx_request == 2'b00));
assign grant     = safe & (pkt_tx_request == 2'b00) & (state == R_WAIT);
assign grant_aux = (AUX != 0) & safe & (pkt_tx_request == 2'b00) & raw_quiet & aux_ready;

always @(posedge clk) begin
  if (safe) own <= grant ? O_RAW : (grant_aux ? O_AUX : O_PKT);
end

assign aux_grant      = grant_aux;
assign raw_enable     = udp0_tx_enable & raw_sel;
assign aux_enable     = udp2_tx_enable & aux_sel;
assign pkt_tx_enable  = udp_tx_enable & (own == O_PKT);

assign udp_tx_request = raw_sel ? ((state == R_REQ) ? 2'b10 : 2'b00) : aux_sel ? aux_tx_request : pkt_tx_request;
assign udp_tx_length  = raw_sel ? raw_len : aux_sel ? aux_tx_length : pkt_tx_length;
assign udp_tx_data    = raw_sel ? tx_d    : aux_sel ? aux_tx_data   : pkt_tx_data;

endmodule
