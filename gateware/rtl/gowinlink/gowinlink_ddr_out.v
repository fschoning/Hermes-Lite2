//
//  gowinlink_ddr_out.v — W-bit DDR output register: 'dh' is driven while 'clk' is high,
//  'dl' while it is low (both sampled at the rising edge). A lane fed dh = 1, dl = 0 is
//  a clock copy with the same edge placement as the data lanes.
//
//  Synthesis: Cyclone IV 'altddio_out' (I/O element DDR registers).
//  Simulation (`ifdef SIM): a glitch-free behavioural model, one register update per edge.
//
module gowinlink_ddr_out #(
  parameter integer W = 1
) (
  input          clk,
  input  [W-1:0] dh,
  input  [W-1:0] dl,
  output [W-1:0] q
);

`ifdef SIM
  reg [W-1:0] q_r  = {W{1'b0}};
  reg [W-1:0] l_r  = {W{1'b0}};
  always @(posedge clk) begin
    q_r <= dh;
    l_r <= dl;
  end
  always @(negedge clk) q_r <= l_r;
  assign q = q_r;
`else
  altddio_out #(
    .width                  (W),
    .intended_device_family ("Cyclone IV E"),
    .extend_oe_disable      ("OFF"),
    .invert_output          ("OFF"),
    .lpm_hint               ("UNUSED"),
    .lpm_type               ("altddio_out"),
    .oe_reg                 ("UNREGISTERED"),
    .power_up_high          ("OFF")
  ) altddio_out_i (
    .datain_h   (dh),
    .datain_l   (dl),
    .outclock   (clk),
    .dataout    (q),
    .aclr       (1'b0),
    .aset       (1'b0),
    .oe         (1'b1),
    .oe_out     (),
    .outclocken (1'b1),
    .sclr       (1'b0),
    .sset       (1'b0)
  );
`endif

endmodule
