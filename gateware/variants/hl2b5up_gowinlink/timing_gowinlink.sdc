# timing_gowinlink.sdc — link timing constraints, sourced after boards/hl2b5up/timing.sdc.
#
# Forward (cable 1): the data lanes and the clock lane are all altddio_out registers on
# the same clock (clk_ad9866 for GL_LANES = 6, clk_ad9866_2x for GL_LANES = 3), so the
# clock lane is a generated clock and the lanes are constrained against it with the skew
# budget the Gowin side needs (its IODELAY sweep tolerates far more, but this keeps the
# fitter honest about the register-to-pin paths).
#
# Reverse (cable 2): 153.6 MHz clock on PIN_88 into a PLL (gowinlink_rxpll, normal mode),
# three DDR data inputs whose eye is centred on the clock edges by the Gowin
# (clock forwarded 90 degrees late). Data valid window assumed +/-1.0 ns around the edge.

# ---------------------------------------------------------------- forward
# GL_LANES is a .qsf variable and not visible here: detect the geometry from the ports
if {[get_collection_size [get_ports -nowarn {gl_d[5]}]] > 0} {
  create_generated_clock -name gl_clk_out -source [get_pins {hermeslite_core_i|ad9866pll_inst|altpll_component|auto_generated|pll1|clk[0]}] [get_ports {gl_clk}]
} else {
  create_generated_clock -name gl_clk_out -source [get_pins {hermeslite_core_i|ad9866pll_inst|altpll_component|auto_generated|pll1|clk[1]}] [get_ports {gl_clk}]
}
set_output_delay -clock gl_clk_out -max  1.000 [get_ports {gl_d[*]}]
set_output_delay -clock gl_clk_out -min -1.000 [get_ports {gl_d[*]}]
set_output_delay -clock gl_clk_out -max  1.000 -clock_fall -add_delay [get_ports {gl_d[*]}]
set_output_delay -clock gl_clk_out -min -1.000 -clock_fall -add_delay [get_ports {gl_d[*]}]
# DDR: same-edge launch/capture only
set_false_path -rise_from [get_clocks {clock_76p8MHz clock_153p6MHz}] -fall_to [get_clocks {gl_clk_out}] -setup
set_false_path -fall_from [get_clocks {clock_76p8MHz clock_153p6MHz}] -rise_to [get_clocks {gl_clk_out}] -setup
set_false_path -rise_from [get_clocks {clock_76p8MHz clock_153p6MHz}] -rise_to [get_clocks {gl_clk_out}] -hold
set_false_path -fall_from [get_clocks {clock_76p8MHz clock_153p6MHz}] -fall_to [get_clocks {gl_clk_out}] -hold

set_false_path -to   [get_ports {gl_status_txd gl_aux_out}]

# ---------------------------------------------------------------- reverse
create_clock -name gl_rev_clk -period 6.510 [get_ports {gl_rev_clk}]
create_generated_clock -source {hermeslite_core_i|gowinlink_hl2_i|rxpll_i|altpll_component|auto_generated|pll1|inclk[0]} -duty_cycle 50.00 -name gl_rev_clk_pll {hermeslite_core_i|gowinlink_hl2_i|rxpll_i|altpll_component|auto_generated|pll1|clk[0]}
set_clock_groups -asynchronous -group {gl_rev_clk gl_rev_clk_pll}

set_input_delay -clock gl_rev_clk -max  1.000 [get_ports {gl_rev[*] gl_fs_rxd}]
set_input_delay -clock gl_rev_clk -min -1.000 [get_ports {gl_rev[*] gl_fs_rxd}]
set_input_delay -clock gl_rev_clk -max  1.000 -clock_fall -add_delay [get_ports {gl_rev[*] gl_fs_rxd}]
set_input_delay -clock gl_rev_clk -min -1.000 -clock_fall -add_delay [get_ports {gl_rev[*] gl_fs_rxd}]
set_false_path -rise_from [get_clocks {gl_rev_clk}] -fall_to [get_clocks {gl_rev_clk_pll}] -setup
set_false_path -fall_from [get_clocks {gl_rev_clk}] -rise_to [get_clocks {gl_rev_clk_pll}] -setup
set_false_path -rise_from [get_clocks {gl_rev_clk}] -rise_to [get_clocks {gl_rev_clk_pll}] -hold
set_false_path -fall_from [get_clocks {gl_rev_clk}] -fall_to [get_clocks {gl_rev_clk_pll}] -hold
