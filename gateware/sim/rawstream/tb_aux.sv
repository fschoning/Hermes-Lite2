// SPDX-License-Identifier: GPL-2.0-or-later
// Copyright 2026 Franz Schöning, https://www.schoning.com
//
// Testbench for the aux data channel: rtl/auxchan.v + rtl/rawstream.v (DUPLEX=1, AUX=1)
// + rtl/txsink.v
//
// PC -> HL2: like tb_duplex.sv, a PC model builds complete Ethernet frames and drives them
// as RGMII nibbles into the REAL receive path (rgmii_recv, mac_recv, ip_recv, udp_recv with
// jumbo counters, dsopenhpsdr1). Register writes, start/stop, discovery, TX sample frames
// (port 1026) and aux packets (port 1027) all arrive that way.
//
// HL2 -> PC: frames leaving the real udp_send/ip_send/mac_send are captured. Raw frames are
// checked as in tb_duplex.sv; radio aux packets are checked here: sequence numbers, the
// radio counter stream against its byte pattern, and the echo bytes against the PC's aux
// byte pattern (with resynchronisation after a gap, as the PC tool does).
//
// Priority: every clock cycle in which a raw frame is due (sender waiting, or idle with a
// full frame in the FIFO) while the aux sender owns or uses the send path is counted, and
// the longest such run is checked against the design bound.
//
// The network.v glue (receive wiring, send arbitration, aux destination capture) and the
// discovery-reply packer are copied into this file because iverilog rejects network.v and
// usopenhpsdr1.v (see tb_rawstream.sv).
//
// Run: ./run.sh aux

`timescale 1ps/1ps

module tb_aux;

localparam TX_AW     = 14;
localparam RX_AW     = 13;
localparam AUX_AW    = 12;
localparam T_AD      = 13020;         // ps, AD9866 clock period (76.805 MHz)
localparam AUX_BOUND = 16;            // clock cycles a due raw frame may wait on the aux sender

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
wire        udp_destination_valid;

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
  .udp_destination_ip(), .udp_destination_mac(), .udp_destination_port(),
  .udp_destination_valid(udp_destination_valid));

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
wire run_sync, cmd_rqst, discover_rqst, dest_stb;
sync       sync_run  (.clock(clk), .sig_in(run),          .sig_out(run_sync));
sync_pulse sync_cmd  (.clock(clk), .sig_in(ds_cmd_cnt),   .sig_out(cmd_rqst));
sync_pulse sync_disc (.clock(clk), .sig_in(discover_cnt), .sig_out(discover_rqst));
sync_pulse sync_dest (.clock(clk), .sig_in(udp_destination_valid), .sig_out(dest_stb));

// network.v (AUX = 1): aux destination capture
logic aux_dest_valid = 1'b0;
always @(posedge clk) if (dest_stb && to_port == 16'd1027) aux_dest_valid <= 1'b1;

// ---------------------------------------------------------------------------
// DUTs

logic [ 1:0] udp_tx_request;
logic [15:0] udp_tx_length;
logic [ 7:0] udp_tx_data;
wire         udp_tx_enable, udp0_tx_enable, udp2_tx_enable, udp_tx_busy;
wire  [ 1:0] pkt_req;
wire  [ 7:0] pkt_data;
wire  [10:0] pkt_len;
logic        pkt_en;
logic        raw_mode;
wire         dup_on;
wire [159:0] dup_status;
wire  [15:0] aux_room;
wire         raw_run, aux_ready, aux_grant, aux_busy, aux_enable;
wire  [ 1:0] aux_tx_request;
wire  [15:0] aux_tx_length;
wire  [ 7:0] aux_tx_data;

logic [11:0] adc = 12'h0;
always @(posedge clk_ad) adc <= adc + 12'd3;

txsink #(.FIFO_AW(TX_AW)) txsink_i (
  .clk_rx(clk_rx), .eth_port(to_port), .eth_broadcast(broadcast), .eth_valid(udp_rx_active),
  .eth_data(rx_data), .clk_ad(clk_ad), .clk(clk), .raw_mode(raw_mode), .run(run_sync),
  .cmd_addr(ds_cmd_addr), .cmd_data(ds_cmd_data), .cmd_rqst(cmd_rqst), .dup_on(dup_on), .status(dup_status));

auxchan #(.FIFO_AW(AUX_AW)) auxchan_i (
  .clk_rx(clk_rx), .eth_port(to_port), .eth_broadcast(broadcast), .eth_valid(udp_rx_active),
  .eth_data(rx_data), .clk(clk), .cmd_addr(ds_cmd_addr), .cmd_data(ds_cmd_data), .cmd_rqst(cmd_rqst),
  .dest_valid(aux_dest_valid), .raw_active(raw_run), .room(aux_room), .ready(aux_ready),
  .grant(aux_grant), .tx_request(aux_tx_request), .tx_length(aux_tx_length), .tx_data(aux_tx_data),
  .tx_enable(aux_enable), .busy(aux_busy));

rawstream #(.FIFO_AW(RX_AW), .MAX_N_OVERRIDE(5968), .DUPLEX(1), .AUX(1)) rawstream_i (
  .clk_ad(clk_ad), .adc_data(adc), .clk(clk), .run(run_sync),
  .cmd_addr(ds_cmd_addr), .cmd_data(ds_cmd_data), .cmd_rqst(cmd_rqst), .raw_mode(raw_mode),
  .pkt_tx_request(pkt_req), .pkt_tx_length({5'h0, pkt_len}), .pkt_tx_data(pkt_data), .pkt_tx_enable(pkt_en),
  .udp_tx_request(udp_tx_request), .udp_tx_length(udp_tx_length), .udp_tx_data(udp_tx_data),
  .udp_tx_enable(udp_tx_enable), .udp0_tx_enable(udp0_tx_enable), .udp_tx_busy(udp_tx_busy),
  .dup_on(dup_on), .dup_status(dup_status), .tx_status(8'h41),
  .aux_room(aux_room), .raw_run(raw_run), .aux_ready(aux_ready), .aux_grant(aux_grant),
  .aux_tx_request(aux_tx_request), .aux_tx_length(aux_tx_length), .aux_tx_data(aux_tx_data),
  .aux_busy(aux_busy), .udp2_tx_enable(udp2_tx_enable), .aux_enable(aux_enable));

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

// Send path (network.v with AUX = 1)
localparam PT_UDP0 = 3'd4, PT_UDP2 = 3'd6;
logic tx_ready = 1'b0, tx_start = 1'b0;
logic [2:0] tx_protocol = 3'd0;
wire rgmii_tx_active;
assign udp_tx_enable  = tx_start;
assign udp0_tx_enable = tx_start && (tx_protocol == PT_UDP0);
assign udp2_tx_enable = tx_start && (tx_protocol == PT_UDP2);
assign udp_tx_busy    = tx_ready | tx_start | rgmii_tx_active;
always @(posedge clk)
  if (rgmii_tx_active) begin tx_ready <= 1'b0; tx_start <= 1'b0; end
  else if (tx_ready) tx_start <= 1'b1;
  else if (udp_tx_request == 2'b10) begin tx_protocol <= PT_UDP0; tx_ready <= 1'b1; end
  else if (udp_tx_request == 2'b01) begin tx_protocol <= PT_UDP2; tx_ready <= 1'b1; end

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
  .length_in(udp_tx_length), .local_port((tx_protocol == PT_UDP2) ? 16'd1027 : 16'd1024),
  .destination_port((tx_protocol == PT_UDP2) ? 16'd50001 : 16'd50000),
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

// Aux byte pattern: byte (o mod 4) of the big-endian 32-bit word floor(o / 4)
function automatic [7:0] aux_pat(input longint o);
  reg [31:0] w;
  w = o >> 2;
  case (o % 4)
    0: return w[31:24];
    1: return w[23:16];
    2: return w[15:8];
    default: return w[7:0];
  endcase
endfunction

// ---------------------------------------------------------------------------
// PC model: frame queue and RGMII driver

byte unsigned txq[$];
integer       txq_len[$];

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
  f[42] = 8'hc3; f[43] = (dport == 16'd1027) ? 8'h51 : 8'h50;   // source port 50000 / 50001
  f[44] = dport[15:8]; f[45] = dport[7:0];
  f[46] = udp_len[15:8]; f[47] = udp_len[7:0];
  f[48] = 8'h00; f[49] = 8'h00;
  for (i = 0; i < plen; i = i + 1) f[50+i] = pay[i];
  crc = crc32_eth(f, 8, 14 + ip_len);
  f[n-4] = crc[7:0]; f[n-3] = crc[15:8]; f[n-2] = crc[23:16]; f[n-1] = crc[31:24];
  for (i = 0; i < n; i = i + 1) txq.push_back(f[i]);
  txq_len.push_back(n);
endtask

initial begin : rgmii_driver
  integer n, i, idle;
  byte unsigned b;
  idle = 12;
  forever begin
    if (txq_len.size() > 0 && idle >= 12) begin
      n = txq_len.pop_front();
      for (i = 0; i < n; i = i + 1) begin
        b = txq.pop_front();
        @(negedge clk_rx); #2000; phy_rx = b[3:0]; phy_dv = 1'b1;
        @(posedge clk_rx); #2000; phy_rx = b[7:4];
      end
      @(negedge clk_rx); #2000; phy_dv = 1'b0; phy_rx = 4'h0;
      @(posedge clk_rx);
      idle = 1;
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

// ---- TX sample frame sender (as tb_duplex.sv), nominal rate ----
integer    tx_n      = 5970;
logic      tx_enable = 1'b0;
longint    tx_seq    = 0;
longint    tx_idx    = 0;
real       tx_next   = 0.0;

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
    i = 16 + 3 * (k / 2);
    p[i] = a[11:4]; p[i+1] = {a[3:0], b[11:8]}; p[i+2] = b[7:0];
  end
  queue_udp(16'd1026, p, plen, 0);
  tx_seq = tx_seq + 1;
  tx_idx = tx_idx + tx_n;
endtask

initial begin : tx_sender
  forever begin
    @(posedge clk_rx);
    if (!tx_enable) tx_next = $realtime;
    else if ($realtime >= tx_next) begin
      send_tx_frame();
      tx_next = tx_next + tx_n * T_AD;
    end
  end
end

// ---- PC aux sender ----
integer    ax_size    = 1024;         // payload bytes per aux packet
real       ax_rate    = 0.0;          // payload bytes per ms, 0 = off
integer    ax_burst   = 0;            // send n packets right away (overflow test)
integer    ax_skip    = 0;            // lose the next n packets on the wire
integer    ax_corrupt = 0;            // corrupt one byte in the next packet
longint    ax_seq     = 0;
longint    ax_off     = 0;            // offset of the next payload byte
longint    ax_bytes_sent = 0;         // payload bytes that reached the wire
real       ax_next    = 0.0;

task automatic send_aux(input integer hello);
  byte unsigned p[];
  integer i, plen, n;
  n = hello ? 0 : ax_size;
  plen = 16 + n;
  p = new[plen];
  p[0] = 8'h5b; p[1] = 8'h01; p[2] = hello ? 8'h01 : 8'h00; p[3] = 8'h00;
  p[4] = ax_seq[31:24]; p[5] = ax_seq[23:16]; p[6] = ax_seq[15:8]; p[7] = ax_seq[7:0];
  p[8] = ax_off[31:24]; p[9] = ax_off[23:16]; p[10] = ax_off[15:8]; p[11] = ax_off[7:0];
  p[12] = n[15:8]; p[13] = n[7:0]; p[14] = 8'h00; p[15] = 8'h00;
  for (i = 0; i < n; i = i + 1) p[16+i] = aux_pat(ax_off + i);
  if (!hello && ax_corrupt) begin p[16 + n/2] = p[16 + n/2] ^ 8'h10; ax_corrupt = 0; end
  if (hello) begin
    queue_udp(16'd1027, p, plen, 0);
  end else begin
    if (ax_skip > 0) ax_skip = ax_skip - 1;
    else begin queue_udp(16'd1027, p, plen, 0); ax_bytes_sent = ax_bytes_sent + n; end
    ax_seq = ax_seq + 1;
    ax_off = ax_off + n;
  end
endtask

initial begin : aux_sender
  forever begin
    @(posedge clk_rx);
    if (ax_burst > 0) begin
      send_aux(0);
      ax_burst = ax_burst - 1;
    end else if (ax_rate <= 0.0) begin
      ax_next = $realtime;
    end else if ($realtime >= ax_next) begin
      send_aux(0);
      ax_next = ax_next + (ax_size * 1.0e9) / ax_rate;   // ps per packet
    end
  end
end

// ---------------------------------------------------------------------------
// HL2 -> PC capture and checking

byte unsigned fr[$];
integer raw_frames = 0, raw_v2 = 0, pkt_frames = 0, other_frames = 0, raw_bad = 0;
longint exp_seq = -1;
longint st_lost = 0, st_bad = 0;
integer st_ovf = 0;
integer raw_hw = 0;

// radio aux packets
integer ra_pkts = 0, ra_max_len = 0;
longint ra_exp_seq = -1;
longint ra_c_exp = 0, ra_c_bytes = 0, ra_c_bad = 0, ra_c_gap = 0;
longint ra_e_exp_off = 0, ra_e_link_gap = 0;
longint ra_e_bytes = 0, ra_e_bad = 0, ra_e_gaps = 0, ra_e_gap_bytes = 0;
longint ra_e_pos = -1;                // PC offset expected for the next echo byte, -1 = not synced
longint ra_rx_pkts = 0, ra_rx_lost = 0, ra_rx_bad = 0, ra_rx_bytes = 0;
integer ra_ovf = 0, ra_fill = 0, ra_wait_max = 0, ra_starve = 0;

// Echo bytes are checked from a queue with 8 bytes of lookahead, so a gap can be
// resynchronised anywhere (the link loses nothing in simulation, so sections are contiguous).
byte unsigned eq[$];

task automatic check_echo_queue(input integer flush);
  integer a, k, ok;
  longint o, w;
  while (eq.size() >= 8 || (flush && eq.size() > 0)) begin
    if (ra_e_pos >= 0 && eq[0] == aux_pat(ra_e_pos)) begin
      ra_e_pos = ra_e_pos + 1;
      void'(eq.pop_front());
    end else begin
      ok = 0;
      if (eq.size() >= 8) begin
        for (a = 0; a < 4 && !ok; a = a + 1) begin
          w = {eq[a], eq[a+1], eq[a+2], eq[a+3]};
          o = w * 4 - a;
          if (o >= 0) begin
            ok = 1;
            for (k = 0; k < 8; k = k + 1) if (eq[k] != aux_pat(o + k)) ok = 0;
          end
        end
      end
      if (ok) begin
        if (ra_e_pos >= 0) begin
          ra_e_gaps = ra_e_gaps + 1;
          ra_e_gap_bytes = ra_e_gap_bytes + (o - ra_e_pos);
        end
        ra_e_pos = o;
      end else begin
        ra_e_bad = ra_e_bad + 1;
        if (ra_e_pos >= 0) ra_e_pos = ra_e_pos + 1;
        void'(eq.pop_front());
      end
    end
  end
endtask

task automatic check_frame();
  integer len, pay, n, j, i, hl, ver, e, c;
  byte unsigned b[];
  longint seq, idx, eo, co;
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
    seq = {b[46], b[47], b[48], b[49]};
    idx = {b[50], b[51], b[52], b[53], b[54], b[55]};
    n   = {b[56], b[57]};
    `CHECK(pay == hl + 3 * n / 2, $sformatf("raw payload %0d bytes, header %0d, N %0d", pay, hl, n))
    fl = b[44];
    if (fl[4]) exp_seq = 0;
    `CHECK(exp_seq < 0 || seq == exp_seq, $sformatf("raw sequence %0d expected %0d", seq, exp_seq))
    exp_seq = seq + 1;
    raw_hw = {b[60], b[61]};
    for (j = 0; j < n; j = j + 2) begin
      i = 42 + hl + 3 * (j / 2);
      b1 = b[i+1];
      a = {b[i], b1[7:4]};
      s = {b1[3:0], b[i+2]};
      if (a != ((idx + j) & 12'hfff) || s != ((idx + j + 1) & 12'hfff)) raw_bad = raw_bad + 1;
    end
    if (ver == 2) begin
      raw_v2 = raw_v2 + 1;
      st_lost = {b[66], b[67], b[68], b[69]};
      st_bad  = {b[70], b[71], b[72], b[73]};
      st_ovf  = {b[78], b[79]};
    end
  end else if (pay >= 44 && b[42] == 8'hb5) begin
    // radio aux packet: UDP header at 34 (source port 1027), aux header at 42
    ra_pkts = ra_pkts + 1;
    `CHECK({b[34], b[35]} == 16'd1027, "aux source port")
    `CHECK(b[43] == 8'h01 && b[45] == 8'h00, "aux version / reserved byte")
    if (pay > ra_max_len) ra_max_len = pay;
    seq = {b[46], b[47], b[48], b[49]};
    eo  = {b[50], b[51], b[52], b[53]};
    e   = {b[54], b[55]};
    co  = {b[56], b[57], b[58], b[59]};
    c   = {b[60], b[61]};
    `CHECK(pay == 44 + e + c, $sformatf("aux payload %0d, echo %0d, counter %0d", pay, e, c))
    `CHECK(ra_exp_seq < 0 || seq == ra_exp_seq || seq == 0, $sformatf("aux sequence %0d expected %0d", seq, ra_exp_seq))
    ra_exp_seq  = seq + 1;
    ra_rx_pkts  = {b[62], b[63], b[64], b[65]};
    ra_rx_lost  = {b[66], b[67], b[68], b[69]};
    ra_rx_bad   = {b[70], b[71], b[72], b[73]};
    ra_rx_bytes = {b[74], b[75], b[76], b[77]};
    ra_ovf      = {b[78], b[79]};
    ra_fill     = {b[80], b[81]};
    if ({b[82], b[83]} > ra_wait_max) ra_wait_max = {b[82], b[83]};
    ra_starve   = {b[84], b[85]};
    if (seq == 0) begin ra_e_exp_off = 0; ra_c_exp = 0; end
    if (eo != ra_e_exp_off) ra_e_link_gap = ra_e_link_gap + 1;
    ra_e_exp_off = eo + e;
    for (j = 0; j < e; j = j + 1) eq.push_back(b[86 + j]);
    ra_e_bytes = ra_e_bytes + e;
    check_echo_queue(0);
    if (co != ra_c_exp) ra_c_gap = ra_c_gap + 1;
    for (j = 0; j < c; j = j + 1) if (b[86 + e + j] != aux_pat(co + j)) ra_c_bad = ra_c_bad + 1;
    ra_c_exp   = co + c;
    ra_c_bytes = ra_c_bytes + c;
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
// Priority monitor: a raw frame is due while the aux sender holds the send path

wire raw_due = (rawstream_i.state == 4'd4) |
               ((rawstream_i.state == 4'd3) & rawstream_i.fill_ge_n & (&rawstream_i.settle));
wire aux_holds = (rawstream_i.own == 2'd2) | aux_busy;
integer due_aux_run = 0, due_aux_max = 0;
integer aux_grants_raw = 0;           // aux packets granted while the raw stream runs
always @(posedge clk) begin
  if (raw_due & aux_holds) begin
    due_aux_run = due_aux_run + 1;
    if (due_aux_run > due_aux_max) due_aux_max = due_aux_run;
  end else due_aux_run = 0;
  if (aux_grant & raw_run) aux_grants_raw = aux_grants_raw + 1;
end

// ---------------------------------------------------------------------------
// Test sequence

task automatic wait_us(input integer us);
  #(us * 64'd1000000);
endtask

// register 0x32: bit 0 on, bit 1 echo, bit 2 counter stream, bits 31:16 bytes per ms
function automatic [31:0] reg_aux(input integer on, input integer echo, input integer cnt, input integer rate);
  return {rate[15:0], 13'd0, cnt[0], echo[0], on[0]};
endfunction

longint b_rx_pkts, b_rx_lost, b_rx_bad, b_c_bytes, b_e_bytes, b_e_bad, b_e_gaps, b_sent;
integer b_ovf, b_raw_frames;

task automatic snap();
  b_rx_pkts = ra_rx_pkts; b_rx_lost = ra_rx_lost; b_rx_bad = ra_rx_bad; b_ovf = ra_ovf;
  b_c_bytes = ra_c_bytes; b_e_bytes = ra_e_bytes; b_e_bad = ra_e_bad; b_e_gaps = ra_e_gaps;
  b_raw_frames = raw_frames; b_sent = ax_bytes_sent;
endtask

task automatic report(input string name);
  $display("%s\n    aux pkts=%0d maxlen=%0d | radio rx: pkts=%0d lost=%0d bad=%0d bytes=%0d ovf=%0d fill=%0d wait_max=%0dus starve=%0d\n    counter bytes=%0d bad=%0d gaps=%0d | echo bytes=%0d (PC sent %0d) bad=%0d gaps=%0d gap_bytes=%0d link_gaps=%0d\n    raw frames=%0d bad=%0d fifo_hw=%0d | due frame waited on aux max %0d cycles | aux grants while streaming=%0d | TX lost=%0d bad=%0d ovf=%0d",
    name, ra_pkts, ra_max_len, ra_rx_pkts, ra_rx_lost, ra_rx_bad, ra_rx_bytes, ra_ovf, ra_fill, ra_wait_max, ra_starve,
    ra_c_bytes, ra_c_bad, ra_c_gap, ra_e_bytes, ax_bytes_sent, ra_e_bad, ra_e_gaps, ra_e_gap_bytes, ra_e_link_gap,
    raw_frames, raw_bad, raw_hw, due_aux_max, aux_grants_raw, st_lost, st_bad, st_ovf);
endtask

integer hw0, rate_c;

initial begin
  wait_us(1);

  // Configure raw pattern mode (5,954 samples) and duplex; announce the aux socket, aux off
  pc_command(6'h30, {16'd5954, 13'd0, 3'b011});
  pc_command(6'h31, 32'h1);
  send_aux(1);
  pc_discover();
  wait_us(3);
  `CHECK(raw_mode == 1'b1, "register 0x30 not decoded")
  `CHECK(aux_dest_valid == 1'b1, "aux destination not captured")
  `CHECK(ra_pkts == 0, "aux packets sent while aux is off")

  // 1. Aux only, radio stopped: 160 Mbit/s from the PC with echo, 80 Mbit/s counter stream
  pc_command(6'h32, reg_aux(1, 1, 1, 10000));
  wait_us(1);
  ax_size = 1400; ax_rate = 20000.0;
  wait_us(3000);
  ax_rate = 0.0;
  wait_us(1500);
  check_echo_queue(1);
  report("1 aux only, radio stopped");
  `CHECK(ra_rx_pkts > 30 && ra_rx_lost == 0 && ra_rx_bad == 0 && ra_ovf == 0, "aux only: radio receive errors")
  `CHECK(ra_rx_bytes == ax_bytes_sent, $sformatf("aux only: radio counted %0d of %0d bytes", ra_rx_bytes, ax_bytes_sent))
  `CHECK(ra_e_bytes == ax_bytes_sent && ra_e_bad == 0 && ra_e_gaps == 0 && ra_e_link_gap == 0, "aux only: echo incomplete or wrong")
  `CHECK(ra_c_bad == 0 && ra_c_gap == 0, "aux only: counter stream errors")
  `CHECK(ra_c_bytes >= 35000 && ra_c_bytes <= 60000, $sformatf("aux only: counter stream %0d bytes in 4.5 ms at 10,000 bytes/ms", ra_c_bytes))
  `CHECK(ra_max_len <= 1400, "aux only: packet longer than 1,400 bytes")

  // 2. Raw stream + duplex TX at full rate, aux off: baseline raw FIFO peak
  pc_command(6'h32, 32'h0);
  wait_us(1);
  pc_startstop(8'h81);
  tx_enable = 1'b1;
  wait_us(4000);
  hw0 = raw_hw;
  report("2 raw + TX, aux off");
  `CHECK(run_sync == 1'b1, "start not decoded")
  `CHECK(raw_bad == 0 && st_lost == 0 && st_bad == 0 && st_ovf == 0, "baseline: raw or TX errors")

  // 3. Aux on while streaming both ways at full rate: 20 Mbit/s PC -> radio with echo and a
  //    12 Mbit/s radio counter stream (32 Mbit/s radio -> PC, in the gaps between raw frames)
  rate_c = 1500;
  pc_command(6'h32, reg_aux(1, 1, 1, rate_c));
  ax_size = 1024; ax_rate = 2500.0;
  wait_us(1500);
  snap();
  due_aux_max = 0; aux_grants_raw = 0; ra_max_len = 0;
  wait_us(9000);
  report("3 raw + TX + aux 20/12 Mbit/s");
  `CHECK(raw_bad == 0 && exp_seq > 0, "aux + stream: raw pattern errors")
  `CHECK(st_lost == 0 && st_bad == 0 && st_ovf == 0, "aux + stream: TX sample errors")
  `CHECK(raw_hw <= hw0 + 16, $sformatf("aux + stream: raw FIFO peak %0d, %0d without aux", raw_hw, hw0))
  `CHECK(due_aux_max <= AUX_BOUND, $sformatf("aux + stream: raw frame waited %0d cycles on aux (bound %0d)", due_aux_max, AUX_BOUND))
  `CHECK(aux_grants_raw > 50, "aux + stream: aux hardly granted")
  `CHECK(ra_rx_lost == 0 && ra_rx_bad == 0 && ra_ovf == 0, "aux + stream: radio aux receive errors")
  `CHECK(ra_e_bad == 0 && ra_e_gaps == 0 && ra_e_link_gap == 0, "aux + stream: echo errors")
  `CHECK(ra_c_bad == 0 && ra_c_gap == 0, "aux + stream: counter errors")
  `CHECK(ra_e_bytes - b_e_bytes > (ax_bytes_sent - b_sent) - 4096, "aux + stream: echo falls behind")
  `CHECK(ra_c_bytes - b_c_bytes > rate_c * 9 * 9 / 10, $sformatf("aux + stream: counter stream %0d bytes in 9 ms at %0d bytes/ms", ra_c_bytes - b_c_bytes, rate_c))
  `CHECK(ra_wait_max < 10000 && ra_starve == 0, "aux + stream: aux starved")

  // 4. One PC aux packet lost on the wire, one corrupted byte
  snap();
  ax_skip = 1;
  wait_us(1000);
  ax_corrupt = 1;
  wait_us(1500);
  report("4 lost packet, bad byte");
  `CHECK(ra_rx_lost - b_rx_lost == 1, $sformatf("aux lost packets %0d, expected 1", ra_rx_lost - b_rx_lost))
  `CHECK(ra_rx_bad - b_rx_bad == 1, $sformatf("aux bad bytes %0d, expected 1", ra_rx_bad - b_rx_bad))
  `CHECK(ra_e_gaps - b_e_gaps == 1 && ra_e_bad - b_e_bad == 1, $sformatf("echo gaps %0d bad %0d, expected 1 and 1", ra_e_gaps - b_e_gaps, ra_e_bad - b_e_bad))
  `CHECK(ra_ovf == b_ovf && raw_bad == 0, "lost/bad: other counters moved")

  // 5. Burst of 6 packets of 1,400 bytes at once: the echo FIFO (4,096) overflows
  snap();
  ax_size = 1400;
  ax_burst = 6;
  wait_us(4000);
  ax_size = 1024;
  report("5 burst, echo FIFO overflow");
  `CHECK(ra_ovf - b_ovf >= 1, "burst: no overflow counted")
  `CHECK(ra_ovf - b_ovf <= 6, "burst: more overflow events than packets")
  `CHECK(ra_rx_bad == b_rx_bad && ra_rx_lost == b_rx_lost, "burst: radio bad/lost moved")
  `CHECK(ra_e_bad == b_e_bad && ra_e_gaps > b_e_gaps, "burst: echo should show gaps and no bad bytes")
  `CHECK(raw_bad == 0 && st_lost == 0 && st_bad == 0, "burst: sample streams disturbed")
  `CHECK(due_aux_max <= AUX_BOUND, $sformatf("burst: raw frame waited %0d cycles on aux", due_aux_max))

  // 6. Radio counter stream asks for more than the gaps carry: samples still come first
  ax_rate = 0.0;
  wait_us(1000);
  snap();
  pc_command(6'h32, reg_aux(1, 1, 1, 20000));
  wait_us(4000);
  report("6 counter stream 160 Mbit/s asked");
  `CHECK(raw_bad == 0 && st_lost == 0 && st_bad == 0, "overload: sample streams disturbed")
  `CHECK(raw_hw <= hw0 + 16, $sformatf("overload: raw FIFO peak %0d, %0d without aux", raw_hw, hw0))
  `CHECK(due_aux_max <= AUX_BOUND, $sformatf("overload: raw frame waited %0d cycles on aux", due_aux_max))
  `CHECK(ra_c_bad == 0 && ra_c_gap == 0, "overload: counter stream errors")
  `CHECK(ra_c_bytes - b_c_bytes > 4 * 3000, $sformatf("overload: counter carried only %0d bytes in 4 ms", ra_c_bytes - b_c_bytes))

  // 7. Aux off: no aux packets, raw stream unaffected; discovery replies still go out
  pc_command(6'h32, 32'h0);
  wait_us(500);
  snap();
  ra_pkts = 0;
  pc_discover();
  wait_us(1500);
  report("7 aux off");
  `CHECK(ra_pkts == 0, "aux off: aux packets still sent")
  `CHECK(raw_frames - b_raw_frames > 15, "aux off: raw stream stopped")

  // 8. Stop
  tx_enable = 1'b0;
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
