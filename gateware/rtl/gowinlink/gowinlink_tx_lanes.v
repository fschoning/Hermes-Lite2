//
//  gowinlink_tx_lanes.v — HL2 lane serialiser: turns the 12-bit word stream (word clock,
//  76.8 MHz) into two bits per lane per lane-clock cycle for the DDR output registers,
//  and generates the per-lane test patterns (LINK_SPEC.md sections 2 to 5).
//
//  LANES = 3: lane_clk = 153.6 MHz, 4 bits per lane per word, two lane cycles per word.
//  LANES = 6: lane_clk = 76.8 MHz (the word clock itself), 2 bits per lane per word.
//
//  Word transfer into the lane clock domain: 'word' and 'wtog' are registers of the word
//  domain, 'wtog' toggling once per word. Both are re-registered here; the cycle in which
//  the registered wtog differs from its previous value is the first lane cycle of that word
//  ('first'). Quartus analyses clk_ad9866 -> clk_ad9866_2x as a related-clock path, so the
//  capture is consistent for any phase between the two PLL outputs.
//
//  Lane j sends sample bits s[B*j+B-1 : B*j], most significant first, "H" (clock high)
//  before "L" (clock low).
//
module gowinlink_tx_lanes #(
  parameter integer LANES = 3
) (
  input                  lane_clk,
  input  [11:0]          word,      // word-domain register
  input                  wtog,      // word-domain toggle, one per word
  input  [2:0]           mode,      // word-domain register (quasi-static)
  input                  pat_rst,   // word-domain toggle: reset pattern generators
  output reg [LANES-1:0] dh = {LANES{1'b0}},
  output reg [LANES-1:0] dl = {LANES{1'b0}}
);

localparam integer B   = 12 / LANES;   // bits per lane per word (4 or 2)
localparam integer CPW = B / 2;        // lane cycles per word (2 or 1)

localparam [2:0] MODE_LIVE = 3'd0, MODE_PRBS = 3'd1, MODE_TOGGLE = 3'd2,
                 MODE_COUNTER = 3'd3, MODE_ALIGN = 3'd4;

// de Bruijn B(2,4) alignment sequence, d_k = ALIGN_SEQ[k], d0 sent first:
// 0000 1001 1010 1111
localparam [15:0] ALIGN_SEQ = 16'hF590;

reg [11:0] word_r    = 12'h000;
reg        wtog_r    = 1'b0, wtog_d = 1'b0;
reg [2:0]  mode_r    = 3'd0;
reg        pat_rst_r = 1'b0, pat_rst_d = 1'b0;
reg [1:0]  ph_prev   = 2'd0;
reg [2:0]  wc        = 3'd0;     // word counter for the alignment sequence
reg        reseed_pend = 1'b0;

wire first  = wtog_r ^ wtog_d;
wire reseed = pat_rst_r ^ pat_rst_d;

always @(posedge lane_clk) begin
  word_r    <= word;
  wtog_r    <= wtog;
  wtog_d    <= wtog_r;
  mode_r    <= mode;
  pat_rst_r <= pat_rst;
  pat_rst_d <= pat_rst_r;
end

// phase within the word: 0 in the 'first' cycle, then 1 (only for CPW = 2)
wire [1:0] ph_cur = first ? 2'd0 : ph_prev + 2'd1;
always @(posedge lane_clk) ph_prev <= ph_cur;

// alignment sequence position: c = (wc * CPW + ph) mod 8, bits 2c (H) and 2c+1 (L).
// wc advances in the last lane cycle of a word so that it is stable for the whole word.
always @(posedge lane_clk) begin
  if (reseed) reseed_pend <= 1'b1;
  if (ph_cur == CPW - 1) begin
    wc          <= reseed_pend ? 3'd0 : wc + 3'd1;
    if (reseed_pend) reseed_pend <= 1'b0;
  end
end
wire [2:0] c = (CPW == 2) ? {wc[1:0], ph_cur[0]} : wc;

// per-lane PRBS-23 generators, distinct seeds
localparam [23*6-1:0] SEEDS = {23'h19495C, 23'h74B0DC, 23'h66334A, 23'h643C98, 23'h327B23, 23'h6B8B45};
wire [LANES-1:0] prbs_b0, prbs_b1;
genvar g;
generate
  for (g = 0; g < LANES; g = g + 1) begin : G_PRBS
    gowinlink_prbs23 #(.SEED(SEEDS[23*g +: 23])) prbs_i (
      .clk    (lane_clk),
      .en     (1'b1),
      .reseed (reseed),
      .b0     (prbs_b0[g]),
      .b1     (prbs_b1[g])
    );
  end
endgenerate

// bit positions within the lane's B-bit group for this phase (MSB first)
wire [3:0] hi = B - 1 - 2 * ph_cur;
wire [3:0] lo = B - 2 - 2 * ph_cur;

integer j;
always @(posedge lane_clk) begin
  case (mode_r)
    MODE_PRBS: begin
      dh <= prbs_b0;
      dl <= prbs_b1;
    end
    MODE_TOGGLE: begin
      dh <= {LANES{1'b1}};
      dl <= {LANES{1'b0}};
    end
    MODE_ALIGN: begin
      dh <= {LANES{ALIGN_SEQ[{c, 1'b0}]}};
      dl <= {LANES{ALIGN_SEQ[{c, 1'b1}]}};
    end
    default: begin // LIVE, COUNTER: word data
      for (j = 0; j < LANES; j = j + 1) begin
        dh[j] <= word_r[B * j + hi];
        dl[j] <= word_r[B * j + lo];
      end
    end
  endcase
end

endmodule
