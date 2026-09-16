// SPDX-License-Identifier: GPL-2.0-or-later
// Copyright 2026 Franz Schöning, https://www.schoning.com
//
// Testbench for the duplex raw stream: rtl/txsink.v + rtl/rawstream.v (DUPLEX=1)
//
// PC -> HL2: a PC model builds complete Ethernet frames (preamble, MAC, IPv4, UDP, CRC)
// and drives them as RGMII nibbles on both clock edges into the REAL receive path:
// rgmii_recv (with the Quartus altddio_in model), mac_recv, ip_recv and udp_recv with
// the jumbo length counters (LW=16), and dsopenhpsdr1. Register writes (port 1025),
// start/stop (port 1024), discovery requests and TX frames (port 1026) all arrive that
// way, so the command decode and the port filter are exercised too.
//
// HL2 -> PC: the raw frames leaving the real udp_send/ip_send/mac_send are captured and
// checked (version 2, 40-byte header, pattern samples); the TX status fields in their
// headers are what the checks below use, exactly as the PC does.
//
// The network.v glue (receive wiring and the send arbitration) and the openHPSDR
// discovery-reply packer are copied into this file because iverilog rejects network.v
// and usopenhpsdr1.v (see tb_rawstream.sv).
//
// Run: ./run.sh

`timescale 1ps/1ps

module tb_duplex;

localparam TX_AW    = 14;
localparam RX_AW    = 13;
localparam T_AD     = 13020;          // ps, AD9866 clock period (76.805 MHz)
localparam RX_N     = 5954;           // radio -> PC samples per frame (9,000 IP MTU with 40-byte header)
localparam HALF     = 1 << (TX_AW-1);

// ---------------------------------------------------------------------------
// Clocks: HL2 125 MHz TX, PHY receive clock (PC's clock, +50 ppm), AD9866

logic clk = 1'b0;
logic clk_rx = 1'b0;
logic clk_ad = 1'b0;
always #4000 clk = ~clk;
initial begin #1111; forever #4000.2 clk_rx = ~clk_rx; end
initial begin #1733; forever #(T_AD/2) clk_ad = ~clk_ad; end

// ---------------------------------------------------------------------------
// RGMII from the PC model

logic [3:0] phy_rx = 4'h0;
logic       phy_dv = 1'b0;

// ---------------------------------------------------------------------------
// Receive path (network.v wiring)

localparam [47:0] HL2_MAC = 48'h001cc0a213dd;
localparam [31:0] HL2_IP  = 32'ha9fe13dd;
localparam [47:0] PC_MAC  = 48'h0a1b2c3d4e5f;
localparam [31:0] PC_IP   = 32'ha9fe0101;

wire        rgmii_rx_active_pipe;
wire [7:0]  rx_data_pipe;
logic       rgmii_rx_active = 1'b0;
logic [7:0] rx_data = 8'h00;
always @(posedge clk_rx) begin
  rx_data         <= rx_data_pipe;
  rgmii_rx_active <= rgmii_rx_active_pipe;
end

wire        mac_rx_active, rx_is_arp, broadcast, ip_rx_active, rx_is_icmp, to_ip_is_me;
wire [47:0] remote_mac;
wire        remote_mac_valid;
wire [31:0] remote_ip, to_ip;
wire        remote_ip_valid;
wire        udp_rx_active, dhcp_rx_active;
wire [15:0] to_port;

rgmii_recv #(.SIM(0)) rgmii_recv_inst (.active(rgmii_rx_active_pipe), .reset(1'b0), .clock(clk_rx),
  .speed_1gb(1'b1), .data(rx_data_pipe), .PHY_RX(phy_rx), .PHY_DV(phy_dv));
mac_recv mac_recv_inst (.rx_enable(rgmii_rx_active), .active(mac_rx_active), .is_arp(rx_is_arp),
  .remote_mac(remote_mac), .remote_mac_valid(remote_mac_valid), .clock(clk_rx), .data(rx_data),
  .local_mac(HL2_MAC), .broadcast(broadcast));
ip_recv #(.LW(16)) ip_recv_inst (.local_ip(HL2_IP), .active(ip_rx_active), .is_icmp(rx_is_icmp),
  .remote_ip(remote_ip), .remote_ip_valid(remote_ip_valid), .clock(clk_rx),
  .rx_enable(mac_rx_active && !rx_is_arp), .broadcast(broadcast), .data(rx_data), .to_ip(to_ip),
  .to_ip_is_me(to_ip_is_me));
udp_recv #(.LW(16)) udp_recv_inst (.clock(clk_rx), .run(1'b0), .rx_enable(ip_rx_active && !rx_is_icmp),
  .data(rx_data), .to_ip(to_ip), .local_ip(HL2_IP), .broadcast(broadcast), .remote_mac(remote_mac),
  .remote_ip(remote_ip), .active(udp_rx_active), .dhcp_active(dhcp_rx_active), .to_port(to_port),
  .udp_destination_ip(), .udp_destination_mac(), .udp_destination_port(), .udp_destination_valid());

// openHPSDR downstream decoder
wire        run, wide_spectrum, discover_port, discover_cnt;
wire [ 5:0] ds_cmd_addr;
wire [31:0] ds_cmd_data;
wire        ds_cmd_cnt;

dsopenhpsdr1 dsopenhpsdr1_i (
  .clk(clk_rx), .eth_port(to_port), .eth_broadcast(broadcast), .eth_valid(udp_rx_active),
  .eth_data(rx_data), .eth_unreachable(1'b0),
  .discover_port(discover_port), .discover_cnt(discover_cnt), .run(run), .wide_spectrum(wide_spectrum),
  .watchdog_up(1'b0), .msec_pulse(1'b0),
  .ds_cmd_addr(ds_cmd_addr), .ds_cmd_data(ds_cmd_data), .ds_cmd_cnt(ds_cmd_cnt), .ds_cmd_resprqst(),
  .ds_cmd_is_alt(), .ds_cmd_mask(), .ds_cmd_ptt(),
  .dseth_tdata(), .dsethiq_tvalid(), .dsethiq_tlast(), .dsethiq_tuser(), .dsethlr_tvalid(), .dsethlr_tlast(),
  .dsethasmi_tvalid(), .dsethasmi_tlast(), .asmi_cnt(), .dsethasmi_erase(), .dsethasmi_erase_ack(1'b1),
  .ds_pkt_cnt(), .cmd_addr(ds_cmd_addr), .cmd_data(ds_cmd_data), .cmd_rqst(1'b0));

// hermeslite_core.v: clock_ethtxint side
wire run_sync, cmd_rqst, discover_rqst;
sync       sync_run  (.clock(clk), .sig_in(run),          .sig_out(run_sync));
sync_pulse sync_cmd  (.clock(clk), .sig_in(ds_cmd_cnt),   .sig_out(cmd_rqst));
sync_pulse sync_disc (.clock(clk), .sig_in(discover_cnt), .sig_out(discover_rqst));

// ---------------------------------------------------------------------------
// DUTs

logic [ 1:0] udp_tx_request;
logic [15:0] udp_tx_length;
logic [ 7:0] udp_tx_data;
wire         udp_tx_enable, udp0_tx_enable, udp_tx_busy;
wire  [ 1:0] pkt_req;
wire  [ 7:0] pkt_data;
wire  [10:0] pkt_len;
logic        pkt_en;
logic        raw_mode;
wire         dup_on;
wire [159:0] dup_status;

// ADC ramp (the raw stream runs in pattern mode here, so this is unused)
logic [11:0] adc = 12'h0;
always @(posedge clk_ad) adc <= adc + 12'd3;

txsink #(.FIFO_AW(TX_AW)) txsink_i (
  .clk_rx(clk_rx), .eth_port(to_port), .eth_broadcast(broadcast), .eth_valid(udp_rx_active),
  .eth_data(rx_data), .clk_ad(clk_ad), .clk(clk), .raw_mode(raw_mode), .run(run_sync),
  .cmd_addr(ds_cmd_addr), .cmd_data(ds_cmd_data), .cmd_rqst(cmd_rqst), .dup_on(dup_on), .status(dup_status));

rawstream #(.FIFO_AW(RX_AW), .MAX_N_OVERRIDE(5968), .DUPLEX(1)) rawstream_i (
  .clk_ad(clk_ad), .adc_data(adc), .clk(clk), .run(run_sync),
  .cmd_addr(ds_cmd_addr), .cmd_data(ds_cmd_data), .cmd_rqst(cmd_rqst), .raw_mode(raw_mode),
  .pkt_tx_request(pkt_req), .pkt_tx_length({5'h0, pkt_len}), .pkt_tx_data(pkt_data), .pkt_tx_enable(pkt_en),
  .udp_tx_request(udp_tx_request), .udp_tx_length(udp_tx_length), .udp_tx_data(udp_tx_data),
  .udp_tx_enable(udp_tx_enable), .udp0_tx_enable(udp0_tx_enable), .udp_tx_busy(udp_tx_busy),
  .dup_on(dup_on), .dup_status(dup_status), .tx_status(8'h41));

// Discovery reply packer model (as tb_rawstream.sv)
localparam P_IDLE = 2'd0, P_REQ = 2'd1, P_SEND = 2'd2;
logic [1:0] p_state = P_IDLE;
logic [7:0] p_byte  = 8'h0;
logic [5:0] p_cnt   = 6'h0;
logic       p_pending = 1'b0;
always @(posedge clk) begin
  if (discover_rqst) p_pending <= 1'b1;
  case (p_state)
    P_IDLE: if (p_pending) p_state <= P_REQ;
    P_REQ: begin
      p_byte <= 8'hef;
      if (pkt_en) begin p_state <= P_SEND; p_cnt <= 6'h3a; p_pending <= 1'b0; end
    end
    P_SEND: begin
      p_cnt <= p_cnt - 6'd1;
      case (p_cnt)
        6'h3a: p_byte <= 8'hfe;
        6'h39: p_byte <= run_sync ? 8'h03 : 8'h02;
        6'h00: begin p_byte <= 8'h00; p_state <= P_IDLE; end
        default: p_byte <= p_cnt[5:0] ^ 8'h55;
      endcase
    end
  endcase
end
assign pkt_req  = (p_state == P_REQ) ? 2'b10 : 2'b00;
assign pkt_data = p_byte;
assign pkt_len  = 11'h3c;

// Send path (network.v)
logic tx_ready = 1'b0, tx_start = 1'b0;
wire rgmii_tx_active;
assign udp_tx_enable  = tx_start;
assign udp0_tx_enable = tx_start;
assign udp_tx_busy    = tx_ready | tx_start | rgmii_tx_active;
always @(posedge clk)
  if (rgmii_tx_active) begin tx_ready <= 1'b0; tx_start <= 1'b0; end
  else if (tx_ready) tx_start <= 1'b1;
  else if (udp_tx_request == 2'b10) tx_ready <= 1'b1;

wire        udp_tx_active;
wire [ 7:0] udp_data;
wire [15:0] udp_length;
wire [ 7:0] ip_tx_data;
wire        ip_tx_active;
wire [ 7:0] mac_tx_data;
wire        mac_tx_active;
logic [7:0] tx_pipe_d;
logic       tx_pipe_en = 1'b0;

udp_send udp_send_inst (.reset(1'b0), .clock(clk), .tx_enable(udp_tx_enable), .data_in(udp_tx_data),
  .length_in(udp_tx_length), .local_port(16'd1024), .destination_port(16'd50000),
  .active(udp_tx_active), .data_out(udp_data), .length_out(udp_length), .port_ID(8'h00));
ip_send ip_send_inst (.data_in(udp_data), .tx_enable(udp_tx_active), .is_icmp(1'b0), .length(udp_length),
  .destination_ip(PC_IP), .data_out(ip_tx_data), .active(ip_tx_active), .clock(clk), .reset(1'b0),
  .local_ip(HL2_IP));
mac_send mac_send_inst (.data_in(ip_tx_data), .tx_enable(ip_tx_active), .destination_mac(PC_MAC),
  .data_out(mac_tx_data), .active(mac_tx_active), .clock(clk), .local_mac(HL2_MAC), .reset(1'b0));
always @(posedge clk) begin
  tx_pipe_d  <= mac_tx_data;
  tx_pipe_en <= mac_tx_active;
end
rgmii_send #(.SIM(1)) rgmii_send_inst (.data(tx_pipe_d), .tx_enable(tx_pipe_en),
  .active(rgmii_tx_active), .clock(clk), .PHY_TX(), .PHY_TX_EN());

initial begin
  udp_send_inst.byte_no = 16'd0; udp_send_inst.sending = 1'b0;
  ip_send_inst.byte_no = 5'd0;   ip_send_inst.sending = 1'b0;
end

// ---------------------------------------------------------------------------
// Helpers

integer errors = 0;
`define CHECK(cond, msg) if (!(cond)) begin errors = errors + 1; if (errors < 40) $display("ERROR t=%0t: %s", $time, msg); end

function automatic [31:0] crc32_eth(input byte unsigned b[], input integer from, input integer len);
  reg [31:0] c; integer i, k;
  c = 32'hffffffff;
  for (i = from; i < from + len; i = i + 1) begin
    c = c ^ b[i];
    for (k = 0; k < 8; k = k + 1) c = c[0] ? ((c >> 1) ^ 32'hedb88320) : (c >> 1);
  end
  return ~c;
endfunction

// ---------------------------------------------------------------------------
// PC model: frame queue and RGMII driver

byte unsigned txq[$];          // bytes of queued frames, frames separated by lengths below
integer       txq_len[$];

// Build one UDP/IPv4/Ethernet frame (with preamble and FCS) from a payload and queue it
task automatic queue_udp(input [15:0] dport, input byte unsigned pay[], input integer plen,
                         input integer to_broadcast);
  byte unsigned f[];
  integer n, i, ip_len, udp_len;
  reg [31:0] sum, crc;
  ip_len  = 20 + 8 + plen;
  udp_len = 8 + plen;
  n = 8 + 14 + ip_len + 4;
  f = new[n];
  for (i = 0; i < 7; i = i + 1) f[i] = 8'h55;
  f[7] = 8'hd5;
  for (i = 0; i < 6; i = i + 1) f[8+i]  = to_broadcast ? 8'hff : HL2_MAC[47-8*i -: 8];
  for (i = 0; i < 6; i = i + 1) f[14+i] = PC_MAC[47-8*i -: 8];
  f[20] = 8'h08; f[21] = 8'h00;
  // IPv4 header at 22
  f[22] = 8'h45; f[23] = 8'h00; f[24] = ip_len[15:8]; f[25] = ip_len[7:0];
  f[26] = 8'h12; f[27] = 8'h34; f[28] = 8'h40; f[29] = 8'h00; f[30] = 8'h40; f[31] = 8'h11;
  f[32] = 8'h00; f[33] = 8'h00;
  for (i = 0; i < 4; i = i + 1) f[34+i] = PC_IP[31-8*i -: 8];
  for (i = 0; i < 4; i = i + 1) f[38+i] = to_broadcast ? 8'hff : HL2_IP[31-8*i -: 8];
  sum = 0;
  for (i = 22; i < 42; i = i + 2) sum = sum + {f[i], f[i+1]};
  sum = (sum & 32'hffff) + (sum >> 16);
  sum = (sum & 32'hffff) + (sum >> 16);
  f[32] = ~sum[15:8]; f[33] = ~sum[7:0];
  // UDP header at 42
  f[42] = 8'hc3; f[43] = 8'h50;               // source port 50000
  f[44] = dport[15:8]; f[45] = dport[7:0];
  f[46] = udp_len[15:8]; f[47] = udp_len[7:0];
  f[48] = 8'h00; f[49] = 8'h00;               // checksum not used
  for (i = 0; i < plen; i = i + 1) f[50+i] = pay[i];
  crc = crc32_eth(f, 8, 14 + ip_len);
  f[n-4] = crc[7:0]; f[n-3] = crc[15:8]; f[n-2] = crc[23:16]; f[n-1] = crc[31:24];
  for (i = 0; i < n; i = i + 1) txq.push_back(f[i]);
  txq_len.push_back(n);
endtask

integer frames_on_wire = 0;
logic   wire_busy = 1'b0;

// RGMII driver: low nibble + DV valid at the rising edge, high nibble at the falling edge
// (the altddio_in model with invert_input_clocks=ON samples exactly that way).
initial begin : rgmii_driver
  integer n, i, idle;
  byte unsigned b;
  idle = 12;
  forever begin
    if (txq_len.size() > 0 && idle >= 12) begin
      n = txq_len.pop_front();
      wire_busy = 1'b1;
      for (i = 0; i < n; i = i + 1) begin
        b = txq.pop_front();
        @(negedge clk_rx); #2000; phy_rx = b[3:0]; phy_dv = 1'b1;
        @(posedge clk_rx); #2000; phy_rx = b[7:4];
      end
      @(negedge clk_rx); #2000; phy_dv = 1'b0; phy_rx = 4'h0;
      @(posedge clk_rx);
      idle = 1;
      frames_on_wire = frames_on_wire + 1;
      wire_busy = 1'b0;
    end else begin
      @(negedge clk_rx); #2000; phy_dv = 1'b0;
      @(posedge clk_rx);
      idle = idle + 1;
    end
  end
end

task automatic pc_command(input [5:0] addr, input [31:0] value);
  byte unsigned p[];
  integer i;
  p = new[60];
  for (i = 0; i < 60; i = i + 1) p[i] = 8'h00;
  p[0] = 8'hef; p[1] = 8'hfe; p[2] = 8'h05; p[3] = 8'h7f; p[4] = {addr, 1'b0};
  p[5] = value[31:24]; p[6] = value[23:16]; p[7] = value[15:8]; p[8] = value[7:0];
  queue_udp(16'd1025, p, 60, 0);
endtask

task automatic pc_startstop(input [7:0] flags);
  byte unsigned p[];
  integer i;
  p = new[64];
  for (i = 0; i < 64; i = i + 1) p[i] = 8'h00;
  p[0] = 8'hef; p[1] = 8'hfe; p[2] = 8'h04; p[3] = flags;
  queue_udp(16'd1024, p, 64, 0);
endtask

integer disc_sent = 0;
task automatic pc_discover();
  byte unsigned p[];
  integer i;
  p = new[60];
  for (i = 0; i < 60; i = i + 1) p[i] = 8'h00;
  p[0] = 8'hef; p[1] = 8'hfe; p[2] = 8'h02;
  queue_udp(16'd1024, p, 60, 1);
  disc_sent = disc_sent + 1;
endtask

// TX frame sender with pacing against the simulated AD9866 clock
integer    tx_n        = 5970;        // samples per TX frame
real       tx_rate     = 1.0;         // sender speed relative to the AD9866 clock
logic      tx_enable   = 1'b0;
integer    tx_port     = 1026;
longint    tx_seq      = 0;
longint    tx_idx      = 0;
integer    tx_skip     = 0;           // lose the next n frames on the wire
integer    tx_extra    = 0;           // send n extra frames right away
integer    tx_corrupt  = 0;           // corrupt one sample in the next frame
integer    tx_sent     = 0;
integer    tx_lost_inj = 0;
integer    tx_bad_inj  = 0;
integer    tx_other    = 0;           // frames sent to a port other than 1026
real       tx_next     = 0.0;

task automatic send_tx_frame();
  byte unsigned p[];
  integer i, plen, k;
  reg [11:0] a, b;
  plen = 16 + 3 * tx_n / 2;
  p = new[plen];
  p[0] = 8'h5a; p[1] = 8'h01; p[2] = 8'h01; p[3] = 8'h00;
  p[4] = tx_seq[31:24]; p[5] = tx_seq[23:16]; p[6] = tx_seq[15:8]; p[7] = tx_seq[7:0];
  for (i = 0; i < 6; i = i + 1) p[8+i] = tx_idx[47-8*i -: 8];
  p[14] = tx_n[15:8]; p[15] = tx_n[7:0];
  for (k = 0; k < tx_n; k = k + 2) begin
    a = (tx_idx + k) & 12'hfff;
    b = (tx_idx + k + 1) & 12'hfff;
    if (tx_corrupt && k == 1000) begin a = a ^ 12'h040; tx_corrupt = 0; tx_bad_inj = tx_bad_inj + 1; end
    i = 16 + 3 * (k / 2);
    p[i] = a[11:4]; p[i+1] = {a[3:0], b[11:8]}; p[i+2] = b[7:0];
  end
  if (tx_skip > 0) begin
    tx_skip = tx_skip - 1;
    tx_lost_inj = tx_lost_inj + 1;
  end else begin
    queue_udp(tx_port[15:0], p, plen, 0);
    if (tx_port == 1026) tx_sent = tx_sent + 1; else tx_other = tx_other + 1;
  end
  tx_seq = tx_seq + 1;
  tx_idx = tx_idx + tx_n;
endtask

initial begin : tx_sender
  forever begin
    @(posedge clk_rx);
    if (!tx_enable) begin
      tx_next = $realtime;
    end else if (tx_extra > 0 && txq_len.size() == 0) begin
      send_tx_frame();
      tx_extra = tx_extra - 1;
    end else if ($realtime >= tx_next) begin
      send_tx_frame();
      tx_next = tx_next + (tx_n * T_AD) / tx_rate;
    end
  end
end

// ---------------------------------------------------------------------------
// HL2 -> PC raw frame capture and checking

byte unsigned fr[$];
integer raw_frames = 0, raw_v2 = 0, pkt_frames = 0, other_frames = 0, raw_bad = 0;
longint exp_seq = -1;
// Latest TX status seen in a raw frame header
longint st_frames = 0, st_lost = 0, st_bad = 0;
integer st_fill = 0, st_unf = 0, st_ovf = 0, st_flags = 0;
integer fill_min = 100000, fill_max = -1;

task automatic check_frame();
  integer len, pay, n, j, i, hl, ver;
  byte unsigned b[];
  longint seq, idx;
  reg [11:0] a, s;
  reg [7:0]  b1, fl;
  len = fr.size();
  b = new[len];
  for (i = 0; i < len; i = i + 1) b[i] = fr[i];
  pay = {b[38], b[39]} - 8;
  if (pay >= 20 && b[42] == 8'ha5) begin
    raw_frames = raw_frames + 1;
    ver = b[43];
    hl  = (ver == 2) ? 40 : 20;
    `CHECK(ver == 1 || ver == 2, "raw frame version")
    seq = {b[46], b[47], b[48], b[49]};
    idx = {b[50], b[51], b[52], b[53], b[54], b[55]};
    n   = {b[56], b[57]};
    `CHECK(pay == hl + 3 * n / 2, $sformatf("raw payload %0d bytes, header %0d, N %0d", pay, hl, n))
    fl = b[44];
    if (fl[4]) exp_seq = 0;
    `CHECK(exp_seq < 0 || seq == exp_seq, $sformatf("raw sequence %0d expected %0d", seq, exp_seq))
    exp_seq = seq + 1;
    for (j = 0; j < n; j = j + 2) begin
      i = 42 + hl + 3 * (j / 2);
      b1 = b[i+1];
      a = {b[i], b1[7:4]};
      s = {b1[3:0], b[i+2]};
      if (a != ((idx + j) & 12'hfff) || s != ((idx + j + 1) & 12'hfff)) raw_bad = raw_bad + 1;
    end
    if (ver == 2) begin
      raw_v2    = raw_v2 + 1;
      st_frames = {b[62], b[63], b[64], b[65]};
      st_lost   = {b[66], b[67], b[68], b[69]};
      st_bad    = {b[70], b[71], b[72], b[73]};
      st_fill   = {b[74], b[75]};
      st_unf    = {b[76], b[77]};
      st_ovf    = {b[78], b[79]};
      st_flags  = b[80];
      `CHECK(b[81] == 0, "status reserved byte")
      if (st_fill < fill_min) fill_min = st_fill;
      if (st_fill > fill_max) fill_max = st_fill;
    end
  end else if (pay == 60 && b[42] == 8'hef) begin
    pkt_frames = pkt_frames + 1;
  end else begin
    other_frames = other_frames + 1;
  end
endtask

logic en_d = 1'b0;
always @(posedge clk) begin
  en_d <= tx_pipe_en;
  if (tx_pipe_en) fr.push_back(tx_pipe_d);
  else if (en_d) begin check_frame(); fr.delete(); end
end

// ---------------------------------------------------------------------------
// Test sequence

task automatic wait_us(input integer us);
  #(us * 64'd1000000);
endtask

task automatic reset_fill();
  fill_min = 100000; fill_max = -1;
endtask

longint b_frames, b_lost, b_bad;
integer b_unf, b_ovf, b_sent;

task automatic snap();
  b_frames = st_frames; b_lost = st_lost; b_bad = st_bad; b_unf = st_unf; b_ovf = st_ovf; b_sent = tx_sent;
endtask

task automatic report(input string name);
  $display("%-34s sent=%0d radio: frames=%0d lost=%0d bad=%0d fill=%0d (min %0d max %0d) unf=%0d ovf=%0d flags=%02h | raw frames v2=%0d bad=%0d",
    name, tx_sent, st_frames, st_lost, st_bad, st_fill, fill_min, fill_max, st_unf, st_ovf, st_flags, raw_v2, raw_bad);
endtask

initial begin
  wait_us(1);

  // Configure: raw pattern mode with 5,954 samples, duplex on; then discovery; start
  pc_command(6'h30, {16'd5954, 13'd0, 3'b011});
  pc_command(6'h31, 32'h1);
  pc_discover();
  wait_us(2);
  `CHECK(raw_mode == 1'b1, "register 0x30 not decoded")
  `CHECK(dup_on == 1'b1, "register 0x31 not decoded")
  pc_startstop(8'h81);
  wait_us(3);
  `CHECK(run_sync == 1'b1, "start not decoded")

  // 1. Nominal rate, jumbo TX frames (5,970 samples = 9,000-byte IP packets)
  tx_n = 5970; tx_rate = 1.0; tx_enable = 1'b1;
  wait_us(3000);                                  // prefill and settle
  `CHECK(st_flags == 8'h03, $sformatf("status flags %02h, expected duplex active + DAC playing", st_flags))
  snap(); reset_fill();
  pc_discover();
  wait_us(9000);
  report("1 nominal, 5,970-sample frames");
  `CHECK(st_lost == 0 && st_bad == 0 && st_unf == 0 && st_ovf == 0, "nominal: TX errors")
  `CHECK(st_frames >= tx_sent - 2 && st_frames <= tx_sent, $sformatf("nominal: radio counted %0d of %0d frames", st_frames, tx_sent))
  `CHECK(fill_min > HALF - 2000 && fill_max < HALF + 2000, "nominal: FIFO fill not near half")
  `CHECK(st_frames - b_frames > 100, "nominal: too few frames")

  // 2. Frame lost on the wire, then one extra frame to restore the fill
  snap();
  tx_skip = 1;
  wait_us(500);
  tx_extra = 1;
  wait_us(2000);
  report("2 one frame lost");
  `CHECK(st_lost - b_lost == 1, $sformatf("lost frame count %0d, expected 1", st_lost - b_lost))
  `CHECK(st_bad == b_bad && st_unf == b_unf && st_ovf == b_ovf, "lost frame: unexpected bad/underflow/overflow")

  // 3. One corrupted sample
  snap();
  tx_corrupt = 1;
  wait_us(1500);
  report("3 one corrupted sample");
  `CHECK(st_bad - b_bad == 1, $sformatf("bad samples %0d, expected 1", st_bad - b_bad))
  `CHECK(st_lost == b_lost && st_unf == b_unf && st_ovf == b_ovf, "corrupt sample: other counters moved")

  // 4. Sender 3 % slow: FIFO drains, underflow, DAC refills to half
  snap(); reset_fill();
  tx_rate = 0.97;
  wait_us(6000);
  tx_rate = 1.0;
  wait_us(1500);
  report("4 sender 3 % slow");
  `CHECK(st_unf - b_unf >= 1, "slow sender: no underflow counted")
  `CHECK(st_bad == b_bad && st_lost == b_lost && st_ovf == b_ovf, "slow sender: bad/lost/overflow moved")
  `CHECK(fill_min < 1000, "slow sender: fill never dropped")

  // 5. Sender 3 % fast: FIFO fills, overflow drops samples, checker resyncs (no bad samples)
  snap(); reset_fill();
  tx_rate = 1.03;
  wait_us(9000);
  report("5 sender 3 % fast");
  `CHECK(st_ovf - b_ovf >= 1, "fast sender: no overflow counted")
  // one event per TX frame that lost samples: at most every frame sent while full
  `CHECK(st_ovf - b_ovf <= tx_sent - b_sent, "fast sender: more overflow events than frames")
  `CHECK(st_bad == b_bad && st_lost == b_lost, "fast sender: bad/lost moved")
  `CHECK(fill_max > (1 << TX_AW) - 1000, "fast sender: fill never reached full")
  // back to the middle
  tx_rate = 0.97;
  wait_us(4500);
  tx_rate = 1.0;
  wait_us(1000);

  // 6. 1,500-byte TX frames (970 samples), nominal rate
  tx_n = 970;
  wait_us(1000);
  snap(); reset_fill();
  wait_us(3000);
  report("6 nominal, 970-sample frames");
  `CHECK(st_lost == b_lost && st_bad == b_bad && st_unf == b_unf && st_ovf == b_ovf, "970-sample frames: TX errors")
  `CHECK(st_frames - b_frames >= (tx_sent - b_sent) - 20, "970-sample frames: frames not counted")

  // 7. Frames to another port are ignored
  snap();
  tx_port = 1027;
  wait_us(1000);
  report("7 frames to port 1027");
  `CHECK(st_frames == b_frames || st_frames <= b_frames + 20, "port filter: frames to 1027 counted")
  tx_port = 1026;
  tx_enable = 1'b0;
  wait_us(1000);

  // 8. Duplex off: version 1 headers again, TX frames ignored
  pc_command(6'h31, 32'h0);
  wait_us(1500);
  raw_v2 = 0;
  tx_enable = 1'b1;
  wait_us(1500);
  tx_enable = 1'b0;
  `CHECK(raw_v2 == 0, "duplex off: version 2 frames still sent")
  `CHECK(dup_on == 1'b0, "duplex off not decoded")
  report("8 duplex off");

  // 9. Stop; raw frames and discovery replies all accounted for
  pc_startstop(8'h00);
  wait_us(2000);
  pc_discover();
  wait_us(1000);
  $display("raw frames=%0d raw pattern errors=%0d discovery requests=%0d replies=%0d other=%0d", raw_frames, raw_bad, disc_sent, pkt_frames, other_frames);
  `CHECK(raw_bad == 0, "raw stream pattern errors")
  `CHECK(pkt_frames == disc_sent, "discovery replies lost")
  `CHECK(other_frames == 0, "unexpected frames from the HL2")

  if (errors == 0) $display("PASS");
  else $display("FAIL: %0d errors", errors);
  $finish;
end

endmodule
