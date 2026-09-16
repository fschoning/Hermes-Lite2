// SPDX-License-Identifier: GPL-2.0-or-later
// Copyright 2026 Franz Schöning, https://www.schoning.com
//
// Transmit interlock and front-end I/O register block (rtl/hl2io.v: hl2io, tx_interlock) with the
// command-bus merge (rtl/hl2bus.v cmd_merge) as in hermeslite_core.v (RAWFRONT = 1).
//
// The register bus is driven as hl2cpu.v drives it (CPU or bridge access, one cycle, combinational
// answer). Simulated time is scaled: one "millisecond" is 8 control-clock cycles (3.2 us) on both the
// control clock (msec pulse) and the CPU clock (ms_tick every 80 cycles).
//
// Checks: power-up state (everything off); permission key; lease renewal keys the outputs in order
// (relays, then PA/bias/DAC after 10 ms) and PA/DAC go off first on key-up with the relays 10 ms later;
// every trip path latches its reason with the outputs off: lease expiry while keyed, over-temperature
// (ADC code and the fan logic state), lowered temperature limit, stale temperature reading, TX-inhibit
// input, CPU watchdog expiry, maximum key-down time; clear only removes reasons whose cut-off is gone;
// normal key-up (key bit 0, then the lease runs out) is no trip; PTT and key inputs key only when
// enabled; register clamps (lease, max key-down, temperature limit only lowered, watchdog timeout);
// watchdog disarm is bridge-only; command injector and I2C transfer register reach the command bus
// with the right address and data, busy refusal, bus 0 refused; bias unlock key; LED and fan registers
// reach the control clock.
`timescale 1 ps / 1 ps

module tb_ilk;

localparam real T_CPU  = 40_000.0;      // 25 MHz
localparam real T_CTRL = 400_000.0;     // 2.5 MHz
localparam real T_RX   = 8_010.0;       // Ethernet receive clock
localparam      MS_CTRL = 8;            // control cycles per simulated ms
localparam      MS_CPU  = 80;           // CPU cycles per simulated ms

logic clk = 0, clk_ctrl = 0, clk_rx = 0;
always #(T_CPU/2)  clk      = ~clk;
always #(T_CTRL/2) clk_ctrl = ~clk_ctrl;
always #(T_RX/2)   clk_rx   = ~clk_rx;

integer errors = 0;
task automatic check(input bit ok, input string what);
  if (ok) $display("[%0.1f ms] ok    %s", sim_ms(), what);
  else begin $display("[%0.1f ms] FAIL  %s", sim_ms(), what); errors = errors + 1; end
endtask

function real sim_ms();
  return $realtime / (T_CTRL * MS_CTRL);
endfunction

// simulated millisecond pulses
integer mc = 0, mcc = 0;
logic msec = 1'b0, ms_tick = 1'b0;
always @(posedge clk_ctrl) begin mc <= (mc == MS_CTRL-1) ? 0 : mc + 1; msec <= (mc == MS_CTRL-1); end
always @(posedge clk)      begin mcc <= (mcc == MS_CPU-1) ? 0 : mcc + 1; ms_tick <= (mcc == MS_CPU-1); end

//////////////////////////////////////////////////////////////////////////////
// DUT

logic [ 5:0] adr = 6'd0;
logic [31:0] dw = 32'd0;
logic        wstb = 1'b0, from_br = 1'b1;
logic [31:0] rdata;
logic        hit, wr_ok;

logic [11:0] temperature = 12'h3ed;     // 30 C
logic        adc_tick = 1'b0;
logic        fan_overheat = 1'b0;
logic        inhibit = 1'b0, ptt_in = 1'b0, key_in = 1'b0;
logic [ 2:0] pa_cfg = 3'b000;           // command 0x09 at power-up: PA disabled
logic [55:0] i2c_status = {32'hA1B2C3D4, 8'd7, 8'd9, 4'd0, 4'b0010};
logic        bias_unlock_c;
logic [ 7:0] led_c;
logic [ 3:0] fan_min_c;
logic        envpa, envop, envbias, inttr, exttr, rfsw, dac_en, tx_on;
logic [31:0] ilk_status;
logic        inj_req, inj_ack;
logic [ 5:0] inj_addr;
logic [31:0] inj_data;

hl2io dut (
  .clk(clk), .sys_rst(1'b0), .ms_tick(ms_tick),
  .adr(adr), .dw(dw), .wstb(wstb), .from_br(from_br), .rdata(rdata), .hit(hit), .wr_ok(wr_ok),
  .clk_ctrl(clk_ctrl), .msec_ctrl(msec), .temperature(temperature), .adc_tick(adc_tick),
  .fan_overheat(fan_overheat), .db_inputs({inhibit, ptt_in, key_in}), .pa_cfg(pa_cfg),
  .i2c_status(i2c_status), .adc_seq(16'd1234), .fan_state(4'b0011),
  .bias_unlock_c(bias_unlock_c), .led_c(led_c), .fan_min_c(fan_min_c),
  .pwr_envpa(envpa), .pwr_envop(envop), .pwr_envbias(envbias), .pa_inttr(inttr), .pa_exttr(exttr),
  .rffe_rfsw_sel(rfsw), .dac_en(dac_en), .tx_on(tx_on), .ilk_status(ilk_status),
  .pins(13'h1a5a), .inj_req(inj_req), .inj_addr(inj_addr), .inj_data(inj_data), .inj_ack(inj_ack));

// command bus as in hermeslite_core.v: PC commands from dsopenhpsdr1 (none here) merged with the injector
logic [ 5:0] c_addr;
logic [31:0] c_data;
logic        c_cnt, c_cnt_d = 1'b0;
cmd_merge #(.QUIET(64), .GUARD(32)) merge_i (
  .clk(clk_rx), .ds_addr(6'd0), .ds_data(32'd0), .ds_cnt(1'b0), .ds_is_alt(1'b0), .ds_resprqst(1'b0),
  .inj_req(1'b0), .inj_addr(6'd0), .inj_data(32'd0), .inj_ack(),
  .inj2_req(inj_req), .inj2_addr(inj_addr), .inj2_data(inj_data), .inj2_ack(inj_ack),
  .addr(c_addr), .data(c_data), .cnt(c_cnt), .is_alt(), .resprqst());

logic [5:0]  last_cmd_addr;
logic [31:0] last_cmd_data;
integer      n_cmds = 0;
always @(posedge clk_rx) begin
  c_cnt_d <= c_cnt;
  if (c_cnt != c_cnt_d) begin
    last_cmd_addr <= c_addr;
    last_cmd_data <= c_data;
    n_cmds <= n_cmds + 1;
  end
end

// slow ADC ticks every 64 ms while adc_run
logic adc_run = 1'b1;
initial forever begin
  repeat (64 * MS_CTRL) @(posedge clk_ctrl);
  if (adc_run) begin adc_tick <= 1'b1; @(posedge clk_ctrl); adc_tick <= 1'b0; end
end

//////////////////////////////////////////////////////////////////////////////
// Bus access and helpers

// two threads use the bus (the test and the renewal loop): they try at different times after the
// clock edge, so the lock is never taken by both in the same step
bit lock = 1'b0;
task automatic acquire(input integer who);
  bit got;
  got = 1'b0;
  while (!got) begin
    @(posedge clk);
    #(100 + who * 1000);
    if (!lock) begin lock = 1'b1; got = 1'b1; end
  end
endtask

task automatic wr(input [7:0] off, input [31:0] v, input bit br, output bit ok, input integer who = 0);
  acquire(who);
  @(negedge clk);
  adr = off[7:2]; dw = v; from_br = br; wstb = 1'b1;
  #1;
  ok = hit & wr_ok;
  @(negedge clk);
  wstb = 1'b0;
  lock = 1'b0;
endtask

task automatic w(input [7:0] off, input [31:0] v);
  bit ok;
  wr(off, v, 1'b1, ok);
  if (!ok) begin $display("[%0.1f ms] FAIL  write 0x%02x refused", sim_ms(), off); errors = errors + 1; end
endtask

task automatic rd(input [7:0] off, output [31:0] v);
  acquire(0);
  @(negedge clk);
  adr = off[7:2]; wstb = 1'b0;
  #1;
  v = rdata;
  lock = 1'b0;
endtask

task automatic ms(input integer n);
  repeat (n * MS_CTRL) @(posedge clk_ctrl);
endtask

localparam [7:0] R_ID = 8'h00, R_PERMIT = 8'h04, R_STATUS = 8'h08, R_CLEAR = 8'h0C, R_LEASE = 8'h10,
                 R_MAXKEY = 8'h14, R_TLIM = 8'h18, R_KEYTIME = 8'h1C, R_WDOG = 8'h20, R_WDOG_MS = 8'h24,
                 R_DISARM = 8'h28, R_CMD_DATA = 8'h2C, R_CMD_ADDR = 8'h30, R_I2C = 8'h34, R_I2C_ST = 8'h38,
                 R_I2C_RD = 8'h3C, R_BIAS = 8'h40, R_LED = 8'h44, R_FAN = 8'h48, R_INPUTS = 8'h4C, R_ADCSEQ = 8'h50;

localparam [31:0] PERMIT = 32'h54580000;

// keep renewing the permission with the given bits every 40 ms while renew = 1
logic       renew = 1'b0;
logic [2:0] renew_bits = 3'b001;
initial forever begin
  bit ok;
  ms(40);
  if (renew) wr(R_PERMIT, PERMIT | renew_bits, 1'b0, ok, 1);   // the CPU renews (firmware path)
end

logic [31:0] st;
task automatic status();
  // the request and the status cross between the CPU and control clocks: give it some cycles
  repeat (500) @(posedge clk);
  rd(R_STATUS, st);
endtask

function automatic [5:0] trips(input [31:0] s);  return s[13:8];  endfunction
function automatic [5:0] causes(input [31:0] s); return s[21:16]; endfunction

// measure the outputs: time of the last change of exttr (relays) and dac_en (PA stage)
real t_rel_on, t_rel_off, t_pa_on, t_pa_off;
always @(posedge exttr)  t_rel_on  = sim_ms();
always @(negedge exttr)  t_rel_off = sim_ms();
always @(posedge dac_en) t_pa_on   = sim_ms();
always @(negedge dac_en) t_pa_off  = sim_ms();

// the PA stage outputs must always agree with each other, and never be on without the relays
logic [2:0] pa_cfg_d = 3'b000;
always @(posedge clk_ctrl) pa_cfg_d <= pa_cfg;
always @(posedge clk_ctrl) begin
  if (envop != dac_en || envpa != (dac_en & pa_cfg_d[0] & ~pa_cfg_d[2]) || envbias != (dac_en & pa_cfg_d[0] & ~pa_cfg_d[2])) begin
    $display("[%0.1f ms] FAIL  PA stage outputs disagree", sim_ms()); errors = errors + 1;
  end
  if (dac_en & ~exttr) begin
    $display("[%0.1f ms] FAIL  PA stage on without the relays", sim_ms()); errors = errors + 1;
  end
end

task automatic key_down_ok(input string what);
  renew = 1'b1;
  ms(60);
  status();
  check(exttr & dac_en & envpa & envbias & envop & inttr & tx_on, {what, ": all transmit outputs on"});
  check(st[0] & st[1] & st[2] & st[3] & ~st[4] & ~st[5], $sformatf("%s: status %08x", what, st));
endtask

task automatic clear();
  w(R_CLEAR, 32'h434C5452);
  status();
endtask

//////////////////////////////////////////////////////////////////////////////

initial begin
  bit ok;
  logic [31:0] v;
  real t0;

  // ---------------- power-up
  repeat (20) @(posedge clk_ctrl);
  check(!(envpa | envop | envbias | inttr | exttr | rfsw | dac_en), "power-up: every transmit output off");
  status();
  check(st[2] == 1'b0 && st[0] == 1'b0, "power-up: no lease, transmit off");
  check(st[16+0] && st[16+5], $sformatf("power-up: lease and stale-temperature cut-offs present (%08x)", st));
  check(trips(st) == 0, "power-up: no trips");
  rd(R_ID, v);          check(v == 32'h494F3031, "ID register");
  rd(R_LEASE, v);       check(v == 100, "default lease 100 ms");
  rd(R_MAXKEY, v);      check(v == 600, "default max key-down 600 s");
  rd(R_TLIM, v);        check(v == 12'h527, "default temperature limit 0x527 (55 C)");
  rd(R_INPUTS, v);      check(v[12:0] == 13'h1a5a, "raw input pins readable");
  ms(70);                                                           // first ADC tick
  status();
  check(!st[16+5], "temperature reading fresh after the first ADC cycle");
  check(rfsw == 1'b0, "RF path switch off with the PA disabled");
  pa_cfg = 3'b001;                         // command 0x09: PA enabled
  ms(2);
  check(rfsw == 1'b1 && !exttr && !envpa, "RF path switch follows PA enable (static config), nothing keyed");

  // ---------------- permission key
  wr(R_PERMIT, 32'h12340001, 1'b1, ok);
  status();
  check(!st[2], "permission with the wrong key: ignored");

  // ---------------- permission without key: lease valid, nothing on
  w(R_PERMIT, PERMIT | 0);
  ms(5);
  status();
  check(st[2] && !st[3] && !tx_on, "permission without key: lease valid, transmit off");
  ms(120);
  status();
  check(!st[2] && trips(st) == 0, "lease ran out while not keyed: no trip");

  // ---------------- keyed by renewing, sequencing
  renew_bits = 3'b001;
  key_down_ok("keyed by lease renewal");
  check(t_pa_on - t_rel_on >= 9.5 && t_pa_on - t_rel_on <= 12.5, $sformatf("relays %.1f ms before the PA stage", t_pa_on - t_rel_on));
  rd(R_KEYTIME, v);
  check(v[9:0] > 0 || v[19:10] > 0, $sformatf("key-down time counts (%0d.%03d s)", v[19:10], v[9:0]));

  // ---------------- normal key-up: key bit 0, then the lease runs out
  renew_bits = 3'b000;
  ms(50);
  check(!dac_en && !exttr, "key bit 0: outputs off");
  check(t_rel_off - t_pa_off >= 9.5 && t_rel_off - t_pa_off <= 12.5, $sformatf("PA stage off %.1f ms before the relays", t_rel_off - t_pa_off));
  renew = 1'b0;
  ms(150);
  status();
  check(trips(st) == 0 && !st[2], "normal key-up and lease end: no trip");

  // ---------------- trip: lease expires while keyed
  renew_bits = 3'b001;
  key_down_ok("keyed again");
  renew = 1'b0;
  t0 = sim_ms();
  ms(150);
  status();
  check(!dac_en && !exttr, "lease expired while keyed: outputs off");
  check(t_pa_off - t0 <= 130.0, $sformatf("PA off %.1f ms after the last renewal (lease 100 ms)", t_pa_off - t0));
  check(trips(st) == 6'b000001 && st[4], $sformatf("trip reason 'lease' latched (%08x)", st));
  renew = 1'b1;
  ms(60);
  check(!exttr && !dac_en, "renewing again does not key while the trip is latched");
  clear();
  check(trips(st) == 0, "clear removes the lease trip");
  ms(60);
  check(exttr && dac_en, "keys again after the clear");

  // ---------------- trip: over-temperature from the ADC code
  temperature = 12'h528;                   // just above 55 C
  ms(2);
  check(!dac_en, "over-temperature: PA stage off at once");
  ms(15);
  status();
  check(!exttr && trips(st) == 6'b000010 && st[16+1], $sformatf("trip reason 'over-temperature' (%08x)", st));
  check(st[17] == 1'b1, "over-temperature cut-off bit");
  clear();
  check(trips(st) == 6'b000010, "clear while still hot: trip stays");
  temperature = 12'h3ed;
  ms(5);
  clear();
  check(trips(st) == 0, "clear after cooling: trip removed");
  ms(60);
  check(exttr && dac_en, "keys again after cooling and clear");

  // ---------------- trip: over-temperature state of the fan logic
  fan_overheat = 1'b1;
  ms(20);
  status();
  check(!exttr && trips(st) == 6'b000010, "fan logic overheat state trips 'over-temperature'");
  fan_overheat = 1'b0;
  ms(2);
  clear();
  ms(60);
  check(exttr && dac_en, "keys again");

  // ---------------- temperature limit can only be lowered
  w(R_TLIM, 32'h800);
  rd(R_TLIM, v);
  check(v == 12'h527, "temperature limit above 55 C clamped to 0x527");
  w(R_TLIM, 32'h3e0);                      // below the current 0x3ed
  ms(20);
  status();
  check(!exttr && trips(st) == 6'b000010, "lowered temperature limit below the reading: trip");
  w(R_TLIM, 32'h527);
  ms(2);
  clear();
  ms(60);
  check(exttr && dac_en, "keys again");

  // ---------------- trip: stale temperature reading
  adc_run = 1'b0;
  ms(1100);
  status();
  check(!exttr && trips(st) == 6'b100000 && st[16+5], $sformatf("no ADC reading for 1 s: trip 'stale temperature' (%08x)", st));
  adc_run = 1'b1;
  ms(70);
  clear();
  check(trips(st) == 0, "clear after the ADC reads again");
  ms(60);
  check(exttr && dac_en, "keys again");

  // ---------------- trip: TX inhibit input
  inhibit = 1'b1;
  ms(2);
  check(!dac_en, "TX inhibit: PA stage off at once");
  ms(15);
  status();
  check(!exttr && trips(st) == 6'b000100, "trip reason 'TX inhibit'");
  clear();
  check(trips(st) == 6'b000100, "clear while inhibit still active: trip stays");
  inhibit = 1'b0;
  ms(2);
  clear();
  ms(60);
  check(exttr && dac_en, "keys again after inhibit released and clear");

  // ---------------- trip: CPU watchdog
  w(R_WDOG_MS, 32'd5);
  rd(R_WDOG_MS, v);
  check(v == 10, "watchdog timeout clamped to 10 ms minimum");
  w(R_WDOG_MS, 32'd200);
  wr(R_WDOG, 32'h57444F47, 1'b0, ok);      // CPU kicks
  check(ok, "CPU can kick the watchdog");
  repeat (5) begin ms(100); wr(R_WDOG, 32'h57444F47, 1'b0, ok); end
  status();
  check(exttr && dac_en && trips(st) == 0, "kicked watchdog: still keyed");
  ms(260);
  rd(R_WDOG, v);
  check(v[31] && v[30], "watchdog fired and armed");
  status();
  check(!exttr && trips(st) == 6'b001000, $sformatf("trip reason 'watchdog' (%08x)", st));
  wr(R_DISARM, 32'd1, 1'b0, ok);
  check(!ok, "CPU cannot disarm the watchdog");
  clear();
  check(trips(st) == 6'b001000, "clear while the watchdog is still fired: trip stays");
  wr(R_WDOG, 32'h57444F47, 1'b0, ok);      // CPU alive again
  ms(2);
  w(R_DISARM, 32'd1);                      // bridge disarms
  rd(R_WDOG, v);
  check(!v[31] && !v[30], "bridge disarm clears fired and armed");
  clear();
  check(trips(st) == 0, "clear after the watchdog recovered");
  ms(60);
  check(exttr && dac_en, "keys again");

  // ---------------- trip: maximum key-down time
  renew_bits = 3'b000;                     // key up: the key-down time restarts
  ms(60);
  w(R_MAXKEY, 32'd9999);
  rd(R_MAXKEY, v);
  check(v == 600, "max key-down above 600 s clamped");
  w(R_MAXKEY, 32'd0);
  rd(R_MAXKEY, v);
  check(v == 1, "max key-down 0 clamped to 1 s");
  renew_bits = 3'b001;
  ms(60);
  check(exttr && dac_en, "keyed with max key-down 1 s");
  ms(1000);
  status();
  check(!exttr && trips(st) == 6'b010000, $sformatf("trip reason 'max key-down' after 1 s (%08x)", st));
  clear();
  check(trips(st) == 6'b010000, "clear while still keyed: trip stays");
  renew_bits = 3'b000;
  ms(50);
  clear();
  check(trips(st) == 0, "clear after key-up");
  w(R_MAXKEY, 32'd600);

  // ---------------- PTT and key inputs
  renew_bits = 3'b000;
  ptt_in = 1'b1;
  ms(60);
  check(!exttr, "PTT input with PTT keying disabled: nothing");
  renew_bits = 3'b010;
  ms(60);
  check(exttr && dac_en, "PTT input keys with PTT keying enabled (lease renewed)");
  ptt_in = 1'b0;
  ms(30);
  check(!dac_en, "PTT released: PA stage off");
  key_in = 1'b1;
  ms(60);
  check(!exttr, "key input with key keying disabled: nothing");
  renew_bits = 3'b100;
  ms(60);
  check(exttr && dac_en, "key (tip) input keys with key keying enabled");
  renew = 1'b0;
  ms(150);
  status();
  check(!exttr && trips(st) == 6'b000001, "lease runs out while the key input holds TX: trip 'lease'");
  key_in = 1'b0;
  clear();

  // ---------------- PA configuration from command 0x09
  pa_cfg = 3'b010;                          // PA disabled, T/R disable: no internal T/R relay, no PA
  renew_bits = 3'b001;
  renew = 1'b1;
  ms(60);
  check(exttr && dac_en && !inttr && !envpa && !envbias && envop && !rfsw, "PA disabled + T/R disable: external T/R and DAC only");
  pa_cfg = 3'b000;
  ms(5);
  check(inttr && !envpa, "PA disabled, T/R enabled: internal T/R relay on, no PA supply");
  renew_bits = 3'b000;
  renew = 1'b0;
  pa_cfg = 3'b001;
  ms(150);

  // ---------------- lease length clamp and use
  w(R_LEASE, 32'd5000); rd(R_LEASE, v); check(v == 1000, "lease above 1000 ms clamped");
  w(R_LEASE, 32'd1);    rd(R_LEASE, v); check(v == 10, "lease below 10 ms clamped");
  w(R_LEASE, 32'd20);
  w(R_PERMIT, PERMIT | 1);
  ms(35);
  status();
  check(!st[2] && !exttr && trips(st) == 6'b000001, "20 ms lease, keyed once: expired within 35 ms with a trip");
  clear();
  w(R_LEASE, 32'd100);

  // ---------------- command injector and I2C transfer register
  begin
    integer n0;
    n0 = n_cmds;
    w(R_CMD_DATA, 32'h00017850);
    w(R_CMD_ADDR, 32'h0a);
    wr(R_CMD_ADDR, 32'h0a, 1'b1, ok);
    check(!ok, "second command while the first is on its way: refused (busy)");
    repeat (4000) @(posedge clk);
    check(n_cmds == n0 + 1 && last_cmd_addr == 6'h0a && last_cmd_data == 32'h00017850, "command 0x0A injected with its data");
    rd(R_CMD_ADDR, v);
    check(!v[31] && v[15:8] == 1 && v[5:0] == 6'h0a, $sformatf("CMD_ADDR status %08x", v));
    w(R_I2C, 32'h80200A55);                // bus 2, write, address 0x20, register 0x0a, value 0x55
    repeat (4000) @(posedge clk);
    check(last_cmd_addr == 6'h3d && last_cmd_data == 32'h06200A55, $sformatf("I2C bus 2 write -> command 0x3D %08x", last_cmd_data));
    w(R_I2C, 32'h4180_0000 | (7'h6a << 16));   // bus 1, probe (read + probe bits), 0x6A
    repeat (4000) @(posedge clk);
    check(last_cmd_addr == 6'h3c && last_cmd_data == 32'h07EA0000, $sformatf("I2C bus 1 probe -> command 0x3C %08x", last_cmd_data));
    w(R_I2C, 32'hC1B40000);                // bus 3, probe 0x34
    repeat (4000) @(posedge clk);
    check(last_cmd_addr == 6'h3e && last_cmd_data == 32'h07B40000, $sformatf("I2C bus 3 probe -> command 0x3E %08x", last_cmd_data));
    wr(R_I2C, 32'h01200000, 1'b1, ok);
    check(!ok, "I2C transfer with bus 0 refused");
    rd(R_I2C_ST, v);
    check(v == {8'd7, 8'd9, 11'd0, 1'b0, 4'b0010}, $sformatf("I2C status from the control clock %08x", v));
    rd(R_I2C_RD, v);
    check(v == 32'hA1B2C3D4, "I2C read data from the control clock");
  end

  // ---------------- bias unlock, LED, fan
  w(R_BIAS, 32'h42494153);
  repeat (40) @(posedge clk_ctrl);
  check(bias_unlock_c == 1'b1, "bias unlock with the key");
  w(R_BIAS, 32'h1);
  repeat (40) @(posedge clk_ctrl);
  check(bias_unlock_c == 1'b0, "bias locked again with any other value");
  w(R_LED, 32'h000000A5);
  w(R_FAN, 32'h0000000F);
  repeat (40) @(posedge clk_ctrl);
  check(led_c == 8'hA5 && fan_min_c == 4'hF, "LED and fan registers reach the control clock");
  rd(R_FAN, v);
  check(v[3:0] == 4'hF && v[11:8] == 4'b0011, "fan register read back with the fan state");
  rd(R_ADCSEQ, v);
  check(v == 1234, "ADC cycle counter");

  $display("");
  if (errors == 0) $display("tb_ilk PASS");
  else $display("tb_ilk FAIL: %0d errors", errors);
  $finish;
end

endmodule
