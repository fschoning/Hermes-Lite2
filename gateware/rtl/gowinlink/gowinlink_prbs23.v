//
//  gowinlink_prbs23.v — PRBS-23 (x^23 + x^18 + 1) serial generator producing two bits per
//  clock: b0 is the earlier bit (sent as "H", while the forwarded clock is high), b1 the
//  later one ("L"). Serial recurrence x[n] = x[n-23] ^ x[n-18]; h[0] is the newest bit.
//
//  'reseed' (level, one or more cycles) reloads SEED. SEED must be non-zero.
//
module gowinlink_prbs23 #(
  parameter [22:0] SEED = 23'h6B8B45
) (
  input      clk,
  input      en,
  input      reseed,
  output     b0,
  output     b1
);

reg [22:0] h = SEED;

assign b0 = h[22] ^ h[17];
assign b1 = h[21] ^ h[16];

always @(posedge clk) begin
  if (reseed)  h <= SEED;
  else if (en) h <= {h[20:0], b0, b1};
end

endmodule
