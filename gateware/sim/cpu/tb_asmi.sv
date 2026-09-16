// SPDX-License-Identifier: GPL-2.0-or-later
// Copyright 2026 Franz Schöning, https://www.schoning.com
//
// asmi_interface with the real ASMI megafunction netlist and an SPI flash model (epcs_model.v).
//  1. Network erase range: stock code (PROTECT_TOP = 0) versus hl2b5up_cpu (PROTECT_TOP = 1).
//  2. Network programming of pages, including a page at 0x1F0000 (must be skipped with PROTECT_TOP).
//  3. CPU port: erase, shift + program a page, read back; commands outside 0x1F0000-0x1FFFFF
//     rejected with the flash unchanged; CPU locked out after network flashing started.
`timescale 1 ps / 1 ps

module tb_asmi;

localparam real T_CLK = 400_000.0;     // 2.5 MHz

logic clk = 1'b0;
always #(T_CLK/2) clk = ~clk;

integer errors = 0;

task automatic check(input bit ok, input string what);
  if (ok) $display("  ok    %s", what);
  else begin $display("  FAIL  %s", what); errors++; end
endtask

// ---------------------------------------------------------------- two DUTs: stock and protected

genvar g;
for (g = 0; g < 2; g++) begin: dut
  logic        erase = 1'b0, erase_ack, erase_done, send_more;
  logic        ack = 1'b0;
  logic [9:0]  rx_used = 10'd0;
  logic        rdreq;
  logic [7:0]  fifo_q = 8'h00;
  logic [13:0] num_blocks = 14'd0;
  logic        nconfig;
  logic        cpu_req = 1'b0;
  logic [2:0]  cpu_cmd = 3'd0;
  logic [23:0] cpu_addr = 24'd0;
  logic [7:0]  cpu_data = 8'd0;
  logic        cpu_done;
  logic [2:0]  cpu_status;
  logic [7:0]  cpu_rdata;

  // network FIFO stand-in: page p byte i = p ^ i (bit-reversed by asmi_interface on the way in)
  integer page_no = 0, byte_no = 0;
  always @(posedge clk) if (rdreq) begin
    fifo_q  <= page_no[7:0] ^ byte_no[7:0];
    byte_no <= byte_no + 1;
  end

  asmi_interface #(.CPU_PORT(1), .PROTECT_TOP(g)) i (
    .clock(clk), .busy(), .erase(erase), .erase_ACK(erase_ack), .IF_Rx_used(rx_used), .rdreq(rdreq),
    .IF_PHY_data(fifo_q), .erase_done(erase_done), .erase_done_ACK(ack), .send_more(send_more),
    .send_more_ACK(ack), .num_blocks(num_blocks), .NCONFIG(nconfig),
    .cpu_req(cpu_req), .cpu_cmd(cpu_cmd), .cpu_addr(cpu_addr), .cpu_data(cpu_data),
    .cpu_done(cpu_done), .cpu_status(cpu_status), .cpu_rdata(cpu_rdata));
end

function automatic [7:0] rev8(input [7:0] b);
  for (int k = 0; k < 8; k++) rev8[k] = b[7-k];
endfunction

task automatic cpu_op(input int d, input [2:0] cmd, input [23:0] addr, input [7:0] data,
                      output [2:0] status, output [7:0] rdata);
  if (d == 0) begin
    dut[0].cpu_cmd = cmd; dut[0].cpu_addr = addr; dut[0].cpu_data = data; dut[0].cpu_req = 1'b1;
    wait (dut[0].cpu_done);
    status = dut[0].cpu_status; rdata = dut[0].cpu_rdata;
    dut[0].cpu_req = 1'b0;
    wait (!dut[0].cpu_done);
  end else begin
    dut[1].cpu_cmd = cmd; dut[1].cpu_addr = addr; dut[1].cpu_data = data; dut[1].cpu_req = 1'b1;
    wait (dut[1].cpu_done);
    status = dut[1].cpu_status; rdata = dut[1].cpu_rdata;
    dut[1].cpu_req = 1'b0;
    wait (!dut[1].cpu_done);
  end
endtask

// flash model instances inside the megafunction netlists
`define FL0 dut[0].i.asmi_inst.sd2.flash
`define FL1 dut[1].i.asmi_inst.sd2.flash

logic [2:0] st;
logic [7:0] rd;
integer n, bad;

initial begin
  $display("tb_asmi: ASMI megafunction + SPI flash model");
  repeat (20) @(posedge clk);

  // ---------------------------------------------------------- CPU port before any network flashing
  $display("CPU port (hl2b5up_cpu configuration)");
  // pre-fill a byte just below the sector and in the factory area to detect stray writes
  `FL1.mem[24'h1EFFFF] = 8'h5A;
  `FL1.mem[24'h000100] = 8'hA5;
  cpu_op(1, 3'd1, 24'h000000, 8'h00, st, rd);                // erase: address ignored, always 0x1F0000
  check(st == 3'b000 && `FL1.n_erase == 1 && `FL1.last_erase == 24'h1F0000, "erase goes to sector 0x1F0000 only");
  check(`FL1.mem[24'h1EFFFF] == 8'h5A && `FL1.mem[24'h000100] == 8'hA5, "neighbouring data untouched by the CPU erase");
  for (n = 0; n < 256; n++) begin
    cpu_op(1, 3'd2, 24'h0, 8'(n * 7 + 3), st, rd);
  end
  cpu_op(1, 3'd3, 24'h1F0100, 8'h00, st, rd);
  check(st == 3'b000 && `FL1.n_prog == 1 && `FL1.prog_min == 24'h1F0100 && `FL1.prog_max == 24'h1F01FF,
        "page program at 0x1F0100 (256 bytes)");
  bad = 0;
  for (n = 0; n < 256; n++) if (`FL1.mem[24'h1F0100 + n] != 8'(n * 7 + 3)) bad++;
  check(bad == 0, "flash holds the shifted bytes");
  bad = 0;
  for (n = 0; n < 300; n += 37) begin
    cpu_op(1, 3'd4, 24'h1F0100 + n, 8'h00, st, rd);
    if (st != 3'b000 || rd != (n < 256 ? 8'(n * 7 + 3) : 8'hff)) begin
      bad++;
      $display("        read 0x%06x: status %b data %02x", 24'h1F0100 + n, st, rd);
    end
  end
  check(bad == 0, "CPU reads return the flash bytes");
  cpu_op(1, 3'd4, 24'h1FFFFF, 8'h00, st, rd);
  check(st == 3'b000 && rd == 8'hff, "read at the last byte 0x1FFFFF allowed");

  n = `FL1.n_prog;
  cpu_op(1, 3'd4, 24'h1EFFFF, 8'h00, st, rd);
  check(st == 3'b001, "read at 0x1EFFFF rejected");
  cpu_op(1, 3'd4, 24'h000100, 8'h00, st, rd);
  check(st == 3'b001, "read in the factory image area rejected");
  cpu_op(1, 3'd2, 24'h0, 8'h00, st, rd);
  cpu_op(1, 3'd3, 24'h100000, 8'h00, st, rd);
  check(st == 3'b001, "program at 0x100000 (application image) rejected");
  cpu_op(1, 3'd3, 24'h000000, 8'h00, st, rd);
  check(st == 3'b001, "program at 0x000000 (factory image) rejected");
  cpu_op(1, 3'd3, 24'h1F0080, 8'h00, st, rd);
  check(st == 3'b001, "program at a non page-aligned address rejected");
  cpu_op(1, 3'd3, 24'h2F0000, 8'h00, st, rd);
  check(st == 3'b001, "program at 0x2F0000 (beyond the device) rejected");
  check(`FL1.n_prog == n && `FL1.n_erase == 1 && `FL1.mem[24'h1EFFFF] == 8'h5A && `FL1.mem[24'h000100] == 8'hA5,
        "no flash write for any rejected command");

  // ---------------------------------------------------------- network erase range
  $display("Network erase (openHPSDR erase command)");
  `FL0.erased_sectors = '0;
  `FL1.erased_sectors = '0;
  `FL1.mem[24'h1F0000] = 8'h11;          // stands in for a saved firmware header
  dut[0].erase = 1'b1;
  dut[1].erase = 1'b1;
  wait (dut[0].erase_ack && dut[1].erase_ack);
  dut[0].erase = 1'b0;
  dut[1].erase = 1'b0;
  wait (dut[0].erase_done && dut[1].erase_done);
  dut[0].ack = 1'b1; dut[1].ack = 1'b1;
  repeat (4) @(posedge clk);
  dut[0].ack = 1'b0; dut[1].ack = 1'b0;
  $display("        stock:     erased sectors 0x%h", `FL0.erased_sectors[31:0]);
  $display("        protected: erased sectors 0x%h", `FL1.erased_sectors[31:0]);
  check(`FL0.erased_sectors[31:0] == 32'hFFFF0000, "stock code erases 0x100000-0x1FFFFF, including the sector 0x1F0000");
  check(`FL1.erased_sectors[31:0] == 32'h7FFF0000, "PROTECT_TOP erases 0x100000-0x1EFFFF, not 0x1F0000");
  check(`FL1.mem[24'h1F0000] == 8'h11, "saved firmware sector survives a network erase");

  // CPU is now locked out
  n = `FL1.n_erase;
  cpu_op(1, 3'd1, 24'h0, 8'h00, st, rd);
  check(st == 3'b010 && `FL1.n_erase == n, "CPU erase refused after network flashing started (locked)");
  cpu_op(1, 3'd4, 24'h1F0000, 8'h00, st, rd);
  check(st == 3'b010, "CPU read refused while locked");

  // ---------------------------------------------------------- network programming reaching 0x1F0000
  $display("Network programming of pages 0x1EFF00 and 0x1F0000 (an image that is too long)");
  `FL1.prog_min = 24'hffffff; `FL1.prog_max = 24'h0;
  n = `FL1.n_prog;
  // start the programming at 0x1EFF00: 0x1EFF00 - 0x100000 = 0xEFF00 = page 3839
  force dut[1].i.address = 24'h1EFF00;
  dut[1].num_blocks = 14'd2;
  dut[1].page_no = 1;
  dut[1].rx_used = 10'd300;
  wait (dut[1].i.state == 5'd6);
  release dut[1].i.address;
  wait (dut[1].send_more);
  wait (dut[1].i.state == 5'd8);
  dut[1].ack = 1'b1;
  wait (!dut[1].send_more);
  dut[1].ack = 1'b0;
  dut[1].page_no = 2;
  wait (dut[1].i.state == 5'd9);
  dut[1].rx_used = 10'd0;
  dut[1].ack = 1'b1;
  wait (dut[1].i.state == 5'd10);
  dut[1].ack = 1'b0;
  repeat (4000) @(posedge clk);
  check(`FL1.n_prog == n + 1 && `FL1.prog_min == 24'h1EFF00 && `FL1.prog_max == 24'h1EFFFF,
        "page 0x1EFF00 programmed, page 0x1F0000 skipped");
  check(`FL1.mem[24'h1F0000] == 8'h11, "sector 0x1F0000 contents unchanged");

  $display("tb_asmi: %s (%0d errors)", errors == 0 ? "PASS" : "FAIL", errors);
  $finish;
end

initial begin
  #(64'd40_000_000_000_000);
  $display("tb_asmi: FAIL timeout");
  $finish;
end

endmodule
