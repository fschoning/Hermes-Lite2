//
//  gl_cdc.v — clock-domain-crossing helpers for the Gowin side.
//
//  gl_sync2     : 2-flop synchroniser for a level (or a slowly changing bus, bit by bit —
//                 only for buses whose consumers tolerate torn samples).
//  gl_tog2pulse : converts a toggle from another domain into a one-cycle pulse here
//                 (2 sync flops + edge detect).
//
module gl_sync2 #(
  parameter integer W = 1
) (
  input              clk,
  input  [W-1:0]     d,
  output reg [W-1:0] q = {W{1'b0}}
);
reg [W-1:0] s1 = {W{1'b0}};
always @(posedge clk) begin
  s1 <= d;
  q  <= s1;
end
endmodule


module gl_tog2pulse (
  input      clk,
  input      t,
  output     p
);
reg [2:0] s = 3'b000;
always @(posedge clk) s <= {s[1:0], t};
assign p = s[2] ^ s[1];
endmodule
