// SPDX-License-Identifier: GPL-2.0-or-later
// Copyright 2026 Franz Schöning, https://www.schoning.com
//
// Echo mode and real-TX gating of the raw front-end image: rtl/txsink.v and rtl/rawstream.v with ECHO = 1,
// the transmit interlock (rtl/hl2io.v tx_interlock), the DAC gate (txdac_gate) and the AD9866 interface
// (rtl/ad9866.v, FAST_LNA) as wired in hermeslite_core.v (RAWFRONT = 1).
//
// Same method as tb_duplex.sv: a PC model drives complete Ethernet frames as RGMII into the real receive
// path (register writes, start, TX frames with the counter pattern and a 48-bit sample index), raw frames
// leave through the real send path and are checked as the PC does.
//
// Checks
//   Echo (0x31 = 0x05): version 3 frames with the 48-byte header; flags (echo on, offset valid); every
//   echoed sample equals the TX sample whose index is the RX index plus the header offset, so throughput,
//   loss and latency can be measured sample by sample; the offset (latency in samples) is the TX FIFO
//   prefill plus a small pipeline; a TX frame lost on the wire, a slow sender (underflow: zeros while not
//   playing, then a new offset) and a fast sender (overflow drops) keep every echoed sample consistent;
//   the DAC is never driven in echo mode, even with transmit granted.
//   Real DAC (0x31 = 0x03): without transmit permission the AD9866 transmit pins stay idle and the RX
//   stream carries the normal pattern; with permission renewed and keyed, the DAC enable follows the
//   interlock and the words on the AD9866 pins are the TX samples, one per AD9866 clock; echo on (0x07)
//   forces the DAC off while granted; the lease running out stops the DAC and latches the lease trip,
//   which the header's trip byte reports.
`timescale 1ps/1ps

module tb_echo;

localparam TX_AW    = 14;
localparam RX_AW    = 13;
localparam T_AD     = 13020;          // ps, AD9866 clock period (76.805 MHz)
localparam RX_N     = 5948;           // radio -> PC samples per frame (9,000 IP MTU with 48-byte header)
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
wire         mode_real, mode_echo, echo_ok, echo_play;
wire  [11:0] dac_out, echo_data;
wire  [47:0] echo_idx;

// ADC ramp (the raw stream runs in pattern mode here, so this is unused)
logic [11:0] adc = 12'h0;
always @(posedge clk_ad) adc <= adc + 12'd3;

txsink #(.FIFO_AW(TX_AW), .ECHO(1)) txsink_i (
  .clk_rx(clk_rx), .eth_port(to_port), .eth_broadcast(broadcast), .eth_valid(udp_rx_active),
  .eth_data(rx_data), .clk_ad(clk_ad), .clk(clk), .raw_mode(raw_mode), .run(run_sync),
  .cmd_addr(ds_cmd_addr), .cmd_data(ds_cmd_data), .cmd_rqst(cmd_rqst), .dup_on(dup_on), .status(dup_status),
  .mode_real(mode_real), .mode_echo(mode_echo), .dac_out(dac_out), .echo_data(echo_data), .echo_idx(echo_idx),
  .echo_ok(echo_ok), .echo_play(echo_play));

// transmit interlock, the CDC of the header bytes and the DAC gate as in hermeslite_core.v (RAWFRONT = 1)
logic        clk_ctrl = 1'b0;
always #200000 clk_ctrl = ~clk_ctrl;       // 2.5 MHz
integer      msc = 0;
logic        msec = 1'b0;                  // simulated millisecond: 5 control cycles (2 us)
always @(posedge clk_ctrl) begin msc <= (msc == 4) ? 0 : msc + 1; msec <= (msc == 4); end
logic        permit_tog = 1'b0, key_req = 1'b0, adc_tick = 1'b0;
always @(posedge clk_ctrl) adc_tick <= msec;
wire         ilk_envpa, ilk_envop, ilk_envbias, ilk_inttr, ilk_exttr, ilk_rfsw, ilk_dac_en, ilk_tx_on;
wire  [31:0] ilk_status;
tx_interlock ilk_i (
  .clk(clk_ctrl), .msec(msec), .permit_tog(permit_tog), .key_req(key_req), .ptt_en(1'b0), .cw_en(1'b0),
  .clear_tog(1'b0), .lease_ms(10'd100), .maxkey_s(10'd600), .temp_limit(12'h527), .temperature(12'h3ed),
  .adc_tick(adc_tick), .fan_overheat(1'b0), .inhibit(1'b0), .ptt_in(1'b0), .key_in(1'b0), .wdog_fired(1'b0),
  .pa_enable(1'b1), .tr_disable(1'b0), .vna(1'b0), .pwr_envpa(ilk_envpa), .pwr_envop(ilk_envop),
  .pwr_envbias(ilk_envbias), .pa_inttr(ilk_inttr), .pa_exttr(ilk_exttr), .rfsw_sel(ilk_rfsw), .dac_en(ilk_dac_en),
  .tx_on(ilk_tx_on), .status(ilk_status), .keytime());

wire  [15:0] ilk_hdr_c;
cdc_word #(.W(16)) cdc_ilk_hdr_i (
  .clk_a(clk_ctrl),
  .d_a  ({1'b0, ilk_status[0], ilk_status[2], ilk_status[4], ilk_status[1], 3'b000, ilk_status[15:8]}),
  .clk_b(clk), .q_b(ilk_hdr_c));
wire  [15:0] ext_status = {ilk_hdr_c[15:12], ilk_hdr_c[11] & mode_real, mode_real, mode_echo, 1'b0, ilk_hdr_c[7:0]};

wire         ad_tx_en;
wire  [11:0] ad_tx_data;
txdac_gate gate_i (.clk_ad(clk_ad), .dac_en(ilk_dac_en), .mode_real(mode_real), .dac_in(dac_out),
                   .tx_en(ad_tx_en), .tx_data(ad_tx_data));

// AD9866 2x clock, rising edges aligned with the 1x clock
logic        clk_ad2 = 1'b0;
initial begin #1733; forever #(T_AD/4) clk_ad2 = ~clk_ad2; end
wire  [5:0]  pin_tx;
wire         pin_txsync, pin_txquiet_n, pin_pga5;
ad9866 #(.FAST_LNA(1)) ad9866_i (
  .clk(clk_ad), .clk_2x(clk_ad2), .rst(1'b0), .tx_data(ad_tx_data), .rx_data(), .tx_en(ad_tx_en), .cw_on(1'b0),
  .rxclip(), .rxgoodlvl(), .rxclrstatus(1'b0), .rffe_ad9866_tx(pin_tx), .rffe_ad9866_rx(6'd0),
  .rffe_ad9866_rxsync(1'b0), .rffe_ad9866_rxclk(1'b0), .rffe_ad9866_txquiet_n(pin_txquiet_n),
  .rffe_ad9866_txsync(pin_txsync), .rffe_ad9866_mode(), .rffe_ad9866_pga5(pin_pga5),
  .cmd_addr(6'd0), .cmd_data(32'd0), .cmd_rqst(1'b0), .cmd_ack());

rawstream #(.FIFO_AW(RX_AW), .MAX_N_OVERRIDE(5968), .DUPLEX(1), .ECHO(1)) rawstream_i (
  .clk_ad(clk_ad), .adc_data(adc), .clk(clk), .run(run_sync),
  .cmd_addr(ds_cmd_addr), .cmd_data(ds_cmd_data), .cmd_rqst(cmd_rqst), .raw_mode(raw_mode),
  .pkt_tx_request(pkt_req), .pkt_tx_length({5'h0, pkt_len}), .pkt_tx_data(pkt_data), .pkt_tx_enable(pkt_en),
  .udp_tx_request(udp_tx_request), .udp_tx_length(udp_tx_length), .udp_tx_data(udp_tx_data),
  .udp_tx_enable(udp_tx_enable), .udp0_tx_enable(udp0_tx_enable), .udp_tx_busy(udp_tx_busy),
  .dup_on(dup_on), .dup_status(dup_status), .tx_status(8'h41),
  .echo_on(mode_echo), .echo_data(echo_data), .echo_idx(echo_idx), .echo_ok(echo_ok), .echo_play(echo_play), .ext_status(ext_status));

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
integer raw_frames = 0, raw_v3 = 0, pkt_frames = 0, other_frames = 0, pat_bad = 0;
longint exp_seq = -1;
longint st_frames = 0, st_lost = 0, st_bad = 0;
integer st_fill = 0, st_unf = 0, st_ovf = 0, st_flags = 0, st_b46 = 0, st_b47 = 0;
longint st_off = 0, prev_off = 0;
integer have_prev = 0;
longint echo_good = 0, echo_bad = 0, echo_zero = 0, echo_stale = 0, echo_frames_valid = 0, off_changes = 0;
longint echo_unsettled = 0;                // mismatches in frames around an offset change (samples written before it)
integer prev_valid = 0;
longint off_min = 64'sh7fffffffffffffff, off_max = -64'sh7fffffffffffffff;

task automatic check_frame();
  integer len, pay, n, j, i, hl, ver, q;
  byte unsigned b[];
  longint seq, idx, off, want, want2;
  reg [11:0] a, s, v;
  reg [7:0]  b1, fl, f46, f80;
  reg [47:0] off48;
  len = fr.size();
  b = new[len];
  for (i = 0; i < len; i = i + 1) b[i] = fr[i];
  pay = {b[38], b[39]} - 8;
  if (pay >= 20 && b[42] == 8'ha5) begin
    raw_frames = raw_frames + 1;
    ver = b[43];
    hl  = (ver == 3) ? 48 : (ver == 2) ? 40 : 20;
    `CHECK(ver == 1 || ver == 3, "raw frame version (1 or 3)")
    seq = {b[46], b[47], b[48], b[49]};
    idx = {b[50], b[51], b[52], b[53], b[54], b[55]};
    n   = {b[56], b[57]};
    `CHECK(pay == hl + 3 * n / 2, $sformatf("raw payload %0d bytes, header %0d, N %0d", pay, hl, n))
    fl = b[44];
    if (fl[4]) exp_seq = 0;
    `CHECK(exp_seq < 0 || seq == exp_seq, $sformatf("raw sequence %0d expected %0d", seq, exp_seq))
    exp_seq = seq + 1;
    f80 = 8'h00;
    f46 = 8'h00;
    if (ver == 3) begin
      raw_v3    = raw_v3 + 1;
      st_frames = {b[62], b[63], b[64], b[65]};
      st_lost   = {b[66], b[67], b[68], b[69]};
      st_bad    = {b[70], b[71], b[72], b[73]};
      st_fill   = {b[74], b[75]};
      st_unf    = {b[76], b[77]};
      st_ovf    = {b[78], b[79]};
      st_flags  = b[80];
      st_b46    = b[88];
      st_b47    = b[89];
      f80       = b[80];
      f46       = b[88];
      off48     = {b[82], b[83], b[84], b[85], b[86], b[87]};
      off       = off48[47] ? (longint'(off48) - (64'sd1 << 48)) : longint'(off48);
      st_off    = off;
    end
    for (j = 0; j < n; j = j + 2) begin
      i = 42 + hl + 3 * (j / 2);
      b1 = b[i+1];
      a = {b[i], b1[7:4]};
      s = {b1[3:0], b[i+2]};
      if (ver == 3 && f80[3]) begin               // echo mode
        if (f46[0]) begin
          // sample k at RX index idx + k is the TX sample with index idx + k + offset; 0 while nothing plays
          for (q = 0; q < 2; q = q + 1) begin
            v = q ? s : a;
            want  = (idx + j + q + off) & 12'hfff;
            want2 = (idx + j + q + prev_off) & 12'hfff;
            if (v == want) echo_good = echo_good + 1;
            else if (have_prev != 0 && v == want2) echo_stale = echo_stale + 1;
            else if (v == 0) echo_zero = echo_zero + 1;
            else if (prev_valid == 0 || off != prev_off) echo_unsettled = echo_unsettled + 1;
            else echo_bad = echo_bad + 1;          // steady offset: every sample must match
          end
        end
      end else begin
        if (a != ((idx + j) & 12'hfff) || s != ((idx + j + 1) & 12'hfff)) pat_bad = pat_bad + 1;
      end
    end
    if (ver == 3 && f80[3] && f46[0]) begin
      echo_frames_valid = echo_frames_valid + 1;
      if (have_prev != 0 && off != prev_off) off_changes = off_changes + 1;
      if (off < off_min) off_min = off;
      if (off > off_max) off_max = off;
      prev_off = off;
      have_prev = 1;
    end
    if (ver == 3) prev_valid = f80[3] & f46[0];
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

// AD9866 transmit pins (FAST_LNA interface on the 2x clock): the high half, then the low half with TXSYNC.
// While the transmit path is enabled the rebuilt words must count up by one (the TX counter pattern).
logic [5:0]  hi6 = 6'd0;
logic [11:0] dac_prev = 12'd0;
integer      dac_words = 0, dac_steps_bad = 0;
logic        have_dac = 1'b0;
always @(posedge clk_ad2) begin
  if (!pin_txquiet_n) begin
    have_dac <= 1'b0;
  end else if (pin_txsync) begin
    if (have_dac && {hi6, pin_tx} != dac_prev + 12'd1) dac_steps_bad <= dac_steps_bad + 1;
    dac_prev  <= {hi6, pin_tx};
    have_dac  <= 1'b1;
    dac_words <= dac_words + 1;
  end else begin
    hi6 <= pin_tx;
  end
end

// ---------------------------------------------------------------------------
// Test sequence

task automatic wait_us(input integer us);
  #(us * 64'd1000000);
endtask

task automatic report(input string name);
  $display("%-34s sent=%0d radio: frames=%0d lost=%0d fill=%0d unf=%0d ovf=%0d flags=%02h b46=%02h trip=%02h off=%0d | echo good=%0d stale=%0d zero=%0d unsettled=%0d bad=%0d changes=%0d | pattern bad=%0d | DAC words=%0d bad steps=%0d",
    name, tx_sent, st_frames, st_lost, st_fill, st_unf, st_ovf, st_flags, st_b46, st_b47, st_off, echo_good, echo_stale, echo_zero,
    echo_unsettled, echo_bad, off_changes, pat_bad, dac_words, dac_steps_bad);
  $fflush();
endtask

// transmit permission: renewed every 30 simulated ms (60 us) while renew = 1; lease 100 ms (200 us)
logic renew = 1'b0;
initial forever begin
  wait_us(60);
  if (renew) permit_tog = ~permit_tog;
end

initial begin
  longint g0, z0;
  integer w0;
  wait_us(1);

  pc_command(6'h30, {16'd5948, 13'd0, 3'b011});     // raw on, pattern (the echo samples replace it in echo mode)
  pc_command(6'h31, 32'h5);                          // duplex + echo
  wait_us(2);
  `CHECK(raw_mode == 1'b1 && dup_on == 1'b1 && mode_echo == 1'b1 && mode_real == 1'b0, "registers 0x30/0x31 (echo) decoded")
  pc_startstop(8'h81);
  wait_us(3);

  // 1. Echo, nominal rate
  tx_n = 5970; tx_rate = 1.0; tx_enable = 1'b1;
  wait_us(3000);
  report("1a echo prefill");
  `CHECK(st_flags == 8'h0b, $sformatf("status flags %02h, expected active + playing + echo", st_flags))
  `CHECK(st_b46[1] == 1'b1 && st_b46[0] == 1'b1 && st_b46[2] == 1'b0, $sformatf("byte 46 %02h: echo on, offset valid, not real", st_b46))
  g0 = echo_good;
  wait_us(6000);
  report("1b echo nominal");
  `CHECK(echo_good - g0 > 400000, "echo: samples checked")
  `CHECK(echo_bad == 0, "echo: every echoed sample is the TX sample at RX index + offset")
  `CHECK(-off_max >= HALF && -off_min <= HALF + 3 * tx_n, $sformatf("echo latency %0d..%0d samples (prefill %0d)", -off_max, -off_min, HALF))
  `CHECK(off_changes == 0, "echo: offset constant at the nominal rate")

  // 2. TX frame lost on the wire: the sink resyncs, the offset changes by one frame, samples stay consistent
  tx_skip = 1;
  wait_us(500);
  tx_extra = 1;
  wait_us(2500);
  report("2 echo, one TX frame lost");
  `CHECK(st_lost == 1, "lost frame counted")
  `CHECK(echo_bad == 0, "echo after a lost frame: no inconsistent samples")
  `CHECK(off_changes >= 1, "echo: offset changed after the lost frame")

  // 3. slow sender: underflow, zeros while refilling, then a new offset
  z0 = echo_zero;
  tx_rate = 0.97;
  wait_us(6000);
  tx_rate = 1.0;
  wait_us(3000);
  report("3 echo, sender 3 % slow");
  `CHECK(st_unf >= 1, "underflow counted")
  `CHECK(echo_zero > z0, "zeros echoed while the sink refills")
  `CHECK(echo_bad == 0, "echo with underflow: no inconsistent samples")

  // 4. fast sender: overflow drops, resync
  tx_rate = 1.03;
  wait_us(9000);
  tx_rate = 0.97;
  wait_us(4500);
  tx_rate = 1.0;
  wait_us(2000);
  report("4 echo, sender 3 % fast then back");
  `CHECK(st_ovf >= 1, "overflow counted")
  `CHECK(echo_bad == 0, "echo with overflow: no inconsistent samples")

  // 4b. bursts into a full FIFO: every other sample dropped, thousands of resync samples per TX frame
  //     (the index must stay correct or be marked not valid, never a wrong offset)
  tx_rate = 1.03;
  wait_us(6000);
  repeat (3) begin
    tx_extra = 4;
    wait_us(1500);
  end
  tx_rate = 0.97;
  wait_us(4500);
  tx_rate = 1.0;
  wait_us(2000);
  report("4b echo, bursts into a full FIFO");
  `CHECK(echo_bad == 0, "echo with overflow bursts: no inconsistent samples")

  // 5. transmit granted while in echo mode: the DAC stays off
  key_req = 1'b1; renew = 1'b1;
  wait_us(500);
  `CHECK(ilk_dac_en == 1'b1, "interlock grants transmit (lease renewed, keyed)")
  `CHECK(ad_tx_en == 1'b0 && pin_txquiet_n == 1'b0 && dac_words == 0, "echo mode with transmit granted: AD9866 transmit path idle")
  report("5 echo with transmit granted");
  key_req = 1'b0;
  wait_us(100);
  renew = 1'b0;
  wait_us(500);
  `CHECK(ilk_dac_en == 1'b0, "key up, lease ran out")

  // 6. real DAC mode without permission: pins idle, RX stream is the pattern again
  pc_command(6'h31, 32'h3);
  wait_us(3000);
  pat_bad = 0;
  wait_us(2000);
  report("6 real DAC, no permission");
  `CHECK(mode_real == 1'b1 && mode_echo == 1'b0, "0x31 = 3: real DAC mode")
  `CHECK(st_b46[2] == 1'b1 && st_b46[3] == 1'b0 && st_b46[1] == 1'b0, $sformatf("byte 46 %02h: real mode, DAC not driven", st_b46))
  `CHECK(ad_tx_en == 1'b0 && pin_txquiet_n == 1'b0 && dac_words == 0 && ad_tx_data == 12'd0, "no permission: AD9866 transmit path idle, DAC input 0")
  `CHECK(pat_bad == 0, "RX pattern stream while in real DAC mode")

  // 7. permission renewed and keyed: DAC driven with the TX samples after the relay delay
  key_req = 1'b1; renew = 1'b1;
  wait_us(1000);
  report("7 real DAC, transmit granted");
  `CHECK(ilk_exttr == 1'b1 && ilk_dac_en == 1'b1, "interlock: relays and PA stage on")
  `CHECK(ad_tx_en == 1'b1 && pin_txquiet_n == 1'b1, "AD9866 transmit enabled")
  `CHECK(dac_words > 50000 && dac_steps_bad == 0, "AD9866 pins carry the TX counter pattern, one sample per clock")
  `CHECK(st_b46[3] == 1'b1 && st_b46[6] == 1'b1 && st_b46[5] == 1'b1, $sformatf("byte 46 %02h: DAC driven, transmit on, lease valid", st_b46))

  // 8. echo switched on while granted: DAC off at once
  pc_command(6'h31, 32'h7);
  wait_us(300);
  w0 = dac_words;
  wait_us(300);
  `CHECK(mode_echo == 1'b1 && mode_real == 1'b0 && ad_tx_en == 1'b0 && dac_words == w0, "0x31 = 7 (echo + real): echo wins, DAC off while granted")
  pc_command(6'h31, 32'h3);
  wait_us(300);
  `CHECK(ad_tx_en == 1'b1, "back to real DAC mode: DAC on again")

  // 9. lease runs out while keyed: DAC off, lease trip in the header
  renew = 1'b0;
  wait_us(1000);
  report("9 real DAC, lease ran out");
  w0 = dac_words;
  wait_us(300);
  `CHECK(ad_tx_en == 1'b0 && pin_txquiet_n == 1'b0 && dac_words == w0, "lease expired: AD9866 transmit path idle")
  `CHECK(st_b47 == 8'h01 && st_b46[4] == 1'b1, $sformatf("header trip byte %02h: lease trip latched", st_b47))
  key_req = 1'b0;

  tx_enable = 1'b0;
  pc_startstop(8'h00);
  wait_us(2000);
  report("end");
  `CHECK(other_frames == 0, "unexpected frames from the HL2")
  `CHECK(echo_bad == 0, "whole run: no echoed sample inconsistent with a steady offset")

  if (errors == 0) $display("tb_echo PASS");
  else $display("tb_echo FAIL: %0d errors", errors);
  $finish;
end

endmodule
