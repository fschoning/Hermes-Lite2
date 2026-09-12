//
//  tb_fwd.v — unit test of the forward chain: HL2 serialiser + DDR out -> skewed cable ->
//  Gowin IBUF/IODELAY/IDDR (vendor models) -> gl_rx_datapath (6 lanes). Sweeps a few taps
//  and prints per-lane PRBS mismatches, then aligns. Prints PASS/FAIL.
//
`timescale 1ns/1ps
module tb_fwd;
parameter integer LANES = 6;
reg clk = 1'b0;  always #6.51 clk = ~clk;
GSR GSR (.GSRI(1'b1));
reg [2:0] mode = 3'd1;  // PRBS
reg [11:0] word = 12'h000; reg wtog = 1'b0;
always @(posedge clk) begin word <= word + 12'd1; wtog <= ~wtog; end
wire [LANES-1:0] dh, dl, q, gw_d;
wire clk_q, gw_clk;
gowinlink_tx_lanes #(.LANES(LANES)) tx_i (.lane_clk(clk), .word(word), .wtog(wtog), .mode(mode), .pat_rst(1'b0), .dh(dh), .dl(dl));
gowinlink_ddr_out #(.W(LANES)) ddr_d (.clk(clk), .dh(dh), .dl(dl), .q(q));
gowinlink_ddr_out #(.W(1)) ddr_c (.clk(clk), .dh(1'b1), .dl(1'b0), .q(clk_q));
tb_cable #(.W(6), .BASE_PS(3000), .SKEW_PS({-16'd200, 16'd900, -16'd1400, 16'd1200, -16'd700, 16'd300})) cable_d (.i(q), .flip(6'b0), .o(gw_d));
tb_cable #(.W(1), .BASE_PS(3000), .SKEW_PS(16'd100)) cable_c (.i(clk_q), .flip(1'b0), .o(gw_clk));
wire [8*LANES-1:0] tap; wire [LANES-1:0] q0, q1;
genvar g;
generate for (g = 0; g < LANES; g = g + 1) begin : G
  gl_lane_rx lane_i (.pad(gw_d[g]), .clk(gw_clk), .tap(tap[8*g +: 8]), .q0(q0[g]), .q1(q1[g]));
end endgenerate
reg pair_swap = 0, meas_start_t = 0, align_start_t = 0, acc_clr_t = 0, snap_t = 0;
reg [8*LANES-1:0] tap_val = 0; reg [4:0] meas_len = 5'd7; reg [1:0] meas_kind = 2'd0;
wire meas_done_t, align_done_t, align_ok, snap_done_t; wire [1:0] align_fail;
wire [16*LANES-1:0] meas_err; wire [15:0] meas_werr; wire [4*LANES-1:0] off, phase;
wire [32*LANES-1:0] snap_prbs; wire [11:0] sample; wire sample_valid, tick;
gl_rx_datapath #(.LANES(LANES)) dp (
  .clk(gw_clk), .q0(q0), .q1(q1), .pair_swap(pair_swap), .tap(tap), .tap_val(tap_val),
  .meas_start_t(meas_start_t), .meas_len_log2(meas_len), .meas_kind(meas_kind), .meas_done_t(meas_done_t),
  .meas_err(meas_err), .meas_werr(meas_werr), .align_start_t(align_start_t), .align_done_t(align_done_t),
  .align_ok(align_ok), .align_fail(align_fail), .off(off), .phase(phase), .descr_en(1'b0),
  .acc_prbs_en(1'b0), .acc_wchk_en(1'b0), .acc_clr_t(acc_clr_t), .snap_t(snap_t), .snap_done_t(snap_done_t),
  .snap_prbs(snap_prbs), .snap_bits(), .snap_words(), .snap_werr(), .tick(tick), .sample(sample),
  .sample_valid(sample_valid), .alive(), .sdr_q0(1'b1), .sdr_q1(1'b1), .ser_bit(), .ser_valid());
integer errors = 0, t, i;
task meas(input [7:0] tp);
  begin
    tap_val = {LANES{tp}};
    meas_start_t = ~meas_start_t;
    @(meas_done_t); #10;
    $write("tap %0d: err", tp);
    for (i = 0; i < LANES; i = i + 1) $write(" %0d", meas_err[16*i +: 16]);
    $write("\n");
  end
endtask
initial begin
  #500;
  for (t = 0; t < 12; t = t + 1) begin
    @(posedge gw_clk); #0.1;
    $display("t=%0t q1q0=%b%b %b%b %b%b %b%b %b%b %b%b dly0=%b pad0=%b hist0=%b", $time,
      q1[0],q0[0], q1[1],q0[1], q1[2],q0[2], q1[3],q0[3], q1[4],q0[4], q1[5],q0[5], G[0].lane_i.dly_o, gw_d[0], dp.hist[15:0]);
  end
  meas(0); meas(40); meas(80); meas(128); meas(200); meas(255);
  if (meas_err != 0) errors = errors + 1;
  mode = 3'd4; #500;
  align_start_t = ~align_start_t; @(align_done_t); #10;
  $display("align ok=%0d fail=%0d off=%h", align_ok, align_fail, off);
  if (!align_ok) errors = errors + 1;
  if (errors == 0) $display("PASS"); else $display("FAIL: %0d errors", errors);
  $finish;
end
endmodule
