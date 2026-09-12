//
//  tb_cable.v — simulation cable model: per-wire transport delay (BASE_PS plus a signed
//  per-wire skew from SKEW_PS, 16 bits each, in picoseconds) and bit-error injection
//  ('flip' XORs the wire at the source; hold it for one unit interval to flip one bit).
//
`timescale 1ns/1ps
module tb_cable #(
  parameter integer      W       = 6,
  parameter integer      BASE_PS = 3000,
  parameter [16*W-1:0]   SKEW_PS = {W{16'd0}}
) (
  input  [W-1:0] i,
  input  [W-1:0] flip,
  output [W-1:0] o
);

genvar g;
generate
  for (g = 0; g < W; g = g + 1) begin : G_W
    reg  o_r = 1'b0;
    wire signed [15:0] skew = SKEW_PS[16*g +: 16];
    real dly;
    initial dly = (BASE_PS + skew) / 1000.0;
    always @(i[g] or flip[g]) o_r <= #(dly) (i[g] ^ flip[g]);
    assign o[g] = o_r;
  end
endgenerate

endmodule
