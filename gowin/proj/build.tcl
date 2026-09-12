# build.tcl — Gowin EDA command-line build of the Tang Mega 138K side.
#
#   cd gowin/proj
#   gw_sh build.tcl            (LANES = 6, the default geometry)
#   gw_sh build.tcl 3          (LANES = 3 fallback: 3 forward lanes at 153.6 MHz DDR)
#
# gw_sh: C:\Gowin\Gowin_V1.9.11.03_Education\Gowin_V1.9.11.03_Education_x64\IDE\bin\gw_sh.exe
# Outputs go to gowin/proj/impl/ (ignored by git): impl/pnr/gowinlink.fs is the bitstream,
# impl/pnr/*.tr.html the timing report, impl/pnr/*.rpt.html the place-and-route report.
#
# The LANES parameter is applied through a one-line wrapper top (gl_top_l3.v) because
# gw_sh has no command-line parameter override; the wrapper instantiates gl_top with
# LANES = 3. The default build uses gl_top directly (LANES = 6).

set lanes 6
if {$argc >= 1} { set lanes [lindex $argv 0] }

set here   [file dirname [file normalize [info script]]]
set root   [file normalize "$here/../.."]
set shared "$root/gateware/rtl/gowinlink"
set grtl   "$root/gowin/rtl"

set_device GW5AST-LV138PG484AC1/I0 -device_version B

foreach f {
  gowinlink_uart_rx.v gowinlink_uart_tx.v gowinlink_crc8.v gowinlink_prbs23.v
  gowinlink_scrambler.v gowinlink_tx_lanes.v gowinlink_cmd_rx.v
  gl_cdc.v gl_rx_datapath.v gl_fastserial_tx.v gl_fastserial_rx.v
} { add_file -type verilog "$shared/$f" }

foreach f {
  gl_lane_rx.v gl_pll.v gl_cmd_tx.v gl_cmd_fs.v gl_status_rx.v gl_train.v gl_console.v gl_top.v
} { add_file -type verilog "$grtl/$f" }

if {$lanes == 3} {
  add_file -type verilog "$grtl/gl_top_l3.v"
  add_file -type cst "$here/gowinlink_l3.cst"
  add_file -type sdc "$here/gowinlink_l3.sdc"
  set_option -top_module gl_top_l3
  set_option -output_base_name gowinlink_l3
} else {
  add_file -type cst "$here/gowinlink.cst"
  add_file -type sdc "$here/gowinlink.sdc"
  set_option -top_module gl_top
  set_option -output_base_name gowinlink
}

set_option -verilog_std sysv2017
set_option -include_path "$grtl"
set_option -use_mspi_as_gpio 1
set_option -use_sspi_as_gpio 1
set_option -use_i2c_as_gpio 1
set_option -gen_text_timing_rpt 1
set_option -gen_verilog_sim_netlist 0
set_option -place_option 1
set_option -route_option 1

run all
