//
//  gl_pll.v — Gowin PLL for the reverse (Gowin -> HL2) link, locked to the forward clock
//  received from the HL2 (U20, SGCLKT_5 / BPLL2/3 CLKIN0 on J14 pin 20).
//
//  fwd_clk   76.8 MHz (LANES = 6) or 153.6 MHz (LANES = 3)
//  clk_w     76.8 MHz  word clock of the reverse transmitter (CLKOUT0)
//  clk_l    153.6 MHz  lane clock, data launched on both edges (CLKOUT1, 0 degrees)
//  clk_c    153.6 MHz  forwarded clock, 90 degrees late (CLKOUT2): the clock edge lands
//                      in the middle of each data bit at the HL2 pins.
//
//  VCO = fwd_clk / IDIV * FBDIV * MDIV = 1228.8 MHz; CLKOUTn = VCO / ODIVn.
//  The 90 degree shift of CLKOUT2 = 1/4 of 6.51 ns = 1.628 ns = 2 VCO periods:
//  CLKOUT2_PE_COARSE = 2, CLKOUT2_PE_FINE = 0 (fine step = VCO period / 8).
//  THIS STATIC PHASE SETTING IS TO BE CONFIRMED ON HARDWARE (scope on the reverse clock
//  and a data lane at the HL2 header); the HL2 reports the alignment result in the status
//  frame, and the HL2 PLL has a trim parameter as a second knob (gowinlink_rxpll PHASE_PS).
//
//  Simulation (`ifdef SIM): behavioural clocks derived from fwd_clk with fixed delays.
//
`timescale 1ns/1ps
module gl_pll #(
  parameter integer LANES = 6
) (
  input  fwd_clk,
  output clk_w,
  output clk_l,
  output clk_c,
  output lock
);

`ifdef SIM
  // 76.8 MHz word clock: fwd_clk itself (LANES = 6) or fwd_clk divided by 2 (LANES = 3)
  reg  div2 = 1'b0;
  always @(posedge fwd_clk) div2 <= ~div2;
  assign clk_w = (LANES == 6) ? fwd_clk : div2;
  // 153.6 MHz: two pulses per clk_w period, generated from both edges of clk_w
  reg  l_r = 1'b0;
  always @(clk_w) begin
    l_r <= 1'b1;
    l_r <= #3.255 1'b0;
  end
  assign clk_l = l_r;
  reg  c_r = 1'b0;
  always @(clk_l) c_r <= #1.628 clk_l;
  assign clk_c = c_r;
  assign lock  = 1'b1;
`else
  wire gw_gnd = 1'b0;
  wire gw_vcc = 1'b1;
  wire clkout3, clkout4, clkout5, clkout6, clkfbout;

  PLL pll_i (
    .LOCK       (lock),
    .CLKOUT0    (clk_w),
    .CLKOUT1    (clk_l),
    .CLKOUT2    (clk_c),
    .CLKOUT3    (clkout3),
    .CLKOUT4    (clkout4),
    .CLKOUT5    (clkout5),
    .CLKOUT6    (clkout6),
    .CLKFBOUT   (clkfbout),
    .CLKIN      (fwd_clk),
    .CLKFB      (gw_gnd),
    .RESET      (gw_gnd),
    .PLLPWD     (gw_gnd),
    .RESET_I    (gw_gnd),
    .RESET_O    (gw_gnd),
    .FBDSEL     (6'b000000),
    .IDSEL      (6'b000000),
    .MDSEL      (7'b0000000),
    .MDSEL_FRAC (3'b000),
    .ODSEL0     (7'b0000000),
    .ODSEL0_FRAC(3'b000),
    .ODSEL1     (7'b0000000),
    .ODSEL2     (7'b0000000),
    .ODSEL3     (7'b0000000),
    .ODSEL4     (7'b0000000),
    .ODSEL5     (7'b0000000),
    .ODSEL6     (7'b0000000),
    .DT0        (4'b0000),
    .DT1        (4'b0000),
    .DT2        (4'b0000),
    .DT3        (4'b0000),
    .ICPSEL     (6'b000000),
    .LPFRES     (3'b000),
    .LPFCAP     (2'b00),
    .PSSEL      (3'b000),
    .PSDIR      (gw_gnd),
    .PSPULSE    (gw_gnd),
    .ENCLK0     (gw_vcc),
    .ENCLK1     (gw_vcc),
    .ENCLK2     (gw_vcc),
    .ENCLK3     (gw_vcc),
    .ENCLK4     (gw_vcc),
    .ENCLK5     (gw_vcc),
    .ENCLK6     (gw_vcc),
    .SSCPOL     (gw_gnd),
    .SSCON      (gw_gnd),
    .SSCMDSEL   (7'b0000000),
    .SSCMDSEL_FRAC(3'b000)
  );

  defparam pll_i.FCLKIN            = (LANES == 6) ? "76.8" : "153.6";
  defparam pll_i.IDIV_SEL          = 1;
  defparam pll_i.FBDIV_SEL         = 1;
  defparam pll_i.MDIV_SEL          = (LANES == 6) ? 16 : 8;   // VCO 1228.8 MHz
  defparam pll_i.MDIV_FRAC_SEL     = 0;
  defparam pll_i.ODIV0_SEL         = 16;                     // 76.8 MHz
  defparam pll_i.ODIV1_SEL         = 8;                      // 153.6 MHz
  defparam pll_i.ODIV2_SEL         = 8;                      // 153.6 MHz, +90 degrees
  defparam pll_i.ODIV3_SEL         = 8;
  defparam pll_i.ODIV4_SEL         = 8;
  defparam pll_i.ODIV5_SEL         = 8;
  defparam pll_i.ODIV6_SEL         = 8;
  defparam pll_i.ODIV0_FRAC_SEL    = 0;
  defparam pll_i.CLKOUT0_EN        = "TRUE";
  defparam pll_i.CLKOUT1_EN        = "TRUE";
  defparam pll_i.CLKOUT2_EN        = "TRUE";
  defparam pll_i.CLKOUT3_EN        = "FALSE";
  defparam pll_i.CLKOUT4_EN        = "FALSE";
  defparam pll_i.CLKOUT5_EN        = "FALSE";
  defparam pll_i.CLKOUT6_EN        = "FALSE";
  defparam pll_i.CLKFB_SEL         = "INTERNAL";
  defparam pll_i.CLKOUT0_DT_DIR    = 1'b1;
  defparam pll_i.CLKOUT1_DT_DIR    = 1'b1;
  defparam pll_i.CLKOUT2_DT_DIR    = 1'b1;
  defparam pll_i.CLKOUT3_DT_DIR    = 1'b1;
  defparam pll_i.CLKOUT0_DT_STEP   = 0;
  defparam pll_i.CLKOUT1_DT_STEP   = 0;
  defparam pll_i.CLKOUT2_DT_STEP   = 0;
  defparam pll_i.CLKOUT3_DT_STEP   = 0;
  defparam pll_i.CLK0_IN_SEL       = 1'b0;
  defparam pll_i.CLK0_OUT_SEL      = 1'b0;
  defparam pll_i.CLK1_IN_SEL       = 1'b0;
  defparam pll_i.CLK1_OUT_SEL      = 1'b0;
  defparam pll_i.CLK2_IN_SEL       = 1'b0;
  defparam pll_i.CLK2_OUT_SEL      = 1'b0;
  defparam pll_i.CLK3_IN_SEL       = 1'b0;
  defparam pll_i.CLK3_OUT_SEL      = 1'b0;
  defparam pll_i.CLK4_IN_SEL       = 2'b00;
  defparam pll_i.CLK4_OUT_SEL      = 1'b0;
  defparam pll_i.CLK5_IN_SEL       = 1'b0;
  defparam pll_i.CLK5_OUT_SEL      = 1'b0;
  defparam pll_i.CLK6_IN_SEL       = 1'b0;
  defparam pll_i.CLK6_OUT_SEL      = 1'b0;
  defparam pll_i.DYN_DPA_EN        = "FALSE";
  defparam pll_i.CLKOUT0_PE_COARSE = 0;
  defparam pll_i.CLKOUT0_PE_FINE   = 0;
  defparam pll_i.CLKOUT1_PE_COARSE = 0;
  defparam pll_i.CLKOUT1_PE_FINE   = 0;
  defparam pll_i.CLKOUT2_PE_COARSE = 2;   // 90 degrees at 153.6 MHz with a 1228.8 MHz VCO
  defparam pll_i.CLKOUT2_PE_FINE   = 0;
  defparam pll_i.CLKOUT3_PE_COARSE = 0;
  defparam pll_i.CLKOUT3_PE_FINE   = 0;
  defparam pll_i.CLKOUT4_PE_COARSE = 0;
  defparam pll_i.CLKOUT4_PE_FINE   = 0;
  defparam pll_i.CLKOUT5_PE_COARSE = 0;
  defparam pll_i.CLKOUT5_PE_FINE   = 0;
  defparam pll_i.CLKOUT6_PE_COARSE = 0;
  defparam pll_i.CLKOUT6_PE_FINE   = 0;
  defparam pll_i.DYN_PE0_SEL       = "FALSE";
  defparam pll_i.DYN_PE1_SEL       = "FALSE";
  defparam pll_i.DYN_PE2_SEL       = "FALSE";
  defparam pll_i.DYN_PE3_SEL       = "FALSE";
  defparam pll_i.DYN_PE4_SEL       = "FALSE";
  defparam pll_i.DYN_PE5_SEL       = "FALSE";
  defparam pll_i.DYN_PE6_SEL       = "FALSE";
  defparam pll_i.DE0_EN            = "FALSE";
  defparam pll_i.DE1_EN            = "FALSE";
  defparam pll_i.DE2_EN            = "FALSE";
  defparam pll_i.DE3_EN            = "FALSE";
  defparam pll_i.DE4_EN            = "FALSE";
  defparam pll_i.DE5_EN            = "FALSE";
  defparam pll_i.DE6_EN            = "FALSE";
  defparam pll_i.RESET_I_EN        = "FALSE";
  defparam pll_i.RESET_O_EN        = "FALSE";
  defparam pll_i.ICP_SEL           = 6'bXXXXXX;
  defparam pll_i.LPF_RES           = 3'bXXX;
  defparam pll_i.LPF_CAP           = 2'b00;
  defparam pll_i.SSC_EN            = "FALSE";
`endif

endmodule
