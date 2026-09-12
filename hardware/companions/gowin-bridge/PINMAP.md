# gowin-bridge pin map (authoritative)

Two adapter PCBs ("bridge boards") carry a 12-bit / 76.8 MSPS ADC stream from a Hermes Lite 2
(Cyclone IV EP4CE22E22C8, E144) to a Sipeed Tang Mega 138K dock (GW5AST-138, PG484) over
**three HDMI cables**, and carry a reverse stream back.

* **Board A = `hl2-bridge`** plugs onto the HL2 headers **DB1** (2x10) and **DB12** (3x2).
  It carries **three mini HDMI (Type C) sockets: `OUT 1`, `OUT 2`, `IN`.**
* **Board B = `tang-bridge`** plugs onto the Tang dock header **J14** (2x40 holes, Bank 4; the
  user solders a 2x20 male pin header into the bare plated holes).
  It carries **three full-size HDMI (Type A) sockets: `IN 1`, `IN 2`, `OUT`.**

Revision: **rev B**, 2026-09-12. Supersedes rev A (two dual-link DVI-D sockets per board).
This file is the single source of truth. The gateware constraints
(`gateware/variants/hl2b5up_gowinlink/gowinlink_pins.tcl` on the HL2 side, `gowin/proj/*.cst` on
the Gowin side) must match it exactly. If anything here disagrees with a brief, this file wins.

---

## 0. What changed from rev A, and one correction

| rev A | rev B |
|---|---|
| 2 x dual-link DVI-D per board, one cable each direction | 3 x HDMI per board, three cables |
| 7 pairs per cable | 4 pairs per cable (1 clock + 3 data) + 1 single-ended slow wire |
| one forward clock (PIN_98) | **two** forward clocks: PIN_98 in `OUT 1`, **PIN_87 in `OUT 2`** (a second copy of the same 76.8 MHz), so each forward cable is self-timed and the two cables' unequal delay stops mattering |
| PIN_87 = "aux out", spare | PIN_87 = forward clock B. **The aux output is gone.** |
| reverse fast serial on a differential pair, 307.2 Mbit/s | **slow in on a single-ended unshielded wire (SCL), ~10-25 Mbit/s** (section 3.3) |
| role assigned per pin inside a connector | **role assigned per socket**, so board A works at both ends of a mini-to-mini cable (section 1) |
| board A 80 x 66 mm, L-shaped, overhung the N2ADR filter board | board A a plain rectangle inside the filter-board corridor (`DESIGN_NOTES.md` 6) |

### 0.1 Correction to rev A - DB12 pins 5 and 6 were swapped

**rev A (and the rev B brief) said PIN_88 is DB12 pin 5 and PIN_89 is DB12 pin 6. That is
wrong, and rev A's KiCad files were wired wrong with it.** Read straight out of
`hardware/hl/hermeslite.net`:

```
(net (code 198) (name "Net-(DB12-Pad6)")  (node (ref U2) (pin 88)) (node (ref R17) (pin 1)) (node (ref DB12) (pin 6)))
(net (code 215) (name "Net-(DB12-Pad5)")  (node (ref DB12) (pin 5)) (node (ref U2) (pin 89)) (node (ref R17) (pin 2)))
```

So, definitively:

* **DB12 pin 5 = FPGA PIN_89** = the slow serial input (command channel).
* **DB12 pin 6 = FPGA PIN_88** = the reverse clock input.

The FPGA pins and their functions are exactly as briefed; only the header holes swap.
`franz-claude-analysis/HL2_EXPANSION_HW_FACTS.md` and the comment block in
`gateware/variants/hl2b5up_gowinlink/gowinlink_pins.tcl` both already had it this way; rev A of
this file did not.

---

## 1. The two socket types (this is the whole symmetry mechanism)

Exactly **two** socket definitions exist, and both boards use only these two. A socket's role
belongs to the socket, never to pins inside it, so **a straight pin-1-to-pin-1 mini-to-mini
cable joins any OUT socket to any IN socket** and every signal lands on its counterpart.

| Role in the socket | OUT socket | IN socket |
|---|---|---|
| TMDS **clock** pair | board **drives** it (LVDS driver) | board **receives** it (LVDS receiver) |
| TMDS **data 0** pair | driven | received |
| TMDS **data 1** pair | driven | received |
| TMDS **data 2** pair | driven | received |
| **SCL** (single-ended) | "slow out" - board drives | "slow in" - board receives |
| **HPD** | **1 k to GND** so the far end detects the cable | **10 k pull-up to +3V3**; reads **low** when a cable is plugged in |
| **+5 V** | not connected on board A; DNP link to the 5 V rail on board B | DNP link to an on-board LDO on board A; not connected on board B |
| CEC, Reserved/Utility, SDA | test pad only | test pad only |
| all 4 pair shields, DDC/CEC ground, shell | GND | GND |

The pair ordering and the slow-wire pin are **identical** on OUT and IN. That is what makes
OUT-to-IN work in every combination.

**Board A: 2 OUT + 1 IN. Board B: 2 IN + 1 OUT.** Always connect **OUT to IN**. Never OUT to
OUT (two drivers into each other) and never IN to IN (no driver at all).

### 1.1 HDMI connector pin numbers for each role

Type A (full size, board B) and Type C (mini, board A) carry the same 19 signals in a
**different pin order**. Both tables below are the standard HDMI receptacle pinouts.
Conveniently **SCL is pin 15, SDA pin 16, +5 V pin 18 and HPD pin 19 in both types**, so only
the four pairs and the two ground/utility pins move.

| Signal / role | **Type A pin** (board B) | **Type C pin** (board A) |
|---|---|---|
| TMDS data 2 + = **lane 2 +** | 1 | 2 |
| TMDS data 2 shield = GND | 2 | 1 |
| TMDS data 2 - = **lane 2 -** | 3 | 3 |
| TMDS data 1 + = **lane 1 +** | 4 | 5 |
| TMDS data 1 shield = GND | 5 | 4 |
| TMDS data 1 - = **lane 1 -** | 6 | 6 |
| TMDS data 0 + = **lane 0 +** | 7 | 8 |
| TMDS data 0 shield = GND | 8 | 7 |
| TMDS data 0 - = **lane 0 -** | 9 | 9 |
| TMDS clock + = **link clock +** | 10 | 11 |
| TMDS clock shield = GND | 11 | 10 |
| TMDS clock - = **link clock -** | 12 | 12 |
| CEC - test pad only | 13 | 13 |
| Reserved / Utility - test pad only | 14 | **17** |
| **SCL = the slow wire** | **15** | **15** |
| SDA - test pad only | 16 | 16 |
| DDC/CEC ground = GND | **17** | **14** |
| **+5 V** | **18** | **18** |
| **HPD = cable detect** | **19** | **19** |
| shell | shell | shell |

A commercial **mini-to-full-size HDMI cable wires signal to signal, not pin number to pin
number** (Type C pin 2 to Type A pin 1, and so on), which is why board A can use Type C and
board B Type A with no crossover anywhere in either board.

---

## 2. The cable configurations

### 2a. HL2 to Gowin - three cables (mini-to-full-size)

```
radio  OUT 1  ==>  IN 1   board B
radio  OUT 2  ==>  IN 2   board B
radio  IN     <==  OUT    board B
```

Forward payload: 2 cables x 3 lanes x 153.6 Mbit/s = **921.6 Mbit/s** = 12 bits x 76.8 MSPS,
the whole ADC stream with no framing overhead. Reverse payload: 3 lanes x 307.2 Mbit/s =
921.6 Mbit/s.

### 2b. Two HL2 radios back to back - two cables (mini-to-mini), no Gowin

```
radio 1  OUT 1  ==>  IN  radio 2
radio 2  OUT 1  ==>  IN  radio 1
```

Each radio's **`OUT 2` is unused**. Each direction carries 1 clock + 3 data lanes at
153.6 Mbit/s = **460.8 Mbit/s**, three times the 153.6 Mbit/s of the HL2's existing one-pair
DB12 two-radio link.

---

## 3. Board A - HL2 side, socket by socket

Lane numbering: **forward lanes 0..5** are the six data lanes of the forward link; `OUT 1`
carries 0,1,2 and `OUT 2` carries 3,4,5. **Reverse lanes 0..2** come back in `IN`.

### 3.1 `OUT 1` socket (J3) - board A drives everything

| Role | Board A net | HL2 FPGA pin | HL2 header pin | Bank / VCCIO | Rate | Notes |
|---|---|---|---|---|---|---|
| link clock | `O1_CLK_P/N` | **PIN_98** | **DB1-9** | 6 / 3.3 V | 76.8 MHz | forward clock A. LED **D2** cathode + 1 k to **+3V3** sits on this pin (section 7.1). |
| lane 0 | `O1_D0_P/N` | **PIN_72** | **DB1-1** | 4 / Veth 2.5 V | 153.6 Mbit/s DDR | reaches PIN_72 only through the HL2's own jumper **J25**, and shares that net with uFL pad **CL8** (section 7.2). Cuttable link `SL_D0` on board A. |
| lane 1 | `O1_D1_P/N` | **PIN_76** | **DB1-2** | 5 / Vlvds 2.5 V | 153.6 Mbit/s | |
| lane 2 | `O1_D2_P/N` | **PIN_77** | **DB1-3** | 5 / Vlvds 2.5 V | 153.6 Mbit/s | |
| slow out (SCL) | `O1_SLOW` | **PIN_86** | **DB12-1** | 5 / Vlvds 2.5 V | status UART, 115200 8N1, up to ~3 Mbaud | single-ended straight onto the cable through 100 R; no driver chip. |
| HPD | `O1_HPD` | - | - | - | DC | 1 k to GND. |
| +5 V | - | - | - | - | - | **not connected.** |

### 3.2 `OUT 2` socket (J4) - board A drives everything

| Role | Board A net | HL2 FPGA pin | HL2 header pin | Bank / VCCIO | Rate | Notes |
|---|---|---|---|---|---|---|
| link clock | `O2_CLK_P/N` | **PIN_87** | **DB12-2** | 5 / Vlvds 2.5 V | 76.8 MHz | **forward clock B**: a second copy of the same clock, so `OUT 2` is self-timed and cable-length mismatch between the two forward cables does not matter. Replaces rev A's aux output. |
| lane 3 | `O2_D0_P/N` | **PIN_80** | **DB1-4** | 5 / Vlvds 2.5 V | 153.6 Mbit/s | **VREFB5N0 pin, ~21 pF of pin capacitance.** Keep its trace to the level translator as short as physically possible (`DESIGN_NOTES.md` 2.2). |
| lane 4 | `O2_D1_P/N` | **PIN_83** | **DB1-5** | 5 / Vlvds 2.5 V | 153.6 Mbit/s | |
| lane 5 | `O2_D2_P/N` | **PIN_85** | **DB1-6** | 5 / Vlvds 2.5 V | 153.6 Mbit/s | |
| slow out (SCL) | `O2_SLOW` | - | - | - | - | **not connected - test pad only.** The HL2 has no further output pin. |
| HPD | `O2_HPD` | - | - | - | DC | 1 k to GND. |
| +5 V | - | - | - | - | - | not connected. |

### 3.3 `IN` socket (J5) - board A receives everything

| Role | Board A net | HL2 FPGA pin | HL2 header pin | Bank / VCCIO | Rate | Notes |
|---|---|---|---|---|---|---|
| link clock | `I_CLK_P/N` | **PIN_88** | **DB12-6** | 5 / 2.5 V, **input only** | 153.6 MHz | `CLK7` / `DIFFCLK_3n`, a dedicated clock input. Fed at 2.5 V through the level translator. |
| reverse lane 0 | `I_D0_P/N` | **PIN_99** | **DB1-11** | 6 / 3.3 V | 307.2 Mbit/s | LED **D3** + 1 k to **+3V3**; the receiver output must sink ~1.4 mA when low (section 7.1). |
| reverse lane 1 | `I_D1_P/N` | **PIN_100** | **DB1-15** | 6 / 3.3 V | 307.2 Mbit/s | LED **D4** + 1 k to +3V3. |
| reverse lane 2 | `I_D2_P/N` | **PIN_101** | **DB1-17** | 6 / 3.3 V | 307.2 Mbit/s | LED **D5** + 1 k to +3V3. |
| slow in (SCL) | `I_SLOW` | **PIN_89** | **DB12-5** | 5 / 2.5 V, **input only** | **~10-25 Mbit/s, see below** | `CLK6` / `DIFFCLK_3p`. Carries the command channel. Fed at 2.5 V through the level translator. |
| HPD | `I_HPD` | - | - | - | DC | 10 k pull-up to +3V3; **low = cable plugged in**; gates the receiver's enable. |
| +5 V | `I_5V` | - | - | - | - | DNP 0 R link `SL_5V` to an on-board AMS1117 (`DESIGN_NOTES.md` 5). |

**The command channel is much slower than in rev A.** rev A gave it a shielded 100 R
differential pair at 307.2 Mbit/s. In rev B it is a **single-ended, unterminated, unshielded
conductor inside the HDMI cable** (the SCL wire), driven 3.3 V CMOS at one end into a level
translator at the other. Realistic ceiling **10 to 25 Mbit/s**, and that is reasoning, not a
measurement: the wire is roughly 100 R and unterminated at both ends, so each edge rings for
several round trips (about 5 ns per metre each way), which puts a floor of roughly 40 ns per
bit before the eye closes on a 2 m cable. **Bench-measure it before any gateware relies on a
number.** The gateware's fast-serial command framing still works, just at a lower baud; the
`CMD_UART = 1` bring-up option (115200 8N1) is unaffected.

---

## 4. Complete HL2 header usage (board A)

### 4.1 DB1 (2x10, footprint `HERMESLITE:10x2`)

| DB1 pin | FPGA pin | Bank / VCCIO | Board A use | Dir w.r.t. HL2 |
|---|---|---|---|---|
| 1  | 72 (via J25) | 4 / Veth 2.5 V | forward lane 0 -> translator -> driver. **Cuttable link `SL_D0` (R1) in series.** | out |
| 2  | 76 | 5 / Vlvds 2.5 V | forward lane 1 -> translator -> driver | out |
| 3  | 77 | 5 / Vlvds 2.5 V | forward lane 2 -> translator -> driver | out |
| 4  | 80 | 5 / Vlvds 2.5 V | forward lane 3 -> translator -> driver. **21 pF VREF pin.** | out |
| 5  | 83 | 5 / Vlvds 2.5 V | forward lane 4 -> translator -> driver | out |
| 6  | 85 | 5 / Vlvds 2.5 V | forward lane 5 -> translator -> driver | out |
| 7  | -  | Vlvds 2.5 V rail | stack-through + test point. DNP 0 R link `SL_VLVDS` can reference the translators' 2.5 V side to this rail instead of the on-board LDO. | HL2 output |
| 8  | -  | Vlvds 2.5 V rail | same net as pin 7 | HL2 output |
| 9  | 98 | 6 / 3.3 V | **forward clock A** -> 68 R / 220 R divider -> translator -> driver. LED D2 + 1 k to +3V3 on this pin. | out |
| 10 | 90 | 6 / 3.3 V | **not connected** (CW/PTT ring, input only, RC filtered). Stack-through tail only. | - |
| 11 | 99 | 6 / 3.3 V | reverse lane 0 <- receiver output (3.3 V) through a 0 R link | **in** |
| 12 | 91 | 6 / 3.3 V | **not connected** (CW/PTT tip). Stack-through tail only. | - |
| 13 | -  | GND | ground | - |
| 14 | -  | GND | ground | - |
| 15 | 100 | 6 / 3.3 V | reverse lane 1 <- receiver output through a 0 R link | **in** |
| 16 | 103 | 6 / 3.3 V | `SCL1` -> stack-through + test point only, no load | - |
| 17 | 101 | 6 / 3.3 V | reverse lane 2 <- receiver output through a 0 R link | **in** |
| 18 | 104 | 6 / 3.3 V | `SDA1` -> stack-through + test point only | - |
| 19 | -  | +3V3 rail | `DB1_3V3` - the board's supply | HL2 output |
| 20 | -  | +3V3 rail | same net as pin 19 | HL2 output |

**Stack-through header J1.** One 2.54 mm long-tail (stack-through) 2x10 female header. Only
positions **7, 8, 10, 12, 13, 14, 16, 18, 19, 20** are meant to pass a tail up to a stacked
companion board. Positions **1-6, 9, 11, 15, 17** carry link signals; the silkscreen beside
them reads `TAILS 1-6 9 11 15 17 = USED BY LINK - CLIP`, and clipping them with side cutters is
the only way to keep a stacked companion off those nets.

### 4.2 DB12 (3x2, footprint `HERMESLITE:3x2`) - **note the corrected pin 5 / pin 6**

| DB12 pin | FPGA pin | Board A use | Dir w.r.t. HL2 |
|---|---|---|---|
| 1 | 86 | `OUT 1` slow out -> 100 R -> Type C pin 15 (SCL). A 2.5 V output feeding the Gowin's LVTTL33 input. | out |
| 2 | 87 | **forward clock B** -> translator -> driver -> `OUT 2` clock pair | out |
| 3 | -  | GND | - |
| 4 | -  | GND | - |
| 5 | **89** | **slow in** <- 2.5 V output of the level translator (command channel from `IN` SCL). Input only. | **in** |
| 6 | **88** | **reverse clock** <- 2.5 V output of the level translator, 153.6 MHz. Input only. | **in** |

### 4.3 HL2 pin budget - nothing spare

**9 outputs:** PIN_72, 76, 77, 80, 83, 85, 86, 87, 98.
**5 inputs:** PIN_88, 89, 99, 100, 101.
**14 total = every usable pin on DB1 and DB12.** There is no spare HL2 pin left for anything.

---

## 5. Complete Tang dock J14 usage (board B)

Row convention on J14, from the Sipeed dock schematic: **even pin = silkscreen "P" = Gowin `A`
leg = differential T (True); odd pin = silkscreen "N" = Gowin `B` leg = differential C (Comp)**.
Adjacent odd/even pins of a column form a true differential pair, **except pins 33 and 34,
which are not a pair**. Every pin used is in **Bank 4** (a bottom bank, VCCIO 3.3 V, so the
on-die 100 R `DIFF_RESISTOR` is available).

| J14 pin | Ball | Gowin IO name | Dedicated clock function | Board B net | Socket / role | Dir w.r.t. Gowin | IO type | Rate |
|---|---|---|---|---|---|---|---|---|
| **9**  | W17 | IOB106B | - | `LINK_R0` | `OUT` reverse lane 0 | **out** | LVCMOS33 | 307.2 Mbit/s |
| **10** | V17 | IOB106A | - | `LINK_D0` | `IN 1` lane 0 | **in** | LVCMOS33 (LVDS25 direct) | 153.6 Mbit/s |
| 11 | - | - | - | `P5V_J14` | `5V_Peripheral` | power in | 5 V | - |
| 12 | - | - | - | `GND` | **the only ground pin on J14** | - | - | - |
| **13** | W22 | IOB124B | - | `LINK_R1` | `OUT` reverse lane 1 | **out** | LVCMOS33 | 307.2 Mbit/s |
| **14** | W21 | IOB124A | - | `LINK_D1` | `IN 1` lane 1 | **in** | LVCMOS33 / LVDS25 | 153.6 Mbit/s |
| **15** | P17 | IOB135B | - | `LINK_R2` | `OUT` reverse lane 2 | **out** | LVCMOS33 | 307.2 Mbit/s |
| **16** | N17 | IOB135A | - | `LINK_D2` | `IN 1` lane 2 | **in** | LVCMOS33 / LVDS25 | 153.6 Mbit/s |
| **17** | N14 | IOB142B | - | `LINK_SLOW_OUT` | `OUT` slow out (SCL) | **out** | LVCMOS33 | ~10-25 Mbit/s |
| **18** | N13 | IOB142A | - | `LINK_D3` | `IN 2` lane 3 | **in** | LVCMOS33 / LVDS25 | 153.6 Mbit/s |
| **19** | V20 | IOB120B | SGCLKC_5 / BPLL2_C_IN0 / BPLL3_C_IN0 | `LINK_SLOW_IN` | `IN 1` slow in (SCL) | **in** | **LVTTL33** | status UART |
| **20** | U20 | IOB120A | **SGCLKT_5 / BPLL2_T_IN0 / BPLL3_T_IN0** | `LINK_CLK_A` | **`IN 1` clock = forward clock A** | **in** | LVCMOS33 / LVDS25 | **76.8 MHz** |
| **31** | Y19 | IOB116B | MGCLKC_4 / BPLL2_C_FB0 / BPLL3_C_FB0 | `LINK_PRESENT2` | `IN 2` cable detect | **in** | LVCMOS33, PULL_MODE=UP | DC |
| **32** | Y18 | IOB116A | **MGCLKT_4 / BPLL2_T_FB0 / BPLL3_T_FB0** | `LINK_CLK_B` | **`IN 2` clock = forward clock B** | **in** | LVCMOS33 / LVDS25 | **76.8 MHz** |
| **33** | T20 | IOB102B | - | `LINK_PRESENT1` | `IN 1` cable detect | **in** | LVCMOS33, PULL_MODE=UP | DC |
| **34** | N15 | IOB146A | - | `LINK_D5` | `IN 2` lane 5 | **in** | LVCMOS33 | 153.6 Mbit/s |
| **35** | U18 | IOB112B | - | `LINK_REVCLK` | `OUT` reverse clock | **out** | LVCMOS33 | 153.6 MHz |
| **36** | U17 | IOB112A | - | `LINK_D4` | `IN 2` lane 4 | **in** | LVCMOS33 / LVDS25 | 153.6 Mbit/s |

**Every other J14 pin is left electrically open on board B** (a socket hole with no copper
beyond the pad), so PMOD0 (J14 1-8), PMOD1 (J14 21-28), the option-resistor pins (29/30) and
the remaining DVP camera pins (37-40) all stay usable.

### 5.1 Why these pins

* The avoid-list is unchanged from rev A: **1-8** are PMOD0 (J9); **21-28** are PMOD1 (J8) and
  the DVP camera; **29/30** sit behind unverified 0 R option resistors; **37-40** are DVP
  camera. What is left is **7 true differential pairs** - (9,10) (13,14) (15,16) (17,18)
  (19,20) (31,32) (35,36) - plus the two pairless pins **33** and **34**: 16 signal pins.
* Board B needs exactly 16 signal pins: **11 in** (2 clocks, 6 data, 1 slow, 2 cable detects)
  and **5 out** (1 clock, 3 data, 1 slow). The fit is exact, nothing spare.
* **Forward clock A is on pin 20 = U20 = SGCLKT_5**, which is also `BPLL2/BPLL3 CLKIN0` - a
  dedicated global clock input *and* a PLL reference input. Required, not a preference: the
  Gowin PLL that generates the reverse transmit clocks takes its reference from here.
* **Forward clock B is on pin 32 = Y18 = MGCLKT_4.** Also a dedicated clock input, on the
  middle global clock network, so it can clock `IN 2`'s three `IDDR`s. It does **not** need to
  be a PLL reference - only clock A drives the PLL. It is a T leg, which is what a single-ended
  clock into a Gowin bank should be (Gowin UG984 section 5.2).
* **Seven of the eight received differential signals sit on the A (T) leg** of a true pair,
  which is what the future no-receiver-chip variant (section 5.3) needs. There are only seven A
  legs and eight received pairs, so **lane 5 goes on pin 34 (N15, IOB146A)** - an A leg, but
  with no pair partner on the header. Lane 5 is therefore the one lane that can never run
  direct-LVDS. It is deliberately the last lane of `IN 2`, so the 3-lane fallback geometry
  (clock A plus lanes 0,1,2, all on `IN 1`, all on true pairs) survives intact in direct mode.
* The fastest outputs (`LINK_REVCLK` on 35, `LINK_R2` on 15) are kept away from pin 20.

### 5.2 Paste-ready Gowin constraints

```
# ==== IN 1 and IN 2: received, 3.3 V CMOS from the LVDS receivers ====
IO_LOC  "link_clk_a" U20;  IO_PORT "link_clk_a" IO_TYPE=LVCMOS33 PULL_MODE=NONE HYSTERESIS=NONE;
IO_LOC  "link_clk_b" Y18;  IO_PORT "link_clk_b" IO_TYPE=LVCMOS33 PULL_MODE=NONE HYSTERESIS=NONE;
IO_LOC  "link_d[0]"  V17;  IO_PORT "link_d[0]"  IO_TYPE=LVCMOS33 PULL_MODE=NONE HYSTERESIS=NONE;
IO_LOC  "link_d[1]"  W21;  IO_PORT "link_d[1]"  IO_TYPE=LVCMOS33 PULL_MODE=NONE HYSTERESIS=NONE;
IO_LOC  "link_d[2]"  N17;  IO_PORT "link_d[2]"  IO_TYPE=LVCMOS33 PULL_MODE=NONE HYSTERESIS=NONE;
IO_LOC  "link_d[3]"  N13;  IO_PORT "link_d[3]"  IO_TYPE=LVCMOS33 PULL_MODE=NONE HYSTERESIS=NONE;
IO_LOC  "link_d[4]"  U17;  IO_PORT "link_d[4]"  IO_TYPE=LVCMOS33 PULL_MODE=NONE HYSTERESIS=NONE;
IO_LOC  "link_d[5]"  N15;  IO_PORT "link_d[5]"  IO_TYPE=LVCMOS33 PULL_MODE=NONE HYSTERESIS=NONE;

# Lanes 0,1,2 are clocked by link_clk_a; lanes 3,4,5 by link_clk_b. Two clock
# domains on the forward side: each cable is self-timed, and the two 6-bit
# halves of a sample are rejoined in the Gowin after per-lane alignment.

# ==== IN 1 slow in: driven by an HL2 2.5 V output straight down the cable ====
# LVTTL33 (VIH min 1.7 V) is MANDATORY. LVCMOS33 (VIH min 2.0 V) leaves 0 mV of
# guaranteed margin against the Cyclone IV 2.5 V output spec (VOH min 2.0 V).
# HYSTERESIS=NONE because the Gowin's 400 mV of hysteresis at VCCIO 3.3 V is
# larger than the whole margin.
IO_LOC  "link_slow_in" V20; IO_PORT "link_slow_in" IO_TYPE=LVTTL33 PULL_MODE=NONE HYSTERESIS=NONE;

# ==== cable detect: LOW = that cable is plugged in ====
IO_LOC  "link_present1" T20; IO_PORT "link_present1" IO_TYPE=LVCMOS33 PULL_MODE=UP;
IO_LOC  "link_present2" Y19; IO_PORT "link_present2" IO_TYPE=LVCMOS33 PULL_MODE=UP;

# ==== OUT: transmitted, into board B's LVDS driver inputs ====
IO_LOC  "link_revclk"   U18; IO_PORT "link_revclk"   IO_TYPE=LVCMOS33 DRIVE=8 PULL_MODE=NONE;
IO_LOC  "link_r[0]"     W17; IO_PORT "link_r[0]"     IO_TYPE=LVCMOS33 DRIVE=8 PULL_MODE=NONE;
IO_LOC  "link_r[1]"     W22; IO_PORT "link_r[1]"     IO_TYPE=LVCMOS33 DRIVE=8 PULL_MODE=NONE;
IO_LOC  "link_r[2]"     P17; IO_PORT "link_r[2]"     IO_TYPE=LVCMOS33 DRIVE=8 PULL_MODE=NONE;
IO_LOC  "link_slow_out" N14; IO_PORT "link_slow_out" IO_TYPE=LVCMOS33 DRIVE=8 PULL_MODE=NONE;
```

`DRIVE=8` is the starting point: board B puts a 22 R series resistor, a 10 k pull-down and a
short (< 25 mm) trace on each driver input, so the load is the driver's ~5 pF input. Do not use
`DRIVE=24`; it only adds crosstalk into the adjacent A-leg receive pins.

### 5.3 The direct-LVDS ("no receiver chip") future variant

Board B carries **14 DNP 0 R links** that connect seven of the eight received pairs straight to
a J14 differential pair, bypassing the receivers:

| Socket / pair | + leg -> J14 pin (A/T leg) | - leg -> J14 pin (B/C leg) | Gowin pair |
|---|---|---|---|
| `IN 1` clock | 20 (U20) | 19 (V20) | IOB120 |
| `IN 1` lane 0 | 10 (V17) | 9 (W17) | IOB106 |
| `IN 1` lane 1 | 14 (W21) | 13 (W22) | IOB124 |
| `IN 1` lane 2 | 16 (N17) | 15 (P17) | IOB135 |
| `IN 2` clock | 32 (Y18) | 31 (Y19) | IOB116 |
| `IN 2` lane 3 | 18 (N13) | 17 (N14) | IOB142 |
| `IN 2` lane 4 | 36 (U17) | 35 (U18) | IOB112 |
| `IN 2` lane 5 | 34 (N15) | **no pair partner exists** | **not possible** |

To run in that mode: move board B's `RX MODE` jumper (J4) to 1-2 so the receiver outputs
tri-state, fit the links for the pairs you want, keep the board's external 100 R terminations
and set `DIFF_RESISTOR=OFF`, then constrain each pair as e.g.

```
IO_LOC "link_clk_a" U20,V20;  IO_PORT "link_clk_a" IO_TYPE=LVDS25;
IO_LOC "link_d[0]"  V17,W17;  IO_PORT "link_d[0]"  IO_TYPE=LVDS25;
```

**What direct-LVDS mode costs:** every B-leg signal is lost - the whole `OUT` socket
(`LINK_REVCLK`, `LINK_R0..2`, `LINK_SLOW_OUT`), plus `LINK_SLOW_IN` (pin 19) and
`LINK_PRESENT2` (pin 31). Lane 5 (pin 34) is lost too, so the 6-lane forward geometry is
unavailable. What survives is **`IN 1` alone as a 3-lane differential forward link with no
reverse path**, plus `LINK_PRESENT1` on pin 33. It is a receive-only experiment, not a usable
configuration of the whole system.

---

## 6. Level shifting - what has to be true at each interface

Full numbers and reasoning in `DESIGN_NOTES.md` section 3. Summary:

| Path | Source | Sink | How it is handled |
|---|---|---|---|
| HL2 2.5 V out -> LVDS driver in (7 signals: lanes 0-5 and clock B) | Cyclone IV 2.5 V LVCMOS, VOH min **2.0 V** at -1 mA | DS90LV047A, VIH min **2.0 V** | **SN74AVC8T245 translator, VCCA = 2.5 V, VCCB = 3.3 V.** VIH = 0.65 x VCCA = **1.63 V**, so **370 mV of guaranteed margin** instead of 0 mV. Eight DNP 0 R bypass links exist if the bench says the translator is unnecessary. |
| HL2 3.3 V out -> the same translator (clock A, PIN_98) | Cyclone IV 3.3 V LVCMOS | SN74AVC8T245 A side, absolute max VCCA + 0.5 V = **3.0 V** | **68 R / 220 R divider** first, so the A-side input sees ~2.3 V. Clock A therefore goes through the *same package* as the data and picks up the *same* propagation delay: the clock-to-data offset stays at the package's channel-to-channel skew instead of a whole translator delay. |
| LVDS receiver out -> HL2 3.3 V bank-6 inputs (reverse lanes 0-2) | DS90LV048A LVCMOS 3.3 V, VOL 0.3 V at 2 mA | Cyclone IV bank 6 at 3.3 V, each pin loaded by an LED + 1 k to +3V3 (~1.4 mA sink when low) | **Direct**, 0 R link in series (0402 pads take 22 R instead if damping is wanted). |
| LVDS receiver out -> HL2 **2.5 V input-only** PIN_88 | DS90LV048A LVCMOS 3.3 V | Cyclone IV bank 5 at 2.5 V, PCI clamp on by default | **SN74AVC4T245 translator, VCCA = 3.3 V, VCCB = 2.5 V.** Not a resistor divider: the receiver's output is specified only to -0.4 mA / +2 mA, and any divider light enough for it is too slow. |
| cable slow-in wire -> HL2 **2.5 V input-only** PIN_89 | board B LVCMOS33 through the cable | Cyclone IV bank 5 at 2.5 V | Same SN74AVC4T245, second channel. |
| HL2 2.5 V out -> Gowin 3.3 V input (`OUT 1` slow out) | Cyclone IV 2.5 V LVCMOS | GW5AST Bank 4 at 3.3 V | Direct, 100 R series on board A. **Gowin side must be `IO_TYPE=LVTTL33` (VIH 1.7 V) with `HYSTERESIS=NONE`.** |
| Gowin 3.3 V out -> LVDS driver in | GW5AST LVCMOS33 | DS90LV047A, VIH 2.0 V | Direct, 22 R series, 10 k pull-down. No margin problem. |

---

## 7. HL2-side loads and hazards this pin map has to live with

### 7.1 The four LED pins carry a pull-**up**, not a pull-down

Verified in `hardware/hl/hermeslite.net`: on each of DB1 pins 9, 11, 15 and 17 the LED
**cathode** is the FPGA pin and the **anode** goes through a **1 k to +3V3** (D2/R71, D3/R72,
D4/R73, D5/R74; all four resistors read `1K`). Each of those pins therefore carries a weak
pull-up delivering about **(3.3 - 1.9) / 1000 = 1.4 mA** when the pin is held low, and nothing
when it is high. (The brief described this as "1 k to ground"; it is not.) Consequences:

* On **DB1-9** (PIN_98, an HL2 output) the pull-up is harmless and it holds the forward clock
  net high while the HL2 is unconfigured.
* On **DB1-11 / 15 / 17** (board A's receiver outputs driving into the HL2) the receiver must
  **sink 1.4 mA**. DS90LV048A specifies VOL <= 0.3 V at 2 mA, so it is inside spec.
* **LEDs D3, D4 and D5 on the HL2 will glow or flicker with reverse-link data.** Unavoidable
  and harmless.
* The stock `hl2b5up_main` gateware drives DB1 pins 11/15/17 as LED outputs. Board A's `RX MODE`
  jumper holds the receivers off until the right gateware is loaded, and the default setting
  keeps them off whenever the `IN` cable is unplugged.

### 7.2 Forward lane 0 sits on a net with a uFL stub

DB1 pin 1 does **not** reach PIN_72 directly. `hermeslite.net`:
`Net-(DB1-Pad1) = DB1.1 + J25.2` and `Net-(CL8-Pad1) = U2.72 + J25.1 + CL8.1`. So:

* **HL2 jumper J25 must be closed** or lane 0 is dead.
* With J25 closed, the lane-0 net also carries uFL pad **CL8**, an unterminated stub on the HL2
  board that board A cannot remove. If lane 0 alone misbehaves at speed, that is the first
  suspect. Board A's cuttable link `SL_D0` (R1) only isolates *board A* from the net; it does
  not remove the stub.

### 7.3 Deliberately unused

* **DB1 pins 10 and 12** (FPGA 90/91, CW key inputs behind 100 R + 2.2 k + 1 uF filters) - not
  connected to anything on board A. Their stack-through tails pass straight up.
* **DB1 pins 16 and 18** (`SCL1` / `SDA1`) - stack-through and a test point only, no load.
* **DB1 pins 7 and 8** (the HL2's own 2.5 V `Vlvds` rail) - stack-through, test point, and the
  DNP link `SL_VLVDS`.
* **J14 pins 1-8, 21-30, 37-40** on the Tang dock - electrically open on board B.
* **HDMI CEC (pin 13), Reserved/Utility and SDA** on all six sockets - test pads only.

## 8. Known conflicts

* Board A occupies **both** DB1 and DB12, so it is mutually exclusive with the AK4951 / "HL2+"
  audio companion and with the HL2's own stock two-radio coherent link (which uses DB12 1/2 and
  5/6).
* Board A is compatible with the N2ADR filter board (DB7) and the N2ADR/Pico HL2 IO Board - no
  electrical overlap, and in rev B **no mechanical overlap either** (`DESIGN_NOTES.md` 6).
* For coherent two-radio operation the HL2's existing clock-chip coax link (CL8/CL2) is still
  required and board A does not affect it - but note section 7.2: CL8 shares lane 0's net.
