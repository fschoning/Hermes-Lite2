//
//  gowinlink_cmd_mux.v — arbitration between the Ethernet-originated command bus and
//  link-originated commands (LINK_SPEC.md section 9). Runs in clk_ad9866.
//
//  Ethernet side: eth_* is the existing producer (hl2link_app outputs, or a synchronised
//  copy of the dsopenhpsdr1 outputs). Every toggle of eth_cnt is re-issued on cmd_* in the
//  next cycle, unconditionally. Nothing Ethernet-originated is delayed or dropped.
//
//  Link side: link_push writes {addr, data} into a 2^DEPTH_LOG2 entry FIFO. One entry is
//  issued when there is no Ethernet toggle this cycle and at least GAP_CYCLES have passed
//  since the last issue of either source. With GAP_CYCLES = 512 (6.7 us) a link command
//  never lands between the two C&C frames of one openHPSDR UDP packet (4.1 us apart at
//  1 Gb/s). FIFO full -> the frame is dropped and cnt_drop incremented.
//
module gowinlink_cmd_mux #(
  parameter integer GAP_CYCLES = 512,
  parameter integer DEPTH_LOG2 = 4
) (
  input             clk,
  // Ethernet-originated bus in
  input      [5:0]  eth_addr,
  input      [31:0] eth_data,
  input             eth_cnt,
  input             eth_resprqst,
  input             eth_is_alt,
  // link-originated commands in
  input             link_push,
  input      [5:0]  link_addr,
  input      [31:0] link_data,
  // arbitrated bus out
  output reg [5:0]  cmd_addr     = 6'h00,
  output reg [31:0] cmd_data     = 32'h0,
  output reg        cmd_cnt      = 1'b0,
  output reg        cmd_resprqst = 1'b0,
  output reg        cmd_is_alt   = 1'b0,
  output reg [7:0]  cnt_drop     = 8'h00
);

localparam integer DEPTH = 1 << DEPTH_LOG2;

reg              eth_cnt_d = 1'b0;
wire             eth_pulse = eth_cnt ^ eth_cnt_d;

reg [37:0]       mem [0:DEPTH-1];
reg [DEPTH_LOG2:0] wr_ptr = {(DEPTH_LOG2+1){1'b0}};
reg [DEPTH_LOG2:0] rd_ptr = {(DEPTH_LOG2+1){1'b0}};
wire             empty = (wr_ptr == rd_ptr);
wire             full  = (wr_ptr[DEPTH_LOG2-1:0] == rd_ptr[DEPTH_LOG2-1:0]) &
                         (wr_ptr[DEPTH_LOG2] != rd_ptr[DEPTH_LOG2]);
wire [37:0]      rd_word = mem[rd_ptr[DEPTH_LOG2-1:0]];

reg [15:0]       gap = 16'd0;
wire             gap_ok = (gap >= GAP_CYCLES);

always @(posedge clk) begin
  eth_cnt_d <= eth_cnt;

  // write side
  if (link_push) begin
    if (!full) begin
      mem[wr_ptr[DEPTH_LOG2-1:0]] <= {link_addr, link_data};
      wr_ptr <= wr_ptr + 1'b1;
    end else begin
      cnt_drop <= cnt_drop + 8'd1;
    end
  end

  // issue side
  if (eth_pulse) begin
    cmd_addr     <= eth_addr;
    cmd_data     <= eth_data;
    cmd_resprqst <= eth_resprqst;
    cmd_is_alt   <= eth_is_alt;
    cmd_cnt      <= ~cmd_cnt;
    gap          <= 16'd0;
  end else if (!empty && gap_ok) begin
    cmd_addr     <= rd_word[37:32];
    cmd_data     <= rd_word[31:0];
    cmd_resprqst <= 1'b0;
    cmd_is_alt   <= 1'b0;
    cmd_cnt      <= ~cmd_cnt;
    rd_ptr       <= rd_ptr + 1'b1;
    gap          <= 16'd0;
  end else if (!gap_ok) begin
    gap <= gap + 16'd1;
  end
end

endmodule
