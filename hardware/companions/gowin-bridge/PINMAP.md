# gowin-bridge pin map (authoritative)

Two adapter PCBs ("bridge boards") carry a 12-bit / 76.8 MSPS ADC stream from a Hermes Lite 2
(Cyclone IV EP4CE22E22C8, E144) to a Sipeed Tang Mega 138K dock (GW5AST-138, PG484) over
**three HDMI cables**, carry the same bandwidth back, and carry a **fast full-duplex control
channel** on the third cable.

* **Board A = `hl2-bridge`** plugs onto the HL2 headers **DB1** (2x10) and **DB12** (3x2).
  Three **mini HDMI (Type C)** sockets, left to right: **`OUT`, `AUX`, `IN`**.
* **Board B = `tang-bridge`** plugs onto the Tang dock header **J14** (2x40, Bank 4).
  Three **full-size HDMI (Type A)** sockets, left to right: **`IN`, `AUX`, `OUT`**.
* The two boards are delivered as **one 94 x 90 mm V-scored panel** (`README.md`).

Revision: **rev C**, 2026-09-12. Supersedes rev B (asymmetric 6-lanes-out / 3-lanes-back with a
single-ended slow control wire) and rev A (two dual-link DVI-D sockets).

This file is the single source of truth. The gateware constraints
(`gateware/variants/hl2b5up_gowinlink/gowinlink_pins.tcl` on the HL2 side, `gowin/proj/*.cst` on
the Gowin side) must match it exactly. If anything here disagrees with a brief, this file wins.

---

## 0. What changed from rev B, and why

| rev B | rev C |
|---|---|
| Forward 6 lanes at 153.6 Mbit/s, reverse 3 lanes at 307.2 Mbit/s | **Every lane DDR at 153.6 MHz = 307.2 Mbit/s, both directions**, 3 lanes each way |
| Two forward cables (`OUT 1`, `OUT 2`), each with its own clock | **One** forward cable, one reverse cable, one **bidirectional auxiliary** cable |
| Control channel: single-ended unshielded wire, ~10-25 Mbit/s | **Differential, source-synchronous, 307.2 Mbit/s each way, full duplex** on the auxiliary cable |
| Two radios: 460.8 Mbit/s each way (3 lanes at 153.6) | Two radios: **921.6 Mbit/s each way - the complete raw ADC stream** |
| Forward lane 3 on PIN_80, the 21 pF VREF pin | **No fast fixed-direction lane on PIN_80.** It carries the slowest auxiliary lane instead |
| PIN_87 = forward clock B | PIN_87 = auxiliary forward data |
| PIN_89 = slow command input from the cable | **PIN_89 = the role strap, read locally** (section 2.4) |
| All 14 HL2 pins used, none spare; Tang J14 exact fit, none spare | All 14 HL2 pins used; **Tang J14 has one spare pin** (pin 36) |
| Two socket types, both self-symmetric | **Three socket types.** `OUT` and `IN` are complementary as before; `AUX` is self-complementary via a board strap (section 2) |

**The reason for the change.** rev B's asymmetry bought nothing. Both directions carried the same
921.6 Mbit/s, the reverse direction needed 307.2 Mbit/s per lane to do it, and so 307.2 Mbit/s had
to work anyway - deferring it to one direction only hid the risk instead of removing it. Spending
the freed pins on a symmetric auxiliary cable restores a fast control channel (a 12 to 30 times
improvement on rev B's single unshielded wire) and puts the forward link onto the 3-lane geometry
the gateware has **already simulated** (`gateware/gowinlink/LINK_SPEC.md`, `GL_LANES = 3`).

### 0.1 Corrections carried forward from rev B - still true, still important

* **DB12 pin 5 is FPGA PIN_89 and DB12 pin 6 is PIN_88.** Read out of
  `hardware/hl/hermeslite.net`; rev A had these swapped and was wired wrong.
* **The LEDs on DB1 pins 9, 11, 15 and 17 are 1 k pull-UPS to +3V3** through the LED (cathode at
  the FPGA pin), not 1 k to ground. A receiver driving those pins must **sink** about 1.4 mA.

---

## 1. The three cables

| Cable | Sockets | Direction | Clock | Data | Payload |
|---|---|---|---|---|---|
| **1 "forward"** | board A `OUT` -> board B `IN` | fixed, one way | 153.6 MHz forwarded | 3 lanes DDR, 307.2 Mbit/s each | **921.6 Mbit/s** = 12 bits x 76.8 MSPS |
| **2 "reverse"** | board B `OUT` -> board A `IN` | fixed, one way | 153.6 MHz, Gowin PLL | 3 lanes DDR, 307.2 Mbit/s each | **921.6 Mbit/s** |
| **3 "auxiliary"** | board A `AUX` <-> board B `AUX` | **bidirectional, full duplex** | one 153.6 MHz clock **each way** | 1 lane DDR each way, 307.2 Mbit/s | **307.2 Mbit/s each way** |

### 1.1 The two configurations

**HL2 to Gowin - three cables, both boards as supplied:**

```
radio  OUT  ==mini-to-full-size==>  IN   Tang dock
radio  AUX  <=mini-to-full-size=>   AUX  Tang dock      (board A strapped ROLE A,
radio  IN   <=mini-to-full-size==   OUT  Tang dock       board B strapped ROLE B)
```

**Two HL2 radios back to back - two or three cables, no Gowin:**

```
radio 1  OUT  ==mini-to-mini==>  IN   radio 2
radio 2  OUT  ==mini-to-mini==>  IN   radio 1
radio 1  AUX  <=mini-to-mini=>   AUX  radio 2      (radio 1 strapped ROLE A,
                                                    radio 2 strapped ROLE B)
```

Each radio sends the **complete raw ADC stream, 921.6 Mbit/s**, and receives the other's. The
auxiliary cable is optional and gives a 307.2 Mbit/s control channel each way.

**`OUT` and `IN` are the two OUTER sockets on both boards**, so the two-radio case never has three
cable boots side by side (`DESIGN_NOTES.md` 6.3).

---

## 2. Socket types

### 2.1 `OUT` - everything driven

| Role in the socket | Wiring |
|---|---|
| TMDS **clock** pair | driven: forwarded 153.6 MHz |
| TMDS **data 0 / 1 / 2** pairs | driven: lanes 0, 1, 2 |
| **SCL** | slow status UART out, single-ended |
| **HPD** | **100 R to GND**, so the far end detects the cable |
| **+5 V** | not connected on board A; DNP link to the 5 V rail on board B |
| CEC, Reserved/Utility, SDA | not connected |
| 4 pair shields, DDC/CEC ground, shell | GND |

### 2.2 `IN` - everything received

Identical pair ordering and identical SCL position to `OUT`. That is the symmetry requirement: a
straight pin-1-to-pin-1 cable joins any `OUT` to any `IN` and every signal lands on its
counterpart.

| Role in the socket | Wiring |
|---|---|
| TMDS **clock** pair | received through an LVDS receiver |
| TMDS **data 0 / 1 / 2** pairs | received |
| **SCL** | **test pad only in rev C.** rev B's command wire lived here; PIN_89 now reads the strap instead, so there is no destination for it at the HL2 end |
| **HPD** | **10 k pull-up to +3V3 and read**; low = cable plugged in; gates the receiver enable |
| **+5 V** | DNP link to an on-board LDO on board A; not connected on board B |

### 2.3 `AUX` - two pairs each way, full duplex, role set by a strap

The four pairs are split into two fixed groups, and a board strap decides which group it drives:

| Group | Pairs | Carries |
|---|---|---|
| **G1** | TMDS **clock** + TMDS **data 0** | one 153.6 MHz clock and one 307.2 Mbit/s lane |
| **G2** | TMDS **data 1** + TMDS **data 2** | one 153.6 MHz clock and one 307.2 Mbit/s lane |

| Strap | Drives | Receives |
|---|---|---|
| **ROLE A** | G1 (clock + data 0) | G2 (data 1 + data 2) |
| **ROLE B** | G2 (data 1 + data 2) | G1 (clock + data 0) |

**G2's "clock" is the TMDS data-1 pair and its "data" is the data-2 pair.** The HDMI connector's
pair names are just wire names here; each group carries its own clock so each direction is
source-synchronous and the two directions are independent.

A straight cable between a ROLE A board and a ROLE B board maps G1 to G1 and G2 to G2, so the
A-board's driven clock lands on the B-board's received clock and vice versa. **`AUX` is therefore
self-complementary: any two boards work, provided one is strapped A and the other B.** That is what
makes the auxiliary cable usable radio-to-radio, which a fixed mixed-direction socket could never be.

| Role in the socket | Wiring |
|---|---|
| **SCL, HPD, +5 V, CEC, Reserved, SDA** | **not connected, test pad only.** The auxiliary cable is detected by clock activity in the gateware, not by HPD: an HPD scheme would itself have to be role-dependent and neither board has a spare pin to read it |
| 4 pair shields, DDC/CEC ground, shell | GND |

### 2.4 What the strap does, and why a wrongly set strap is harmless

**One 1x3 pin header (`ROLE`) with a single shunt, plus one single-gate
inverter** produces two guaranteed-complementary 3.3 V levels, `ROLE` and
`ROLE_N`:

```
   J9 ROLE      1 +3V3 --- 2 ROLE --- 3 GND
                shunt on 1-2  =>  ROLE A        shunt on 2-3  =>  ROLE B

   U11 74LVC1G04:  ROLE_N = NOT ROLE      10 k pull-up on ROLE_N
```

**Why an inverter rather than a second link or a double-pole jumper.** The
scheme needs a complementary *pair*, and the two halves must never disagree.
An earlier draft of this section used a 2x3 header with two shunts as a
double-pole changeover, which is wrong: a user can put one shunt in the A
position and the other in the B position, and one of the four resulting
combinations - both levels low - **enables the G2 translator port while the
gateware believes it is in ROLE B and is driving those pins as outputs.** That
is CMOS-against-CMOS contention on PIN_72 and PIN_80, tens of milliamps, and it
is exactly the failure this design must not have. A single shunt plus one
inverter gate makes the complement a property of the circuit rather than of the
user's attention, at a cost of one SOT-23-5 part and a few cents.

The 10 k **pull-up** on `ROLE_N` sets the safe failure direction: if the
inverter is missing, unpowered or dead, `ROLE_N` reads high, which *disables*
the G2 translator port. The auxiliary link then does not work, and nothing is
stressed. A pull-down would have done the opposite.

`ROLE` / `ROLE_N` drive four things:

| Controls | ROLE A | ROLE B |
|---|---|---|
| G1 LVDS driver pair (`EN` = `ROLE`) | enabled | tri-stated |
| G2 LVDS driver pair (`EN` = `ROLE_N`) | tri-stated | enabled |
| Translator port carrying G1 toward the HL2 (`OE` = `ROLE`) | disabled | enabled |
| Translator port carrying G2 toward the HL2 (`OE` = `ROLE_N`) | enabled | disabled |
| **100 R termination on each `AUX` pair** | fit on G2 (the pairs it receives) | fit on G1 |

The **termination is four solder links, not electrical**, because a switched 100 R would need an
analogue switch. Fit the two links for the pairs this board *receives*. If both ends terminate a
driven pair the driver sees 50 R and the differential swing halves from about 350 mV to about
175 mV against the receiver's 100 mV threshold - it would still work, with 75 mV of margin over a
2 m cable, which is not enough. Hence the links.

**The FPGA reads the strap on PIN_89** (DB12 pin 5, an input-only pin that has no other use in
rev C) through a translator channel, so the gateware knows its own role and sets the direction of
its four auxiliary pins to match.

**A wrongly set or inconsistent strap cannot damage anything, and this is the argument:**

1. **LVDS driver against LVDS driver is harmless.** An LVDS driver is a **current source**: the
   DS90LV047A steers about 3.5 mA into the 100 R load to make its 350 mV swing, and its
   short-circuit output current is internally limited (`IOS`, specified, of order 10 mA and bounded
   well below 25 mA). Two drivers fighting on one pair present each other with a current source,
   not a low-impedance voltage rail, so the pair settles at some intermediate differential voltage
   and the data is garbled. Dissipation per output stays in the milliwatts. **The signal is lost;
   nothing is stressed.**
2. **The dangerous case would be a translator output fighting an HL2 output** on a shared
   auxiliary pin - two CMOS push-pull stages, tens of milliamps. **The strap read on PIN_89 is what
   prevents it.** The gateware follows `ROLE`, so whenever the board's translator is driving an
   auxiliary pin the gateware has already made that pin an input, and whenever the gateware drives
   the pin the translator port for it is disabled by the same `ROLE` level. The two always agree
   because they are the same wire.
3. **There is only one control point, so the two levels cannot disagree.** With a single shunt and
   an inverter, `ROLE_N` is always the complement of `ROLE`, so the invariant that matters - *the
   translator port driving a pin is disabled exactly when the gateware drives that pin* - holds by
   construction for both groups. The only remaining mis-set is putting the shunt in the wrong
   position, which makes both boards the same role: both drive the same group, both receive the
   other, the LVDS contention of point 1 garbles both directions, no CMOS contention occurs, and
   the link simply does not come up.

---

## 3. HDMI connector pin numbers

Type A (full size, board B) and Type C (mini, board A) carry the same 19 signals in a **different
pin order**. Both tables below are the standard HDMI receptacle pinouts, cross-checked against the
KiCad `Connector` library symbols and against the SOFNG HDMI-519 datasheet's own pin-assignment
table. **SCL is pin 15, SDA 16, +5 V 18 and HPD 19 in both types**; only the four pairs and the two
ground/utility pins move.

| Signal / role | **Type A pin** | **Type C pin** |
|---|---|---|
| TMDS data 2 + | 1 | 2 |
| TMDS data 2 shield = GND | 2 | 1 |
| TMDS data 2 - | 3 | 3 |
| TMDS data 1 + | 4 | 5 |
| TMDS data 1 shield = GND | 5 | 4 |
| TMDS data 1 - | 6 | 6 |
| TMDS data 0 + | 7 | 8 |
| TMDS data 0 shield = GND | 8 | 7 |
| TMDS data 0 - | 9 | 9 |
| TMDS clock + | 10 | 11 |
| TMDS clock shield = GND | 11 | 10 |
| TMDS clock - | 12 | 12 |
| CEC - not connected | 13 | 14 |
| Reserved / Utility - not connected | 14 | **17** |
| **SCL** | **15** | **15** |
| SDA - not connected | 16 | 16 |
| DDC/CEC ground = GND | **17** | **14** |
| **+5 V** | **18** | **18** |
| **HPD** | **19** | **19** |
| shell | shell | shell |

A commercial **mini-to-full-size HDMI cable wires signal to signal, not pin number to pin number**,
which is why board A can use Type C and board B Type A with no crossover anywhere.

---

## 4. Board A - HL2 side, socket by socket

### 4.1 `OUT` socket (J3, left) - all driven

| Role | Net | FPGA pin | Header pin | Bank / VCCIO | Rate | Notes |
|---|---|---|---|---|---|---|
| link clock | `O_CLK_P/N` | **PIN_98** | **DB1-9** | 6 / 3.3 V | 153.6 MHz | LED **D2** cathode + 1 k to +3V3 on this pin. Reaches the translator through a **100 R / 660 R divider** (`DESIGN_NOTES.md` 3.2). |
| lane 0 | `O_D0_P/N` | **PIN_76** | **DB1-2** | 5 / Vlvds 2.5 V | 307.2 Mbit/s | |
| lane 1 | `O_D1_P/N` | **PIN_77** | **DB1-3** | 5 / Vlvds 2.5 V | 307.2 Mbit/s | |
| lane 2 | `O_D2_P/N` | **PIN_83** | **DB1-5** | 5 / Vlvds 2.5 V | 307.2 Mbit/s | |
| slow out (SCL) | `O_SLOW` | **PIN_86** | **DB12-1** | 5 / Vlvds 2.5 V | 115200 8N1, up to ~3 Mbaud | Single-ended straight onto the cable through 100 R, no driver chip. Kept as a bring-up aid. |
| HPD | `O_HPD` | - | - | - | DC | 100 R to GND. |
| +5 V | - | - | - | - | - | **not connected.** |

### 4.2 `AUX` socket (J4, middle) - bidirectional, strap-selected

Board A ships strapped **ROLE A**: it drives G1 and receives G2.

| Group | Role | Net | FPGA pin | Header pin | Bank | Rate | Notes |
|---|---|---|---|---|---|---|---|
| **G1** | auxiliary clock | `AX_CLK_P/N` | **PIN_85** | **DB1-6** | 5 / 2.5 V | 153.6 MHz | **Bidirectional.** Output in ROLE A. A clean ordinary pin - deliberately the group the default role drives. |
| **G1** | auxiliary data | `AX_D0_P/N` | **PIN_87** | **DB12-2** | 5 / 2.5 V | 307.2 Mbit/s | **Bidirectional.** Output in ROLE A. |
| **G2** | auxiliary clock | `AX_D1_P/N` | **PIN_72** | **DB1-1** | 4 / Veth 2.5 V | 153.6 MHz | **Bidirectional.** Input in ROLE A. Reaches PIN_72 only through the HL2's jumper **J25**, and shares that net with uFL pad **CL8** (section 6.2). Cuttable link `SL_D0` retained. |
| **G2** | auxiliary data | `AX_D2_P/N` | **PIN_80** | **DB1-4** | 5 / 2.5 V | 307.2 Mbit/s, **see below** | **Bidirectional.** Input in ROLE A. **VREFB5N0, ~21 pF of pin capacitance.** |
| - | SCL, HPD, +5 V | - | - | - | - | - | not connected, test pads. |

**PIN_80 is the rate-limited lane on either board.** At 21 pF of pin capacitance plus about 6 pF of
trace and header, a 2.5 V CMOS source of roughly 25 R gives a 10-90 % edge of **1.49 ns, which is
46 % of the 3.255 ns unit interval** at 307.2 Mbit/s. It works, with the narrowest eye anywhere in
the design, and is **comfortable to about 135 Mbit/s**. Use the auxiliary channel at a lower rate if
the bench says so; nothing else depends on it. The Cyclone IV handbook permits a VREF pin as a
regular I/O when its bank carries no VREF-based standard (HL2 bank 5 carries only `2.5 V`), and
warns only qualitatively of "reduced performance of toggle rate and tCO" with **no numeric limit
published anywhere** - so the figure above is a calculation, not a datasheet guarantee.

**The G2 auxiliary clock arrives on PIN_72, an ordinary I/O, not a dedicated clock input.** Both of
the HL2's dedicated clock inputs are spent - PIN_88 on the reverse link and PIN_89 on the strap. A
regular I/O can drive the Cyclone IV global clock network but **cannot feed a PLL input**, so the
gateware must capture the G2 auxiliary lane directly with that clock. For a source-synchronous DDR
lane that is the right architecture anyway; it costs a PLL's jitter filtering, which a 1-lane
control channel does not need.

### 4.3 `IN` socket (J5, right) - all received

| Role | Net | FPGA pin | Header pin | Bank / VCCIO | Rate | Notes |
|---|---|---|---|---|---|---|
| link clock | `I_CLK_P/N` | **PIN_88** | **DB12-6** | 5 / 2.5 V, **input only** | 153.6 MHz | `CLK7` / `DIFFCLK_3n`, a dedicated clock input. Fed at 2.5 V through the translator. |
| reverse lane 0 | `I_D0_P/N` | **PIN_99** | **DB1-11** | 6 / 3.3 V | 307.2 Mbit/s | LED **D3** + 1 k to +3V3; the receiver must sink ~1.4 mA when low. |
| reverse lane 1 | `I_D1_P/N` | **PIN_100** | **DB1-15** | 6 / 3.3 V | 307.2 Mbit/s | LED **D4**. |
| reverse lane 2 | `I_D2_P/N` | **PIN_101** | **DB1-17** | 6 / 3.3 V | 307.2 Mbit/s | LED **D5**. |
| slow (SCL) | `I_SLOW` | - | - | - | - | **test pad only** (section 2.2). |
| HPD | `I_HPD` | - | - | - | DC | 10 k pull-up; low = cable plugged in; gates the `IN` receiver's enable. |
| +5 V | `I_5V_PIN` | - | - | - | - | DNP link `SL_5V` to an on-board AMS1117. |

### 4.4 Complete HL2 header usage

#### DB1 (2x10)

| DB1 | FPGA | Bank / VCCIO | rev C use | Direction w.r.t. HL2 |
|---|---|---|---|---|
| 1 | 72 (via J25) | 4 / 2.5 V | **`AUX` G2 clock - BIDIRECTIONAL.** Cuttable link `SL_D0`. | **in** (ROLE A) / out (ROLE B) |
| 2 | 76 | 5 / 2.5 V | `OUT` lane 0 | out |
| 3 | 77 | 5 / 2.5 V | `OUT` lane 1 | out |
| 4 | 80 | 5 / 2.5 V | **`AUX` G2 data - BIDIRECTIONAL.** 21 pF VREF pin. | **in** (ROLE A) / out (ROLE B) |
| 5 | 83 | 5 / 2.5 V | `OUT` lane 2 | out |
| 6 | 85 | 5 / 2.5 V | **`AUX` G1 clock - BIDIRECTIONAL.** | **out** (ROLE A) / in (ROLE B) |
| 7 | - | Vlvds rail | stack-through + test point; DNP link `SL_VLVDS` | HL2 output |
| 8 | - | Vlvds rail | same net as pin 7 | HL2 output |
| 9 | 98 | 6 / 3.3 V | `OUT` clock, through the 100 R / 660 R divider. LED D2 + 1 k to +3V3. | out |
| 10 | 90 | 6 / 3.3 V | **not connected** (CW/PTT ring). Stack-through tail only. | - |
| 11 | 99 | 6 / 3.3 V | `IN` reverse lane 0 | **in** |
| 12 | 91 | 6 / 3.3 V | **not connected** (CW/PTT tip). Stack-through tail only. | - |
| 13, 14 | - | GND | ground | - |
| 15 | 100 | 6 / 3.3 V | `IN` reverse lane 1 | **in** |
| 16 | 103 | 6 / 3.3 V | `SCL1` - stack-through + test point only | - |
| 17 | 101 | 6 / 3.3 V | `IN` reverse lane 2 | **in** |
| 18 | 104 | 6 / 3.3 V | `SDA1` - stack-through + test point only | - |
| 19, 20 | - | +3V3 | `DB1_3V3`, the board supply | HL2 output |

#### DB12 (3x2) - note pins 5 and 6

| DB12 | FPGA | rev C use | Direction w.r.t. HL2 |
|---|---|---|---|
| 1 | 86 | slow status UART out -> `OUT` SCL | out |
| 2 | 87 | **`AUX` G1 data - BIDIRECTIONAL** | **out** (ROLE A) / in (ROLE B) |
| 3, 4 | - | GND | - |
| 5 | **89** | **the ROLE strap, read locally.** Input only. | **in** |
| 6 | **88** | `IN` clock, 153.6 MHz, through the translator. Input only. | **in** |

#### The pin budget - 14 used, none spare

| Direction | Pins |
|---|---|
| **Outputs (5)** | PIN_98 (`OUT` clock), PIN_76, 77, 83 (`OUT` lanes), PIN_86 (slow status out) |
| **Inputs (5)** | PIN_88 (`IN` clock), PIN_99, 100, 101 (`IN` lanes), PIN_89 (strap read) |
| **Bidirectional (4)** | PIN_72, 80, 85, 87 (`AUX`) |

### 4.5 Required HL2 gateware changes

```tcl
# ---- cable 1, OUT: 3 lanes DDR at 153.6 MHz, the GL_LANES = 3 geometry ----
set_location_assignment PIN_98 -to gl_clk         ;# was the 76.8 MHz clock in the 6-lane build
set_location_assignment PIN_76 -to gl_d[0]
set_location_assignment PIN_77 -to gl_d[1]
set_location_assignment PIN_83 -to gl_d[2]
set_instance_assignment -name IO_STANDARD "3.3-V LVTTL" -to gl_clk
set_instance_assignment -name CURRENT_STRENGTH_NEW 8MA  -to gl_clk
set_instance_assignment -name IO_STANDARD "2.5 V" -to gl_d[*]
set_instance_assignment -name OUTPUT_TERMINATION "SERIES 50 OHM WITHOUT CALIBRATION" -to gl_d[*]
set_instance_assignment -name FAST_OUTPUT_REGISTER ON -to gl_d[*]
set_instance_assignment -name FAST_OUTPUT_REGISTER ON -to gl_clk

# ---- cable 2, IN ----
set_location_assignment PIN_88  -to gl_rev_clk    ;# DB12 pin 6, dedicated clock input
set_location_assignment PIN_99  -to gl_rev[0]
set_location_assignment PIN_100 -to gl_rev[1]
set_location_assignment PIN_101 -to gl_rev[2]
set_instance_assignment -name IO_STANDARD "2.5 V" -to gl_rev_clk
set_instance_assignment -name IO_STANDARD "3.3-V LVTTL" -to gl_rev[*]
set_instance_assignment -name FAST_INPUT_REGISTER ON -to gl_rev[*]
set_instance_assignment -name CLAMPING_DIODE OFF -to gl_rev_clk

# ---- the ROLE strap, read locally. NEW in rev C ----
set_location_assignment PIN_89 -to gl_role        ;# DB12 pin 5, input only
set_instance_assignment -name IO_STANDARD "2.5 V" -to gl_role
set_instance_assignment -name CLAMPING_DIODE OFF  -to gl_role
# gl_role HIGH = ROLE A = this board drives AUX G1 and receives G2.
# The gateware MUST set the four AUX pin directions from gl_role. That is what
# makes a wrongly set strap harmless (PINMAP.md 2.4).

# ---- cable 3, AUX: four BIDIRECTIONAL pins. NEW in rev C ----
set_location_assignment PIN_85 -to gl_aux_g1_clk  ;# out in ROLE A, in in ROLE B
set_location_assignment PIN_87 -to gl_aux_g1_dat
set_location_assignment PIN_72 -to gl_aux_g2_clk  ;# in in ROLE A, out in ROLE B
set_location_assignment PIN_80 -to gl_aux_g2_dat
set_instance_assignment -name IO_STANDARD "2.5 V" -to gl_aux_*
set_instance_assignment -name OUTPUT_TERMINATION "SERIES 50 OHM WITHOUT CALIBRATION" -to gl_aux_*
# PIN_72 and PIN_80 are used as INPUTS for the first time in any revision.
# Permitted; PIN_80 is VREFB5N0 with 21 pF and is the slowest lane (section 4.2).
# The G2 clock on PIN_72 is an ordinary I/O: route it to a global clock network,
# NOT to a PLL input, which a regular I/O cannot feed.
```

`gl_aux_out` and the 6-lane `GL_LANES = 6` geometry are both gone. The fallback 3-lane geometry in
`LINK_SPEC.md` becomes the only forward geometry, on new pins.

---

## 5. Board B - Tang dock J14

Row convention, from the Sipeed dock schematic: **even pin = silkscreen "P" = Gowin `A` leg =
differential T; odd pin = "N" = Gowin `B` leg = differential C**. Adjacent odd/even pins of a column
are a true pair **except pins 33 and 34**. Every pin used is in **Bank 4** (a bottom bank, VCCIO
3.3 V, so the on-die 100 R `DIFF_RESISTOR` is available).

Board B ships strapped **ROLE B**: it receives `AUX` G1 and drives G2.

| J14 | Ball | Gowin IO | Dedicated clock function | Net | Socket / role | Dir | IO type | Rate |
|---|---|---|---|---|---|---|---|---|
| **9** | W17 | IOB106B | - | `LINK_R0` | `OUT` lane 0 | **out** | LVCMOS33 | 307.2 Mbit/s |
| **10** | V17 | IOB106A | - | `LINK_D0` | `IN` lane 0 | **in** | LVCMOS33 / LVDS25 | 307.2 Mbit/s |
| 11 | - | - | - | `P5V_J14` | `5V_Peripheral` | power | 5 V | - |
| 12 | - | - | - | `GND` | **the only ground pin** | - | - | - |
| **13** | W22 | IOB124B | - | `LINK_R1` | `OUT` lane 1 | **out** | LVCMOS33 | 307.2 Mbit/s |
| **14** | W21 | IOB124A | - | `LINK_D1` | `IN` lane 1 | **in** | LVCMOS33 / LVDS25 | 307.2 Mbit/s |
| **15** | P17 | IOB135B | - | `LINK_R2` | `OUT` lane 2 | **out** | LVCMOS33 | 307.2 Mbit/s |
| **16** | N17 | IOB135A | - | `LINK_D2` | `IN` lane 2 | **in** | LVCMOS33 / LVDS25 | 307.2 Mbit/s |
| **17** | N14 | IOB142B | - | `LINK_AUX_G2_CLK` | `AUX` G2 clock | **out** | LVCMOS33 | 153.6 MHz |
| **18** | N13 | IOB142A | - | `LINK_AUX_G1_DAT` | `AUX` G1 data | **in** | LVCMOS33 / LVDS25 | 307.2 Mbit/s |
| **19** | V20 | IOB120B | SGCLKC_5 / BPLL2_C_IN0 | `LINK_SLOW_IN` | `IN`... see note | **in** | **LVTTL33** | status UART |
| **20** | U20 | IOB120A | **SGCLKT_5 / BPLL2_T_IN0 / BPLL3_T_IN0** | `LINK_CLK` | **`IN` clock = the PLL reference** | **in** | LVCMOS33 / LVDS25 | **153.6 MHz** |
| **31** | Y19 | IOB116B | MGCLKC_4 / BPLL2_C_FB0 | `LINK_AUX_G2_DAT` | `AUX` G2 data | **out** | LVCMOS33 | 307.2 Mbit/s |
| **32** | Y18 | IOB116A | **MGCLKT_4 / BPLL2_T_FB0** | `LINK_AUX_G1_CLK` | **`AUX` G1 clock received** | **in** | LVCMOS33 / LVDS25 | **153.6 MHz** |
| **33** | T20 | IOB102B | - | `LINK_PRESENT` | `IN` cable detect | **in** | LVCMOS33, PULL_MODE=UP | DC |
| **34** | N15 | IOB146A | - | `LINK_ROLE` | the ROLE strap, read locally | **in** | LVCMOS33 | DC |
| **35** | U18 | IOB112B | - | `LINK_REVCLK` | `OUT` clock, PLL-derived | **out** | LVCMOS33 | 153.6 MHz |
| **36** | U17 | IOB112A | - | - | **SPARE** | - | - | - |

**Note on pin 19.** The `IN` socket's SCL carries nothing in rev C (section 2.2), so pin 19 is fed
by the **`OUT` socket's SCL** instead - the status UART still travels from the HL2 on cable 1, whose
SCL lands on board B's `IN` socket. Keep the net name `LINK_SLOW_IN` and `IO_TYPE=LVTTL33`: it is
driven by an HL2 2.5 V output down an unshielded wire, so `LVCMOS33`'s 2.0 V threshold would leave
zero guaranteed margin where `LVTTL33`'s 1.7 V leaves 300 mV.

**Every other J14 pin is electrically open on board B**, so PMOD0 (1-8), PMOD1 (21-28), the
option-resistor pins (29/30) and the remaining DVP camera pins (37-40) stay usable.

### 5.1 Why these pins

* The avoid-list is unchanged: **1-8** PMOD0, **21-28** PMOD1 and DVP camera, **29/30** behind
  unverified option resistors, **37-40** DVP camera. What is left is **7 true pairs** - (9,10)
  (13,14) (15,16) (17,18) (19,20) (31,32) (35,36) - plus pairless **33** and **34**: 16 signal pins.
* rev C needs **15**, so **pin 36 (U17) is spare** - the first spare J14 pin in any revision.
* **The `IN` clock is on pin 20 = U20 = `SGCLKT_5` = `BPLL2/BPLL3 CLKIN0`**, a dedicated global
  clock input that is also the PLL reference. Required: the Gowin PLL that generates the reverse
  transmit clocks takes its reference from here.
* **The received `AUX` G1 clock is on pin 32 = Y18 = `MGCLKT_4`**, also a dedicated clock input on
  the middle global clock network, so it can clock the G1 `IDDR` directly.
* **All six received differential signals sit on the A (T) leg of a true pair** - pins 10, 14, 16,
  18, 20 and 32 - so the future no-receiver-chip variant covers **every** received pair. rev B could
  not manage that for one lane.
* The two pairless pins 33 and 34 carry the two DC levels, which is the only thing they are good for.

### 5.2 Paste-ready Gowin constraints

```
# ==== cable 1, IN: received, 3.3 V CMOS from the LVDS receivers ====
IO_LOC  "link_clk"  U20;  IO_PORT "link_clk"  IO_TYPE=LVCMOS33 PULL_MODE=NONE HYSTERESIS=NONE;
IO_LOC  "link_d[0]" V17;  IO_PORT "link_d[0]" IO_TYPE=LVCMOS33 PULL_MODE=NONE HYSTERESIS=NONE;
IO_LOC  "link_d[1]" W21;  IO_PORT "link_d[1]" IO_TYPE=LVCMOS33 PULL_MODE=NONE HYSTERESIS=NONE;
IO_LOC  "link_d[2]" N17;  IO_PORT "link_d[2]" IO_TYPE=LVCMOS33 PULL_MODE=NONE HYSTERESIS=NONE;

# ==== cable 1 slow in: an HL2 2.5 V output straight down the cable ====
# LVTTL33 (VIH min 1.7 V) is MANDATORY; LVCMOS33 (2.0 V) leaves 0 mV of margin.
IO_LOC  "link_slow_in" V20; IO_PORT "link_slow_in" IO_TYPE=LVTTL33 PULL_MODE=NONE HYSTERESIS=NONE;

# ==== cable 2, OUT: transmitted into board B's LVDS driver inputs ====
IO_LOC  "link_revclk" U18; IO_PORT "link_revclk" IO_TYPE=LVCMOS33 DRIVE=8 PULL_MODE=NONE;
IO_LOC  "link_r[0]"   W17; IO_PORT "link_r[0]"   IO_TYPE=LVCMOS33 DRIVE=8 PULL_MODE=NONE;
IO_LOC  "link_r[1]"   W22; IO_PORT "link_r[1]"   IO_TYPE=LVCMOS33 DRIVE=8 PULL_MODE=NONE;
IO_LOC  "link_r[2]"   P17; IO_PORT "link_r[2]"   IO_TYPE=LVCMOS33 DRIVE=8 PULL_MODE=NONE;

# ==== cable 3, AUX. Board B is strapped ROLE B: receives G1, drives G2. ====
IO_LOC  "aux_g1_clk" Y18;  IO_PORT "aux_g1_clk" IO_TYPE=LVCMOS33 PULL_MODE=NONE HYSTERESIS=NONE;
IO_LOC  "aux_g1_dat" N13;  IO_PORT "aux_g1_dat" IO_TYPE=LVCMOS33 PULL_MODE=NONE HYSTERESIS=NONE;
IO_LOC  "aux_g2_clk" N14;  IO_PORT "aux_g2_clk" IO_TYPE=LVCMOS33 DRIVE=8 PULL_MODE=NONE;
IO_LOC  "aux_g2_dat" Y19;  IO_PORT "aux_g2_dat" IO_TYPE=LVCMOS33 DRIVE=8 PULL_MODE=NONE;

# ==== DC levels ====
IO_LOC  "link_present" T20; IO_PORT "link_present" IO_TYPE=LVCMOS33 PULL_MODE=UP;
IO_LOC  "link_role"    N15; IO_PORT "link_role"    IO_TYPE=LVCMOS33 PULL_MODE=NONE;
# link_role HIGH = ROLE A. Board B ships ROLE B, so it should read LOW.
# Read it and set the aux_g1_*/aux_g2_* directions from it, as the HL2 does.

# ==== J14 pin 36 (U17) is spare. Leave unconstrained. ====
```

### 5.3 The direct-LVDS ("no receiver chip") future variant

**All six received pairs** can bypass their receiver, via 12 DNP 0 R links:

| Socket / pair | + leg -> J14 (A/T leg) | - leg -> J14 (B/C leg) | Gowin pair | What that B leg normally carries |
|---|---|---|---|---|
| `IN` clock | 20 (U20) | 19 (V20) | IOB120 | the slow status UART in |
| `IN` lane 0 | 10 (V17) | 9 (W17) | IOB106 | `OUT` lane 0 |
| `IN` lane 1 | 14 (W21) | 13 (W22) | IOB124 | `OUT` lane 1 |
| `IN` lane 2 | 16 (N17) | 15 (P17) | IOB135 | `OUT` lane 2 |
| `AUX` G1 data | 18 (N13) | 17 (N14) | IOB142 | `AUX` G2 clock |
| `AUX` G1 clock | 32 (Y18) | 31 (Y19) | IOB116 | `AUX` G2 data |

To use it: move board B's `RX MODE` jumper to 1-2 so the receiver outputs tri-state, fit the links
for the pairs wanted, keep the external 100 R terminations, set `DIFF_RESISTOR=OFF`, and constrain
each pair as e.g. `IO_LOC "link_clk" U20,V20; IO_PORT "link_clk" IO_TYPE=LVDS25;`.

**What it costs:** every B-leg signal - the whole `OUT` socket and the whole `AUX` G2 direction.
What survives is `IN` as a 3-lane differential forward link plus `AUX` G1 inbound, with no reverse
path. A receive-only experiment, not a usable configuration.

---

## 6. HL2-side loads and hazards

### 6.1 The four LED pins are pull-**ups**

Verified in `hardware/hl/hermeslite.net`: on DB1 pins 9, 11, 15 and 17 the LED **cathode** is the
FPGA pin and the anode goes through **1 k to +3V3** (D2/R71, D3/R72, D4/R73, D5/R74, all `1K`). Each
carries a weak pull-up delivering **(3.3 - 1.9) / 1000 = 1.4 mA** when the pin is held low.

* On **DB1-9** (PIN_98, an output) it is harmless and holds the forward clock net high while the
  HL2 is unconfigured.
* On **DB1-11 / 15 / 17** the receiver must **sink 1.4 mA**. DS90LV048A specifies `VOL` <= 0.3 V at
  2 mA, so it is inside spec.
* **LEDs D3, D4 and D5 will glow or flicker with reverse-link data.** Unavoidable, harmless.
* The stock `hl2b5up_main` gateware drives DB1 11/15/17 as LED outputs. The `RX MODE` jumper holds
  the `IN` receiver off until the right gateware is loaded, and the default setting keeps it off
  whenever the `IN` cable is unplugged.

### 6.2 `AUX` G2's clock sits on a net with a uFL stub

`hermeslite.net`: `Net-(DB1-Pad1) = DB1.1 + J25.2` and `Net-(CL8-Pad1) = U2.72 + J25.1 + CL8.1`.

* **HL2 jumper J25 must be closed** or the `AUX` G2 clock is dead.
* With J25 closed the net also carries uFL pad **CL8**, an unterminated stub on the HL2 that board A
  cannot remove. In **ROLE A** the stub is driven by board A's receiver through the translator; in
  **ROLE B** it is driven by the HL2 itself as a 153.6 MHz clock output, which is the worse case.
  If the `AUX` G2 direction misbehaves at speed, this is the first suspect.
* Board A's cuttable link `SL_D0` isolates *board A* from the net; it does not remove the stub.

### 6.3 Deliberately unused

* **DB1 pins 10 and 12** (FPGA 90/91, CW key inputs behind RC filters) - not connected.
* **DB1 pins 16 and 18** (`SCL1`/`SDA1`) - stack-through and a test point only.
* **DB1 pins 7 and 8** (the HL2's `Vlvds` rail) - stack-through, test point, DNP link `SL_VLVDS`.
* **J14 pins 1-8, 21-30, 37-40** on the dock - electrically open. **Pin 36 is spare.**
* **HDMI CEC, Reserved/Utility and SDA** on all six sockets; **SCL and HPD on both `AUX` sockets**;
  **SCL on both `IN` sockets**.

## 7. Known conflicts

* Board A occupies **both** DB1 and DB12, so it is mutually exclusive with the AK4951 / "HL2+"
  audio companion and with the HL2's own stock two-radio link (which uses DB12 1/2 and 5/6).
* Board A is compatible with the N2ADR filter board (DB7) and the N2ADR/Pico IO Board - no
  electrical overlap and, since rev B, no mechanical overlap either.
* For coherent two-radio operation the HL2's clock-chip coax link (CL8/CL2) is still required, and
  note section 6.2: CL8 shares the `AUX` G2 clock net.
* **`AUX` requires one board strapped ROLE A and the other ROLE B.** Two boards strapped the same
  will not bring the auxiliary link up; nothing is damaged (section 2.4).
