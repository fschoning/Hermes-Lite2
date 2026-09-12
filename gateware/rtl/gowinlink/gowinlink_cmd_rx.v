//
//  gowinlink_cmd_rx.v — command frame parser (LINK_SPEC.md section 8), fed by the byte
//  stream of gowinlink_uart_rx.
//
//  Frame: 0xA5, ADDR, D[31:24], D[23:16], D[15:8], D[7:0], CRC-8(ADDR..D[7:0]).
//  Hunts for the sync byte, collects the frame, checks the CRC. A CRC failure, or more
//  than TIMEOUT_CYCLES between two bytes of a frame, discards the frame (cnt_err++).
//  Accepted frames give a one-cycle cmd_valid (cnt_ok++).
//
module gowinlink_cmd_rx #(
  parameter integer TIMEOUT_CYCLES = 26640   // 4 byte times at 115200 baud, 76.8 MHz
) (
  input             clk,
  input      [7:0]  rx_data,
  input             rx_valid,
  output reg        cmd_valid = 1'b0,
  output reg [7:0]  cmd_addr  = 8'h00,
  output reg [31:0] cmd_data  = 32'h0,
  output reg [7:0]  cnt_ok    = 8'h00,
  output reg [7:0]  cnt_err   = 8'h00
);

reg [2:0]  idx   = 3'd0;      // 0 = hunting, 1..6 = byte position within the frame
reg [7:0]  crc   = 8'h00;
reg [23:0] tmo   = 24'd0;
reg [7:0]  addr_r = 8'h00;
reg [31:0] data_r = 32'h0;

wire [7:0] crc_next;
gowinlink_crc8 crc_i (.crc_in(crc), .data(rx_data), .crc_out(crc_next));

always @(posedge clk) begin
  cmd_valid <= 1'b0;

  if (rx_valid) begin
    tmo <= 24'd0;
    case (idx)
      3'd0: begin
        if (rx_data == 8'hA5) begin
          idx <= 3'd1;
          crc <= 8'h00;
        end
      end
      3'd1: begin addr_r        <= rx_data; crc <= crc_next; idx <= 3'd2; end
      3'd2: begin data_r[31:24] <= rx_data; crc <= crc_next; idx <= 3'd3; end
      3'd3: begin data_r[23:16] <= rx_data; crc <= crc_next; idx <= 3'd4; end
      3'd4: begin data_r[15:8]  <= rx_data; crc <= crc_next; idx <= 3'd5; end
      3'd5: begin data_r[7:0]   <= rx_data; crc <= crc_next; idx <= 3'd6; end
      default: begin
        idx <= 3'd0;
        if (rx_data == crc) begin
          cmd_valid <= 1'b1;
          cmd_addr  <= addr_r;
          cmd_data  <= data_r;
          cnt_ok    <= cnt_ok + 8'd1;
        end else begin
          cnt_err   <= cnt_err + 8'd1;
        end
      end
    endcase
  end else if (idx != 3'd0) begin
    if (tmo == TIMEOUT_CYCLES) begin
      idx     <= 3'd0;
      cnt_err <= cnt_err + 8'd1;
    end else begin
      tmo <= tmo + 24'd1;
    end
  end
end

endmodule
