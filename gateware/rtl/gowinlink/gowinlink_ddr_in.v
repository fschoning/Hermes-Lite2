//
//  gowinlink_ddr_in.v — W-bit DDR input capture. 'qh' is the sample taken at the rising
//  edge of 'clk', 'ql' the sample taken at the preceding falling edge (the older bit);
//  both are presented aligned to the rising edge (Cyclone IV 'altddio_in' semantics).
//
//  Synthesis: altddio_in (IOE input register + falling-edge register).
//  Simulation (`ifdef SIM): behavioural model with the same timing.
//
module gowinlink_ddr_in #(
  parameter integer W = 1
) (
  input          clk,
  input  [W-1:0] d,
  output [W-1:0] qh,
  output [W-1:0] ql
);

`ifdef SIM
  reg [W-1:0] latched = {W{1'b0}};
  reg [W-1:0] qh_r    = {W{1'b0}};
  reg [W-1:0] ql_r    = {W{1'b0}};
  always @(negedge clk) latched <= d;
  always @(posedge clk) begin
    qh_r <= d;
    ql_r <= latched;
  end
  assign qh = qh_r;
  assign ql = ql_r;
`else
  altddio_in #(
    .intended_device_family ("Cyclone IV E"),
    .invert_input_clocks    ("OFF"),
    .lpm_hint               ("UNUSED"),
    .lpm_type               ("altddio_in"),
    .power_up_high          ("OFF"),
    .width                  (W)
  ) altddio_in_i (
    .datain    (d),
    .inclock   (clk),
    .dataout_h (qh),
    .dataout_l (ql),
    .aclr      (1'b0),
    .aset      (1'b0),
    .inclocken (1'b1),
    .sclr      (1'b0),
    .sset      (1'b0)
  );
`endif

endmodule
