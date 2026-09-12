// gowinlink.sdc — timing constraints for the Gowin side (LANES = 6 default build).
//
// Clocks
//   clk50     on-board oscillator, 50 MHz
//   fwd_clk   forwarded from the HL2, 76.8 MHz (LANES = 6). For the LANES = 3 build the
//             period is 6.51 ns (153.6 MHz): edit the create_clock line.
//   PLL outputs (gl_pll): 76.8 MHz word clock, 153.6 MHz lane clock, 153.6 MHz +90 deg.
//
// The forward data lanes are captured by IDDR after a per-lane IODELAY whose value is
// found at run time (delay sweep, LINK_SPEC.md 6.2), so a static input-delay analysis of
// link_d does not describe the design: those paths are cut. The reverse outputs are a
// source-synchronous DDR interface whose clock is generated 90 degrees late by the PLL;
// their skew is constrained relative to the lane clock.

create_clock -name clk50   -period 20.000 [get_ports {clk50}]
create_clock -name fwd_clk -period 13.021 [get_ports {fwd_clk}]

// PLL outputs: VCO 1228.8 MHz; CLKOUT0 /16, CLKOUT1 /8, CLKOUT2 /8 + 90 deg
create_generated_clock -name clk_w -source [get_ports {fwd_clk}] -multiply_by 1  [get_pins {pll_i/pll_i/CLKOUT0}]
create_generated_clock -name clk_l -source [get_ports {fwd_clk}] -multiply_by 2  [get_pins {pll_i/pll_i/CLKOUT1}]
create_generated_clock -name clk_c -source [get_ports {fwd_clk}] -multiply_by 2 -phase 90 [get_pins {pll_i/pll_i/CLKOUT2}]

set_clock_groups -asynchronous -group [get_clocks {clk50}] -group [get_clocks {fwd_clk}] -group [get_clocks {clk_w clk_l clk_c}]

// forward lanes: calibrated at run time
set_false_path -from [get_ports {link_d[*]}]

// slow / asynchronous pins
set_false_path -from [get_ports {status_rxd aux_in dbg_rxd key_n}]
set_false_path -to   [get_ports {dbg_txd cmd_txd led[*]}]

// reverse DDR outputs launched by clk_l; the forwarded clock (clk_c) is 90 deg late,
// i.e. the HL2 samples 1.63 ns after each data edge: allow +/-0.8 ns of skew
set_output_delay -clock [get_clocks {clk_l}] -max  0.800 [get_ports {gl_rev[*]}]
set_output_delay -clock [get_clocks {clk_l}] -min -0.800 [get_ports {gl_rev[*]}]
set_output_delay -clock [get_clocks {clk_l}] -max  0.800 -clock_fall -add_delay [get_ports {gl_rev[*]}]
set_output_delay -clock [get_clocks {clk_l}] -min -0.800 -clock_fall -add_delay [get_ports {gl_rev[*]}]
// fast serial: SDR at the word rate, sampled by the HL2 in the middle of the bit
set_output_delay -clock [get_clocks {clk_w}] -max  2.000 [get_ports {fs_txd}]
set_output_delay -clock [get_clocks {clk_w}] -min -2.000 [get_ports {fs_txd}]
