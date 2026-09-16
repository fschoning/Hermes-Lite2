// SPDX-License-Identifier: GPL-2.0-or-later
// Copyright 2026 Franz Schöning, https://www.schoning.com
//
// hl2b5up_neo soft CPU system (NEORV32 rv32imc) with the real boot ROM and demo application.
// Derived from tb_cpu.sv (hl2b5up_cpu, VexRiscv); the NEORV32 is the Verilog produced by
// rtl/neorv32/convert.sh.
//
// DUT (wired as in rtl/hermeslite_core.v, HL2BUS_ON.CPU_ON): ebbridge (CPU_IO = 1), hl2bus_regs,
// wb_cdc, pbuf_ram, hl2cpu (CORE = 2, ROM from bootrom_neo.hex), asmi_interface (CPU_PORT, PROTECT_TOP)
// with the ASMI megafunction netlist and an SPI flash model. The PC side drives the bridge's UDP
// receive interface directly and captures the datagrams the bridge sends.
//
// Checks: ROM boot and console banner; bridge register reads through both paths; flash guard
// (commands outside 0x1F0000-0x1FFFFF rejected); RAM load via the bridge with the CPU in reset and
// start (hl2fw.py run); demo console output with the temperature; halt and resume; crash with the
// bridge still working; save to flash (hl2fw.py save) and boot from flash after reset; stay-in-ROM
// override; firmware saved by the VexRiscv ROM (header format 1) refused; GDB stub (qSupported, ?, g,
// m, X load, P, breakpoint by ebreak and c.ebreak, continue, single step with the step interrupt, also
// where the target has interrupts off, console as 'O' packets, Ctrl-C, monitor command, detach);
// network erase locks the CPU out of the flash.
`timescale 1 ps / 1 ps

module tb_neo;

localparam real T_ETH  = 80_000.0;      // Ethernet send clock at 100 Mbit/s rate (12.5 MHz), keeps the simulation fast
localparam real T_RX   = 80_100.0;      // receive clock, not locked to the send clock
localparam real T_CPU  = 80_000.0;      // 12.5 MHz
localparam real T_CTRL = 400_000.0;     // 2.5 MHz
localparam      MS_DIV = 125;           // simulated millisecond = 125 CPU cycles (10 us)

logic clk = 0, clk_rx = 0, clk_cpu = 0, clk_ctrl = 0;
always #(T_ETH/2)  clk      = ~clk;
always #(T_RX/2)   clk_rx   = ~clk_rx;
always #(T_CPU/2)  clk_cpu  = ~clk_cpu;
always #(T_CTRL/2) clk_ctrl = ~clk_ctrl;

logic rst_async = 1'b1;
initial #(1_000_000) rst_async = 1'b0;

// Real hardware powers up with arbitrary register-file and RAM contents; the simulator would carry
// X values through saved-and-restored registers, so start from zeros.
initial begin
  for (int i = 0; i < 32; i++) cpu_sys.NEO.cpu_i.neorv32_top_inst.core_complex_gen_n1_neorv32_cpu_inst.neorv32_cpu_regfile_inst.regfile[i] = 32'd0;
  for (int i = 0; i < 4096; i++) cpu_sys.ram[i] = 32'd0;
end

integer errors = 0;
task automatic check(input bit ok, input string what);
  if (ok) $display("[%0d ms] ok    %s", $time / 1000_000_000, what);
  else begin $display("[%0d ms] FAIL  %s", $time / 1000_000_000, what); errors = errors + 1; end
  $fflush();
endtask

//////////////////////////////////////////////////////////////////////////////
// DUT

logic [15:0] eth_port = 16'd1027;
logic        eth_broadcast = 1'b0, eth_valid = 1'b0;
logic [ 7:0] eth_data = 8'h00;
logic        dest_valid = 1'b0;
logic        eth_valid_d = 1'b0;
always @(posedge clk) eth_valid_d <= eth_valid;

logic        eb_ready, eb_grant, eb_busy, eb_enable;
logic [ 1:0] eb_tx_request;
logic [15:0] eb_tx_length;
logic [ 7:0] eb_tx_data;
logic [29:0] wb_adr;
logic [31:0] wb_dat_w, wb_dat_r, reg_dat_r, cdc_dat_r;
logic [ 3:0] wb_sel;
logic        wb_we, wb_cyc, wb_stb, wb_ack, wb_err, reg_ack, reg_err, cdc_ack, cdc_err;
logic [95:0] eb_stats;
logic [ 9:0] pb_adr_a, pb_adr_b, cpu_rx_wr, cpu_rx_rd;
logic        pb_we_a, pb_we_b, cpu_tx_req, cpu_tx_done;
logic [ 7:0] pb_wd_a, pb_wd_b, pb_q_a, pb_q_b;
logic [ 8:0] cpu_tx_len;
logic [31:0] cpu_counts;
logic        wb_regs;
wire         to_cpu = ~wb_regs;

ebbridge #(.CPU_IO(1)) ebbridge_i (
  .clk_rx(clk_rx), .eth_port(eth_port), .eth_broadcast(eth_broadcast), .eth_valid(eth_valid), .eth_data(eth_data),
  .clk(clk), .dest_valid(dest_valid), .room(16'hffff), .ready(eb_ready), .grant(eb_grant),
  .tx_request(eb_tx_request), .tx_length(eb_tx_length), .tx_data(eb_tx_data), .tx_enable(eb_enable), .busy(eb_busy),
  .wb_adr(wb_adr), .wb_regs(wb_regs), .wb_dat_w(wb_dat_w), .wb_dat_r(wb_dat_r), .wb_sel(wb_sel), .wb_we(wb_we), .wb_cyc(wb_cyc),
  .wb_stb(wb_stb), .wb_ack(wb_ack), .wb_err(wb_err), .stats(eb_stats),
  .pb_adr(pb_adr_b), .pb_we(pb_we_b), .pb_wd(pb_wd_b), .pb_q(pb_q_b), .clk_cpu(clk_cpu),
  .cpu_rx_wr(cpu_rx_wr), .cpu_rx_rd(cpu_rx_rd), .cpu_tx_req(cpu_tx_req), .cpu_tx_len(cpu_tx_len),
  .cpu_tx_done(cpu_tx_done), .cpu_counts(cpu_counts));

assign wb_dat_r = to_cpu ? cdc_dat_r : reg_dat_r;
assign wb_ack   = to_cpu ? cdc_ack   : reg_ack;
assign wb_err   = to_cpu ? cdc_err   : reg_err;

logic [11:0] temp_code = 12'd942;
logic [52:0] ctrl_status;
assign ctrl_status = {5'b00000, temp_code, 12'd11, 12'd22, 12'd33};

hl2bus_regs #(.VERSION_MAJOR(8'd74), .VERSION_MINOR(8'd2), .DIAG_ID(8'hC3), .CAPS(16'h003C)) regs_i (
  .clk(clk), .wb_adr(wb_adr), .wb_dat_w(wb_dat_w), .wb_dat_r(reg_dat_r), .wb_sel(wb_sel), .wb_we(wb_we),
  .wb_cyc(wb_cyc & ~to_cpu), .wb_stb(wb_stb & ~to_cpu), .wb_ack(reg_ack), .wb_err(reg_err),
  .bridge_stats(eb_stats), .tx_status(8'h01), .ctrl_status(ctrl_status), .cmd_addr(6'd0), .cmd_data(32'd0),
  .cmd_rqst(1'b0), .inj_req(), .inj_addr(), .inj_data(), .inj_ack(1'b0));

logic        br_req, br_we, br_done, br_err;
logic [29:0] br_adr;
logic [31:0] br_dat_w, br_dat_r;
logic [ 3:0] br_sel;

wb_cdc wb_cdc_i (
  .clk_m(clk), .m_adr(wb_adr), .m_dat_w(wb_dat_w), .m_sel(wb_sel), .m_we(wb_we), .m_stb(wb_stb & to_cpu),
  .m_dat_r(cdc_dat_r), .m_ack(cdc_ack), .m_err(cdc_err), .clk_s(clk_cpu), .s_req(br_req), .s_adr(br_adr),
  .s_dat_w(br_dat_w), .s_sel(br_sel), .s_we(br_we), .s_done(br_done), .s_dat_r(br_dat_r), .s_err(br_err));

pbuf_ram pbuf_ram_i (
  .clk_a(clk_cpu), .adr_a(pb_adr_a), .we_a(pb_we_a), .wd_a(pb_wd_a), .q_a(pb_q_a),
  .clk_b(clk), .adr_b(pb_adr_b), .we_b(pb_we_b), .wd_b(pb_wd_b), .q_b(pb_q_b));

logic        fl_req, fl_done, led_en, led_on;
logic [ 2:0] fl_cmd, fl_status;
logic [23:0] fl_addr;
logic [ 7:0] fl_data, fl_rdata;

hl2cpu #(.CORE(2), .ROM_WORDS(1024), .RAM_WORDS(4096), .ROM_HEX("bootrom_neo.hex"), .VERSION_MAJOR(8'd74),
         .VERSION_MINOR(8'd2), .DIAG_ID(8'hC3), .CAPS(16'h003C), .MS_DIV(MS_DIV)) cpu_sys (
  .clk(clk_cpu), .rst_async(rst_async),
  .br_req(br_req), .br_adr(br_adr), .br_dat_w(br_dat_w), .br_sel(br_sel), .br_we(br_we),
  .br_done(br_done), .br_dat_r(br_dat_r), .br_err(br_err),
  .clk_ctrl(clk_ctrl), .ctrl_status(ctrl_status), .clk_eth(clk), .tx_status(8'h01),
  .pb_adr(pb_adr_a), .pb_we(pb_we_a), .pb_wd(pb_wd_a), .pb_q(pb_q_a),
  .eth_rx_wr(cpu_rx_wr), .rx_rd(cpu_rx_rd), .tx_req(cpu_tx_req), .tx_len(cpu_tx_len),
  .eth_tx_done(cpu_tx_done), .eth_dest(dest_valid), .eth_counts(cpu_counts),
  .fl_req(fl_req), .fl_cmd(fl_cmd), .fl_addr(fl_addr), .fl_data(fl_data), .fl_done(fl_done),
  .fl_status(fl_status), .fl_rdata(fl_rdata), .led_en(led_en), .led_on(led_on), .cpu_running());

logic        net_erase = 1'b0;
asmi_interface #(.CPU_PORT(1), .PROTECT_TOP(1)) asmi_i (
  .clock(clk_ctrl), .busy(), .erase(net_erase), .erase_ACK(), .IF_Rx_used(10'd0), .rdreq(), .IF_PHY_data(8'h00),
  .erase_done(), .erase_done_ACK(1'b1), .send_more(), .send_more_ACK(1'b0), .num_blocks(14'd0), .NCONFIG(),
  .cpu_req(fl_req), .cpu_cmd(fl_cmd), .cpu_addr(fl_addr), .cpu_data(fl_data), .cpu_done(fl_done),
  .cpu_status(fl_status), .cpu_rdata(fl_rdata));

`define FLASH asmi_i.asmi_inst.sd2.flash

//////////////////////////////////////////////////////////////////////////////
// Send slot (as rawstream/network grant it)

logic        grant_d = 1'b0;
integer      req_cnt = 0;
logic        tx_en = 1'b0;
assign eb_grant  = eb_ready & ~grant_d & ~eb_busy;
assign eb_enable = tx_en;
always @(posedge clk) begin
  grant_d <= eb_grant;
  tx_en   <= 1'b0;
  if (eb_tx_request == 2'b01) begin
    req_cnt <= req_cnt + 1;
    if (req_cnt == 3) tx_en <= 1'b1;
  end else req_cnt <= 0;
end

// capture: the bridge drives one payload byte per cycle from the cycle after the send enable
// (the network's udp_send takes them the same way)
logic         tx_en_d = 1'b0;
integer       cap_left = 0;
logic [7:0]   capbuf [0:2047];
integer       caplen = 0;
byte unsigned con[$];                   // console bytes
byte unsigned gdb[$];                   // gdb stream bytes
logic [31:0]  eb_reply [0:63];
integer       eb_reply_n = 0;
integer       n_eb_replies = 0;
integer       k;

always @(posedge clk) begin
  tx_en_d <= tx_en;
  if (tx_en_d) begin
    cap_left = eb_tx_length;
    caplen = 0;
  end
  if (cap_left > 0) begin
    capbuf[caplen] = eb_tx_data;
    caplen = caplen + 1;
    cap_left = cap_left - 1;
    if (cap_left == 0) begin
      if (caplen >= 8 && capbuf[0] == 8'h4e && capbuf[1] == 8'h6f) begin
        eb_reply_n = 0;
        for (k = 16; k + 3 < caplen; k = k + 4) begin
          eb_reply[eb_reply_n] = {capbuf[k], capbuf[k+1], capbuf[k+2], capbuf[k+3]};
          eb_reply_n = eb_reply_n + 1;
        end
        n_eb_replies = n_eb_replies + 1;
      end else if (caplen >= 2 && capbuf[0] == 8'h01 && capbuf[1] == 8'h43) begin
        for (k = 2; k < caplen; k = k + 1) con.push_back(capbuf[k]);
      end else begin
        for (k = 0; k < caplen; k = k + 1) gdb.push_back(capbuf[k]);
      end
    end
  end
end

// echo the console to the log, line by line
integer con_shown = 0, kk;
string  line;
always @(posedge clk) begin
  if (con_shown < con.size() && con[con.size() - 1] == 8'h0a) begin
    line = "";
    for (kk = con_shown; kk < con.size(); kk = kk + 1) begin
      if (con[kk] == 8'h0a) begin
        if (line.len() > 0) begin $display("        console | %s", line); $fflush(); end
        line = "";
      end else line = $sformatf("%s%c", line, con[kk]);
    end
    con_shown = con.size();
  end
end

//////////////////////////////////////////////////////////////////////////////
// PC side

byte unsigned txq[$];
integer       txq_len[$];
integer       tn, ti;
always @(posedge clk_rx) begin
  if (txq_len.size() > 0) begin
    tn = txq_len.pop_front();
    repeat (4) @(posedge clk_rx);
    dest_valid <= 1'b1;
    eth_port   <= 16'd1027;
    for (ti = 0; ti < tn; ti = ti + 1) begin
      eth_valid <= 1'b1;
      eth_data  <= txq.pop_front();
      @(posedge clk_rx);
    end
    eth_valid <= 1'b0;
    // at least the Ethernet CRC, gap, preamble and MAC/IP/UDP headers of the next frame (66 bytes)
    repeat (66) @(posedge clk_rx);
  end
end

byte unsigned pkt[$];                   // datagram under construction

task automatic send_pkt();
  txq_len.push_back(pkt.size());
  for (int i = 0; i < pkt.size(); i++) txq.push_back(pkt[i]);
  pkt.delete();
  while (txq_len.size() != 0) @(posedge clk_rx);
  @(posedge clk_rx);
  wait (!eth_valid);
  repeat (10) @(posedge clk_rx);
endtask

task automatic put_str(input string s);
  for (int i = 0; i < s.len(); i++) pkt.push_back(s[i]);
endtask

task automatic wait_us(input integer us);
  #(64'd1_000_000 * us);
endtask

function automatic int con_find(input string sub, input int from);
  int i, j, m;
  for (i = from; i + sub.len() <= con.size(); i++) begin
    m = 1;
    for (j = 0; j < sub.len(); j++) if (con[i + j] != sub[j]) begin m = 0; break; end
    if (m) return i;
  end
  return -1;
endfunction

function automatic int gdb_find(input byte unsigned ch, input int from);
  for (int i = from; i < gdb.size(); i++) if (gdb[i] == ch) return i;
  return -1;
endfunction

task automatic wait_console(input string sub, input integer from, input integer timeout_ms, output bit found);
  integer t;
  t = 0;
  found = 0;
  while (t < timeout_ms * 10) begin
    if (con_find(sub, from) >= 0) begin found = 1; return; end
    wait_us(100);
    t = t + 1;
  end
endtask

// Etherbone request: nw writes at wbase and/or nr reads; the reply values land in eb_reply[]
logic [31:0] ebw [0:63];
logic [31:0] ebr [0:63];
task automatic eb(input integer nw, input [31:0] wbase, input integer nr, output bit ok);
  integer nbefore, t, attempt;
  ok = 0;
  for (attempt = 0; attempt < 4 && !ok; attempt++) begin
    pkt.delete();
    pkt.push_back(8'h4e); pkt.push_back(8'h6f); pkt.push_back(8'h10); pkt.push_back(8'h44);
    repeat (4) pkt.push_back(8'h00);
    pkt.push_back(8'h00); pkt.push_back(8'h0f); pkt.push_back(nw[7:0]); pkt.push_back(nr[7:0]);
    if (nw > 0) begin
      for (int b = 3; b >= 0; b--) pkt.push_back(wbase[8*b +: 8]);
      for (int i = 0; i < nw; i++) for (int b = 3; b >= 0; b--) pkt.push_back(ebw[i][8*b +: 8]);
    end
    if (nr > 0) begin
      repeat (4) pkt.push_back(8'h00);
      for (int i = 0; i < nr; i++) for (int b = 3; b >= 0; b--) pkt.push_back(ebr[i][8*b +: 8]);
    end
    nbefore = n_eb_replies;
    send_pkt();
    if (nr == 0) begin wait_us(3000); ok = 1; end
    else begin
      t = 0;
      while (n_eb_replies == nbefore && t < 300) begin wait_us(100); t++; end
      ok = (n_eb_replies != nbefore) && (eb_reply_n == nr);
    end
  end
endtask

task automatic rd(input [31:0] a, output [31:0] v);
  bit ok;
  ebr[0] = a;
  eb(0, 0, 1, ok);
  v = ok ? eb_reply[0] : 32'hdeadbeef;
endtask

task automatic wr(input [31:0] a, input [31:0] v);
  bit ok;
  ebw[0] = v;
  ebr[0] = a;
  eb(1, a, 1, ok);                      // write and read back in one record (gives a reply)
endtask

// restart the CPU with control bits c and wait until the boot ROM has started (as hl2fw.py does)
task automatic cpu_restart(input [31:0] c);
  logic [31:0] st;
  integer t;
  wr(32'h40010008, c | 32'h1);
  wr(32'h40010010, 32'h0);
  wr(32'h40010008, c);
  st = 0;
  t = 0;
  while (st[31:24] < 8'd2 && t < 200) begin wait_us(500); rd(32'h40010010, st); t++; end
endtask

// control datagram for the boot ROM (as hl2fw.py sends it)
logic [31:0] cargs [0:7];
task automatic ctrl(input byte unsigned c, input integer nargs);
  pkt.delete();
  pkt.push_back(8'h01);
  pkt.push_back(c);
  for (int i = 0; i < nargs; i++) for (int b = 0; b < 4; b++) pkt.push_back(cargs[i][8*b +: 8]);
  send_pkt();
endtask

// gdb: "+" (optional) and "$body#cs"
task automatic gdb_send(input bit ack, input string body);
  byte unsigned cs;
  cs = 0;
  pkt.delete();
  if (ack) pkt.push_back("+");
  pkt.push_back("$");
  for (int i = 0; i < body.len(); i++) begin pkt.push_back(body[i]); cs += body[i]; end
  put_str($sformatf("#%02x", cs));
  send_pkt();
endtask

// binary body variant (X packets): body bytes already escaped in 'pkt' after a prefix
task automatic gdb_send_pkt_body();
  byte unsigned cs;
  byte unsigned b[$];
  cs = 0;
  b = pkt;
  pkt.delete();
  pkt.push_back("+");
  pkt.push_back("$");
  for (int i = 0; i < b.size(); i++) begin pkt.push_back(b[i]); cs += b[i]; end
  put_str($sformatf("#%02x", cs));
  send_pkt();
endtask

// next complete gdb packet after position gpos; body into rbody[0..rlen-1]
byte unsigned rbody [0:1023];
integer rlen;
integer gpos = 0;
task automatic gdb_reply(input integer timeout_ms, output bit ok);
  integer t, s, h;
  t = 0;
  ok = 0;
  rlen = 0;
  while (t < timeout_ms * 10) begin
    s = gdb_find("$", gpos);
    h = (s >= 0) ? gdb_find("#", s) : -1;
    if (s >= 0 && h >= 0 && h + 2 < gdb.size()) begin
      for (int i = s + 1; i < h; i++) begin rbody[rlen] = gdb[i]; rlen++; end
      gpos = h + 3;
      ok = 1;
      return;
    end
    wait_us(100);
    t++;
  end
endtask

function automatic bit body_is(input string s);
  if (s.len() != rlen) return 0;
  for (int i = 0; i < rlen; i++) if (rbody[i] != s[i]) return 0;
  return 1;
endfunction

function automatic string body_str();
  string r;
  r = "";
  for (int i = 0; i < rlen && i < 80; i++) r = $sformatf("%s%c", r, rbody[i]);
  return r;
endfunction

function automatic [3:0] hexd(input byte unsigned c);
  if (c >= "0" && c <= "9") return c - "0";
  if (c >= "a" && c <= "f") return c - "a" + 10;
  return c - "A" + 10;
endfunction

function automatic [31:0] body_le32(input int at);
  logic [31:0] v;
  for (int i = 0; i < 4; i++) v[8*i +: 8] = {hexd(rbody[at + 2*i]), hexd(rbody[at + 2*i + 1])};
  return v;
endfunction

// skip console 'O' packets, return the next other packet
task automatic gdb_reply_skip_o(input integer timeout_ms, output bit ok);
  gdb_reply(timeout_ms, ok);
  while (ok && rlen > 0 && rbody[0] == "O" && !body_is("OK")) gdb_reply(timeout_ms, ok);
endtask

//////////////////////////////////////////////////////////////////////////////
// Demo image

byte unsigned demo[$];
byte unsigned hdr[$];

task automatic put_le32(input [31:0] x);
  for (int i = 0; i < 4; i++) hdr.push_back(x[8*i +: 8]);
endtask

function automatic [31:0] crc32_hdr();      // CRC-32 of hdr[]
  logic [31:0] crc;
  crc = 32'hffffffff;
  for (int i = 0; i < hdr.size(); i++) begin
    crc = crc ^ hdr[i];
    for (int b = 0; b < 8; b++) crc = (crc >> 1) ^ (32'hEDB88320 & {32{crc[0]}});
  end
  return ~crc;
endfunction
integer fd, c;
logic [31:0] demo_crc;
logic [31:0] demo_wfi = 32'h82c;
logic [31:0] demo_out = 32'h84a;        // out(): ends with a tail call into the boot ROM (c.jr a5)
logic [31:0] jr_addr;

function automatic [31:0] crc32_img();
  logic [31:0] crc;
  crc = 32'hffffffff;
  for (int i = 0; i < demo.size(); i++) begin
    crc = crc ^ demo[i];
    for (int b = 0; b < 8; b++) crc = (crc >> 1) ^ (32'hEDB88320 & {32{crc[0]}});
  end
  return ~crc;
endfunction

function automatic [31:0] demo_word(input int off);
  return {demo[off+3], demo[off+2], demo[off+1], demo[off]};
endfunction

task automatic load_demo_via_bridge(output bit ok);
  bit eok;
  integer bad, off, n;
  bad = 0;
  for (off = 0; off < demo.size(); off += 4 * 32) begin
    n = (demo.size() - off) / 4;
    if (n > 32) n = 32;
    for (int i = 0; i < n; i++) ebw[i] = demo_word(off + 4 * i);
    eb(n, 32'h800 + off, 0, eok);
  end
  for (off = 0; off < demo.size(); off += 4 * 32) begin
    n = (demo.size() - off) / 4;
    if (n > 32) n = 32;
    for (int i = 0; i < n; i++) ebr[i] = 32'h800 + off + 4 * i;
    eb(0, 0, n, eok);
    if (!eok) bad++;
    else for (int i = 0; i < n; i++) if (eb_reply[i] != demo_word(off + 4 * i)) bad++;
  end
  ok = (bad == 0);
endtask

//////////////////////////////////////////////////////////////////////////////
// Test sequence

logic [31:0] v;
bit ok, found;
integer mark, n, off, n2;
byte unsigned bb;
string s;

initial begin
  fd = $fopen("../../../firmware/hl2neo/build/demo.bin", "rb");
  if (fd == 0) begin $display("tb_neo: demo.bin not found (run firmware/hl2neo/build.py)"); $finish; end
  c = $fgetc(fd);
  while (c != -1) begin demo.push_back(c[7:0]); c = $fgetc(fd); end
  $fclose(fd);
  while (demo.size() % 4) demo.push_back(8'h00);
  demo_crc = crc32_img();
  if ($value$plusargs("demo_wfi=%h", demo_wfi)) ;
  if ($value$plusargs("demo_out=%h", demo_out)) ;
  $display("tb_neo: demo %0d bytes, crc %08x, cpu_wfi at %08x", demo.size(), demo_crc, demo_wfi);

  wait (!rst_async);
  wait_us(20000);

  // ------------------------------------------------------------------ ROM boot, console
  $display("--- boot ROM start (flash sector empty)");
  ctrl("A", 0);
  wait_console("HL2 RV32 boot ROM NEORV32", 0, 20, found);
  check(found, "console attach replays the boot banner");
  wait_console("result 42010006", 0, 50, found);
  check(found, "no saved firmware: boot result 'B' code 6 (no image)");
  rd(32'h40010010, v);
  check(v == 32'h02000000, $sformatf("FW_STATUS = ROM idle (%08x)", v));

  if (!$test$plusargs("gdb_only")) begin
  // ------------------------------------------------------------------ bridge paths
  $display("--- bridge");
  rd(32'h40000000, v);  check(v == 32'h484c3242, $sformatf("bridge register block ID %08x", v));
  rd(32'h40000010, v);  check(v != 32'hffffffff && v > 0, $sformatf("bridge request counter from the bridge's own block (%0d)", v));
  wr(32'h40000008, 32'hcafef00d);
  check(eb_reply[0] == 32'hcafef00d, $sformatf("bridge scratch register write/read back (%08x)", eb_reply[0]));
  rd(32'h40010000, v);  check(v == 32'h52563332, $sformatf("CPU system ID through the clock crossing %08x", v));
  rd(32'h40010004, v);  check(v == 32'h02041000, $sformatf("SYS_INFO: map version 2 (NEORV32), ROM 4 kB, RAM 16 kB (%08x)", v));
  rd(32'h00010004, v);  check(v == 32'h4d4f5248, $sformatf("boot ROM readable by the bridge (%08x)", v));
  wr(32'h00010004, 32'h12345678);
  check(eb_reply[0] == 32'h4d4f5248, "bridge write to the ROM refused");
  rd(32'h50000000, v);  check(v == 32'hffffffff, $sformatf("unmapped CPU-side address reads %08x", v));
  if ($test$plusargs("quick")) begin $display("tb_neo: quick run ends here (%0d errors)", errors); $finish; end

  // ------------------------------------------------------------------ flash guard
  if (!$test$plusargs("skip_guard")) begin
  $display("--- flash sector guard (commands from the bridge through the CPU flash registers)");
  `FLASH.mem[24'h1EFFFF] = 8'h5a;
  `FLASH.mem[24'h100000] = 8'ha5;
  n = `FLASH.n_prog;
  wr(32'h40030000, 32'h100000); wr(32'h40030008, 4); wait_us(3000); rd(32'h40030008, v);
  check(v[1] == 1'b1 && v[0] == 1'b0, $sformatf("read at 0x100000 rejected (status %0x)", v));
  wr(32'h40030000, 32'h1effff); wr(32'h40030008, 4); wait_us(3000); rd(32'h40030008, v);
  check(v[1] == 1'b1, "read at 0x1EFFFF rejected");
  wr(32'h40030000, 32'h1f0010); wr(32'h40030008, 4); wait_us(3000); rd(32'h40030008, v);
  check(v[1] == 1'b0 && v[0] == 1'b0, "read at 0x1F0010 accepted");
  wr(32'h40030004, 32'h00); wr(32'h40030008, 2); wait_us(3000);
  wr(32'h40030000, 32'h000000); wr(32'h40030008, 3); wait_us(3000); rd(32'h40030008, v);
  check(v[1] == 1'b1, "program at 0x000000 (factory image) rejected");
  wr(32'h40030000, 32'h1e0000); wr(32'h40030008, 3); wait_us(3000); rd(32'h40030008, v);
  check(v[1] == 1'b1, "program at 0x1E0000 rejected");
  wr(32'h40030000, 32'h200000); wr(32'h40030008, 3); wait_us(3000); rd(32'h40030008, v);
  check(v[1] == 1'b1, "program at 0x200000 rejected");
  check(`FLASH.n_prog == n && `FLASH.n_erase == 0 && `FLASH.mem[24'h1EFFFF] == 8'h5a && `FLASH.mem[24'h100000] == 8'ha5,
        "flash unchanged outside the sector");
  end

  // ------------------------------------------------------------------ hl2fw run
  $display("--- load the demo into RAM with the CPU held in reset, start it");
  wr(32'h40010008, 32'h1);
  rd(32'h4001002c, v);
  check(v[16] == 1'b1, "CPU held in reset");
  load_demo_via_bridge(ok);
  check(ok, "demo written into RAM and read back through the bridge");
  wr(32'h4001000c, 32'h800);
  mark = con.size();
  cpu_restart(32'h8);                       // boot RAM
  ctrl("A", 0);
  wait_console("demo: HL2 RV32 demo", mark, 500, found);
  check(found, "demo banner on the console");
  wait_console("C  code 942", mark, 3000, found);
  check(found, "demo prints the temperature (code 942)");
  wait_console("n 1", mark, 3000, found);
  check(found, "second temperature line one simulated second later");
  check(led_en == 1'b1, "demo drives LED D5");

  // ------------------------------------------------------------------ halt
  $display("--- halt and resume from the bridge");
  wr(32'h40010008, 32'ha);              // halt
  mark = con.size();
  ebr[0] = 32'h800; ebr[1] = 32'h40010018;
  eb(0, 0, 2, ok);
  check(ok && eb_reply[0] == demo_word(0), "RAM readable while the CPU is halted");
  wait_us(25000);
  check(con.size() == mark, "no console output while halted");
  wr(32'h40010008, 32'h8);
  wait_console("C  code", mark, 3000, found);
  check(found, "demo continues after resume");

  // ------------------------------------------------------------------ crash
  $display("--- crash the demo, bridge keeps working");
  mark = con.size();
  wr(demo_wfi, 32'h00000000);           // all-zero word: illegal instruction
  wait_console("stop, mcause 00000002", mark, 3000, found);
  check(found, "illegal instruction reported on the console");
  rd(32'h40010010, v);
  check(v == 32'h04000004, $sformatf("FW_STATUS = stopped, SIGILL (%08x)", v));
  wr(32'h40010030, 32'hcafef00d); rd(32'h40010030, v);
  check(v == 32'hcafef00d, "bridge read/write works with the CPU crashed");
  wr(32'h40010008, 32'h1);

  // ------------------------------------------------------------------ save and boot from flash
  $display("--- save to the flash sector (hl2fw save), boot from it");
  wr(32'h40010008, 32'h5);              // stay in ROM, in reset
  load_demo_via_bridge(ok);
  check(ok, "demo reloaded");
  mark = con.size();
  cpu_restart(32'h4);                       // into the ROM, stay there
  ctrl("A", 0);
  wait_console("stay in ROM", mark, 500, found);
  check(found, "stay-in-ROM override honoured");
  cargs[0] = 32'h800; cargs[1] = demo.size(); cargs[2] = 32'h800; cargs[3] = 32'h00010203; cargs[4] = demo_crc;
  ctrl("S", 5);
  n = 0;
  v = 0;
  while (v[31:24] != 8'h53 && n < 600) begin wait_us(5000); rd(32'h40010014, v); n++; end
  check(v[31:24] == 8'h53 && v[7:0] == 8'd0, $sformatf("save result %08x", v));
  check({`FLASH.mem[24'h1f0003], `FLASH.mem[24'h1f0002], `FLASH.mem[24'h1f0001], `FLASH.mem[24'h1f0000]} == 32'h46324c48,
        "flash sector starts with the HL2F header");
  check({`FLASH.mem[24'h1f0017], `FLASH.mem[24'h1f0016], `FLASH.mem[24'h1f0015], `FLASH.mem[24'h1f0014]} == 32'h00010203,
        "header version field");
  check(`FLASH.mem[24'h1f0020] == demo[0] && `FLASH.mem[24'h1f0020 + demo.size() - 1] == demo[demo.size() - 1],
        "image bytes in flash");
  check(`FLASH.mem[24'h1EFFFF] == 8'h5a && `FLASH.mem[24'h100000] == 8'ha5, "flash outside the sector untouched by the save");
  cargs[4] = 32'h12345678;
  ctrl("S", 5);
  n = 0;
  while (v[7:0] != 8'd2 && n < 100) begin wait_us(2000); rd(32'h40010014, v); n++; end
  check(v[31:24] == 8'h53 && v[7:0] == 8'd2, $sformatf("save with a wrong CRC refused (result %08x)", v));

  wr(32'h40010008, 32'h1);
  for (int i = 0; i < 4; i++) ebw[i] = 0;
  ebr[0] = 32'h800;
  eb(4, 32'h800, 1, ok);
  check(ok && eb_reply[0] == 0, "RAM cleared");
  mark = con.size();
  cpu_restart(32'h0);
  ctrl("A", 0);
  wait_console("boot 00010203", mark, 8000, found);
  check(found, "boot ROM loads the saved firmware (version 00010203)");
  wait_console("C  code 942", mark, 3000, found);
  check(found, "saved demo runs after reset");

  wr(32'h40010008, 32'h5);
  mark = con.size();
  cpu_restart(32'h4);
  ctrl("A", 0);
  wait_console("stay in ROM", mark, 500, found);
  wait_us(30000);
  check(found && con_find("boot 000", mark) < 0, "override keeps the ROM from starting the saved firmware");

  $display("--- firmware saved by the VexRiscv boot ROM (header format 1) is refused");
  hdr.delete();
  put_le32(32'h46324c48); put_le32(32'h1); put_le32(32'h800); put_le32(demo.size());
  put_le32(32'h800); put_le32(32'h00010005); put_le32(demo_crc);
  put_le32(crc32_hdr());
  for (int i = 0; i < 32; i++) `FLASH.mem[24'h1f0000 + i] = hdr[i];
  wr(32'h40010008, 32'h1);
  for (int i = 0; i < 4; i++) ebw[i] = 0;
  eb(4, 32'h800, 0, ok);
  mark = con.size();
  cpu_restart(32'h0);
  ctrl("A", 0);
  wait_console("0008", mark, 8000, found);
  wait_us(30000);
  check(found && con_find("result 42", mark) >= 0 && con_find("boot 000", mark) < 0,
        "header format 1: result code 8 (another CPU), not started");
  rd(32'h40010010, v);
  check(v == 32'h02000000, $sformatf("FW_STATUS = ROM idle (%08x)", v));

  end

  // ------------------------------------------------------------------ GDB stub
  $display("--- gdb remote protocol");
  gpos = gdb.size();
  pkt.delete(); pkt.push_back("+"); send_pkt();
  gdb_send(0, "qSupported:multiprocess+;swbreak+;hwbreak+");
  gdb_reply(400, ok);
  check(ok && body_is("PacketSize=180"), $sformatf("qSupported -> '%s'", body_str()));
  gdb_send(1, "?");
  gdb_reply(400, ok);
  check(ok && body_is("S02"), $sformatf("? -> '%s'", body_str()));
  gdb_send(1, "g");
  gdb_reply(400, ok);
  check(ok && rlen == 264, $sformatf("g -> %0d hex digits (33 registers)", rlen));
  v = body_le32(256);
  check(v >= 32'h10000 && v < 32'h11000, $sformatf("stopped pc %08x is in the boot ROM", v));
  gdb_send(1, "m10004,4");
  gdb_reply(400, ok);
  check(ok && body_is("48524f4d"), $sformatf("m 10004,4 -> '%s'", body_str()));
  gdb_send(1, "m40020000,4");
  gdb_reply(400, ok);
  check(ok && body_is("E14"), "m of the packet registers refused");

  // load the demo with X packets (binary, escaped), 200 bytes each
  for (off = 0; off < demo.size(); off += n2) begin
    n2 = (demo.size() - off > 200) ? 200 : demo.size() - off;
    pkt.delete();
    put_str($sformatf("X%0x,%0x:", 32'h800 + off, n2));
    for (int i = 0; i < n2; i++) begin
      bb = demo[off + i];
      if (bb == "#" || bb == "$" || bb == "}" || bb == "*") begin pkt.push_back("}"); pkt.push_back(bb ^ 8'h20); end
      else pkt.push_back(bb);
    end
    gdb_send_pkt_body();
    gdb_reply(400, ok);
    if (!ok || !body_is("OK")) begin $display("        X at %0x -> %s", off, body_str()); errors++; end
  end
  gdb_send(1, "m800,4");
  gdb_reply(400, ok);
  s = $sformatf("%02x%02x%02x%02x", demo[0], demo[1], demo[2], demo[3]);
  check(ok && body_is(s), $sformatf("X load verified by m (%s)", body_str()));
  gdb_send(1, "P20=00080000");
  gdb_reply(400, ok);
  check(ok && body_is("OK"), "P pc=0x800");

  // breakpoint at cpu_wfi: ebreak written with X as gdb does
  pkt.delete();
  put_str($sformatf("X%0x,4:", demo_wfi));
  pkt.push_back(8'h73); pkt.push_back(8'h00); pkt.push_back(8'h10); pkt.push_back(8'h00);
  gdb_send_pkt_body();
  gdb_reply(400, ok);
  check(ok && body_is("OK"), "breakpoint (ebreak) written");
  mark = gdb.size();
  gdb_send(1, "c");
  gdb_reply_skip_o(3000, ok);
  check(ok && body_is("S05"), $sformatf("continue -> stop reply '%s' (SIGTRAP)", body_str()));
  check(gdb_find("O", mark) >= 0, "demo banner reached gdb as an O packet");
  gdb_send(1, "g");
  gdb_reply(400, ok);
  v = body_le32(256);
  check(ok && v == demo_wfi, $sformatf("pc at the breakpoint %08x", v));

  pkt.delete();
  put_str($sformatf("X%0x,4:", demo_wfi));
  for (int i = 0; i < 4; i++) begin
    bb = demo[demo_wfi - 32'h800 + i];
    if (bb == "#" || bb == "$" || bb == "}" || bb == "*") begin pkt.push_back("}"); pkt.push_back(bb ^ 8'h20); end
    else pkt.push_back(bb);
  end
  gdb_send_pkt_body();
  gdb_reply(400, ok);
  check(ok && body_is("OK"), "breakpoint removed");

  // single step: the demo stopped at cpu_wfi with interrupts off (MIE clear)
  gdb_send(1, "s");
  gdb_reply_skip_o(3000, ok);
  check(ok && body_is("S05"), $sformatf("step -> '%s'", body_str()));
  gdb_send(1, "g");
  gdb_reply(400, ok);
  v = body_le32(256);
  check(ok && v == demo_wfi + 4, $sformatf("step over wfi (interrupts off): pc %08x", v));
  gdb_send(1, "s");
  gdb_reply_skip_o(3000, ok);
  gdb_send(1, "g");
  gdb_reply(400, ok);
  v = body_le32(256);
  check(ok && v >= 32'h800 && v < 32'h800 + demo.size() && (v < demo_wfi || v > demo_wfi + 4), $sformatf("step over ret: pc %08x back in main", v));
  rd(32'h40010038, v);
  check(v == 32'h0, "step interrupt released after the step");
  gdb_send(1, "g");
  gdb_reply(400, ok);
  n2 = body_le32(256);
  gdb_send(1, "s");
  gdb_reply_skip_o(3000, ok);
  gdb_send(1, "g");
  gdb_reply(400, ok);
  v = body_le32(256);
  check(ok && v != n2 && v >= 32'h800 && v < 32'h4000, $sformatf("step from %08x (not word-aligned: %0d) -> pc %08x", n2, n2[1], v));

  // continue to a 4-byte ebreak at cpu_wfi, then (that one removed, as gdb does when stopped) to a
  // c.ebreak (2 bytes, as gdb writes over a compressed instruction) at the return address in main:
  // cpu_wfi sleeps until the timer interrupt, so reaching it shows the step restored the interrupts
  gdb_send(1, "g");
  gdb_reply(400, ok);
  n2 = body_le32(256);
  pkt.delete();
  put_str($sformatf("X%0x,4:", demo_wfi));
  pkt.push_back(8'h73); pkt.push_back(8'h00); pkt.push_back(8'h10); pkt.push_back(8'h00);
  gdb_send_pkt_body();
  gdb_reply(400, ok);
  gdb_send(1, "c");
  gdb_reply_skip_o(3000, ok);
  check(ok && body_is("S05"), $sformatf("continue -> '%s'", body_str()));
  gdb_send(1, "g");
  gdb_reply(400, ok);
  v = body_le32(256);
  check(ok && v == demo_wfi, $sformatf("stopped at cpu_wfi again (%08x)", v));
  pkt.delete();
  put_str($sformatf("X%0x,4:", demo_wfi));
  for (int i = 0; i < 4; i++) begin
    bb = demo[demo_wfi - 32'h800 + i];
    if (bb == "#" || bb == "$" || bb == "}" || bb == "*") begin pkt.push_back("}"); pkt.push_back(bb ^ 8'h20); end
    else pkt.push_back(bb);
  end
  gdb_send_pkt_body();
  gdb_reply(400, ok);
  pkt.delete();
  put_str($sformatf("X%0x,2:", n2));
  pkt.push_back(8'h02); pkt.push_back(8'h90);
  gdb_send_pkt_body();
  gdb_reply(400, ok);
  gdb_send(1, "c");
  gdb_reply_skip_o(3000, ok);
  gdb_send(1, "g");
  gdb_reply(400, ok);
  v = body_le32(256);
  check(ok && v == n2, $sformatf("timer wakes cpu_wfi, c.ebreak breakpoint hit at %08x (%08x)", n2, v));
  pkt.delete();
  put_str($sformatf("X%0x,2:", n2));
  for (int i = 0; i < 2; i++) begin
    bb = demo[n2 - 32'h800 + i];
    if (bb == "#" || bb == "$" || bb == "}" || bb == "*") begin pkt.push_back("}"); pkt.push_back(bb ^ 8'h20); end
    else pkt.push_back(bb);
  end
  gdb_send_pkt_body();
  gdb_reply(400, ok);
  check(ok && body_is("OK"), "breakpoints removed");

  // step over the tail call from out() into the boot ROM's con_write: the stub steps through the ROM
  jr_addr = demo_out;
  while (jr_addr < demo_out + 64 && !(demo[jr_addr - 32'h800] == 8'h82 && demo[jr_addr - 32'h800 + 1] == 8'h87)) jr_addr += 2;
  pkt.delete();
  put_str($sformatf("X%0x,2:", jr_addr));
  pkt.push_back(8'h02); pkt.push_back(8'h90);
  gdb_send_pkt_body();
  gdb_reply(400, ok);
  gdb_send(1, "c");
  gdb_reply_skip_o(3000, ok);
  gdb_send(1, "g");
  gdb_reply(400, ok);
  v = body_le32(256);
  check(ok && v == jr_addr, $sformatf("stopped at the jump into the ROM in out() (%08x, %08x)", jr_addr, v));
  pkt.delete();
  put_str($sformatf("X%0x,2:", jr_addr));
  for (int i = 0; i < 2; i++) pkt.push_back(demo[jr_addr - 32'h800 + i]);
  gdb_send_pkt_body();
  gdb_reply(400, ok);
  mark = gdb.size();
  gdb_send(1, "s");
  gdb_reply_skip_o(8000, ok);
  check(ok && body_is("S05"), $sformatf("step over the ROM call -> '%s'", body_str()));
  gdb_send(1, "g");
  gdb_reply(400, ok);
  v = body_le32(256);
  check(ok && v >= 32'h800 && v < 32'h4000, $sformatf("step over the ROM call ends back in the application (pc %08x)", v));
  mark = gdb.size();
  gdb_send(1, "c");
  wait_us(30000);
  check(gdb_find("O", mark) >= 0, "console output reaches gdb as O packets while running");
  gpos = gdb.size();
  pkt.delete(); pkt.push_back(8'h03); send_pkt();
  gdb_reply_skip_o(3000, ok);
  check(ok && body_is("S02"), $sformatf("Ctrl-C -> '%s'", body_str()));
  gdb_send(1, "qRcmd,68656c70");        // "help"
  gdb_reply_skip_o(400, ok);
  check(ok && body_is("OK"), "monitor command answered");
  gdb_send(1, "D");
  gdb_reply(400, ok);
  check(ok && body_is("OK"), "detach");
  mark = con.size();
  ctrl("A", 0);
  wait_console("C  code", mark, 3000, found);
  check(found, "target runs after detach, console back on hl2fw");

  // ------------------------------------------------------------------ network flashing locks the CPU out
  $display("--- network erase request");
  net_erase = 1'b1;
  wait (asmi_i.state == 5'd1 || asmi_i.state == 5'd2);
  net_erase = 1'b0;
  wait (asmi_i.state == 5'd4);
  wr(32'h40030000, 32'h1f0000); wr(32'h40030008, 4); wait_us(3000); rd(32'h40030008, v);
  check(v[2] == 1'b1, $sformatf("CPU flash command refused after a network erase (status %0x)", v));
  if (!$test$plusargs("gdb_only"))
    check(`FLASH.mem[24'h1f0000] == 8'h48, "saved firmware not erased by the network erase");

  $display("tb_neo: bridge requests %0d, drops %0d, bus errors %0d; CPU datagrams sent %0d, receive ring drops %0d",
           eb_stats[95:64], eb_stats[63:32], eb_stats[31:0], cpu_counts[31:16], cpu_counts[15:0]);
  $display("tb_neo: %s (%0d errors)", errors == 0 ? "PASS" : "FAIL", errors);
  $finish;
end

initial begin
  #(64'd5_000_000_000_000);
  $display("tb_neo: FAIL timeout");
  $finish;
end

endmodule
