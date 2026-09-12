//
//  gl_status_rx.v — HL2 -> Gowin status frame parser (LINK_SPEC.md section 10).
//  Frame: 0x5A, 32 payload bytes, CRC-8(payload). Good frames update 'frame'
//  (payload, byte 1 in frame[255:248]) and increment frame_cnt; CRC failures and
//  inter-byte timeouts increment err_cnt.
//
module gl_status_rx #(
  parameter integer CLK_HZ = 50000000,
  parameter integer BAUD   = 115200
) (
  input              clk,
  input              rxd,
  output reg [255:0] frame     = 256'h0,
  output reg [15:0]  frame_cnt = 16'd0,
  output reg [15:0]  err_cnt   = 16'd0,
  output reg         frame_ok  = 1'b0    // one-cycle pulse per good frame
);

localparam integer TIMEOUT_CYCLES = 40 * (CLK_HZ / BAUD);

wire [7:0] rx_data;
wire       rx_valid;

gowinlink_uart_rx #(.CLK_HZ(CLK_HZ), .BAUD(BAUD)) uart_rx_i (
  .clk(clk), .rxd(rxd), .data(rx_data), .valid(rx_valid)
);

reg [5:0]   idx  = 6'd0;     // 0 hunting, 1..33
reg [7:0]   crc  = 8'h00;
reg [255:0] acc  = 256'h0;
reg [23:0]  tmo  = 24'd0;

wire [7:0] crc_next;
gowinlink_crc8 crc_i (.crc_in(crc), .data(rx_data), .crc_out(crc_next));

always @(posedge clk) begin
  frame_ok <= 1'b0;
  if (rx_valid) begin
    tmo <= 24'd0;
    if (idx == 6'd0) begin
      if (rx_data == 8'h5A) begin
        idx <= 6'd1;
        crc <= 8'h00;
      end
    end else if (idx <= 6'd32) begin
      acc <= {acc[247:0], rx_data};
      crc <= crc_next;
      idx <= idx + 6'd1;
    end else begin
      idx <= 6'd0;
      if (rx_data == crc) begin
        frame     <= acc;
        frame_cnt <= frame_cnt + 16'd1;
        frame_ok  <= 1'b1;
      end else begin
        err_cnt   <= err_cnt + 16'd1;
      end
    end
  end else if (idx != 6'd0) begin
    if (tmo == TIMEOUT_CYCLES) begin
      idx     <= 6'd0;
      err_cnt <= err_cnt + 16'd1;
    end else begin
      tmo <= tmo + 24'd1;
    end
  end
end

endmodule
