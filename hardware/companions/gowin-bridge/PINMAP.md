# gowin-bridge pin map, rev D

**One design.** One schematic, one PCB, one BOM. Two copies of this board and
one cable make a radio-to-radio link; one copy plus a Gowin-side board makes a
radio-to-FPGA link. There is no board A and no board B — rev C's two designs,
three HDMI cables, upright riser and production panel are in git history.

Authoritative. `tools/check_netlist.py` retypes every table below from this
file and asserts it against the generated netlist, so the two cannot drift.

| | |
|---|---|
| Connector | **Amphenol ICC U10A474240T**, LCSC **C5432262**, SlimSAS SFF-8654 8i, 74 position, right angle, 23.50 mm wide, 9.90 mm above the board, 15.80 mm deep |
| Cable | **10Gtek CAB-8654/8654-8i-P**, 8i to 8i, 0.5 m, $15. Twinax construction, 32 AWG, 100 Ω |
| Pairs | 16 differential, of which 14 used and 2 spare |
| Sidebands | 16 single-ended, all 16 wired or clamped |
| Lane rate | DDR at 153.6 MHz = **307.2 Mbit/s** per lane, both directions simultaneously |
| Payload | 3 lanes each way = **921.6 Mbit/s** = the complete raw 12-bit 76.8 MSPS ADC stream |
| Auxiliary | 307.2 Mbit/s each way, simultaneously, on its own clock |

---

## 1. The crossover, which is the whole reason one design works

**SFF-9402 Rev 1.1**, *Multi-Protocol Internal Cable Pinouts for SAS and/or
PCIe*, section 5, implementation note **16**:

> "The pinouts in this reference guide define full crossover cables (The A row
> on one end crosses over to the B row on the other end) … a. Based on a full
> crossover the TX (inputs to the cable at one end) crossover to RX (outputs
> from the cable at the other end). b. The sideband signals also implement a
> full crossover such that the Root/Controller and Endpoint/Backplane have
> different fixed end pin assignments."

**Tables 6-2 and 6-3** of the same document then show it contact by contact:
Table 6-2 maps the Root end's SFF-8654 **A1…A37** onto the Endpoint end's
**B1…B37**, and Table 6-3 maps **B1…B37** onto **A1…A37**. So the rule is

> **A(n) at one end ↔ B(n) at the other end, for n = 1…37.**

The contact number is preserved and only the row letter flips. It holds for the
16 high-speed pairs, all 16 sideband contacts, the two-wire management contacts
and the REFCLK/VSP contacts alike, with **no exceptions on this connector** —
SFF-9402's exemptions (notes 17 and 18) apply only to power contacts, which
exist on the 80-circuit SFF-8621 and not on the 74-circuit SFF-8654.

**Documents used, named exactly: SFF-9402 Rev 1.1 section 5 implementation
note 16, and its Tables 6-2 and 6-3**, read together with **SFF-8654 Rev 1.2
Figure 3-5** for the contact numbering and **Figure A-1 / Table A-1** for the
land pattern. Note that the real titles differ from the ones in the brief:
SFF-9402 Rev 1.1 is *Multi-Protocol Internal Cable Pinouts for SAS and/or
PCIe*, not "Multilane Copper Cable Assemblies", and SFF-9400 Rev 1.1 is
*Universal 4/8X Pinouts*, not "Multilane Copper Connector and Cable Assembly
Overview". SFF-8654 itself contains **no signal names at all** — its section
3.1 says outright "Refer to documents SFF-9400 and SFF-9402 for the possible
pinout signal assignments", which is why the names come from SFF-9402.

Independently corroborated by two production cable drawings that match the
tables exactly: IcyDock's SFF-8654 4i-to-4i pinout sheet, and Dongguan Aiqun
drawing AQ03-0219A for a 74-position 8i end.

**So: this board drives row A and listens on row B.** The identical board at
the far end drives its row A into this board's row B. Nothing is strapped,
configured or asymmetric.

**Still unverified, and it is the one thing to check with an ohmmeter.**
10Gtek publish no pinout or wiring diagram for CAB-8654/8654-8i-P — not on the
product page, not in the catalogue, not in the family datasheet. The crossover
for that exact part is therefore inferred from the specification it claims to
comply with plus two third-party drawings, not stated by the vendor. Buy one
cable and confirm that a contact in one plug's row A reaches the **other** row,
same number, at the far end. Five minutes, on a cable you are buying anyway.
A warning while doing it: 10Gtek's "straight" versus "right-angle" naming
refers to the connector body's exit direction, not to the internal wiring.

### 1.1 A reassurance about the A1 end

The SFF-8654 8X pinout is **mirror-symmetric about the connector centreline**.
Under n → 38−n the grounds map to grounds (1↔37, 4↔34, 7↔31, 13↔25, 16↔22,
19↔19), the pair positions map to pair positions, and the sideband set
{8, 9, 11, 12, 26, 27, 29, 30} maps onto itself. Both ends of the link use the
same footprint, so if the footprint has A1 at the wrong physical end of the
part, the error cancels through the cable. The only residual effect is that P
and N swap inside every pair, which inverts every lane consistently in both
directions and is undone in gateware. This is the class of mistake that
threatened rev C's mini-HDMI footprint; here it cannot scrap a board.

---

## 2. HL2 DB1 — the 2×10 header (socket J2, underside)

FPGA pin numbers are Cyclone IV EP4CE22E144 package pins. Net names are the
schematic's own.

| DB1 | Net | FPGA | Direction | What it is |
|---|---|---|---|---|
| 1 | `HL2_AUXIO_EN` | 72 | HL2 out, DC | AUXIO drive enable, **active LOW**. 2.5 V bank. Reaches the FPGA only through HL2 solder jumper **J25**; with J25 open the feature is simply unavailable and nothing else changes |
| 2 | `HL2_ADC_D0` | 76 | HL2 out | ADC sample data 0, 307.2 Mbit/s. 2.5 V bank |
| 3 | `HL2_ADC_D1` | 77 | HL2 out | ADC sample data 1. 2.5 V bank |
| 4 | `HL2_JTAG_EN` | 80 | HL2 out, DC | JTAG-over-cable enable, **active LOW**. 2.5 V bank. The VREF pin with ~21 pF of stray capacitance, which is irrelevant for a DC level |
| 5 | `HL2_ADC_D2` | 83 | HL2 out | ADC sample data 2. 2.5 V bank |
| 6 | `HL2_AUX_CLK_OUT` | 85 | HL2 out | auxiliary clock out. 2.5 V bank |
| 7, 8 | `VLVDS` | — | — | the radio's 2.5 V rail. **Tapped but not used by default** — section 10 |
| 9 | `HL2_FWD_CLK_RAW` | 98 | HL2 out | forward clock, 153.6 MHz. **3.3 V bank**, so it goes through a divider. Carries LED **D2** through R71 |
| 10 | `HL2_CWR` | 90 | bidirectional | AUXIO line 0. **CW/PTT ring**, not an LED |
| 11 | `HL2_TX_D0` | 99 | HL2 in | transmit data 0, 307.2 Mbit/s. 3.3 V bank. Carries LED **D3** through R72 |
| 12 | `HL2_CWT` | 91 | bidirectional | AUXIO line 1. **CW/PTT tip**, not an LED |
| 13, 14 | `GND` | — | — | ground |
| 15 | `HL2_TX_D1` | 100 | HL2 in | transmit data 1. Carries LED **D4** through R73 |
| 16 | `HL2_SCL1` | 103 | bidirectional | AUXIO line 2. **I2C1 SCL**, not an LED |
| 17 | `HL2_TX_D2` | 101 | HL2 in | transmit data 2. Carries LED **D5** through R74 |
| 18 | `HL2_SDA1` | 104 | bidirectional | AUXIO line 3. **I2C1 SDA**, not an LED |
| 19, 20 | `DB1_3V3` | — | — | board supply, ahead of ferrite FB1 |

## 3. HL2 DB12 — the 2×3 header (socket J3, underside)

| DB12 | Net | FPGA | Direction | What it is |
|---|---|---|---|---|
| 1 | `HL2_AUX_DAT_OUT` | 86 | HL2 out | auxiliary data out. 2.5 V bank |
| 2 | `HL2_AUX_DAT_IN` | 87 | HL2 in | auxiliary data in. 2.5 V bank |
| 3, 4 | `GND` | — | — | ground |
| **5** | `HL2_AUX_CLK_IN` | **89** | HL2 in | auxiliary clock in. **INPUT ONLY**, 2.5 V bank |
| **6** | `HL2_REV_CLK` | **88** | HL2 in | reverse clock in, a dedicated clock input. **INPUT ONLY**, 2.5 V bank |

**DB12 pins 5 and 6 are FPGA 89 and 88 in that order, not the other way
round.** rev A of this file had them transposed. `tools/check_netlist.py`
asserts it.

**HL2 R17 must not be fitted.** R17 is a 100 Ω optional LVDS termination on the
radio, wired directly between the DB12 pin 5 net and the DB12 pin 6 net — it
shorts the auxiliary clock input to the reverse clock input through 100 Ω. It
is not populated on the owner's radio; anyone else building this must check.
That is a build prerequisite, not a preference.

## 4. HL2 CN1 — the 2×5 JTAG header (socket J4, underside)

Confirmed from `hardware/hl/hermeslite.net` by taking every net that touches
CN1 and reading the other node on it.

| CN1 | Net | FPGA | What it is |
|---|---|---|---|
| 1 | `J_TCK` | 16 | TCK. HL2 R4 is a **10 kΩ pull-up** on it |
| 2 | `GND` | — | ground |
| 3 | `J_TDO` | 20 | TDO, an FPGA **output** |
| 4 | `CN1_VTREF` | — | +3V3, the programmer's VTREF **sense** line. Draw no current from it |
| 5 | `J_TMS` | 18 | TMS. HL2 R2 is a 10 kΩ pull-up |
| 6, 7, 8 | `CN1_NC6/7/8` | — | unconnected on the HL2 today; nCE, nCS and nCONFIG in Active Serial mode, so left open rather than grounded |
| 9 | `J_TDI` | 15 | TDI. HL2 R3 is a 10 kΩ pull-up |
| 10 | `GND` | — | ground |

**Correction to earlier notes:** R2, R3 and R4 are 10 kΩ **pull-ups to +3V3**,
not series resistors. `HL2_MECHANICAL_ENVELOPE.md` §12.1 called them existing
series resistors; the netlist says otherwise. Nothing on the HL2 is in series
with TCK, TMS or TDI, so every series resistor in the JTAG path is ours.

All ten nets also appear, straight through, on **J5**, a top-side 2×5 header,
so a USB Blaster still plugs in locally with this board fitted.

---

## 5. The 16 differential pairs

Position numbers are SFF-8654 contact numbers. **Row A is what this board
drives; row B is what it receives.** The right-hand column gives the brief's
own cable-pair numbering so the two can be lined up.

| Pos | Row A — this board drives | FPGA | Row B — this board receives | FPGA | Brief's pair |
|---|---|---|---|---|---|
| 2/3 | `A_AUXCLK_P/N` auxiliary clock out | 85 | `B_AUXCLK_P/N` auxiliary clock in | 89 | 9 out / 11 in |
| 5/6 | `A_AUXDAT_P/N` auxiliary data out | 86 | `B_AUXDAT_P/N` auxiliary data in | 87 | 10 out / 12 in |
| 14/15 | `A_FWDCLK_P/N` **forward clock, 153.6 MHz** | 98 | `B_REVCLK_P/N` **reverse clock** | 88 | 1 out / 5 in |
| 17/18 | `A_ADCD0_P/N` ADC sample data 0 | 76 | `B_TXD0_P/N` transmit data 0 | 99 | 2 out / 6 in |
| 20/21 | `A_ADCD1_P/N` ADC sample data 1 | 77 | `B_TXD1_P/N` transmit data 1 | 100 | 3 out / 7 in |
| 23/24 | `A_ADCD2_P/N` ADC sample data 2 | 83 | `B_TXD2_P/N` transmit data 2 | 101 | 4 out / 8 in |
| 32/33 | `A_DUPCLK_P/N` **duplicate** forward clock | 98 | `B_DUPCLK_P/N` duplicate reverse clock | 88, by link | 13 |
| 35/36 | `A_SPARE_P/N` spare driver channel | — | `B_SPARE_P/N` spare receiver channel | — | — |

Every other contact in both rows — 1, 4, 7, 10, 13, 16, 19, 22, 25, 28, 31, 34
and 37 — is **ground**: 26 contacts in all. Tally: 32 pair legs + 26 grounds +
16 sidebands = 74.

The forward group is on positions 14/15, 17/18, 20/21 and 23/24 deliberately.
Those are **four contiguous pairs, each flanked by grounds, uninterrupted by
either sideband block** (which sit at 8–12 and 26–30), and they are the four
whose skew has to match.

### 5.1 The function mirroring, and why it is the contract

The same position number carries this board's output in row A and its input in
row B, and those two must be functional counterparts, because the crossover
delivers one board's row A output onto the other board's row B input. Get this
right and radio-to-radio works with no configuration at all: each radio sends
its own samples on its forward lanes and receives the other radio's samples on
its reverse lanes.

| This board drives | faces, at the far end | so the lane is |
|---|---|---|
| forward clock, FPGA 98 | reverse clock in, FPGA 88 | the receive clock |
| ADC data 0, FPGA 76 | transmit data 0 in, FPGA 99 | lane 0 |
| ADC data 1, FPGA 77 | transmit data 1 in, FPGA 100 | lane 1 |
| ADC data 2, FPGA 83 | transmit data 2 in, FPGA 101 | lane 2 |
| aux clock out, FPGA 85 | aux clock in, FPGA 89 | the auxiliary clock |
| aux data out, FPGA 86 | aux data in, FPGA 87 | the auxiliary data |
| duplicate forward clock | a **second receiver channel**, link-selectable onto FPGA 88 | the redundant clock |
| a spare driver channel | a spare receiver channel | a spare full-duplex lane |

`check_netlist.py` asserts this table row by row, asserts that the P leg is on
the lower-numbered contact in both rows so P never meets N, and walks the whole
cable to prove each output arrives at the input that wants it.

### 5.2 The duplicate forward clock, and one deviation from the brief

The forward clock is the single point of failure for the entire receive path:
lose that trace, contact or solder joint and three good data lanes carry
nothing. So it is sent twice, from two driver channels, and the far end trains
on whichever lane works.

**The brief asked for the duplicate on a spare channel of the same driver chip.
That is not possible, and the reason is arithmetic.** A DS90LV047A has four
channels and the forward group is five signals — the clock, its three data
lanes, and the duplicate. The clock and its three data lanes have to be in one
package, because propagation delay is a part-to-part property and splitting
them turns a 0.5 ns channel-to-channel skew into a 2.6 ns part-to-part one. So
the duplicate goes in the second driver, **U5 channel 1**, fed from the same
translated net as the primary.

That costs the same one trace, and it is wider redundancy, not narrower: it
also survives a dead U4. What it gives up is skew matching to the data, which
does not matter — the duplicate exists to cover a dead lane, and the far end
re-centres whichever clock it uses with its own input delay.

The hardware half of the selection is **R_CLKSEL_A** (fitted, primary) and
**R_CLKSEL_B** (not fitted, duplicate), two 0 Ω links onto the FPGA pin 88 net.
**Fit exactly one.**

---

## 6. The 16 sideband contacts

Same convention: row A is driven by this board, row B is received.

| Pos | Row A — driven | Row B — received | What it does |
|---|---|---|---|
| 8 | `SB_PRSNT_OUT`, 1 kΩ to +3V3 | `SB_PRSNT_IN`, 10 kΩ to GND | presence and link reset |
| 9 | **nothing** — ESD clamp and a test pad only | `SB_TCK_IN` → gated buffer → 330 Ω → CN1 pin 1 | JTAG TCK in |
| 11 | `SB_AUXIO0_OUT` | `SB_AUXIO0_IN` | AUXIO line 0 (FPGA 90) |
| 12 | `SB_AUXIO1_OUT` | `SB_AUXIO1_IN` | AUXIO line 1 (FPGA 91) |
| 26 | `SB_AUXIO2_OUT` | `SB_AUXIO2_IN` | AUXIO line 2 (FPGA 103) |
| 27 | `SB_AUXIO3_OUT` | `SB_AUXIO3_IN` | AUXIO line 3 (FPGA 104) |
| 29 | **nothing** — ESD clamp and a test pad only | `SB_TMS_IN` → gated buffer → 330 Ω → CN1 pin 5 | JTAG TMS in |
| 30 | `SB_TDO_OUT`, from CN1 pin 3 | `SB_TDI_IN` → gated buffer → 330 Ω → CN1 pin 9 | JTAG TDO out, TDI in |

Contacts 10 and 28 in both rows are ground, per the specification. All 16
sideband contacts are clamped, including the two undriven outputs, because they
still leave the enclosure on a cable.

SFF-9402's own warning applies and is honoured: sideband use differs between
protocols, so "each sideband signal should be isolated i.e. NOT COMMONED in the
cable" — no two of the sixteen share a net here.

### 6.1 Presence detect, given that the cable crosses the sidebands too

Because the cable crosses A(8) onto B(8), presence detect is symmetric and
needs nothing clever: each board **asserts** on contact A8 through 1 kΩ to its
own +3V3, and **reads** contact B8 against a 10 kΩ pull-down.

| Case | What B8 reads |
|---|---|
| Far end present and powered | 3.3 × 10/11 = **3.0 V**, at 0.30 mA |
| Far end absent | the local 10 kΩ pull-down, **0 V** |
| Far end plugged in but **unpowered** | its 1 kΩ sits on a dead rail, so **low** |

That last row is the point. A hard link to ground would read "present" on an
unpowered board; referencing the assertion to +3V3 makes it read
present-**and**-powered, which is what the brief asked for.

`SB_PRSNT_IN` also serves as **link reset**: the far end pulls it low. On this
board there is a test pad you can ground by hand to assert reset in the other
direction — a gateware-driven reset would need another HL2 pin and there is not
one. The signal is brought to a test pad and to the not-fitted link
**R_DRVEN_PRSNT**, which if fitted instead of **R_DRVEN_ON** gates the two LVDS
drivers on the far end being present and powered, saving about 60 mA with no
cable plugged in. It is not the default because 10Gtek sell a **no-sideband**
variant of this cable that would leave the link dead with no clue why.

### 6.2 JTAG over the cable, and the radio-to-radio proof

**Two sideband positions are deliberately left undriven, and that is the whole
safety argument.** Position 9's far-end input is TCK and position 29's is TMS.
Nothing on this board drives A9 or A29, so in a radio-to-radio link one radio
physically cannot clock or steer the other radio's JTAG state machine, whatever
any enable does. TDO is driven out on position 30, whose far-end input is TDI —
a data line that does nothing without a clock.

`check_netlist.py` asserts that the only things on those two nets are a
connector contact, an ESD clamp and a test pad.

**What happens to all four JTAG lines in a radio-to-radio link, with the
feature disabled — which is its power-up state:**

| Line | State at the far CN1 |
|---|---|
| TCK | the gated buffer output is **tri-stated**, so CN1 pin 1 sees only the HL2's own 10 kΩ pull-up (R4) |
| TMS | the same, with R2 |
| TDI | the same, with R3 |
| TDO | read by a **high-impedance buffer input** through 330 Ω; the FPGA's TDO pin is not loaded by the cable and nothing drives against it |

**Neither radio can disturb the other's programming pins.** And if the feature
is wrongly enabled in a radio-to-radio link it is *still* safe: TCK and TMS
arrive from undriven positions, held at their pull levels — TCK low, TMS high —
and a JTAG TAP controller with no TCK edge cannot change state at all.

---

## 7. The AUXIO group — and a correction the brief needs

**FPGA pins 90, 91, 103 and 104 are not the indicator LED pins.** Read out of
`hardware/hl/hermeslite.net`:

| FPGA | DB1 | What is actually on it |
|---|---|---|
| 90 | 10 | **CW/PTT ring.** R75 2.2 kΩ to +3V3, R77 100 Ω out to the KEY jack CN4 through dual diode D8, and **C71 1 µF to ground** — a 2.2 ms time constant |
| 91 | 12 | **CW/PTT tip.** R76 2.2 kΩ, R78 100 Ω, **C72 1 µF** |
| 103 | 16 | **I2C1 SCL.** R43 4.7 kΩ pull-up, and it is a **bus**: U6, the IDT 5P49V5923 VersaClock that generates the radio's master clock, sits on it |
| 104 | 18 | **I2C1 SDA.** R44 4.7 kΩ, same bus |

**The four indicator LEDs D2–D5 are on FPGA pins 98, 99, 100 and 101** — DB1
pins 9, 11, 15 and 17 — each through a 1 kΩ resistor (R71–R74) to +3V3. The
1.4 mA sink figure in the brief is right; it belongs to those pins.

And **rev D's link already owns all four of them**: 98 is the forward clock,
99/100/101 are the transmit data lanes. So there is nothing left to tap, and
two consequences follow:

1. **The LEDs become link-activity indicators whether anyone wants them to or
   not.** D2 flickers with the forward clock, D3–D5 with the transmit data.
2. **The 1.4 mA sink requirement is real and lands on our LVDS receiver.** Each
   of DB1 pins 11, 15 and 17 has a 1 kΩ pull-up to +3V3 through an LED, so the
   receiver output must sink (3.3 − 1.9)/1000 = **1.4 mA** when low.
   DS90LV048A specifies VOL ≤ 0.25 V at IOL = 2 mA, so it is inside spec with
   the LED lit. What loads the edge is the FPGA pin (about 7 pF) plus the header
   and trace, **not** the LED: the LED's junction capacitance is in series with
   the 1 kΩ, so at 150 MHz that branch is resistive.

The mechanism the brief asked for is built anyway, on pins 90/91/103/104,
because a buffered bidirectional tap on them is genuinely useful — remote
keying, and remote access to the clock generator. It is built as **two one-way
paths**, which is safer than one bidirectional translator:

| Path | Wiring | State |
|---|---|---|
| **READ** (default) | HL2 pin → 330 Ω → **buffer input** (high impedance) → sideband out | **always on, and physically incapable of driving an HL2 pin** |
| **DRIVE** (optional) | sideband in → **buffer output** → 330 Ω → HL2 pin | gated by `AUXIO_EN_N`, pulled up at both ends and therefore **off** at power-up |

There is no direction net and no inverter, so there is no "both halves
disagree" state to analyse at all. That is the safety property rev C bought
with a one-shunt strap plus a MOSFET inverter, obtained here for free by not
having a direction.

**Contention current, at 3.3 V.** If someone loads stock HL2 gateware while the
DRIVE path is enabled, two CMOS outputs fight through **one 330 Ω resistor**.
SN74AVC4T245 at 3.3 V specifies VOL 0.7 V at 12 mA and VOH 2.3 V at −12 mA,
i.e. about 58 Ω and 83 Ω of effective source impedance; a Cyclone IV 3.3-V
LVTTL pin at its 8 mA setting is about 56 Ω.

| | |
|---|---|
| **Worst case** | 3.3 / (58 + 330 + 56) = **7.4 mA** |
| Datasheet-typical impedances | about **6.6 mA** |
| Cyclone IV absolute maximum per pin | **25 mA sink, 40 mA source** (Cyclone IV Device Datasheet CYIV-53001-1.8, Table 1-1) |
| Margin on the tighter limit | **3.4×** |
| For comparison, 100 Ω | 3.3 / (58 + 100 + 56) = 15.4 mA — inside the limit, but only 1.6× of margin |

330 Ω costs nothing on lines whose own time constant is 2.2 ms and whose
fastest legitimate use is 400 kHz I2C. **Be aware that AUXIO lines 2 and 3 are
the I2C bus to the chip that makes the radio's master clock.** The default is
READ, so this is a hazard you have to switch on deliberately.

---

## 8. The two enable levels, and why an unprogrammed board is safe

Both remote-drive features are controlled by the HL2's own gateware, through a
register the far end writes over the auxiliary channel, and both are **active
LOW**:

| Net at DB1 | FPGA | Feature | 3.3 V net |
|---|---|---|---|
| `HL2_JTAG_EN` | 80 (DB1-4) | JTAG over the cable | `JTAG_EN_N` |
| `HL2_AUXIO_EN` | 72 (DB1-1) | the AUXIO drive path | `AUXIO_EN_N` |

Each is pulled **UP at both ends** of the translator that carries it: 10 kΩ to
+2V5 on the HL2 side and 10 kΩ to +3V3 on the logic side. Pulled up is
disabled. So the disabled state survives every one of these:

| Fault | Why it is still disabled |
|---|---|
| No gateware loaded at all | Cyclone IV user I/O carry a weak pull-up during configuration, and our 10 kΩ to +2V5 reinforces it |
| Gateware loaded but not driving the pin | the 10 kΩ pull-up holds it high |
| Far end unplugged or unpowered | irrelevant — both controls are local |
| U2, the translator, missing, unfitted or unpowered | its output is high-impedance and the 10 kΩ to +3V3 wins |
| **HL2 jumper J25 never soldered** | DB1 pin 1 is then an isolated pad and the 10 kΩ to +2V5 holds AUXIO disabled. The feature is unavailable; nothing is at risk |

**`check_netlist.py` asserts exactly this**: four pull-ups, to the right rails,
and no fitted pull-down anywhere on either enable. That check replaces rev C's
strap-contention proof, and it is a stronger claim, because there is no longer
a complementary pair whose two halves could disagree.

**One deliberate departure.** The brief said FPGA pin 72 is unused in rev D so
the owner need not solder J25. It is used here, for a static DC enable level
only — and in a way that keeps soldering J25 **optional**: leave it open and
the AUXIO drive feature simply does not exist. Everything the brief was
avoiding about pin 72 — the 307 Mbit/s auxiliary clock, the unterminated uFL
stub at CL8, the unadjustable sampling phase — applies to signalling, not to a
jumper level.

**And one limitation, stated plainly.** JTAG over the cable is enabled by the
HL2's own gateware, which is a chicken-and-egg problem in exactly the case you
most want it: a radio whose gateware will not run. The recovery path is
**R_JTAG_FORCE**, a not-fitted 1 kΩ from `HL2_JTAG_EN` to ground. Fitted, it
beats the 10 kΩ pull-up (0.23 V, enabled) and costs the FPGA only 2.5 mA if the
gateware drives that pin high anyway. It is a soldering-iron job on a board
whose headers you are soldering regardless.

---

## 9. Required HL2 gateware changes

`gateware/variants/hl2b5up_gowinlink/gowinlink_pins.tcl` on branch
`gowin-link` is marked PROVISIONAL and must be rewritten to this map.

```tcl
# --- forward link: 3 lanes DDR at 153.6 MHz = 921.6 Mbit/s ---
set_location_assignment PIN_98  -to gl_fwd_clk      ;# DB1-9,  3.3 V bank
set_location_assignment PIN_76  -to gl_adc_d[0]     ;# DB1-2,  2.5 V bank
set_location_assignment PIN_77  -to gl_adc_d[1]     ;# DB1-3
set_location_assignment PIN_83  -to gl_adc_d[2]     ;# DB1-5
# --- reverse link: 3 lanes in, clock on a dedicated clock input ---
set_location_assignment PIN_88  -to gl_rev_clk      ;# DB12-6, INPUT ONLY
set_location_assignment PIN_99  -to gl_tx_d[0]      ;# DB1-11
set_location_assignment PIN_100 -to gl_tx_d[1]      ;# DB1-15
set_location_assignment PIN_101 -to gl_tx_d[2]      ;# DB1-17
# --- auxiliary link, full duplex, its own clock each way ---
set_location_assignment PIN_85  -to gl_aux_clk_out  ;# DB1-6
set_location_assignment PIN_86  -to gl_aux_dat_out  ;# DB12-1
set_location_assignment PIN_89  -to gl_aux_clk_in   ;# DB12-5, INPUT ONLY
set_location_assignment PIN_87  -to gl_aux_dat_in   ;# DB12-2
# --- two DC enable outputs, ACTIVE LOW, must power up HIGH = disabled ---
set_location_assignment PIN_80  -to gl_jtag_en_n    ;# DB1-4
set_location_assignment PIN_72  -to gl_auxio_en_n   ;# DB1-1, needs HL2 J25
# --- the AUXIO group: TRI-STATE THESE FOUR before asserting gl_auxio_en_n ---
set_location_assignment PIN_90  -to gl_auxio[0]     ;# DB1-10, CW/PTT ring
set_location_assignment PIN_91  -to gl_auxio[1]     ;# DB1-12, CW/PTT tip
set_location_assignment PIN_103 -to gl_auxio[2]     ;# DB1-16, I2C1 SCL
set_location_assignment PIN_104 -to gl_auxio[3]     ;# DB1-18, I2C1 SDA

# PIN_98 drives a 100 R / 470 R divider that draws 5.8 mA, so it needs the
# 8 mA drive setting, not the 4 mA default.
set_instance_assignment -name CURRENT_STRENGTH_NEW "8MA" -to gl_fwd_clk
set_instance_assignment -name WEAK_PULL_UP_RESISTOR ON -to gl_jtag_en_n
set_instance_assignment -name WEAK_PULL_UP_RESISTOR ON -to gl_auxio_en_n
```

What the gateware must do that the hardware cannot enforce:

* **Tri-state PIN_90, 91, 103 and 104 before asserting `gl_auxio_en_n`.** The
  330 Ω series resistors make getting the order wrong survivable at 7.4 mA, not
  harmless.
* **Never assert `gl_auxio_en_n` on a radio-to-radio link** unless you mean the
  other radio to drive this one's CW/PTT inputs and I2C bus.
* **Both enables must power up and stay HIGH** until something deliberately
  asserts them.
* PIN_98's forward clock leaves the FPGA ahead of the divider, so what the
  divider sees is the pin's own edge and what the translator sees is the
  divider's 132 Ω Thevenin driving about 4 pF — 0.53 ns.

## 10. Deliberately unused

| | Why |
|---|---|
| HL2 `VLVDS` on DB1 pins 7/8 | brought to a test pad and to the not-fitted link `SL_VLVDS`, but the board makes its own 2.5 V. `DESIGN_NOTES.md` section 5: the radio's 2.5 V LDO has perhaps 50 mA spare, and the rail it would brown out is the FPGA bank supply carrying the ADC data |
| CN1 pins 6, 7, 8 | unconnected on the HL2 today, but nCE/nCS/nCONFIG in Active Serial mode. Passed through to J5 and left **open**, not grounded |
| CN1 pin 4 | passed through to J5 as the programmer's VTREF sense line; no current drawn |
| Two sideband output contacts, A9 and A29 | undriven on purpose — section 6.2 |
| One of the 16 differential pairs, positions 35/36 | a spare full-duplex lane; driver input and receiver output both on test pads |
| Two of 48 ESD channels | the twelfth array's spare channels |
| Three of 28 translator channels | U11's port 2 is disabled with its inputs grounded and its outputs on test pads, and one channel of U11 port 1 is spare. Three gated 3.3 V channels available for a future revision |
