//
//  gowinlink_uart_rx.v — 8N1 UART receiver, shared by the HL2 and Gowin sides.
//
//  Samples the line at the middle of each bit. A start bit is accepted on a low level
//  after a 2-flop synchroniser; a false start (line high again at mid-start) is ignored.
//  A byte is delivered (data + one-cycle valid) only if the stop bit is high.
//
//  CLK_HZ / BAUD is the number of clocks per bit (integer division; the error at
//  76.8 MHz / 115200 = 666.67 -> 666 is 0.1 %, at 50 MHz / 115200 = 434.03 -> 434 it is
//  0.007 %, both far inside the 8N1 tolerance).
//
module gowinlink_uart_rx #(
  parameter integer CLK_HZ = 76800000,
  parameter integer BAUD   = 115200
) (
  input            clk,
  input            rxd,
  output reg [7:0] data  = 8'h00,
  output reg       valid = 1'b0
);

localparam integer DIV  = CLK_HZ / BAUD;
localparam integer HALF = DIV / 2;

reg [1:0]  sync  = 2'b11;
reg        busy  = 1'b0;
reg [15:0] cnt   = 16'd0;
reg [3:0]  bitno = 4'd0;
reg [7:0]  shreg = 8'h00;

always @(posedge clk) begin
  sync  <= {sync[0], rxd};
  valid <= 1'b0;

  if (!busy) begin
    if (!sync[1]) begin
      busy  <= 1'b1;
      cnt   <= 16'd0;
      bitno <= 4'd0;
    end
  end else begin
    if (cnt == DIV - 1) cnt <= 16'd0;
    else                cnt <= cnt + 16'd1;

    if (cnt == HALF) begin
      // sample point of bit 'bitno': 0 = start, 1..8 = data (LSB first), 9 = stop
      if (bitno == 4'd0) begin
        if (sync[1]) busy <= 1'b0;          // false start
      end else if (bitno <= 4'd8) begin
        shreg <= {sync[1], shreg[7:1]};
      end else begin
        busy <= 1'b0;
        if (sync[1]) begin                  // good stop bit
          data  <= shreg;
          valid <= 1'b1;
        end
      end
      bitno <= bitno + 4'd1;
    end
  end
end

endmodule
