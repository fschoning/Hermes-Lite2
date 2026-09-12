# gowinlink_pins.tcl — HL2 pin locations and I/O settings for the HL2 <-> Tang Mega 138K
# link. THE ONLY FILE WITH LINK PIN LOCATIONS ON THE HL2 SIDE.
#
# STATUS: PROVISIONAL. The adapter PCBs (LVDS driver/receiver boards joined by two DVI
# cables) are being designed; when hardware/companions/gowin-bridge/PINMAP.md is published
# (worktree G:\proj\worktrees\Hermes-Lite2-gowin-bridge-pcb) bring this file in line with it.
#
# Set GL_LANES (6 or 3) before sourcing this file; the variant's hermeslite.qsf does it.
# GL_LANES must match the localparam of the same name in the variant's hermeslite.v.
#
# Cable 1, HL2 -> Gowin (source-synchronous DDR, forwarded clock, plus the status UART):
#
#   GL_LANES = 6 (default): 6 data lanes DDR at 76.8 MHz (153.6 Mbit/s each)
#     gl_clk       PIN_98  bank 6, 3.3 V LVTTL 8 mA   DB1 pin 9  (LED D2 cathode is on this pin)
#     gl_d[0]      PIN_72  bank 4, 2.5 V (Veth)        DB1 pin 1  (via J25, PLL4_CLKOUTn pin)
#     gl_d[1]      PIN_76  bank 5, 2.5 V (Vlvds)       DB1 pin 2  (RUP3 pin; OCT calibration unused)
#     gl_d[2]      PIN_77  bank 5, 2.5 V               DB1 pin 3  (RDN3 pin)
#     gl_d[3]      PIN_80  bank 5, 2.5 V               DB1 pin 4  (VREFB5N0: 21 pF pin, the slowest lane)
#     gl_d[4]      PIN_83  bank 5, 2.5 V               DB1 pin 5
#     gl_d[5]      PIN_85  bank 5, 2.5 V               DB1 pin 6
#     gl_status_txd PIN_86 bank 5, 2.5 V output        DB12 pin 1 (status UART, 115200 8N1)
#     gl_aux_out   PIN_87  bank 5, 2.5 V output        DB12 pin 2 (reserved, driven low)
#
#   GL_LANES = 3 (fallback): 3 data lanes DDR at 153.6 MHz (307.2 Mbit/s each)
#     gl_clk       PIN_76 (153.6 MHz), gl_d[0..2] = PIN_77, PIN_83, PIN_85; PIN_72/80/98 unused
#
#   Lane j carries sample bits s[B*j+B-1 : B*j] (B = 12/GL_LANES), MSB first, H bit while the
#   forwarded clock is high. The 2.5 V lanes use 50 ohm series OCT without calibration
#   (fastest edge, damps the unterminated line, does not need the RUP/RDN pins); if Quartus
#   rejects it on a pin, fall back to CURRENT_STRENGTH_NEW 16mA + SLEW_RATE 0.
#
# Cable 2, Gowin -> HL2 (source-synchronous DDR at 153.6 MHz, clock centred by the Gowin):
#     gl_rev_clk   PIN_88  bank 5, 2.5 V, CLK7/DIFFCLK_3n dedicated clock input (input only) DB12 pin 6
#     gl_rev[0]    PIN_99  bank 6, 3.3 V LVTTL input   DB1 pin 11 (LED D3 + 1 kohm to 3.3 V stays attached)
#     gl_rev[1]    PIN_100 bank 6, 3.3 V LVTTL input   DB1 pin 15 (LED D4)
#     gl_rev[2]    PIN_101 bank 6, 3.3 V LVTTL input   DB1 pin 17 (LED D5)
#     gl_fs_rxd    PIN_89  bank 5, 2.5 V, CLK6/DIFFCLK_3p (input only) DB12 pin 5:
#                          fast serial in (framed, carries the commands), or the plain
#                          command UART in the CMD_UART=1 build (2.5 V levels or open drain
#                          from the Gowin side against the weak pull-up enabled here)
#
#   The three LED pins are 3.3 V inputs driven by the adapter's LVDS receiver (3.3 V CMOS);
#   the LED + 1 kohm pull-up on each pin loads the driver with ~1.5 mA when low.
#   The 2.5 V-bank inputs (PIN_88, PIN_89) must be driven with 2.5 V-compatible levels by
#   the adapter (a 3.3 V driver would forward-bias the PCI clamp diode into the 2.5 V rail):
#   the clamp is explicitly disabled on them below so that a 3.3 V level is tolerated
#   (VI max 3.6 V per the Cyclone IV handbook), but 2.5 V drive is still the intended use.

if {![info exists GL_LANES]} { set GL_LANES 6 }

# ---------------------------------------------------------------- cable 1
if {$GL_LANES == 6} {
  set_location_assignment PIN_98 -to gl_clk
  set_location_assignment PIN_72 -to gl_d[0]
  set_location_assignment PIN_76 -to gl_d[1]
  set_location_assignment PIN_77 -to gl_d[2]
  set_location_assignment PIN_80 -to gl_d[3]
  set_location_assignment PIN_83 -to gl_d[4]
  set_location_assignment PIN_85 -to gl_d[5]
  set_instance_assignment -name IO_STANDARD "3.3-V LVTTL" -to gl_clk
  set_instance_assignment -name CURRENT_STRENGTH_NEW 8MA -to gl_clk
} else {
  set_location_assignment PIN_76 -to gl_clk
  set_location_assignment PIN_77 -to gl_d[0]
  set_location_assignment PIN_83 -to gl_d[1]
  set_location_assignment PIN_85 -to gl_d[2]
  set_instance_assignment -name IO_STANDARD "2.5 V" -to gl_clk
  set_instance_assignment -name OUTPUT_TERMINATION "SERIES 50 OHM WITHOUT CALIBRATION" -to gl_clk
}
set_instance_assignment -name IO_STANDARD "2.5 V" -to gl_d[*]
set_instance_assignment -name OUTPUT_TERMINATION "SERIES 50 OHM WITHOUT CALIBRATION" -to gl_d[*]
set_instance_assignment -name FAST_OUTPUT_REGISTER ON -to gl_d[*]
set_instance_assignment -name FAST_OUTPUT_REGISTER ON -to gl_clk

set_location_assignment PIN_86 -to gl_status_txd
set_location_assignment PIN_87 -to gl_aux_out
set_instance_assignment -name IO_STANDARD "2.5 V" -to gl_status_txd
set_instance_assignment -name IO_STANDARD "2.5 V" -to gl_aux_out
set_instance_assignment -name FAST_OUTPUT_REGISTER ON -to gl_status_txd

# ---------------------------------------------------------------- cable 2
set_location_assignment PIN_88  -to gl_rev_clk
set_location_assignment PIN_99  -to gl_rev[0]
set_location_assignment PIN_100 -to gl_rev[1]
set_location_assignment PIN_101 -to gl_rev[2]
set_location_assignment PIN_89  -to gl_fs_rxd
set_instance_assignment -name IO_STANDARD "2.5 V" -to gl_rev_clk
set_instance_assignment -name IO_STANDARD "3.3-V LVTTL" -to gl_rev[*]
set_instance_assignment -name IO_STANDARD "2.5 V" -to gl_fs_rxd
set_instance_assignment -name FAST_INPUT_REGISTER ON -to gl_rev[*]
set_instance_assignment -name FAST_INPUT_REGISTER ON -to gl_fs_rxd
set_instance_assignment -name WEAK_PULL_UP_RESISTOR ON -to gl_fs_rxd
# 2.5 V-bank inputs that may see 3.3 V levels: no clamp diode into the 2.5 V rail
set_instance_assignment -name CLAMPING_DIODE OFF -to gl_rev_clk
set_instance_assignment -name CLAMPING_DIODE OFF -to gl_fs_rxd
