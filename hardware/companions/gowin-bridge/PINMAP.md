# gowin-bridge pin map (authoritative)

Two adapter PCBs ("bridge boards") carry a 12-bit / 76.8 MSPS ADC stream from a Hermes Lite 2
(Cyclone IV EP4CE22E22C8, E144) to a Sipeed Tang Mega 138K dock (GW5AST-138, PG484) over **two
dual-link DVI-D cables**, one per direction.

* **Board A = `hl2-bridge`** plugs onto the HL2 headers **DB1** (2x10) and **DB12** (3x2).
* **Board B = `tang-bridge`** plugs onto the Tang dock header **J14** (2x40 holes, Bank 4; the user
  solders a 2x20 male pin header into the bare plated holes).
* **Cable 1 "FWD"** = HL2 -> Gowin. Every pair is driven by board A and received on board B.
* **Cable 2 "REV"** = Gowin -> HL2. Every pair is driven by board B and received on board A.

This file is the single source of truth. The gateware constraints (`gateware/variants/*gowin*`,
`gowin/proj/*.cst`) must match it exactly. If anything here disagrees with a brief, this file wins.

Revision: **rev A**, 2026-09-12. Supersedes any earlier bidirectional-cable description.

---

## 0. Quick reference — one line per physical wire

Direction is always "signal source -> signal sink". `DVI pin` is the pin of the 24-pin digital
field of a DVI-D dual-link receptacle (pin 8 and the C1..C5 analog pins are not used).

### 0.1 Cable 1 "FWD" — HL2 to Gowin (board A drives, board B receives)

| Lane | HL2 FPGA pin | HL2 hdr pin | Board A net | Level at HL2 | DVI-1 pair / pin | Board B net | J14 pin | Gowin ball | Gowin IO name | Rate |
|---|---|---|---|---|---|---|---|---|---|---|
| CLK    | PIN_98  | DB1-9  | `HL2_CLK`  | 3.3 V LVCMOS (bank 6) | TMDS **clock** 23(+)/24(-) | `LINK_CLK`  | **20** | **U20** | IOB120A / SGCLKT_5 / BPLL2_T_IN0 / BPLL3_T_IN0 | 76.8 MHz |
| DATA0  | PIN_72  | DB1-1  | `HL2_D0`   | 2.5 V LVCMOS (bank 4) | TMDS data0 18(+)/17(-)     | `LINK_D0`   | **10** | **V17** | IOB106A | 153.6 Mbit/s (DDR @76.8) |
| DATA1  | PIN_76  | DB1-2  | `HL2_D1`   | 2.5 V LVCMOS (bank 5) | TMDS data1 10(+)/9(-)      | `LINK_D1`   | **14** | **W21** | IOB124A | 153.6 Mbit/s |
| DATA2  | PIN_77  | DB1-3  | `HL2_D2`   | 2.5 V LVCMOS (bank 5) | TMDS data2 2(+)/1(-)       | `LINK_D2`   | **16** | **N17** | IOB135A | 153.6 Mbit/s |
| DATA3  | PIN_80  | DB1-4  | `HL2_D3`   | 2.5 V LVCMOS (bank 5) | TMDS data3 13(+)/12(-)     | `LINK_D3`   | **18** | **N13** | IOB142A | 153.6 Mbit/s |
| DATA4  | PIN_83  | DB1-5  | `HL2_D4`   | 2.5 V LVCMOS (bank 5) | TMDS data4 5(+)/4(-)       | `LINK_D4`   | **32** | **Y18** | IOB116A / MGCLKT_4 / BPLL2_T_FB0 | 153.6 Mbit/s |
| DATA5  | PIN_85  | DB1-6  | `HL2_D5`   | 2.5 V LVCMOS (bank 5) | TMDS data5 21(+)/20(-)     | `LINK_D5`   | **36** | **U17** | IOB112A | 153.6 Mbit/s |
| STAT   | PIN_86  | DB12-1 | `HL2_STAT` | 2.5 V LVCMOS out (bank 5) | **DDC SCL, pin 6** single-ended | `LINK_STAT_IN` | **19** | **V20** | IOB120B / SGCLKC_5 / BPLL2_C_IN0 | status UART, <= 3 Mbaud |
| AUX    | PIN_87  | DB12-2 | `HL2_AUX`  | 2.5 V LVCMOS out (bank 5) | **DDC SDA, pin 7** single-ended | `LINK_AUX_IN`  | **34** | **N15** | IOB146A | aux slow line, <= 3 Mbaud |
| PRESENT| -       | -      | `C1_HPD` (1 k to GND on board A) | - | **HPD, pin 16** single-ended | `LINK_PRESENT` | **33** | **T20** | IOB102B | DC level |
| +5 V   | -       | -      | `P5V_DVI1` (optional supply in) | 5 V | **pin 14** | `P5V_DVI1` (from J14-11) | (J14-11) | - | 5V_Peripheral | DC |
| GND    | -       | DB1-13/14, DB12-3/4 | `GND` | - | pins **15**, shields **3, 11, 19, 22**, shell | `GND` | J14-12 | - | - | - |

### 0.2 Cable 2 "REV" — Gowin to HL2 (board B drives, board A receives)

| Lane | J14 pin | Gowin ball | Gowin IO name | Board B net | DVI-2 pair / pin | Board A net | HL2 hdr pin | HL2 FPGA pin | Level at HL2 | Rate |
|---|---|---|---|---|---|---|---|---|---|---|
| REVCLK | **35** | **U18** | IOB112B | `LINK_REVCLK` | TMDS **clock** 23(+)/24(-) | `HL2_REVCLK` | **DB12-5** | **PIN_88** | **2.5 V, input only** (CLK7 / DIFFCLK_3n) | 153.6 MHz |
| REV0   | **9**  | **W17** | IOB106B | `LINK_R0` | TMDS data0 18(+)/17(-) | `HL2_REV0` | **DB1-11** | **PIN_99**  | 3.3 V (bank 6, LED D3 + 1 k) | 307.2 Mbit/s |
| REV1   | **13** | **W22** | IOB124B | `LINK_R1` | TMDS data1 10(+)/9(-)  | `HL2_REV1` | **DB1-15** | **PIN_100** | 3.3 V (bank 6, LED D4 + 1 k) | 307.2 Mbit/s |
| REV2   | **15** | **P17** | IOB135B | `LINK_R2` | TMDS data2 2(+)/1(-)   | `HL2_REV2` | **DB1-17** | **PIN_101** | 3.3 V (bank 6, LED D5 + 1 k) | 307.2 Mbit/s |
| FSER   | **31** | **Y19** | IOB116B / MGCLKC_4 / BPLL2_C_FB0 | `LINK_FSER` | TMDS data3 13(+)/12(-) | `HL2_FSER` | **DB12-6** | **PIN_89** | **2.5 V, input only** (CLK6 / DIFFCLK_3p) | 307.2 Mbit/s, framed (carries commands) |
| SPARE0 | (none - board B test pads / J5 hdr; DNP 0R to J14-40 = P14 = IOB133A) | - | - | `SPARE0_IN` | TMDS data4 5(+)/4(-) | `SPARE0_OUT` -> test pad | - | - | - | unused |
| SPARE1 | (none - board B test pads / J5 hdr; DNP 0R to J14-39 = R14 = IOB133B) | - | - | `SPARE1_IN` | TMDS data5 21(+)/20(-) | `SPARE1_OUT` -> test pad | - | - | - | unused |
| CMDU   | **17** | **N14** | IOB142B | `LINK_CMD_OUT` | **DDC SDA, pin 7** single-ended | `C2_SDA` -> 2.5 V translator -> `HL2_FSER` **through solder links** | **DB12-6** | **PIN_89** | 2.5 V, input only | optional slow command UART, <= 1 Mbaud |
| SPARE_SLOW | (none - test pad only on both boards) | - | - | `C2_SCL_TP` | **DDC SCL, pin 6** single-ended | `C2_SCL_TP` -> test pad | - | - | - | unused |
| PRESENT| - | - | - | `C2_HPD` (1 k to GND on board B) | **HPD, pin 16** single-ended | `C2_HPD` (10 k pull-up on board A, gates the cable-2 receivers) | - | - | - | DC level |
| +5 V   | - | - | - | not connected | pin **14** | not connected | - | - | - | - |
| GND    | J14-12 | - | - | `GND` | pins **15**, shields **3, 11, 19, 22**, shell | `GND` | DB1-13/14, DB12-3/4 | - | - | - |

**PIN_89 is shared.** It is driven either by the **fast-serial** receiver output (default: solder
link `SL_FSER` fitted, `SL_CMD` not fitted) **or** by the **slow command UART** from cable-2 DDC SDA
(`SL_CMD` fitted, `SL_FSER` not fitted). Never both. Both paths pass through the same 3.3 V -> 2.5 V
translator on board A.

---

## 3. Complete HL2 header usage (board A)

### DB1 (2x10, `IO20`)

| DB1 pin | FPGA pin | Bank / VCCIO | Board A use | Direction (w.r.t. HL2) |
|---|---|---|---|---|
| 1  | 72  | 4 / Veth 2.5 V   | `HL2_D0` -> LVDS driver. **Cuttable solder link `SL_D0` in series** (pin 1 is also the FPGA PLL clock-output net that reaches uFL pad CL8 through the HL2's normally-closed jumper J25). | out |
| 2  | 76  | 5 / Vlvds 2.5 V  | `HL2_D1` -> LVDS driver | out |
| 3  | 77  | 5 / Vlvds 2.5 V  | `HL2_D2` -> LVDS driver | out |
| 4  | 80  | 5 / Vlvds 2.5 V  | `HL2_D3` -> LVDS driver | out |
| 5  | 83  | 5 / Vlvds 2.5 V  | `HL2_D4` -> LVDS driver | out |
| 6  | 85  | 5 / Vlvds 2.5 V  | `HL2_D5` -> LVDS driver | out |
| 7  | -   | Vlvds 2.5 V rail | breakout pad + test point only. **Not connected to any board-A supply by default.** A DNP 0 R link `SL_VLVDS` can tie it to the board's local 2.5 V rail instead of the on-board LDO. | HL2 output |
| 8  | -   | Vlvds 2.5 V rail | same net as pin 7 | HL2 output |
| 9  | 98  | 6 / 3.3 V        | `HL2_CLK` (76.8 MHz) -> LVDS driver. LED D2 + 1 k is on this pin. | out |
| 10 | 90  | 6 / 3.3 V        | **not connected** (CW/PTT ring, input only, RC filtered) | - |
| 11 | 99  | 6 / 3.3 V        | `HL2_REV0` <- LVDS receiver output (3.3 V). LED D3 + 1 k on this pin. | **in** |
| 12 | 91  | 6 / 3.3 V        | **not connected** (CW/PTT tip, input only, RC filtered) | - |
| 13 | -   | GND              | ground | - |
| 14 | -   | GND              | ground | - |
| 15 | 100 | 6 / 3.3 V        | `HL2_REV1` <- LVDS receiver output (3.3 V). LED D4 + 1 k on this pin. | **in** |
| 16 | 103 | 6 / 3.3 V        | `SCL1` -> breakout header J8 + test point only (no other load) | - |
| 17 | 101 | 6 / 3.3 V        | `HL2_REV2` <- LVDS receiver output (3.3 V). LED D5 + 1 k on this pin. | **in** |
| 18 | 104 | 6 / 3.3 V        | `SDA1` -> breakout header J8 + test point only | - |
| 19 | -   | +3V3 rail        | `DB1_3V3` - primary board-A supply, selected by header J6 | HL2 output |
| 20 | -   | +3V3 rail        | same net as pin 19 | HL2 output |

### DB12 (3x2, `IO6b`)

| DB12 pin | FPGA pin | Board A use | Direction (w.r.t. HL2) |
|---|---|---|---|
| 1 | 86 | `HL2_STAT` -> 100 R series -> DVI-1 pin 6 (DDC SCL). 2.5 V output into a Gowin 3.3 V input. | out |
| 2 | 87 | `HL2_AUX`  -> 100 R series -> DVI-1 pin 7 (DDC SDA). 2.5 V output into a Gowin 3.3 V input. | out |
| 3 | -  | GND | - |
| 4 | -  | GND | - |
| 5 | 88 | `HL2_REVCLK` <- **2.5 V** output of the level translator (reverse clock, 153.6 MHz). Input-only pin. | **in** |
| 6 | 89 | `HL2_FSER` <- **2.5 V** output of the level translator (fast serial, or slow command UART - link selected). Input-only pin. | **in** |

---

## 4. Complete Tang dock J14 usage (board B)

Row convention on J14 (verified from the Sipeed dock schematic): **even pin = silkscreen "P" = Gowin
`A` leg = differential T (True); odd pin = silkscreen "N" = Gowin `B` leg = differential C (Comp)**.
Adjacent odd/even pins of the same column are a true differential pair, except pins 33/34 which are
not a pair.

Only these J14 pins are used, and they are all in **Bank 4 (bottom bank, VCCIO 3.3 V)**:

| J14 pin | Ball | Gowin IO name | Dedicated clock function | Board B net | Direction (w.r.t. Gowin) | Level | Notes |
|---|---|---|---|---|---|---|---|
| **9**  | W17 | IOB106B | - | `LINK_R0` | **out** | LVCMOS33 | 307.2 Mbit/s, partner of pin 10 |
| **10** | V17 | IOB106A | - | `LINK_D0` | **in** | LVCMOS33 (LVDS25 in direct mode) | 153.6 Mbit/s |
| 11 | - | - | - | `5V_Peripheral` | power in | 5 V | feeds board B's 3.3 V LDO |
| 12 | - | - | - | `GND` | - | - | the only ground pin on J14 |
| **13** | W22 | IOB124B | - | `LINK_R1` | **out** | LVCMOS33 | 307.2 Mbit/s |
| **14** | W21 | IOB124A | - | `LINK_D1` | **in** | LVCMOS33 / LVDS25 | 153.6 Mbit/s |
| **15** | P17 | IOB135B | - | `LINK_R2` | **out** | LVCMOS33 | 307.2 Mbit/s |
| **16** | N17 | IOB135A | - | `LINK_D2` | **in** | LVCMOS33 / LVDS25 | 153.6 Mbit/s |
| **17** | N14 | IOB142B | - | `LINK_CMD_OUT` | **out** | LVCMOS33 | slow command UART, cable-2 DDC SDA |
| **18** | N13 | IOB142A | - | `LINK_D3` | **in** | LVCMOS33 / LVDS25 | 153.6 Mbit/s |
| **19** | V20 | IOB120B | SGCLKC_5 / BPLL2_C_IN0 / BPLL3_C_IN0 | `LINK_STAT_IN` | **in** | **LVTTL33** | slow status UART from the HL2; becomes CLK- in direct-LVDS mode |
| **20** | U20 | IOB120A | **SGCLKT_5 / BPLL2_T_IN0 / BPLL3_T_IN0** | `LINK_CLK` | **in** | LVCMOS33 / LVDS25 | **76.8 MHz forwarded ADC clock** |
| **31** | Y19 | IOB116B | MGCLKC_4 / BPLL2_C_FB0 / BPLL3_C_FB0 | `LINK_FSER` | **out** | LVCMOS33 | 307.2 Mbit/s framed fast serial |
| **32** | Y18 | IOB116A | MGCLKT_4 / BPLL2_T_FB0 / BPLL3_T_FB0 | `LINK_D4` | **in** | LVCMOS33 / LVDS25 | 153.6 Mbit/s |
| **33** | T20 | IOB102B | - | `LINK_PRESENT` | **in** | LVCMOS33 | DC cable-1 detect, **low = cable 1 plugged in**. No pair partner on J14, so this pin can never be differential - which is why the DC signal lives here. Shared with `CAM0_D5` on the DVP camera FPC. |
| **34** | N15 | IOB146A | - | `LINK_AUX_IN` | **in** | **LVTTL33** | slow aux line from the HL2. No pair partner on J14. Shared with `CAM0_D4`. |
| **35** | U18 | IOB112B | - | `LINK_REVCLK` | **out** | LVCMOS33 | **153.6 MHz reverse clock**, PLL-derived |
| **36** | U17 | IOB112A | - | `LINK_D5` | **in** | LVCMOS33 / LVDS25 | 153.6 Mbit/s |
| (39) | R14 | IOB133B | - | `SPARE1_IN` | out | LVCMOS33 | **DNP 0 R link only** - not connected by default. Shared with `CAM0_D3`. |
| (40) | P14 | IOB133A | - | `SPARE0_IN` | out | LVCMOS33 | **DNP 0 R link only** - not connected by default. Shared with `CAM0_D0`. |

**Every other J14 pin is left electrically open on board B** (pads present in the socket, no copper
beyond the pad), so PMOD0 (J14 1-8), PMOD1 (J14 21-28), the option-resistor pins (29/30) and the
remaining DVP camera pins (37/38) stay usable.

### 4.1 Why these pins

* Board B must avoid J14 pins **1-8** (shared with PMOD0 socket J9), **21-28** (shared with PMOD1
  socket J8 and the DVP camera), **29/30** (behind unverified 0 R option resistors) and **37-40**
  (DVP camera). That leaves exactly **14 pins forming 7 true differential pairs** -
  (9,10) (13,14) (15,16) (17,18) (19,20) (31,32) (35,36) - plus the two pairless pins **33** and
  **34**. 16 pins for 16 signals: the fit is exact, with nothing spare.
* All seven **cable-1 receive lanes sit on the A (T) legs** of those seven pairs, so a future
  no-receiver-chip variant can take the DVI pairs straight into the bank as `LVDS25` inputs with the
  bank's on-die 100 R (`DIFF_RESISTOR`, available because Bank 4 is a bottom bank). See section 5.
* The forwarded 76.8 MHz clock is on **pin 20 = U20 = SGCLKT_5**, which is both a dedicated global
  clock input and `BPLL2/BPLL3 CLKIN0`. Gowin UG984 5.2 advises the **T** leg for a single-ended
  clock, which is what the receiver drives.
* The **seven cable-2 transmit lanes and the two slow lines occupy the B (C) legs** of the same
  seven pairs plus pins 33/34. The two slowest signals (`LINK_STAT_IN`, `LINK_CMD_OUT`) are placed
  closest to the clock input (pins 19 and 17) and the two fastest outputs
  (`LINK_FSER` on 31, `LINK_REVCLK` on 35) are placed at the far end of the header from pin 20.
* The reverse clock is a plain Bank 4 GPIO (`U18`), driven from a PLL output through `ODDR`/`OSER`
  or directly. It does not need a dedicated clock pin because it is an **output**.

### 4.2 Required Gowin I/O attributes

```
# ---- cable 1, receive (board B receiver outputs, 3.3 V CMOS) ----
IO_LOC  "link_clk"  U20;   IO_PORT "link_clk"  IO_TYPE=LVCMOS33 PULL_MODE=NONE HYSTERESIS=NONE;
IO_LOC  "link_d[0]" V17;   IO_PORT "link_d[0]" IO_TYPE=LVCMOS33 PULL_MODE=NONE HYSTERESIS=NONE;
IO_LOC  "link_d[1]" W21;   IO_PORT "link_d[1]" IO_TYPE=LVCMOS33 PULL_MODE=NONE HYSTERESIS=NONE;
IO_LOC  "link_d[2]" N17;   IO_PORT "link_d[2]" IO_TYPE=LVCMOS33 PULL_MODE=NONE HYSTERESIS=NONE;
IO_LOC  "link_d[3]" N13;   IO_PORT "link_d[3]" IO_TYPE=LVCMOS33 PULL_MODE=NONE HYSTERESIS=NONE;
IO_LOC  "link_d[4]" Y18;   IO_PORT "link_d[4]" IO_TYPE=LVCMOS33 PULL_MODE=NONE HYSTERESIS=NONE;
IO_LOC  "link_d[5]" U17;   IO_PORT "link_d[5]" IO_TYPE=LVCMOS33 PULL_MODE=NONE HYSTERESIS=NONE;

# ---- cable 1, slow single-ended lines: driven by a 2.5 V HL2 output ----
# LVTTL33 (VIH min 1.7 V) is MANDATORY here. LVCMOS33 (VIH min 2.0 V) leaves 0 mV of
# guaranteed margin against the Cyclone IV 2.5 V output spec (VOH min 2.0 V).
IO_LOC  "link_stat" V20;   IO_PORT "link_stat" IO_TYPE=LVTTL33 PULL_MODE=NONE HYSTERESIS=NONE;
IO_LOC  "link_aux"  N15;   IO_PORT "link_aux"  IO_TYPE=LVTTL33 PULL_MODE=NONE HYSTERESIS=NONE;

# ---- cable detect: low = cable 1 present ----
IO_LOC  "link_present" T20; IO_PORT "link_present" IO_TYPE=LVCMOS33 PULL_MODE=UP;

# ---- cable 2, transmit (into board B LVDS drivers) ----
IO_LOC  "link_revclk" U18; IO_PORT "link_revclk" IO_TYPE=LVCMOS33 DRIVE=8 PULL_MODE=NONE;
IO_LOC  "link_r[0]"   W17; IO_PORT "link_r[0]"   IO_TYPE=LVCMOS33 DRIVE=8 PULL_MODE=NONE;
IO_LOC  "link_r[1]"   W22; IO_PORT "link_r[1]"   IO_TYPE=LVCMOS33 DRIVE=8 PULL_MODE=NONE;
IO_LOC  "link_r[2]"   P17; IO_PORT "link_r[2]"   IO_TYPE=LVCMOS33 DRIVE=8 PULL_MODE=NONE;
IO_LOC  "link_fser"   Y19; IO_PORT "link_fser"   IO_TYPE=LVCMOS33 DRIVE=8 PULL_MODE=NONE;
IO_LOC  "link_cmd"    N14; IO_PORT "link_cmd"    IO_TYPE=LVCMOS33 DRIVE=8 PULL_MODE=NONE;
```

`DRIVE=8` is a starting point: board B puts a 10 k pull-down and a short (< 25 mm) trace on each
driver input, so the load is the driver's 5 pF input. Do not use `DRIVE=24` - it only adds
crosstalk into the adjacent A-leg receive pins.

### 4.3 The direct-LVDS ("no receiver chip") future variant

Board B carries **14 DNP 0 R links** that connect each cable-1 DVI pair straight to a J14
differential pair, bypassing the receivers:

| DVI-1 pair | + leg -> J14 pin (A/T leg) | - leg -> J14 pin (B/C leg) | Gowin pair |
|---|---|---|---|
| clock 23/24 | 20 (U20) | 19 (V20) | IOB120 |
| data0 18/17 | 10 (V17) | 9  (W17) | IOB106 |
| data1 10/9  | 14 (W21) | 13 (W22) | IOB124 |
| data2 2/1   | 16 (N17) | 15 (P17) | IOB135 |
| data3 13/12 | 18 (N13) | 17 (N14) | IOB142 |
| data4 5/4   | 32 (Y18) | 31 (Y19) | IOB116 |
| data5 21/20 | 36 (U17) | 35 (U18) | IOB112 |

To run in that mode: pull the jumper on board B's `RX MODE` header J4 (which tri-states the
cable-1 receiver outputs), fit the 14 links, keep the board's external 100 R terminations and set
`DIFF_RESISTOR=OFF`, and constrain the seven pairs as e.g.

```
IO_LOC  "link_clk" U20,V20;   IO_PORT "link_clk" IO_TYPE=LVDS25;
IO_LOC  "link_d[0]" V17,W17;  IO_PORT "link_d[0]" IO_TYPE=LVDS25;
...
```

**In this mode the seven B-leg signals are lost**: `LINK_REVCLK`, `LINK_R0..2`, `LINK_FSER`,
`LINK_CMD_OUT` and `LINK_STAT_IN` all sit on B legs. Cable 2 therefore cannot be used at the same
time as direct-LVDS mode. `LINK_PRESENT` (pin 33) and `LINK_AUX_IN` (pin 34) survive, because they
are on the two pairless pins.

---

## 5. DVI-D dual-link connector pin usage (both cables)

24-pin digital field. **Pin 8 (analog VSync) and the C1..C5 analog contacts are not connected on
either board** - many DVI-D cables do not wire pin 8.

| DVI pin | Standard function | Cable 1 "FWD" | Cable 2 "REV" |
|---|---|---|---|
| 1  | TMDS data2- | `TX_D2_N` | `RX_D2_N` (REV2) |
| 2  | TMDS data2+ | `TX_D2_P` | `RX_D2_P` (REV2) |
| 3  | data2/4 shield | GND | GND |
| 4  | TMDS data4- | `TX_D4_N` | `RX_D4_N` (SPARE0) |
| 5  | TMDS data4+ | `TX_D4_P` | `RX_D4_P` (SPARE0) |
| 6  | DDC clock | **STAT** (HL2 PIN_86 -> Gowin V20) | **SPARE_SLOW** (test pad only) |
| 7  | DDC data | **AUX** (HL2 PIN_87 -> Gowin N15) | **CMDU** (Gowin N14 -> HL2 PIN_89 via links) |
| 8  | analog VSync | not connected | not connected |
| 9  | TMDS data1- | `TX_D1_N` | `RX_D1_N` (REV1) |
| 10 | TMDS data1+ | `TX_D1_P` | `RX_D1_P` (REV1) |
| 11 | data1/3 shield | GND | GND |
| 12 | TMDS data3- | `TX_D3_N` | `RX_D3_N` (FSER) |
| 13 | TMDS data3+ | `TX_D3_P` | `RX_D3_P` (FSER) |
| 14 | +5 V | **5 V from board B to board A** (optional, jumper-selected) | not connected |
| 15 | GND (5 V return) | GND | GND |
| 16 | Hot Plug Detect | **cable-1 detect**: 10 k pull-up on board B, 1 k to GND on board A | **cable-2 detect**: 10 k pull-up on board A, 1 k to GND on board B |
| 17 | TMDS data0- | `TX_D0_N` | `RX_D0_N` (REV0) |
| 18 | TMDS data0+ | `TX_D0_P` | `RX_D0_P` (REV0) |
| 19 | data0/5 shield | GND | GND |
| 20 | TMDS data5- | `TX_D5_N` | `RX_D5_N` (SPARE1) |
| 21 | TMDS data5+ | `TX_D5_P` | `RX_D5_P` (SPARE1) |
| 22 | TMDS clock shield | GND | GND |
| 23 | TMDS clock+ | `TX_CLK_P` | `RX_CLK_P` (REVCLK) |
| 24 | TMDS clock- | `TX_CLK_N` | `RX_CLK_N` (REVCLK) |
| shell | - | GND through a fitted 0 R link | GND through a fitted 0 R link |

---

## 6. Level-shift summary (what has to be true at each end)

| Path | Source | Sink | How it is handled |
|---|---|---|---|
| HL2 2.5 V out -> LVDS driver in (DATA0..5) | Cyclone IV 2.5 V LVCMOS, VOH min 2.0 V at 1 mA | DS90LV047A, VIH min 2.0 V, IIN +/-10 uA | **Direct**, 22 R series. Guaranteed margin 0 mV at the datasheet's 1 mA test current; real margin >= 375 mV because the driver input draws 10 uA so the line settles at VCCIO5 (2.375 V min). See DESIGN_NOTES.md 3.2. |
| HL2 3.3 V out -> LVDS driver in (CLK) | Cyclone IV 3.3 V LVCMOS | DS90LV047A | Direct, 22 R series. |
| LVDS receiver out -> HL2 3.3 V bank-6 input (REV0..2) | DS90LV048A LVCMOS 3.3 V | Cyclone IV bank 6 at 3.3 V | **Direct**, 0 R link in series (22 R pads as an alternative). |
| LVDS receiver out -> HL2 **2.5 V input-only** pins (PIN_88, PIN_89) | DS90LV048A LVCMOS 3.3 V | Cyclone IV bank 5 at 2.5 V, PCI clamp on by default | **SN74AVC4T245 translator**, VCCA = 3.3 V, VCCB = 2.5 V. Not a resistor divider: the receiver's LVCMOS output is only specified to -0.4 mA / +2 mA, and a divider light enough for it would have an RC that eats half of the 3.26 ns unit interval of the 307.2 Mbit/s fast-serial lane. See DESIGN_NOTES.md 3.3. |
| HL2 2.5 V out -> Gowin 3.3 V input (STAT, AUX) | Cyclone IV 2.5 V LVCMOS | GW5AST Bank 4 at 3.3 V | Direct, 100 R series on board A. **Gowin side must be `IO_TYPE=LVTTL33` (VIH 1.7 V) with `HYSTERESIS=NONE`.** |
| Gowin 3.3 V out -> LVDS driver in | GW5AST LVCMOS33 | DS90LV047A | Direct, 22 R series, 10 k pull-down. |
| Gowin 3.3 V out -> HL2 2.5 V input-only pin (CMDU) | GW5AST LVCMOS33 | Cyclone IV bank 5 | Same SN74AVC4T245 on board A (channel 3), link-selected onto PIN_89. |

---

## 7. Things this pin map deliberately does **not** use

* **DB1 pins 10 and 12** (FPGA 90/91, CW key inputs with 100 R + 2.2 k + 1 uF filters) - left
  completely unconnected on board A.
* **DB1 pins 7/8** (the HL2's own 2.5 V `Vlvds` rail) - brought to a breakout pad and a test point
  only. Board A generates its own 2.5 V; the DNP link `SL_VLVDS` exists if you would rather
  reference the translator to the FPGA's actual bank supply.
* **DB1 pins 16/18** (`SCL1`/`SDA1`) - breakout header and test points only, no load.
* **J14 pins 1-8, 21-30, 37, 38** on the Tang dock - electrically open on board B.
* **DVI pin 8** on both cables.

## 8. Known conflicts

* Board A occupies **both** DB1 and DB12, so it is mutually exclusive with the AK4951 / "HL2+"
  audio companion board and with the two-HL2 coherent link (which uses DB12 1/2 and 5/6).
* Board A drives DB1 pins 11, 15 and 17, which are LED outputs in the stock `hl2b5up_main`
  gateware. **Load the gowin-link HL2 gateware before plugging cable 2 in**, or leave board A's
  `RX MODE` jumper off. Status LEDs D3, D4 and D5 will flicker with reverse-link data.
* Board A is compatible with the N2ADR filter board (DB7) and with the N2ADR/Pico HL2 IO Board -
  no electrical overlap. See DESIGN_NOTES.md 6 for the mechanical clearances.
