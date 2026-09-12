//
//  gl_top_l3.v — wrapper for the 3-lane fallback build (3 forward lanes, 153.6 MHz DDR).
//  gw_sh cannot override parameters from the command line, so this one-line top selects
//  LANES = 3; everything else is gl_top. Pins: gowin/proj/gowinlink_l3.cst.
//
module gl_top_l3 (
  input        clk50,
  input        fwd_clk,
  input  [2:0] link_d,
  input        status_rxd,
  input        aux_in,
  output       rev_clk_out,
  output [2:0] gl_rev,
  output       fs_txd,
  output       cmd_txd,
  output       dbg_txd,
  input        dbg_rxd,
  output [3:0] led,
  input        key_n
);

gl_top #(.LANES(3)) top_i (
  .clk50(clk50), .fwd_clk(fwd_clk), .link_d(link_d), .status_rxd(status_rxd), .aux_in(aux_in),
  .rev_clk_out(rev_clk_out), .gl_rev(gl_rev), .fs_txd(fs_txd), .cmd_txd(cmd_txd),
  .dbg_txd(dbg_txd), .dbg_rxd(dbg_rxd), .led(led), .key_n(key_n)
);

endmodule
