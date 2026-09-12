//
//  gowinlink_scrambler.v — self-synchronising x^43 + 1 scrambler / descrambler on a
//  12-bit word stream (see LINK_SPEC.md section 7).
//
//  Serial bit index of bit i of word n is 12n + i.  y[k] = x[k] ^ y[k-43].
//  43 = 3*12 + 7, so bit i of the feedback comes from output word n-3 (bit i-7) for
//  i >= 7 and from output word n-4 (bit i+5) for i < 7.
//
//  DESCRAMBLE = 0: history = own output (scrambled stream).
//  DESCRAMBLE = 1: history = input (the received scrambled stream); self-synchronises
//                  after 4 words.
//  'bypass' passes din through unchanged (history still tracks, harmless).
//  One word of latency, advanced by 'en'.
//
module gowinlink_scrambler #(
  parameter DESCRAMBLE = 0
) (
  input             clk,
  input             en,
  input             bypass,
  input      [11:0] din,
  output reg [11:0] dout = 12'h000
);

reg [11:0] h1 = 12'h000, h2 = 12'h000, h3 = 12'h000, h4 = 12'h000;

wire [11:0] fb = {h3[4:0], h4[11:5]};
wire [11:0] y  = din ^ fb;
wire [11:0] scr = (DESCRAMBLE != 0) ? din : y;

always @(posedge clk) begin
  if (en) begin
    dout <= bypass ? din : y;
    h1   <= scr;
    h2   <= h1;
    h3   <= h2;
    h4   <= h3;
  end
end

endmodule
