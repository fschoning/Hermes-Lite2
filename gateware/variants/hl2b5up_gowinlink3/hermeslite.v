//  Hermes Lite — hl2b5up_gowinlink variant
//
//  hl2b5up_main plus the HL2 <-> Tang Mega 138K link (gateware/gowinlink/LINK_SPEC.md):
//  cable 1 streams the 12-bit ADC samples to the Gowin board (6 DDR lanes + forwarded
//  clock on DB1, status UART on DB12), cable 2 brings a 153.6 MHz DDR reverse link and the
//  command channel back. The Ethernet stack is untouched; link-originated commands are
//  merged onto the internal command bus behind the Ethernet source.
//
//  Pins taken by the link (see gowinlink_pins.tcl): DB1 pins 1-6 (io_db1_1..6: TX envelope
//  PWM, amplifier UART, fan PWM and the ATU are therefore not available in this variant),
//  DB12 pins 1/2/5/6 (the two-HL2 link, HL2LINK, is kept in the core with its pins
//  unconnected), and LED D3/D4/D5 pins (which become reverse-link inputs; D2 stays the
//  run LED).
//
//  GL_LANES here must match GL_LANES in hermeslite.qsf (pin file). Default 6.
//
//  This program is free software; you can redistribute it and/or modify
//  it under the terms of the GNU General Public License as published by
//  the Free Software Foundation; either version 2 of the License, or
//  (at your option) any later version.

module hermeslite (
  // Power
  output       pwr_clk3p3           ,
  output       pwr_clk1p2           ,
  output       pwr_envpa            ,
  output       pwr_envop            ,
  output       pwr_envbias          ,
  // Ethernet PHY
  input        phy_clk125           ,
  output [3:0] phy_tx               ,
  output       phy_tx_en            ,
  output       phy_tx_clk           ,
  input  [3:0] phy_rx               ,
  input        phy_rx_dv            ,
  input        phy_rx_clk           ,
  input        phy_rst_n            ,
  inout        phy_mdio             ,
  output       phy_mdc              ,
  // Clock
  inout        clk_sda1             ,
  inout        clk_scl1             ,
  // RF Frontend
  output       rffe_ad9866_rst_n    ,
  output [5:0] rffe_ad9866_tx       ,
  input  [5:0] rffe_ad9866_rx       ,
  input        rffe_ad9866_rxsync   ,
  input        rffe_ad9866_rxclk    ,
  output       rffe_ad9866_txquiet_n,
  output       rffe_ad9866_txsync   ,
  output       rffe_ad9866_sdio     ,
  output       rffe_ad9866_sclk     ,
  output       rffe_ad9866_sen_n    ,
  input        rffe_ad9866_clk76p8  ,
  output       rffe_rfsw_sel        ,
  output       rffe_ad9866_mode     ,
  output       rffe_ad9866_pga5     ,
  //
  input        io_cn8               ,
  input        io_cn9               ,
  input        io_cn10              ,
  //
  inout        io_adc_scl           ,
  inout        io_adc_sda           ,
  inout        io_scl2              ,
  inout        io_sda2              ,
  //
  input        io_phone_tip         ,
  input        io_phone_ring        ,
  input        io_tp2               ,
  input        io_tp7               ,
  input        io_tp8               ,
  input        io_tp9               ,
  //
  output       pa_inttr             ,
  output       pa_exttr             ,
  // Gowin link, cable 1 (HL2 -> Gowin)
  output       gl_clk               ,
  output [GL_LANES-1:0] gl_d        ,
  output       gl_status_txd        ,
  output       gl_aux_out           ,
  // Gowin link, cable 2 (Gowin -> HL2)
  input        gl_rev_clk           ,
  input  [2:0] gl_rev               ,
  input        gl_fs_rxd
);

localparam GL_LANES = 3;

  hermeslite_core #(
    .BOARD        (5                                    ),
    .IP           ({8'd0,8'd0,8'd0,8'd0}                ),
    .MAC          ({8'h00,8'h1c,8'hc0,8'ha2,8'h13,8'hdd}),
    .NR           (4                                    ),
    .NT           (1                                    ),
    .UART         (0                                    ),
    .ATU          (0                                    ),
    .FAN          (1                                    ),
    .PSSYNC       (1                                    ),
    .CW           (1                                    ),
    .ASMII        (1                                    ),
    .HL2LINK      (1                                    ),
    .AK4951       (0                                    ),
    .FAST_LNA     (1                                    ),
    .EXTENDED_RESP(1                                    ),
    .EXTENDED_DEBUG_RESP(1                              ),
    .GOWINLINK    (1                                    ),
    .GL_LANES     (GL_LANES                             ),
    .GL_CMD_UART  (0                                    )
  ) hermeslite_core_i (
    .pwr_clk3p3                (pwr_clk3p3           ),
    .pwr_clk1p2                (pwr_clk1p2           ),
    .pwr_envpa                 (pwr_envpa            ),
    .pwr_envop                 (pwr_envop            ),
    .pwr_envbias               (pwr_envbias          ),
    .phy_clk125                (phy_clk125           ),
    .phy_tx                    (phy_tx               ),
    .phy_tx_en                 (phy_tx_en            ),
    .phy_tx_clk                (phy_tx_clk           ),
    .phy_rx                    (phy_rx               ),
    .phy_rx_dv                 (phy_rx_dv            ),
    .phy_rx_clk                (phy_rx_clk           ),
    .phy_rst_n                 (phy_rst_n            ),
    .phy_mdio                  (phy_mdio             ),
    .phy_mdc                   (phy_mdc              ),
    .clk_sda1                  (clk_sda1             ),
    .clk_scl1                  (clk_scl1             ),
    .rffe_ad9866_rst_n         (rffe_ad9866_rst_n    ),
    .rffe_ad9866_tx            (rffe_ad9866_tx       ),
    .rffe_ad9866_rx            (rffe_ad9866_rx       ),
    .rffe_ad9866_rxsync        (rffe_ad9866_rxsync   ),
    .rffe_ad9866_rxclk         (rffe_ad9866_rxclk    ),
    .rffe_ad9866_txquiet_n     (rffe_ad9866_txquiet_n),
    .rffe_ad9866_txsync        (rffe_ad9866_txsync   ),
    .rffe_ad9866_sdio          (rffe_ad9866_sdio     ),
    .rffe_ad9866_sclk          (rffe_ad9866_sclk     ),
    .rffe_ad9866_sen_n         (rffe_ad9866_sen_n    ),
    .rffe_ad9866_clk76p8       (rffe_ad9866_clk76p8  ),
    .rffe_rfsw_sel             (rffe_rfsw_sel        ),
    .rffe_ad9866_mode          (rffe_ad9866_mode     ),
    .rffe_ad9866_pga5          (rffe_ad9866_pga5     ),
    .io_led_run                (                     ),
    .io_led_tx                 (                     ),
    .io_led_adc75              (                     ),
    .io_led_adc100             (                     ),
    .io_tx_envelope_pwm_out    (                     ),
    .io_tx_envelope_pwm_out_inv(                     ),
    .io_tx_inhibit             (io_cn8               ),
    .io_id_hermeslite          (io_cn9               ),
    .io_alternate_mac          (io_cn10              ),
    .io_adc_scl                (io_adc_scl           ),
    .io_adc_sda                (io_adc_sda           ),
    .io_scl2                   (io_scl2              ),
    .io_sda2                   (io_sda2              ),
    .io_uart_txd               (                     ),
    .io_uart_rxd               (1'b1                 ),
    .io_cw_keydown             (                     ),
    .io_phone_tip              (io_phone_tip         ),
    .io_phone_ring             (io_phone_ring        ),
    .io_atu_ack                (1'b1                 ),
    .io_atu_req                (                     ),
    .pa_inttr                  (pa_inttr             ),
    .pa_exttr                  (pa_exttr             ),
    .fan_pwm                   (                     ),
    .linkrx                    (2'b00                ),
    .linktx                    (                     ),
    .pa_exttr_clone            (                     ),
    .io_ptt_in                 (1'b0                 ),
    .i2s_pdn                   (                     ),
    .i2s_bck                   (                     ),
    .i2s_lrck                  (                     ),
    .i2s_miso                  (1'b0                 ),
    .i2s_mosi                  (                     ),
    .gl_clk                    (gl_clk               ),
    .gl_d                      (gl_d                 ),
    .gl_status_txd             (gl_status_txd        ),
    .gl_aux_out                (gl_aux_out           ),
    .gl_rev_clk                (gl_rev_clk           ),
    .gl_rev                    (gl_rev               ),
    .gl_fs_rxd                 (gl_fs_rxd            )
  );

endmodule
