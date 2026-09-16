// SPDX-License-Identifier: GPL-2.0-or-later
// Copyright 2026 Franz Schöning, https://www.schoning.com
//
// Message layer firmware (firmware/hl2neo/msg) on the NEORV32 CPU system of the raw front-end image, with the
// front-end register block and interlock (rtl/hl2io.v) and the command-bus merge.
//
// DUT (wired as in rtl/hermeslite_core.v, RAWFRONT = 1): ebbridge (CPU_IO), hl2bus_regs, wb_cdc, pbuf_ram, hl2cpu
// (CORE = 2, IO = 1, boot ROM from ../cpu/bootrom_neo.hex), hl2io with tx_interlock, cmd_merge. The PC side
// drives the bridge's UDP receive interface and captures what the bridge sends. The control side of the
// I2C engine is modelled: an I2C command on the command bus completes after a short delay with a NACK or
// ACK chosen per address, and data for reads.
//
// Checks: firmware loaded into RAM and started; HELLO in a new session (versions, register block ID);
// register read; command-bus injection executed exactly once although the request is repeated; a request
// with a sequence gap is not executed and answered with a bare ACK; the next in-order request executes;
// unreliable transmit permission renews the interlock lease; refused register write; I2C transfer with
// data and NACK status; I2C scan bitmap; telemetry at the set period; a reliable event on an input change,
// retransmitted until acknowledged; the firmware keeps the CPU watchdog armed; a console attach datagram
// goes to the boot ROM (banner replayed) and messages still work afterwards.
`timescale 1 ps / 1 ps

module tb_msg;

localparam real T_ETH  = 80_000.0;
localparam real T_RX   = 80_100.0;
localparam real T_CPU  = 80_000.0;
localparam real T_CTRL = 400_000.0;
localparam      MS_DIV = 125;           // simulated millisecond = 125 CPU cycles (10 us)

logic clk = 0, clk_rx = 0, clk_cpu = 0, clk_ctrl = 0;
always #(T_ETH/2)  clk      = ~clk;
always #(T_RX/2)   clk_rx   = ~clk_rx;
always #(T_CPU/2)  clk_cpu  = ~clk_cpu;
always #(T_CTRL/2) clk_ctrl = ~clk_ctrl;

logic rst_async = 1'b1;
initial #(1_000_000) rst_async = 1'b0;

initial begin
  for (int i = 0; i < 32; i++) cpu_sys.NEO.cpu_i.neorv32_top_inst.core_complex_gen_n1_neorv32_cpu_inst.neorv32_cpu_regfile_inst.regfile[i] = 32'd0;
  for (int i = 0; i < 4096; i++) cpu_sys.ram[i] = 32'd0;
end

integer errors = 0;
task automatic check(input bit ok, input string what);
  if (ok) $display("[%0.1f ms] ok    %s", $realtime / 1.0e10, what);
  else begin $display("[%0.1f ms] FAIL  %s", $realtime / 1.0e10, what); errors = errors + 1; end
  $fflush();
endtask

//////////////////////////////////////////////////////////////////////////////
// DUT

logic [15:0] eth_port = 16'd1027;
logic        eth_broadcast = 1'b0, eth_valid = 1'b0;
logic [ 7:0] eth_data = 8'h00;
logic        dest_valid = 1'b0;

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
logic        inhibit = 1'b0;
assign ctrl_status = {2'b00, inhibit, 2'b00, temp_code, 12'd11, 12'd22, 12'd33};

hl2bus_regs #(.VERSION_MAJOR(8'd74), .VERSION_MINOR(8'd2), .DIAG_ID(8'hD1), .CAPS(16'h003C)) regs_i (
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

logic        io_wstb, io_from_br, io_hit, io_wr_ok, ms_tick, cpu_sys_rst;
logic [ 5:0] io_adr;
logic [31:0] io_dw, io_rdata;

hl2cpu #(.CORE(2), .ROM_WORDS(1024), .RAM_WORDS(4096), .ROM_HEX("../cpu/bootrom_neo.hex"), .VERSION_MAJOR(8'd74),
         .VERSION_MINOR(8'd2), .DIAG_ID(8'hD1), .CAPS(16'h003C), .MS_DIV(MS_DIV), .IO(1)) cpu_sys (
  .clk(clk_cpu), .rst_async(rst_async),
  .br_req(br_req), .br_adr(br_adr), .br_dat_w(br_dat_w), .br_sel(br_sel), .br_we(br_we),
  .br_done(br_done), .br_dat_r(br_dat_r), .br_err(br_err),
  .clk_ctrl(clk_ctrl), .ctrl_status(ctrl_status), .clk_eth(clk), .tx_status(8'h01),
  .pb_adr(pb_adr_a), .pb_we(pb_we_a), .pb_wd(pb_wd_a), .pb_q(pb_q_a),
  .eth_rx_wr(cpu_rx_wr), .rx_rd(cpu_rx_rd), .tx_req(cpu_tx_req), .tx_len(cpu_tx_len),
  .eth_tx_done(cpu_tx_done), .eth_dest(dest_valid), .eth_counts(cpu_counts),
  .fl_req(), .fl_cmd(), .fl_addr(), .fl_data(), .fl_done(1'b0),
  .fl_status(3'd0), .fl_rdata(8'd0), .led_en(), .led_on(), .cpu_running(),
  .io_wstb(io_wstb), .io_adr(io_adr), .io_dw(io_dw), .io_from_br(io_from_br), .io_rdata(io_rdata),
  .io_hit(io_hit), .io_wr_ok(io_wr_ok), .ms_tick(ms_tick), .sys_rst_o(cpu_sys_rst));

// control side: millisecond pulse (25 control cycles = 10 us), slow ADC ticks, I2C engine model
integer msc = 0;
logic   msec = 1'b0, adc_tick = 1'b0;
always @(posedge clk_ctrl) begin msc <= (msc == 24) ? 0 : msc + 1; msec <= (msc == 24); adc_tick <= msec; end

logic [ 7:0] i2c_done = 8'd0, i2c_ref = 8'd0;
logic        i2c_nack = 1'b0;
logic [31:0] i2c_rdata = 32'd0;
wire  [55:0] i2c_status = {i2c_rdata, i2c_ref, i2c_done, 5'd0, 1'b0, i2c_nack, 1'b0};

logic        inj_req, inj_ack;
logic [ 5:0] inj_addr;
logic [31:0] inj_data;
wire  [31:0] ilk_status;

hl2io io_i (
  .clk(clk_cpu), .sys_rst(cpu_sys_rst), .ms_tick(ms_tick),
  .adr(io_adr), .dw(io_dw), .wstb(io_wstb), .from_br(io_from_br), .rdata(io_rdata), .hit(io_hit), .wr_ok(io_wr_ok),
  .clk_ctrl(clk_ctrl), .msec_ctrl(msec), .temperature(12'h3ed), .adc_tick(adc_tick), .fan_overheat(1'b0),
  .db_inputs({inhibit, 2'b00}), .pa_cfg(3'b001), .i2c_status(i2c_status), .adc_seq(16'd7), .fan_state(4'd0),
  .bias_unlock_c(), .led_c(), .fan_min_c(), .pwr_envpa(), .pwr_envop(), .pwr_envbias(), .pa_inttr(), .pa_exttr(),
  .rffe_rfsw_sel(), .dac_en(), .tx_on(), .ilk_status(ilk_status), .pins(13'h0003),
  .inj_req(inj_req), .inj_addr(inj_addr), .inj_data(inj_data), .inj_ack(inj_ack));

logic [ 5:0] c_addr;
logic [31:0] c_data;
logic        c_cnt, c_cnt_d = 1'b0;
cmd_merge #(.QUIET(64), .GUARD(32)) merge_i (
  .clk(clk_rx), .ds_addr(6'd0), .ds_data(32'd0), .ds_cnt(1'b0), .ds_is_alt(1'b0), .ds_resprqst(1'b0),
  .inj_req(1'b0), .inj_addr(6'd0), .inj_data(32'd0), .inj_ack(),
  .inj2_req(inj_req), .inj2_addr(inj_addr), .inj2_data(inj_data), .inj2_ack(inj_ack),
  .addr(c_addr), .data(c_data), .cnt(c_cnt), .is_alt(), .resprqst());

integer      n_cmd0a = 0;
logic [31:0] last_0a = 32'd0;
logic [ 5:0] i2c_a;
logic [31:0] i2c_d;
integer      i2c_wait = 0;                      // control cycles until the modelled transfer completes
always @(posedge clk_rx) begin
  c_cnt_d <= c_cnt;
  if (c_cnt != c_cnt_d) begin
    if (c_addr == 6'h0a) begin n_cmd0a <= n_cmd0a + 1; last_0a <= c_data; end
    if (c_addr == 6'h3c || c_addr == 6'h3d) begin i2c_a <= c_addr; i2c_d <= c_data; i2c_wait <= 50; end
  end
end
// an I2C transfer completes 2 ms later; only 0x20 (bus 2) and 0x6A (bus 1) answer
always @(posedge clk_ctrl) begin
  if (i2c_wait == 1) begin
    i2c_nack  <= !((i2c_a == 6'h3d && i2c_d[22:16] == 7'h20) || (i2c_a == 6'h3c && i2c_d[22:16] == 7'h6a));
    i2c_rdata <= (i2c_d[24] && i2c_d[22:16] == 7'h20) ? 32'h44332211 : 32'hffffffff;
    i2c_done  <= i2c_done + 8'd1;
  end
  if (i2c_wait > 0) i2c_wait <= i2c_wait - 1;
end

//////////////////////////////////////////////////////////////////////////////
// Send slot and capture (as tb_neo)

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

logic         tx_en_d = 1'b0;
integer       cap_left = 0;
logic [7:0]   capbuf [0:2047];
integer       caplen = 0;
byte unsigned con[$];
logic [31:0]  eb_reply [0:63];
integer       eb_reply_n = 0;
integer       n_eb_replies = 0;
integer       k;

// HM packets from the radio: responses and bare ACKs (hm_*), events (ev_*): bytes queued, lengths queued
byte unsigned hm_bytes[$];
integer       hm_lens[$];
byte unsigned ev_bytes[$];
integer       ev_lens[$];
integer       n_tele = 0, n_hm = 0;

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
      end else if (caplen >= 16 && capbuf[0] == "H" && capbuf[1] == "M") begin
        if (caplen >= 22 && capbuf[16] == 8'd5) n_tele = n_tele + 1;
        else if (caplen >= 22 && capbuf[16] == 8'd6) begin
          for (k = 0; k < caplen; k = k + 1) ev_bytes.push_back(capbuf[k]);
          ev_lens.push_back(caplen);
        end else begin
          for (k = 0; k < caplen; k = k + 1) hm_bytes.push_back(capbuf[k]);
          hm_lens.push_back(caplen);
          n_hm = n_hm + 1;
        end
      end
    end
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
    for (ti = 0; ti < tn; ti = ti + 1) begin
      eth_valid <= 1'b1;
      eth_data  <= txq.pop_front();
      @(posedge clk_rx);
    end
    eth_valid <= 1'b0;
    repeat (66) @(posedge clk_rx);
  end
end

byte unsigned pkt[$];
task automatic send_pkt();
  txq_len.push_back(pkt.size());
  for (int i = 0; i < pkt.size(); i++) txq.push_back(pkt[i]);
  pkt.delete();
  while (txq_len.size() != 0) @(posedge clk_rx);
  @(posedge clk_rx);
  wait (!eth_valid);
  repeat (10) @(posedge clk_rx);
endtask

task automatic wait_ms(input integer ms);     // simulated milliseconds (10 us)
  #(64'd10_000_000 * ms);
endtask

// Etherbone
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
    if (nr == 0) begin wait_ms(30); ok = 1; end
    else begin
      t = 0;
      while (n_eb_replies == nbefore && t < 300) begin #(64'd100_000_000); t++; end
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
  eb(1, a, 1, ok);
endtask

// HM request: header + one message
function automatic void hm_begin(input byte unsigned flags, input int seq, input int ack);
  pkt.delete();
  pkt.push_back(8'h48); pkt.push_back(8'h4d); pkt.push_back(8'd1); pkt.push_back(flags);
  repeat (4) pkt.push_back(8'd0);
  pkt.push_back(seq[7:0]); pkt.push_back(seq[15:8]);
  pkt.push_back(ack[7:0]); pkt.push_back(ack[15:8]);
  pkt.push_back(8'd0); pkt.push_back(8'd0);           // length, set by hm_msg
  pkt.push_back(8'd0); pkt.push_back(8'd0);
endfunction

// message body under construction
byte unsigned body[$];
function automatic void b8(input [7:0] v); body.push_back(v); endfunction
function automatic void b32(input [31:0] v); for (int i = 0; i < 4; i++) body.push_back(v[8*i +: 8]); endfunction

function automatic void hm_msg(input byte unsigned cls, input byte unsigned op, input int tag);
  int len;
  logic [7:0] bl;
  bl = body.size();
  pkt.push_back(cls); pkt.push_back(op); pkt.push_back(tag[7:0]); pkt.push_back(tag[15:8]);
  pkt.push_back(bl); pkt.push_back(8'd0);
  for (int i = 0; i < body.size(); i++) pkt.push_back(body[i]);
  len = pkt.size() - 16;
  pkt[12] = len[7:0]; pkt[13] = len[15:8];
  body.delete();
endfunction

// received packet being checked
logic [7:0] rsp [0:299];
integer     rsp_len = 0;
function automatic int le16(input int at); return rsp[at] | (rsp[at+1] << 8); endfunction
function automatic [31:0] le32(input int at); return {rsp[at+3], rsp[at+2], rsp[at+1], rsp[at]}; endfunction

task automatic hm_wait(input integer ms, output bit got);   // next response / ACK packet
  integer t;
  got = 0;
  t = 0;
  while (hm_lens.size() == 0 && t < ms) begin wait_ms(1); t++; end
  if (hm_lens.size() > 0) begin
    rsp_len = hm_lens.pop_front();
    for (int i = 0; i < rsp_len; i++) rsp[i] = hm_bytes.pop_front();
    got = 1;
  end
endtask

task automatic ev_next(output bit got);                      // next event packet, if any
  got = 0;
  if (ev_lens.size() > 0) begin
    rsp_len = ev_lens.pop_front();
    for (int i = 0; i < rsp_len; i++) rsp[i] = ev_bytes.pop_front();
    got = 1;
  end
endtask

task automatic ev_clear();
  ev_bytes.delete();
  ev_lens.delete();
endtask

//////////////////////////////////////////////////////////////////////////////
// Test

byte unsigned img[$];
integer fd, c;

initial begin
  logic [31:0] v, st;
  bit got, same;
  byte unsigned r1[$];
  logic [7:0] r2 [0:299];
  integer r2_len;
  integer seq, t, n0, ev_seq, ev_sends;

  wait (!rst_async);
  #(64'd200_000_000);

  // ------------------------------------------------------------------ load and start the firmware
  wr(32'h40010008, 32'h1);                              // CPU held in reset
  fd = $fopen("msg_ram.hex", "r");
  if (fd == 0) begin $display("tb_msg: msg_ram.hex not found (run firmware/hl2neo/build.py)"); $finish; end
  $fclose(fd);
  $readmemh("msg_ram.hex", cpu_sys.ram, 12'h200);
  wr(32'h40010010, 32'h0);
  wr(32'h40010008, 32'h8);                              // boot RAM: the ROM jumps to 0x800
  st = 0; t = 0;
  while (st[31:24] != 8'd3 && t < 100) begin wait_ms(5); rd(32'h40010010, st); t++; end
  check(st[31:24] == 8'd3, $sformatf("firmware running (state %08x)", st));
  wait_ms(20);

  // ------------------------------------------------------------------ HELLO, new session
  seq = 16'h1234;
  hm_begin(8'h05, seq, 0);                              // RELIABLE | RESET
  hm_msg(0, 1, 16'h0101);
  send_pkt();
  hm_wait(100, got);
  check(got && rsp[3] == 8'h02 && le16(10) == seq, "HELLO: response with ACK of the request sequence");
  if (!got) begin
    logic [31:0] d1, d2, d3, d4;
    rd(32'h40010010, d1); rd(32'h40020000, d2); rd(32'h40020004, d3); rd(32'h4002000C, d4);
    $display("        no response: firmware state %08x, ring wr %08x rd %08x, counts %08x", d1, d2, d3, d4);
  end
  check(got && rsp[16] == 0 && rsp[17] == 8'h81 && le16(18) == 16'h0101 && rsp[22] == 0, "HELLO: SYS op 0x81, tag echoed, status ok");
  check(got && le32(26) == 32'h4a02d101 && le32(30) == 32'h00030001 && le32(42) == 32'h494f3031,
        $sformatf("HELLO: gateware %08x, firmware %08x, register block %08x", le32(26), le32(30), le32(42)));

  // the first event (state at session start) is acknowledged by the next request's ACK field
  t = 0;
  while (ev_lens.size() == 0 && t < 100) begin wait_ms(1); t++; end
  ev_next(got);
  check(got, "EVENT with the state at session start");
  ev_seq = le16(8);

  // ------------------------------------------------------------------ register read
  seq++;
  hm_begin(8'h03, seq, ev_seq);                         // RELIABLE | ACK_VALID (acknowledges the event)
  b32(32'h40040000); b8(2);
  hm_msg(1, 1, 7);
  send_pkt();
  hm_wait(100, got);
  check(got && rsp[22] == 0 && le32(23) == 32'h494f3031 && le16(20) == 9, "REG READ of the register block ID (2 words)");

  // ------------------------------------------------------------------ command injection exactly once
  seq++;
  n0 = n_cmd0a;
  hm_begin(8'h01, seq, 0);
  b8(8'h0a); b32(32'h00000054);
  hm_msg(3, 4, 9);
  r1 = pkt;
  send_pkt();
  hm_wait(100, got);
  for (int i = 0; i < rsp_len; i++) r2[i] = rsp[i];
  r2_len = rsp_len;
  wait_ms(30);
  check(got && rsp[22] == 0 && n_cmd0a == n0 + 1 && last_0a == 32'h54, "CMD 0x0A through the firmware: on the command bus once");
  pkt = r1;                                             // the same request again (response lost)
  send_pkt();
  hm_wait(100, got);
  wait_ms(30);
  same = got && (rsp_len == r2_len);
  for (int i = 0; i < rsp_len && same; i++) if (rsp[i] != r2[i]) same = 0;
  check(same, "repeated request: the cached response again");
  check(n_cmd0a == n0 + 1, "repeated request: not executed again");

  // ------------------------------------------------------------------ sequence gap
  hm_begin(8'h01, seq + 2, 0);
  b8(8'h0a); b32(32'h00000054);
  hm_msg(3, 4, 10);
  send_pkt();
  hm_wait(100, got);
  wait_ms(30);
  check(got && le16(12) == 0 && le16(10) == seq, "request with a sequence gap: bare ACK of the last executed sequence");
  check(n_cmd0a == n0 + 1, "request with a sequence gap: not executed");
  seq++;
  hm_begin(8'h01, seq, 0);
  b8(8'h0a); b32(32'h00000054);
  hm_msg(3, 4, 11);
  send_pkt();
  hm_wait(100, got);
  wait_ms(30);
  check(got && rsp[22] == 0 && n_cmd0a == n0 + 2, "next in-order request executes");

  // ------------------------------------------------------------------ unreliable transmit permission
  hm_begin(8'h00, 0, 0);
  b8(0);
  hm_msg(3, 1, 12);
  send_pkt();
  hm_wait(100, got);
  check(got && rsp[3] == 8'h02 && rsp[17] == 8'h81 && rsp[22] == 0, "TX_PERMIT (unreliable, no key): answered");
  wait_ms(5);
  rd(32'h40040008, v);
  check(v[2] == 1'b1 && v[0] == 1'b0, $sformatf("lease valid, transmit off (interlock %08x)", v));

  // ------------------------------------------------------------------ refused write
  seq++;
  hm_begin(8'h01, seq, 0);
  b32(32'h00000800); b32(32'h0);
  hm_msg(1, 2, 13);
  send_pkt();
  hm_wait(100, got);
  check(got && rsp[22] == 8'h12, "REG WRITE into the firmware's own RAM: refused");

  // ------------------------------------------------------------------ I2C transfer and scan
  seq++;
  hm_begin(8'h01, seq, 0);
  b8(2); b8(8'h20); b8(1); b8(8'h09); b8(0);
  hm_msg(2, 1, 14);
  send_pkt();
  hm_wait(500, got);
  check(got && rsp[22] == 0 && rsp[23] == 0 && le32(24) == 32'h44332211, "I2C XFER read bus 2 0x20: ok with data");
  seq++;
  hm_begin(8'h01, seq, 0);
  b8(2); b8(8'h1d); b8(0); b8(8'h00); b8(1);
  hm_msg(2, 1, 15);
  send_pkt();
  hm_wait(500, got);
  check(got && rsp[22] == 0 && rsp[23] == 1, "I2C XFER write to absent 0x1D: NACK status");
  seq++;
  hm_begin(8'h01, seq, 0);
  b8(1); b8(8'h68); b8(8'h6b);
  hm_msg(2, 2, 16);
  send_pkt();
  hm_wait(1000, got);
  check(got && rsp[22] == 0 && le16(20) == 17 && rsp[23 + 13] == 8'h04 && rsp[23 + 12] == 0,
        $sformatf("I2C SCAN bus 1 0x68-0x6B: only 0x6A acknowledges (bitmap byte 13 = %02x)", rsp[36]));

  // ------------------------------------------------------------------ telemetry
  n0 = n_tele;
  wait_ms(500);
  check(n_tele - n0 >= 4 && n_tele - n0 <= 6, $sformatf("telemetry every 100 ms (%0d in 500 ms)", n_tele - n0));

  // ------------------------------------------------------------------ event on an input change, retransmitted until acknowledged
  ev_clear();
  inhibit = 1'b1;
  t = 0;
  while (ev_lens.size() == 0 && t < 200) begin wait_ms(1); t++; end
  ev_next(got);
  check(got && rsp[3] == 8'h03 && rsp[17] == 1, "TX-inhibit input change: reliable EVENT");
  ev_seq = le16(8);
  check(got && (le32(26) & (1 << 18)) != 0, "EVENT carries the debounced inputs (inhibit set)");
  wait_ms(200);
  ev_sends = 1;
  ev_next(got);
  while (got) begin if (le16(8) == ev_seq) ev_sends++; ev_next(got); end
  check(ev_sends >= 3, $sformatf("unacknowledged EVENT retransmitted (%0d sends in 200 ms)", ev_sends));
  hm_begin(8'h02, 0, ev_seq);                           // bare ACK
  send_pkt();
  wait_ms(50);
  ev_clear();
  wait_ms(400);
  check(ev_lens.size() == 0, "EVENT acknowledged: no more retransmissions");

  // ------------------------------------------------------------------ watchdog kept armed
  rd(32'h40040020, v);
  check(v[30] && !v[31], $sformatf("CPU watchdog armed and kicked (%08x)", v));

  // ------------------------------------------------------------------ console datagram goes to the boot ROM
  pkt.delete(); pkt.push_back(8'h01); pkt.push_back(8'h41);
  send_pkt();
  t = 0;
  while (con.size() < 20 && t < 300) begin wait_ms(1); t++; end
  check(con.size() >= 20, $sformatf("console attach handled by the boot ROM (%0d console bytes)", con.size()));
  // a message that arrives while the boot ROM still owns the ring is read by the ROM and lost: the far
  // side sends a reliable request again after its timeout, as a client does
  seq++;
  got = 0;
  for (int attempt = 0; attempt < 3 && !got; attempt++) begin
    hm_begin(8'h01, seq, 0);
    hm_msg(0, 2, 17);
    send_pkt();
    hm_wait(100, got);
  end
  check(got && rsp[17] == 8'h82 && rsp[22] == 0, "messages work again after the boot ROM read the console datagram");

  $display("");
  if (errors == 0) $display("tb_msg PASS");
  else $display("tb_msg FAIL: %0d errors", errors);
  $finish;
end

endmodule
