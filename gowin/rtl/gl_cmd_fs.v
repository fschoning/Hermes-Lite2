//
//  gl_cmd_fs.v — Gowin -> HL2 command backend over the fast serial channel, plus a
//  periodic test packet generator. Same req/busy interface as gl_cmd_tx (UART backend).
//
//  A command becomes one fast-serial packet: type 0x01, ADDR, D[31:24..7:0] (6 bytes).
//  Every TEST_PERIOD word-clock cycles (0 = never) a 16-byte type 0x02 packet
//  {0x02, seq, 14 ramp bytes} is queued so the channel is exercised and counted by the
//  HL2 even when no command is pending. Commands have priority.
//
module gl_cmd_fs #(
  parameter integer TEST_PERIOD = 768000    // word-clock cycles between test packets (10 ms)
) (
  // control clock domain
  input         clk,
  input         req,
  input  [7:0]  addr,
  input  [31:0] data,
  output        busy,
  // word clock domain (fast serial bit clock)
  input         clk_w,
  output        txd,
  output [15:0] pkt_cnt
);

// ---------------- control side handshake
reg        req_t   = 1'b0;
reg [39:0] body    = 40'h0;
reg        ack_s1  = 1'b0, ack_s2 = 1'b0;
wire       ack_t;
assign busy = (req_t != ack_s2);

always @(posedge clk) begin
  ack_s1 <= ack_t;
  ack_s2 <= ack_s1;
  if (req && !busy) begin
    body  <= {addr, data};
    req_t <= ~req_t;
  end
end

// ---------------- word clock side: FIFO writer
reg        req_s1 = 1'b0, req_s2 = 1'b0;
reg        ack_r  = 1'b0;
assign ack_t = ack_r;
wire       cmd_pend = (req_s2 != ack_r);

reg [7:0]  wr_data = 8'h00;
reg        wr_en   = 1'b0;
reg        wr_last = 1'b0;
wire       full;

reg [1:0]  ws      = 2'd0;    // 0 idle, 1 writing command, 2 writing test packet
reg [3:0]  bi      = 4'd0;
reg [23:0] tmr     = 24'd0;
reg [7:0]  tseq    = 8'h00;
reg        test_due = 1'b0;

always @(posedge clk_w) begin
  req_s1 <= req_t;
  req_s2 <= req_s1;
  wr_en  <= 1'b0;
  wr_last <= 1'b0;

  if (TEST_PERIOD != 0) begin
    if (tmr == TEST_PERIOD - 1) begin
      tmr      <= 24'd0;
      test_due <= 1'b1;
    end else begin
      tmr <= tmr + 24'd1;
    end
  end

  case (ws)
    2'd0: begin
      bi <= 4'd0;
      if (cmd_pend)      ws <= 2'd1;
      else if (test_due) ws <= 2'd2;
    end
    2'd1: begin
      if (!full) begin
        wr_en <= 1'b1;
        case (bi)
          4'd0: wr_data <= 8'h01;
          4'd1: wr_data <= body[39:32];
          4'd2: wr_data <= body[31:24];
          4'd3: wr_data <= body[23:16];
          4'd4: wr_data <= body[15:8];
          default: begin wr_data <= body[7:0]; wr_last <= 1'b1; end
        endcase
        bi <= bi + 4'd1;
        if (bi == 4'd5) begin
          ack_r <= ~ack_r;
          ws    <= 2'd0;
        end
      end
    end
    default: begin
      if (!full) begin
        wr_en <= 1'b1;
        case (bi)
          4'd0: wr_data <= 8'h02;
          4'd1: wr_data <= tseq;
          default: wr_data <= {4'h0, bi} + tseq;
        endcase
        if (bi == 4'd15) begin
          wr_last  <= 1'b1;
          test_due <= 1'b0;
          tseq     <= tseq + 8'd1;
          ws       <= 2'd0;
        end
        bi <= bi + 4'd1;
      end
    end
  endcase
end

gl_fastserial_tx #(.FIFO_LOG2(9)) fs_tx_i (
  .clk     (clk_w),
  .tick    (1'b1),
  .wr_data (wr_data),
  .wr_en   (wr_en),
  .wr_last (wr_last),
  .full    (full),
  .txd     (txd),
  .pkt_cnt (pkt_cnt)
);

endmodule
