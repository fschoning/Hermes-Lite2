//
//  gowinlink_rxpll.v — PLL for the reverse (Gowin -> HL2) link clock.
//
//  The Gowin forwards a 153.6 MHz clock that it has already centred on its data (data
//  launched on one PLL output, clock forwarded from a 90-degree shifted output). The HL2
//  passes that clock through a PLL in normal mode so that the DDR input registers see the
//  same phase as the pin (the global clock network insertion delay is compensated), then
//  captures the lanes with altddio_in. PHASE_PS allows a static trim if the timing report
//  shows the capture window is off-centre (see LINK_SPEC.md section 6.6).
//
//  Simulation (`ifdef SIM): c0 = inclk, locked = 1 (an RTL simulation has no clock
//  network delay to compensate).
//
module gowinlink_rxpll #(
  parameter PHASE_PS = "0"
) (
  input  inclk,
  input  areset,
  output c0,
  output locked
);

`ifdef SIM
  assign c0     = inclk;
  assign locked = ~areset;
`else
  wire [4:0] sub_wire_clk;
  assign c0 = sub_wire_clk[0];

  altpll #(
    .bandwidth_type            ("AUTO"),
    .clk0_divide_by            (1),
    .clk0_duty_cycle           (50),
    .clk0_multiply_by          (1),
    .clk0_phase_shift          (PHASE_PS),
    .compensate_clock          ("CLK0"),
    .inclk0_input_frequency    (6510),          // ps, 153.6 MHz
    .intended_device_family    ("Cyclone IV E"),
    .lpm_hint                  ("CBX_MODULE_PREFIX=gowinlink_rxpll"),
    .lpm_type                  ("altpll"),
    .operation_mode            ("NORMAL"),
    .pll_type                  ("AUTO"),
    .port_activeclock          ("PORT_UNUSED"),
    .port_areset               ("PORT_USED"),
    .port_clkbad0              ("PORT_UNUSED"),
    .port_clkbad1              ("PORT_UNUSED"),
    .port_clkloss              ("PORT_UNUSED"),
    .port_clkswitch            ("PORT_UNUSED"),
    .port_configupdate         ("PORT_UNUSED"),
    .port_fbin                 ("PORT_UNUSED"),
    .port_inclk0               ("PORT_USED"),
    .port_inclk1               ("PORT_UNUSED"),
    .port_locked               ("PORT_USED"),
    .port_pfdena               ("PORT_UNUSED"),
    .port_phasecounterselect   ("PORT_UNUSED"),
    .port_phasedone            ("PORT_UNUSED"),
    .port_phasestep            ("PORT_UNUSED"),
    .port_phaseupdown          ("PORT_UNUSED"),
    .port_pllena               ("PORT_UNUSED"),
    .port_scanaclr             ("PORT_UNUSED"),
    .port_scanclk              ("PORT_UNUSED"),
    .port_scanclkena           ("PORT_UNUSED"),
    .port_scandata             ("PORT_UNUSED"),
    .port_scandataout          ("PORT_UNUSED"),
    .port_scandone             ("PORT_UNUSED"),
    .port_scanread             ("PORT_UNUSED"),
    .port_scanwrite            ("PORT_UNUSED"),
    .port_clk0                 ("PORT_USED"),
    .port_clk1                 ("PORT_UNUSED"),
    .port_clk2                 ("PORT_UNUSED"),
    .port_clk3                 ("PORT_UNUSED"),
    .port_clk4                 ("PORT_UNUSED"),
    .port_clk5                 ("PORT_UNUSED"),
    .port_clkena0              ("PORT_UNUSED"),
    .port_clkena1              ("PORT_UNUSED"),
    .port_clkena2              ("PORT_UNUSED"),
    .port_clkena3              ("PORT_UNUSED"),
    .port_clkena4              ("PORT_UNUSED"),
    .port_clkena5              ("PORT_UNUSED"),
    .port_extclk0              ("PORT_UNUSED"),
    .port_extclk1              ("PORT_UNUSED"),
    .port_extclk2              ("PORT_UNUSED"),
    .port_extclk3              ("PORT_UNUSED"),
    .self_reset_on_loss_lock   ("ON"),
    .width_clock               (5)
  ) altpll_component (
    .areset             (areset),
    .inclk              ({1'b0, inclk}),
    .clk                (sub_wire_clk),
    .locked             (locked),
    .activeclock        (),
    .clkbad             (),
    .clkena             ({6{1'b1}}),
    .clkloss            (),
    .clkswitch          (1'b0),
    .configupdate       (1'b0),
    .enable0            (),
    .enable1            (),
    .extclk             (),
    .extclkena          ({4{1'b1}}),
    .fbin               (1'b1),
    .fbmimicbidir       (),
    .fbout              (),
    .fref               (),
    .icdrclk            (),
    .pfdena             (1'b1),
    .phasecounterselect ({4{1'b1}}),
    .phasedone          (),
    .phasestep          (1'b1),
    .phaseupdown        (1'b1),
    .pllena             (1'b1),
    .scanaclr           (1'b0),
    .scanclk            (1'b0),
    .scanclkena         (1'b1),
    .scandata           (1'b0),
    .scandataout        (),
    .scandone           (),
    .scanread           (1'b0),
    .scanwrite          (1'b0),
    .sclkout0           (),
    .sclkout1           (),
    .vcooverrange       (),
    .vcounderrange      ()
  );
`endif

endmodule
