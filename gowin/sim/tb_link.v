//
//  tb_link.v — full-link self-checking simulation: HL2 side (gowinlink_hl2) <-> two cable
//  models <-> Gowin side (gl_top). Drives the Gowin debug console like the user would
//  ('t', 'r', 'x', 'l', 's', 'c', 'p'), watches the internals hierarchically, and checks:
//
//   1. the forward link trains (sweep, alignment, verification) and locks
//   2. the reverse link locks autonomously and the command channel works through it
//   3. PRBS error counters stay zero with no injected errors, count injected errors on
//      the right lane only, and clear on 'r'
//   4. Ethernet-originated commands pass the arbiter in order and none is lost while
//      link commands (the 'x' test command) are interleaved
//   5. live ADC samples (ramp + sine) arrive bit-exact, with and without scrambling
//   6. counter mode is word-exact in both directions
//   7. fast serial test packets arrive with no CRC errors
//
//  Run for LANES = 6 (default) and LANES = 3 (fallback), see run_sim.sh.
//
`timescale 1ns/1ps
module tb_link;

parameter integer LANES = 6;

localparam integer SIM_BAUD = 921600;

// ---------------------------------------------------------------- clocks
reg clk2x = 1'b0;                       // 153.6 MHz
always #3.255 clk2x = ~clk2x;
reg clk = 1'b0;                         // 76.8 MHz, rising edges coincide with clk2x rising edges
always @(posedge clk2x) clk <= ~clk;
reg clk50 = 1'b0;
always #10 clk50 = ~clk50;

wire lane_clk = (LANES == 3) ? clk2x : clk;

GSR GSR (.GSRI(1'b1));

// ---------------------------------------------------------------- HL2 side
reg  [11:0] adc_data = 12'h000;
wire        hl2_link_clk, hl2_status_txd, hl2_aux;
wire [LANES-1:0] hl2_link_d;
wire        hl2_rev_clk_in, hl2_fs_in;
wire [2:0]  hl2_rev_in;

reg  [5:0]  eth_addr = 6'h00;
reg  [31:0] eth_data = 32'h0;
reg         eth_cnt  = 1'b0;
wire [5:0]  cmd_addr;
wire [31:0] cmd_data;
wire        cmd_cnt, cmd_resprqst, cmd_is_alt;

reg         run = 1'b1, tx_on = 1'b0, cw_on = 1'b0, ptt = 1'b0, key = 1'b0;

gowinlink_hl2 #(
  .LANES                (LANES),
  .CMD_UART             (0),
  .STATUS_BAUD          (SIM_BAUD),
  .CYCLES_10MS          (7680),          // 100 us "10 ms" tick: status frame every 1 ms
  .REV_VERIFY_LEN_LOG2  (8)
) u_hl2 (
  .clk              (clk),
  .lane_clk         (lane_clk),
  .adc_data         (adc_data),
  .link_clk_pin     (hl2_link_clk),
  .link_d_pin       (hl2_link_d),
  .status_txd       (hl2_status_txd),
  .aux_out          (hl2_aux),
  .rev_clk_pin      (hl2_rev_clk_in),
  .gl_rev           (hl2_rev_in),
  .fs_rxd           (hl2_fs_in),
  .eth_cmd_addr     (eth_addr),
  .eth_cmd_data     (eth_data),
  .eth_cmd_cnt      (eth_cnt),
  .eth_cmd_resprqst (1'b0),
  .eth_cmd_is_alt   (1'b0),
  .cmd_addr         (cmd_addr),
  .cmd_data         (cmd_data),
  .cmd_cnt          (cmd_cnt),
  .cmd_resprqst     (cmd_resprqst),
  .cmd_is_alt       (cmd_is_alt),
  .run              (run),
  .tx_on            (tx_on),
  .cw_on            (cw_on),
  .ptt              (ptt),
  .key              (key),
  .temperature      (12'h812),
  .fwdpwr           (12'h123),
  .revpwr           (12'h045),
  .bias             (12'h3AB),
  .link_ptt         (),
  .rev_clk          (),
  .rev_sample       (),
  .rev_sample_valid ()
);

// ---------------------------------------------------------------- cables
// forward: clock + data lanes, skews up to +/-1.5 ns
wire [LANES-1:0] fwd_flip;
wire [LANES-1:0] gw_link_d;
wire             gw_fwd_clk;
reg  [LANES-1:0] fwd_flip_r = {LANES{1'b0}};
assign fwd_flip = fwd_flip_r;

generate
  if (LANES == 6) begin : G_C6
    tb_cable #(.W(6), .BASE_PS(3000),
               .SKEW_PS({-16'd200, 16'd900, -16'd1400, 16'd1200, -16'd700, 16'd300}))
      cable_fwd (.i(hl2_link_d), .flip(fwd_flip), .o(gw_link_d));
  end else begin : G_C3
    tb_cable #(.W(3), .BASE_PS(3000),
               .SKEW_PS({16'd1100, -16'd900, 16'd300}))
      cable_fwd (.i(hl2_link_d), .flip(fwd_flip), .o(gw_link_d));
  end
endgenerate
tb_cable #(.W(1), .BASE_PS(3000), .SKEW_PS(16'd100)) cable_fwd_clk (.i(hl2_link_clk), .flip(1'b0), .o(gw_fwd_clk));

wire gw_status_rxd;
tb_cable #(.W(1), .BASE_PS(3000)) cable_status (.i(hl2_status_txd), .flip(1'b0), .o(gw_status_rxd));

// reverse: clock + 3 lanes + fast serial
wire [2:0] gw_rev, rev_flip;
wire       gw_rev_clk, gw_fs_txd, gw_cmd_txd;
reg  [2:0] rev_flip_r = 3'b000;
assign rev_flip = rev_flip_r;
tb_cable #(.W(3), .BASE_PS(3000), .SKEW_PS({16'd800, -16'd500, 16'd400})) cable_rev (.i(gw_rev), .flip(rev_flip), .o(hl2_rev_in));
tb_cable #(.W(1), .BASE_PS(3000), .SKEW_PS(-16'd100)) cable_rev_clk (.i(gw_rev_clk), .flip(1'b0), .o(hl2_rev_clk_in));
tb_cable #(.W(1), .BASE_PS(3000), .SKEW_PS(16'd200))  cable_fs      (.i(gw_fs_txd),  .flip(1'b0), .o(hl2_fs_in));

// ---------------------------------------------------------------- Gowin side
reg  dbg_rxd = 1'b1;
wire dbg_txd;
wire [3:0] led;

gl_top #(
  .LANES            (LANES),
  .CMD_UART         (0),
  .DEBUG_BAUD       (SIM_BAUD),
  .STATUS_BAUD      (SIM_BAUD),
  .CONSOLE_PERIOD   (100000),     // 2 ms
  .SWEEP_LEN_LOG2   (6),
  .VERIFY_LEN_LOG2  (8),
  .SETTLE_CYCLES    (500),        // 10 us
  .AUTOTRAIN_CYCLES (25000),      // 0.5 ms
  .CLK_TIMEOUT      (5000),       // 100 us
  .STATUS_TIMEOUT   (250000),     // 5 ms
  .FS_TEST_PERIOD   (38400)       // 0.5 ms
) u_gowin (
  .clk50       (clk50),
  .fwd_clk     (gw_fwd_clk),
  .link_d      (gw_link_d),
  .status_rxd  (gw_status_rxd),
  .aux_in      (1'b0),
  .rev_clk_out (gw_rev_clk),
  .gl_rev      (gw_rev),
  .fs_txd      (gw_fs_txd),
  .cmd_txd     (gw_cmd_txd),
  .dbg_txd     (dbg_txd),
  .dbg_rxd     (dbg_rxd),
  .led         (led),
  .key_n       (1'b1)
);

// ---------------------------------------------------------------- console monitor
localparam real BIT_NS = 1.0e9 / SIM_BAUD;
reg [7:0] line [0:511];
integer   linelen = 0;
integer   nlines = 0;

task dbg_recv_byte(output [7:0] b);
  integer k;
  begin
    @(negedge dbg_txd);
    #(BIT_NS * 1.5);
    for (k = 0; k < 8; k = k + 1) begin
      b[k] = dbg_txd;
      #(BIT_NS);
    end
  end
endtask

reg [7:0] rb;
integer   k2;
always begin
  dbg_recv_byte(rb);
  if (rb == 8'h0A) begin
    $write("[%0t] CONSOLE: ", $time);
    for (k2 = 0; k2 < linelen; k2 = k2 + 1) $write("%c", line[k2]);
    $write("\n");
    linelen = 0;
    nlines  = nlines + 1;
  end else if (rb != 8'h0D && linelen < 512) begin
    line[linelen] = rb;
    linelen = linelen + 1;
  end
end

task dbg_send(input [7:0] b);
  integer k;
  begin
    dbg_rxd = 1'b0;
    #(BIT_NS);
    for (k = 0; k < 8; k = k + 1) begin
      dbg_rxd = b[k];
      #(BIT_NS);
    end
    dbg_rxd = 1'b1;
    #(BIT_NS * 2);
  end
endtask

// ---------------------------------------------------------------- ADC stimulus and record
reg [11:0] tx_hist [0:65535];
integer    tx_n = 0;
integer    stim_phase = 0;   // 0 ramp, 1 sine
real       ang = 0.0;
always @(posedge clk) begin
  if (stim_phase == 0) adc_data <= adc_data + 12'd1;
  else begin
    ang = ang + 0.0123;
    adc_data <= $rtoi(1800.0 * $sin(ang)) + $rtoi(200.0 * $sin(7.0 * ang));
  end
  tx_hist[tx_n[15:0]] <= adc_data;
  tx_n <= tx_n + 1;
end

// received samples at the Gowin
reg [11:0] rx_hist [0:65535];
integer    rx_n = 0;
integer    rx_rec = 0;
integer    tx_base = 0;      // tx_n when recording started
always @(posedge gw_fwd_clk) begin
  if (rx_rec && u_gowin.dp_i.sample_valid) begin
    if (rx_n == 0) tx_base = tx_n;
    rx_hist[rx_n[15:0]] <= u_gowin.dp_i.sample;
    rx_n <= rx_n + 1;
  end
end

// ---------------------------------------------------------------- Ethernet command scoreboard
reg [37:0] eth_q [0:1023];
integer    eth_wr = 0, eth_rd = 0;
integer    link_cmd_seen = 0, bad_cmd = 0;
reg        cmd_cnt_d = 1'b0;
always @(posedge clk) begin
  cmd_cnt_d <= cmd_cnt;
  if (cmd_cnt != cmd_cnt_d) begin
    if (eth_rd < eth_wr && {cmd_addr, cmd_data} == eth_q[eth_rd % 1024]) begin
      eth_rd = eth_rd + 1;
    end else if (cmd_addr == 6'h01 && cmd_data == 32'h00ABCDEF) begin
      link_cmd_seen = link_cmd_seen + 1;
    end else begin
      bad_cmd = bad_cmd + 1;
      $display("[%0t] ERROR: unexpected command on the bus addr=%h data=%h", $time, cmd_addr, cmd_data);
    end
  end
end

integer eth_run = 0;
integer eth_seed = 1;
always begin
  #(10000 + ($urandom(eth_seed) % 50000) / 1.0);
  if (eth_run) begin
    @(posedge clk);
    eth_addr <= $urandom % 64;
    eth_data <= $urandom;
    @(posedge clk);
    eth_q[eth_wr % 1024] = {eth_addr, eth_data};
    eth_wr = eth_wr + 1;
    eth_cnt <= ~eth_cnt;
  end
end

// ---------------------------------------------------------------- helpers
integer errors = 0;
task check(input cond, input [511:0] msg);
  begin
    if (!cond) begin
      errors = errors + 1;
      $display("[%0t] FAIL: %0s", $time, msg);
    end else begin
      $display("[%0t] ok:   %0s", $time, msg);
    end
  end
endtask


function all_zero_prbs;
  input [32*LANES-1:0] v;
  begin
    all_zero_prbs = (v == {(32*LANES){1'b0}});
  end
endfunction

task flip_fwd_lane(input integer lane, input integer nbits);
  integer b;
  begin
    for (b = 0; b < nbits; b = b + 1) begin
      @(posedge lane_clk);
      #0.5;
      fwd_flip_r[lane] = 1'b1;
      #((LANES == 6) ? 6.5 : 3.25);
      fwd_flip_r[lane] = 1'b0;
      #100;
    end
  end
endtask

task flip_rev_lane(input integer lane, input integer nbits);
  integer b;
  begin
    for (b = 0; b < nbits; b = b + 1) begin
      @(posedge clk2x);
      #0.5;
      rev_flip_r[lane] = 1'b1;
      #3.25;
      rev_flip_r[lane] = 1'b0;
      #100;
    end
  end
endtask

// compare rx_hist against tx_hist: the first received sample was transmitted 'lat'
// samples before tx_base (unknown link latency, searched 0..4000)
task check_live(input [511:0] what);
  integer lat, i, best_lat, match, found, mism, base;
  begin
    found = 0; best_lat = 0;
    for (lat = 0; lat < 4000 && !found; lat = lat + 1) begin
      base  = tx_base - lat;
      match = 1;
      for (i = 0; i < 64; i = i + 1)
        if (rx_hist[i] != tx_hist[(base + i) & 16'hFFFF]) match = 0;
      if (match) begin found = 1; best_lat = lat; end
    end
    if (!found) begin
      check(0, what);
    end else begin
      base = tx_base - best_lat;
      mism = 0;
      for (i = 0; i < rx_n - 1; i = i + 1)
        if (rx_hist[i] != tx_hist[(base + i) & 16'hFFFF]) mism = mism + 1;
      $display("[%0t] live check %0s: latency %0d samples, %0d samples, %0d mismatches", $time, what, best_lat, rx_n, mism);
      check(mism == 0, what);
    end
  end
endtask

// ---------------------------------------------------------------- main sequence
integer ok, i;
reg [32*LANES-1:0] fe;
reg [95:0] re;
initial begin
  $display("tb_link LANES=%0d", LANES);
  eth_run = 1;

  // 1. wait for the forward link to lock (reverse bootstrap + auto-train happen first)
  fork
    begin : W1
      while (u_gowin.train_i.state != 3'd4) #1000;
    end
    begin : T1
      #40000000;   // 40 ms
      $display("[%0t] timeout waiting for forward LOCKED (state=%0d fail=%0d)", $time, u_gowin.train_i.state, u_gowin.train_i.fail);
      errors = errors + 1;
      disable W1;
    end
  join_any
  disable T1;
  check(u_gowin.train_i.state == 3'd4, "forward link LOCKED");
  check(u_gowin.train_i.rev_locked, "HL2 reports reverse link locked");
  $display("[%0t] taps=%h eye=%h off=%h swap=%0d rev off=%h swap=%0d", $time,
           u_gowin.dp_i.tap, u_gowin.train_i.eye, u_gowin.dp_i.off, u_gowin.dp_i.pair_swap,
           u_hl2.rev_dp_i.off, u_hl2.rev_dp_i.pair_swap);

  // 2. PRBS BER test, both directions, no errors expected
  #1500000;
  fe = u_gowin.dp_i.acc_prbs;
  re = u_hl2.rev_dp_i.acc_prbs;
  check(all_zero_prbs(fe), "forward PRBS mismatches are zero");
  check(u_gowin.dp_i.acc_words > 40'd50000, "forward words counted");
  check(re == 96'd0, "reverse PRBS mismatches are zero");
  check(u_hl2.rev_dp_i.acc_words > 40'd10000, "reverse words counted");
  check(u_hl2.rev_train_i.acc_prbs_en, "HL2 reverse PRBS accumulator enabled by REV_MODE");

  // 3. injected errors land on the right lane
  flip_fwd_lane(1, 3);
  flip_rev_lane(2, 2);
  #50000;
  fe = u_gowin.dp_i.acc_prbs;
  re = u_hl2.rev_dp_i.acc_prbs;
  check(fe[32*1 +: 32] >= 3 && fe[32*1 +: 32] <= 9, "forward lane 1 counted the injected errors");
  check(fe[31:0] == 0 && (LANES == 3 ? fe[95:64] == 0 : (fe[95:64] == 0 && fe[191:96] == 0)), "other forward lanes stayed clean");
  check(re[95:64] >= 2 && re[95:64] <= 6, "reverse lane 2 counted the injected errors");
  check(re[63:0] == 64'd0, "other reverse lanes stayed clean");

  // 4. reset counters
  dbg_send("r");
  #300000;
  check(all_zero_prbs(u_gowin.dp_i.acc_prbs), "forward counters cleared by r");
  check(u_hl2.rev_dp_i.acc_prbs == 96'd0, "reverse counters cleared by r");

  // 5. test openHPSDR command over the link
  dbg_send("x");
  #300000;
  check(link_cmd_seen >= 1, "test command 0x01/0x00ABCDEF reached the HL2 command bus");

  // 6. live mode, bit-exact delivery
  dbg_send("l");
  #200000;
  rx_n = 0; rx_rec = 1;
  #60000;
  rx_rec = 0;
  check_live("live samples bit-exact (ramp, scrambler off)");
  stim_phase = 1;
  dbg_send("s");
  #300000;
  check(u_hl2.scr_en && u_gowin.train_i.scr_on, "scrambler on both sides");
  rx_n = 0; rx_rec = 1;
  #60000;
  rx_rec = 0;
  check_live("live samples bit-exact (sine, scrambler on)");

  // 7. counter mode both directions
  dbg_send("c");
  #1000000;
  check(u_gowin.dp_i.acc_werr == 32'd0 && u_gowin.dp_i.acc_words > 40'd20000, "forward counter mode word-exact");
  check(u_hl2.rev_dp_i.acc_werr == 32'd0 && u_hl2.rev_train_i.acc_wchk_en, "reverse counter mode word-exact");

  // 8. back to PRBS, scrambler off, final checks
  dbg_send("s");
  #200000;
  dbg_send("p");
  #1000000;
  check(all_zero_prbs(u_gowin.dp_i.acc_prbs), "forward PRBS clean after mode changes");
  check(u_hl2.rev_dp_i.acc_prbs == 96'd0, "reverse PRBS clean after mode changes");
  check(u_hl2.G_CMD_FS.fs_rx_i.pkt_ok > 16'd8 && u_hl2.G_CMD_FS.fs_rx_i.pkt_err <= 16'd2, "fast serial packets received (at most the bootstrap packet lost)");
  $display("[%0t] status frames good %0d bad %0d", $time, u_gowin.status_rx_i.frame_cnt, u_gowin.status_rx_i.err_cnt);
  check(u_gowin.status_rx_i.frame_cnt >= 16'd5 && u_gowin.status_rx_i.err_cnt <= 16'd2, "status frames received (at most the hunt-in errors)");

  eth_run = 0;
  #4000000;   // let the console finish at least one more status line
  $display("[%0t] Ethernet commands issued %0d, passed %0d, link commands %0d, unexpected %0d", $time, eth_wr, eth_rd, link_cmd_seen, bad_cmd);
  check(eth_wr > 20 && eth_rd == eth_wr && bad_cmd == 0, "all Ethernet commands passed the arbiter in order");
  check(nlines >= 2, "console lines printed");

  if (errors == 0) $display("PASS (LANES=%0d)", LANES);
  else             $display("FAIL (LANES=%0d): %0d errors", LANES, errors);
  $finish;
end

endmodule
