//
//  gl_lane_rx.v — one receive lane on the Gowin GW5AST:
//      pad -> IBUF -> IODELAY (dynamic, DLYSTEP = tap, 12.5 ps per step) -> IDDR
//  Outputs follow the data-plane convention: q1 is the OLDER bit of the pair, q0 the newer.
//  Gowin's IDDR (per its simulation model) presents Q0 = the rising-edge sample and
//  Q1 = the falling-edge sample taken half a cycle AFTER it, so IDDR.Q0 is the older bit
//  and is routed to q1, IDDR.Q1 to q0. If the silicon differs, the trainer's pair_swap
//  retry compensates.
//
//  Primitive names and ports per Gowin UG304 (Arora V GPIO user guide). The same code
//  simulates with Gowin's simlib/gw5a/prim_sim.v (IODELAY delays DI by
//  0.0125 ns * (DLYSTEP + 1) as a transport delay).
//
`timescale 1ns/1ps
module gl_lane_rx (
  input        pad,
  input        clk,
  input  [7:0] tap,
  output       q0,
  output       q1
);

wire ibuf_o;
wire dly_o;

// Simulation only: Gowin's IODELAY model latches DLYSTEP only on an SDTAP/VALUE event, so
// pulse VALUE whenever the tap changes (VALUE has no effect while SDTAP = 0).
`ifdef SIM
  reg value_sim = 1'b0;
  initial begin #1 value_sim = 1'b1; #0.05 value_sim = 1'b0; end
  always @(tap) begin value_sim = 1'b1; #0.05 value_sim = 1'b0; end
  wire value_w = value_sim;
`else
  wire value_w = 1'b0;
`endif

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
  .VALUE   (value_w)
);

IDDR #(
  .Q0_INIT (1'b0),
  .Q1_INIT (1'b0)
) iddr_i (
  .Q0  (q1),   // rising-edge sample = older bit
  .Q1  (q0),   // following falling-edge sample = newer bit
  .D   (dly_o),
  .CLK (clk)
);

endmodule
