// SPDX-License-Identifier: GPL-2.0-or-later
// Copyright 2026 Franz Schöning, https://www.schoning.com
//
// Testbench for rtl/rawstream.v
//
// Uses the real HL2 send path: network.v (udp_send, ip_send, mac_send, crc32),
// the real openHPSDR packer usopenhpsdr1.v (sending discovery replies in between),
// and the Quartus dcfifo simulation model. Every Ethernet frame leaving mac_send
// is checked: CRC32, IP header checksum, IP and UDP lengths. Raw frames are
// unpacked and checked for magic, sequence numbers, sample index, sample
// packing (test pattern = sample index mod 4096, ADC ramp) and flags.
//
// Run: ./run.sh (needs iverilog from oss-cad-suite and Quartus altera_mf.v)

`timescale 1ps/1ps

module tb_rawstream;

// ---------------------------------------------------------------------------
// Clocks: 125 MHz Ethernet TX and 76.8 MHz AD9866, unrelated phases

logic clk = 1'b0;
logic clk_ad = 1'b0;
always #4000 clk = ~clk;
initial begin #1733; forever #6510 clk_ad = ~clk_ad; end

// ---------------------------------------------------------------------------
// Stimulus signals

logic        run = 1'b0;
logic [ 5:0] cmd_addr = 6'h0;
logic [31:0] cmd_data = 32'h0;
logic        cmd_rqst = 1'b0;
logic        stall = 1'b0;            // consumer stall: keeps the network "busy" for the raw sender
logic        discover_rqst = 1'b0;

// ADC ramp: +3 per sample, so a correct ADC capture satisfies sample - 3*index = constant
logic [11:0] adc = 12'h0;
always @(posedge clk_ad) adc <= adc + 12'd3;

// ---------------------------------------------------------------------------
// DUT wiring (mirrors hermeslite_core.v)

logic [ 1:0] udp_tx_request;
logic [15:0] udp_tx_length;
logic [ 7:0] udp_tx_data;
wire         udp_tx_enable, udp0_tx_enable, udp_tx_busy;
wire  [ 1:0] pkt_req;
wire  [ 7:0] pkt_data;
wire  [10:0] pkt_len;
logic        pkt_en;
logic        raw_mode;

rawstream #(.FIFO_AW(14)) dut (
  .clk_ad        (clk_ad),
  .adc_data      (adc),
  .clk           (clk),
  .run           (run),
  .cmd_addr      (cmd_addr),
  .cmd_data      (cmd_data),
  .cmd_rqst      (cmd_rqst),
  .raw_mode      (raw_mode),
  .pkt_tx_request(pkt_req),
  .pkt_tx_length ({5'h0, pkt_len}),
  .pkt_tx_data   (pkt_data),
  .pkt_tx_enable (pkt_en),
  .udp_tx_request(udp_tx_request),
  .udp_tx_length (udp_tx_length),
  .udp_tx_data   (udp_tx_data),
  .udp_tx_enable (udp_tx_enable),
  .udp0_tx_enable(udp0_tx_enable),
  .udp_tx_busy   (udp_tx_busy | stall),
  .dup_on        (1'b0),
  .dup_status    (160'd0),
  .tx_status     (8'h41)
);

// Packer model. The real usopenhpsdr1.v and network.v use constructs iverilog
// rejects (names used before declaration, procedural assignment to plain outputs),
// so the openHPSDR packer's discovery-reply handshake (DISCOVER1/DISCOVER2 in
// usopenhpsdr1.v) and the send arbitration of network.v (lines "tx_ready/tx_start"
// plus the two raw-stream status outputs) are copied here. udp_send, ip_send,
// mac_send, crc32 and rgmii_send are the real modules.

localparam P_IDLE = 2'd0, P_REQ = 2'd1, P_SEND = 2'd2;
logic [1:0] p_state = P_IDLE;
logic [7:0] p_byte  = 8'h0;
logic [5:0] p_cnt   = 6'h0;
logic       p_pending = 1'b0;
logic [10:0] p_len  = 11'd0;
always @(posedge clk) begin
  if (discover_rqst) p_pending <= 1'b1;
  case (p_state)
    P_IDLE: if (p_pending) begin p_len <= 11'h3c; p_state <= P_REQ; end
    P_REQ: begin
      p_byte <= 8'hef;
      if (pkt_en) begin p_state <= P_SEND; p_cnt <= 6'h3a; p_pending <= 1'b0; end
    end
    P_SEND: begin
      p_cnt <= p_cnt - 6'd1;
      case (p_cnt)
        6'h3a: p_byte <= 8'hfe;
        6'h39: p_byte <= run ? 8'h03 : 8'h02;
        6'h38: p_byte <= 8'h00;
        6'h37: p_byte <= 8'h1c;
        6'h36: p_byte <= 8'hc0;
        6'h35: p_byte <= 8'ha2;
        6'h34: p_byte <= 8'h13;
        6'h33: p_byte <= 8'hdd;
        6'h00: begin p_byte <= 8'h00; p_state <= P_IDLE; end
        default: p_byte <= p_cnt[5:0] ^ 8'h55;
      endcase
    end
  endcase
end
assign pkt_req  = (p_state == P_REQ) ? 2'b10 : 2'b00;
assign pkt_data = p_byte;
assign pkt_len  = p_len;

// network.v send path
logic tx_ready = 1'b0, tx_start = 1'b0;
logic [2:0] tx_protocol = 3'd0;
localparam PT_UDP0 = 3'd4;
wire rgmii_tx_active;
assign udp_tx_enable  = tx_start && (tx_protocol == PT_UDP0);
assign udp0_tx_enable = tx_start && (tx_protocol == PT_UDP0);
assign udp_tx_busy    = tx_ready | tx_start | rgmii_tx_active;
always @(posedge clk)
  if (rgmii_tx_active) begin tx_ready <= 1'b0; tx_start <= 1'b0; end
  else if (tx_ready) tx_start <= 1'b1;
  else if (udp_tx_request == 2'b10) begin tx_protocol <= PT_UDP0; tx_ready <= 1'b1; end

wire        udp_tx_active;
wire [ 7:0] udp_data;
wire [15:0] udp_length;
wire [ 7:0] ip_tx_data;
wire        ip_tx_active;
wire [ 7:0] mac_tx_data;
wire        mac_tx_active;
logic [7:0] rgmii_tx_data_in_pipe;
logic       rgmii_tx_enable_pipe = 1'b0;

udp_send udp_send_inst (.reset(1'b0), .clock(clk), .tx_enable(udp_tx_enable), .data_in(udp_tx_data),
  .length_in(udp_tx_length), .local_port(16'd1024), .destination_port(16'd50000),
  .active(udp_tx_active), .data_out(udp_data), .length_out(udp_length), .port_ID(8'h00));
ip_send ip_send_inst (.data_in(udp_data), .tx_enable(udp_tx_active), .is_icmp(1'b0), .length(udp_length),
  .destination_ip(32'ha9fe0101), .data_out(ip_tx_data), .active(ip_tx_active), .clock(clk), .reset(1'b0),
  .local_ip(32'ha9fe13dd));
mac_send mac_send_inst (.data_in(ip_tx_data), .tx_enable(ip_tx_active), .destination_mac(48'h0a1b2c3d4e5f),
  .data_out(mac_tx_data), .active(mac_tx_active), .clock(clk), .local_mac(48'h001cc0a213dd), .reset(1'b0));
always @(posedge clk) begin
  rgmii_tx_data_in_pipe <= mac_tx_data;
  rgmii_tx_enable_pipe  <= mac_tx_active;
end
rgmii_send #(.SIM(1)) rgmii_send_inst (.data(rgmii_tx_data_in_pipe), .tx_enable(rgmii_tx_enable_pipe),
  .active(rgmii_tx_active), .clock(clk), .PHY_TX(), .PHY_TX_EN());

initial begin
  udp_send_inst.byte_no = 16'd0; udp_send_inst.sending = 1'b0;
  ip_send_inst.byte_no = 5'd0;   ip_send_inst.sending = 1'b0;
end

// ---------------------------------------------------------------------------
// Helpers

integer errors = 0;
integer debug = 0;
`define CHECK(cond, msg) if (!(cond)) begin errors = errors + 1; if (errors < 40) $display("ERROR t=%0t: %s", $time, msg); end

task automatic send_cmd(input [5:0] addr, input [31:0] data);
  @(posedge clk); cmd_addr <= addr; cmd_data <= data; cmd_rqst <= 1'b1;
  @(posedge clk); cmd_rqst <= 1'b0;
endtask

task automatic wait_cycles(input integer n);
  repeat (n) @(posedge clk);
endtask

function automatic [31:0] crc32_eth(input byte unsigned b[], input integer len);
  reg [31:0] c; integer i, k;
  c = 32'hffffffff;
  for (i = 0; i < len; i = i + 1) begin
    c = c ^ b[i];
    for (k = 0; k < 8; k = k + 1) c = c[0] ? ((c >> 1) ^ 32'hedb88320) : (c >> 1);
  end
  return ~c;
endfunction

// ---------------------------------------------------------------------------
// Frame capture at the input of rgmii_send and checking

byte unsigned fr[$];
integer frame_idle = 0;          // enable-low cycles before the current frame

// Stream model
integer raw_frames = 0, pkt_frames = 0, other_frames = 0;
integer raw_frames_quiet = 0, frames_ovf = 0, frames_gap = 0, frames_first = 0, frames_clip = 0;
logic   have_prev = 1'b0;
longint exp_idx = 0;
longint exp_seq = 0;
integer max_ovf_cnt = 0, max_hw = 0;
integer expect_n = 968;
integer expect_pattern = 1;
integer adc_offset = -1;
integer last_n = 0;
integer pattern_errors = 0;
integer gap_idle_raw_sum = 0, gap_idle_raw_cnt = 0, gap_idle_min = 1000000, gap_idle_max = 0;
integer prev_was_raw = 0;
integer quiet_block_samples = 0, quiet_block_last = 0;
longint quiet_block_start = -1;

task automatic check_frame(input integer idle_before);
  integer len, ip_len, udp_len, pay_len, i, n, j, flags;
  byte unsigned b[];
  reg [31:0] crc, fcs, sum;
  longint seq, idx, a, s;
  integer ovf, hw;
  reg [7:0] b0, b1, b2;
  len = fr.size();
  b = new[len];
  for (i = 0; i < len; i = i + 1) b[i] = fr[i];

  // Ethernet
  `CHECK(len >= 64, $sformatf("short frame %0d", len))
  if (debug && raw_frames+pkt_frames < 1) begin for (i=0;i<len;i=i+1) $write("%h ", b[i]); $display(""); end
  crc = crc32_eth(b, len - 4);
  fcs = {b[len-1], b[len-2], b[len-3], b[len-4]};
  `CHECK(crc == fcs, $sformatf("CRC mismatch len=%0d calc=%h frame=%h", len, crc, fcs))
  `CHECK({b[12], b[13]} == 16'h0800, "ethertype")
  `CHECK({b[0],b[1],b[2],b[3],b[4],b[5]} == 48'h0a1b2c3d4e5f, "destination MAC")

  // IP
  `CHECK(b[14] == 8'h45, "IP version/IHL")
  ip_len = {b[16], b[17]};
  sum = 0;
  for (i = 14; i < 34; i = i + 2) sum = sum + {b[i], b[i+1]};
  sum = (sum & 32'hffff) + (sum >> 16);
  sum = (sum & 32'hffff) + (sum >> 16);
  `CHECK(sum == 32'hffff, $sformatf("IP header checksum wrong (sum=%h)", sum))
  `CHECK(b[23] == 8'd17, "IP protocol UDP")

  // UDP
  udp_len = {b[38], b[39]};
  `CHECK(ip_len == udp_len + 20, $sformatf("IP length %0d != UDP length %0d + 20", ip_len, udp_len))
  pay_len = udp_len - 8;
  `CHECK(len == 14 + ip_len + 4 || (ip_len < 46 && len == 64), $sformatf("frame length %0d vs IP length %0d", len, ip_len))
  `CHECK({b[36], b[37]} == 16'd50000, "UDP destination port")

  if (pay_len >= 20 && b[42] == 8'ha5) begin
    // Raw frame
    raw_frames = raw_frames + 1;
    if (debug) $display("raw frame at %0t len %0d", $time, len);
    `CHECK(b[43] == 8'h01, "version")
    `CHECK(b[45] == 8'h41, "transmit-safety status byte")
    flags = b[44];
    seq = {b[46], b[47], b[48], b[49]};
    idx = {b[50], b[51], b[52], b[53], b[54], b[55]};
    n   = {b[56], b[57]};
    ovf = {b[58], b[59]};
    hw  = {b[60], b[61]};
    `CHECK(pay_len == 20 + 3 * n / 2, $sformatf("payload %0d bytes for %0d samples", pay_len, n))
    `CHECK(n == expect_n, $sformatf("samples per frame %0d, expected %0d", n, expect_n))
    `CHECK(flags[0] == expect_pattern, "pattern flag")
    if (flags[1]) frames_ovf = frames_ovf + 1;
    if (flags[2]) frames_clip = frames_clip + 1;
    if (flags[3]) raw_frames_quiet = raw_frames_quiet + 1;
    if (flags[5]) frames_gap = frames_gap + 1;
    if (ovf > max_ovf_cnt) max_ovf_cnt = ovf;
    if (hw > max_hw) max_hw = hw;
    `CHECK(hw <= 16384, "high water above FIFO depth")

    if (flags[4]) begin
      frames_first = frames_first + 1;
      `CHECK(seq == 0, "first frame sequence number not 0")
      `CHECK(flags[1] == 0 && ovf == 0, "overflow flag set on first frame")
      exp_seq = 0;
      have_prev = 1'b0;
      adc_offset = -1;
    end
    `CHECK(seq == exp_seq, $sformatf("sequence %0d expected %0d", seq, exp_seq))
    if (have_prev && !flags[5]) begin
      `CHECK(idx == exp_idx, $sformatf("sample index %0d expected %0d (seq %0d)", idx, exp_idx, seq))
    end
    if (have_prev && flags[5]) begin
      `CHECK(idx > exp_idx, $sformatf("gap frame index %0d not after %0d", idx, exp_idx))
    end

    // Quiet-capture blocks: count contiguous samples per block
    if (flags[3]) begin
      if (quiet_block_start < 0 || flags[5] || flags[4]) begin
        if (quiet_block_start >= 0) quiet_block_last = quiet_block_samples;
        quiet_block_start = idx; quiet_block_samples = 0;
      end
      quiet_block_samples = quiet_block_samples + n;
    end

    // Samples
    for (j = 0; j < n; j = j + 2) begin
      i = 62 + 3 * (j / 2);
      b0 = b[i]; b1 = b[i+1]; b2 = b[i+2];
      a = {b0, b1[7:4]};
      s = {b1[3:0], b2};
      if (flags[0]) begin
        if (a != ((idx + j) & 12'hfff) || s != ((idx + j + 1) & 12'hfff)) begin
          pattern_errors = pattern_errors + 1;
          `CHECK(0, $sformatf("pattern sample %0d: got %h %h expected %h %h", j, a, s, (idx+j)&12'hfff, (idx+j+1)&12'hfff))
        end
      end else begin
        if (adc_offset < 0) adc_offset = (a - 3 * (idx + j)) & 12'hfff;
        if (((a - 3 * (idx + j)) & 12'hfff) != adc_offset || ((s - 3 * (idx + j + 1)) & 12'hfff) != adc_offset) begin
          pattern_errors = pattern_errors + 1;
          `CHECK(0, $sformatf("ADC ramp sample %0d wrong: %h %h", j, a, s))
        end
      end
    end

    if (prev_was_raw) begin
      gap_idle_raw_sum = gap_idle_raw_sum + idle_before;
      gap_idle_raw_cnt = gap_idle_raw_cnt + 1;
      if (idle_before < gap_idle_min) gap_idle_min = idle_before;
      if (idle_before > gap_idle_max) gap_idle_max = idle_before;
    end
    prev_was_raw = 1;

    exp_seq = seq + 1;
    exp_idx = idx + n;
    have_prev = 1'b1;
    last_n = n;
  end else if (pay_len == 60 && b[42] == 8'hef && b[43] == 8'hfe && (b[44] == 8'h02 || b[44] == 8'h03)) begin
    pkt_frames = pkt_frames + 1;
    if (debug) $display("reply %0d at %0t", pkt_frames, $time);
    `CHECK({b[45],b[46],b[47],b[48],b[49],b[50]} == 48'h001cc0a213dd, "discovery reply MAC")
    prev_was_raw = 0;
  end else begin
    other_frames = other_frames + 1;
    `CHECK(0, $sformatf("unexpected frame, UDP payload %0d bytes, first byte %h", pay_len, b[42]))
    prev_was_raw = 0;
  end
endtask

logic en_d = 1'b0;
always @(posedge clk) begin
  en_d <= rgmii_tx_enable_pipe;
  if (rgmii_tx_enable_pipe) begin
    fr.push_back(rgmii_tx_data_in_pipe);
  end else begin
    if (en_d) begin
      check_frame(frame_idle);
      fr.delete();
      frame_idle = 0;
    end
    frame_idle = frame_idle + 1;
  end
end

// ---------------------------------------------------------------------------
// Discovery requests every ~2 ms of packer time while enabled

integer disc_sent = 0;
logic   disc_enable = 1'b1;
always begin
  wait_cycles(30011);   // longer than two maximum-size raw frames, so requests never merge
  if (disc_enable && !stall) begin
    @(posedge clk) discover_rqst <= 1'b1;
    @(posedge clk) discover_rqst <= 1'b0;
    disc_sent = disc_sent + 1;
    if (debug) $display("request %0d at %0t", disc_sent, $time);
  end
end

// ---------------------------------------------------------------------------
// Test sequence

task automatic reset_stats();
  raw_frames = 0; frames_ovf = 0; frames_gap = 0; frames_first = 0; raw_frames_quiet = 0; frames_clip = 0;
  max_ovf_cnt = 0; max_hw = 0; pattern_errors = 0;
  gap_idle_raw_sum = 0; gap_idle_raw_cnt = 0; gap_idle_min = 1000000; gap_idle_max = 0;
  quiet_block_start = -1; quiet_block_samples = 0; quiet_block_last = 0;
endtask

task automatic stop_stream();
  run <= 1'b0;
  wait_cycles(30000);       // longest frame plus FIFO drain
endtask

task automatic run_case(input string name, input integer n_req, input integer n_exp, input integer pattern,
                        input integer cycles, input integer min_frames);
  integer e0;
  e0 = errors;
  reset_stats();
  expect_n = n_exp;
  expect_pattern = pattern;
  send_cmd(6'h30, {n_req[15:0], 13'd0, 1'b0, pattern[0], 1'b1});
  wait_cycles(10);
  run <= 1'b1;
  wait_cycles(cycles);
  stop_stream();
  // samples arriving in 'cycles' 8 ns cycles at 76.8 MHz, minus start-up latency
  min_frames = (cycles * 0.6144) / n_exp - 2;
  `CHECK(raw_frames >= min_frames, $sformatf("%s: only %0d raw frames, expected at least %0d", name, raw_frames, min_frames))
  `CHECK(frames_first == 1, $sformatf("%s: %0d first-frame flags", name, frames_first))
  `CHECK(frames_ovf == 0 && frames_gap == 0 && max_ovf_cnt == 0, $sformatf("%s: unexpected overflow", name))
  $display("%-28s N=%4d frames=%4d idle between raw frames min/avg/max=%0d/%0d/%0d cycles, FIFO high water=%0d, errors=%0d",
    name, n_exp, raw_frames, gap_idle_min, (gap_idle_raw_cnt > 0) ? gap_idle_raw_sum / gap_idle_raw_cnt : 0,
    gap_idle_max, max_hw, errors - e0);
endtask

integer e0;

initial begin
  wait_cycles(200);

  // 1. Raw mode off: only discovery replies, no raw frames
  reset_stats();
  run <= 1'b1;
  wait_cycles(65000);
  run <= 1'b0;
  wait_cycles(1000);
  `CHECK(raw_frames == 0, "raw frames while raw mode is off")
  `CHECK(pkt_frames >= 2, "no discovery replies with raw mode off")
  $display("%-28s raw frames=%0d discovery replies=%0d", "raw mode off", raw_frames, pkt_frames);

  // 2. Frame sizes, test pattern
  run_case("pattern 1500 MTU",    968,  968, 1, 60000, 40);
  run_case("pattern 4088 NIC",   2684, 2684, 1, 60000, 12);
  run_case("pattern 9014 jumbo", 5968, 5968, 1, 90000, 8);
  run_case("pattern odd N 1001",  1001, 1000, 1, 30000, 10);
  run_case("pattern N 0 default",    0,  968, 1, 30000, 10);
  run_case("pattern N clamp",    9000, 7680, 1, 90000, 6);
  // 3. ADC data path
  run_case("ADC ramp 9014 jumbo",  5968, 5968, 0, 90000, 8);
  run_case("ADC ramp 1500 MTU",     968,  968, 0, 60000, 40);

  // 4. Overflow when the consumer stalls: the network is held busy for 40,000 cycles (320 ms)
  e0 = errors;
  reset_stats();
  expect_n = 5968; expect_pattern = 1;
  send_cmd(6'h30, {16'd5968, 13'd0, 3'b011});
  wait_cycles(10);
  run <= 1'b1;
  wait_cycles(30000);
  stall <= 1'b1;
  wait_cycles(40000);
  stall <= 1'b0;
  wait_cycles(80000);
  stop_stream();
  `CHECK(frames_ovf > 0, "overflow flag not set after stall")
  `CHECK(frames_gap >= 1, "no gap flag after overflow")
  `CHECK(max_ovf_cnt == 1, $sformatf("overflow count %0d, expected 1", max_ovf_cnt))
  `CHECK(pattern_errors == 0, "pattern errors after overflow")
  $display("%-28s frames=%0d overflow-flag frames=%0d gap frames=%0d overflow count=%0d high water=%0d errors=%0d",
    "stall -> overflow", raw_frames, frames_ovf, frames_gap, max_ovf_cnt, max_hw, errors - e0);

  // 5. Overflow because the wire cannot keep up (N=100 needs >1 Gbit/s)
  e0 = errors;
  reset_stats();
  expect_n = 100; expect_pattern = 1;
  send_cmd(6'h30, {16'd100, 13'd0, 3'b011});
  wait_cycles(10);
  run <= 1'b1;
  wait_cycles(200000);
  stop_stream();
  `CHECK(frames_ovf > 0 && max_ovf_cnt >= 1, "no overflow at N=100")
  `CHECK(pattern_errors == 0, "pattern errors at N=100")
  $display("%-28s frames=%0d overflow-flag frames=%0d gap frames=%0d overflow count=%0d errors=%0d",
    "N=100 over wire rate", raw_frames, frames_ovf, frames_gap, max_ovf_cnt, errors - e0);

  // 6. Quiet-capture mode, N=4096: one block = the whole FIFO
  e0 = errors;
  reset_stats();
  expect_n = 4096; expect_pattern = 1;
  send_cmd(6'h30, {16'd4096, 13'd0, 3'b111});
  wait_cycles(10);
  run <= 1'b1;
  wait_cycles(150000);
  stop_stream();
  if (quiet_block_start >= 0 && quiet_block_last == 0) quiet_block_last = quiet_block_samples;
  `CHECK(raw_frames_quiet == raw_frames && raw_frames >= 8, $sformatf("quiet: %0d of %0d frames flagged", raw_frames_quiet, raw_frames))
  `CHECK(max_ovf_cnt == 0, "quiet mode counted overflow events")
  `CHECK(quiet_block_last >= 12288, $sformatf("quiet block only %0d samples", quiet_block_last))
  $display("%-28s frames=%0d quiet-flag frames=%0d blocks(gaps)=%0d samples per block=%0d errors=%0d",
    "quiet capture N=4096", raw_frames, raw_frames_quiet, frames_gap, quiet_block_last, errors - e0);

  // 7. Stop mid-stream and restart: sequence restarts at 0
  e0 = errors;
  run_case("restart after stop",  968, 968, 1, 40000, 20);

  // Discovery replies must all have been sent (none lost by the arbiter)
  disc_enable = 1'b0;
  wait_cycles(40000);
  $display("discovery requests=%0d replies=%0d other frames=%0d", disc_sent, pkt_frames, other_frames);
  `CHECK(pkt_frames == disc_sent, "discovery replies lost")

  if (errors == 0) $display("PASS");
  else $display("FAIL: %0d errors", errors);
  $finish;
end

endmodule
