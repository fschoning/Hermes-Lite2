//
//  gl_fastserial_rx.v — framed serial receiver matching gl_fastserial_tx. The line is
//  sampled elsewhere; this module takes one bit per 'bit_valid'.
//
//  A packet is written tentatively into the byte FIFO and committed only when the sync
//  byte, length, CRC-16 and stop bit are all good; otherwise the write pointer is rolled
//  back and pkt_err is incremented. Read port: rd_data / rd_last (last byte of a packet),
//  rd_en pops one byte, 'empty'.
//
module gl_fastserial_rx #(
  parameter integer FIFO_LOG2 = 9
) (
  input             clk,
  input             bit_valid,
  input             bit_in,
  output [7:0]      rd_data,
  output            rd_last,
  output            empty,
  input             rd_en,
  output reg [15:0] pkt_ok  = 16'd0,
  output reg [15:0] pkt_err = 16'd0
);

localparam integer DEPTH = 1 << FIFO_LOG2;

reg  [8:0]         mem [0:DEPTH-1];       // {last, data}
reg  [FIFO_LOG2:0] wr_ptr  = {(FIFO_LOG2+1){1'b0}};   // tentative
reg  [FIFO_LOG2:0] wr_cmt  = {(FIFO_LOG2+1){1'b0}};   // committed
reg  [FIFO_LOG2:0] rd_ptr  = {(FIFO_LOG2+1){1'b0}};
wire               full    = (wr_ptr[FIFO_LOG2-1:0] == rd_ptr[FIFO_LOG2-1:0]) & (wr_ptr[FIFO_LOG2] != rd_ptr[FIFO_LOG2]);
wire [8:0]         rd_word = mem[rd_ptr[FIFO_LOG2-1:0]];

assign empty   = (wr_cmt == rd_ptr);
assign rd_data = rd_word[7:0];
assign rd_last = rd_word[8];

always @(posedge clk) if (rd_en && !empty) rd_ptr <= rd_ptr + 1'b1;

localparam [2:0] R_IDLE = 3'd0, R_SYNC = 3'd1, R_LENL = 3'd2, R_LENH = 3'd3, R_DATA = 3'd4, R_CRC = 3'd5, R_STOP = 3'd6;
reg [2:0]  rs     = R_IDLE;
reg [7:0]  sh     = 8'h00;
reg [2:0]  bitno  = 3'd0;
reg [15:0] len    = 16'd0;
reg [15:0] remain = 16'd0;
reg [15:0] crc    = 16'hFFFF;
reg [15:0] rcrc   = 16'h0000;
reg [3:0]  crcbit = 4'd0;
reg        bad    = 1'b0;

wire [7:0]  byte_next = {bit_in, sh[7:1]};
wire [15:0] crc_next  = {crc[14:0], 1'b0} ^ ((crc[15] ^ bit_in) ? 16'h1021 : 16'h0000);

always @(posedge clk) begin
  if (bit_valid) begin
    case (rs)
      R_IDLE: begin
        if (!bit_in) begin          // start bit
          rs    <= R_SYNC;
          bitno <= 3'd0;
          crc   <= 16'hFFFF;
          bad   <= 1'b0;
          wr_ptr <= wr_cmt;         // discard anything tentative
        end
      end
      R_SYNC: begin
        sh    <= byte_next;
        bitno <= bitno + 3'd1;
        if (bitno == 3'd7) begin
          if (byte_next == 8'h5C) rs <= R_LENL;
          else begin
            rs      <= R_IDLE;
            pkt_err <= pkt_err + 16'd1;
          end
        end
      end
      R_LENL: begin
        sh    <= byte_next;
        crc   <= crc_next;
        bitno <= bitno + 3'd1;
        if (bitno == 3'd7) begin
          len[7:0] <= byte_next;
          rs       <= R_LENH;
        end
      end
      R_LENH: begin
        sh    <= byte_next;
        crc   <= crc_next;
        bitno <= bitno + 3'd1;
        if (bitno == 3'd7) begin
          len[15:8] <= byte_next;
          remain    <= {byte_next, len[7:0]};
          if ({byte_next, len[7:0]} == 16'd0 || {byte_next, len[7:0]} >= DEPTH) begin
            rs      <= R_IDLE;
            pkt_err <= pkt_err + 16'd1;
          end else begin
            rs     <= R_DATA;
            crcbit <= 4'd0;
          end
        end
      end
      R_DATA: begin
        sh    <= byte_next;
        crc   <= crc_next;
        bitno <= bitno + 3'd1;
        if (bitno == 3'd7) begin
          if (!full) begin
            mem[wr_ptr[FIFO_LOG2-1:0]] <= {(remain == 16'd1), byte_next};
            wr_ptr <= wr_ptr + 1'b1;
          end else begin
            bad <= 1'b1;
          end
          remain <= remain - 16'd1;
          if (remain == 16'd1) begin
            rs     <= R_CRC;
            crcbit <= 4'd0;
          end
        end
      end
      R_CRC: begin
        rcrc   <= {rcrc[14:0], bit_in};
        crcbit <= crcbit + 4'd1;
        if (crcbit == 4'd15) rs <= R_STOP;
      end
      R_STOP: begin
        rs <= R_IDLE;
        if (bit_in && !bad && rcrc == crc) begin
          wr_cmt <= wr_ptr;
          pkt_ok <= pkt_ok + 16'd1;
        end else begin
          wr_ptr  <= wr_cmt;
          pkt_err <= pkt_err + 16'd1;
        end
      end
      default: rs <= R_IDLE;
    endcase
  end
end

endmodule
