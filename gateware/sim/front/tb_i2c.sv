// SPDX-License-Identifier: GPL-2.0-or-later
// Copyright 2026 Franz Schöning, https://www.schoning.com
//
// I2C and AD9866 SPI register paths of the raw front-end image: rtl/control.v (RAWFRONT = 1, FAN, PSSYNC,
// FAST_LNA as in hl2b5up_raw) with rtl/i2c.v, i2c_bus2.v, i2c_master.v, slow_adc.v and ad9866ctrl.v, and
// behavioural I2C slaves on the three buses: Versa 5 (0x6A) on bus 1; MCP23008 filter board (0x20) and
// MCP4662 bias pots/EEPROM (0x2C) on bus 2 (no device at 0x1D: the Pico IO board is absent); the slow ADC
// (0x34) on bus 3. Commands arrive on the command bus as the register block's injector puts them there.
// (control.v's generate labels clash with its parameter names in iverilog; run.sh simulates a copy with
// the labels renamed.)
//
// Checks: power-up Versa init and EEPROM reads; bus 2 register write and 4-byte read with the status
// (done count, NACK, read data); write to an absent device (NACK); address-only probes on buses 1, 2
// and 3 (present and absent); the slow ADC keeps sampling around bus-3 probes; the bias guard refuses
// writes and increment/decrement commands to 0x2C while locked and allows read commands and probes; a
// write after unlock reaches the device; a request while the engine is busy is reported as dropped; the
// stock filter command 0x00 still writes the MCP23008; AD9866 SPI frames for the generic write 0x3B and
// TX gain 0x09; PA configuration bits of 0x09; LED override; minimum fan duty.
`timescale 1 ps / 1 ps

module tb_i2c;

localparam real T_CTRL = 400_000.0;

logic clk = 0, clk_ad = 0, clk_125 = 0;
always #(T_CTRL/2) clk = ~clk;
always #500_000    clk_ad = ~clk_ad;        // only used for the clock monitor and CW here: slow keeps it fast
always #300_000    clk_125 = ~clk_125;      // supply sync clocks only

integer errors = 0;
task automatic check(input bit ok, input string what);
  if (ok) $display("[%0.2f ms] ok    %s", $realtime / 1.0e9, what);
  else begin $display("[%0.2f ms] FAIL  %s", $realtime / 1.0e9, what); errors = errors + 1; end
endtask

// buses with pull-ups
tri1 scl1, sda1, scl2, sda2, scl3, sda3;
logic sda1_o, sda1_t, scl1_o, scl1_t, sda2_o, sda2_t, scl2_o, scl2_t, sda3_o, sda3_t, scl3_o, scl3_t;
assign scl1 = scl1_t ? 1'bz : scl1_o;  assign sda1 = sda1_t ? 1'bz : sda1_o;
assign scl2 = scl2_t ? 1'bz : scl2_o;  assign sda2 = sda2_t ? 1'bz : sda2_o;
assign scl3 = scl3_t ? 1'bz : scl3_o;  assign sda3 = sda3_t ? 1'bz : sda3_o;

i2c_slave_model #(.ADDR(7'h6a)) versa   (.scl(scl1), .sda(sda1));
i2c_slave_model #(.ADDR(7'h20)) mcp23008(.scl(scl2), .sda(sda2));
i2c_slave_model #(.ADDR(7'h2c)) mcp4662 (.scl(scl2), .sda(sda2));
i2c_slave_model #(.ADDR(7'h34)) adc     (.scl(scl3), .sda(sda3));

logic [ 5:0] cmd_addr = 6'd0;
logic [31:0] cmd_data = 32'd0;
logic        cmd_rqst = 1'b0;
logic        bias_unlock = 1'b0;
logic [ 7:0] led_ovr = 8'd0;
logic [ 3:0] fan_min = 4'd0;
logic [55:0] i2c_status;
logic        adc_tick;
logic [15:0] adc_seq;
logic [ 3:0] fan_status;
logic        fan_overheat, fan_pwm;
logic [ 2:0] pa_cfg;
logic        sdio, sclk, sen_n;
logic        led_run, led_tx, led_75, led_100;
logic [11:0] temp;

control_sim #(
  .VERSION_MAJOR(8'd74), .UART(0), .ATU(0), .FAN(1), .PSSYNC(1), .CW(0), .FAST_LNA(1), .AK4951(0),
  .EXTENDED_RESP(1), .BYPASS_VERSA(0), .SLOW_ADC_FREE(1), .RAWFRONT(1)
) dut (
  .clk(clk), .clk_ad9866(clk_ad), .clk_125(clk_125), .clk_slow(clk_ad), .ethup(1'b1), .have_dhcp_ip(1'b0),
  .have_fixed_ip(1'b0), .network_speed(2'b10), .is_ksz9021(1'b0), .ad9866up(1'b1), .rxclip(1'b0),
  .rxgoodlvl(1'b0), .rxclrstatus(), .run(1'b0), .slave_link_running(1'b0), .dsiq_status(8'd0), .dsiq_sample(),
  .cmd_addr(cmd_addr), .cmd_data(cmd_data), .cmd_rqst(cmd_rqst), .cmd_is_alt(1'b0), .cmd_requires_resp(1'b0),
  .atu_txinhibit(), .tx_on(1'b0), .cw_on(1'b0), .cw_keydown(), .ext_pttout(), .msec_pulse(), .qmsec_pulse(),
  .resp_rqst(1'b0), .resp(), .static_ip(), .alt_mac(), .eeprom_config(),
  .rffe_rfsw_sel(), .rffe_ad9866_rst_n(), .rffe_ad9866_sdio(sdio), .rffe_ad9866_sclk(sclk), .rffe_ad9866_sen_n(sen_n),
  .debug(16'd0), .hl2link_rst_req(), .hl2link_rst_ack(1'b0), .pwr_clk3p3(), .pwr_clk1p2(), .pwr_envpa(),
  .pwr_envop(), .pwr_envbias(),
  .sda1_i(sda1), .sda1_o(sda1_o), .sda1_t(sda1_t), .scl1_i(scl1), .scl1_o(scl1_o), .scl1_t(scl1_t),
  .sda2_i(sda2), .sda2_o(sda2_o), .sda2_t(sda2_t), .scl2_i(scl2), .scl2_o(scl2_o), .scl2_t(scl2_t),
  .sda3_i(sda3), .sda3_o(sda3_o), .sda3_t(sda3_t), .scl3_i(scl3), .scl3_o(scl3_o), .scl3_t(scl3_t),
  .io_led_run(led_run), .io_led_tx(led_tx), .io_led_adc75(led_75), .io_led_adc100(led_100),
  .io_tx_inhibit(1'b1), .io_uart_txd(), .io_cw_keydown(), .io_phone_tip(1'b1), .io_phone_ring(1'b1),
  .io_atu_ack(1'b0), .io_atu_req(), .pa_inttr(), .pa_exttr(), .hl2_reset(), .fan_pwm(fan_pwm), .ad9866_rst(),
  .io_ptt_in(1'b0), .clk_i2c_rst(), .alt_resp_cnt(), .resp_data(), .resp_control(), .temp(temp), .fwdpwr(),
  .revpwr(), .bias(), .control_dsiq_status(), .safety_status(),
  .ilk_tx_on(1'b0), .bias_unlock(bias_unlock), .led_ovr(led_ovr), .fan_min(fan_min), .i2c_status(i2c_status),
  .adc_tick(adc_tick), .adc_seq(adc_seq), .fan_status(fan_status), .fan_overheat(fan_overheat), .pa_cfg(pa_cfg));

// AD9866 SPI frames: 16 bits, sampled on the rising clock edge while enable is low
logic [15:0] spi_sh;
integer      spi_bits = 0;
logic [15:0] spi_frames [$];
always @(posedge sclk) if (!sen_n) begin spi_sh = {spi_sh[14:0], sdio}; spi_bits = spi_bits + 1; end
always @(posedge sen_n) begin
  if (spi_bits == 16) spi_frames.push_back(spi_sh);
  spi_bits = 0;
end

task automatic cmd(input [5:0] a, input [31:0] d);
  @(negedge clk);
  cmd_addr = a; cmd_data = d; cmd_rqst = 1'b1;
  @(negedge clk);
  cmd_rqst = 1'b0;
endtask

function automatic [7:0] n_done();    return i2c_status[15:8];  endfunction
function automatic [7:0] n_ref();     return i2c_status[23:16]; endfunction

// wait until the transfer count moves (or time out)
task automatic wait_done(input [7:0] from, input string what);
  integer t;
  t = 0;
  while (n_done() == from && t < 20000) begin @(posedge clk); t = t + 1; end
  if (t >= 20000) begin $display("FAIL  timeout waiting for %s", what); errors = errors + 1; end
  repeat (4) @(posedge clk);
endtask

// I2C commands in the stock 0x3C/0x3D format, [23] probe; 0x3E probe on bus 3
function automatic [31:0] i2c_w(input [6:0] a, input [7:0] r, input [7:0] v); return {7'h03, 1'b0, 1'b0, a, r, v}; endfunction
function automatic [31:0] i2c_r(input [6:0] a, input [7:0] r);                return {7'h03, 1'b1, 1'b0, a, r, 8'h00}; endfunction
function automatic [31:0] i2c_p(input [6:0] a);                               return {7'h03, 1'b1, 1'b1, a, 16'h0000}; endfunction

initial begin
  logic [7:0] d0, r0;
  integer w0;

  // power-up: reset counter (26 ms), Versa init, EEPROM reads
  #(60.0e9);
  check(versa.mem[8'h17] == 8'h04 && versa.mem[8'h60] == 8'h3b, "Versa 5 initialised on bus 1 at power-up");
  check(mcp4662.addressed >= 7 && mcp4662.writes == 0, "configuration EEPROM (0x2C) read at power-up, nothing written");
  check(adc_seq > 0, $sformatf("slow ADC sampling (%0d cycles)", adc_seq));
  check(!i2c_status[0], "I2C engine idle");

  // bus 2 write and read
  d0 = n_done();
  cmd(6'h3d, i2c_w(7'h20, 8'h0a, 8'h55));
  wait_done(d0, "write 0x20");
  check(mcp23008.mem[8'h0a] == 8'h55, "bus 2 write reached the MCP23008 register 0x0A");
  check(n_done() == d0 + 1 && !i2c_status[1], "write counted as done, no NACK");

  mcp23008.mem[8'h09] = 8'h11; mcp23008.mem[8'h0a] = 8'h22; mcp23008.mem[8'h0b] = 8'h33; mcp23008.mem[8'h0c] = 8'h44;
  d0 = n_done();
  cmd(6'h3d, i2c_r(7'h20, 8'h09));
  wait_done(d0, "read 0x20");
  check(i2c_status[55:24] == 32'h44332211 && !i2c_status[1], $sformatf("bus 2 read of 4 bytes: %08x (first byte in [7:0])", i2c_status[55:24]));

  // absent device
  d0 = n_done();
  cmd(6'h3d, i2c_w(7'h1d, 8'h00, 8'h01));
  wait_done(d0, "write 0x1d");
  check(i2c_status[1], "write to an absent device (Pico IO board 0x1D not fitted): NACK");

  // probes
  d0 = n_done();
  cmd(6'h3d, i2c_p(7'h20));
  wait_done(d0, "probe bus 2 0x20");
  check(!i2c_status[1], "probe bus 2, 0x20 present: ACK");
  w0 = mcp23008.writes;
  d0 = n_done();
  cmd(6'h3d, i2c_p(7'h1d));
  wait_done(d0, "probe bus 2 0x1d");
  check(i2c_status[1], "probe bus 2, 0x1D absent: NACK");
  check(mcp23008.writes == w0, "probes write nothing");
  d0 = n_done();
  cmd(6'h3c, i2c_p(7'h6a));
  wait_done(d0, "probe bus 1 0x6a");
  check(!i2c_status[1], "probe bus 1, Versa 5 0x6A: ACK");
  d0 = n_done();
  cmd(6'h3c, i2c_p(7'h55));
  wait_done(d0, "probe bus 1 0x55");
  check(i2c_status[1], "probe bus 1, 0x55 absent: NACK");
  adc.mem[adc.ptr] = 8'hc3;
  d0 = n_done();
  cmd(6'h3e, i2c_p(7'h34));
  wait_done(d0, "probe bus 3 0x34");
  check(!i2c_status[1] && adc.addressed > 0, "probe bus 3, slow ADC 0x34: ACK");
  d0 = n_done();
  cmd(6'h3e, i2c_p(7'h50));
  wait_done(d0, "probe bus 3 0x50");
  check(i2c_status[1], "probe bus 3, 0x50 absent: NACK");
  begin
    logic [15:0] s0;
    s0 = adc_seq;
    #(300.0e9);
    check(adc_seq > s0 + 2, "slow ADC keeps sampling after the bus-3 probes");
  end

  // bias guard
  w0 = mcp4662.writes;
  r0 = n_ref();
  d0 = n_done();
  cmd(6'h3d, i2c_w(7'h2c, 8'h00, 8'h80));
  #(20.0e9);
  check(mcp4662.writes == w0 && n_ref() == r0 + 1 && i2c_status[2] && n_done() == d0, "locked: write to the bias pots (0x2C) refused");
  cmd(6'h3d, i2c_r(7'h2c, 8'h04));
  #(20.0e9);
  check(n_ref() == r0 + 2 && n_done() == d0, "locked: increment command (read path, bits 3:2 = 01) refused");
  cmd(6'h3d, i2c_r(7'h2c, 8'h0c));
  wait_done(d0, "read 0x2c");
  check(n_ref() == r0 + 2 && !i2c_status[2] && !i2c_status[1], "locked: read command 0x0C to 0x2C allowed");
  d0 = n_done();
  cmd(6'h3d, i2c_p(7'h2c));
  wait_done(d0, "probe 0x2c");
  check(!i2c_status[1], "locked: probe of 0x2C allowed");
  check(mcp4662.writes == w0, "bias pots unchanged while locked");
  bias_unlock = 1'b1;
  d0 = n_done();
  cmd(6'h3d, i2c_w(7'h2c, 8'h00, 8'h80));
  wait_done(d0, "unlocked write 0x2c");
  check(mcp4662.writes == w0 + 1 && mcp4662.mem[8'h00] == 8'h80, "unlocked: write reaches the bias pots");
  bias_unlock = 1'b0;

  // request while busy
  r0 = n_ref();
  d0 = n_done();
  cmd(6'h3d, i2c_r(7'h20, 8'h00));
  cmd(6'h3d, i2c_r(7'h20, 8'h01));
  repeat (3) @(posedge clk);
  check(n_ref() == r0 + 1 && i2c_status[3] && i2c_status[0], "second request while busy: dropped and reported (flag until the next event)");
  wait_done(d0, "busy test");
  #(2.0e9);
  check(n_ref() == r0 + 1 && n_done() == d0 + 1, "the first request completes, the second never runs");

  // stock filter command 0x00 still writes the MCP23008 (register 0x0A = {RX antenna, filters})
  cmd(6'h00, 32'h00A41000 | (1 << 13));
  #(20.0e9);
  check(mcp23008.mem[8'h0a] == {1'b1, 7'h52}, $sformatf("filter command 0x00 wrote 0x%02x to MCP23008 register 0x0A", mcp23008.mem[8'h0a]));

  // AD9866 SPI
  $display("SPI frames since power-up: %0d", spi_frames.size());
  spi_frames.delete();
  cmd(6'h3b, 32'h06_0f_00_a5);           // generic write: address 0x0F, value 0xA5
  #(5.0e9);
  check(spi_frames.size() == 1 && spi_frames[0] == 16'h0fa5, $sformatf("AD9866 generic write 0x3B -> SPI frame %04x", spi_frames.size() ? spi_frames[0] : 16'hffff));
  spi_frames.delete();
  cmd(6'h09, 32'h9008_0000);             // TX gain 9, PA enable (bit 19)
  #(5.0e9);
  check(spi_frames.size() == 1 && spi_frames[0] == 16'h0a49, $sformatf("TX gain 0x09 -> SPI frame %04x (register 0x0A = 0x49)", spi_frames.size() ? spi_frames[0] : 16'hffff));
  check(pa_cfg == 3'b001, "command 0x09: PA enable bit reaches the interlock configuration");
  cmd(6'h09, 32'h9084_0000);             // VNA bit 23, T/R disable bit 18
  #(1.0e9);
  check(pa_cfg == 3'b110, "command 0x09: VNA and T/R disable bits");

  // LEDs and fan
  led_ovr = 8'b1010_1111;
  #(1.0e9);
  check(led_run == 1'b1 && led_tx == 1'b0 && led_75 == 1'b1 && led_100 == 1'b0, "LED override (active-low pins)");
  fan_min = 4'hf;
  #(1.0e9);
  check(fan_pwm == 1'b1 && fan_status[2:0] == 3'b000, "fan forced on with the fan logic off");

  $display("");
  if (errors == 0) $display("tb_i2c PASS");
  else $display("tb_i2c FAIL: %0d errors", errors);
  $finish;
end

endmodule
