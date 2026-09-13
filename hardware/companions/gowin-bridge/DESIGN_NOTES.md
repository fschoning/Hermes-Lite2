# gowin-bridge design notes, rev D

Why the design is the way it is, with the numbers. `PINMAP.md` is the pin
contract; this is the reasoning. **One design with two ends on one panel**:
the radio end (sections 1-10) and the Gowin end (section 11). One schematic,
one PCB, one BOM. rev C's three HDMI cables and riser are in git history.

---

## 1. Data rates and unit intervals

| | Value |
|---|---|
| AD9866 sample rate | 76.8 MSPS, 12 bits |
| Raw stream | **921.6 Mbit/s** |
| Lanes per direction | 3 data + 1 clock |
| Lane rate | DDR at 153.6 MHz = **307.2 Mbit/s** |
| Unit interval | **3.2552 ns** |
| Both directions | simultaneously, on their own forwarded clocks |
| Auxiliary channel | one more clock and one more data lane each way, also 307.2 Mbit/s, also simultaneously |
| Driver rating | DS90LV047A fMAX 200 MHz min / 250 MHz typ, i.e. 400 Mbit/s — **77 % of rating** |
| Translator rating | SN74AVC4T245 380 Mbit/s at these rails — **81 % of rating** |
| LVDS transition time | about 1 ns, so **31 % of a unit interval** |

Both the 77 % and the 81 % are worth a scope check at bring-up. They are
unchanged from rev C, because rev C already ran every lane at this rate.

### 1.1 What is still unverified about the rate

Whether the Cyclone IV C8 fabric can capture 307.2 Mbit/s DDR on ordinary
bank-6 inputs. The device has one input register per IOE, so DDR input needs
soft logic clocked at 153.6 MHz. This gates every received lane. It is a
gateware and timing-closure question, not a board question, and no board change
can fix it if the answer is no.

---

## 2. The 2.5 V threshold, and the part that does not exist

### 2.1 The problem, with the numbers

| | Value | Source |
|---|---|---|
| Cyclone IV 2.5 V output, VOH min | **2.0 V** at IOH = −1 mA | Cyclone IV Device Datasheet CYIV-53001-1.8, Table 1-15 |
| DS90LV047A input VIH min | **2.0 V** | TI SNLS044D, Electrical Characteristics |
| **Guaranteed margin** | **0 mV** | |

Every 2.5 V-bank signal that originates at the HL2 and has to reach an LVDS
driver hits this: the three ADC data lanes and the auxiliary transmit pair.
It is the main signal path, not an edge case.

### 2.2 The 2.5 V LVDS driver was looked for properly. It does not exist.

The obvious fix is to power the LVDS driver from 2.5 V, whereupon its input
threshold would become about 0.7 × VCC = 1.75 V and the HL2's guaranteed 2.0 V
would have 250 mV of margin with no translator at all. That would delete three
chips and a divider. It was chased before anything else was decided.

**There is no quad CMOS-in / LVDS-out driver and no quad LVDS-in / CMOS-out
receiver specified from a 2.5 V supply, from any manufacturer, in any package,
at any price, that can be bought.** Two reasons:

1. Every quad LVDS line driver and receiver ever made runs 3.0–3.6 V. All 253
   parts in LCSC's LVDS category were swept; **not one has a supply range
   starting below 3.0 V.**
2. **Lowering the supply would not lower the threshold anyway.** These parts
   specify VIH = 2.0 V and VIL = 0.8 V as absolute TTL levels, not as a
   fraction of VCC. TI's own application note **SNLA307** exists to say so:
   "most LVDS drivers and receivers available on the market have 3.3-V supplies
   and only support 3.3-V LVTTL/LVCMOS signals", and its recommended fix is
   exactly a `SN74AVCxx45` translator in front of a 3.3 V driver.

Parts that genuinely are specified at 2.5 V, and why none of them helps:

| Part | What it is | Why not |
|---|---|---|
| TI SN65LVDS1 | single driver, 2.4–3.6 V, real 2.5 V spec | **VIH still 2.0 V.** Buys nothing. Four of them cost more than one quad plus a translator, in four times the area |
| TI SN65LVDS2 | single receiver, 2.4–3.6 V | single channel |
| TI SN65LVDS4 | single receiver with a separate 1.8/2.5/3.3 V output supply, fully specified at VCC = 2.5 V | single channel, and LCSC holds 34 pieces |
| TI CDCLVD1204 | fully 2.375–2.625 V | needs an external threshold reference on a complementary pin, i.e. the resistor divider this was meant to remove |
| ST RHFLVDS41 | **a real 2.3–3.6 V quad LVDS driver, announced February 2026** | space-qualified, ceramic Flat-16, QML-V, four-figure unit price, months of lead time, no distributor. It exists; you cannot have it |
| TI SN75LVDS83B | the only catalogue LVDS transmitter with a **guaranteed 1.65 V** input threshold, from a separate IOVCC pin (SLLS846C table 7.3) | it is a 28-bit 7:1 serializer, not a 4-channel driver, and −10 to +70 °C |

Also checked and all 3.0–3.6 V with 2.0 V thresholds: SN65LVDS047/048,
SN65LVDS31/32, SN65LVDS3486/3487, SN65LVDS9637/9638, SN65LVDS389/388A,
SN65MLVD, DS90LV031A/032A, DS90LV011A/012A, DS90LV004, the whole onsemi FIN
family (FIN1027/1028/1031/1032/1047/1048/1101/1102/1108, titled "3.3 V LVDS"),
ADI ADN4661–4668 and ADN4696/4697, Maxim MAX9111/9112/9121–9124/9173–9176,
Pericom PI90LV047/048, ROHM BU90LV047A/048, ST STLVDS47B, Runic RS90LV047,
Relmon MS90C032/385B/386B, 3PEAK TPT9H221, LKI8010/8011/8012. Renesas/IDT's
2.375–2.625 V parts are clock fanout buffers with differential inputs, not
CMOS-to-LVDS drivers. LTC1685/1686 are 5 V RS-485 parts, not LVDS.

### 2.3 So the translator stays, and what it costs

**U1 and U2 are SN74AVC4T245PW (LCSC C81461), VCCA = 2.5 V, VCCB = 3.3 V, both
DIR tied to VCCA, both OE* to ground.**

| | Value |
|---|---|
| A-side VIH min | **0.65 × VCCA** |
| At VCCA = 2.5 V nominal | 1.63 V → **370 mV of margin** over the HL2's 2.0 V |
| At VCCA = 2.55 V, the LDO's +2 % corner | 1.66 V → **340 mV**, the number to design to |
| At VCCA = 2.375 V | 1.54 V → 460 mV |
| B-side output | 3.3 V CMOS into the driver's 2.0 V threshold, 1.3 V of margin |
| Rated data rate | 380 Mbit/s; fastest signal through it 307.2 Mbit/s = **81 %** |
| Propagation delay | about 0.1 to 2.9 ns over the process and temperature table |
| Quiescent | ICCA and ICCB **8 µA max each** |

**The forward clock goes through the same package as its three data lanes.**
That is U1: four channels, exactly the forward group, nothing else. Propagation
delay is a part-to-part property, so putting them in one package turns a 2.6 ns
part-to-part uncertainty into a channel-to-channel one. The auxiliary clock and
data share U2's port 1 for the same reason.

**The forward clock is the awkward one, because FPGA pin 98 is a 3.3 V bank pin
and the translator's A-side absolute maximum is VCCA + 0.5 V = 3.0 V.** It
arrives through a divider:

| | Value |
|---|---|
| Divider | **100 Ω series + 470 Ω shunt**, both JLCPCB Basic parts |
| High level | 3.3 × 470/(470+100+50) = **2.50 V** |
| Worst corner (3.465 V rail, 2.45 V VCCA → 2.95 V absolute max) | 2.63 V — **320 mV of headroom** |
| Margin over VIH 1.63 V | **870 mV** |
| Current from pin 98 | 3.3 / 570 = **5.8 mA**, so set that pin to its 8 mA drive strength |
| Thevenin impedance | 100 ∥ 470 + 50 = **132 Ω** |
| Edge into the translator's ~4 pF | **0.53 ns** |
| Low level with the HL2 FPGA unconfigured | pin 98 carries LED D2 and R71, 1 kΩ to +3V3, so it sits at 1.4 V behind 1 kΩ: 1.4 × 470/1570 = **0.42 V** against the 0.875 V VIL limit |

rev C used 100 Ω + 660 Ω as two 330 Ω resistors because 470 Ω was not then a
Basic part in JLCPCB's library. It is now (**C25117**), so this is one resistor
instead of two, with better margin at every corner and 130 mV more headroom
under the absolute maximum.

**Pull-downs.** Every 2.5 V-bank net into U1 and U2 gets a 10 kΩ pull-down so
it is defined while nothing drives it. **The forward clock deliberately does
not**: its own LED pull-up plus the divider already define it at 0.42 V, and
adding 10 kΩ would park the node in the translator's forbidden band between
VIL 0.875 V and VIH 1.63 V.

### 2.4 And the other direction: 3.3 V into the HL2's 2.5 V input-only pins

HL2 PIN_88 (DB12-6), PIN_89 (DB12-5) and PIN_87 (DB12-2) are in a 2.5 V bank
with the PCI clamp diode on by default, and 88 and 89 are input-only. A 3.3 V
driver held high would inject DC into the radio's 2.5 V rail. **U3 is a third
SN74AVC4T245 with VCCA = 3.3 V and VCCB = 2.5 V**, carrying the two candidate
reverse clocks in port 1 and the auxiliary receive pair in port 2.

A resistor divider was rejected on the same numbers as in rev C: DS90LV048A
specifies VOH only to 2.7 V at −0.4 mA and VOL 0.25 V at 2 mA, so it cannot
drive a divider light enough to resolve a 3.2552 ns unit interval.

**The three transmit data lanes need no translation** — DB1 pins 11, 15 and 17
are 3.3 V-bank pins — so the receiver output drives them through a 0 Ω link on
0402 pads, with 22 Ω available if damping ever helps.

### 2.5 The option that would delete all three translators, for the record

The Cyclone IV can drive true LVDS on the output pins of its row I/O banks and
emulated LVDS (three external resistors) anywhere, with VCCIO = 2.5 V, which
these banks already run at. That deletes both the translators and the driver
chips. It needs the pins brought out to DB1 and DB12 to be assignable as
adjacent differential pairs, and they are not: 76, 77, 83, 85, 86 and 98 are
scattered across two banks and two headers. Recorded so nobody has to
rediscover it. rev C's `PINMAP.md` §5.3 examined the same idea.

---

## 3. Termination, edge rates and the tight paths

* **Every received pair gets a 100 Ω differential resistor**, eight in all,
  **within 5 mm of the receiver pins**. There is no termination at a driver
  output, which is correct for LVDS.
* **LVDS swing** 250–450 mV (VOD1 into 100 Ω), common mode 1.125–1.375 V.
* **The cable is not the limit.** SFF-8654 8i cable is **twinax** construction,
  32 AWG, 100 Ω, qualified to 24 Gb/s per channel for SAS-4. 307.2 Mbit/s is
  two orders of magnitude below that. The 400 Mbit/s driver rating is the
  limit, not the cable, and a metre is fine.
  **On the word "unshielded":** the phrase that appears on cable listings comes
  from the connector standard's own title, *0.6mm 4/8X **Unshielded** I/O
  Connector*, and from Amphenol's own connector page — "Designed for
  unshielded, internal or external I/O connectors". It describes a connector
  with no metal shroud, not a cable with no shield. 3M's equivalent product is
  literally named "SlimLine **Twin Axial** Cable Assembly (SFF-8654)", and
  10Gtek's own family datasheet is titled "SAS Slimeline **Twinax** Cable".
  What is **not** confirmable from any openable document is the layer-by-layer
  shield stack-up — foil per pair versus overall foil plus braid, and the
  drain-wire count. If a formal EMC case ever needs that, ask 10Gtek or cut one
  open.
* **Every single-ended HL2 net is under 25 mm** by layout rule. The floor plan
  in section 6 is built around that.
* **Impedance:** the connector is specified 85 Ω ±10 differential and the
  chosen cable SKU is 100 Ω. An 85/100 mismatch is a 8 % reflection
  coefficient, which at 307.2 Mbit/s is irrelevant. JLCPCB Economic gives no
  impedance guarantee, so aim the board for 100 Ω differential and accept it.

### 3.1 Tight path one: the three transmit lanes into the HL2's LED pins

DB1 pins 11, 15 and 17 are FPGA pins 99, 100 and 101, and each carries an LED
whose anode goes through 1 kΩ to +3V3 (D3/R72, D4/R73, D5/R74, verified in
`hermeslite.net`).

* **The receiver must sink 1.4 mA** when low: (3.3 − 1.9)/1000. DS90LV048A
  specifies VOL ≤ 0.25 V at IOL = 2 mA, so it is inside spec with the LED lit.
* **The LED does not load the edge.** Its junction capacitance (20–50 pF) is in
  *series* with the 1 kΩ, so at 150 MHz that branch is resistive. What loads
  the edge is the FPGA pin (about 7 pF for a right-side Cyclone IV pin) plus
  the header and trace, roughly 12–15 pF.
* A 3.3 V CMOS output with about 50 Ω of effective source impedance into 15 pF
  gives a 10–90 % rise of about **1.65 ns, which is 51 % of the unit
  interval.** That works, and it is the tightest margin on the board.
* The series parts are **0 Ω by default on 0402 pads**, so a damping value can
  be substituted without a respin — but do not raise them much: at 22 Ω the
  rise grows to about 1.9 ns.

### 3.2 Tight path two: nothing, and that is the change from rev C

rev C's second tight path was FPGA pin 80, the VREF pin with ~21 pF of stray
capacitance, carrying a bidirectional auxiliary lane at 1.49 ns of edge. In
rev D pin 80 carries a **DC enable level** and nothing else, so the 21 pF is
irrelevant and the path is gone. Pin 72, whose uFL stub at CL8 and unadjustable
sampling phase were the other worry, likewise carries only a DC level.

---

## 4. Power. This is the number that was blocking the order.

### 4.1 What the board draws

Every figure below is either a datasheet maximum or a computed
`I = (Cpd + CL) × V × f`. Where a datasheet publishes no guaranteed number, it
says so.

**On the 3.3 V rail:**

| Load | Current | Where it comes from |
|---|---|---|
| U4, U5 — two DS90LV047A quad drivers | **80 mA** (40 each) | SNLS044D: ICC no load 8 mA max, ICC loaded static (RL = 100 Ω on all four) **30 mA max**. TI publishes **no guaranteed switching ICC** — only Figure 24, whose "All Switching" curve rises to about 35–38 mA. 40 mA is the design figure and it is above the only guaranteed number there is |
| U6, U7 — two DS90LV048A quad receivers | **80 mA** (40 each) | SNLS045C: ICC no load 15 mA max; four outputs into ~10 pF at 153.6 MHz add 4 × 10p × 3.3 × 153.6M = 20 mA. Again no guaranteed switching ICC, only Figure 21 at about 40 mA |
| U1 — forward group translator, B side | **47 mA** | 4 channels × (CpdB 15 pF + 8 pF of load) × 3.3 V × 153.6 MHz. Cpd from SCES576I Table 5.6 |
| U2 — auxiliary translator, B side | **23 mA** | 2 switching channels, same arithmetic. The two enable channels are static |
| U3 — reverse translator, A side | **4 mA** | 4 channels × CpdA 2 pF × 3.3 V × 153.6 MHz |
| U8–U11 — the AUXIO and JTAG buffers | **12 mA** | dominated by TCK at 24 MHz, and only while programming; the AUXIO lines are DC to 400 kHz |
| The whole 2.5 V rail, through U12 | **50 mA** | see below. An LDO passes its output current straight through |
| Presence assert, 1 kΩ | **0.3 mA** | |
| Pull-ups, pull-downs, the divider | **3 mA** | |
| Quiescent: 7 × SN74AVC4T245 at 8 µA, U12 at 40 µA, 12 ESD arrays | **<0.1 mA** | |
| **Total** | **299 mA** | |
| **Design figure** | **350 mA** | |

**On the 2.5 V rail, which the board makes itself:**

| Load | Current |
|---|---|
| U3 B side: three switching channels × (CpdB 14 pF + 12 pF of HL2 pin and trace) × 2.5 V × 153.6 MHz | **30 mA** |
| U3 B side: the duplicate-clock channel driving an open pad (~3 pF) | **6.5 mA** |
| U1 A side: 4 × CpdA 2 pF × 2.5 V × 153.6 MHz | **3.1 mA** |
| U2 A side: 2 switching channels | **1.5 mA** |
| **Total** | **41 mA** |
| **Design figure** | **50 mA** |

### 4.2 What the radio can actually spare

Traced through `hardware/hl/Power.sch`, `hermeslite.net` and
`hermeslite.kicad_pcb` on schematic revision **2.0-build9**.

**+3V3 — one regulator for the whole radio.**

| | |
|---|---|
| Regulator | **U3, ST1S10PHR** synchronous buck, HSOP-8, **no heatsink** (the only two heatsinks on the radio are HS2 on the FPGA and HS7 on the AD9866) |
| Input | VSUP, 11–16 V, after the 3 A PTC fuse F1 and reverse-polarity FET Q1 |
| Chip rating | **3.0 A** |
| Output inductor | **L1, SRR4528A-3R3Y, rated 2.4 A** — the real hardware ceiling |
| Set point | R11 35.7 k / R12 11.5 k → 0.8 × (1 + 35.7/11.5) = **3.28 V** |
| **The designer's own annotation beside it on Power.sch** | **"<=1.5A"** |
| There is **no second 3.3 V regulator** | the Ethernet PHY and the FPGA share this one |

Existing load on it, bottom-up. The four largest are estimates and are labelled
as such:

| Consumer | Current | Basis |
|---|---|---|
| U7 AD9866 codec, all four 3.3 V domains (via FB17–FB20) | 150 mA | **estimate** from its ~0.4–0.6 W class at 76.8 MHz |
| U4 KSZ9031RNX PHY, AVDDH (via FB10) | 60 mA at 1 Gb | **estimate** |
| FPGA VCCIO banks 1, 2, 6, 7, 8 | 45 mA | **estimate**, dominated by the AD9866 DDR bus |
| U6 5P49V5923 VersaClock (via FB23–FB26) | 50 mA | **estimate** |
| X2 38.4 MHz oscillator (via FB12) | 15 mA | estimate |
| U17 TPS73025, i.e. the whole 2.5 V rail | 100 mA | see below |
| Magjack LEDs, R133/R134 = 270 Ω | 9.6 mA | **calculated** |
| Front-panel LEDs D2–D5, R71–R74 = 1 kΩ | 5 mA all on | **calculated** |
| Flash, MAX11613, MCP4662, MCP9700, PE4259, pull-ups | 8 mA | estimate |
| K2 TR relay coil | **0 mA** — PA.sch says the assembly house does not fit it | |
| **Total** | **≈ 450 mA** (range 350–600) | |

| Against | Spare |
|---|---|
| the ST1S10's 3.0 A | 2.55 A |
| L1's 2.4 A | 1.95 A |
| **the designer's own 1.5 A note** | **≈ 1.05 A** ← use this one |

**This board's 350 mA is 33 % of that spare.** Even at the pessimistic 600 mA
of existing load the spare is 900 mA and the board is 39 % of it. The rail
total becomes about 800 mA against a 2.4 A inductor.

**The copper is not the limit either.** DB1 pins 19/20 have **no series element
whatever** — no bead, no resistor, no fuse, no TVS — between L1 and the header.
The narrowest segment of that path is **1.25 mm on an external layer with no
plane** (+3V3 has no zone anywhere on the 4-layer radio), which IPC-2221 puts
at **2.8 A at a 10 °C rise**. One 0.5 mm via in the path is worth 2–2.5 A.

**2.5 V — and this is why the board makes its own.**

| | |
|---|---|
| Regulator | **U17, TPS73025DBVR**, a fixed 2.5 V LDO in **SOT-23-5**, fed from +3V3 |
| Rating | **200 mA total** |
| **The designer's own note** | **"150 mA sufficient for all 2.5V use"** |
| What it already feeds | FPGA VCCA1–VCCA4 (the four PLL supplies, via FB5–FB8) ≈ 12 mA; **net Veth** via FB30 = the KSZ9031's DVDDH RGMII I/O supply plus FPGA VCCIO banks 3 and 4 ≈ 55 mA at 125 MHz DDR; **net Vlvds** via FB28 = FPGA VCCIO **bank 5** plus DB1 pins 7/8 ≈ 8 mA; and FPGA pin 96, the MSEL1 configuration strap |
| Existing total | **≈ 75 mA** (range 45–135), every component of which is an estimate |
| Spare | **50 mA safely, 100 mA plausibly, 125 mA as an absolute ceiling** |
| FB28, the bead in the DB1 path | **TDK MPZ1608S601ATA00**, 600 Ω at 100 MHz, **1 A**, ≤200 mΩ. Not the limit — the 200 mA LDO binds first. What it does cost: every milliamp the board takes drops across 200 mΩ on the **shared** side, pulling down the FPGA's own VCCIO5 |
| Copper from FB28 to DB1 7/8 | 0.7 mm on B.Cu, ~19 mm, no vias → 1.85 A at a 10 °C rise. Not the limit |

**Verdict: fit the on-board LDO.** This board's 50 mA is the *whole* of the
radio's conservative 2.5 V headroom, that headroom figure is a bottom-up
estimate with wide error bars, and the rail it would brown out is **VCCIO5, the
bank that carries the ADC data this board exists to read**. So:

* **U12, ME6211C25M5G-N (LCSC C194395), 2.5 V 400 mA LDO, FITTED.** Fed from
  the board's own +3V3. 0.8 V of drop × 50 mA = **40 mW**, and 8× of current
  headroom. Output tolerance ±2 %, which is where the 340 mV threshold margin
  in section 2.3 comes from.
* **`SL_VLVDS` and `FB2`, NOT FITTED**, are the alternative: tie the 2.5 V side
  to the radio's own Vlvds instead. Electrically ideal, because the thresholds
  then track the FPGA bank supply exactly. Do not fit them together with U12.
  Measure Vlvds under load before trusting it.

It costs $3.07 in a feeder fee and six cents in silicon. That is cheap
insurance against browning out the rail you are reading.

**There is no 5 V, 12 V or unregulated supply on DB1 or DB12.** DB1 offers only
+3V3 (pins 19/20), 2.5 V (7/8) and ground (13/14); DB12 offers ground (3/4) and
four signals and no power at all. Raw power exists only on DB7, the filter-board
edge header, which this board does not reach.

**There is no published limit on what an expansion board may draw from DB1.**
Searched every schematic text note, the Sphinx documentation dump and every
`.md` in the repository. The only numbers the design offers are the two Power.sch
annotations quoted above. For what it is worth, KF7O's own unreleased DB1
companion (`hardware/companions/io/io.sch`) carries the note "Optional
Regulator for 5-11V", i.e. it provisioned its own supply rather than living off
the header.

### 4.3 Inrush, and the one thing not to do

Bulk capacitance is deliberately modest — **10 µF per rail and no more**.

| | |
|---|---|
| Total on the 3.3 V side | 10 µF after FB1 + 10 µF before it + ~1.7 µF of 100 nF = **21.7 µF** |
| Total on the 2.5 V side, behind the LDO | 10 µF + 1 µF + ~0.5 µF = **11.5 µF** |
| **At power-up**, with the radio's ST1S10 soft-starting over about 1 ms | I = C dV/dt = 21.7 µF × 3.3 V / 1 ms = **72 mA** of charging current on top of the load. Nothing |
| **On hot plug**, inserting the board with the radio running | 3.3 V / (FB1's 50 mΩ + about 100 mΩ of trace and contact) = **about 22 A**, decaying with τ = 0.15 Ω × 21.7 µF = **3.3 µs**, total charge 72 µC |

**Do not fit or remove the board with the radio powered.** It is on the
silkscreen. That 22 A microsecond spike would dip the radio's 3.3 V rail, and
it is also the reason the bulk is 10 µF and not 100 µF.

**FB1, BLM18PG121SN1D (LCSC C14709), 0603, 120 Ω at 100 MHz, 2 A, 50 mΩ**,
sits in the 3.3 V feed and drops **15 mV at 300 mA**. It keeps this board's
switching currents out of a rail that has no filtering of its own between the
regulator and the header. It is JLCPCB **Basic**, which matters: it is the only
Basic bead that combines ≥1 A with ≤150 mΩ. No Basic bead reaches 600 Ω at that
current, and 120 Ω is ample for a rail filter — the whole Basic range is four
parts and the other three fail on current or DC resistance.

---

## 5. ESD. Every conductor that leaves the enclosure.

**Decision: protect all of them.** 32 pair conductors plus all 16 sideband
conductors = **48**, in twelve 4-channel arrays.

| | |
|---|---|
| Part | **TPD4E05U06DQAR**, LCSC **C138714** |
| Capacitance | **0.5 pF per channel** |
| Standoff / clamp | 5.5 V / 6.5 V, unidirectional — right for 3.3 V logic and for LVDS at a 1.2 V common mode |
| Package | USON-10, 2.5 × 1.0 mm |
| Stock / price | 45,345 at LCSC, **$0.0698 at qty 10**, JLCPCB Extended |
| Count | **12 arrays**, 48 channels, 2 spare |
| Cost | **$0.84 per board** plus one $3.07 feeder fee |
| **Electrical cost** | 0.5 pF × 50 Ω = **25 ps** of added rise time on a 3.2552 ns unit interval, i.e. **0.8 %**. Free |

Placement rule: **within 5 mm of the SlimSAS contacts, on the connector side of
the terminations, the series resistors and the buffers, with the shortest
possible ground return.**

Why not something cheaper or bigger:

* **No ESD array of any channel count is Basic tier** in JLCPCB's library. The
  entire Basic TVS range is four SMA/SMB power diodes with 5–12 V standoff and
  unpublished (i.e. 100 pF class) capacitance. They would not clamp a 3.3 V
  line and would destroy a 307 Mbit/s lane.
* **The 6- and 8-channel parts are worse on every axis.** TPD6E004 is 1.6 pF
  per channel and TPD8E003 is **9 pF** — three to eighteen times over budget —
  and the 8-channel part costs 25 times more per conductor and has 61 pieces in
  stock.
* **SRV05-4 (C558418)** at $0.0248 would be the cheapest 4-channel option, but
  its I/O-to-ground capacitance is **0.8 pF**, over the 0.5 pF limit, and the
  in-stock part is a clone with 20 V clamping rather than the brand-name part's.
* **SP3012-04UTG (C2987148)**, 0.3 pF, DFN2510-10, $0.0388, is the better part
  on both capacitance and price and is recorded as the alternative. It was not
  taken because LCSC holds 4,021 against C138714's 45,345 and C138714 is
  already proven in this BOM.

---

## 6. Mechanical: the outline, and why the connector is not in front of DB1

### 6.1 The new outline

| | |
|---|---|
| Outline | **local x 0…64.50, y 0…64.95 = HL2 x 70.00…134.50, y 73.30…138.25** |
| Size | **64.50 × 64.95 mm**, 4 layers, 1.6 mm, HASL |
| Local origin | HL2 main-board (70.00, 73.30), so local x = HL2 x − 70.00 |
| Underside | **11.04 mm** above the HL2's top surface; top surface at 12.64 mm |
| Window in the board | **local x 44.50…57.00, y 39.50…50.00** (131 mm², 3 % of the board) to keep HL2 config headers DB6 and DB3 reachable. They clear an 11.04 mm underside by 2.5 mm, so this is about access, not collision — without it you would lift the whole board off to move a jumper |
| M3 anchor | a **3.4 mm U-notch open to the top edge**, centred on local x 3.00 |
| Locating peg | **1.1 mm unplated hole at local (4.04, 2.12)** = HL2 MH6 (74.04, 75.42) |

**Confirmed from `hermeslite.kicad_pcb`:** the board must reach **x = 134.50**
because CN1's two pad columns are at HL2 x **128.23 and 130.77** with a 1.85 mm
pad, i.e. copper to 131.70, plus the socket body. It may reach **y = 138.25**
and no further, because `HL2_MECHANICAL_ENVELOPE.md` §2.5 puts the extrusion's
internal clear width at HL2 y 41.75…138.25. And `HL2_MECHANICAL_ENVELOPE.md`
§12.4 confirms the corridor is clean: apart from CN1 itself at 8.54 mm, the
tallest thing in 54 mm of board between x 73 and 136 at y 75…100 is the FPGA at
1.60 mm.

**The M3 anchor had to become a notch.** HL2 MH2 sits at (73.00, 137.00) =
local (3.00, 63.70), only **1.25 mm** from the top edge, and the top edge
cannot move. A 3.2 mm hole centred 1.25 mm from an edge breaks out of it by
0.35 mm. So the screw passes through a U-notch instead: the screw head and
washer still clamp the board onto the 11.04 mm standoff, and with the connector
lying flat there is almost no tipping moment for it to resist anyway.
`check_geometry.py` recomputes the 1.25 mm and fails if it ever becomes big
enough for a plain hole.

**MH6, the 1 mm locating peg, is available in rev D and was not in rev C.**
With the connector moved away from that corner there is nothing in the way.

### 6.2 Why the connector moved along the front edge, and this is a hard finding

The obvious place for the receptacle is the middle of the front edge, inside
the 29.60 mm of panel that is free at board level (HL2 y 72.86…102.44, bounded
by the magjack and the clock SMAs). **It cannot go there.**

A right-angle SFF-8654 receptacle lands its contact pads **12.35 to 15.35 mm**
inboard of the board edge and its four shell tails **1.65 to 8.15 mm** inboard.
And in that y span:

* **DB12's six through-holes are at local x 13.50 and 16.04** — straight through
  the middle of a 0.60 mm pitch pad field.
* **DB1's twenty holes are at local x 4.04 and 6.58**, which collide with the
  shell tails: the tail column at x 5.15 is only 1.11 mm from DB1's x = 4.04
  column, and the tails' 23.26 mm span is not commensurate with DB1's 2.54 mm
  pitch, so no y offset clears both tails at once.

**No setback fixes it.** Pushing the connector inboard far enough to clear both
hole columns needs ≥ 16.4 mm, which puts the mating face about 6 mm behind the
panel where no plug can reach it.

**So the connector moves along the edge to local y 46.00 = HL2 y 119.30**, past
the far end of DB1. That works because **the panel opens out with height**:
§2.4 and §11.3 give 29.60 mm of clear width at board level but the full
96.50 mm of the extrusion's internal width above about 14 mm, and a connector
standing on this board's 12.64 mm top surface occupies **12.64 to 22.54 mm**
above the main board — entirely inside that band, and **above** the existing
clock-SMA and KEY-jack holes rather than beside them.

| | |
|---|---|
| Receptacle | local y 34.25…57.75 = **HL2 y 107.55…131.05** |
| Mated plug overmould, 25.95 mm (SFF-8654 Table 5-1, A03) | **HL2 y 106.33…132.28** |
| Against the extrusion's clear width 41.75…138.25 | **64.58 mm spare below, 5.97 mm above** |
| Plug thickness, 9.90 mm (Table 5-1, A13) | 12.64…22.54 mm above the main board |
| **Panel window** | **26.5 × 10.5 mm**, centred on HL2 y 119.30, from **19.6 to 30.2 mm above the enclosure's outer bottom face** (the PCB top surface is 7.30 mm up) |

What is underneath at that y, and it is the one thing still to measure: the two
clock SMAs (CL1/CL2, HL2 x 74.04…78.24, y 103.36…123.60, expected 3–8 mm,
**measurement M3**) and the 3.5 mm KEY jack (CN4, x 70.20…82.10, y
124.00…136.00, expected 6–10 mm, **measurement M2**). An 11.04 mm underside
clears both if they measure as expected.

**The floor plan this produces is better than rev C's, not worse.** The
translators and LVDS chips sit in local x 9…53, y 12…34, right beside DB1 and
DB12, so every single-ended HL2 net stays well inside §11.6's 25 mm rule; the
only long runs are the terminated 100 Ω differential pairs from the chips up to
the connector at y 34…58, about 25–35 mm over an unbroken ground plane, which
do not care.

### 6.3 What the flat board buys over rev C

| | rev C | rev D |
|---|---|---|
| Connectors for 12+ pairs | 3 × mini HDMI | **1** |
| Boot envelope required | 3 × 17.4 = 52.1 mm | **25.95 mm** |
| Upright riser section | required, 8–28 mm tall, right-angle soldered joint | **none** |
| Socket shell centre height | 22.0 mm | ~17.6 mm, and the board is flat |
| Insertion force | 44.1 N at a 22 mm shell height = 970 N·mm of tipping moment | **55.5 N** at a ~2.6 mm shell height, near zero moment |
| Designs to fabricate | 2, plus a panel | **1** |
| Mating cycles | 10,000 (HDMI) | **250 minimum** (Amphenol U10 series) |

That last row is the one real regression and the owner should know it in
advance: SlimSAS is a server-internal connector. 250 cycles is about one
insertion a week for five years, which is almost certainly fine for a radio,
but it is not a consumer port.

### 6.4 The land pattern, and the one dimension nobody publishes

Amphenol publish no recommended land pattern for U10A474240T and their
datasheet server refuses automated fetching, so the footprint is built from the
governing specification's own informative footprint: **SFF-8654 Rev 1.2 Figure
A-1 and Table A-1, "8X RIGHT ANGLE RECEPTACLE FOOTPRINT DIMENSIONS"**. Every
designator J01 to J12 is transcribed in the `SLIMSAS` block in
`tools/gen_gowin_bridge.py`, and `tools/check_geometry.py` recomputes all 78
pads from those twelve numbers independently and compares. Cross-checked
against **Foxconn customer drawing 303-0000-3299 sheet 4/5**, the "RECOMMEND
PCB LAYOUT" view for the 38-position sibling of the same LDL family, which
prints the identical construction and confirms that the shell tails sit
*outside* the locating holes and on the opposite side of the datum line from
the contacts.

**The one dimension that is in no document I could read** is the distance from
the locating-hole datum line to the front face of the latch shroud — i.e. how
far back the footprint must sit for the mating face to be flush with the panel.
Derived instead: the footprint spans 9.10 mm on the shell-tail side and 5.70 mm
on the pad side, 14.80 mm total, against a 15.80 mm body depth, so the body
overhangs the footprint by about 1.00 mm and the front face is about 10.10 mm
ahead of the datum. **The setback is set to 10.40 mm**, which puts the nominal
front face 0.30 mm behind the board edge and leaves 1.75 mm of copper-to-edge
clearance on the shell-tail pads. A 0.5 mm error here is absorbed by the panel
window, which is clearance-only and which the owner cuts himself — but
**check it against Amphenol's drawing before cutting the panel.**

---

## 7. Parts sourcing

**Every number was checked against a live LCSC page and against JLCPCB's
assembly library.** Seventeen part numbers are placed; eleven are Basic and six
are Extended.

| Function | Part | LCSC | Tier | Qty | $ @10 |
|---|---|---|---|---|---|
| SlimSAS 8i receptacle | Amphenol ICC U10A474240T | **C5432262** | Extended | 1 | 3.17 |
| Quad LVDS driver | DS90LV047ATMX/NOPB, SOIC-16 | **C206491** | Extended | 2 | 1.84 |
| Quad LVDS receiver | DS90LV048ATMTCX/NOPB, TSSOP-16 | **C87137** | Extended | 2 | 1.43 |
| Translator / buffer, **the only logic part number** | SN74AVC4T245PWR, TSSOP-16 | **C81461** | Extended | 7 | 0.3096 |
| ESD array, 0.5 pF | TPD4E05U06DQAR, USON-10 | **C138714** | Extended | 12 | 0.0698 |
| 2.5 V LDO | ME6211C25M5G-N, SOT-23-5 | **C194395** | Extended | 1 | 0.0561 |
| Ferrite bead | BLM18PG121SN1D, 0603 | **C14709** | **Basic** | 1 + 1 DNP | 0.0159 |
| 100 nF 0402 | | **C1525** | Basic | 22 | 0.0046 |
| 10 kΩ 0402 | | **C25744** | Basic | 18 | 0.0031 |
| 100 Ω 0402 | | **C25076** | Basic | 9 | 0.0037 |
| 330 Ω 0402 | | **C25104** | Basic | 8 | 0.0044 |
| 0 Ω 0402 | | **C17168** | Basic | 7 + 3 DNP | 0.0028 |
| 10 µF 25 V 0805 | CL21A106KAYNNNE | **C15850** | Basic | 3 | 0.085 |
| 470 Ω 0402 | | **C25117** | Basic | 1 | 0.0027 |
| 1 kΩ 0402 | | **C11702** | Basic | 1 + 1 DNP | 0.0022 |
| 1 µF 0402 | | **C52923** | Basic | 1 | 0.0097 |
| 0 Ω 0805 | 0805W8F0000T5E | **C17477** | Basic | 1 | 0.0045 |

**One part number for all seven translators and buffers, and that is a money
decision, not an aesthetic one.** JLCPCB's assembly library contains **no
Basic-tier buffer, driver, receiver or transceiver of any family from any
manufacturer** — the whole 244 octal family, the 125 and 126 quad families and
the entire Buffers/Drivers/Receivers category were swept, and the complete
Basic logic range turns out to be two chips: a hex Schmitt inverter and a shift
register. So every extra logic part number costs its own $3.07. Seven
SN74AVC4T245 cost **one** fee and $2.17 of silicon; a 74LVC244 plus a 74LVC125
would have cost **two** fees and $0.30 of silicon — $6.14 against $2.17.

**And no Basic quad LVDS part exists either.** 72 distinct LVDS driver and
receiver parts in JLCPCB's library, every one Extended, none even Preferred
Extended, and the Chinese brands hoped for (3PEAK, SGMICRO, Runic, Chipanalog,
Novosense, HGSEMI, Techcode, Belling, Shouding) carry no quad LVDS parts at
all. So C206491 and C87137 stay. One saving available and not taken:
**C87097**, the same DS90LV047A silicon in TSSOP-16 instead of SOIC-16, is
$0.43 cheaper each — $0.86 a board. SOIC-16 was kept for its thermal margin
(the drivers dissipate the most on the board) and its higher stock.

**The four parts the owner solders himself**, hand-fitted and not on the
assembly BOM, because every through-hole part is a distinct Extended part number
to JLCPCB:

| | Part | LCSC |
|---|---|---|
| DB1 2×10 female socket, bottom side | JXTCONN PM2.54-2X10P-H85 | C42431860 |
| DB12 2×3 female socket, bottom side | **LCSC has no vertical 2×3 socket at all** — their vertical female headers start at 2×4, and the 2×3 they list (C99515) is side entry, which cannot work on a socket that plugs straight down. Buy a 2×4 and cut it down | — |
| CN1 2×5 female socket, bottom side | PM254V-12-10P-H85 | C492399 |
| JTAG pass-through 2×5 male header, top side | PZ254V-12-10P, or DC3-2.54-10PAS (C2977596) for a keyed boxed header | C492422 |
| Ground clip 1×2 header | hanxia PH254 | C52016390 |
| **and the connector's four 2.2 mm shell tails**, which are through-hole on an otherwise SMD part | | |

---

## 8. The JTAG tap: series resistors or a buffer?

**Both, and the buffer is the part that matters.** The question was whether a
locally plugged USB Blaster and the remote path can fight.

**Series resistors alone are not enough.** They bound the current, but they
leave the logic level undefined, and an undefined TCK is exactly the thing that
can walk a TAP controller into an arbitrary state or corrupt a configuration in
progress. A gated buffer makes "the cable cannot touch CN1" a property of the
hardware rather than of the owner's memory:

| Line | Path | Gating |
|---|---|---|
| TCK, TMS, TDI | cable → **gated buffer** → 330 Ω → CN1 | OE* = `JTAG_EN_N`, pulled up at both ends, so **disabled with no gateware and with nothing plugged in** |
| TDO | CN1 → 330 Ω → **buffer input** (high impedance) → cable | always on; reading TDO cannot fight the FPGA that drives it, and the cable never loads the FPGA pin |

So a USB Blaster in the local pass-through meets **a tri-stated output**, not a
driver, unless the gateware has deliberately enabled the remote path — and you
would only do that with no Blaster plugged in.

**The series resistors are still there and still earn their place:** 330 Ω
bounds a fight to about 8 mA if the enable is left on while a Blaster is
plugged in, and 330 Ω into the ~15 pF of CN1 plus trace is **5 ns** against the
**41.7 ns** period of a 24 MHz TCK, or 167 ns at the Blaster's 6 MHz default.
`HL2_MECHANICAL_ENVELOPE.md` §12.3's arithmetic still applies: the whole added
electrical length is worth 0.085 ns, which is 0.2 % of a TCK period, and the
Blaster's own 150–300 mm ribbon is a far larger discontinuity than anything
this board adds.

**Radio-to-radio is covered structurally, not by the enable.** Two sideband
positions are deliberately undriven so that no radio can reach another radio's
TCK or TMS at all. `PINMAP.md` §6.2 has the table and the proof, and
`check_netlist.py` asserts it.

**The tolerance warning, which is the real risk here.** J4 is the third rigid
2.54 mm socket on one board, 54.19 mm from DB1, and
`HL2_MECHANICAL_ENVELOPE.md` §12.2 puts the worst-case misalignment at CN1
relative to DB1 at about **±0.8 mm** against the **±0.35 mm** a 2.54 mm socket
takes comfortably and ±0.6 mm before pins bend. That analysis is unchanged and
it is a coin toss on a hand-soldered radio. **The fallback needs no board
change: leave J4 off and run a flying 10-way IDC ribbon from CN1 to J5**, which
carries the same ten nets. A flying ribbon absorbs any misalignment, and it is
what §12.2 recommends.

---

## 9. Deliberate departures from the brief

| Brief said | What was done | Why |
|---|---|---|
| the duplicate forward clock on a spare channel of the **same** driver chip | on the second driver, U5 channel 1 | a quad driver has four channels and the forward group is five signals. `PINMAP.md` §5.2 |
| JTAG on pairs 14–16 plus one more | JTAG on four **sideband** conductors | under the function-mirroring rule the 16 pairs are exactly eight mirrored full-duplex lanes, and seven are spoken for. JTAG's four lines do not fit, and at 24 MHz maximum a single-ended sideband is trivially adequate |
| FPGA pin 72 unused, so J25 need not be soldered | pin 72 carries a DC enable level | soldering J25 stays **optional**: leave it open and the AUXIO drive feature simply does not exist. `PINMAP.md` §8 |
| pins 90, 91, 103, 104 are "the four indicator LED pins" | the mechanism is built on those four pins, but they are CW/PTT and the clock-generator I2C bus | the LEDs are on pins 98–101, which the link already owns. `PINMAP.md` §7 |
| bidirectional translator channels with direction control | two one-way paths with an enable on the DRIVE path only | the READ path then physically cannot drive an HL2 pin, and there is no direction net whose halves could disagree |
| the Gowin end on J14 with 16 pairs | 14 pairs; the spare lane and the AUXIO lines are not wired at the Gowin end | the 40 mm case position puts J14 positions 1-4 under the connector, leaving 34 pins. §11.5 |
| a 7 mm or lower J14 stack | 7.5 mm as built, 7.0 mm with the header insulator removed | no stocked square-pin pair is lower. §11.4 |

---

## 10. Everything unverified, in one list

The ones that could stop the build are first.

| Item | Why it matters | How to settle it |
|---|---|---|
| **The cable's pin wiring** | The whole one-design argument rests on the A(n)↔B(n) crossover, and 10Gtek publish no wiring diagram for this part — not the product page, not the catalogue, not the datasheet. It is inferred from SFF-9402 plus two third-party drawings | **Ohmmeter the first cable.** Five minutes. Confirm a row A contact reaches the other row, same number, at the far end |
| **The connector's front-face setback** | The one land-pattern dimension in no readable document. 10.40 mm is derived, ±0.5 mm | Open Amphenol's drawing for U10A474240T, or measure a part. Then cut the panel window |
| **M2: the 3.5 mm KEY jack's height** | It sits under the board at HL2 x 70.20–82.10, y 124.00–136.00, i.e. under the connector's y span. Expected 6–10 mm against an 11.04 mm underside | Callipers, with and without a plug fitted |
| **M3: the clock SMAs' height** | Under the board at x 74.04–78.24, y 103.36–123.60. Expected 3–8 mm | Callipers. First just look: are there two coaxial connectors on that face? |
| **HL2 R17** | 100 Ω between the DB12 pin 5 and pin 6 nets; if fitted it shorts the auxiliary clock input to the reverse clock input. Not populated on the owner's radio | Look at the radio before plugging this in |
| **The +3V3 spare current** | The 450 mA existing load is a bottom-up estimate whose four largest terms are guesses. The conclusion (350 mA is a third of the spare) is robust even at the pessimistic end, but the number is not measured | Measure the radio's 3.3 V rail current with and without the board |
| **The 2.5 V spare current** | Every component of the 75 mA existing estimate is a guess, which is precisely why the board makes its own 2.5 V rather than relying on it | Measure Vlvds under load before ever fitting SL_VLVDS |
| **Whether the Cyclone IV C8 fabric can capture 307.2 Mbit/s DDR** | Gates every received lane. One input register per IOE, so DDR input needs soft logic at 153.6 MHz | Timing closure in Quartus, then a bench measurement |
| **The three-socket tolerance stack** | ±0.8 mm worst case at CN1 against ±0.35 mm comfortable | Print `templates/bridge-1to1-TOP-fit-check.pdf` at 100 %, measure its rule, offer it up. The fallback is the flying ribbon |
| **The cable's shield stack-up** | Confirmed twinax; the layer-by-layer construction is not confirmable from any openable document | Ask 10Gtek, or cut one open. Only matters for a formal EMC case |
| **The A1 end of the connector** | Which physical end carries contact A1 is not stated in anything readable | It cannot scrap the board — `PINMAP.md` §1.1 — but knowing it saves a gateware polarity inversion |
| **The exact assembly fee** | JLCPCB will not compute the solder-joint fee without a login and an uploaded position file, and two of their own pages disagree on the setup fee ($8.18 vs $8.00) and the per-joint rate ($0.0016 vs $0.0017) | Upload and look. It is a few dollars |
| **The Gowin-end M3 spacer** | Its hole is under the connector housing and 0.66 mm from the connector's locating-peg hole, so the spacer must be fixed from below and must fit a 3.2 mm hole | Choose the part before ordering. §11.3 |
| **Dock coordinates on rev 31005** | Every Gowin-end position comes from Sipeed's interactive BOM for dock rev 31004 | Measure J14 pin 1 and hole H7_LU1 on the dock in hand, or offer up the 1:1 template |
| **C55160396 stock** | The only 5.0 mm 2×18 socket found for the scheme 1 stack; 10 in stock | Buy early. §11.4 |
| **Gowin on-die termination at VCCIO 3.3 V** | Documented for the bottom banks with no voltage restriction, accepted by Gowin EDA, not yet measured | Seven not-fitted 100 Ω footprints are on the Gowin end as the fallback |

---

## 11. The Gowin end

The far end of the same design, on the Sipeed Tang Mega 138K dock. It is on the
same schematic, the same PCB and the same panel as the radio end, and is
snapped off it. `PINMAP.md` §11 is its pin contract; this is the reasoning.

### 11.1 The question that set the cost: can Bank 4 do LVDS at 3.3 V?

**Yes, in both directions, with no parts.**

| Step | Finding | Source |
|---|---|---|
| What bank is J14 | Bank 4, a bottom bank | dock schematic net labels `BANK4_<ball>_<IO>`; `TANG_MEGA_138K_FACTS.md` §2.5 |
| Its VCCIO | **3.3 V**, generated on the SOM, fed through a filter and the board-to-board connector to VCCIO2/3/4/5 together. No jumper, no regulator option on the dock except an unfitted resistor from a dock 1.8 V rail | dock schematic **sheet 2/21, PWR_TREE** |
| LVDS output at 3.3 V | **Allowed.** LVDS25, "Differential (TLVDS)", Bank VCCIO **2.5/3.3**, drive 3.5/2.5/4.5/6 mA | Gowin **DS1239** 1.0.3E §2.3.1 **Table 2-1** |
| …and not only a table header | LVDS25 appears twice in the output VCCIO table: 2.375–2.625 V and **3.135–3.465 V** | DS1239 §3.2.3 **Table 3-10** |
| On which pins | All 143 differential pairs of the PG484A package are True LVDS Output | Gowin **UG1102** 1.0.8E §2.4.1 **Table 2-3** |
| LVDS input at 3.3 V | Allowed, VCCIO 1.0–3.3 V | DS1239 **Table 2-2**; UG304 1.3.8E §3.1 |
| Input termination | 100 Ω on-die, bottom banks of the 138K | UG304 §3.3.2; DS1239 §3.2.1 Table 3-8 note 1 |
| **The tool agrees** | Gowin EDA 1.9.11.03 Education, device GW5AST-LV138PG484AC1/I0, placed, routed and wrote a bitstream for the final pin map: LVDS25 inputs with Diff Resistor ON, LVDS25 outputs at 3.5 mA, BANK_VCCIO 3.3, no errors | run on this machine, 13 Sep 2026 |
| Corroboration | Sipeed's own HDMI transmitter on the same dock drives true LVDS pairs from 3.3 V Bank 3 at `DRIVE=3.5` | `tang_mega_138K_pins.cst` |

**So J13 and the "change Bank 4's VCCIO" options were not needed** and were
not pursued. Bank 2 (J13) would in any case have been worse: no on-die
termination, and it shares its bank with the Ethernet RGMII bus.

**Electrical compatibility with the radio end.** The Gowin LVDS25 output is
VOD 250–600 mV at VOS 1.000–1.425 V into 100 Ω (DS1239 Table 3-12); the radio
end's DS90LV048A accepts any differential input over 100 mV. The radio end's
DS90LV047A drives 250–450 mV at 1.125–1.375 V; the Gowin input threshold is
±100 mV. Both ends are DC-coupled and share ground through the cable's 26
ground conductors.

**What one tool run found that no document said.** Bank 4 is also the CPU and
SSPI configuration bank. Gowin EDA refuses five of the chosen balls unless the
project sets `-use_sspi_as_gpio 1` and `-use_cpu_as_gpio 1`. TCK is on N15,
the one chosen ball with no configuration function at all.

### 11.2 What is on the Gowin end

| Part | Qty | LCSC | Tier | Why |
|---|---|---|---|---|
| SlimSAS 8i receptacle | 1 | C5432262 | Extended, **already paid for by the radio end** | same part both ends |
| TPD4E05U06 ESD array | 12 | C138714 | Extended, **already paid for** | every one of the 48 conductors |
| 330 Ω 0402 | 4 | C25104 | Basic | TCK, TMS, TDI, TDO series |
| 1 kΩ 0402 | 3 | C11702 | Basic | presence out and in series, TCK pull-down |
| 10 kΩ 0402 | 2 | C25744 | Basic | presence and TDO pull-downs |
| 0 Ω 0805 | 1 | C17477 | Basic | shell to ground |
| 100 Ω 0402, **not fitted** | 7 | C25076 | — | optional external termination per received pair |
| 2×18 socket or header | 1 | see §11.4 | hand-fitted | onto J14 positions 5–40 |

**No new part number.** Every factory-placed part number on the Gowin end is
already on the radio end, so the Gowin end adds **no** $3.07 Extended-part
fee. Components come to **$4.04 per Gowin end**, $3.17 of it the connector.

### 11.3 Position: the 40 mm case position, which also serves the bench

From `franz-claude-analysis/TANG_IN_40MM_CASE.md`, in Sipeed's dock
board-file coordinates:

| | Dock coordinates | Why |
|---|---|---|
| SlimSAS mating face | **x 89.73**, facing the dock's short (Ethernet) edge | flush with the dock RJ45 face; both leave through the front panel |
| SlimSAS centreline | **y 53.73** | 10.11 mm from J14 pin 1 toward the PMOD edge |
| Board | x 89.43–153.93, y 41.17–66.29 = **64.50 × 25.12 mm** | 64.50 long so it shares a straight V-score with the radio end; 25.12 wide is the minimum that keeps both rows of shell-tail pads 0.30 mm inside the edges; y ≤ 66.5 keeps clear of the USB3 bridge and the core module |
| HDMI notch | x ≥ 148.50, y ≤ 57.50 removed | a cable can stay in the dock's HDMI socket J29 |
| M3 spacer hole | (97.67, 62.66), over dock corner hole H7_LU1 | the connector takes 55.5 N on insertion |
| J14 | positions 5–40 only | positions 1 and 2 are under the contact field, 3 and 4 under the housing |

**Two things the case position forces that the owner should know.**

1. **The spacer hole is under the connector housing.** Nothing can be
   screwed into it from above. The spacer has to be fixed to the adapter from
   below (a surface-mount threaded spacer, or a standoff bonded in place) and
   the screw comes up from under the carrier plate or case floor. The hole is
   0.66 mm from the connector's own locating-peg hole, so a spacer that needs a
   mounting hole larger than 3.2 mm will not fit; the common PEM-style SMT
   spacers want 4.2 mm. **Choose the spacer before ordering.** The hole is part
   of the Gowin end's copy of the connector land pattern, which is why DRC
   accepts a hole inside the connector's outline.
2. **The J14 PMOD pins, the camera and the two PMOD sockets are unusable**
   while the adapter is fitted: J14 positions 5–8 are PMOD0, 21–28 are PMOD1
   and the camera. In scheme 1 the adapter underside clears PMOD socket J9 by
   about 0.6 mm (its 6.4 mm height is an estimate).

**Height.** The tallest thing on the adapter is the SlimSAS at 9.90 mm. In
scheme 1 the seat is 8.6 mm (7.0 mm stack) or 9.1 mm (7.5 mm stack) above the
dock, so the connector top is at case height 33.3 or 33.8 mm against the
study's worst-case 36.9 mm ceiling: 3.6 or 3.1 mm spare. **The 7.5 mm stack
lowers nothing but moves the plug 0.5 mm up against a front-panel window with
0.3 mm of clearance: if the insulator is left on, the window must move up
0.5 mm.** In scheme 1 the upside-down header's 6.0 mm ends stand 4.4 mm above
the adapter before clipping, beside the connector, not over it.

### 11.4 The stack, and the search for a 7 mm one

A standard 2.54 mm male header plus female socket is 11.0 mm. LCSC was
searched for anything lower in 2×18 or 2×20:

| Candidate | Height | Stock | Verdict |
|---|---|---|---|
| **kinghelm KH-2.54FH-2X18P-H5.0, C55160396** | 5.0 mm female, square hole | **10** | **chosen for scheme 1**, with C41376109 upside down |
| chxunda XDM254C-2-18-Z-3.0-G0, C19184331 | 3.0 mm machined round-hole female | 66 | accepts only 0.40–0.60 mm round pins; no stocked 2×18 round-pin male found to mate it |
| XKB X5521FV-2x18-C70D30, C2682207 | 7.0 mm round-hole female | 170 | same round-pin problem, and 7.0 mm on its own |
| every 8.5 mm 2×18 female | 8.5 mm | thousands | scheme 2 |

**Scheme 1 is 7.5 mm as built, or 7.0 mm with the header insulator slid off**
and the spacer setting the height. **C55160396 has only 10 in stock: buy them
now if scheme 1 is chosen.**

### 11.5 The sidebands, and JTAG driven from this end

J14 has 38 usable pins; positions 1–4 remove four. Fourteen pairs take 28. The
remaining six carry presence in, presence out/link reset, TCK, TMS, TDI and
TDO. **The spare lane and the four AUXIO lines are not wired at this end** —
PINMAP.md §11.4 explains why nothing that works today is lost.

| Property the radio end has | Kept at the Gowin end by |
|---|---|
| Radio-to-radio cannot touch programming pins | untouched: the radio end still leaves A9 and A29 undriven |
| JTAG disabled at power-up by a pull resistor | the radio end's gated buffer and its pull-ups still decide; the Gowin can drive TCK/TMS/TDI but they reach the radio's CN1 only once the radio enables the path |
| No TCK edge from an unconfigured controller | **R105, 1 kΩ to ground on the FPGA side of TCK**: against the Gowin's strongest 400 µA configuration pull-up it holds 0.4 V |
| A fight is bounded | 330 Ω in every JTAG line at this end too |
| Unpowered end does not back-feed | 1 k in the presence input and 330 Ω in TDO limit injection into an unpowered FPGA |

**Presence here is driven by the gateware** because J14 has no 3.3 V pin:
HIGH through 1 k is present, LOW is link reset. The radio end only uses its
presence input for the optional driver-gating link, so an unconfigured Gowin
reading as absent is harmless.

### 11.6 One design on one panel

| | |
|---|---|
| Panel | **64.50 × 100.07 mm**, 4 layer, 1.6 mm |
| Top to bottom | 5.00 mm rail, V-score, Gowin end 25.12 mm, V-score, radio end 64.95 mm, V-score, 5.00 mm rail |
| Connectors | both on the panel's left edge, which is a routed outer edge, so no score runs under a connector housing |
| Scores crossing air | y 5.00 over the 3.4 mm HDMI notch at the right edge; y 95.07 over the radio end's 3.4 mm M3 notch |
| Electrical separation | every Gowin-end net is prefixed `G_`; `check_netlist.py` asserts that no net touches both ends; ground pours are per end |
| Designators | radio end as before; Gowin end numbered from 101 (J101, J102, D101–D112, R101–R117, TP101–TP121) |

**A pre-existing bug fixed on the way.** The committed rev D BOM carried two
R1s and two R2s: the generator named the forward-clock divider R1/R2 by hand
and also handed out R1 and R2 automatically to two 330 Ω AUXIO resistors.
JLCPCB's placement file cannot hold duplicate designators. The automatic
numbering now skips R1 and R2, so every automatically numbered radio-end
resistor moved up by two; no net changed.
