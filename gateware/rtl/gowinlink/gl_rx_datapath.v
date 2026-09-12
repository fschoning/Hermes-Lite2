//
//  gl_rx_datapath.v — Gowin receive data plane, lane clock domain (153.6 MHz for
//  LANES = 3, 76.8 MHz for LANES = 6). See LINK_SPEC.md section 6.
//
//  Per lane: 16-bit bit history from the IDDR pair, PRBS-23 self-synchronising checker.
//  Word tick (every B/2 cycles): per-lane offset extraction (word alignment + gearbox),
//  descrambler, counter check. Measurement engine, alignment search and accumulators are
//  driven from the 50 MHz control plane through toggles ('*_t') with static side data.
//
//  IDDR pair order: q1 is assumed to be the older bit (Gowin simulation model). If the
//  silicon delivers the pair the other way round, 'pair_swap' = 1 fixes it; the trainer
//  tries both orders.
//
module gl_rx_datapath #(
  parameter integer LANES = 3
) (
  input                      clk,
  input  [LANES-1:0]         q0,
  input  [LANES-1:0]         q1,
  input                      pair_swap,
  output reg [8*LANES-1:0]   tap = {(8*LANES){1'b0}},
  // measurement transaction
  input  [8*LANES-1:0]       tap_val,
  input                      meas_start_t,
  input  [4:0]               meas_len_log2,
  input  [1:0]               meas_kind,       // 0 PRBS mismatches, 1 ALIGN word errors, 2 COUNTER word errors
  output reg                 meas_done_t = 1'b0,
  output reg [16*LANES-1:0]  meas_err  = {(16*LANES){1'b0}},
  output reg [15:0]          meas_werr = 16'd0,
  // alignment transaction
  input                      align_start_t,
  output reg                 align_done_t = 1'b0,
  output reg                 align_ok     = 1'b0,
  output reg [1:0]           align_fail   = 2'd0,   // 1 no phase found, 2 offset out of range
  output reg [4*LANES-1:0]   off   = {(4*LANES){1'b0}},
  output reg [4*LANES-1:0]   phase = {(4*LANES){1'b0}},
  // continuous operation
  input                      descr_en,
  input                      acc_prbs_en,
  input                      acc_wchk_en,
  input                      acc_clr_t,
  input                      snap_t,
  output reg                 snap_done_t = 1'b0,
  output reg [32*LANES-1:0]  snap_prbs  = {(32*LANES){1'b0}},
  output reg [47:0]          snap_bits  = 48'd0,
  output reg [39:0]          snap_words = 40'd0,
  output reg [31:0]          snap_werr  = 32'd0,
  output                     tick,
  output [11:0]              sample,
  output reg                 sample_valid = 1'b0,
  output reg                 alive = 1'b0,
  // optional SDR "serial" line sampled by the same DDR front end (one bit per word,
  // transitions at word boundaries): the sample in the middle of the word is picked
  // using lane 0's alignment offset
  input                      sdr_q0,
  input                      sdr_q1,
  output reg                 ser_bit   = 1'b1,
  output reg                 ser_valid = 1'b0
);

localparam integer B   = 12 / LANES;
localparam integer CPW = B / 2;
localparam [15:0] ALIGN_SEQ = 16'hF590;   // d_k = ALIGN_SEQ[k], d0 first

// ---------------------------------------------------------------- control pulses
wire meas_start, align_start, acc_clr, snap;
gl_tog2pulse s_meas  (.clk(clk), .t(meas_start_t),  .p(meas_start));
gl_tog2pulse s_align (.clk(clk), .t(align_start_t), .p(align_start));
gl_tog2pulse s_clr   (.clk(clk), .t(acc_clr_t),     .p(acc_clr));
gl_tog2pulse s_snap  (.clk(clk), .t(snap_t),        .p(snap));

// ---------------------------------------------------------------- word tick
reg wt = 1'b0;
always @(posedge clk) wt <= ~wt;
assign tick = (CPW == 1) ? 1'b1 : wt;
reg tick_d1 = 1'b0, tick_d2 = 1'b0;
always @(posedge clk) begin
  tick_d1 <= tick;
  tick_d2 <= tick_d1;
end

reg [7:0] alive_cnt = 8'd0;
always @(posedge clk) begin
  alive_cnt <= alive_cnt + 8'd1;
  alive     <= alive_cnt[7];
end

// ---------------------------------------------------------------- bit history, PRBS checkers
wire [LANES-1:0] bo = pair_swap ? q0 : q1;   // older bit of the pair
wire [LANES-1:0] bn = pair_swap ? q1 : q0;   // newer bit

reg  [16*LANES-1:0] hist = {(16*LANES){1'b0}};
reg  [23*LANES-1:0] prh  = {(23*LANES){1'b0}};
wire [LANES-1:0]    e0, e1;                   // PRBS mismatches per lane this cycle
reg  [2*LANES-1:0]  m;                        // 0..2 mismatches per lane, registered

genvar g;
generate
  for (g = 0; g < LANES; g = g + 1) begin : G_LANE
    always @(posedge clk) begin
      hist[16*g +: 16] <= {hist[16*g +: 14], bo[g], bn[g]};
      prh[23*g +: 23]  <= {prh[23*g +: 21], bo[g], bn[g]};
    end
    assign e0[g] = bo[g] ^ (prh[23*g+22] ^ prh[23*g+17]);
    assign e1[g] = bn[g] ^ (prh[23*g+21] ^ prh[23*g+16]);
    always @(posedge clk) m[2*g +: 2] <= {1'b0, e0[g]} + {1'b0, e1[g]};
  end
endgenerate

// ---------------------------------------------------------------- word extraction
reg  [11:0] word_al = 12'h000;
wire [11:0] word_ext;
generate
  for (g = 0; g < LANES; g = g + 1) begin : G_EXT
    wire [3:0] o = off[4*g +: 4];
    assign word_ext[B*g +: B] = hist[16*g + o +: B];
  end
endgenerate
always @(posedge clk) if (tick) word_al <= word_ext;

// serial (SDR) line: same history structure, pick the sample B/2 positions after the
// start of lane 0's word (hist[off0 + B - 1] is the first sample of the word)
reg  [15:0] shist = 16'hFFFF;
wire        sbo = pair_swap ? sdr_q0 : sdr_q1;
wire        sbn = pair_swap ? sdr_q1 : sdr_q0;
wire [3:0]  ssel = off[3:0] + (B / 2);
always @(posedge clk) begin
  shist <= {shist[13:0], sbo, sbn};
  if (tick) ser_bit <= shist[ssel];
  ser_valid <= tick;
end

// descrambler (one word latency, enabled in the cycle word_al is valid)
gowinlink_scrambler #(.DESCRAMBLE(1)) descr_i (
  .clk(clk), .en(tick_d1), .bypass(~descr_en), .din(word_al), .dout(sample)
);
always @(posedge clk) sample_valid <= tick_d2;

// counter check (on descrambled samples, valid at tick_d2)
reg [11:0] prev_sample = 12'h000;
reg        prev_valid  = 1'b0;
wire       cnt_err = prev_valid & (sample != prev_sample + 12'd1);

// alignment-pattern check (on raw aligned words, valid at tick_d1)
// window sync: the first 4 bits (4/B ticks) identify the phase, then compare
reg  [3:0] awin   = 4'h0;
reg  [1:0] awcnt  = 2'd0;      // groups collected so far (needs 4/B)
reg        asynced = 1'b0;
reg  [3:0] ai     = 4'h0;      // index in ALIGN_SEQ of the first bit of the next expected group
wire [3:0] awin_next = (B == 4) ? word_al[3:0] : {awin[1:0], word_al[1:0]};

function [3:0] seq_index;   // index k with {D[k],D[k+1],D[k+2],D[k+3]} == w
  input [3:0] w;
  integer k;
  reg [3:0] r;
  begin
    r = 4'h0;
    for (k = 0; k < 16; k = k + 1)
      if ({ALIGN_SEQ[k], ALIGN_SEQ[(k+1) & 15], ALIGN_SEQ[(k+2) & 15], ALIGN_SEQ[(k+3) & 15]} == w)
        r = k;
    seq_index = r;
  end
endfunction

reg [B-1:0] exp_grp;
integer bi;
always @* begin
  for (bi = 0; bi < B; bi = bi + 1)
    exp_grp[B-1-bi] = ALIGN_SEQ[(ai + bi) & 15];
end

reg align_err;
integer li;
always @* begin
  align_err = 1'b0;
  for (li = 0; li < LANES; li = li + 1)
    if (word_al[B*li +: B] != exp_grp) align_err = 1'b1;
end

// ---------------------------------------------------------------- measurement engine
localparam [1:0] M_IDLE = 2'd0, M_SETTLE = 2'd1, M_RUN = 2'd2;
reg [1:0]  mstate  = M_IDLE;
reg [5:0]  settle  = 6'd0;
reg [31:0] wcount  = 32'd0;
reg [4:0]  mlen    = 5'd0;
reg [1:0]  mkind   = 2'd0;
reg        wchk_first = 1'b0;

integer mi;
always @(posedge clk) begin
  case (mstate)
    M_IDLE: begin
      if (meas_start) begin
        tap    <= tap_val;
        mlen   <= meas_len_log2;
        mkind  <= meas_kind;
        settle <= 6'd0;
        mstate <= M_SETTLE;
      end
    end
    M_SETTLE: begin
      settle <= settle + 6'd1;
      if (settle == 6'd40) begin
        meas_err   <= {(16*LANES){1'b0}};
        meas_werr  <= 16'd0;
        wcount     <= 32'd0;
        awcnt      <= 2'd0;
        asynced    <= 1'b0;
        wchk_first <= 1'b1;
        mstate     <= M_RUN;
      end
    end
    M_RUN: begin
      // per-lane PRBS mismatches (every cycle)
      if (mkind == 2'd0) begin
        for (mi = 0; mi < LANES; mi = mi + 1)
          if (meas_err[16*mi +: 16] <= 16'hFFFD)
            meas_err[16*mi +: 16] <= meas_err[16*mi +: 16] + {14'd0, m[2*mi +: 2]};
      end
      // alignment word check (word_al valid at tick_d1)
      if (mkind == 2'd1 && tick_d1) begin
        if (!asynced) begin
          awin  <= awin_next;
          awcnt <= awcnt + 2'd1;
          if (awcnt == (4 / B) - 1) begin
            asynced <= 1'b1;
            ai      <= seq_index(awin_next) + 4'd4;
          end
        end else begin
          ai <= ai + B;
          if (align_err && meas_werr != 16'hFFFF) meas_werr <= meas_werr + 16'd1;
        end
      end
      // counter check (sample valid at tick_d2)
      if (mkind == 2'd2 && tick_d2) begin
        wchk_first <= 1'b0;
        if (!wchk_first && cnt_err && meas_werr != 16'hFFFF) meas_werr <= meas_werr + 16'd1;
      end
      if (tick_d1) begin
        wcount <= wcount + 32'd1;
        if (wcount == (32'd1 << mlen)) begin
          mstate      <= M_IDLE;
          meas_done_t <= ~meas_done_t;
        end
      end
    end
    default: mstate <= M_IDLE;
  endcase
end

// ---------------------------------------------------------------- alignment search
localparam [2:0] A_IDLE = 3'd0, A_SEARCH = 3'd1, A_CALC = 3'd2, A_ADJ = 3'd3, A_DONE = 3'd4;
reg [2:0]        astate = A_IDLE;
reg [6:0]        at     = 7'd0;                 // search tick counter
reg [LANES-1:0]  found  = {LANES{1'b0}};
reg [4*LANES-1:0] ph_r  = {(4*LANES){1'b0}};

// candidate phase at search tick 'at' for reference-phase candidate (at mod 16)
wire [3:0] cph = (at[3:0] * (B + 1)) & 4'hF;
reg  [15:0] ehist;                              // expected history for candidate cph
integer ei;
always @* begin
  for (ei = 0; ei < 16; ei = ei + 1)
    ehist[ei] = ALIGN_SEQ[(cph - ei) & 15];
end

reg  signed [5:0] offs [0:5];                   // signed candidate offsets
reg  signed [5:0] dmin, dmax;
integer ai_i;

// off_0 = (p_0 + 1) mod B ; d_j = (p_j - p_0) mod 16 as signed [-8, 8)
localparam [3:0] BM1 = B - 1;
wire [3:0]         off0 = (ph_r[3:0] + 4'd1) & BM1;
wire [4*LANES-1:0] dj;
generate
  for (g = 0; g < LANES; g = g + 1) begin : G_DJ
    assign dj[4*g +: 4] = ph_r[4*g +: 4] - ph_r[3:0];
  end
endgenerate

always @(posedge clk) begin
  case (astate)
    A_IDLE: begin
      if (align_start) begin
        at     <= 7'd0;
        found  <= {LANES{1'b0}};
        astate <= A_SEARCH;
      end
    end
    A_SEARCH: begin
      if (tick) begin
        for (ai_i = 0; ai_i < LANES; ai_i = ai_i + 1) begin
          if (!found[ai_i] && hist[16*ai_i +: 16] == ehist) begin
            found[ai_i]          <= 1'b1;
            ph_r[4*ai_i +: 4]    <= at[3:0];
          end
        end
        at <= at + 7'd1;
        if (&found) astate <= A_CALC;
        else if (at == 7'd127) begin
          align_ok   <= 1'b0;
          align_fail <= 2'd1;
          astate     <= A_DONE;
        end
      end
    end
    A_CALC: begin
      // off_0 = (p_0 + 1) mod B ; off_j = off_0 + signed((p_j - p_0) mod 16)
      for (ai_i = 0; ai_i < LANES; ai_i = ai_i + 1)
        offs[ai_i] <= $signed({2'b00, off0}) +
                      $signed({{2{dj[4*ai_i+3]}}, dj[4*ai_i +: 4]});
      astate <= A_ADJ;
    end
    A_ADJ: begin
      dmin = offs[0];
      dmax = offs[0];
      for (ai_i = 1; ai_i < LANES; ai_i = ai_i + 1) begin
        if (offs[ai_i] < dmin) dmin = offs[ai_i];
        if (offs[ai_i] > dmax) dmax = offs[ai_i];
      end
      if (dmin < 0) begin
        dmin = dmin + B;
        dmax = dmax + B;
        for (ai_i = 0; ai_i < LANES; ai_i = ai_i + 1) offs[ai_i] <= offs[ai_i] + B;
      end
      if (dmax > 16 - B) begin
        align_ok   <= 1'b0;
        align_fail <= 2'd2;
      end else begin
        align_ok   <= 1'b1;
        align_fail <= 2'd0;
      end
      phase  <= ph_r;
      astate <= A_DONE;
    end
    A_DONE: begin
      if (align_ok)
        for (ai_i = 0; ai_i < LANES; ai_i = ai_i + 1) off[4*ai_i +: 4] <= offs[ai_i][3:0];
      align_done_t <= ~align_done_t;
      astate       <= A_IDLE;
    end
    default: astate <= A_IDLE;
  endcase
end

// ---------------------------------------------------------------- accumulators
reg [32*LANES-1:0] acc_prbs  = {(32*LANES){1'b0}};
reg [47:0]         acc_bits  = 48'd0;
reg [39:0]         acc_words = 40'd0;
reg [31:0]         acc_werr  = 32'd0;

integer ci;
always @(posedge clk) begin
  if (acc_clr) begin
    acc_prbs   <= {(32*LANES){1'b0}};
    acc_bits   <= 48'd0;
    acc_words  <= 40'd0;
    acc_werr   <= 32'd0;
    prev_valid <= 1'b0;
  end else begin
    if (acc_prbs_en)
      for (ci = 0; ci < LANES; ci = ci + 1)
        if (acc_prbs[32*ci +: 32] <= 32'hFFFFFFFD)
          acc_prbs[32*ci +: 32] <= acc_prbs[32*ci +: 32] + {30'd0, m[2*ci +: 2]};
    if (tick_d2) begin
      acc_words   <= acc_words + 40'd1;
      acc_bits    <= acc_bits + 48'd12;
      prev_sample <= sample;
      prev_valid  <= 1'b1;
      if (acc_wchk_en && cnt_err && acc_werr != 32'hFFFFFFFF) acc_werr <= acc_werr + 32'd1;
    end
  end
  if (snap) begin
    snap_prbs   <= acc_prbs;
    snap_bits   <= acc_bits;
    snap_words  <= acc_words;
    snap_werr   <= acc_werr;
    snap_done_t <= ~snap_done_t;
  end
end

endmodule
