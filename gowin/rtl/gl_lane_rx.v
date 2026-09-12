//
//  gl_lane_rx.v — one receive lane on the Gowin GW5AST:
//      pad -> IBUF -> IODELAY (dynamic, DLYSTEP = tap, 12.5 ps per step) -> IDDR
//  q0 = sample taken at the rising edge of 'clk', q1 = sample taken at the falling edge
//  that precedes it (q1 is the older bit). Both are presented aligned to the rising edge.
//
//  Primitive names and ports per Gowin UG304 (Arora V GPIO user guide). The same code
//  simulates with Gowin's simlib/gw5a/prim_sim.v (IODELAY delays DI by
//  0.0125 ns * (DLYSTEP + 1) as a transport delay).
//
module gl_lane_rx (
  input        pad,
  input        clk,
  input  [7:0] tap,
  output       q0,
  output       q1
);

wire ibuf_o;
wire dly_o;

IBUF ibuf_i (
  .O (ibuf_o),
  .I (pad)
);

IODELAY #(
  .C_STATIC_DLY (0),
  .DYN_DLY_EN   ("TRUE"),
  .ADAPT_EN     ("FALSE")
) iodelay_i (
  .DO      (dly_o),
  .DF      (),
  .DI      (ibuf_o),
  .DLYSTEP (tap),
  .SDTAP   (1'b0),
  .VALUE   (1'b0)
);

IDDR #(
  .Q0_INIT (1'b0),
  .Q1_INIT (1'b0)
) iddr_i (
  .Q0  (q0),
  .Q1  (q1),
  .D   (dly_o),
  .CLK (clk)
);

endmodule
