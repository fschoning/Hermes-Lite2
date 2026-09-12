//
//  gl_cmd_tx.v — Gowin -> HL2 command frame sender (LINK_SPEC.md section 8).
//  'req' (one cycle, while busy = 0) sends 0xA5, addr, data[31:24..7:0], CRC-8.
//  'busy' stays high until the last byte has been accepted by the UART transmitter and
//  the transmitter is idle again.
//
module gl_cmd_tx #(
  parameter integer CLK_HZ = 50000000,
  parameter integer BAUD   = 115200
) (
  input         clk,
  input         req,
  input  [7:0]  addr,
  input  [31:0] data,
  output        busy,
  output        txd
);

reg [39:0] shreg  = 40'h0;   // {addr, data}
reg [7:0]  crc    = 8'h00;
reg [3:0]  idx    = 4'd0;    // 0 idle; 1..7 byte being presented (1 = sync)
reg [7:0]  tx_data = 8'h00;
reg        tx_valid = 1'b0;
wire       tx_ready;

wire [7:0] crc_next;
gowinlink_crc8 crc_i (.crc_in(crc), .data(tx_data), .crc_out(crc_next));

assign busy = (idx != 4'd0) | ~tx_ready;

always @(posedge clk) begin
  if (idx == 4'd0) begin
    tx_valid <= 1'b0;
    if (req && tx_ready) begin
      shreg    <= {addr, data};
      crc      <= 8'h00;
      tx_data  <= 8'hA5;
      tx_valid <= 1'b1;
      idx      <= 4'd1;
    end
  end else if (tx_valid && tx_ready) begin
    // byte idx accepted
    if (idx >= 4'd2 && idx <= 4'd6) crc <= crc_next;
    if (idx == 4'd7) begin
      tx_valid <= 1'b0;
      idx      <= 4'd0;
    end else begin
      if (idx == 4'd6) tx_data <= crc_next;
      else begin
        tx_data <= shreg[39:32];
        shreg   <= {shreg[31:0], 8'h00};
      end
      idx <= idx + 4'd1;
    end
  end
end

gowinlink_uart_tx #(.CLK_HZ(CLK_HZ), .BAUD(BAUD)) uart_tx_i (
  .clk(clk), .data(tx_data), .valid(tx_valid), .ready(tx_ready), .txd(txd)
);

endmodule
