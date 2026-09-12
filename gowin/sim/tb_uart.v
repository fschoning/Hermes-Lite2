//
//  tb_uart.v — unit test of the UART pair, the CRC-8 command framer/parser and the
//  fast serial framed link (transmitter -> receiver with CRC-16, corrupted packet
//  rejected). Prints PASS/FAIL.
//
`timescale 1ns/1ps
module tb_uart;

reg clk = 1'b0;
always #6.51 clk = ~clk;      // 76.8 MHz

integer errors = 0;
task check(input cond, input [511:0] msg);
  begin
    if (!cond) begin errors = errors + 1; $display("FAIL: %0s", msg); end
    else $display("ok:   %0s", msg);
  end
endtask

// ---------------------------------------------------------------- UART + command frame
reg  [7:0]  tx_data = 8'h00;
reg         tx_valid = 1'b0;
wire        tx_ready, line;
wire [7:0]  rx_data;
wire        rx_valid;

gowinlink_uart_tx #(.CLK_HZ(76800000), .BAUD(115200)) utx (.clk(clk), .data(tx_data), .valid(tx_valid), .ready(tx_ready), .txd(line));
gowinlink_uart_rx #(.CLK_HZ(76800000), .BAUD(115200)) urx (.clk(clk), .rxd(line), .data(rx_data), .valid(rx_valid));

wire        cmd_valid;
wire [7:0]  cmd_addr;
wire [31:0] cmd_data;
wire [7:0]  cnt_ok, cnt_err;
gowinlink_cmd_rx #(.TIMEOUT_CYCLES(26640)) crx (.clk(clk), .rx_data(rx_data), .rx_valid(rx_valid),
  .cmd_valid(cmd_valid), .cmd_addr(cmd_addr), .cmd_data(cmd_data), .cnt_ok(cnt_ok), .cnt_err(cnt_err));

task send_byte(input [7:0] b);
  begin
    @(posedge clk);
    while (!tx_ready) @(posedge clk);
    tx_data  <= b;
    tx_valid <= 1'b1;
    @(posedge clk);
    tx_valid <= 1'b0;
    @(posedge clk);
  end
endtask

function [7:0] crc8;
  input [39:0] v;
  integer i, j;
  reg [7:0] c;
  begin
    c = 8'h00;
    for (i = 4; i >= 0; i = i - 1) begin
      c = c ^ v[8*i +: 8];
      for (j = 0; j < 8; j = j + 1) c = c[7] ? ({c[6:0], 1'b0} ^ 8'h07) : {c[6:0], 1'b0};
    end
    crc8 = c;
  end
endfunction

task send_frame(input [7:0] a, input [31:0] d, input corrupt);
  reg [7:0] c;
  begin
    c = crc8({a, d});
    send_byte(8'hA5); send_byte(a); send_byte(d[31:24]); send_byte(d[23:16]); send_byte(d[15:8]); send_byte(d[7:0]);
    send_byte(corrupt ? (c ^ 8'h10) : c);
  end
endtask

reg [7:0]  got_addr; reg [31:0] got_data; integer got = 0;
always @(posedge clk) if (cmd_valid) begin got_addr = cmd_addr; got_data = cmd_data; got = got + 1; end

// ---------------------------------------------------------------- fast serial
reg  [7:0] fw_data = 8'h00; reg fw_en = 1'b0, fw_last = 1'b0;
wire fs_full, fs_line;
wire [15:0] fs_pkt;
reg  fs_flip = 1'b0;
gl_fastserial_tx #(.FIFO_LOG2(6)) fstx (.clk(clk), .tick(1'b1), .wr_data(fw_data), .wr_en(fw_en), .wr_last(fw_last), .full(fs_full), .txd(fs_line), .pkt_cnt(fs_pkt));
wire [7:0] fr_data; wire fr_last, fr_empty; reg fr_en = 1'b0;
wire [15:0] fs_ok, fs_err;
gl_fastserial_rx #(.FIFO_LOG2(6)) fsrx (.clk(clk), .bit_valid(1'b1), .bit_in(fs_line ^ fs_flip), .rd_data(fr_data), .rd_last(fr_last), .empty(fr_empty), .rd_en(fr_en), .pkt_ok(fs_ok), .pkt_err(fs_err));

reg [7:0] fr_bytes [0:63]; integer fr_n = 0;
always @(posedge clk) begin
  fr_en <= 1'b0;
  if (!fr_empty && !fr_en) begin
    fr_en <= 1'b1;
    fr_bytes[fr_n] = fr_data;
    fr_n = fr_n + 1;
  end
end

task fs_write(input [7:0] b, input last);
  begin
    @(posedge clk);
    fw_data <= b; fw_en <= 1'b1; fw_last <= last;
    @(posedge clk);
    fw_en <= 1'b0; fw_last <= 1'b0;
  end
endtask

integer i;
initial begin
  #100;
  // good frame
  send_frame(8'h01, 32'h12345678, 0);
  #200000;
  check(got == 1 && got_addr == 8'h01 && got_data == 32'h12345678, "UART command frame delivered");
  // corrupted frame
  send_frame(8'hC0, 32'h00000001, 1);
  #200000;
  check(got == 1 && cnt_err == 8'd1, "corrupted UART frame rejected");
  // resync: sync byte inside garbage then a good frame
  send_byte(8'h00); send_byte(8'hA5); send_byte(8'h11);
  #800000;  // timeout resets the parser
  send_frame(8'h3F, 32'hDEADBEEF, 0);
  #200000;
  check(got == 2 && got_addr == 8'h3F && got_data == 32'hDEADBEEF && cnt_err == 8'd2, "parser resynchronised after timeout");

  // fast serial: 5-byte packet then a 1-byte packet
  for (i = 0; i < 5; i = i + 1) fs_write(8'h10 + i, i == 4);
  fs_write(8'hEE, 1);
  #10000;
  check(fs_ok == 2 && fs_err == 0 && fr_n == 6 && fr_bytes[0] == 8'h10 && fr_bytes[4] == 8'h14 && fr_bytes[5] == 8'hEE, "fast serial packets delivered");
  // corrupt one bit during the next packet
  fork
    begin for (i = 0; i < 3; i = i + 1) fs_write(8'hA0 + i, i == 2); end
    begin #300; fs_flip = 1'b1; #13; fs_flip = 1'b0; end
  join
  #10000;
  $display("after corruption: fs_ok=%0d fs_err=%0d fr_n=%0d", fs_ok, fs_err, fr_n);
  check(fs_ok == 2 && fs_err >= 1 && fr_n == 6, "corrupted fast serial packet rejected, FIFO untouched");
  fs_write(8'h55, 1);
  #10000;
  check(fs_ok == 3 && fr_n == 7 && fr_bytes[6] == 8'h55, "fast serial recovers after a bad packet");

  if (errors == 0) $display("PASS"); else $display("FAIL: %0d errors", errors);
  $finish;
end

endmodule
