// SPDX-License-Identifier: GPL-2.0-or-later
// Copyright 2026 Franz Schöning, https://www.schoning.com
//
// Testbench for the layer-1 register bridge: rtl/hl2bus.v (ebbridge, hl2bus_regs, cmd_merge)
// with rtl/rawstream.v (DUPLEX=1, AUX=1), rtl/auxchan.v and rtl/txsink.v, wired as in
// hermeslite_core.v with HL2BUS=1.
//
// PC -> HL2: complete Ethernet frames driven as RGMII nibbles into the REAL receive path
// (rgmii_recv, mac_recv, ip_recv, udp_recv, dsopenhpsdr1): register writes, start/stop,
// discovery, aux packets and Etherbone packets (port 1027).
// HL2 -> PC: frames leaving the real udp_send/ip_send/mac_send are captured and decoded:
// raw frames (pattern, header byte 3 = transmit-safety status), aux packets, Etherbone replies.
//
// The network.v glue and the discovery-reply packer are copied from tb_aux.sv (iverilog
// rejects network.v and usopenhpsdr1.v).
//
// Run: ./run.sh bridge

`timescale 1ps/1ps

module tb_bridge;

localparam TX_AW     = 14;
localparam RX_AW     = 13;
localparam AUX_AW    = 12;
localparam T_AD      = 13020;
localparam AUX_BOUND = 16;
localparam [7:0]  TXST  = 8'h41;
localparam [52:0] CTRL  = {5'b00110, 12'h3ae, 12'h012, 12'h034, 12'h056};

logic clk = 1'b0;
logic clk_rx = 1'b0;
logic clk_ad = 1'b0;
logic clk_ctrl = 1'b0;
always #4000 clk = ~clk;
initial begin #1111; forever #4000.2 clk_rx = ~clk_rx; end
initial begin #1733; forever #(T_AD/2) clk_ad = ~clk_ad; end
always #200000 clk_ctrl = ~clk_ctrl;          // 2.5 MHz command consumer (control.v domain)

logic [3:0] phy_rx = 4'h0;
logic       phy_dv = 1'b0;

// ---------------------------------------------------------------------------
// Receive path

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

wire        run, wide_spectrum, discover_port, discover_cnt;
wire [ 5:0] ds_cmd_addr;
wire [31:0] ds_cmd_data;
wire        ds_cmd_cnt, ds_cmd_is_alt, ds_cmd_resprqst;
wire [ 5:0] cmd_addr;
wire [31:0] cmd_data;
wire        cmd_cnt, cmd_is_alt, cmd_resprqst;

dsopenhpsdr1 dsopenhpsdr1_i (
  .clk(clk_rx), .eth_port(to_port), .eth_broadcast(broadcast), .eth_valid(udp_rx_active),
  .eth_data(rx_data), .eth_unreachable(1'b0),
  .discover_port(discover_port), .discover_cnt(discover_cnt), .run(run), .wide_spectrum(wide_spectrum),
  .watchdog_up(1'b0), .msec_pulse(1'b0),
  .ds_cmd_addr(ds_cmd_addr), .ds_cmd_data(ds_cmd_data), .ds_cmd_cnt(ds_cmd_cnt), .ds_cmd_resprqst(ds_cmd_resprqst),
  .ds_cmd_is_alt(ds_cmd_is_alt), .ds_cmd_mask(), .ds_cmd_ptt(),
  .dseth_tdata(), .dsethiq_tvalid(), .dsethiq_tlast(), .dsethiq_tuser(), .dsethlr_tvalid(), .dsethlr_tlast(),
  .dsethasmi_tvalid(), .dsethasmi_tlast(), .asmi_cnt(), .dsethasmi_erase(), .dsethasmi_erase_ack(1'b1),
  .ds_pkt_cnt(), .cmd_addr(cmd_addr), .cmd_data(cmd_data), .cmd_rqst(1'b0));

// hermeslite_core.v CMD_MERGE
wire        inj_req, inj_ack;
wire [ 5:0] inj_addr;
wire [31:0] inj_data;
cmd_merge cmd_merge_i (.clk(clk_rx), .ds_addr(ds_cmd_addr), .ds_data(ds_cmd_data), .ds_cnt(ds_cmd_cnt),
  .ds_is_alt(ds_cmd_is_alt), .ds_resprqst(ds_cmd_resprqst), .inj_req(inj_req), .inj_addr(inj_addr),
  .inj_data(inj_data), .inj_ack(inj_ack), .addr(cmd_addr), .data(cmd_data), .cnt(cmd_cnt),
  .is_alt(cmd_is_alt), .resprqst(cmd_resprqst));

wire run_sync, cmd_rqst, discover_rqst, dest_stb;
sync       sync_run  (.clock(clk), .sig_in(run),          .sig_out(run_sync));
sync_pulse sync_cmd  (.clock(clk), .sig_in(cmd_cnt),      .sig_out(cmd_rqst));
sync_pulse sync_disc (.clock(clk), .sig_in(discover_cnt), .sig_out(discover_rqst));
sync_pulse sync_dest (.clock(clk), .sig_in(udp_destination_valid), .sig_out(dest_stb));

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
  .cmd_addr(cmd_addr), .cmd_data(cmd_data), .cmd_rqst(cmd_rqst), .dup_on(dup_on), .status(dup_status));

wire         ax_ready, ax_grant, ax_busy, ax_enable;
wire  [ 1:0] ax_tx_request;
wire  [15:0] ax_tx_length;
wire  [ 7:0] ax_tx_data;

auxchan #(.FIFO_AW(AUX_AW)) auxchan_i (
  .clk_rx(clk_rx), .eth_port(to_port), .eth_broadcast(broadcast), .eth_valid(udp_rx_active),
  .eth_data(rx_data), .clk(clk), .cmd_addr(cmd_addr), .cmd_data(cmd_data), .cmd_rqst(cmd_rqst),
  .dest_valid(aux_dest_valid), .raw_active(raw_run), .room(aux_room), .ready(ax_ready),
  .grant(ax_grant), .tx_request(ax_tx_request), .tx_length(ax_tx_length), .tx_data(ax_tx_data),
  .tx_enable(ax_enable), .busy(ax_busy));

wire         eb_ready, eb_grant, eb_busy, eb_enable;
wire  [ 1:0] eb_tx_request;
wire  [15:0] eb_tx_length;
wire  [ 7:0] eb_tx_data;
logic        eb_own = 1'b0;
wire  [29:0] wb_adr;
wire  [31:0] wb_dat_w, wb_dat_r;
wire  [ 3:0] wb_sel;
wire         wb_we, wb_cyc, wb_stb, wb_ack, wb_err;
wire  [95:0] eb_stats;

ebbridge ebbridge_i (
  .clk_rx(clk_rx), .eth_port(to_port), .eth_broadcast(broadcast), .eth_valid(udp_rx_active),
  .eth_data(rx_data), .clk(clk), .dest_valid(aux_dest_valid), .room(aux_room), .ready(eb_ready),
  .grant(eb_grant), .tx_request(eb_tx_request), .tx_length(eb_tx_length), .tx_data(eb_tx_data),
  .tx_enable(eb_enable), .busy(eb_busy), .wb_adr(wb_adr), .wb_dat_w(wb_dat_w), .wb_dat_r(wb_dat_r),
  .wb_sel(wb_sel), .wb_we(wb_we), .wb_cyc(wb_cyc), .wb_stb(wb_stb), .wb_ack(wb_ack), .wb_err(wb_err),
  .stats(eb_stats));

logic [1:0] inj_ack_s = 2'b00;
always @(posedge clk) inj_ack_s <= {inj_ack_s[0], inj_ack};

hl2bus_regs #(.VERSION_MAJOR(8'd74), .VERSION_MINOR(8'd2), .DIAG_ID(8'hf1), .CAPS(16'h001c)) regs_i (
  .clk(clk), .wb_adr(wb_adr), .wb_dat_w(wb_dat_w), .wb_dat_r(wb_dat_r), .wb_sel(wb_sel), .wb_we(wb_we),
  .wb_cyc(wb_cyc), .wb_stb(wb_stb), .wb_ack(wb_ack), .wb_err(wb_err), .bridge_stats(eb_stats),
  .tx_status(TXST), .ctrl_status(CTRL), .cmd_addr(cmd_addr), .cmd_data(cmd_data), .cmd_rqst(cmd_rqst),
  .inj_req(inj_req), .inj_addr(inj_addr), .inj_data(inj_data), .inj_ack(inj_ack_s[1]));

// aux slot shared by bridge replies (first) and aux packets
assign aux_ready = eb_ready | ax_ready;
// alternate when both wait, so neither a busy bridge client nor aux traffic starves the other
assign eb_grant  = aux_grant & eb_ready & (~ax_ready | ~eb_own);
assign ax_grant  = aux_grant & ~eb_grant;
always @(posedge clk) if (aux_grant) eb_own <= eb_grant;
assign aux_busy       = eb_busy | ax_busy;
assign eb_enable      = aux_enable & eb_own;
assign ax_enable      = aux_enable & ~eb_own;
assign aux_tx_request = eb_own ? eb_tx_request : ax_tx_request;
assign aux_tx_length  = eb_own ? eb_tx_length  : ax_tx_length;
assign aux_tx_data    = eb_own ? eb_tx_data    : ax_tx_data;

rawstream #(.FIFO_AW(RX_AW), .MAX_N_OVERRIDE(5968), .DUPLEX(1), .AUX(1)) rawstream_i (
  .clk_ad(clk_ad), .adc_data(adc), .clk(clk), .run(run_sync),
  .cmd_addr(cmd_addr), .cmd_data(cmd_data), .cmd_rqst(cmd_rqst), .raw_mode(raw_mode),
  .pkt_tx_request(pkt_req), .pkt_tx_length({5'h0, pkt_len}), .pkt_tx_data(pkt_data), .pkt_tx_enable(pkt_en),
  .udp_tx_request(udp_tx_request), .udp_tx_length(udp_tx_length), .udp_tx_data(udp_tx_data),
  .udp_tx_enable(udp_tx_enable), .udp0_tx_enable(udp0_tx_enable), .udp_tx_busy(udp_tx_busy),
  .dup_on(dup_on), .dup_status(dup_status), .tx_status(TXST),
  .aux_room(aux_room), .raw_run(raw_run), .aux_ready(aux_ready), .aux_grant(aux_grant),
  .aux_tx_request(aux_tx_request), .aux_tx_length(aux_tx_length), .aux_tx_data(aux_tx_data),
  .aux_busy(aux_busy), .udp2_tx_enable(udp2_tx_enable), .aux_enable(aux_enable));

// Discovery reply packer model
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
  f[42] = 8'hc3; f[43] = (dport == 16'd1027) ? 8'h51 : 8'h50;
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

task automatic aux_hello();
  byte unsigned p[];
  integer i;
  p = new[16];
  for (i = 0; i < 16; i = i + 1) p[i] = 8'h00;
  p[0] = 8'h5b; p[1] = 8'h01; p[2] = 8'h01;
  queue_udp(16'd1027, p, 16, 0);
endtask

// ---- Etherbone requests ----
localparam [31:0] A_ID = 32'h40000000, A_VER = 32'h40000004, A_SCR = 32'h40000008, A_CAPS = 32'h4000000c,
                  A_REQ = 32'h40000010, A_DROP = 32'h40000014, A_BERR = 32'h40000018,
                  A_RXG = 32'h40002000, A_TEMP = 32'h40003000, A_FWD = 32'h40003004, A_REV = 32'h40003008,
                  A_BIAS = 32'h4000300c, A_IN = 32'h40004000, A_TXS = 32'h40007000;

// one record: nw writes from wbase (values wv), nr reads (addresses ra); flags byte 2 = hflags
task automatic eb_request(input [7:0] hflags, input integer nw, input [31:0] wbase, input [31:0] wv[],
                          input integer nr, input [31:0] ra[], input integer truncate);
  byte unsigned p[];
  integer n, i, o;
  reg [31:0] t;
  n = 12 + ((nw > 0) ? 4 + 4 * nw : 0) + ((nr > 0) ? 4 + 4 * nr : 0);
  if (hflags[0]) n = 8;
  p = new[n];
  p[0] = 8'h4e; p[1] = 8'h6f; p[2] = hflags; p[3] = 8'h44;
  p[4] = 0; p[5] = 0; p[6] = 0; p[7] = 0;
  if (!hflags[0]) begin
    p[8] = 8'h00; p[9] = 8'h0f; p[10] = nw; p[11] = nr;
    o = 12;
    if (nw > 0) begin
      for (i = 0; i < 4; i = i + 1) p[o+i] = wbase[31-8*i -: 8];
      o = o + 4;
      for (i = 0; i < nw; i = i + 1) begin
        t = wv[i];
        p[o] = t[31:24]; p[o+1] = t[23:16]; p[o+2] = t[15:8]; p[o+3] = t[7:0];
        o = o + 4;
      end
    end
    if (nr > 0) begin
      p[o] = 8'h12; p[o+1] = 8'h34; p[o+2] = 8'h56; p[o+3] = 8'h78;   // base return address
      o = o + 4;
      for (i = 0; i < nr; i = i + 1) begin
        t = ra[i];
        p[o] = t[31:24]; p[o+1] = t[23:16]; p[o+2] = t[15:8]; p[o+3] = t[7:0];
        o = o + 4;
      end
    end
  end
  queue_udp(16'd1027, p, n - truncate, 0);
endtask

// ---------------------------------------------------------------------------
// HL2 -> PC capture

byte unsigned fr[$];
integer raw_frames = 0, pkt_frames = 0, other_frames = 0, raw_bad = 0, raw_txst_bad = 0;
longint exp_seq = -1;
integer raw_hw = 0;
integer ra_pkts = 0;
longint ra_c_exp = 0, ra_c_bytes = 0, ra_c_bad = 0, ra_c_gap = 0;
integer ra_exp_seq = -1;

byte unsigned ebq[$];                          // Etherbone reply payloads
integer       ebq_len[$];
integer       eb_replies = 0;

task automatic check_frame();
  integer len, pay, n, j, i, hl, ver, c, e;
  byte unsigned b[];
  longint seq, idx, co;
  reg [11:0] a, s;
  reg [7:0]  b1;
  len = fr.size();
  b = new[len];
  for (i = 0; i < len; i = i + 1) b[i] = fr[i];
  pay = {b[38], b[39]} - 8;
  if (pay >= 20 && b[42] == 8'ha5) begin
    raw_frames = raw_frames + 1;
    ver = b[43];
    hl  = (ver == 2) ? 40 : 20;
    if (b[45] != TXST) raw_txst_bad = raw_txst_bad + 1;
    seq = {b[46], b[47], b[48], b[49]};
    idx = {b[50], b[51], b[52], b[53], b[54], b[55]};
    n   = {b[56], b[57]};
    `CHECK(pay == hl + 3 * n / 2, $sformatf("raw payload %0d bytes, header %0d, N %0d", pay, hl, n))
    if (b[44] & 8'h10) exp_seq = 0;
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
  end else if (pay >= 44 && b[42] == 8'hb5) begin
    ra_pkts = ra_pkts + 1;
    seq = {b[46], b[47], b[48], b[49]};
    e   = {b[54], b[55]};
    co  = {b[56], b[57], b[58], b[59]};
    c   = {b[60], b[61]};
    `CHECK(pay == 44 + e + c, "aux payload length")
    if (seq == 0) ra_c_exp = 0;
    if (co != ra_c_exp) ra_c_gap = ra_c_gap + 1;
    for (j = 0; j < c; j = j + 1) if (b[86 + e + j] != aux_pat(co + j)) ra_c_bad = ra_c_bad + 1;
    ra_c_exp   = co + c;
    ra_c_bytes = ra_c_bytes + c;
  end else if (pay >= 8 && b[42] == 8'h4e && b[43] == 8'h6f) begin
    `CHECK({b[34], b[35]} == 16'd1027, "Etherbone reply source port")
    eb_replies = eb_replies + 1;
    for (j = 0; j < pay; j = j + 1) ebq.push_back(b[42 + j]);
    ebq_len.push_back(pay);
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

// Priority monitor (as tb_aux.sv)
wire raw_due = (rawstream_i.state == 4'd4) |
               ((rawstream_i.state == 4'd3) & rawstream_i.fill_ge_n & (&rawstream_i.settle));
wire aux_holds = (rawstream_i.own == 2'd2) | aux_busy;
integer due_aux_run = 0, due_aux_max = 0;
always @(posedge clk) begin
  if (raw_due & aux_holds) begin
    due_aux_run = due_aux_run + 1;
    if (due_aux_run > due_aux_max) due_aux_max = due_aux_run;
  end else due_aux_run = 0;
end

// ---------------------------------------------------------------------------
// Command consumer in a 2.5 MHz domain (control.v style): every command seen must be one
// that was sent, with its own data.

wire cmd_rqst_slow;
sync_pulse #(.DEPTH(2)) sync_cmd_slow (.clock(clk_ctrl), .sig_in(cmd_cnt), .sig_out(cmd_rqst_slow));
integer slow_rxg = 0, slow_rxg_bad = 0, slow_30 = 0, slow_30_bad = 0, slow_other = 0;
integer fast_rxg = 0;
logic [31:0] exp_rxg = 32'h0;
logic [31:0] exp_30  = 32'h0;
always @(posedge clk_ctrl) if (cmd_rqst_slow) begin
  if (cmd_addr == 6'h0a) begin
    slow_rxg = slow_rxg + 1;
    if (cmd_data != exp_rxg) slow_rxg_bad = slow_rxg_bad + 1;
  end else if (cmd_addr == 6'h30) begin
    slow_30 = slow_30 + 1;
    if (cmd_data != exp_30) slow_30_bad = slow_30_bad + 1;
  end else slow_other = slow_other + 1;
end
always @(posedge clk) if (cmd_rqst && cmd_addr == 6'h0a) fast_rxg = fast_rxg + 1;
integer collisions = 0;
logic   collide_d = 1'b0;
always @(posedge clk_rx) begin
  collide_d <= cmd_merge_i.collide;
  if (cmd_merge_i.collide & ~collide_d) collisions = collisions + 1;
end
integer alt_seen = 0;
always @(posedge clk_ctrl) if (cmd_rqst_slow && cmd_addr == 6'h0a && (cmd_is_alt || cmd_resprqst)) alt_seen = alt_seen + 1;

// ---------------------------------------------------------------------------
// Test sequence

task automatic wait_us(input integer us);
  #(us * 64'd1000000);
endtask

// wait for one Etherbone reply; returns its length (0 = none within timeout)
integer rl;
byte unsigned rb[0:1023];
task automatic eb_wait(input integer timeout_us);
  integer t, i;
  rl = 0;
  for (t = 0; t < timeout_us * 10 && ebq_len.size() == 0; t = t + 1) #100000;
  if (ebq_len.size() > 0) begin
    rl = ebq_len.pop_front();
    for (i = 0; i < rl; i = i + 1) rb[i] = ebq.pop_front();
  end
endtask

function automatic [31:0] rword(input integer o);
  return {rb[o], rb[o+1], rb[o+2], rb[o+3]};
endfunction

// read nr addresses in one record, check the reply shape, return values in rv
logic [31:0] rv[0:63];
task automatic eb_read(input [31:0] ra[], input integer nr, input string what);
  integer i;
  logic [31:0] none[];
  none = new[1];
  eb_request(8'h10, 0, 0, none, nr, ra, 0);
  eb_wait(3000);
  `CHECK(rl == 16 + 4 * nr, $sformatf("%s: reply length %0d, expected %0d", what, rl, 16 + 4 * nr))
  if (rl == 16 + 4 * nr) begin
    `CHECK(rb[0] == 8'h4e && rb[1] == 8'h6f && rb[2] == 8'h10 && rb[3] == 8'h44, $sformatf("%s: reply packet header", what))
    `CHECK(rb[9] == 8'h0f && rb[10] == nr && rb[11] == 8'h00, $sformatf("%s: reply record header", what))
    `CHECK(rword(12) == 32'h12345678, $sformatf("%s: base return address", what))
    for (i = 0; i < nr; i = i + 1) rv[i] = rword(16 + 4 * i);
  end
endtask

logic [31:0] a1[], v1[];
integer i, n0, hw0, drops0, berr0, req0, loops, loop_bad, rxg0;

initial begin
  a1 = new[64];
  v1 = new[64];
  wait_us(1);

  // Raw pattern mode (5,954 samples) and duplex configured; bridge and aux off
  exp_30 = {16'd5954, 13'd0, 3'b011};
  pc_command(6'h30, exp_30);
  pc_command(6'h31, 32'h1);
  pc_discover();
  wait_us(3);
  `CHECK(raw_mode == 1'b1, "register 0x30 not decoded")

  // 1. Probe
  eb_request(8'h11, 0, 0, v1, 0, a1, 0);
  eb_wait(3000);
  `CHECK(rl == 8 && rb[0] == 8'h4e && rb[1] == 8'h6f && rb[2] == 8'h12 && rb[3] == 8'h44, $sformatf("probe reply length %0d byte2 %02x", rl, rb[2]))
  `CHECK(aux_dest_valid == 1'b1, "aux destination not captured by an Etherbone packet")

  // 2. ID, version, scratch, capabilities, status registers
  a1[0] = A_ID; a1[1] = A_VER; a1[2] = A_SCR; a1[3] = A_CAPS; a1[4] = A_TEMP; a1[5] = A_FWD;
  a1[6] = A_REV; a1[7] = A_BIAS; a1[8] = A_IN; a1[9] = A_TXS;
  eb_read(a1, 10, "2 status read");
  `CHECK(rv[0] == 32'h484c3242, $sformatf("ID %08x", rv[0]))
  `CHECK(rv[1] == 32'h4a02f101, $sformatf("version %08x", rv[1]))
  `CHECK(rv[2] == 32'h12345678, $sformatf("scratch reset value %08x", rv[2]))
  `CHECK(rv[3] == 32'h0000001c, $sformatf("capabilities %08x", rv[3]))
  `CHECK(rv[4] == 32'h3ae && rv[5] == 32'h012 && rv[6] == 32'h034 && rv[7] == 32'h056, "slow ADC values")
  `CHECK(rv[8] == 32'h06 && rv[9] == TXST, $sformatf("inputs %08x tx status %08x", rv[8], rv[9]))

  // 3. Write scratch and read it back in the same record; then write-only (no reply)
  v1[0] = 32'hcafef00d; a1[0] = A_SCR;
  eb_request(8'h10, 1, A_SCR, v1, 1, a1, 0);
  eb_wait(3000);
  `CHECK(rl == 20 && rword(16) == 32'hcafef00d, $sformatf("write + read scratch: len %0d value %08x", rl, rword(16)))
  v1[0] = 32'h0badbeef;
  eb_request(8'h10, 1, A_SCR, v1, 0, a1, 0);
  wait_us(2000);
  `CHECK(ebq_len.size() == 0, "write-only record answered")
  eb_read(a1, 1, "3 scratch after write-only");
  `CHECK(rv[0] == 32'h0badbeef, $sformatf("scratch %08x after write-only", rv[0]))

  // 4. Errors: write to a read-only register, read an unmapped address
  a1[0] = A_BERR; eb_read(a1, 1, "4a"); berr0 = rv[0];
  v1[0] = 32'h11111111;
  eb_request(8'h10, 1, A_ID, v1, 0, a1, 0);
  a1[0] = 32'h50000000; a1[1] = A_ID; a1[2] = A_BERR;
  eb_read(a1, 3, "4 errors");
  `CHECK(rv[0] == 32'hffffffff, $sformatf("unmapped read %08x", rv[0]))
  `CHECK(rv[1] == 32'h484c3242, "ID changed by a write")
  `CHECK(rv[2] == berr0 + 2, $sformatf("bus errors %0d, expected %0d", rv[2], berr0 + 2))

  // 5. Bad packets are dropped without a reply
  a1[0] = A_DROP; eb_read(a1, 1, "5a"); drops0 = rv[0];
  a1[0] = A_ID;
  eb_request(8'h10, 0, 0, v1, 1, a1, 3);          // truncated
  eb_request(8'h10, 0, 0, v1, 65, a1, 0);         // read count above 64
  eb_request(8'h20, 0, 0, v1, 1, a1, 0);          // version 2
  wait_us(2000);
  `CHECK(ebq_len.size() == 0, "bad packets answered")
  a1[0] = A_DROP; eb_read(a1, 1, "5 drops");
  `CHECK(rv[0] == drops0 + 3, $sformatf("drops %0d, expected %0d", rv[0], drops0 + 3))

  // 6. RX gain through the command bus, with a PC command close by
  a1[0] = A_RXG; eb_read(a1, 1, "6a");
  `CHECK(rv[0] == 32'h0, $sformatf("RX gain before any command %08x", rv[0]))
  exp_rxg = 32'h0000004a;
  v1[0] = 32'hffffff4a;                           // only bits 6:0 are used
  eb_request(8'h10, 1, A_RXG, v1, 0, a1, 0);
  wait_us(300);
  exp_30 = {16'd5954, 13'd0, 3'b011};
  pc_command(6'h30, exp_30);
  wait_us(2000);
  a1[0] = A_RXG; eb_read(a1, 1, "6 RX gain");
  `CHECK(rv[0] == 32'h0000014a, $sformatf("RX gain register %08x", rv[0]))
  `CHECK(slow_rxg >= 1 && slow_rxg_bad == 0 && slow_30_bad == 0 && slow_other == 1, $sformatf("slow domain: 0x0A %0d (bad %0d), 0x30 %0d (bad %0d), other %0d", slow_rxg, slow_rxg_bad, slow_30, slow_30_bad, slow_other))
  `CHECK(alt_seen == 0, "bridge command marked as alt / response request")
  // injection racing a stream of PC commands 0x30 every ~200 us: the PC commands all arrive intact
  exp_rxg = 32'h00000055;
  v1[0] = 32'h55;
  eb_request(8'h10, 1, A_RXG, v1, 0, a1, 0);
  for (i = 0; i < 10; i = i + 1) begin wait_us(200); pc_command(6'h30, exp_30); end
  wait_us(3000);
  a1[0] = A_RXG; eb_read(a1, 1, "6 RX gain racing");
  `CHECK(rv[0] == 32'h00000155, $sformatf("RX gain register after racing %08x", rv[0]))
  `CHECK(slow_rxg_bad == 0 && slow_30_bad == 0, $sformatf("slow domain corrupted commands: 0x0A bad %0d, 0x30 bad %0d", slow_rxg_bad, slow_30_bad))
  `CHECK(slow_30 == 12, $sformatf("slow domain saw %0d of 12 PC commands 0x30", slow_30))
  // a PC command inside the guard window after an insertion (0.5 to 4 us after it): the bridge
  // command must be sent again, nothing lost or mixed
  n0 = slow_30;
  for (i = 0; i < 48; i = i + 1) begin
    exp_rxg = 32'h40 + i;
    v1[0] = exp_rxg;
    eb_request(8'h10, 1, A_RXG, v1, 0, a1, 0);
    @(posedge cmd_merge_i.guarding);
    #((i % 8) * 64'd500000);
    pc_command(6'h30, exp_30);
    wait_us(60);
  end
  wait_us(100);
  a1[0] = A_RXG; eb_read(a1, 1, "6 RX gain sweep");
  `CHECK(rv[0] == 32'h0000016f, $sformatf("RX gain register after sweep %08x", rv[0]))
  `CHECK(slow_rxg_bad == 0 && slow_30_bad == 0, $sformatf("sweep: corrupted commands 0x0A bad %0d, 0x30 bad %0d", slow_rxg_bad, slow_30_bad))
  // a PC command right after an insertion can be read twice by the 2.5 MHz domain (the bridge
  // command is then sent again); none may be lost or mixed
  `CHECK(slow_30 >= n0 + 48 && slow_30 <= n0 + 96, $sformatf("sweep: slow domain saw %0d of 48 PC commands", slow_30 - n0))
  `CHECK(collisions > 0, "sweep: no PC command landed in the guard window (test did not exercise the retry)")
  $display("6: slow 0x0A=%0d fast 0x0A=%0d 0x30=%0d collisions=%0d", slow_rxg, fast_rxg, slow_30, collisions);

  // 7. Full-rate raw + TX stream, aux counter stream 12 Mbit/s, bridge reads of 64 words in a loop
  pc_startstop(8'h81);
  wait_us(3000);
  hw0 = raw_hw;
  aux_hello();
  pc_command(6'h32, {16'd1500, 13'd0, 3'b101});  // aux on, counter stream
  wait_us(1000);
  due_aux_max = 0;
  for (i = 0; i < 64; i = i + 1) a1[i] = (i % 2) ? A_ID : A_TXS;
  a1[5] = A_REQ;
  loops = 0; loop_bad = 0;
  a1[5] = A_ID;
  n0 = raw_frames; rxg0 = ra_c_bytes;
  repeat (100) begin
    eb_read(a1, 64, "7 burst read");
    loops = loops + 1;
    for (i = 0; i < 64; i = i + 1) if (rv[i] != ((i % 2) ? 32'h484c3242 : TXST)) loop_bad = loop_bad + 1;
  end
  $display("7: raw frames=%0d bad=%0d txstatus bad=%0d hw=%0d (base %0d) due-wait max=%0d | bridge loops=%0d bad=%0d | counter bytes=%0d bad=%0d gaps=%0d",
           raw_frames, raw_bad, raw_txst_bad, raw_hw, hw0, due_aux_max, loops, loop_bad, ra_c_bytes, ra_c_bad, ra_c_gap);
  $display("7: raw frames in the loop %0d, counter bytes %0d", raw_frames - n0, ra_c_bytes - rxg0);
  `CHECK(raw_frames - n0 >= 50 && raw_bad == 0 && raw_txst_bad == 0, "stream: raw frames, pattern or status byte wrong")
  `CHECK(raw_hw <= hw0 + 16, $sformatf("stream: raw FIFO peak %0d, %0d before", raw_hw, hw0))
  `CHECK(due_aux_max <= AUX_BOUND, $sformatf("stream: raw frame waited %0d cycles on aux/bridge", due_aux_max))
  `CHECK(loop_bad == 0, "stream: bridge values wrong")
  `CHECK(ra_c_bad == 0 && ra_c_gap == 0, "stream: aux counter stream errors")
  `CHECK(ra_c_bytes - rxg0 > (raw_frames - n0) * 78 * 1500 / 3000, "stream: aux counter stream starved by bridge replies")

  // 8. Stop, discovery
  pc_command(6'h32, 32'h0);
  pc_startstop(8'h00);
  wait_us(2000);
  pc_discover();
  wait_us(1000);
  a1[0] = A_REQ; a1[1] = A_DROP; a1[2] = A_BERR;
  eb_read(a1, 3, "8 counters");
  $display("bridge requests=%0d drops=%0d bus errors=%0d replies=%0d | discovery %0d/%0d other=%0d",
           rv[0], rv[1], rv[2], eb_replies, pkt_frames, disc_sent, other_frames);
  `CHECK(rv[1] == drops0 + 3, "unexpected drops during streaming")
  `CHECK(pkt_frames == disc_sent, "discovery replies lost")
  `CHECK(other_frames == 0, "unexpected frames from the HL2")

  if (errors == 0) $display("PASS");
  else $display("FAIL: %0d errors", errors);
  $finish;
end

endmodule
