//
//  Hermes Lite
//
//
//  This program is free software; you can redistribute it and/or modify
//  it under the terms of the GNU General Public License as published by
//  the Free Software Foundation; either version 2 of the License, or
//  (at your option) any later version.
//
//  This program is distributed in the hope that it will be useful,
//  but WITHOUT ANY WARRANTY; without even the implied warranty of
//  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
//  GNU General Public License for more details.
//
//  You should have received a copy of the GNU General Public License
//  along with this program; if not, write to the Free Software
//  Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

// (C) Steve Haynal KF7O 2014-2019
// Modified 2026 by Franz Schöning
// This RTL originated from www.openhpsdr.org and has been modified to support
// the Hermes-Lite hardware described at http://github.com/softerhardware/Hermes-Lite2.

module hermeslite_core (
  // Power
  output       pwr_clk3p3                ,
  output       pwr_clk1p2                ,
  output       pwr_envpa                 ,
  output       pwr_envop                 ,
  output       pwr_envbias               ,
  // Ethernet PHY
  input        phy_clk125                ,
  output [3:0] phy_tx                    ,
  output       phy_tx_en                 ,
  output       phy_tx_clk                ,
  input  [3:0] phy_rx                    ,
  input        phy_rx_dv                 ,
  input        phy_rx_clk                ,
  input        phy_rst_n                 ,
  inout        phy_mdio                  ,
  output       phy_mdc                   ,
  // Clock
  inout        clk_sda1                  ,
  inout        clk_scl1                  ,
  // RF Frontend
  output       rffe_ad9866_rst_n         ,
  output [5:0] rffe_ad9866_tx            ,
  input  [5:0] rffe_ad9866_rx            ,
  input        rffe_ad9866_rxsync        ,
  input        rffe_ad9866_rxclk         ,
  output       rffe_ad9866_txquiet_n     ,
  output       rffe_ad9866_txsync        ,
  output       rffe_ad9866_sdio          ,
  output       rffe_ad9866_sclk          ,
  output       rffe_ad9866_sen_n         ,
  input        rffe_ad9866_clk76p8       ,
  output       rffe_rfsw_sel             ,
  output       rffe_ad9866_mode          ,
  output       rffe_ad9866_pga5          ,
  // IO
  output       io_led_run                ,
  output       io_led_tx                 ,
  output       io_led_adc75              ,
  output       io_led_adc100             ,
  //
  output       io_tx_envelope_pwm_out    ,
  output       io_tx_envelope_pwm_out_inv,
  //
  input        io_tx_inhibit             ,
  input        io_id_hermeslite          ,
  input        io_alternate_mac          ,
  //
  inout        io_adc_scl                ,
  inout        io_adc_sda                ,
  inout        io_scl2                   ,
  inout        io_sda2                   ,
  output       io_uart_txd               ,
  input        io_uart_rxd               ,
  output       io_cw_keydown             ,
  input        io_phone_tip              ,
  input        io_phone_ring             ,
  input        io_atu_ack                ,
  output       io_atu_req                ,
  output       pa_inttr                  ,
  output       pa_exttr                  ,
  // AK4951
  output       pa_exttr_clone            , // AK4951 Companion Board V3
  input        io_ptt_in                 , // AK4951 Companion Board V3
  output       i2s_pdn                   ,
  output       i2s_bck                   ,
  output       i2s_lrck                  ,
  input        i2s_miso                  ,
  output       i2s_mosi                  ,
  //
  output       fan_pwm                   ,
  input  [1:0] linkrx                    ,
  output [1:0] linktx                    ,
  output [3:0] debug_out                 ,
  input  [3:0] io_tp                         // test points TP2, TP7, TP8, TP9 (read only, RAWFRONT = 1)
);


// PARAMETERS
parameter       BOARD = 5;
parameter       IP = {8'd0,8'd0,8'd0,8'd0};
parameter       MAC = {8'h00,8'h1c,8'hc0,8'ha2,8'h13,8'hdd};
parameter       NR = 4; // Recievers
parameter       NT = 1; // Transmitters
parameter       CLK_FREQ = 76800000;

// UART Type 0 is none, 1 is JI1UDD HR50
parameter       UART = 0;

// ATU Type 0 is none, 1 is JI1UDD ATU
parameter       ATU = 0;

parameter       FAN = 0;    // Generate fan support
parameter       PSSYNC = 0; // Generate power supply sync frequency

parameter       CW = 0; // CW Support

// Downstream audio channel usage:
//   0=not used, 1=predistortion, 2=TX envelope PWM
//   when using the TX envelope PWM reduce the number of receivers (NR) above by 1
parameter       LRDATA = 0;

// Use ASMII for EEPROM configuration
parameter       ASMII = 0;

parameter       HL2LINK = 0;

parameter       FAST_LNA = 0; // Support for fast LNA setting, TX/RX values

parameter       AK4951 = 0;
parameter       EXTENDED_RESP = 1;
parameter       EXTENDED_DEBUG_RESP = 0;

parameter       DSIQ_FIFO_DEPTH = 16384;

parameter       BYPASS_VERSA = 0;

// Raw ADC stream test sender (rtl/rawstream.v), 0 = not built
parameter       RAWSTREAM = 0;
parameter       RAWSTREAM_FIFO_AW = 14; // raw stream FIFO depth = 2**RAWSTREAM_FIFO_AW samples
parameter       RAWSTREAM_MAX_N = 0;    // 0 = default largest frame for the FIFO depth

// Duplex raw stream test: PC -> HL2 TX sample sink on UDP port 1026 (rtl/txsink.v),
// needs RAWSTREAM = 1. Also accepts jumbo UDP packets in the network receive path.
parameter       DUPLEX = 0;
parameter       DUPLEX_FIFO_AW = 14;    // TX sink FIFO depth = 2**DUPLEX_FIFO_AW samples

// Aux data channel for the raw stream test (rtl/auxchan.v): bytes both ways in UDP packets on
// port 1027, sent in the gaps of the raw stream. Needs RAWSTREAM = 1.
parameter       AUX = 0;
parameter       AUX_FIFO_AW = 12;       // echo FIFO depth = 2**AUX_FIFO_AW bytes

// 0 = front-end image: no receivers (radio.v DDC chain) and no openHPSDR IQ/bandscope FIFOs.
// Discovery, commands, control.v functions, network flashing and the raw stream stay.
parameter       RADIO = 1;

// Layer-1 register bridge (rtl/hl2bus.v): Etherbone-format register access on the aux port
// 1027 and a command-bus merge for the bridge's RX gain register. Needs RAWSTREAM = 1, AUX = 1.
parameter       HL2BUS = 0;

// Soft RISC-V CPU system (rtl/hl2cpu.v) behind the register bridge: boot ROM, RAM, packet interface
// on port 1027, flash-sector access for saved firmware. Needs HL2BUS = 1 and ASMII = 1.
// 1 = VexRiscv Min (docs/rawfront/RISCV.md), 2 = NEORV32 rv32imc (docs/rawfront/RISCV.md).
parameter       CPU = 0;
parameter       CPU_ROM_WORDS = 1536;   // boot ROM, 32-bit words (6 kB)
parameter       CPU_RAM_WORDS = 4096;   // RAM, 32-bit words
parameter       CPU_CLK_25 = 0;         // CPU system clock: 0 = 12.5 MHz (ethpll c4), 1 = 25 MHz (ethpll c3)

// Raw front-end release image (docs/rawfront/PROTOCOL.md). Needs RAWSTREAM, DUPLEX, AUX, HL2BUS and
// CPU. Adds the hardware transmit interlock and the front-end I/O register block (rtl/hl2io.v, 0x4004_0000),
// drives the real AD9866 transmit DAC from the duplex TX samples while the interlock allows it, echo mode
// and the 48-byte duplex header, the bias-pot guard, I2C status and address probes, LED and fan overrides.
parameter       RAWFRONT = 0;

// Diagnostic image marker, sent in discovery reply byte 0x0C (0 in stock images and in
// every factory image, so a nonzero value proves the image itself is running)
parameter       DIAG_ID = 8'h00;

localparam      TUSERWIDTH = (AK4951 == 1) ? 16 : 2;

localparam      VERSION_MAJOR = (BOARD==2) ? 8'd54 : 8'd74;
localparam      VERSION_MINOR = 8'd2;

logic   [5:0]   cmd_addr;
logic   [31:0]  cmd_data;
logic           cmd_cnt;
logic           cmd_is_alt;
logic           cmd_resprqst;

logic   [5:0]   ds_cmd_addr;
logic   [31:0]  ds_cmd_data;
logic           ds_cmd_cnt;
logic           ds_cmd_is_alt;
logic   [1:0]   ds_cmd_mask;
logic           ds_cmd_resprqst;
logic           ds_cmd_ptt, ds_cmd_ptt_ad9866sync;

logic           tx_on, tx_on_iosync;
logic           cw_on, cw_on_iosync;
logic           cw_keydown, cw_keydown_ad9866sync;
logic           ext_ptt, ext_ptt_ad9866sync;
logic   [18:0]  cw_profile;

logic   [7:0]   dseth_tdata;

logic   [35:0]  dsiq_tdata;
logic           dsiq_tready;    // controls reading of fifo
logic           dsiq_tvalid;
logic           dsiq_sample, dsiq_sample_ad9866sync;
logic   [7:0]   dsiq_status;
logic           dsiq_twait;

logic           dsethiq_tvalid;
logic           dsethiq_tlast;
logic           dsethiq_tuser;

logic   [35:0]  dslr_tdata;
logic           dslr_tready;    // controls reading of fifo
logic           dslr_tvalid;
logic           dsethlr_tvalid;
logic           dsethlr_tlast;
logic           dsethlr_tuser;

logic  [23:0]   rx_tdata;
logic           rx_tlast;
logic           rx_tready;
logic           rx_tvalid;
logic  [ 1:0]   rx_tuser;

logic  [23:0]   usiq_tdata;
logic           usiq_tlast;
logic           usiq_tready;
logic           usiq_tvalid;

logic  [TUSERWIDTH-1:0]   usiq_tuser;

logic  [10:0]   usiq_tlength;

logic           bs_tvalid;
logic           bs_tready;
logic [11:0]    bs_tdata;

logic           cmd_rqst_usopenhpsdr1;
logic           cmd_rqst_dsopenhpsdr1;

logic           clock_125_mhz_0_deg;
logic           clock_125_mhz_90_deg;
logic           clock_25_mhz;
logic           clock_12p5_mhz;
wire            clock_cpu = (CPU_CLK_25 != 0) ? clock_25_mhz : clock_12p5_mhz;   // soft CPU system (CPU != 0)
logic           ethpll_locked;
logic           clock_ethtxint;
logic           clock_ethtxext;
logic           clock_ethrxint;
logic           speed_1gb;
logic           speed_1gb_clksel = 1'b0;

logic           phy_rx_clk_div2 = 1'b0;
logic           ethup;

logic           clk_ad9866;
logic           clk_ad9866_2x;
logic           clk_envelope;
logic           clk_ad9866_slow;
logic           ad9866up;
logic           ad9866_rst;

logic           run, run_sync, run_iosync, run_ad9866sync;
logic           wide_spectrum, wide_spectrum_sync;
logic           discover_port;
logic           discover_cnt;
logic           discover_rqst_usopenhpsdr1;

logic           dst_unreachable;

logic [ 1:0]    udp_tx_request;
logic [ 7:0]    udp_tx_data;
logic [15:0]    udp_tx_length;
logic           udp_tx_enable;
logic           udp_tx_busy;
logic           udp0_tx_enable;
logic           udp2_tx_enable;
logic           aux_dest_valid;

// openHPSDR packer side of the UDP send path (shared with the raw stream sender)
logic [ 1:0]    pkt_udp_tx_request;
logic [ 7:0]    pkt_udp_tx_data;
logic [10:0]    pkt_udp_tx_length;
logic           pkt_udp_tx_enable;
logic           raw_mode;
logic           tx_on_int, cw_on_int;

logic [15:0]    to_port;
logic           broadcast;
logic           udp_rx_active;
logic [ 7:0]    udp_rx_data;

logic           network_state_dhcp, network_state_fixedip;
logic [ 1:0]    network_speed;
logic           phy_connected;
logic           is_ksz9021;

logic [47:0]    local_mac;

logic           cmd_rqst_ad9866;
logic [11:0]    rx_data;
logic [11:0]    tx_data;

logic           sda1_i;
logic           sda1_o;
logic           sda1_t;
logic           scl1_i;
logic           scl1_o;
logic           scl1_t;

logic           sda2_i;
logic           sda2_o;
logic           sda2_t;
logic           scl2_i;
logic           scl2_o;
logic           scl2_t;

logic           sda3_i;
logic           sda3_o;
logic           sda3_t;
logic           scl3_i;
logic           scl3_o;
logic           scl3_t;

logic           cmd_rqst_io;
logic           clk_ctrl;

logic           rxclip, rxclip_iosync;
logic           rxgoodlvl, rxgoodlvl_iosync;
logic           rxclrstatus, rxclrstatus_ad9866sync;

logic [39:0]    resp;
logic           resp_rqst, resp_rqst_iosync;

logic           watchdog_up, watchdog_up_sync;

logic           dsethasmi_erase, dsethasmi_erase_ack;
logic           usethasmi_send_more, usethasmi_erase_done, usethasmi_ack;
logic [13:0]    asmi_cnt = 14'h0000;
logic           dsethasmi_tvalid;

logic  [31:0]   static_ip;
logic  [15:0]   alt_mac;
logic  [ 7:0]   eeprom_config;

logic           hl2_reset;

logic           qmsec_pulse, qmsec_pulse_ad9866sync;
logic           msec_pulse, msec_pulse_ethsync;

logic           atu_txinhibit, atu_txinhibit_ad9866ync;

logic        stall_req, stall_req_sync;
logic        stall_ack, stall_ack_ad9866;
logic        rst_all, rst_nco;
logic        link_running;
logic        link_master ;
logic [23:0] lm_data     ;
logic        lm_valid    ;
logic        ls_valid    ;
logic        ls_done     ;


logic        clk_i2c_rst;
logic [15:0] au_rdata   ;

logic        alt_resp_cnt              ;
logic        alt_resp_rqst_usopenhpsdr1;
logic [31:0] resp_data                 ;
logic [ 7:0] resp_control              ;
logic [11:0] temperature               ;
logic [11:0] fwdpwr                    ;
logic [11:0] revpwr                    ;
logic [11:0] bias                      ;
logic [ 7:0] control_dsiq_status       ;
logic        ds_pkt_cnt                ;
logic        ds_pkt_usopenhpsdr1       ;

logic        hl2link_rst_req, hl2link_rst_ack;

logic [ 4:0] safety_status             ;  // control.v, clk_ctrl domain
logic [ 7:0] tx_status                 ;  // raw frame header byte 3, clock_ethtxint domain
logic        bus_inj_req, bus_inj_ack  ;
logic [ 5:0] bus_inj_addr              ;
logic [31:0] bus_inj_data              ;

// CPU system signals (CPU = 1)
logic        cpu_fl_req, cpu_fl_done;
logic [ 2:0] cpu_fl_cmd, cpu_fl_status;
logic [23:0] cpu_fl_addr;
logic [ 7:0] cpu_fl_data, cpu_fl_rdata;
logic        cpu_led_en, cpu_led_on;
logic        led_adc100_ctrl;

// Raw front-end image (RAWFRONT = 1)
logic        ilk_pwr_envpa, ilk_pwr_envop, ilk_pwr_envbias, ilk_pa_inttr, ilk_pa_exttr, ilk_rfsw_sel;
logic        ilk_dac_en, ilk_tx_on;
logic [31:0] ilk_status;
logic        ctrl_pwr_envpa, ctrl_pwr_envop, ctrl_pwr_envbias, ctrl_pa_inttr, ctrl_pa_exttr, ctrl_rfsw_sel;
logic        bias_unlock_c;
logic [ 7:0] led_ovr_c;
logic [ 3:0] fan_min_c;
logic        io_inj_req, io_inj_ack;
logic [ 5:0] io_inj_addr;
logic [31:0] io_inj_data;
logic [55:0] ctrl_i2c_status;
logic        adc_tick, fan_overheat;
logic [15:0] adc_seq;
logic [ 3:0] fan_status;
logic [ 2:0] pa_cfg;
logic        txs_real, txs_echo;
logic [11:0] txs_dac;

logic [15:0] debug;
//assign debug_out = debug[3:0];
logic link_error;
assign debug_out = {cmd_rqst_ad9866,debug[2],link_error,debug[0]};


/////////////////////////////////////////////////////
// Clocks

ethpll ethpll_inst (
    .inclk0   (phy_clk125),   //  refclk.clk
    .c0 (clock_125_mhz_0_deg), // outclk0.clk
    .c1 (clock_125_mhz_90_deg), // outclk1.clk
    .c2 (clk_ctrl), // outclk2.clk
    .c3 (clock_25_mhz),
    .c4 (clock_12p5_mhz),
    .locked (ethpll_locked)
);

always @(posedge clk_ctrl)
  speed_1gb_clksel <= speed_1gb;

altclkctrl #(
    .clock_type("AUTO"),
    //.intended_device_family("Cyclone IV E"),
    //.ena_register_mode("none"),
    //.implement_in_les("OFF"),
    .number_of_clocks(2),
    //.use_glitch_free_switch_over_implementation("OFF"),
    .width_clkselect(1)
    //.lpm_type("altclkctrl"),
    //.lpm_hint("unused")
    ) ethtxint_clkmux_i
(
    .clkselect(speed_1gb_clksel),
    .ena(1'b1),
    .inclk({clock_125_mhz_0_deg,clock_12p5_mhz}),
    .outclk(clock_ethtxint)
);


altclkctrl #(
    .clock_type("AUTO"),
    //.intended_device_family("Cyclone IV E"),
    //.ena_register_mode("none"),
    //.implement_in_les("OFF"),
    .number_of_clocks(2),
    //.use_glitch_free_switch_over_implementation("OFF"),
    .width_clkselect(1)
    //.lpm_type("altclkctrl"),
    //.lpm_hint("unused")
    ) ethtxext_clkmux_i
(
    .clkselect(speed_1gb_clksel),
    .ena(1'b1),
    .inclk({clock_125_mhz_90_deg,clock_25_mhz}),
    .outclk(clock_ethtxext)
);

assign phy_tx_clk = clock_ethtxext;

always @(posedge phy_rx_clk) begin
  phy_rx_clk_div2 <= ~phy_rx_clk_div2;
end

assign clock_ethrxint = speed_1gb_clksel ? phy_rx_clk : phy_rx_clk_div2;

// Infer above as altclkctrl does not map correctly in Quartus for this case
//altclkctrl #(
//    .clock_type("AUTO"),
//    //.intended_device_family("Cyclone IV E"),
//    //.ena_register_mode("none"),
//    //.implement_in_les("OFF"),
//    .number_of_clocks(2),
//    //.use_glitch_free_switch_over_implementation("OFF"),
//    .width_clkselect(1)
//    //.lpm_type("altclkctrl"),
//    //.lpm_hint("unused")
//    ) ethrxint_clkmux_i
//(
//    .clkselect(speed_1gb_clksel),
//    .ena(1'b1),
//    .inclk({phy_rx_clk,phy_rx_clk_div2}),
//    .outclk(clock_ethrxint)
//);


// phy_rst_n will go high after ~50ms due to RC
// ethpll_locked will go high once pll is locked
assign ethup = ethpll_locked & phy_rst_n;

// ethup starts I2C configuration of the Versa
// the PLL may lock twice the frequency changes


ad9866pll ad9866pll_inst (
  .inclk0   (rffe_ad9866_clk76p8),   //  refclk.clk
  .areset   (~ethup),      //   reset.reset
  .c0 (clk_ad9866), // outclk0.clk
  .c1 (clk_ad9866_2x), // outclk1.clk
  .c2 (clk_envelope),
  .c3 (clk_ad9866_slow),
  .locked (ad9866up)
);



/////////////////////////////////////////////////////
// Network

assign local_mac = eeprom_config[6] ? {MAC[47:16],alt_mac} : {MAC[47:2],~io_alternate_mac,MAC[0]};

network #(.RX_JUMBO((DUPLEX != 0) || (AUX != 0)), .AUX(AUX)) network_inst(

  .clock_2_5MHz(clk_ctrl),

  .tx_clock(clock_ethtxint),
  .udp_tx_request(udp_tx_request),
  .udp_tx_length(udp_tx_length),
  .udp_tx_data(udp_tx_data),
  .udp_tx_enable(udp_tx_enable),
  .udp_tx_busy(udp_tx_busy),
  .udp0_tx_enable(udp0_tx_enable),
  .udp2_tx_enable(udp2_tx_enable),
  .aux_dest_valid(aux_dest_valid),
  .run(run_sync),
  .port_id(8'h00),

  .rx_clock(clock_ethrxint),
  .to_port(to_port),
  .udp_rx_data(udp_rx_data),
  .udp_rx_active(udp_rx_active),
  .broadcast(broadcast),
  .dst_unreachable(dst_unreachable),

  .eeprom_config(eeprom_config),
  .static_ip(static_ip),
  .local_mac(local_mac),
  .speed_1gb(speed_1gb),
  .network_state_dhcp(network_state_dhcp),
  .network_state_fixedip(network_state_fixedip),
  .network_speed(network_speed),
  .phy_connected(phy_connected),
  .is_ksz9021(is_ksz9021),

  .PHY_TX(phy_tx),
  .PHY_TX_EN(phy_tx_en),
  .PHY_RX(phy_rx),
  .PHY_DV(phy_rx_dv),

  .PHY_MDIO(phy_mdio),
  .PHY_MDC(phy_mdc)
);



///////////////////////////////////////////////
// Downstream ethrxint clock domain

sync_pulse sync_pulse_watchdog (
  .clock(clock_ethrxint),
  .sig_in(watchdog_up),
  .sig_out(watchdog_up_sync)
);

// CDC okay as clock is >2x faster than sig_in domain
sync_one sync_msec_pulse_eth (
  .clock(clock_ethrxint),
  .sig_in(msec_pulse),
  .sig_out(msec_pulse_ethsync)
);

sync_pulse sync_pulse_dsopenhpsdr1 (
  .clock(clock_ethrxint),
  .sig_in(cmd_cnt),
  .sig_out(cmd_rqst_dsopenhpsdr1)
);

dsopenhpsdr1 dsopenhpsdr1_i (
  .clk(clock_ethrxint),
  .eth_port(to_port),
  .eth_broadcast(broadcast),
  .eth_valid(udp_rx_active),
  .eth_data(udp_rx_data),
  .eth_unreachable(dst_unreachable),

  .discover_port(discover_port),
  .discover_cnt(discover_cnt),

  .run(run),
  .wide_spectrum(wide_spectrum),

  .watchdog_up(watchdog_up_sync),

  .msec_pulse(msec_pulse_ethsync),

  .ds_cmd_addr(ds_cmd_addr),
  .ds_cmd_data(ds_cmd_data),
  .ds_cmd_cnt(ds_cmd_cnt),
  .ds_cmd_resprqst(ds_cmd_resprqst),
  .ds_cmd_is_alt(ds_cmd_is_alt),
  .ds_cmd_mask(ds_cmd_mask),
  .ds_cmd_ptt(ds_cmd_ptt),

  .dseth_tdata(dseth_tdata),
  .dsethiq_tvalid(dsethiq_tvalid),
  .dsethiq_tlast(dsethiq_tlast),
  .dsethiq_tuser(dsethiq_tuser),
  .dsethlr_tvalid(dsethlr_tvalid),
  .dsethlr_tlast(dsethlr_tlast),

  .dsethasmi_tvalid(dsethasmi_tvalid),
  .dsethasmi_tlast(),
  .asmi_cnt(asmi_cnt),
  .dsethasmi_erase(dsethasmi_erase),
  .dsethasmi_erase_ack(dsethasmi_erase_ack),

  .ds_pkt_cnt(ds_pkt_cnt),

  .cmd_addr(cmd_addr),
  .cmd_data(cmd_data),
  .cmd_rqst(cmd_rqst_dsopenhpsdr1)
);


generate

if (NT != 0) begin

dsiq_fifo #(.depth(DSIQ_FIFO_DEPTH)) dsiq_fifo_i (
  .wr_clk(clock_ethrxint),
  .wr_tdata({dsethiq_tuser,dseth_tdata}),
  .wr_tvalid(dsethiq_tvalid),
  .wr_tready(),
  .wr_tlast(dsethiq_tlast),

  .rd_clk(clk_ad9866),
  .rd_tdata(dsiq_tdata),
  .rd_tvalid(dsiq_tvalid),
  .rd_tready(dsiq_tready),
  .rd_sample(dsiq_sample_ad9866sync),
  .rd_status(dsiq_status)
);

sync_pulse sync_pulse_dsiq_sample (
  .clock(clk_ad9866),
  .sig_in(dsiq_sample),
  .sig_out(dsiq_sample_ad9866sync)
);

end else begin
  assign dsiq_tdata = 36'b0;
  assign dsiq_tvalid = 1'b0;
  assign dsiq_status = 8'b0;
end
endgenerate


generate if (AK4951 == 0) begin

case (LRDATA)
  0: begin // Left/Right downstream (PC->Card) audio data not used
    assign dslr_tvalid = 1'b0;
    assign dslr_tdata = 36'h0;
  end
  1: begin: PD2 // TX predistortion
    // simple fifo to get predistortion tables
    dslr_fifo dslr_fifo_i (
      .wr_clk(clock_ethrxint),
      .wr_tdata({1'b0,dseth_tdata}),
      .wr_tvalid(dsethlr_tvalid),
      .wr_tready(),

      .rd_clk(clk_ad9866),
      .rd_tdata(dslr_tdata),
      .rd_tvalid(dslr_tvalid),
      .rd_tready(dslr_tready)
    );
  end
  2: begin // TX envelope PWM generation for ET/EER
    // need to use same fifo as the TX I/Q data to keep the envelope in sync
    dsiq_fifo #(.depth(DSIQ_FIFO_DEPTH)) dslr_fifo_i (
      .wr_clk(clock_ethrxint),
      .wr_tdata({1'b0,dseth_tdata}),
      .wr_tvalid(dsethlr_tvalid),
      .wr_tready(),
      .wr_tlast(dsethlr_tlast),

      .rd_clk(clk_ad9866),
      .rd_tdata(dslr_tdata),
      .rd_tvalid(dslr_tvalid),
      .rd_tready(dslr_tready)
    );
  end
endcase
end
endgenerate


///////////////////////////////////////////////
// Upstream ethtxint clock domain

sync sync_inst2(.clock(clock_ethtxint), .sig_in(run), .sig_out(run_sync));
sync sync_inst3(.clock(clock_ethtxint), .sig_in(wide_spectrum), .sig_out(wide_spectrum_sync));

sync_pulse sync_pulse_usopenhpsdr1 (
  .clock(clock_ethtxint),
  .sig_in(cmd_cnt),
  .sig_out(cmd_rqst_usopenhpsdr1)
);

sync_pulse sync_discover_usopenhpsdr1 (
  .clock(clock_ethtxint),
  .sig_in(discover_cnt),
  .sig_out(discover_rqst_usopenhpsdr1)
);

sync_pulse sync_resp_usopenhpsdr1 (
  .clock(clock_ethtxint),
  .sig_in(alt_resp_cnt),
  .sig_out(alt_resp_rqst_usopenhpsdr1)
);

sync_pulse sync_pkt_cnt_usopenhpsdr1 (
  .clock(clock_ethtxint),
  .sig_in(ds_pkt_cnt),
  .sig_out(ds_pkt_usopenhpsdr1)
);

usopenhpsdr1 #(
  .NR(NR),
  .VERSION_MAJOR(VERSION_MAJOR),
  .VERSION_MINOR(VERSION_MINOR),
  .BOARD(BOARD),
  .AK4951(AK4951),
  .EXTENDED_DEBUG_RESP(EXTENDED_DEBUG_RESP),
  .DIAG_ID(DIAG_ID)
) usopenhpsdr1_i (
  .clk(clock_ethtxint),
  .have_ip(~(network_state_dhcp & network_state_fixedip)), // network_state is on sync 2.5 MHz domain
  .run(run_sync),
  .wide_spectrum(wide_spectrum_sync & ~raw_mode),
  .idhermeslite(io_id_hermeslite),
  .mac(local_mac),

  .discover_port(discover_port),
  .discover_rqst(discover_rqst_usopenhpsdr1),

  .udp_tx_enable(pkt_udp_tx_enable),
  .udp_tx_request(pkt_udp_tx_request),
  .udp_tx_data(pkt_udp_tx_data),
  .udp_tx_length(pkt_udp_tx_length),

  .bs_tdata(bs_tdata),
  .bs_tready(bs_tready),
  .bs_tvalid(bs_tvalid),

  .us_tdata(usiq_tdata),
  .us_tlast(usiq_tlast),
  .us_tready(usiq_tready),
  .us_tvalid(usiq_tvalid & ~raw_mode),
  .us_tuser(usiq_tuser),
  .us_tlength(usiq_tlength),

  .cmd_addr(cmd_addr),
  .cmd_data(cmd_data),
  .cmd_rqst(cmd_rqst_usopenhpsdr1),

  .resp(resp),
  .resp_rqst(resp_rqst),

  .stall_req(stall_req_sync),
  .stall_ack(stall_ack),

  .static_ip(static_ip),
  .alt_mac(alt_mac),
  .eeprom_config(eeprom_config),

  .watchdog_up(watchdog_up),

  .usethasmi_send_more(usethasmi_send_more),
  .usethasmi_erase_done(usethasmi_erase_done),
  .usethasmi_ack(usethasmi_ack),

  .ds_cmd_ptt(ds_cmd_ptt),
  .ds_pkt(ds_pkt_usopenhpsdr1),
  .ds_wait(dsiq_twait),
  .alt_resp_rqst(alt_resp_rqst_usopenhpsdr1),
  .resp_data(resp_data),
  .resp_control(resp_control),
  .temperature(temperature),
  .fwdpwr(fwdpwr),
  .revpwr(revpwr),
  .bias(bias),
  .dsiq_status(control_dsiq_status),
  .master_link_running(link_running & link_master)
);

generate if (RADIO != 0) begin: USIQ_ON
usiq_fifo #(.AK4951(AK4951))
  usiq_fifo_i
(
  .wr_clk(clk_ad9866),
  .wr_tdata(rx_tdata),
  .wr_tvalid(rx_tvalid),
  .wr_tready(rx_tready),
  .wr_tlast(rx_tlast),
  .wr_tuser( (AK4951 == 1) ? au_rdata : rx_tuser),
  //.wr_tuser( vna? {14'b0,rx_tuser} : au_rdata ),
  .wr_aclr(rst_all),

  .rd_clk(clock_ethtxint),
  .rd_tdata(usiq_tdata),
  .rd_tvalid(usiq_tvalid),
  .rd_tready(usiq_tready),
  .rd_tlast(usiq_tlast),
  .rd_tuser(usiq_tuser),
  .rd_tlength(usiq_tlength)
);
end else begin: USIQ_OFF
  assign usiq_tdata   = 24'd0;
  assign usiq_tvalid  = 1'b0;
  assign usiq_tlast   = 1'b0;
  assign usiq_tuser   = '0;
  assign usiq_tlength = 11'd0;
  assign rx_tready    = 1'b0;
end
endgenerate


generate
if (RAWSTREAM != 0) begin: RAWSTREAM_ON

logic         dup_on;
logic [159:0] dup_status;
logic [11:0]  echo_data;
logic [47:0]  echo_idx;
logic         echo_ok;
logic         echo_play;

if (DUPLEX != 0) begin: DUPLEX_ON

txsink #(.FIFO_AW(DUPLEX_FIFO_AW), .ECHO(RAWFRONT)) txsink_i (
  .clk_rx        (clock_ethrxint        ),
  .eth_port      (to_port               ),
  .eth_broadcast (broadcast             ),
  .eth_valid     (udp_rx_active         ),
  .eth_data      (udp_rx_data           ),
  .clk_ad        (clk_ad9866            ),
  .clk           (clock_ethtxint        ),
  .raw_mode      (raw_mode              ),
  .run           (run_sync              ),
  .cmd_addr      (cmd_addr              ),
  .cmd_data      (cmd_data              ),
  .cmd_rqst      (cmd_rqst_usopenhpsdr1 ),
  .dup_on        (dup_on                ),
  .status        (dup_status            ),
  .mode_real     (txs_real              ),
  .mode_echo     (txs_echo              ),
  .dac_out       (txs_dac               ),
  .echo_data     (echo_data             ),
  .echo_idx      (echo_idx              ),
  .echo_ok       (echo_ok               ),
  .echo_play     (echo_play             )
);

end else begin: DUPLEX_OFF
  assign dup_on     = 1'b0;
  assign dup_status = 160'd0;
  assign txs_real   = 1'b0;
  assign txs_echo   = 1'b0;
  assign txs_dac    = 12'd0;
  assign echo_data  = 12'd0;
  assign echo_idx   = 48'd0;
  assign echo_ok    = 1'b0;
  assign echo_play  = 1'b0;
end

logic [15:0] aux_room;
logic        raw_run;
logic        aux_ready, aux_grant, aux_busy, aux_enable;
logic [ 1:0] aux_tx_request;
logic [15:0] aux_tx_length;
logic [ 7:0] aux_tx_data;

if (AUX != 0) begin: AUX_ON

logic        ax_ready, ax_grant, ax_busy, ax_enable;
logic [ 1:0] ax_tx_request;
logic [15:0] ax_tx_length;
logic [ 7:0] ax_tx_data;

auxchan #(.FIFO_AW(AUX_FIFO_AW)) auxchan_i (
  .clk_rx        (clock_ethrxint        ),
  .eth_port      (to_port               ),
  .eth_broadcast (broadcast             ),
  .eth_valid     (udp_rx_active         ),
  .eth_data      (udp_rx_data           ),
  .clk           (clock_ethtxint        ),
  .cmd_addr      (cmd_addr              ),
  .cmd_data      (cmd_data              ),
  .cmd_rqst      (cmd_rqst_usopenhpsdr1 ),
  .dest_valid    (aux_dest_valid        ),
  .raw_active    (raw_run               ),
  .room          (aux_room              ),
  .ready         (ax_ready              ),
  .grant         (ax_grant              ),
  .tx_request    (ax_tx_request         ),
  .tx_length     (ax_tx_length          ),
  .tx_data       (ax_tx_data            ),
  .tx_enable     (ax_enable             ),
  .busy          (ax_busy               )
);

if (HL2BUS != 0) begin: HL2BUS_ON

  // Bridge replies and aux packets share the aux send slot; a bridge reply goes first.
  logic        eb_ready, eb_grant, eb_busy, eb_enable;
  logic [ 1:0] eb_tx_request;
  logic [15:0] eb_tx_length;
  logic [ 7:0] eb_tx_data;
  logic        eb_own = 1'b0;

  logic [29:0] wb_adr;
  logic [31:0] wb_dat_w, wb_dat_r;
  logic [ 3:0] wb_sel;
  logic        wb_we, wb_cyc, wb_stb, wb_ack, wb_err;
  logic [95:0] eb_stats;

  // CPU system (CPU = 1): the bridge reaches everything outside 0x4000_xxxx through wb_cdc
  logic [ 9:0] pb_adr_a, pb_adr_b, cpu_rx_wr, cpu_rx_rd;
  logic        pb_we_a, pb_we_b, cpu_tx_req, cpu_tx_done;
  logic [ 7:0] pb_wd_a, pb_wd_b, pb_q_a, pb_q_b;
  logic [ 8:0] cpu_tx_len;
  logic [31:0] cpu_counts;
  logic [31:0] reg_dat_r, cdc_dat_r;
  logic        reg_ack, reg_err, cdc_ack, cdc_err;
  logic        wb_regs;
  wire         to_cpu = (CPU != 0) & ~wb_regs;   // registered decode, timed like wb_adr

  ebbridge #(.CPU_IO(CPU)) ebbridge_i (
    .clk_rx        (clock_ethrxint        ),
    .eth_port      (to_port               ),
    .eth_broadcast (broadcast             ),
    .eth_valid     (udp_rx_active         ),
    .eth_data      (udp_rx_data           ),
    .clk           (clock_ethtxint        ),
    .dest_valid    (aux_dest_valid        ),
    .room          (aux_room              ),
    .ready         (eb_ready              ),
    .grant         (eb_grant              ),
    .tx_request    (eb_tx_request         ),
    .tx_length     (eb_tx_length          ),
    .tx_data       (eb_tx_data            ),
    .tx_enable     (eb_enable             ),
    .busy          (eb_busy               ),
    .wb_adr        (wb_adr                ),
    .wb_regs       (wb_regs               ),
    .wb_dat_w      (wb_dat_w              ),
    .wb_dat_r      (wb_dat_r              ),
    .wb_sel        (wb_sel                ),
    .wb_we         (wb_we                 ),
    .wb_cyc        (wb_cyc                ),
    .wb_stb        (wb_stb                ),
    .wb_ack        (wb_ack                ),
    .wb_err        (wb_err                ),
    .stats         (eb_stats              ),
    .pb_adr        (pb_adr_b              ),
    .pb_we         (pb_we_b               ),
    .pb_wd         (pb_wd_b               ),
    .pb_q          (pb_q_b                ),
    .clk_cpu       (clock_cpu             ),
    .cpu_rx_wr     (cpu_rx_wr             ),
    .cpu_rx_rd     (cpu_rx_rd             ),
    .cpu_tx_req    (cpu_tx_req            ),
    .cpu_tx_len    (cpu_tx_len            ),
    .cpu_tx_done   (cpu_tx_done           ),
    .cpu_counts    (cpu_counts            )
  );

  assign wb_dat_r = to_cpu ? cdc_dat_r : reg_dat_r;
  assign wb_ack   = to_cpu ? cdc_ack   : reg_ack;
  assign wb_err   = to_cpu ? cdc_err   : reg_err;

  // slow ADC values and debounced inputs from the 2.5 MHz control domain
  logic [52:0] ctrl_status_c;
  cdc_word #(.W(53)) cdc_ctrl_status_i (
    .clk_a(clk_ctrl),
    .d_a  ({safety_status, temperature, fwdpwr, revpwr, bias}),
    .clk_b(clock_ethtxint),
    .q_b  (ctrl_status_c)
  );

  (* preserve *) logic [1:0] inj_ack_s = 2'b00;
  always @(posedge clock_ethtxint) inj_ack_s <= {inj_ack_s[0], bus_inj_ack};

  hl2bus_regs #(
    .VERSION_MAJOR(VERSION_MAJOR),
    .VERSION_MINOR(VERSION_MINOR),
    .DIAG_ID      (DIAG_ID      ),
    .CAPS         ({9'd0, (RAWFRONT != 0), (CPU != 0), (AUX != 0), (DUPLEX != 0), (RAWSTREAM != 0), (NT != 0), (RADIO != 0)})
  ) hl2bus_regs_i (
    .clk          (clock_ethtxint        ),
    .wb_adr       (wb_adr                ),
    .wb_dat_w     (wb_dat_w              ),
    .wb_dat_r     (reg_dat_r             ),
    .wb_sel       (wb_sel                ),
    .wb_we        (wb_we                 ),
    .wb_cyc       (wb_cyc & ~to_cpu      ),
    .wb_stb       (wb_stb & ~to_cpu      ),
    .wb_ack       (reg_ack               ),
    .wb_err       (reg_err               ),
    .bridge_stats (eb_stats              ),
    .tx_status    (tx_status             ),
    .ctrl_status  (ctrl_status_c         ),
    .cmd_addr     (cmd_addr              ),
    .cmd_data     (cmd_data              ),
    .cmd_rqst     (cmd_rqst_usopenhpsdr1 ),
    .inj_req      (bus_inj_req           ),
    .inj_addr     (bus_inj_addr          ),
    .inj_data     (bus_inj_data          ),
    .inj_ack      (inj_ack_s[1]          )
  );

  if (CPU != 0) begin: CPU_ON
    logic        br_req, br_we, br_done, br_err;
    logic [29:0] br_adr;
    logic [31:0] br_dat_w, br_dat_r;
    logic [ 3:0] br_sel;
    logic        io_wstb, io_from_br, io_hit, io_wr_ok, cpu_ms_tick, cpu_sys_rst;
    logic [ 5:0] io_adr;
    logic [31:0] io_dw, io_rdata;

    wb_cdc wb_cdc_i (
      .clk_m   (clock_ethtxint     ),
      .m_adr   (wb_adr             ),
      .m_dat_w (wb_dat_w           ),
      .m_sel   (wb_sel             ),
      .m_we    (wb_we              ),
      .m_stb   (wb_stb & to_cpu    ),
      .m_dat_r (cdc_dat_r          ),
      .m_ack   (cdc_ack            ),
      .m_err   (cdc_err            ),
      .clk_s   (clock_cpu          ),
      .s_req   (br_req             ),
      .s_adr   (br_adr             ),
      .s_dat_w (br_dat_w           ),
      .s_sel   (br_sel             ),
      .s_we    (br_we              ),
      .s_done  (br_done            ),
      .s_dat_r (br_dat_r           ),
      .s_err   (br_err             )
    );

    pbuf_ram pbuf_ram_i (
      .clk_a (clock_cpu     ), .adr_a(pb_adr_a), .we_a(pb_we_a), .wd_a(pb_wd_a), .q_a(pb_q_a),
      .clk_b (clock_ethtxint), .adr_b(pb_adr_b), .we_b(pb_we_b), .wd_b(pb_wd_b), .q_b(pb_q_b)
    );

    hl2cpu #(
      .CORE         (CPU          ),
      .MS_DIV       ((CPU_CLK_25 != 0) ? 25000 : 12500),
      .ROM_WORDS    (CPU_ROM_WORDS),
      .RAM_WORDS    (CPU_RAM_WORDS),
      .VERSION_MAJOR(VERSION_MAJOR),
      .VERSION_MINOR(VERSION_MINOR),
      .DIAG_ID      (DIAG_ID      ),
      .CAPS         ({9'd0, (RAWFRONT != 0), 1'b1, (AUX != 0), (DUPLEX != 0), (RAWSTREAM != 0), (NT != 0), (RADIO != 0)}),
      .IO           (RAWFRONT     )
    ) hl2cpu_i (
      .clk          (clock_cpu      ),
      .rst_async    (~ethpll_locked ),
      .br_req       (br_req         ),
      .br_adr       (br_adr         ),
      .br_dat_w     (br_dat_w       ),
      .br_sel       (br_sel         ),
      .br_we        (br_we          ),
      .br_done      (br_done        ),
      .br_dat_r     (br_dat_r       ),
      .br_err       (br_err         ),
      .clk_ctrl     (clk_ctrl       ),
      .ctrl_status  ({safety_status, temperature, fwdpwr, revpwr, bias}),
      .clk_eth      (clock_ethtxint ),
      .tx_status    (tx_status      ),
      .pb_adr       (pb_adr_a       ),
      .pb_we        (pb_we_a        ),
      .pb_wd        (pb_wd_a        ),
      .pb_q         (pb_q_a         ),
      .eth_rx_wr    (cpu_rx_wr      ),
      .rx_rd        (cpu_rx_rd      ),
      .tx_req       (cpu_tx_req     ),
      .tx_len       (cpu_tx_len     ),
      .eth_tx_done  (cpu_tx_done    ),
      .eth_dest     (aux_dest_valid ),
      .eth_counts   (cpu_counts     ),
      .fl_req       (cpu_fl_req     ),
      .fl_cmd       (cpu_fl_cmd     ),
      .fl_addr      (cpu_fl_addr    ),
      .fl_data      (cpu_fl_data    ),
      .fl_done      (cpu_fl_done    ),
      .fl_status    (cpu_fl_status  ),
      .fl_rdata     (cpu_fl_rdata   ),
      .led_en       (cpu_led_en     ),
      .led_on       (cpu_led_on     ),
      .cpu_running  (               ),
      .io_wstb      (io_wstb        ),
      .io_adr       (io_adr         ),
      .io_dw        (io_dw          ),
      .io_from_br   (io_from_br     ),
      .io_rdata     (io_rdata       ),
      .io_hit       (io_hit         ),
      .io_wr_ok     (io_wr_ok       ),
      .ms_tick      (cpu_ms_tick    ),
      .sys_rst_o    (cpu_sys_rst    )
    );

    if (RAWFRONT != 0) begin: IO_ON
      hl2io hl2io_i (
        .clk          (clock_cpu      ),
        .sys_rst      (cpu_sys_rst    ),
        .ms_tick      (cpu_ms_tick    ),
        .adr          (io_adr         ),
        .dw           (io_dw          ),
        .wstb         (io_wstb        ),
        .from_br      (io_from_br     ),
        .rdata        (io_rdata       ),
        .hit          (io_hit         ),
        .wr_ok        (io_wr_ok       ),
        .clk_ctrl     (clk_ctrl       ),
        .msec_ctrl    (msec_pulse     ),
        .temperature  (temperature    ),
        .adc_tick     (adc_tick       ),
        .fan_overheat (fan_overheat   ),
        .db_inputs    (safety_status[2:0]),
        .pa_cfg       (pa_cfg         ),
        .i2c_status   (ctrl_i2c_status),
        .adc_seq      (adc_seq        ),
        .fan_state    (fan_status     ),
        .bias_unlock_c(bias_unlock_c  ),
        .led_c        (led_ovr_c      ),
        .fan_min_c    (fan_min_c      ),
        .pwr_envpa    (ilk_pwr_envpa  ),
        .pwr_envop    (ilk_pwr_envop  ),
        .pwr_envbias  (ilk_pwr_envbias),
        .pa_inttr     (ilk_pa_inttr   ),
        .pa_exttr     (ilk_pa_exttr   ),
        .rffe_rfsw_sel(ilk_rfsw_sel   ),
        .dac_en       (ilk_dac_en     ),
        .tx_on        (ilk_tx_on      ),
        .ilk_status   (ilk_status     ),
        .pins         ({io_tp, linkrx, io_atu_ack, io_uart_rxd, io_alternate_mac, io_id_hermeslite,
                        io_tx_inhibit, io_phone_ring, io_phone_tip}),
        .inj_req      (io_inj_req     ),
        .inj_addr     (io_inj_addr    ),
        .inj_data     (io_inj_data    ),
        .inj_ack      (io_inj_ack     )
      );
    end else begin: IO_OFF
      assign io_rdata = 32'd0;
      assign io_hit   = 1'b0;
      assign io_wr_ok = 1'b0;
    end
  end else begin: CPU_OFF
    assign cdc_dat_r   = 32'd0;
    assign cdc_ack     = 1'b0;
    assign cdc_err     = 1'b0;
    assign pb_q_b      = 8'd0;
    assign cpu_rx_rd   = 10'd0;
    assign cpu_tx_req  = 1'b0;
    assign cpu_tx_len  = 9'd0;
    assign cpu_fl_req  = 1'b0;
    assign cpu_fl_cmd  = 3'd0;
    assign cpu_fl_addr = 24'd0;
    assign cpu_fl_data = 8'd0;
    assign cpu_led_en  = 1'b0;
    assign cpu_led_on  = 1'b0;
  end

  assign aux_ready = eb_ready | ax_ready;
  // alternate when both wait, so neither a busy bridge client nor aux traffic starves the other
  assign eb_grant  = aux_grant & eb_ready & (~ax_ready | ~eb_own);
  assign ax_grant  = aux_grant & ~eb_grant;
  always @(posedge clock_ethtxint) if (aux_grant) eb_own <= eb_grant;

  assign aux_busy       = eb_busy | ax_busy;
  assign eb_enable      = aux_enable & eb_own;
  assign ax_enable      = aux_enable & ~eb_own;
  assign aux_tx_request = eb_own ? eb_tx_request : ax_tx_request;
  assign aux_tx_length  = eb_own ? eb_tx_length  : ax_tx_length;
  assign aux_tx_data    = eb_own ? eb_tx_data    : ax_tx_data;

end else begin: HL2BUS_OFF

  assign aux_ready      = ax_ready;
  assign ax_grant       = aux_grant;
  assign aux_busy       = ax_busy;
  assign ax_enable      = aux_enable;
  assign aux_tx_request = ax_tx_request;
  assign aux_tx_length  = ax_tx_length;
  assign aux_tx_data    = ax_tx_data;
  assign bus_inj_req    = 1'b0;
  assign bus_inj_addr   = 6'd0;
  assign bus_inj_data   = 32'd0;
  assign cpu_fl_req     = 1'b0;
  assign cpu_fl_cmd     = 3'd0;
  assign cpu_fl_addr    = 24'd0;
  assign cpu_fl_data    = 8'd0;
  assign cpu_led_en     = 1'b0;
  assign cpu_led_on     = 1'b0;

end

end else begin: AUX_OFF
  assign cpu_fl_req     = 1'b0;
  assign cpu_fl_cmd     = 3'd0;
  assign cpu_fl_addr    = 24'd0;
  assign cpu_fl_data    = 8'd0;
  assign cpu_led_en     = 1'b0;
  assign cpu_led_on     = 1'b0;
  assign bus_inj_req    = 1'b0;
  assign bus_inj_addr   = 6'd0;
  assign bus_inj_data   = 32'd0;
  assign aux_ready      = 1'b0;
  assign aux_busy       = 1'b0;
  assign aux_tx_request = 2'b00;
  assign aux_tx_length  = 16'd0;
  assign aux_tx_data    = 8'd0;
end

// header bytes 46-47 of the 48-byte duplex header (RAWFRONT): flags and latched trip reasons
logic [15:0] ilk_hdr_c;
if (RAWFRONT != 0) begin: ILK_HDR
  cdc_word #(.W(16)) cdc_ilk_hdr_i (
    .clk_a(clk_ctrl),
    .d_a  ({1'b0, ilk_status[0], ilk_status[2], ilk_status[4], ilk_status[1], 3'b000, ilk_status[15:8]}),
    .clk_b(clock_ethtxint),
    .q_b  (ilk_hdr_c));
end else begin: NO_ILK_HDR
  assign ilk_hdr_c = 16'd0;
end
// byte 46: [1] echo on [2] real DAC mode [3] DAC driven [4] trip latched [5] lease valid [6] transmit on
wire [15:0] ext_status = {ilk_hdr_c[15:12], ilk_hdr_c[11] & txs_real, txs_real, txs_echo, 1'b0, ilk_hdr_c[7:0]};

rawstream #(.FIFO_AW(RAWSTREAM_FIFO_AW), .MAX_N_OVERRIDE(RAWSTREAM_MAX_N), .DUPLEX(DUPLEX), .AUX(AUX), .ECHO(RAWFRONT)) rawstream_i (
  .clk_ad        (clk_ad9866            ),
  .adc_data      (rx_data               ),
  .clk           (clock_ethtxint        ),
  .run           (run_sync              ),
  .cmd_addr      (cmd_addr              ),
  .cmd_data      (cmd_data              ),
  .cmd_rqst      (cmd_rqst_usopenhpsdr1 ),
  .raw_mode      (raw_mode              ),
  .pkt_tx_request(pkt_udp_tx_request    ),
  .pkt_tx_length ({5'h00,pkt_udp_tx_length}),
  .pkt_tx_data   (pkt_udp_tx_data       ),
  .pkt_tx_enable (pkt_udp_tx_enable     ),
  .udp_tx_request(udp_tx_request        ),
  .udp_tx_length (udp_tx_length         ),
  .udp_tx_data   (udp_tx_data           ),
  .udp_tx_enable (udp_tx_enable         ),
  .udp0_tx_enable(udp0_tx_enable        ),
  .udp_tx_busy   (udp_tx_busy           ),
  .dup_on        (dup_on                ),
  .dup_status    (dup_status            ),
  .tx_status     (tx_status             ),
  .aux_room     (aux_room              ),
  .raw_run       (raw_run               ),
  .aux_ready     (aux_ready             ),
  .aux_grant     (aux_grant             ),
  .aux_tx_request(aux_tx_request        ),
  .aux_tx_length (aux_tx_length         ),
  .aux_tx_data   (aux_tx_data           ),
  .aux_busy      (aux_busy              ),
  .udp2_tx_enable(udp2_tx_enable        ),
  .aux_enable    (aux_enable            ),
  .echo_on       (txs_echo              ),
  .echo_data     (echo_data             ),
  .echo_idx      (echo_idx              ),
  .echo_ok       (echo_ok               ),
  .echo_play     (echo_play             ),
  .ext_status    (ext_status            )
);

end else begin: RAWSTREAM_OFF

assign raw_mode          = 1'b0;
assign udp_tx_request    = pkt_udp_tx_request;
assign udp_tx_length     = {5'h00,pkt_udp_tx_length};
assign udp_tx_data       = pkt_udp_tx_data;
assign pkt_udp_tx_enable = udp_tx_enable;
assign cpu_fl_req        = 1'b0;
assign cpu_fl_cmd        = 3'd0;
assign cpu_fl_addr       = 24'd0;
assign cpu_fl_data       = 8'd0;
assign cpu_led_en        = 1'b0;
assign cpu_led_on        = 1'b0;
assign bus_inj_req       = 1'b0;
assign bus_inj_addr      = 6'd0;
assign bus_inj_data      = 32'd0;

end
endgenerate

// A raw stream image without a transmitter can never key the PA, the T/R relay
// or the AD9866 transmit path: force the transmit flags to zero.
generate
if ((RAWSTREAM != 0) && (NT == 0)) begin: TX_OFF
  assign tx_on_int = 1'b0;
  assign cw_on_int = 1'b0;
end else begin: TX_PASS
  assign tx_on_int = tx_on;
  assign cw_on_int = cw_on;
end
endgenerate

generate if (RADIO != 0) begin: USBS_ON
usbs_fifo usbs_fifo_i (
  .wr_clk(clk_ad9866),
  .wr_tdata(rx_data),
  .wr_tvalid(1'b1),
  .wr_tready(),

  .rd_clk(clock_ethtxint),
  .rd_tdata(bs_tdata),
  .rd_tvalid(bs_tvalid),
  .rd_tready(bs_tready)
);
end else begin: USBS_OFF
  assign bs_tdata  = 12'd0;
  assign bs_tvalid = 1'b0;
end
endgenerate

// Transmit-safety status, raw frame header byte 3 (docs/rawfront/PROTOCOL.md). Every bit is a slow level
// from another domain, synchronised on its own:
//   [0] transmit forced off in logic (raw image without transmitter)
//   [1] a PA / T-R / bias output is driven     [2] PC requests transmit (openHPSDR MOX bit)
//   [3] PTT input (ring) closed                [4] key input (tip) closed
//   [5] TX inhibit input (CN8) active          [6] over-temperature: transmit disabled
//   [7] 0 (reserved for the transmit interlock)
// Raw front-end image (docs/rawfront/PROTOCOL.md): [0] transmit off (interlock outputs off) [2] transmit requested
// (lease valid and key) [6] over-temperature cut-off now [7] interlock trip latched; [1], [3]-[5] as above.
wire [7:0] tx_status_async = (RAWFRONT != 0) ?
                             {ilk_status[4], ilk_status[17], safety_status[2], safety_status[0], safety_status[1],
                              ilk_status[3], (pa_inttr | pa_exttr | pwr_envpa | pwr_envbias | pwr_envop), ~ilk_status[0]} :
                             {1'b0, safety_status[3], safety_status[2], safety_status[0], safety_status[1],
                              ds_cmd_ptt, (pa_inttr | pa_exttr | pwr_envpa | pwr_envbias | pwr_envop),
                              ((RAWSTREAM != 0) && (NT == 0)) ? 1'b1 : 1'b0};
(* preserve *) logic [7:0] tx_status_s1 = 8'd0;
(* preserve *) logic [7:0] tx_status_s2 = 8'd0;
always @(posedge clock_ethtxint) begin
  tx_status_s1 <= tx_status_async;
  tx_status_s2 <= tx_status_s1;
end
assign tx_status = tx_status_s2;


///////////////////////////////////////////////
// AD9866 clock domain

sync_pulse sync_pulse_ad9866 (
  .clock(clk_ad9866),
  .sig_in(cmd_cnt),
  .sig_out(cmd_rqst_ad9866)
);

sync_pulse sync_rxclrstatus_ad9866 (
  .clock(clk_ad9866),
  .sig_in(rxclrstatus),
  .sig_out(rxclrstatus_ad9866sync)
);

// CDC okay as clock is >2x faster than sig_in domain
sync_one sync_qmsec_pulse_ad9866 (
  .clock(clk_ad9866),
  .sig_in(qmsec_pulse),
  .sig_out(qmsec_pulse_ad9866sync)
);

// Psuedostatic
sync sync_ds_cmd_ptt_ad9866 (
  .clock(clk_ad9866),
  .sig_in(ds_cmd_ptt),
  .sig_out(ds_cmd_ptt_ad9866sync)
);

sync sync_run_ad9866 (
  .clock(clk_ad9866),
  .sig_in(run),
  .sig_out(run_ad9866sync)
);

// CDC okay as clock is >2x faster than sig_in domain
sync sync_keydown_ad9866 (
  .clock(clk_ad9866),
  .sig_in(cw_keydown),
  .sig_out(cw_keydown_ad9866sync)
);

// CDC okay as clock is >2x faster than sig_in domain
sync sync_ptt_ad9866 (
  .clock(clk_ad9866),
  .sig_in(ext_ptt),
  .sig_out(ext_ptt_ad9866sync)
);

// CDC okay as clock is >2x faster than sig_in domain
sync sync_atutxinhibit_ad9866 (
  .clock(clk_ad9866),
  .sig_in(atu_txinhibit),
  .sig_out(atu_txinhibit_ad9866sync)
);

// Raw front-end image: the duplex TX samples reach the AD9866 transmit DAC only while the interlock
// enables the DAC (PA stage on) and the sink is in real-DAC mode; otherwise the DAC input is 0 and its
// transmit enable is off.
logic        ad_tx_en;
logic [11:0] ad_tx_data;
generate if (RAWFRONT != 0) begin: TXDAC_RAW
  txdac_gate txdac_gate_i (.clk_ad(clk_ad9866), .dac_en(ilk_dac_en), .mode_real(txs_real), .dac_in(txs_dac),
                           .tx_en(ad_tx_en), .tx_data(ad_tx_data));
end else begin: TXDAC_RADIO
  assign ad_tx_en   = tx_on_int & ~atu_txinhibit_ad9866sync;
  assign ad_tx_data = tx_data;
end endgenerate

ad9866 #(.FAST_LNA(FAST_LNA)) ad9866_i (
  .clk(clk_ad9866),
  .clk_2x(clk_ad9866_2x),

  .rst(ad9866_rst),

  .tx_data(ad_tx_data),
  .rx_data(rx_data),
  .tx_en(ad_tx_en),
  .cw_on((RAWFRONT != 0) ? 1'b0 : (cw_on_int & ~atu_txinhibit_ad9866sync)),

  .rxclip(rxclip),
  .rxgoodlvl(rxgoodlvl),
  .rxclrstatus(rxclrstatus_ad9866sync),

  .rffe_ad9866_tx(rffe_ad9866_tx),
  .rffe_ad9866_rx(rffe_ad9866_rx),
  .rffe_ad9866_rxsync(rffe_ad9866_rxsync),
  .rffe_ad9866_rxclk(rffe_ad9866_rxclk),
  .rffe_ad9866_txquiet_n(rffe_ad9866_txquiet_n),
  .rffe_ad9866_txsync(rffe_ad9866_txsync),

  .rffe_ad9866_mode(rffe_ad9866_mode),
  .rffe_ad9866_pga5(rffe_ad9866_pga5),

  // Command Slave
  .cmd_addr(cmd_addr),
  .cmd_data(cmd_data),
  .cmd_rqst(cmd_rqst_ad9866),
  .cmd_ack() // No need for ack
);

generate if (RADIO != 0) begin: RADIO_ON
radio #(
  .NR(NR),
  .NT(NT),
  .LRDATA(LRDATA),
  .CLK_FREQ(CLK_FREQ),
  .HL2LINK(HL2LINK)
)
radio_i
(
  .clk(clk_ad9866),
  .clk_2x(clk_ad9866_2x),

  .rst_all(rst_all),
  .rst_nco(rst_nco),

  .link_running(link_running),
  .link_master(link_master),
  .lm_data(lm_data),
  .lm_valid(lm_valid),
  .ls_valid(ls_valid),
  .ls_done(ls_done),

  .ds_cmd_ptt(ds_cmd_ptt_ad9866sync),
  .run(run_ad9866sync),
  .qmsec_pulse(qmsec_pulse_ad9866sync),
  .ext_keydown(cw_keydown_ad9866sync),
  .ext_ptt(ext_ptt_ad9866sync),

  .tx_on(tx_on),
  .cw_on(cw_on),
  .cw_profile(cw_profile),
  
  // Transmit
  .tx_tdata({dsiq_tdata[7:0],dsiq_tdata[16:9],dsiq_tdata[25:18],dsiq_tdata[34:27]}),
  .tx_tlast(1'b1),
  .tx_tready(dsiq_tready),
  .tx_tvalid(dsiq_tvalid),
  .tx_tuser({dsiq_tdata[8],dsiq_tdata[17],dsiq_tdata[26],dsiq_tdata[35]}),
  .tx_twait(dsiq_twait),

  .tx_data_dac(tx_data),

  .clk_envelope(clk_envelope),
  .tx_envelope_pwm_out(io_tx_envelope_pwm_out),
  .tx_envelope_pwm_out_inv(io_tx_envelope_pwm_out_inv),

  // Optional Audio Stream
  .lr_tdata({dslr_tdata[7:0],dslr_tdata[16:9],dslr_tdata[25:18],dslr_tdata[34:27]}),
  .lr_tid(3'h0),
  .lr_tlast(1'b1),
  .lr_tready(dslr_tready),
  .lr_tvalid(dslr_tvalid),

  // Receive
  .rx_data_adc(rx_data),

  .rx_tdata(rx_tdata),
  .rx_tlast(rx_tlast),
  .rx_tready(rx_tready),
  .rx_tvalid(rx_tvalid),
  .rx_tuser(rx_tuser),

  // Command Slave
  .cmd_addr(cmd_addr),
  .cmd_data(cmd_data),
  .cmd_rqst(cmd_rqst_ad9866),
  .cmd_ack(), // No need for ack from radio yet
  .debug_out(debug)
);
end else begin: RADIO_OFF
  // Front-end image: nothing is received, and nothing is ever transmitted
  assign tx_on                      = 1'b0;
  assign cw_on                      = 1'b0;
  assign cw_profile                 = 19'd0;
  assign tx_data                    = 12'd0;
  assign dsiq_tready                = 1'b0;
  assign dsiq_twait                 = 1'b0;
  assign dslr_tready                = 1'b0;
  assign io_tx_envelope_pwm_out     = 1'b0;
  assign io_tx_envelope_pwm_out_inv = 1'b0;
  assign rx_tdata                   = 24'd0;
  assign rx_tlast                   = 1'b0;
  assign rx_tvalid                  = 1'b0;
  assign rx_tuser                   = 2'b00;
  assign debug                      = 16'd0;
end
endgenerate




///////////////////////////////////////////////
// IO clock domain


// clk_ctrl at 2.5MHz, 1Gbs ethernet at 125 MHz, implies 50 ethernet ticks
// Worst case is a bit more than 50 ethernet ticks
// Add up all the overheads and we have at 8+20+22+4+12+UDP length minimum
// space between commands

sync_pulse #(.DEPTH(2)) syncio_cmd_rqst (
  .clock(clk_ctrl),
  .sig_in(cmd_cnt),
  .sig_out(cmd_rqst_io)
);

// Clocks are really synchronous so save time
sync_pulse #(.DEPTH(2)) syncio_rqst_io (
  .clock(clk_ctrl),
  .sig_in(resp_rqst),
  .sig_out(resp_rqst_iosync)
);

sync syncio_rxclip (
  .clock(clk_ctrl),
  .sig_in(rxclip),
  .sig_out(rxclip_iosync)
);

sync syncio_rxgoodlvl (
  .clock(clk_ctrl),
  .sig_in(rxgoodlvl),
  .sig_out(rxgoodlvl_iosync)
);

sync syncio_run (
  .clock(clk_ctrl),
  .sig_in(run),
  .sig_out(run_iosync)
);

sync syncio_tx_on (
  .clock(clk_ctrl),
  .sig_in(tx_on_int),
  .sig_out(tx_on_iosync)
);

sync syncio_cw_on (
  .clock(clk_ctrl),
  .sig_in(cw_on_int),
  .sig_out(cw_on_iosync)
);

control #(
  .VERSION_MAJOR(VERSION_MAJOR),
  .UART         (UART         ),
  .ATU          (ATU          ),
  .FAN          (FAN          ),
  .PSSYNC       (PSSYNC       ),
  .CW           (CW           ),
  .FAST_LNA     (FAST_LNA     ),
  .AK4951       (AK4951       ),
  .EXTENDED_RESP(EXTENDED_RESP),
  .BYPASS_VERSA (BYPASS_VERSA ),
  .SLOW_ADC_FREE((RADIO == 0) ? 1 : 0),
  .RAWFRONT     (RAWFRONT     )
) control_i (
  // Internal
  .clk                (clk_ctrl                   ),
  .clk_ad9866         (clk_ad9866                 ), // Just for measurement
  .clk_125            (clock_125_mhz_0_deg        ),
  .clk_slow           (clk_ad9866_slow            ),
  
  .ethup              (ethup                      ),
  .have_dhcp_ip       (~network_state_dhcp        ),
  .have_fixed_ip      (~network_state_fixedip     ),
  .network_speed      (network_speed              ),
  .is_ksz9021         (is_ksz9021                 ),
  .ad9866up           (ad9866up                   ),
  
  .rxclip             (rxclip_iosync              ),
  .rxgoodlvl          (rxgoodlvl_iosync           ),
  .rxclrstatus        (rxclrstatus                ),
  .run                (run_iosync                 ),
  .slave_link_running (link_running & ~link_master),
  
  .dsiq_status        (dsiq_status                ),
  .dsiq_sample        (dsiq_sample                ),
  
  .cmd_addr           (cmd_addr                   ),
  .cmd_data           (cmd_data                   ),
  .cmd_rqst           (cmd_rqst_io                ),
  .cmd_is_alt         (cmd_is_alt                 ),
  .cmd_requires_resp  (cmd_resprqst               ),
  
  .atu_txinhibit      (atu_txinhibit              ),
  .tx_on              (tx_on_iosync               ),
  .cw_on              (cw_on_iosync               ),
  .cw_keydown         (cw_keydown                 ),
  .ext_pttout         (ext_ptt                    ),
  
  
  .msec_pulse         (msec_pulse                 ),
  .qmsec_pulse        (qmsec_pulse                ),
  
  .resp_rqst          (resp_rqst_iosync           ),
  .resp               (resp                       ),
  
  .static_ip          (static_ip                  ),
  .alt_mac            (alt_mac                    ),
  .eeprom_config      (eeprom_config              ),
  
  // External
  .rffe_rfsw_sel      (ctrl_rfsw_sel              ),
  
  // AD9866
  .rffe_ad9866_rst_n  (rffe_ad9866_rst_n          ),
  
  .rffe_ad9866_sdio   (rffe_ad9866_sdio           ),
  .rffe_ad9866_sclk   (rffe_ad9866_sclk           ),
  .rffe_ad9866_sen_n  (rffe_ad9866_sen_n          ),
  
  // Power
  .pwr_clk3p3         (pwr_clk3p3                 ),
  .pwr_clk1p2         (pwr_clk1p2                 ),
  .pwr_envpa          (ctrl_pwr_envpa             ),
  .pwr_envop          (ctrl_pwr_envop             ),
  .pwr_envbias        (ctrl_pwr_envbias           ),
  
  .sda1_i             (sda1_i                     ),
  .sda1_o             (sda1_o                     ),
  .sda1_t             (sda1_t                     ),
  .scl1_i             (scl1_i                     ),
  .scl1_o             (scl1_o                     ),
  .scl1_t             (scl1_t                     ),
  
  .sda2_i             (sda2_i                     ),
  .sda2_o             (sda2_o                     ),
  .sda2_t             (sda2_t                     ),
  .scl2_i             (scl2_i                     ),
  .scl2_o             (scl2_o                     ),
  .scl2_t             (scl2_t                     ),
  
  .sda3_i             (sda3_i                     ),
  .sda3_o             (sda3_o                     ),
  .sda3_t             (sda3_t                     ),
  .scl3_i             (scl3_i                     ),
  .scl3_o             (scl3_o                     ),
  .scl3_t             (scl3_t                     ),
  
  // IO
  .io_led_run         (io_led_run                 ),
  .io_led_tx          (io_led_tx                  ),
  .io_led_adc75       (io_led_adc75               ),
  .io_led_adc100      (led_adc100_ctrl            ),
  
  .io_tx_inhibit      (io_tx_inhibit              ),
  
  .io_uart_txd        (io_uart_txd                ),
  //.io_uart_txd        (                      ),
  .io_cw_keydown      (io_cw_keydown              ),
  
  .io_phone_tip       (io_phone_tip               ),
  .io_phone_ring      (io_phone_ring              ),
  
  .io_atu_ack         (io_atu_ack                 ),
  .io_atu_req         (io_atu_req                 ),
  
  // PA
  .pa_inttr           (ctrl_pa_inttr              ),
  .pa_exttr           (ctrl_pa_exttr              ),
  
  .hl2_reset          (hl2_reset                  ),
  
  .fan_pwm            (fan_pwm                    ),
  
  .ad9866_rst         (ad9866_rst                 ),
  
  .clk_i2c_rst        (clk_i2c_rst                ),
  .io_ptt_in          (io_ptt_in                  ),
  
  .alt_resp_cnt       (alt_resp_cnt               ),
  .resp_data          (resp_data                  ),
  .resp_control       (resp_control               ),
  .temp               (temperature                ),
  .fwdpwr             (fwdpwr                     ),
  .revpwr             (revpwr                     ),
  .bias               (bias                       ),
  .control_dsiq_status(control_dsiq_status        ),
  
  .hl2link_rst_req    (hl2link_rst_req            ),
  .hl2link_rst_ack    (hl2link_rst_ack            ),
  .safety_status      (safety_status              ),
  .ilk_tx_on          (ilk_tx_on                  ),
  .bias_unlock        (bias_unlock_c              ),
  .led_ovr            (led_ovr_c                  ),
  .fan_min            (fan_min_c                  ),
  .i2c_status         (ctrl_i2c_status            ),
  .adc_tick           (adc_tick                   ),
  .adc_seq            (adc_seq                    ),
  .fan_status         (fan_status                 ),
  .fan_overheat       (fan_overheat               ),
  .pa_cfg             (pa_cfg                     ),

  .debug              (16'h0000                   )  //(debug                      )
);

// Transmit-related pins: the interlock in the raw front-end image, control.v otherwise
generate if (RAWFRONT != 0) begin: PINS_ILK
  assign pwr_envpa     = ilk_pwr_envpa;
  assign pwr_envop     = ilk_pwr_envop;
  assign pwr_envbias   = ilk_pwr_envbias;
  assign pa_inttr      = ilk_pa_inttr;
  assign pa_exttr      = ilk_pa_exttr;
  assign rffe_rfsw_sel = ilk_rfsw_sel;
end else begin: PINS_CTRL
  assign pwr_envpa     = ctrl_pwr_envpa;
  assign pwr_envop     = ctrl_pwr_envop;
  assign pwr_envbias   = ctrl_pwr_envbias;
  assign pa_inttr      = ctrl_pa_inttr;
  assign pa_exttr      = ctrl_pa_exttr;
  assign rffe_rfsw_sel = ctrl_rfsw_sel;
  assign ilk_pwr_envpa = 1'b0;  assign ilk_pwr_envop = 1'b0;  assign ilk_pwr_envbias = 1'b0;
  assign ilk_pa_inttr  = 1'b0;  assign ilk_pa_exttr  = 1'b0;  assign ilk_rfsw_sel    = 1'b0;
  assign ilk_dac_en    = 1'b0;
  assign ilk_tx_on     = 1'b0;
  assign ilk_status    = 32'd0;
  assign bias_unlock_c = 1'b0;
  assign led_ovr_c     = 8'd0;
  assign fan_min_c     = 4'd0;
  assign io_inj_req    = 1'b0;
  assign io_inj_addr   = 6'd0;
  assign io_inj_data   = 32'd0;
end endgenerate


// LED D5 (active low): the CPU may drive it once it enables the override (CPU = 1)
assign io_led_adc100 = cpu_led_en ? ~cpu_led_on : led_adc100_ctrl;

assign scl1_i = clk_scl1;
assign clk_scl1 = scl1_t ? 1'bz : scl1_o;
assign sda1_i = clk_sda1;
assign clk_sda1 = sda1_t ? 1'bz : sda1_o;

assign scl2_i = io_scl2;
assign io_scl2 = scl2_t ? 1'bz : scl2_o;
assign sda2_i = io_sda2;
assign io_sda2 = sda2_t ? 1'bz : sda2_o;

assign scl3_i = io_adc_scl;
assign io_adc_scl = scl3_t ? 1'bz : scl3_o;
assign sda3_i = io_adc_sda;
assign io_adc_sda = sda3_t ? 1'bz : sda3_o;


generate case (ASMII)

  1: begin: INCLUDEASMII
    logic [ 7:0]    asmi_data;
    logic [ 9:0]    asmi_rx_used;
    logic           asmi_rdreq;
    logic           asmi_reconfig;

    asmi_fifo asmi_fifo_i (
      .wrclk (clock_ethrxint),
      .wrreq(dsethasmi_tvalid),
      .data (dseth_tdata),
      .rdreq (asmi_rdreq),
      .rdclk (clk_ctrl),
      .q (asmi_data),
      .rdusedw(asmi_rx_used),
      .aclr(1'b0)
    );

    asmi_interface #(.CPU_PORT(CPU), .PROTECT_TOP(CPU)) asmi_interface_i (
      .clock(clk_ctrl),
      .busy(),
      .erase(dsethasmi_erase),
      .erase_ACK(dsethasmi_erase_ack),
      .IF_Rx_used(asmi_rx_used),
      .rdreq(asmi_rdreq),
      .IF_PHY_data(asmi_data),
      .erase_done(usethasmi_erase_done),
      .erase_done_ACK(usethasmi_ack),
      .send_more(usethasmi_send_more),
      .send_more_ACK(usethasmi_ack),
      .num_blocks(asmi_cnt),
      .NCONFIG(asmi_reconfig),
      .cpu_req(cpu_fl_req),
      .cpu_cmd(cpu_fl_cmd),
      .cpu_addr(cpu_fl_addr),
      .cpu_data(cpu_fl_data),
      .cpu_done(cpu_fl_done),
      .cpu_status(cpu_fl_status),
      .cpu_rdata(cpu_fl_rdata)
    );

    remote_update remote_update_i (
      .clk(clk_ctrl),
      .rst(~ethpll_locked),
      .reboot(asmi_reconfig | hl2_reset),
      .factory( (~io_phone_tip & ~io_phone_ring) )
    );

  end

  default: begin: NOASMII

    assign usethasmi_erase_done = 1'b0;
    assign usethasmi_send_more = 1'b0;
    assign dsethasmi_erase_ack = 1'b1;
    assign cpu_fl_done = 1'b0;
    assign cpu_fl_status = 3'd0;
    assign cpu_fl_rdata = 8'd0;

  end
endcase
endgenerate

generate
if (HL2LINK == 1) begin

  logic ds_cmd_rqst_ad9866;

  sync_pulse sync_pulse_ad9866 (
    .clock(clk_ad9866),
    .sig_in(ds_cmd_cnt),
    .sig_out(ds_cmd_rqst_ad9866)
  );

  sync sync_stall_ack (
    .clock(clk_ad9866),
    .sig_in(stall_ack),
    .sig_out(stall_ack_ad9866)
  );

  sync sync_stall_req(
    .clock(clock_ethtxint),
    .sig_in(stall_req),
    .sig_out(stall_req_sync)
  );

  hl2link_app hl2link_app_i (
    .clk            (clk_ad9866        ),
    .phy_connected  (phy_connected     ),
    .linkrx         (linkrx            ),
    .linktx         (linktx            ),
    .stall_req      (stall_req         ),
    .stall_ack      (stall_ack_ad9866  ),
    .rst_all        (rst_all           ),
    .rst_nco        (rst_nco           ),
    .running        (link_running      ),
    .master_sel     (link_master       ),
    .lm_data        (lm_data           ),
    .lm_valid       (lm_valid          ),
    .ls_valid       (ls_valid          ),
    .ls_done        (ls_done           ),
    .ls_data        (rx_tdata          ),
    .ds_cmd_addr    (ds_cmd_addr       ),
    .ds_cmd_data    (ds_cmd_data       ),
    .ds_cmd_rqst    (ds_cmd_rqst_ad9866),
    .ds_cmd_resprqst(ds_cmd_resprqst   ),
    .ds_cmd_is_alt  (ds_cmd_is_alt     ),
    .ds_cmd_mask    (ds_cmd_mask       ),
    .cmd_addr       (cmd_addr          ),
    .cmd_data       (cmd_data          ),
    .cmd_cnt        (cmd_cnt           ),
    .cmd_resprqst   (cmd_resprqst      ),
    .cmd_is_alt     (cmd_is_alt        ),
    .cmd_rqst       (cmd_rqst_ad9866   ),
    .hl2link_rst_req(hl2link_rst_req   ),
    .hl2link_rst_ack(hl2link_rst_ack   ),
    .link_error(link_error)
  );

  assign bus_inj_ack = 1'b0;
  //assign io_uart_txd = cmd_cnt;



end else begin
  assign linktx = 2'b00;
  assign stall_req_sync = 1'b0;
  assign rst_all        = 1'b0;
  assign rst_nco        = 1'b0;

  if (HL2BUS != 0) begin: CMD_MERGE
    // PC commands plus the register bridge's RX gain command on the one command bus
    cmd_merge cmd_merge_i (
      .clk        (clock_ethrxint ),
      .ds_addr    (ds_cmd_addr    ),
      .ds_data    (ds_cmd_data    ),
      .ds_cnt     (ds_cmd_cnt     ),
      .ds_is_alt  (ds_cmd_is_alt  ),
      .ds_resprqst(ds_cmd_resprqst),
      .inj_req    (bus_inj_req    ),
      .inj_addr   (bus_inj_addr   ),
      .inj_data   (bus_inj_data   ),
      .inj_ack    (bus_inj_ack    ),
      .inj2_req   ((RAWFRONT != 0) ? io_inj_req : 1'b0),
      .inj2_addr  (io_inj_addr    ),
      .inj2_data  (io_inj_data    ),
      .inj2_ack   (io_inj_ack     ),
      .addr       (cmd_addr       ),
      .data       (cmd_data       ),
      .cnt        (cmd_cnt        ),
      .is_alt     (cmd_is_alt     ),
      .resprqst   (cmd_resprqst   )
    );
  end else begin: CMD_DIRECT
    assign cmd_addr           = ds_cmd_addr;
    assign cmd_data           = ds_cmd_data;
    assign cmd_cnt            = ds_cmd_cnt;
    assign cmd_is_alt         = ds_cmd_is_alt;
    assign cmd_resprqst       = ds_cmd_resprqst;
    assign bus_inj_ack        = 1'b0;
  end
  assign link_running       = 1'b0;
  assign link_master        = 1'b0;
  assign lm_data       = 24'hXXXXXX;
  assign lm_valid = 1'b1;
end

endgenerate


generate
if (AK4951 == 1) begin

  logic        au_tready  ;

  dslr_fifo dslr_fifo_i (
    .wr_clk(clock_ethrxint),
    .wr_tdata(dseth_tdata),
    .wr_tvalid(dsethlr_tvalid),
    .wr_tready(),

    .rd_clk(clk_ad9866),
    .rd_tdata(dslr_tdata),
    .rd_tvalid(dslr_tvalid),
    .rd_tready(au_tready)
  );

  localaudio localaudio_i (
    .clk(clk_ad9866),
    .rst(ad9866_rst),
    .clk_i2c_rst(clk_i2c_rst),

    .au_tdata(dslr_tdata),                 // audio L/R tx data (16bit * 2)
    .au_tready(au_tready),                 // next tx data request
    .au_rdata(au_rdata),                   // audio L rx data (16bit)
    .au_rvalid(),                          // audio rx data valid

    .sidetone_sel(cw_on),                  // select sidetone as audio output ; ad9866sync
    .profile(cw_profile[18:12]),           // sidetone profile (7bit)

    .cmd_addr(cmd_addr),                   // Command slave interface
    .cmd_data(cmd_data),
    .cmd_rqst(cmd_rqst_ad9866),            // cmd_cnt ; ad9866sync

    .i2s_pdn(i2s_pdn),                     // AK4951 i/o pins (I2S)
    .i2s_bck(i2s_bck),
    .i2s_lrck(i2s_lrck),
    .i2s_mosi(i2s_mosi),
    .i2s_miso(i2s_miso)
  );

  assign pa_exttr_clone = pa_exttr ; // AK4951 Companion Board V3


end else begin
  assign pa_exttr_clone = 1'b0;
  assign i2s_pdn  = 1'b0;
  assign i2s_bck  = 1'b0;
  assign i2s_lrck = 1'b0;
  assign i2s_mosi = 1'b0;

end
endgenerate



endmodule
