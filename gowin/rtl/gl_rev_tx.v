//
//  gl_rev_tx.v — placeholder for the reverse (Gowin -> HL2) fast direction.
//
//  Each of the three wires carries, at one bit per word tick (76.8 Mbit/s), the repeating
//  32-bit frame {counter[23:0], 8'hA5} sent LSB first; wire k sends counter + k. The
//  counter increments once per frame. It exists so the pins are constrained, placed and
//  toggling; the HL2 only reports activity on them.
//
module gl_rev_tx (
  input            clk,      // lane clock
  input            tick,     // word tick (76.8 MHz rate)
  output reg [2:0] rev = 3'b000
);

reg [23:0] counter = 24'd0;
reg [4:0]  bitno   = 5'd0;

wire [31:0] frame0 = {counter,          8'hA5};
wire [31:0] frame1 = {counter + 24'd1,  8'hA5};
wire [31:0] frame2 = {counter + 24'd2,  8'hA5};

always @(posedge clk) begin
  if (tick) begin
    rev   <= {frame2[bitno], frame1[bitno], frame0[bitno]};
    bitno <= bitno + 5'd1;
    if (bitno == 5'd31) counter <= counter + 24'd1;
  end
end

endmodule
