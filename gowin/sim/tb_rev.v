//
//  tb_rev.v — unit test of the reverse lane chain: Gowin PLL model + lane serialiser +
//  ODDR -> cable (skew) -> HL2 altddio_in model + gl_rx_datapath(3 lanes): alignment
//  search, verification and PRBS check. Prints PASS/FAIL. Also usable with +DEBUG to
//  print the received bit history.
//
`timescale 1ns/1ps
module tb_rev;

reg fwd_clk = 1'b0;
always #6.51 fwd_clk = ~fwd_clk;      // 76.8 MHz
reg clk_ctl = 1'b0;
always #10 clk_ctl = ~clk_ctl;        // 50 MHz control side

GSR GSR (.GSRI(1'b1));

wire clk_w, clk_l, clk_c, lock;
gl_pll #(.LANES(6)) pll_i (.fwd_clk(fwd_clk), .clk_w(clk_w), .clk_l(clk_l), .clk_c(clk_c), .lock(lock));

reg [2:0] mode = 3'd4;   // ALIGN
reg [11:0] word = 12'h000;
reg wtog = 1'b0;
always @(posedge clk_w) begin word <= word + 12'd1; wtog <= ~wtog; end

wire [2:0] dh, dl, q, rev_in;
wire clk_q, clk_in;
gowinlink_tx_lanes #(.LANES(3)) tx_i (.lane_clk(clk_l), .word(word), .wtog(wtog), .mode(mode), .pat_rst(1'b0), .dh(dh), .dl(dl));
genvar g;
generate for (g = 0; g < 3; g = g + 1) begin : G
  ODDR #(.TXCLK_POL(1'b0), .INIT(1'b0)) oddr_i (.Q0(q[g]), .Q1(), .D0(dh[g]), .D1(dl[g]), .TX(1'b0), .CLK(clk_l));
end endgenerate
ODDR #(.TXCLK_POL(1'b0), .INIT(1'b0)) oddr_c (.Q0(clk_q), .Q1(), .D0(1'b1), .D1(1'b0), .TX(1'b0), .CLK(clk_c));

tb_cable #(.W(3), .BASE_PS(3000), .SKEW_PS({16'd800, -16'd500, 16'd400})) cable_d (.i(q), .flip(3'b000), .o(rev_in));
tb_cable #(.W(1), .BASE_PS(3000), .SKEW_PS(-16'd100)) cable_c (.i(clk_q), .flip(1'b0), .o(clk_in));

wire rev_clk, locked;
gowinlink_rxpll rxpll_i (.inclk(clk_in), .areset(1'b0), .c0(rev_clk), .locked(locked));
wire [2:0] q0, q1;
gowinlink_ddr_in #(.W(3)) ddr_i (.clk(rev_clk), .d(rev_in), .qh(q0), .ql(q1));

reg  pair_swap = 1'b0, align_start_t = 1'b0, meas_start_t = 1'b0, acc_clr_t = 1'b0, snap_t = 1'b0;
reg  [4:0] meas_len = 5'd8; reg [1:0] meas_kind = 2'd1;
reg  acc_prbs_en = 1'b0;
wire align_done_t, align_ok, meas_done_t, snap_done_t;
wire [1:0] align_fail;
wire [11:0] off, phase;
wire [15:0] meas_werr;
wire [47:0] meas_err;
wire [95:0] snap_prbs, acc_prbs_w;
wire [11:0] sample; wire sample_valid, tick;

gl_rx_datapath #(.LANES(3)) dp (
  .clk(rev_clk), .q0(q0), .q1(q1), .pair_swap(pair_swap), .tap(), .tap_val(24'd0),
  .meas_start_t(meas_start_t), .meas_len_log2(meas_len), .meas_kind(meas_kind), .meas_done_t(meas_done_t),
  .meas_err(meas_err), .meas_werr(meas_werr),
  .align_start_t(align_start_t), .align_done_t(align_done_t), .align_ok(align_ok), .align_fail(align_fail),
  .off(off), .phase(phase), .descr_en(1'b0), .acc_prbs_en(acc_prbs_en), .acc_wchk_en(1'b0), .acc_clr_t(acc_clr_t),
  .snap_t(snap_t), .snap_done_t(snap_done_t), .snap_prbs(snap_prbs), .snap_bits(), .snap_words(), .snap_werr(),
  .tick(tick), .sample(sample), .sample_valid(sample_valid), .alive(), .sdr_q0(1'b1), .sdr_q1(1'b1), .ser_bit(), .ser_valid()
);

integer errors = 0;
task check(input cond, input [511:0] msg);
  begin
    if (!cond) begin errors = errors + 1; $display("FAIL: %0s", msg); end
    else $display("ok:   %0s", msg);
  end
endtask

integer i;
reg dbg = 0;
initial begin
  if ($test$plusargs("DEBUG")) dbg = 1;
  #2000;
  if (dbg) begin
    for (i = 0; i < 12; i = i + 1) begin
      @(posedge rev_clk); #0.1;
      $display("t=%0t tick=%b q1q0 lane0=%b%b lane1=%b%b lane2=%b%b hist0=%b dh=%b dl=%b first=%b c=%0d mode_r=%0d",
               $time, tick, q1[0], q0[0], q1[1], q0[1], q1[2], q0[2], dp.hist[15:0], dh, dl, tx_i.first, tx_i.c, tx_i.mode_r);
    end
  end
  // alignment
  align_start_t = ~align_start_t;
  @(posedge align_done_t or negedge align_done_t);
  #100;
  $display("align ok=%0d fail=%0d off=%h phase=%h", align_ok, align_fail, off, phase);
  check(align_ok, "reverse alignment found");
  // verification
  meas_start_t = ~meas_start_t;
  @(meas_done_t);
  #100;
  $display("verify werr=%0d", meas_werr);
  check(meas_werr == 0, "alignment pattern verified");
  // PRBS
  mode = 3'd1;
  #2000;
  acc_clr_t = ~acc_clr_t;
  #100;
  acc_prbs_en = 1'b1;
  #20000;
  snap_t = ~snap_t;
  @(snap_done_t);
  #100;
  $display("prbs acc=%h", snap_prbs);
  check(snap_prbs == 96'd0, "reverse PRBS error free");
  // counter mode
  mode = 3'd3;
  #2000;
  meas_kind = 2'd2;
  meas_start_t = ~meas_start_t;
  @(meas_done_t);
  #100;
  $display("counter werr=%0d", meas_werr);
  check(meas_werr == 0, "counter words exact");
  if (errors == 0) $display("PASS"); else $display("FAIL: %0d errors", errors);
  $finish;
end

endmodule
