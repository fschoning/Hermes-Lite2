//
//  gl_fastserial_tx.v — framed serial transmitter, one bit per 'tick' (76.8 Mbit/s when
//  ticked at the word rate). Reusable; used on the Gowin for the Gowin -> HL2 channel.
//
//  Line format (idle = 1):
//     start bit 0, sync byte 0x5C, len[7:0], len[15:8], len payload bytes, CRC-16, stop bit 1,
//     then at least 4 idle bits. Bytes LSB first. CRC-16-CCITT (poly 0x1021, init 0xFFFF)
//     computed bit-serially over the len and payload bits in transmission order and sent
//     MSB first.
//
//  Byte FIFO interface: write bytes with wr_en, marking the last byte of a packet with
//  wr_last. A packet is sent once its last byte is in the FIFO. Up to 15 packets may be
//  queued; a write while 'full' is dropped. Maximum packet length 2^FIFO_LOG2 - 1 bytes.
//
module gl_fastserial_tx #(
  parameter integer FIFO_LOG2 = 9
) (
  input             clk,
  input             tick,
  input  [7:0]      wr_data,
  input             wr_en,
  input             wr_last,
  output            full,
  output reg        txd     = 1'b1,
  output reg [15:0] pkt_cnt = 16'd0
);

localparam integer DEPTH = 1 << FIFO_LOG2;

// byte FIFO
reg  [7:0]           mem [0:DEPTH-1];
reg  [FIFO_LOG2:0]   wr_ptr = {(FIFO_LOG2+1){1'b0}};
reg  [FIFO_LOG2:0]   rd_ptr = {(FIFO_LOG2+1){1'b0}};
wire                 empty  = (wr_ptr == rd_ptr);
assign full = (wr_ptr[FIFO_LOG2-1:0] == rd_ptr[FIFO_LOG2-1:0]) & (wr_ptr[FIFO_LOG2] != rd_ptr[FIFO_LOG2]);

// packet length FIFO (16 entries)
reg  [15:0] lmem [0:15];
reg  [4:0]  lwr = 5'd0, lrd = 5'd0;
wire        lempty = (lwr == lrd);
wire        lfull  = (lwr[3:0] == lrd[3:0]) & (lwr[4] != lrd[4]);
reg  [15:0] cur_len = 16'd0;      // bytes of the packet being written

always @(posedge clk) begin
  if (wr_en && !full && !(wr_last && lfull)) begin
    mem[wr_ptr[FIFO_LOG2-1:0]] <= wr_data;
    wr_ptr <= wr_ptr + 1'b1;
    if (wr_last) begin
      lmem[lwr[3:0]] <= cur_len + 16'd1;
      lwr     <= lwr + 5'd1;
      cur_len <= 16'd0;
    end else begin
      cur_len <= cur_len + 16'd1;
    end
  end
end

// bit-level transmitter
localparam [2:0] T_IDLE = 3'd0, T_START = 3'd1, T_BYTE = 3'd2, T_CRC = 3'd3, T_STOP = 3'd4, T_GAP = 3'd5;
reg [2:0]  ts      = T_IDLE;
reg [7:0]  sh      = 8'h00;
reg [2:0]  bitno   = 3'd0;
reg [15:0] len     = 16'd0;
reg [15:0] remain  = 16'd0;
reg [1:0]  hdr     = 2'd0;     // 0 sync, 1 len lo, 2 len hi, 3 payload
reg [15:0] crc     = 16'hFFFF;
reg [3:0]  crcbit  = 4'd0;
reg [2:0]  gap     = 3'd0;

wire       bit_out = sh[0];
wire [15:0] crc_next = {crc[14:0], 1'b0} ^ ((crc[15] ^ bit_out) ? 16'h1021 : 16'h0000);

always @(posedge clk) begin
  if (tick) begin
    case (ts)
      T_IDLE: begin
        txd <= 1'b1;
        if (!lempty) begin
          len    <= lmem[lrd[3:0]];
          remain <= lmem[lrd[3:0]];
          lrd    <= lrd + 5'd1;
          crc    <= 16'hFFFF;
          hdr    <= 2'd0;
          txd    <= 1'b0;          // start bit
          sh     <= 8'h5C;
          bitno  <= 3'd0;
          ts     <= T_BYTE;
        end
      end
      T_BYTE: begin
        txd <= bit_out;
        if (hdr != 2'd0) crc <= crc_next;
        sh    <= {1'b0, sh[7:1]};
        bitno <= bitno + 3'd1;
        if (bitno == 3'd7) begin
          case (hdr)
            2'd0: begin sh <= len[7:0];  hdr <= 2'd1; end
            2'd1: begin sh <= len[15:8]; hdr <= 2'd2; end
            default: begin
              if (remain == 16'd0) begin
                ts     <= T_CRC;
                crcbit <= 4'd0;
              end else begin
                sh     <= mem[rd_ptr[FIFO_LOG2-1:0]];
                rd_ptr <= rd_ptr + 1'b1;
                remain <= remain - 16'd1;
                hdr    <= 2'd3;
              end
            end
          endcase
        end
      end
      T_CRC: begin
        txd    <= crc[15];
        crc    <= {crc[14:0], 1'b0};
        crcbit <= crcbit + 4'd1;
        if (crcbit == 4'd15) ts <= T_STOP;
      end
      T_STOP: begin
        txd     <= 1'b1;
        gap     <= 3'd0;
        pkt_cnt <= pkt_cnt + 16'd1;
        ts      <= T_GAP;
      end
      T_GAP: begin
        txd <= 1'b1;
        gap <= gap + 3'd1;
        if (gap == 3'd3) ts <= T_IDLE;
      end
      default: ts <= T_IDLE;
    endcase
  end
end

endmodule
