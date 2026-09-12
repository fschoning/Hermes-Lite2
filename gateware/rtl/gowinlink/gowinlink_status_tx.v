//
//  gowinlink_status_tx.v — periodic status frame builder (LINK_SPEC.md section 10).
//
//  Every 'period' ticks of tick_10ms (period = 0 disables) a frame is started: first
//  'snap_req' toggles so that counters living in other clock domains can be copied into
//  stable shadow registers; when 'snap_done_t' has toggled back (or immediately when
//  SNAPSHOT = 0) the 32 payload bytes are latched (payload[255:248] is byte 1 ...
//  payload[7:0] is byte 32), 'frame_start' pulses for one cycle so the parent can clear
//  its per-frame counters, and the 34-byte frame 0x5A, payload, CRC-8(payload) is handed
//  byte by byte to gowinlink_uart_tx.
//
module gowinlink_status_tx #(
  parameter integer SNAPSHOT = 1
) (
  input              clk,
  input              tick_10ms,
  input      [7:0]   period,
  input      [255:0] payload,
  output reg         snap_req    = 1'b0,
  input              snap_done_t,
  output reg         frame_start = 1'b0,
  output reg [7:0]   tx_data     = 8'h00,
  output reg         tx_valid    = 1'b0,
  input              tx_ready
);

reg [7:0]   ticks   = 8'd0;
reg [255:0] buf_r   = 256'h0;
reg [7:0]   crc     = 8'h00;
reg [5:0]   idx     = 6'd0;   // byte index 0..33
reg [1:0]   st      = 2'd0;   // 0 idle, 1 wait snapshot, 2 sending
reg [15:0]  snap_to = 16'd0;

wire snap_done;
gl_tog2pulse s_sd (.clk(clk), .t(snap_done_t), .p(snap_done));

wire [7:0] crc_next;
gowinlink_crc8 crc_i (.crc_in(crc), .data(tx_data), .crc_out(crc_next));

always @(posedge clk) begin
  frame_start <= 1'b0;

  case (st)
    2'd0: begin
      tx_valid <= 1'b0;
      if (tick_10ms) begin
        if (period != 8'd0 && ticks + 8'd1 >= period) begin
          ticks    <= 8'd0;
          snap_req <= ~snap_req;
          snap_to  <= 16'd0;
          st       <= 2'd1;
        end else begin
          ticks <= ticks + 8'd1;
        end
      end
    end

    2'd1: begin
      snap_to <= snap_to + 16'd1;
      if (SNAPSHOT == 0 || snap_done || snap_to == 16'hFFFF) begin
        buf_r       <= payload;
        frame_start <= 1'b1;
        idx         <= 6'd0;
        crc         <= 8'h00;
        tx_data     <= 8'h5A;
        tx_valid    <= 1'b1;
        st          <= 2'd2;
      end
    end

    2'd2: begin
      if (tx_valid && tx_ready) begin
        // byte 'idx' has just been accepted
        if (idx >= 6'd1 && idx <= 6'd32) crc <= crc_next;
        if (idx == 6'd33) begin
          tx_valid <= 1'b0;
          st       <= 2'd0;
        end else begin
          idx <= idx + 6'd1;
          if (idx == 6'd32) tx_data <= crc_next;                 // CRC byte
          else              tx_data <= buf_r[255 - 8*idx -: 8];  // payload byte idx+1
        end
      end
    end

    default: st <= 2'd0;
  endcase
end

endmodule
