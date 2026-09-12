# gowin-bridge design notes — rev B

Assumptions, calculations, decisions and everything unverified. Read with
`PINMAP.md` (what connects to what), `ROUTING.md` (how to route it) and
`README.md` (how to build and order it).

Revision **B**, 2026-09-12. rev A used two dual-link DVI-D sockets per board;
rev B uses three HDMI sockets per board and makes the HL2-side board symmetric.

---

## 1. Data rates and unit intervals

| Signal | Where | Rate | Unit interval |
|---|---|---|---|
| Forward clock A | `OUT 1` / `IN 1` TMDS clock pair | 76.8 MHz | 13.02 ns period |
| Forward clock B | `OUT 2` / `IN 2` TMDS clock pair | 76.8 MHz | 13.02 ns period |
| Forward lanes 0-5 | 3 pairs per forward cable | 153.6 Mbit/s each (DDR against 76.8 MHz) | **6.51 ns** |
| Reverse clock | `OUT` / `IN` TMDS clock pair | 153.6 MHz | 6.51 ns period |
| Reverse lanes 0-2 | 3 pairs | 307.2 Mbit/s each | **3.26 ns** |
| Slow out (status UART) | `OUT 1` SCL, single-ended | 115200 8N1, up to ~3 Mbaud | >= 333 ns |
| Slow in (command channel) | `IN` SCL, single-ended | **~10-25 Mbit/s ceiling** | >= 40 ns |
| Cable detect | HPD on every socket | DC | - |

6 lanes x 153.6 Mbit/s = 921.6 Mbit/s = 12 bits x 76.8 MSPS: the whole ADC
stream, no compression, no framing overhead. The reverse direction carries the
same 921.6 Mbit/s on three lanes at double the rate.

The DS90LV047A / DS90LV048A pair is rated **400 Mbit/s** per channel, so the
worst case (307.2 Mbit/s) uses 77 % of the rating and the forward lanes use
38 %. The Gowin `IDDR` gearbox limit is 400 Mbit/s and `IDES4` is 800 Mbit/s.

### 1.1 What rev B gave up to gain the second clock

rev A put the reverse command channel on a shielded 100 ohm differential pair
at 307.2 Mbit/s. In rev B it is a **single-ended, unterminated, unshielded
conductor inside an HDMI cable** (the SCL wire), because an HDMI cable has four
pairs, not seven, and all four are needed for clock plus three data lanes.

The ceiling is **10 to 25 Mbit/s** and that is reasoning, not measurement. The
wire is roughly 100 ohm and unterminated at both ends, so every edge rings for
several round trips; at about 5 ns per metre each way, a 2 m cable rings for
roughly 20 ns before the reflections have decayed usefully, which puts a floor
of order 40 ns per bit. **Measure it on the bench before any gateware relies on
a number.** The `CMD_UART = 1` bring-up option (115200 8N1) is unaffected.

What was bought with that loss: **each forward cable now carries its own copy
of the 76.8 MHz clock**, so each cable is self-timed and the two cables'
unequal electrical length stops mattering. With one clock shared across two
cables, any difference in cable length would appear directly as clock-to-data
skew on the far cable's three lanes, and the user buys the cables.

---

## 2. Termination, edge rates and the two tight paths

* **Every LVDS receiver input pair gets a 100 ohm resistor on the board**,
  within 5 mm of the receiver pins. Board A has four, board B has eight. There
  is no termination at a driver output, which is correct for LVDS.
* **LVDS differential swing** 250-450 mV (DS90LV047A `VOD1` into 100 ohm),
  common mode 1.125-1.375 V, transition about 1 ns. At 307.2 Mbit/s the edge
  occupies 30 % of a unit interval.
* **Cable.** An HDMI cable is 100 ohm differential, individually shielded per
  pair, and qualified far above these rates - even HDMI 1.0 runs 1.65 Gbit/s
  per pair. Cable length is not an electrical limit here; the 400 Mbit/s driver
  rating is. Anything up to a few metres is fine.
* **Every single-ended run is under 25 mm** by layout rule, with a series
  resistor where one is useful.

### 2.1 Tight path one: the three reverse lanes into the HL2's LED pins

Reverse lanes 0-2 land on **DB1 pins 11, 15 and 17 at 307.2 Mbit/s**, and each
of those FPGA pins carries an LED whose anode goes through 1 k to **+3V3**
(verified in `hermeslite.net`: D3/R72, D4/R73, D5/R74, all 1K).

* The LED's junction capacitance (20-50 pF) is **in series with the 1 k**, so at
  150 MHz the branch looks like 1 k resistive, not capacitive - the LED does not
  load the edge. What loads it is the FPGA pin itself (7 pF for a right-side
  Cyclone IV pin) plus the header and trace, roughly 12-15 pF.
* A 3.3 V CMOS output with about 50 ohm of effective source impedance into
  15 pF gives a 10-90 % rise of about **1.65 ns, which is 51 % of the 3.26 ns
  unit interval.** That works, and it is the tightest margin on either board.
* The receiver must also **sink 1.4 mA** when low ((3.3 - 1.9) / 1000).
  DS90LV048A specifies `VOL` <= 0.3 V at 2 mA, so it is inside spec.
* The series parts are **0 ohm by default** on 0402 pads, so a damping value can
  be substituted without a respin - but do not raise them much: at 22 ohm the
  rise grows to about 1.9 ns.

**Unverified:** whether the Cyclone IV C8 fabric can actually capture
307.2 Mbit/s DDR on ordinary bank-6 inputs. The device has one input register
per IOE, so DDR input needs soft logic clocked at 153.6 MHz. Gateware problem,
but it gates the reverse link.

### 2.2 Tight path two: forward lane 3 on PIN_80, the 21 pF VREF pin

**HL2 PIN_80 (DB1 pin 4) is `VREFB5N0`**, and a Cyclone IV VREF pin carries
about **21 pF** of pin capacitance rather than the usual 7 pF - three times the
load of its neighbours.

* At 153.6 Mbit/s (6.51 ns UI) a 2.5 V output with ~50 ohm of source impedance
  into 21 pF plus ~6 pF of trace and header gives a 10-90 % rise of about
  **2.97 ns, which is 46 % of the unit interval.** Comparable to section 2.1,
  and acceptable, but it is the slowest of the six forward lanes.
* **Consequence for the layout: keep the trace from DB1 pin 4 to U1's A-side
  input as short as physically possible.** It is the one single-ended net on
  board A where every millimetre counts; the other six have three times the
  margin. The generated placement puts U1 about 19 mm from DB1, which is inside
  the 25 mm rule, but PIN_80 should get the shortest of the seven.
* Per-lane delay is not a problem - the Gowin's `IODELAY` centres each lane's
  eye independently (section 4.2 of `ROUTING.md`). What the extra capacitance
  costs is **eye width**, not position, and that the sweep cannot recover.
* The 3-lane fallback geometry in `LINK_SPEC.md` does not use PIN_80 at all, so
  if lane 3 is the one that fails, that fallback is the escape.

---

## 3. The 2.5 V / 3.3 V level cases

### 3.1 The problem, stated with the numbers

| | Value | Source |
|---|---|---|
| Cyclone IV 2.5 V LVCMOS output, `VOH` min | **2.0 V** at `IOH` = -1 mA | Cyclone IV Device Datasheet, Table 1-15 |
| DS90LV047A input `VIH` min | **2.0 V** | TI SNLS044D, Electrical Characteristics |
| **Guaranteed margin** | **0 mV** | |

**Eight of board A's nine HL2 outputs are on a 2.5 V bank** (PIN_72, 76, 77,
80, 83, 85, 86, 87; only PIN_98 is 3.3 V), and seven of those eight feed an
LVDS driver input. So this is not an edge case, it is the main signal path.

Four candidate resolutions were considered. The brief asked for one to be
chosen and justified.

**(a) An LVDS driver with LVTTL-specified inputs, `VIH` min 1.7 V.**
Rejected: no such part was found. `VIH` = 2.0 V is the TTL threshold and it is
what every discrete LVDS driver in the LCSC catalogue specifies - DS90LV047A,
SN65LVDS047, SN65LVDS31, DS90LV031A, ADN4667 are all 2.0 V. The 1.7 V figure
is the *FPGA* `3.3-V LVTTL` I/O standard, not a logic-family spec; it is
available on the Gowin side (section 3.5) but not in a driver chip.

**(b) An LVDS driver specified for a 2.5 V supply.** Rejected: no quad LVDS
driver in the catalogue operates below 3.0 V. DS90LV047A, SN65LVDS047,
SN65LVDS9637 and DS90LV031A are all specified 3.0-3.6 V. Running one at 2.5 V
is out of spec, and its `VOD` and common-mode output would both move.

**(c) A dual-supply translator in front of the drivers.** **CHOSEN.** Section
3.2.

**(d) Argue that `VOH` approaches `VCCIO` at microamp load.** Kept as the
documented fallback, section 3.3, with bypass links fitted for it - but not the
default, because it is an unguaranteed practical argument and the brief asked
to prefer (a) or (c).

### 3.2 The chosen solution: one SN74AVC8T245, and what it costs

**U1 on board A is an SN74AVC8T245PW (TSSOP-24, LCSC C53535), `VCCA` = 2.5 V,
`VCCB` = 3.3 V, `DIR` tied to `VCCA` (A to B), `OE` low.**

| | Value |
|---|---|
| A-side `VIH` min | **0.65 x VCCA = 1.63 V** |
| Cyclone IV 2.5 V `VOH` min | 2.0 V |
| **Guaranteed margin** | **370 mV**, up from 0 mV |
| B-side output | 3.3 V CMOS, straight into the driver's 2.0 V threshold with 1.3 V of margin |
| Rated data rate | 380 Mbit/s at these rails; the fastest signal through it is 153.6 Mbit/s, i.e. **40 % of rating** |
| Propagation delay | about 1.1 to 3.7 ns over process and temperature |
| Channel-to-channel skew within one package | about 0.5 ns |

**All eight forward signals go through this one package.** That is the whole
reason it is an 8-bit part and not two 4-bit parts: propagation delay is a
part-to-part property, so putting clock and data in one package turns a 2.6 ns
part-to-part uncertainty into a 0.5 ns channel-to-channel one.

**Forward clock A is the awkward one.** PIN_98 is a 3.3 V output, and the
SN74AVC8T245's A-side absolute maximum is `VCCA` + 0.5 V = **3.0 V**. Feeding
it 3.3 V directly is out of spec. Two ways out, and the wrong one first:

* *Let clock A bypass the translator.* Rejected. The clock would then lead the
  data by the translator's whole 1.1-3.7 ns propagation delay, on a 6.51 ns
  unit interval - a displacement of 0.17 to 0.57 UI, uncertain by 2.6 ns. The
  Gowin's `IODELAY` sweep would still find an eye (it has 3.2 ns of range and a
  word aligner behind it), but it would spend most of its adjustment range
  undoing a fixed offset instead of holding it as margin.
* **Divide it down first. Chosen.** A 150 ohm / 470 ohm divider from PIN_98 to
  the translator's A-side input:

| | Calculation | Result |
|---|---|---|
| High level at the A input | 3.3 x 470 / (470 + 150 + 25) *(25 ohm = the FPGA output's own impedance)* | **2.40 V** |
| Margin over `VIH` 1.63 V | | **770 mV** |
| Headroom under the 3.0 V absolute maximum | | **600 mV** |
| Current drawn from PIN_98 when high | 3.3 / (470 + 150 + 25) | **5.1 mA**, inside the pin's 8 mA drive setting |
| Thevenin source impedance at the A input | 150 \|\| 470 | **113 ohm** |
| Rise-time contribution into the translator's ~4 pF input | 2.2 x 113 x 4p | **0.45 ns**, i.e. 3.5 % of the 13.02 ns clock period |
| Low level with the HL2 FPGA unconfigured *(the HL2's own LED pull-up: 1 k + LED forward drop through the divider)* | (3.3 - 1.7) x 470 / (1000 + 150 + 470) | **0.46 V**, under the 0.875 V `VIL` max |

So clock A and all six data lanes and clock B share one package, one
propagation delay and 0.5 ns of skew. That is what the second forward clock was
added for, and it would have been wasted if the clock took a different path
through the level shift than the data.

**Pull-downs.** The seven 2.5 V forward signals each get a 10 k pull-down so
they are defined while the HL2 FPGA is unconfigured. **Clock A deliberately
does not get one**: the HL2's own LED pull-up on DB1 pin 9 plus the divider
already define it at 0.46 V, and adding a 10 k pull-down to a net that already
has a 1 k pull-up through an LED would park it at about **1.45 V - squarely in
the translator's forbidden band** between `VIL` 0.875 V and `VIH` 1.63 V. That
is the kind of mistake that produces an oscillating input and 50 mA of supply
current, so it is called out here rather than left implicit.

### 3.3 The fallback, and why the bypass links exist

Eight DNP 0 ohm links (`SL_BYP1..8`) short each A-side net to its B-side net.
Fit all eight, remove U1 and remove the 470 ohm divider leg, and the HL2
outputs drive the LVDS drivers directly - which is argument (d):

| | Value |
|---|---|
| DS90LV047A input current | **-10 to +10 uA** max (`IIH`/`IIL`, SNLS044D) |
| Voltage on the line at that current | **>= 2.375 V** (`VCCIO5` min); 10 uA through a ~50 ohm source is 0.5 mV |
| **Actual margin against `VIH` 2.0 V** | **>= 375 mV** |

The 0 mV figure in section 3.1 is an artefact of comparing a `VOH` specified at
1 mA against a load that draws 10 uA. A 2.5 V CMOS output driving a 3.3 V LVDS
serialiser input is ordinary practice and it will almost certainly work.

**But it is unguaranteed**, and this is a board that plugs into someone's radio
and has to work on every HL2, at every temperature, with every Cyclone IV
process corner. The translator costs one package, 12 mA and 0.5 ns of skew.
Ship the translator; keep the links so that if the bench says the translator is
the problem, it can be removed in ten minutes.

### 3.4 3.3 V receiver output into the HL2's two input-only 2.5 V pins

HL2 **PIN_88** (DB12 pin 6, reverse clock, 153.6 MHz) and **PIN_89** (DB12
pin 5, slow in) are dedicated clock *inputs* in bank 5 at `VCCIO` 2.5 V. The
Cyclone IV handbook permits up to 3.6 V on any pin but warns of leakage above
`VCCIO`, and **the PCI clamp diode is on by default for a 2.5 V bank** - a
3.3 V driver held high would inject DC into the HL2's 2.5 V rail, which comes
from a TPS730 LDO through a ferrite. Not acceptable.

**U5, an SN74AVC4T245PW (LCSC C81461), `VCCA` = 3.3 V, `VCCB` = 2.5 V**, two
channels used. Kept unchanged from rev A and re-checked against the new rates:
the fastest signal through it is now the 153.6 MHz reverse clock (equivalent to
307.2 Mbit/s of toggling) against a 380 Mbit/s rating, i.e. **81 % of rating** -
the least comfortable margin in the design after sections 2.1 and 2.2, and
worth a scope check at bring-up. The slow-in channel is trivial.

A resistor divider was rejected on numbers, as in rev A: the DS90LV048A output
is specified only to `VOH` 2.7 V at **-0.4 mA** and `VOL` 0.3 V at **2 mA**, so
it cannot drive a low-impedance divider, and a divider light enough for it
(1 k / 3.3 k, Thevenin 767 ohm) into the pin's ~10 pF gives tau = 7.7 ns -
more than twice the 3.26 ns unit interval it has to resolve. Dead.

`R_SL_VLVDS` (not fitted) can tie U5's `VCCB` and U1's `VCCA` to the HL2's own
`Vlvds` rail on DB1 pins 7/8 instead of the on-board LDO. Electrically ideal -
the thresholds then track the FPGA's bank supply exactly - at the cost of about
10 mA from the HL2's TPS730, whose headroom is **unverified**. Hence the LDO as
default.

### 3.5 HL2 2.5 V output into a Gowin 3.3 V input (the slow out)

PIN_86's status UART goes straight down the cable to Gowin pin V20 with a
100 ohm series resistor and no buffer. The Gowin has the same 0 mV problem
(`LVCMOS33` `VIH` min 2.0 V), and here there *is* a free fix:
**`IO_TYPE=LVTTL33`** has `VIH` min 1.7 V, giving **300 mV of guaranteed
margin**. `PINMAP.md` 5.2 marks that pin `LVTTL33` and `HYSTERESIS=NONE` -
the Gowin's 400 mV of hysteresis at `VCCIO` 3.3 V is larger than the whole
margin and has to be switched off explicitly rather than left to the tool.

### 3.6 Board B needs none of this

The Gowin's Bank 4 is at 3.3 V and so are the drivers and receivers. Every
interface on board B is 3.3 V to 3.3 V. Driver inputs get a 22 ohm series
resistor and a 10 k pull-down; receiver outputs get 22 ohm into the J14 pin.

---

## 4. The AC-coupling option

Fitted as an **option, not fitted by default.** Every received pair carries,
per leg: a **100 nF 0402 series capacitor (DNP)** in parallel with a **0 ohm
0402 link (FITTED)**. Board A has four such pairs, board B eight.

To convert a pair to AC coupling: remove its two 0 ohm links, fit its two
100 nF capacitors, fit its two 4k7 bias resistors, and fit the shared `VBIAS`
divider (1k8 / 1k0 from +3V3 with a 100 nF bypass, one per receiver chip).

### 4.1 Why it is an option and not the default

**For:** coupling capacitors block any DC path between the two boards, so a
driver cannot be damaged by the far board being powered when this one is not,
or by a ground offset between a radio and a dev board on different supplies.
That is a real hazard in this application - the HL2 and the Tang dock have
separate power supplies and are joined only by cable shields.

**Against, and decisive:** AC coupling requires the data to be **DC balanced**,
and the current gateware does not guarantee it. `LINK_SPEC.md` section 5 is
explicit that its x^43 + 1 scrambler exists "to spread the spectrum of
near-static ADC data next to an HF receiver, not DC balance". A self-
synchronising scrambler bounds nothing: a run of identical bits long enough to
discharge the coupling network produces a baseline wander that closes the eye,
and with a quiet antenna the ADC output is nearly constant, which is exactly
the worst case.

So: provide the footprints and the links, default to DC, and let the option be
taken later - when either the gateware gains 8b/10b or a run-length-bounded
code, or a bench measurement shows the DC path is causing trouble.

### 4.2 Component values and what was assumed

**Coupling capacitor: 100 nF 0402 (X7R, 16 V or better).**

| | |
|---|---|
| Resistance each leg sees toward the termination | 50 ohm (half of the 100 ohm differential termination) |
| RC time constant | 100 nF x 50 ohm = **5 us** |
| Longest run length assumed tolerable | 5 identical bits = 32.5 ns at 153.6 Mbit/s |
| Droop over that run | 32.5 ns / 5 us = **0.65 %** of the 350 mV swing = 2.3 mV |
| Reactance at the lowest frequency of interest (153.6 Mbit/s / 10 = 15 MHz) | 1 / (2 pi x 15e6 x 100n) = **0.11 ohm**, negligible against 50 ohm |

100 nF is the standard LVDS AC-coupling value and the arithmetic above is why:
it is three orders of magnitude larger than the reactance requirement and the
limit is the run length, not the capacitor. **Raising it does not help** - a
1 ms burst of identical bits would droop completely through any capacitor that
fits on a 0402 pad. That is the point of section 4.1.

**Bias network: 1k8 / 1k0 divider, 4k7 per leg.**

| | |
|---|---|
| Target receiver common mode | 1.2 V (DS90LV048A accepts 0.05 to 2.35 V; 1.2 V is mid-range) |
| Divider | 1k8 from +3V3, 1k0 to GND -> 3.3 x 1.0 / 2.8 = **1.18 V** |
| Current in the divider | **1.18 mA** (which is why it is DNP: that is 1 % of the board's total) |
| Divider Thevenin impedance | 1k8 \|\| 1k0 = 643 ohm, bypassed with 100 nF |
| Bias resistor per leg | **4k7** |
| Effect on the differential impedance | 100 \|\| (2 x 4700) = **98.9 ohm**, a 1.1 % error |
| DC current through the termination | **zero** - both legs are biased equally, so the bias appears as pure common mode |

One `VBIAS` rail is shared by all of a receiver's pairs, which is why the
divider is one network per board rather than one per pair.

---

## 5. Power

### 5.1 Board A

| Load | Current at 3.3 V |
|---|---|
| U2, U3 DS90LV047A, all four channels driving 100 ohm (`ICCL` max 30 mA each) | 60 mA |
| U4 DS90LV048A (`ICC` max ~25 mA) | 25 mA |
| U1 SN74AVC8T245, eight channels switching into 5 pF at up to 76.8 MHz (`C x V x f` = 5p x 3.3 x 76.8M = 1.27 mA each) plus quiescent | 12 mA |
| U6 ME6211C25 LDO, output ~6 mA plus quiescent (feeds U1's A side and U5's B side) | 7 mA |
| U5 SN74AVC4T245, A side | 1 mA |
| Receiver outputs sinking the HL2's three LED pull-ups (1.4 mA each, average ~50 % duty) | 2 mA |
| Pull-ups, pull-downs, HPD dividers | 5 mA |
| **Total** | **~112 mA** |

Two extra loads on the HL2 that are **not** on board A's 3.3 V rail and are
easy to miss:

* **5.1 mA out of PIN_98** through the clock-A divider (section 3.2). Inside
  the pin's 8 mA drive setting, but it is 5 mA the HL2's +3V3 rail did not
  previously supply.
* **1.4 mA into each of DB1 pins 11, 15, 17** sunk by board A's receiver, which
  is current the HL2's own +3V3 rail sources through the LEDs.

**Supply: DB1 pins 19/20, the HL2's +3V3 rail, selected by header J6 (default
shunt on 1-2).**

`hardware/hl/Power.sch` shows +3V3 generated by a switching stage (a 3.3 uH
inductor network), not by the TPS730 - the TPS730 (U17) makes +2V5, from which
`Vlvds` and `Veth` are fed through ferrites FB28 and FB30. **The +3V3
regulator's part number and current rating were not identified, so the headroom
for another 112 mA is UNVERIFIED.** This is still the single most important
electrical unknown: measure the HL2's 3.3 V rail with board A plugged in before
trusting it.

**The alternative, and the decision not to make it the default.** The `IN`
socket's HDMI +5 V pin (pin 18) reaches an AMS1117-3.3 (U7) through the DNP
link `SL_5V`; move J6's shunt to 2-3 to use it. **U7 and `SL_5V` are both
not fitted by default**, deliberately:

* **In the two-radio configuration there is no Gowin and therefore no 5 V
  source at all**, so board A has to be able to run from its own HL2 anyway.
  A supply path that exists in only one of the two supported configurations is
  a trap, not a feature.
* If both radios in a two-radio pair had the 5 V links fitted, and board B's
  `SL_5V_OUT` were also fitted somewhere, two 5 V sources could end up tied
  together through a cable.

So: **board A's `OUT 1` and `OUT 2` sockets have +5 V not connected at all**
(the pin has no copper), the `IN` socket's +5 V pin goes to a test point and a
DNP link, and **board B's `OUT` socket has a DNP 0 ohm link (`SL_5V_OUT`) from
the dock's 5 V rail** so the path can be completed at both ends if the HL2's
3.3 V measurement disappoints. Both ends are DNP; fitting one without the other
does nothing, which is the safe failure mode.

### 5.2 Board B

| Load | Current at 3.3 V |
|---|---|
| U1, U2 DS90LV048A (`ICC` max ~25 mA each) | 50 mA |
| U3 DS90LV047A, four channels into 100 ohm | 30 mA |
| Eight receiver outputs into a Gowin pin (~8 pF) at up to 76.8 MHz | 16 mA |
| Driver input pull-downs, HPD pull-ups, odds and ends | 10 mA |
| **Total** | **~106 mA** |

From J14 pin 11 (`5V_Peripheral`) through **U4, an AMS1117-3.3 in SOT-223**.
Dissipation (5.0 - 3.3) x 0.106 = **0.18 W**, and **0.25 W** if every chip sits
at its datasheet maximum. Flood the tab to the layer-3 plane with at least six
0.3 mm thermal vias; that gives roughly a 30 degC rise, which is fine.

**How much current J14 pin 11 can actually supply is UNVERIFIED.** The dock is
fed from a 12 V barrel jack so 150 mA should be unremarkable, but no figure was
found in the Sipeed documentation.

---

## 6. Mechanical — and this is what rev B exists for

### 6.1 Why rev A did not fit, in one line

Two right-angle dual-link DVI-D receptacles are **37.83 mm wide each, so 76 mm
side by side**, and the corridor left by the N2ADR filter board is **50 mm**.
rev A's answer was an L-shaped 80 x 66 mm board with a tab overhanging the
filter board. rev B's answer is three mini HDMI sockets at **11.20 mm** each.

### 6.2 The corridor, and where board A sits in it

From `hardware/hl/hermeslite.kicad_pcb`, whose outline is x 70.00-169.95,
y 40.00-140.00 (a 100 x 100 mm board):

* `DB1` is footprint `HERMESLITE:10x2` at **(75.31, 89.39) rotated 270**. For
  270 degrees KiCad gives absolute = (module_x - pad_y, module_y + pad_x), so
  pin 1 (local -11.43, +1.27) lands at **(74.04, 77.96)** and pin 20 (local
  +11.43, -1.27) at **(76.58, 100.82)**. Odd pins at x 74.04, even at 76.58,
  pin 1 at the y = 40 end. Cross-checked two ways: the footprint's own pin-1
  silkscreen circle is at (72.61, 76.49), diagonally outboard of pin 1 at the
  low-x, low-y corner; and KiCad's `RotatePoint` gives the same answer.
* `DB12` is `HERMESLITE:3x2` at **(83.50, 90.00), not rotated**: pin 1 at
  (83.50, 87.46), pin 6 at (86.04, 92.54). Odd pins at x 83.50, even at 86.04,
  rows at y 87.46 / 90.00 / 92.54.
* **The two headers are not on a common 0.1 inch grid.** DB12's first column is
  6.92 mm inboard of DB1's inner row and its first row is 9.50 mm toward
  y = 140 from DB1 pin 1. Neither is a multiple of 2.54 mm. Both socket
  footprints are therefore placed at these measured offsets, not snapped.
* The **N2ADR filter board** (`hardware/companions/n2adr/n2adr.kicad_pcb`) is
  100 x 49.9 mm; matching its 1x20 header `CN2` (1.1 mm from its y = 55 edge,
  48.26 mm long) to the HL2's `DB7` (22x1 at (168.7, 100.26) rot 90, 1.25 mm
  from the x = 169.95 edge) maps the filter board's x axis to the HL2's y axis
  and puts the filter board over **HL2 x 120.05 to 169.95, full y range**.

**So the free corridor is HL2 x 70.00 to 120.05 = 50.05 mm.** Board A is
**48.00 x 66.00 mm** at HL2 x 70.50-118.50, y 74.00-140.00, leaving **1.55 mm**
to the filter board's edge. There is no electrical overlap and, unlike rev A,
**no mechanical overlap** - board A is a plain rectangle entirely inside the
corridor, and the filter board can stay fitted.

`HL2_ORIGIN` in `tools/gen_gowin_bridge.py` is the one constant that sets this;
the board can slide anywhere from HL2 x 70.00 to 72.05 with a one-line change.
Section 6.4 says when you would want to.

### 6.3 Do three mini HDMI sockets fit? Yes. Do three cables? Almost certainly.

**The sockets: yes, comfortably.** XKB A71-05H4-111N1, from its drawing:
body **11.20 mm wide x 7.50 mm deep x 3.10 mm high**, front face 0.50 mm
beyond the PCB edge so it occupies 7.00 mm of board. Land pattern 12.60 mm
wide overall (the shell-leg pads reach +/-6.05 mm from the centre).

| | |
|---|---|
| Socket centres, local x | **6.60, 24.00, 41.40** (pitch **17.40 mm**) |
| Bodies occupy | 1.00-12.20, 18.40-29.60, 35.80-47.00 mm |
| Gap between adjacent bodies | **6.20 mm** |
| Outermost copper (a shell-leg pad) | 0.55 mm from the board edge, against JLCPCB's 0.30 mm minimum |
| Largest pitch the 48 mm board allows | **17.65 mm** at the 0.30 mm limit; 17.40 was chosen to keep 0.55 mm |

Verified by reading the Excellon export back: the shell slots are at local
x 1.175 / 12.025, 18.575 / 29.425, 35.975 / 46.825 mm, and the locating pegs
at +/-3.75 mm from each centre.

**The cables: the binding constraint, and it is not fully verifiable.** The
moulded boot on the end of an HDMI cable is wider than the connector shell, and
**no manufacturer or distributor publishes a dimensioned drawing of a mini HDMI
cable's boot.** About fifteen were checked. What is published:

| | Width | Source |
|---|---|---|
| Full-size Type A plug **boot** | **20.8 mm** (x 10.9 mm high) | PIC Wire assembly drawing 11012-4946 rev 7 sheet 2; corroborated by L-com's 20.8 mm recommended panel opening |
| Full-size Type A plug **shell** | 13.9 mm | same |
| Mini Type C plug **shell** | **10.42 mm** (+0.03/-0.04) x 2.42 mm | Multicomp 60S019P-301N-B2 datasheet |
| Mini Type C plug **boot** | **not published** | - |

So the full-size boot adds 6.9 mm to its shell, i.e. 3.45 mm of moulding per
side. Scaling that to the mini shell two ways:

| Estimate | Method | Mini boot width | Clearance at 17.40 mm pitch |
|---|---|---|---|
| Pessimistic | same absolute wall thickness: 10.42 + 6.9 | **17.32 mm** | **+0.08 mm** |
| Proportional | wall scales with the part: 20.8 x 10.42 / 13.9 | **15.59 mm** | **+1.81 mm** |

**Three cables therefore fit under both estimates, but only just under the
pessimistic one.** Measure the boots on the cables you intend to use with
calipers; if they are 17.4 mm or narrower, the board is fine as generated.

**Staggering the sockets in depth does not rescue this, and it is worth saying
why, because it is the obvious-looking fix.** Recessing the middle socket 9 mm
would separate the socket *bodies* but not the boots: a Type A boot is
**44.2 mm long** (same PIC drawing) and a mini one is comparable, so with any
depth offset a 66 mm board can provide the boots still lie side by side over
90 % of their length. The middle plug would have to pass laterally between its
two neighbours' boots, and the gap between them is smaller than the boot.

**If the measured boots are too wide**, in order of preference:

1. **Buy narrower cables.** The boot is the whole problem and it varies a lot
   between brands; camera-type mini HDMI cables tend to be slim.
2. **Run the 3-lane fallback geometry** (`LINK_SPEC.md`: `GL_LANES = 3`, clock
   at 153.6 MHz, lanes at 307.2 Mbit/s). It uses **only `OUT 1` and `IN`, the
   two outer sockets, 34.80 mm apart**, so boot width becomes irrelevant. This
   costs nothing in bandwidth on paper - 3 lanes x 307.2 Mbit/s is still
   921.6 Mbit/s - but it moves the forward lanes onto the tight 307.2 Mbit/s
   single-ended path of section 2.1, and the gateware already supports it.
3. **Make a 100 mm mini-to-mini pigtail with a right-angle plug** on the board
   end for the middle socket.
4. **Reduce `MINI_PITCH` and shift `HL2_ORIGIN`** in the generator: moving the
   board to HL2 x 72.00 and dropping the pitch to 16.00 mm keeps all three
   bodies on the board and gives every boot 2 mm more room toward the
   extrusion wall, at the price of 1.5 mm of filter-board clearance.

**The two-radio configuration is immune.** It uses only `OUT 1` and `IN`, whose
centres are **34.80 mm apart** - more than twice the widest boot estimate. That
is why the socket order on the board edge is `OUT 1`, `OUT 2`, `IN`: the two
sockets used in the two-radio case are the outer pair, by design.

**One clearance to check by measurement.** The leftmost boot, at the
pessimistic 17.32 mm, reaches HL2 x 6.60 - 8.66 + 70.50 = **68.44 mm**. The
HL2 board's left edge is x = 70.00 and the extrusion's internal cavity is about
105 mm across a 100 mm board, putting its inner wall near HL2 x 67.6 -
**roughly 0.8 mm of clearance, and that figure is derived from the enclosure
cross-section, not measured.** Option 4 above is the fix if it fouls.

### 6.4 Height, and stacking now works

| | Above the HL2 board top |
|---|---|
| HL2 DB1 / DB12 male header insulator | 2.54 mm |
| 2.54 mm female socket body | 8.50 mm |
| **Board A underside** | **11.04 mm** |
| Board A (1.6 mm) top surface | 12.64 mm |
| **Mini HDMI shell top** | **15.74 mm** (12.64 + 3.10) |
| Cable boot, 12 mm high, centred on the shell | about 8.2 to 20.2 mm |
| Stack-through tails above board A | ~3-6 mm |
| A stacked DB1 companion's own board | ~22.7 mm |

Two consequences, both improvements on rev A:

* **Board A must not extend past HL2 y = 74.** The RJ45 magjack at
  (81.1, 62.8) is about 13.5 mm tall and occupies roughly HL2 x 73-89,
  y 52-73, and the barrel jack CN2 at (80.8, 47.2) is about 11 mm tall. Board
  A's underside sits at 11.04 mm, **below both**, so it must stop short of
  them rather than pass over. Its outline starts at exactly y = 74.00, giving
  **1.0 mm in y** to the magjack - not in z. Verify by measurement.
* **A stacked companion board now clears the sockets.** rev A's DVI
  receptacles reached ~26 mm and blocked the DB1 stack-through entirely. The
  mini HDMI shells reach 15.74 mm, so a companion at ~22.7 mm passes over
  them. The cable boots reach 20.2 mm, which still clears 22.7 mm by 2.5 mm,
  though a companion with tall parts on its underside would not.

The enclosure's rear panel is 104.7 x 54.3 mm, confirming a 55 x 105 mm
cross-section, so there is roughly 40 mm above the HL2 board. Board A's tallest
feature at 15.74 mm uses under half of it.

### 6.5 The panel cutout

The three sockets are at **HL2 x 77.10, 94.50, 111.90** on the **y = 140 end**
of the board - the end that carries the RF connectors, not the Ethernet and
power end, which the RJ45 magjack blocks. The endcaps are 0.8 mm PCBs
(`hardware/enclosure/endcaps/`), so a custom one is straightforward.

**One slot, not three holes**, because the boots are wider than the sockets and
the middle plug has to go in past its neighbours:

| | |
|---|---|
| Slot width | **HL2 x 68.4 to 120.6**, i.e. 52.2 mm, centred on x 94.5 |
| Slot height | **8.2 to 20.2 mm** above the HL2 board, i.e. 12.0 mm |
| Plug insertion depth needed past the panel | about 7.5 mm (the shell), plus the boot |

The HL2's own front-edge RF connectors (`COMBORFGND` at x 133.3 and 150.3,
y 140) are outside that window.

### 6.6 Board B on the Tang dock — still unverified

**"User must verify by measurement."** No Tang Mega 138K dock board file,
mechanical drawing or 3D model was obtained, so board B's J14 socket position
is a plausible guess and nothing more:

| | |
|---|---|
| Board B | 90.00 x 46.00 mm |
| J14 socket pin 1 hole | local **(6.00, 8.00)** |
| Odd pins (J14 silkscreen "N") | the **y = 8.00** row |
| Even pins ("P") | the **y = 10.54** row |
| Pins ascend | in **+x**, to pins 39/40 at x 54.26 |
| Three Type A sockets | centres at local x **21.00, 45.00, 69.00** (pitch 24.00 mm) on the y = 46.00 edge |

All verified from the Excellon export. The Type A boot is **20.8 mm** wide
(published, section 6.3), so a 24.00 mm pitch gives **3.2 mm** between
adjacent boots - no problem, and board B has 11 mm of spare board either side
if the pitch needs to grow.

**What to measure on the real dock before ordering:** the distance from the
J14 hole row to the nearest board edge, the clearance to the PMOD sockets
(J8/J9 are right-angle parts and therefore low profile, so board A's 11 mm
standoff should clear them - but board B's standoff is the same 11.04 mm and
that is the number to check), and which end of J14 is pin 1. Then change
`board_b()`'s J14 position in `tools/gen_gowin_bridge.py` and regenerate.

**Print `templates/tang-bridge-1to1-TOP-fit-check.pdf` at 100 %, measure its
50 mm calibration rule, and offer it up to the dock.** That is what it is for.

### 6.7 The bottom-side mirroring trap, re-tested

KiCad does **not** mirror pad coordinates for a footprint placed on `B.Cu`.
Board A's two sockets must mate a male header whose hole positions are fixed by
the HL2, so the generator mirrors them in x explicitly (`Part.mirror`). This
was proved from the drill export, not assumed:

* DB1's odd column lands at local x **3.54** and its even column at **6.08**,
  which is the HL2's grid.
* **There is no hole at local x = 1.00**, which is where the even column would
  be if the mirroring were missing. That is the specific check, and
  `tools/check_geometry.py` runs it every time.

Board B's J14 socket is **not** mirrored, and that is correct for a different
reason: its position is not fixed by anything, and un-mirrored is what makes
the header run in +x from x = 6.00 instead of off the left edge. Because board
B's position is unverified anyway, the user has to confirm the handedness
against the dock; section 6.6 states it explicitly so there is something to
check against.

---

## 7. Parts sourcing

| Part | LCSC | Verified | Note |
|---|---|---|---|
| Mini HDMI Type C, right angle, hybrid | **C2682170**, XKB A71-05H4-111N1 | body and full land pattern from the manufacturer drawing, dimensioned **relative to the PCB edge** | 2,217 in stock, about $0.46 at qty 10 (12 Sep 2026). **No mating-cycle rating on its drawing.** |
| — alternative | C136421, SOFNG HDMI-519 | **6,000 no-load / 5,000 loaded mating cycles** - the only mini HDMI at LCSC with a published figure - and about $0.21 | **Not a drop-in.** Its layout datum is the pad row, not the board edge, so its edge relationship is derived; its features sit 0.20-0.35 mm further in and its pads are 0.27 mm not 0.23 mm. Switching means editing `MINI_HDMI` and regenerating. |
| Full-size HDMI Type A, right angle, hybrid | **C427307**, Amphenol ICC 10029449-111RLF | **10,000 mating cycles**, 44.1 N mating / 9.8-39.2 N unmating, 6.1 mm high, 9.9 mm deep | 3,324 in stock, $0.51 at qty 10 and qty 50. Uses the **stock KiCad footprint unchanged**; every value in it was re-checked against Amphenol drawing 10029449 rev Y sheet 3. |

Two notes on the Type A choice worth recording, because they are easy traps:

* The four dash numbers a naive search reaches (-001TLF, -001RLF, -101TLF,
  -101RLF) are all out of stock or down to 35 pieces at LCSC. **-111RLF is the
  one that is stocked**, it is served the same Amphenol drawing, and the KiCad
  footprint was in fact contributed from that exact dash number
  (kicad-footprints PR #2021). The -002 variants are the **with-flange** body,
  15.4 mm tall because of an M3 boss - do not substitute them.
* A cheaper all-through-hole alternative exists (C711354, HOAUC
  HYC12-HDMIA19-610B, $0.32, 10,000 cycles) but **its land pattern is not
  interchangeable** with the Amphenol one: three rows on a 1.50 mm in-row
  pitch, a different pin-to-row assignment (using the wrong one cross-wires the
  TMDS pairs), two shell slots instead of four, and its drawing never dimensions
  the PCB edge. Using it means drawing a footprint from scratch.

**Note on the contact field offset**, since it looks like an error: both the
Amphenol and the HOAUC Type A patterns place the 19-contact field **0.25 mm
off the shell centreline** (pads run +4.75 to -4.25 rather than +/-4.50). This
is normal for a Type A right-angle receptacle and the KiCad footprint
reproduces it. Do not "correct" it.

### 7.1 The one thing to check before sending gerbers

**Which end of the mini HDMI land pattern is pin 1.** The XKB drawing labels
pin 1 and pin 19 on its front view but not on its land-pattern view. The
footprint is generated with **pin 1 at the +x end**. If the part is the other
way round, every signal lands on the wrong cable wire - clock on +5 V and so
on - and the board is scrap.

The fix is one line: set `MINI_HDMI['pin1_at_plus_x'] = False` in
`tools/gen_gowin_bridge.py` and regenerate. Check it against the part in your
hand, or against the SOFNG drawing, which does label its land pattern (pin 1
at the right-hand end in its top-of-board view).

---

## 8. Deliberate departures from the brief

| Brief said | What was done | Why |
|---|---|---|
| PIN_88 = DB12 pin 5, PIN_89 = DB12 pin 6 | **Swapped**: PIN_88 = DB12 pin **6**, PIN_89 = DB12 pin **5** | The HL2 netlist says so. `PINMAP.md` 0.1 quotes it. rev A had it wrong and rev A's KiCad files were wired wrong accordingly. |
| The LED pins have "1 k to ground" | They are 1 k **pull-ups to +3V3** through the LED | `hermeslite.net`: cathode at the FPGA pin, anode through 1 k to +3V3. Changes the sign of the load: the receiver must sink 1.4 mA, not source it. |
| Resolve the 2.5 V threshold with option (a) or (c) | **(c)**, one SN74AVC8T245, with (d)'s argument documented and bypass links fitted for it | Option (a) does not exist: no discrete LVDS driver specifies `VIH` below 2.0 V. Section 3.1. |
| Mini HDMI socket, hybrid SMT + THT shell | XKB A71-05H4-111N1: SMT contacts, **four THT shell legs in plated slots plus two THT locating pegs** | Better than asked for - six through-hole anchors, not just tabs. |
| Three sockets side by side, "state the arithmetic" | Done, and they fit - **but the cable boot, which sets the real pitch, is not published by anyone** | Section 6.3 gives both estimates and the clearance each implies. The pessimistic one leaves 0.08 mm. |
| Grounded M3 mounting holes on both boards | Board B has two; **board A has none** | No mounting boss inside the HL2 enclosure was identified for a hole to line up with, and board A is carried by DB1, DB12 and the panel. Grounding is the J8 header plus two through-hole pads. Adding holes to a 48 mm-wide board that is already tight for the socket fan-outs costs layout room for no known benefit. |
| 22 ohm series resistors on the driver inputs | **Not fitted on board A** (board B has them) | On board A the driver inputs are driven by U1's B-side outputs over a trace under 10 mm long. The translator's output impedance is already controlled and a series resistor there would only add delay. Board B's driver inputs come from a J14 header pin over a longer unterminated run, so they keep the 22 ohm. |

---

## 9. Everything unverified, in one list

1. **The mini HDMI land pattern's pin-1 end.** Section 7.1. Highest-risk item
   on the board: getting it wrong makes it scrap.
2. **The mini HDMI cable boot width**, and therefore whether three cables plug
   in at once. Section 6.3. Estimates 15.6 to 17.3 mm against 17.4 mm of pitch.
   **Measure your cables.**
3. **The HL2 +3V3 rail's spare current.** The regulator was not identified.
   Measure with board A plugged in. Section 5.1.
4. **The clearance from the leftmost cable boot to the extrusion's inner wall**
   - about 0.8 mm, derived from the enclosure cross-section rather than
   measured. Section 6.3.
5. **Board B's position on the Tang dock**, including which end of J14 is
   pin 1. Section 6.6. Print the template.
6. **How much current J14 pin 11 can supply.** Section 5.2.
7. **Whether the Tang dock's mounting holes are grounded** (dock schematic not
   obtained), which is why board B has the `GND AUX` header.
8. **Whether the Cyclone IV C8 can capture 307.2 Mbit/s DDR** on bank-6 inputs
   in soft logic. Gateware question, gates the reverse link. Section 2.1.
9. **The SN74AVC4T245's 380 Mbit/s rating against the 153.6 MHz reverse clock**
   (81 % of rating). Scope check at bring-up. Section 3.4.
10. **The real ceiling of the single-ended slow-in line.** 10-25 Mbit/s is
    reasoning, not measurement. Section 1.1.
11. **Whether DB12 ships fitted** on a factory-built HL2. The HL2 BOM says
    "do not install"; assume you solder it.
12. **Forward lane 3's eye width on the 21 pF VREF pin** (PIN_80). 46 % of the
    unit interval is calculated, not measured. Section 2.2.
13. **Whether a board A plugged into DB1 pins 11/15/17 while the HL2 still runs
    stock LED gateware causes contention.** The `RX MODE` jumper exists to hold
    the receivers off until the right gateware is loaded, and the default
    setting keeps them off whenever the `IN` cable is unplugged.
14. **Whether the N2ADR filter board is clear of board A in z.** rev A had to
    worry about a tab overhanging it; rev B does not overhang it at all, so
    this reduces to the 1.55 mm edge-to-edge gap in plan view.
