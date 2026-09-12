//
//  gowinlink_fs_cmd.v — reads packets from a gl_fastserial_rx byte FIFO (reverse clock
//  domain) and hands command bodies to the clk_ad9866 domain.
//
//  Packet payload byte 0 = type: 0x01 = commands, followed by N x 5 bytes
//  {ADDR, D[31:24], D[23:16], D[15:8], D[7:0]} (LINK_SPEC.md section 8); other types are
//  consumed and ignored. Each command is transferred with a toggle/ack handshake, so the
//  packet reader stalls while a command waits (commands are rare; the FIFO absorbs it).
//
module gowinlink_fs_cmd (
  // FIFO side (rx clock domain)
  input             rx_clk,
  input  [7:0]      rd_data,
  input             rd_last,
  input             empty,
  output reg        rd_en = 1'b0,
  // command side (clk domain)
  input             clk,
  output reg        cmd_valid = 1'b0,
  output reg [7:0]  cmd_addr  = 8'h00,
  output reg [31:0] cmd_data  = 32'h0,
  output reg [7:0]  cnt_ok    = 8'h00
);

// ---------------- rx clock domain: packet reader
reg [2:0]  idx   = 3'd0;      // 0 = type byte expected, 1..5 command body bytes
reg        is_cmd = 1'b0;
reg [39:0] body  = 40'h0;
reg        req_t = 1'b0;
reg        ack_t = 1'b0;
reg        ack_s1 = 1'b0, ack_s2 = 1'b0;
wire       pending = (req_t != ack_s2);

always @(posedge rx_clk) begin
  ack_s1 <= ack_t;
  ack_s2 <= ack_s1;
  rd_en  <= 1'b0;
  if (!empty && !rd_en && !pending) begin
    rd_en <= 1'b1;
    if (idx == 3'd0) begin
      is_cmd <= (rd_data == 8'h01);
      idx    <= rd_last ? 3'd0 : 3'd1;
    end else begin
      body <= {body[31:0], rd_data};
      if (idx == 3'd5) begin
        idx <= rd_last ? 3'd0 : 3'd1;
        if (is_cmd) req_t <= ~req_t;
      end else begin
        idx <= rd_last ? 3'd0 : idx + 3'd1;
      end
    end
  end
end

// ---------------- clk domain: receive the body
reg req_s1 = 1'b0, req_s2 = 1'b0;
always @(posedge clk) begin
  req_s1    <= req_t;
  req_s2    <= req_s1;
  cmd_valid <= 1'b0;
  if (req_s2 != ack_t) begin
    cmd_addr  <= body[39:32];
    cmd_data  <= body[31:0];
    cmd_valid <= 1'b1;
    cnt_ok    <= cnt_ok + 8'd1;
    ack_t     <= ~ack_t;
  end
end

endmodule
