//
//  gowinlink_uart_tx.v — 8N1 UART transmitter, shared by the HL2 and Gowin sides.
//
//  Handshake: the caller holds 'valid' with 'data'; the byte is taken when ready & valid
//  (one cycle), after which 'ready' drops until the stop bit has been sent.
//  'txd' is the logic level of the line (idle = 1). An open-drain wire is made by the
//  top level as  pin = txd ? 1'bz : 1'b0.
//
module gowinlink_uart_tx #(
  parameter integer CLK_HZ = 76800000,
  parameter integer BAUD   = 115200
) (
  input        clk,
  input  [7:0] data,
  input        valid,
  output       ready,
  output       txd
);

localparam integer DIV = CLK_HZ / BAUD;

reg [9:0]  shreg = 10'h3FF;   // {stop, d7..d0, start}
reg [3:0]  bitno = 4'd0;      // bits remaining
reg [15:0] cnt   = 16'd0;

assign ready = (bitno == 4'd0);
assign txd   = shreg[0];

always @(posedge clk) begin
  if (bitno == 4'd0) begin
    if (valid) begin
      shreg <= {1'b1, data, 1'b0};
      bitno <= 4'd10;
      cnt   <= 16'd0;
    end
  end else begin
    if (cnt == DIV - 1) begin
      cnt   <= 16'd0;
      shreg <= {1'b1, shreg[9:1]};
      bitno <= bitno - 4'd1;
    end else begin
      cnt <= cnt + 16'd1;
    end
  end
end

endmodule
