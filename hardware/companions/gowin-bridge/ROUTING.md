# Routing the gowin-bridge boards in EasyEDA Pro

Written for someone who is comfortable with a PCB editor but is not a
high-speed specialist. It is specific to these boards: where their hard bits
are, what the numbers actually are, and what you can safely ignore.

**There are three KiCad projects**, all generated from one source
(`tools/gen_gowin_bridge.py`):

* `hl2-bridge/` — board A alone, for working on the HL2 side of the link on
  its own bench.
* `tang-bridge/` — board B alone, for working on the Tang dock side on its
  own.
* `panel/` — both boards on one 94.00 x 100.00 mm V-scored production panel.
  **This is the one you order.** Route board A and board B in their own
  projects first (that is what sections 1-6 below are about), then carry the
  same routing onto the panel (section 7) — the panel is not a place to route
  from scratch.

The KiCad projects contain **placement, nets, board outline, stackup and
zones, and no tracks at all**. Everything below is the routing.

Read `PINMAP.md` for what connects to what and `DESIGN_NOTES.md` for why.

---

## 0. The short version

| | Board A (`hl2-bridge`) | Board B (`tang-bridge`) |
|---|---|---|
| Size | 48.00 x 66.00 mm, 4 layer | 90.00 x 46.00 mm, 4 layer |
| Sockets, left to right | **OUT** (x 6.60), **AUX** (x 24.00), **IN** (x 41.40) — front edge y = 66.00, 17.40 mm pitch | **IN** (x 21.00), **AUX** (x 45.00), **OUT** (x 69.00) — front edge y = 46.00, 24.00 mm pitch |
| Differential pairs to route | **16** (4 per socket x 3, the 4 `IN` pairs each in two segments) | **16** (4 per socket x 3, the 4 `IN` pairs each in two segments) |
| Every lane's rate | **307.2 Mbit/s**, both directions, on every socket | **307.2 Mbit/s**, both directions, on every socket |
| The hard bit | **fanning out three 19-pin 0.40 mm-pitch mini HDMI footprints** | the three-way junction on the four **AUX** pairs (section 3.6) |
| Time to expect | an evening | an hour or two |

**`OUT` and `IN` are the two OUTER sockets on both boards and are each
fixed-direction** — `OUT` all driven, `IN` all received. **`AUX`, in the
middle, is bidirectional**: a strap on each board decides which two of its
four pairs it drives and which two it receives. rev B's socket names (`OUT 1`,
`OUT 2`, `IN` on board A; `IN 1`, `IN 2`, `OUT` on board B) are gone.

Three things decide whether this board works, and none of them is the trace
impedance:

1. **Every pair must have unbroken ground on layer 2 directly underneath it,
   for its whole length.** Nothing else you do matters as much.
2. **Every single-ended trace between an HL2 header pin and a chip input, or
   between a chip output and a J14 pin, must be under 25 mm.** These are the
   only unterminated fast nets on either board.
3. **Every `AUX` pair has a three-way junction, and every branch off its
   through-path must be a short stub.** Section 3.6. This is new in rev C and
   it is the one hazard `OUT` and `IN` do not have.

---

## 1. Stackup, and the trace geometry that follows from it

### 1.1 Set the stackup before you draw anything

Order the boards as **JLCPCB 4-layer, 1.6 mm, stackup `JLC04161H-7628`**
(their default), and set EasyEDA Pro to match:

| Layer | Role | Thickness |
|---|---|---|
| Top (L1) | **signal** - every differential pair lives here | 0.035 mm (1 oz) |
| prepreg 7628 x1 | | **0.2104 mm** |
| Inner 1 (L2) | **solid ground plane. Do not cut it.** | 0.0152 mm (0.5 oz) |
| core | | 1.065 mm |
| Inner 2 (L3) | **power plane** (+3V3, with a +2V5 island on board A) | 0.0152 mm (0.5 oz) |
| prepreg 7628 x1 | | 0.2104 mm |
| Bottom (L4) | signal - the slow stuff, and the HL2 / J14 sockets | 0.035 mm (1 oz) |

Do not let EasyEDA Pro turn the inner layers into signal layers. The entire
point of paying for four layers on a board this small is that the 0.2104 mm
prepreg puts a solid ground plane 0.21 mm under every pair.

### 1.2 100 ohm differential: start at 0.25 mm trace / 0.20 mm gap

Edge-coupled microstrip on an outer layer over the layer-2 plane:

| | |
|---|---|
| dielectric height to the plane | 0.2104 mm (7628 prepreg) |
| dielectric constant assumed | **4.3** (7628 glass at 150 MHz; JLCPCB quote 4.6 at 1 MHz, and it falls with frequency) |
| trace width | **0.25 mm** |
| edge-to-edge gap | **0.20 mm** |
| single-ended impedance of one leg | 61 ohm |
| **differential impedance** | **98.5 ohm** |

**Confirm this in EasyEDA Pro's impedance calculator against the stackup
JLCPCB actually quotes you**, because the prepreg thickness is the dominant
term and JLCPCB will substitute a different stackup without asking if the
order is a different copper weight or thickness. If the calculator says
anything between 90 and 110 ohm, use it - these traces are 20 to 45 mm long
and the reflection from a 10 % mismatch at that length is invisible at the
LVDS driver's roughly 1 ns edge, which does not get any faster at 307.2 Mbit/s
than it was at 153.6 Mbit/s (section 4.1 has the reasoning).

Two geometries to know about but not use:

* **0.20 mm / 0.13 mm** also computes to about 100 ohm on this stackup (tight
  coupling), and it is what an earlier revision of these notes specified.
  Don't: 0.13 mm sits on JLCPCB's 0.127 mm minimum, so the +/-0.02 mm etch
  tolerance is 15 % of the gap and the impedance swings with it.
* **0.30 mm / 0.35 mm** is the loosely-coupled alternative, also about
  100 ohm, more tolerant of etch variation, and it needs more room than
  board A has between the mini HDMI fan-outs.

### 1.3 JLCPCB manufacturing rules to enter

| Rule | Value |
|---|---|
| Minimum trace width | 0.127 mm |
| Minimum clearance | 0.127 mm |
| Minimum via | 0.45 mm pad / 0.25 mm drill |
| Minimum annular ring | 0.075 mm |
| Trace / copper to board edge | 0.30 mm |
| Minimum hole-to-hole | 0.50 mm |
| Solder mask minimum dam | 0.10 mm |

The KiCad projects already carry these, plus three net classes which should
survive the import. The `LVDS100` numbers are the section 1.2 geometry, and
the projects also define a second differential preset of **0.15 mm / 0.17 mm**
for the connector fan-out neck (section 3.1):

| Net class | Applies to | Track | Clearance | Diff width / gap |
|---|---|---|---|---|
| `LVDS100` | every `O_*`, `AX_*`, `I_*` pair (`*_P`/`*_N`, panel-prefixed `A_`/`B_` too) | 0.25 mm | 0.13 mm | **0.25 / 0.20 mm** |
| `Power` | `+3V3`, `+2V5`, `DB1_3V3`, `P5V_*`, `LDO3V3` | 0.60 mm | 0.20 mm | - |
| `Default` | everything else, GND included | 0.25 mm | 0.15 mm | - |

**`LVDS100`'s clearance is deliberately 0.13 mm, not 0.20 mm.** The mini HDMI
footprint's own pads are 0.17 mm apart - that is the manufacturer's land
pattern - and a 0.20 mm clearance rule fails against the connector itself.
Keep pairs *far* from other nets by drawing them that way (section 3.4), not
by setting a clearance rule you then have to override.

**GND is deliberately NOT in the `Power` class.** It is a plane; it needs no
wide-track rule, and a 0.20 mm clearance on it also fails against the
connector pads.

### 1.4 Differential pair rules

Every pair net is named `<socket>_<lane>_P` / `<socket>_<lane>_N` — `<socket>`
is `O`, `AX` or `I` on the two individual boards, and `A_O`, `A_AX`, `A_I`,
`B_O`, `B_AX` or `B_I` on the panel — so EasyEDA Pro's automatic pair
detection finds all of them with no manual pairing.

**The `IN` socket's four pairs, on both boards, exist in two segments** either
side of the AC-coupling option, and both boards follow the same convention:

```
connector  I_CLK_P  ---[ Cc || 0R link ]---  I_CLK_RX_P  --- receiver
           I_CLK_N  ---[ Cc || 0R link ]---  I_CLK_RX_N  --- receiver
```

Treat each segment as its own pair. The link/capacitor pads break the
coupling for about 1.5 mm; that is unavoidable and electrically harmless
(section 3.5).

**The `AUX` socket's four pairs do NOT do this.** There is no segmentation and
no coupling option on `AUX` — each pair is one continuous run from the
connector to a three-way junction where a driver output and a receiver input
both land. That junction, not a coupling option, is `AUX`'s routing hazard;
section 3.6 covers it, and it is why `AUX` gets its own fan-out and passives
subsections separate from `IN`'s (3.5) and `OUT`'s (implicit in 3.1/3.2).

---

## 2. Route in this order

The order matters because the mini HDMI fan-out has no freedom, the `AUX`
junction constrains where three chips sit, and everything else has plenty of
room.

1. **Board A: fan out the three mini HDMI footprints — `OUT`, `AUX`, `IN`.**
   Section 3.1. Do this before anything else; it fixes where the pairs enter
   the board.
2. **Board B: fan out the three Type A footprints — `IN`, `AUX`, `OUT`.**
   Section 3.2. Easier.
3. **The `IN` pairs**, connector to receiver, as short as you can, with the
   termination resistor at the receiver end. Board A has 4, board B has 4.
   These carry 307.2 Mbit/s and the receiver's input threshold is the most
   easily upset thing on either board.
4. **The `AUX` pairs**, connector to the three-way junction. Board A has 4,
   board B has 4. Section 3.6. Route the through-path (connector to
   termination) as the main run and keep the driver-output and
   receiver-input branches to under 5 mm each — do this while U3/U4/U6
   (board A) or U4/U5/U2 (board B) are still easy to move, because their
   placement is what makes the stubs short.
5. **The `OUT` pairs**, driver to connector. Board A has 4, board B has 4.
   These can be long; the driver does not care.
6. **The single-ended fast nets, all under 25 mm.**
   * **Board A**: HL2 header pin into U1's A-side (the 2.5 V -> 3.3 V
     translator that feeds the `OUT` clock, the three `OUT` lanes and all
     four `AUX` pins into their LVDS drivers), and the LVDS receiver
     outputs into the HL2 header pins through the two 3.3 V -> 2.5 V
     translators U7 and U8 (the `IN` clock, the ROLE strap, and whichever
     `AUX` group this board currently receives).
   * **Board B**: J14 pin into a driver input, a receiver output into a
     J14 pin, and (new in rev C) J14 pin to/from the strap-gated buffer U6
     for the two `AUX` groups.

   **Give the traces at DB1 pin 4 (PIN_80, `HL2_AX_G2DAT`) the shortest run
   on the board.** That HL2 pin is `VREFB5N0` and carries about 21 pF of pin
   capacitance instead of the usual 7 pF. At the full 307.2 Mbit/s rate that
   costs it a 10-90 % edge of 1.49 ns, which is **45.8 % of the 3.2552 ns
   unit interval** (`PINMAP.md` 4.2). The gateware runs `AUX` divided today
   (section 3.6 below), which makes this comfortable in practice, but the
   board has to be routed as if it were running at full rate, because
   `PINMAP.md` 2.3 says the hardware must support it. Route the DB1 pin 1
   net (`HL2_AX_G2CLK`, PIN_72) short too, for the same reason and because it
   also carries the HL2's own uFL stub (`PINMAP.md` 6.2) — nothing on this
   board can fix that stub, but there is no reason to add board length on
   top of it.
7. **Power.** 0.60 mm minimum, and see section 6.
8. **The slow lines, HPD, +5 V and the test points.** Route these loosely,
   last, anywhere.
9. **Pour and stitch.** Section 5.

---

## 3. The fan-outs

### 3.1 Board A: three mini HDMI footprints at 0.40 mm pitch

This is the whole difficulty of board A. Each socket has **19 pads, 0.23 mm
wide, 1.20 mm long, on a 0.40 mm pitch, leaving 0.17 mm between pads**, in one
row 7.15 mm in from the board edge. Socket centres are **x = 6.60 (`OUT`),
24.00 (`AUX`), 41.40 (`IN`)**, all on the front edge **y = 66.00**, a
17.40 mm pitch.

**The good news, and it is very good news: Type C puts the two legs of every
pair on adjacent pads, with a ground pad between pairs.**

| pad | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| | GND | **D2+** | **D2-** | GND | **D1+** | **D1-** | GND | **D0+** | **D0-** | GND | **CLK+** | **CLK-** |

So the fan-out is: pair, ground, pair, ground, pair, ground, pair. Do this for
all three sockets, `OUT`, `AUX` and `IN` alike — the land pattern and the
fan-out mechanics do not know or care which socket is bidirectional:

1. **Take the four ground pads (1, 4, 7, 10) straight down to layer 2 first.**
   One 0.45/0.25 mm via per pad, centred about 0.9 mm behind the pad, on the
   pad's own centre line. These four vias are the single most important
   feature on board A: they are the return path for the pairs either side of
   them, and they are what keeps the pairs referenced to the plane through the
   region where the traces are too narrow to be 100 ohm.
2. **Neck each pair down to 0.15 mm trace / 0.17 mm gap** and run it straight
   back off its two pads for about 1.5 mm, parallel, no bends.
3. **Then flare to 0.25 / 0.20 mm** and route away.

The necked region is roughly 130 ohm rather than 100 ohm. That is fine and
here is why, with the number: 1.5 mm of FR4 microstrip is **9 ps** of delay,
and the LVDS edge rate is about **1 ns**. A discontinuity 110 times shorter
than the edge is not a discontinuity - the edge cannot resolve it. Do not try
to fix it, and in particular do not lengthen the necked region trying to
taper gradually.

Pads 13 to 19 are DDC/CEC ground (13), CEC (14), SCL (15), SDA (16),
Reserved (17), +5 V (18) and HPD (19). **CEC, SDA and Reserved have no copper
at all** - leave them bare. Pad 13 goes to a plane via like the other grounds.
On `OUT` and `IN`, SCL is the slow status/command line; on `AUX` it is a test
pad only (`PINMAP.md` 2.3), because the auxiliary cable is detected by clock
activity in the gateware, not by HPD or SCL. **SCL, +5 V and HPD are slow on
every socket**: route them out on 0.25 mm with no impedance control, on
whichever side is convenient.

The four shell legs sit in plated slots at x = +/-5.425 mm from each socket
centre and the two locating pegs are Ø0.99 mm holes at +/-3.75 mm. **Ring each
socket's shell slots with ground vias** - the shell is the cable's shield
return and it needs a low-inductance path to the plane, not a single trace.

**The outermost copper on board A is a shell-leg pad 0.55 mm from the board
edge.** That is inside JLCPCB's 0.30 mm rule but it is the tightest place on
the board; don't add anything out there. (On the panel this same pad sits
0.55 mm from the x = 48 V-score on `IN` — section 7 has the number again in
that context.)

### 3.2 Board B: three Type A footprints at 0.50 mm pitch

Easier in every way - 0.50 mm pitch, 0.30 mm pads, and the board has room -
but the pin ordering is **worse** than Type C for fan-out, because Type A puts
the shield pad *between* the two legs of each pair. Socket centres are
**x = 21.00 (`IN`), 45.00 (`AUX`), 69.00 (`OUT`)**, all on the front edge
**y = 46.00**, a 24.00 mm pitch:

| pad | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| | **D2+** | GND | **D2-** | **D1+** | GND | **D1-** | **D0+** | GND | **D0-** | **CLK+** | GND | **CLK-** |

1. **Via every shield pad (2, 5, 8, 11) straight down to layer 2** immediately
   behind the pad. Do this first, for the same reason as board A.
2. Bring each pair's + and - legs back past that via and **converge them into
   a coupled pair about 1.5 mm behind the pad row.** The pair is uncoupled for
   those 1.5 mm; same 9 ps argument, same conclusion - ignore it.
3. Then route at 0.25 / 0.20 mm.

Pad 17 is DDC/CEC ground: plane via. Pads 13, 14 and 16 (CEC, Reserved, SDA)
have no copper. Pad 15 (SCL) carries the HL2 status UART on the `IN` socket
only (`PINMAP.md` 5, note on pin 19) — it is a test pad on `AUX` and on `OUT`
(board B's `OUT` socket SCL has no source in rev C; J14 pin 36 is spare).
Pads 18 (+5 V) and 19 (HPD) are slow on every socket.

The four Amphenol shell legs are Ø1.30 mm plated holes, the rear pair 14.50 mm
apart and the front pair 15.70 mm apart. Ring them with ground vias.

### 3.3 The IC pins

* **U1 on board A is a TSSOP-24 at 0.65 mm pitch** with all eight A-side
  inputs on one side and all eight B-side outputs on the other. It needs no
  cleverness: single-ended in one side, single-ended out the other.
* **The LVDS drivers and receivers are flow-through parts**: DS90LV047A has
  its four single-ended inputs on pins 2, 3, 6, 7 (one side) and its four
  differential output pairs on pins 9-16 (the other side). DS90LV048A is the
  mirror. **Route the single-ended side and the differential side on opposite
  sides of the package and never let them cross.** This is the one placement
  rule the generated layout already honours - do not undo it by routing
  around the back of a chip.
* Keep the LVDS legs of each package under 10 mm before the pair reaches its
  termination or its connector fan-out.
* **Board A now carries three LVDS drivers (U2, U3, U4) and two LVDS
  receivers (U5, U6)** — one driver each for `OUT`, `AUX` group G1 and `AUX`
  group G2 (three separate enable domains need three packages, because the
  DS90LV047A has one enable per package), one receiver for `IN` and one for
  `AUX`. **Board B is the same shape**: three drivers (U3 `OUT`, U4 `AUX` G1,
  U5 `AUX` G2) and two receivers (U1 `IN`, U2 `AUX`). Section 3.6 has the
  placement consequence.

### 3.4 How far pairs must stay from everything else

| From | To | Minimum | Why |
|---|---|---|---|
| pair edge | any other net | **0.60 mm** (3x the 0.20 mm pair gap) | crosstalk falls roughly as the square of separation; 3x the intra-pair gap puts the coupling 10x below the intra-pair coupling |
| pair edge | another pair's edge | **0.75 mm** | as above, plus the neighbour is also a fast edge |
| pair edge | ground pour | **0.60 mm**, or cut the pour away | a pour 0.2 mm from a 0.25/0.20 pair pulls the differential impedance down by roughly 15 % |
| any 307.2 Mbit/s pair | any clock pair (`OUT` clock, `IN` clock, or either `AUX` group's clock) | **as far as the board allows** | every clock pair is the timing reference for its own direction; noise on it becomes jitter on every lane that direction carries |

Board B has one specific crosstalk problem worth care: **on J14 the A (even)
pins carry received signals and the B (odd) pins carry transmitted ones, on
adjacent header pins**, because only 16 usable pins exist (`PINMAP.md` 5.1).
Over the short run from the socket to the chips, **a 307.2 Mbit/s output sits
2.54 mm from a 307.2 Mbit/s input** — both directions run the same rate now,
so there is no longer a slower aggressor or victim to lean on. Route the two
groups on opposite layers where you can, and put a grounded via fence between
them where you cannot.

### 3.5 Where the passives go, relative to the receiver — `IN` pairs only

For each `IN` pair, the order from the connector inwards is fixed:

```
socket pad -> ESD array -> [ 100nF (DNP) || 0R link ] -> 100R -> receiver pin
                                                      |
                                                     4k7 x2 (DNP) -> VBIAS
```

* **ESD array within 5 mm of the connector pads**, on the connector side of
  everything else, so a strike is clamped before it reaches a chip. The
  TPD4E05U06's 0.5 pF per channel is why it is safe to put in line on a
  307 Mbit/s pair at all - do not substitute a fatter part.
* **The 0 R link and its parallel 100 nF pad** sit next, in the pair. Keep the
  two legs' link pads side by side and at the same distance along the pair, so
  fitting or removing them does not create intra-pair skew.
* **The 100 ohm termination within 5 mm of the receiver input pins**, on the
  same layer, **with no via between the resistor and the pins.** A via there
  adds about 0.3 nH, which at a 1 ns edge is a visible reflection right at the
  point where the signal is smallest.
* The two 4k7 bias resistors (not fitted) tap the pair on the receiver side of
  the termination. Their pads are a stub on the pair; keep them under 1 mm
  long.

This whole structure — ESD array, DC-link/AC-coupling option, then
termination — exists only on `IN`. `OUT` has none of it (a driver output needs
no termination or ESD-in-line treatment beyond the socket's own ESD array, see
3.1/3.2). `AUX` has a different, simpler structure of its own: section 3.6.

### 3.6 The auxiliary fan-out — a hazard `OUT` and `IN` do not have

**An `AUX` pair is bidirectional.** On the board side a driver output and a
receiver input meet at **one node**, and that node goes straight to the
connector pin. There is no series link and no AC-coupling option in the path
— `PINMAP.md` 2.3 explains why: a series part in the middle of a pair that is
driven half the time is an impedance discontinuity on the outgoing signal, and
a series capacitor would leave the far end's receiver common mode undefined,
because on a bidirectional pair there is no always-DC-coupled end to set it.

**So every `AUX` pair has a three-way junction**: the connector pin, the LVDS
driver output, and the LVDS receiver input, plus the 100 R termination
position (section 3.7). Each branch off the connector-to-termination
through-path is a **stub** — an unterminated length of transmission line —
and a stub reflects.

**The practical rule.** Draw the through-path — connector pad to termination
resistor, passing the driver output and receiver input as close to that line
as the placement allows — as the main run, and keep the driver-output and
receiver-input branches as short as physically possible.

**A number to route to: keep each stub under 5 mm, and ideally under 3 mm.**
FR4 microstrip propagates at roughly 6.7 ps/mm, so:

| Stub length | One-way delay | Fraction of the 3.2552 ns unit interval |
|---|---|---|
| 5 mm | 5 x 6.7 ps = **34 ps** | about 1 % |
| 3 mm | 3 x 6.7 ps = **20 ps** | about 0.6 % |

Both are a small fraction of the unit interval, which is why 5 mm (and
ideally 3 mm) is the target rather than something tighter. If you cannot keep
a stub short at a given placement, **move the chip physically closer** rather
than routing further to reach it — the junction only works if the geometry is
short, not if the copper is clever.

**Which chips, so you can plan placement before drawing a track:**

* **Board A**: the `AUX` node is shared between driver **U3** (group G1 — the
  clock and data-0 pairs) or driver **U4** (group G2 — the data-1 and
  data-2 pairs), and receiver **U6**, which sits across all four `AUX` pairs.
* **Board B**: the equivalent parts are drivers **U4** (G1) and **U5** (G2),
  and receiver **U2**.

So **U6 on board A and U2 on board B each have four pairs arriving**, and the
two drivers on each board each contribute two of those four. Place the
receiver centrally across the four pairs and each driver near its own two,
before you route anything, or the stub-length target is unreachable no matter
how careful the routing is.

**One asymmetry that helps.** `OUT`'s four pairs are driven only and `IN`'s
four pairs are received only, so those eight pairs are ordinary point-to-point
runs with no junction. Only the four `AUX` pairs have this hazard — it does
not spread to the rest of either board.

**Why this matters even though the gateware runs `AUX` divided today.**
`PINMAP.md` 2.3 has the gateware clock `AUX` at 38.4 MHz DDR (76.8 Mbit/s per
lane, 13.02 ns unit interval) rather than the full 153.6 MHz DDR
(307.2 Mbit/s), because the G2 return clock on PIN_72 is an ordinary I/O that
cannot feed a PLL, so the sampling phase cannot be adjusted, and at the
divided rate it does not need to be. **The board itself is capable of
307.2 Mbit/s on `AUX` and must be routed as if it will be used at that rate**
— the divided rate is a gateware choice that can be revisited once the real
phase is measured on the bench, not a routing allowance.

### 3.7 The strap-selected termination

Each of the four `AUX` pairs has a **100 R differential termination
position**, but only two of the four are fitted, and which two depends on
which role the board ships in:

* **Board A ships ROLE A**, so it **receives** group G2 (the D1 and D2 pairs)
  — fit those two positions.
* **Board B ships ROLE B**, so it **receives** group G1 (the CLK and D0
  pairs) — fit those two positions.

The other two positions on each board stay **empty** — this board *drives*
those pairs in its shipped role, and the far end terminates them.

**Routing consequence: route all four positions anyway, on every board,
regardless of which two ship fitted.** Place each one within 5 mm of the
receiver pins for that pair, exactly as you would a fixed-direction `IN`
pair — because the user may move the ROLE shunt, and then the other two
positions get fitted instead. A position you did not route properly, on the
theory that "this board never receives that pair", becomes a real fault the
moment somebody changes the strap.

**Why the termination is four solder links and not a switch.** A switched
100 R would need an analogue switch, which is a part this design does not
otherwise need. And terminating both ends of a driven pair is actively wrong:
the driver would see 50 R instead of 100 R and the differential swing would
halve, from about 350 mV to about 175 mV, against the receiver's 100 mV
threshold — 75 mV of margin over a 2 m cable, which is not enough. Hence
fitting only the two positions this board receives, by hand, at build time.

**The 100 R HPD pull-downs changed from 1 k in rev B.** They are DC and can be
routed loosely, same as any other slow net (section 6).

---

## 4. Length matching: one number that is tight, one that does not matter

### 4.1 Intra-pair (P against N of the same pair): 0.15 mm

**Target 0.15 mm.** That is about 0.9 ps of skew on FR4 microstrip
(propagation is 6.0 ps/mm at an effective dielectric constant of 3.2).

The real physical limit is much looser: intra-pair skew becomes a measurable
problem above roughly 5 % of the transition time, and the LVDS transition is
about 1 ns, so the limit is **50 ps, which is 8.4 mm**. So why aim 50 times
inside it?

Because of what intra-pair skew *does*. Skew converts part of the differential
signal into a common-mode signal - for the duration of the skew, both legs are
briefly at the same potential instead of opposite ones. Common mode does not
cancel, so it becomes current on the cable shield, and that cable leaves the
enclosure of an HF receiver whose front end is 20 mm away. Differential-mode
current on a tightly coupled pair radiates almost nothing; common-mode current
on a metre of cable radiates very well indeed.

**None of this arithmetic changes now that every lane runs at 307.2 Mbit/s.**
The 50 ps / 8.4 mm limit comes from the LVDS transition time, which is a
property of the driver and receiver silicon (about 1 ns), not of how often
they switch. Doubling the data rate from rev B's forward lanes (153.6 Mbit/s)
to 307.2 Mbit/s shrinks the unit interval, which is why the *device-rating*
and *PIN_80* margins tighten elsewhere in this document — but it does not
touch the transition time, so it does not touch this number. **0.15 mm is
still the right target for exactly the reason rev B gave.**

And it costs nothing. Draw the pair with the differential-pair router and you
get well under 0.15 mm for free. The number exists to catch the two places
where the tool cannot help you:

* **the connector fan-out**, where the two legs come off pads that are not
  quite symmetric - keep the necked section the same length on both legs;
* **the chip pins**, where the + and - pins are on opposite sides of the
  package centre line - the DS90LV047A's DOUT1+ (pin 15) and DOUT1- (pin 16)
  are adjacent, so this is easy, but check it.

Do not serpentine to fix intra-pair skew. If you find more than 0.15 mm, the
pair is drawn wrong; fix the drawing.

### 4.2 Lane to lane: **relaxed, and you should not match it at all**

**Forward direction** (board A `OUT` -> board B `IN`): the Gowin receiver
retimes **every lane independently**, an `IODELAY` per lane with 256 taps of
12.5 ps, a total adjustment range of about **3.2 ns**, swept at power-up until
each lane's eye is centred (`gateware/gowinlink/LINK_SPEC.md` sections 6.1 and
6.2). Budgeting half that range for board and cable skew gives 1.6 ns, which
at 6.0 ps/mm is **about 265 mm of permissible lane-to-lane mismatch**. Board
A's longest `OUT` pair is about 45 mm and its shortest about 20 mm - a 25 mm
spread, which is 150 ps, **4.7 % of the adjustment range.** Nothing.

**So: do not add a single serpentine anywhere for lane-to-lane matching.** Do
not match a data lane to its clock pair either - the clock is the reference
the `IODELAY` sweep moves the data against, so board skew between clock and
data is exactly what the sweep is for.

**Reverse direction** (board B `OUT` -> board A `IN`): the HL2 has no
per-lane delay adjustment, but it has a word-alignment search that absorbs up
to +/-8 bit positions (`LINK_SPEC` 6.3), and a bit is 3.2552 ns, so the
tolerance is tens of nanoseconds. Within a bit you want skew under about
0.5 ns, which is 83 mm. Also nothing — and this was already true in rev B,
because the reverse lanes already ran at 307.2 Mbit/s there.

**`AUX` direction**: neither side has active per-lane compensation for `AUX`,
and today the gateware runs it divided (76.8 Mbit/s, 13.02 ns unit interval —
section 3.6), which gives far more slack than either the forward or reverse
link. But because `PINMAP.md` 2.3 requires the board be routable at the full
307.2 Mbit/s, don't let an `AUX` pair run wild just because the current
gateware tolerates it: keep the two pairs of each group in the same rough
length envelope as `OUT`/`IN` (tens of millimetres, not the width of the
board), so a future full-rate gateware is not immediately blocked by
routing skew nobody thought was a problem.

**The one thing that *does* consume the adjustment range** is the fixed
offset the level translator adds, and that is handled on the schematic rather
than in the layout: the `OUT` clock goes through the same SN74AVC8T245 (U1)
as the `OUT` lanes and all four `AUX` pins, so they all share one propagation
delay (`DESIGN_NOTES.md` 3.2). Don't defeat that by routing the clock a very
different length from the data - keep it within, say, 20 mm of the data
lanes, which happens naturally.

---

## 5. The ground plane, vias and pour

### 5.1 Layer 2 is sacred

**A differential pair must never cross a gap, slot or void in the layer-2
plane.** Not a thin one, not at a shallow angle, not "just a via antipad".

What goes wrong, with numbers: the return current for a 100 ohm pair on the
top layer flows in the plane directly under the pair, within roughly one
dielectric thickness (0.21 mm) either side. If the plane is cut, that current
has to detour around the end of the cut. A 10 mm detour adds roughly 10 nH of
loop inductance; at a 1 ns edge that is an impedance bump of order 15 % *and*
the detour loop is a small but efficient loop antenna at 150-300 MHz. On a
board bolted to an HF receiver, the second effect is the one that will annoy
you, and it will not show up in any DRC.

Practically, on these two boards:

* There is nothing on layer 2 but the plane. Keep it that way - **do not route
  a single track on layer 2**, however tempting.
* Via antipads are unavoidable. Keep them from lining up into a row under a
  pair: if you need a line of vias, put it parallel to the pairs, not across
  them.
* Where a pair must cross something on layer 3 (the power plane), that is
  fine - layer 3 is not the pair's reference.

### 5.2 Vias in a pair

Prefer not to. Every pair on both boards can be routed entirely on the top
layer, and that is the intent of the placement. If a pair truly must change
layer:

* **via both legs together**, side by side, symmetric about the pair's centre
  line, same via size;
* **put two ground stitching vias immediately beside them**, one each side, no
  more than 1 mm away - these carry the return current between the planes, and
  without them the pair's return has to find its own way and you have created
  the section 5.1 problem deliberately;
* keep the two pair vias' antipads merged into one opening rather than two
  overlapping circles, if EasyEDA Pro will let you.

On a 1.6 mm 4-layer board a top-to-bottom through via has no stub, so via
stub resonance is not a concern here.

### 5.3 Pour and stitching

* **Ground pour on both outer layers**, in the gaps left after routing.
* **Keep the pour 0.60 mm clear of every pair**, or cut it away entirely along
  the pairs. A pour crowding a pair changes its impedance more than any etch
  tolerance will (section 3.4).
* **Stitch the outer pours to layer 2 every 5 mm** across the board, and
  **every 3 mm along the whole board edge**. At 300 Mbit/s the top-layer pour
  is only useful if it is tied to the plane often enough to have the same
  potential; an unstitched pour is a floating conductor next to your pairs,
  which is worse than no pour.
* **A ring of ground vias around every connector shell pad and slot.**
* **Board B's AMS1117 (U7) tab**: flood it to the layer-3 plane with at least
  six 0.3 mm thermal vias. It dissipates (5.0 - 3.3) x 0.106 = **0.18 W**, or
  0.25 W with every chip at its datasheet maximum.
* **Board B has exactly one ground pin on J14 (pin 12).** Give it the widest,
  shortest possible connection to the plane - a via right at the pad, plus a
  ring of vias around it - and fit the ground wire to the `GND AUX` header J6.
  That wire is not optional in practice (`DESIGN_NOTES.md` 5).

### 5.4 Layer 3, the power plane

* Board A: mostly `+3V3`, with a **`+2V5` island** covering the translator row
  (it is already drawn in the KiCad file, local x 17-43, y 1-18). The island
  is a cut in the +3V3 plane, not in the ground plane, so it costs nothing -
  but check that no pair runs over the island's boundary on the top layer
  anyway, because it is free to avoid.
* Board B: `+3V3` throughout.
* Keep every decoupling capacitor's ground via within 1 mm of its pad.

---

## 6. Power and the slow nets: route these loosely

* **0.60 mm minimum** on `+3V3`, `+2V5`, `DB1_3V3`, `LDO3V3` and `P5V_*`.
  Board A draws roughly 100-115 mA and board B roughly 100-110 mA depending on
  activity (`DESIGN_NOTES.md` 5), so current is not the issue - inductance to
  the decoupling capacitors is.
* Get `DB1_3V3` from DB1 pins 19/20 to the J6 shunt to the plane in as few
  millimetres as possible, with the 100 nF entry capacitor right at the header.
* **The slow lines** (SCL on `OUT`/`IN`, the ROLE strap net, and the `AUX`
  test pads), **HPD** (`*_HPD`), **+5 V pins** and all the test points have no
  timing requirement worth respecting. 0.25 mm, anywhere, any layer. The only
  rule: **do not run a slow line alongside a pair for more than a few
  millimetres**, because the slow lines go out on an unshielded cable
  conductor and will happily carry away whatever they pick up.
* `RXEN_N` is a DC level. Ignore it.

---

## 7. Routing the panel

**This is the section that matters if you skip straight to ordering**, because
the panel is what you send to JLCPCB. Route board A and board B in their own
projects first (sections 1-6); this section is about carrying that routing
onto the shared panel without breaking anything.

The panel is **94.00 x 100.00 mm, two designs.** Board A occupies panel
**x 0..48, y 29..95** at its own orientation. Board B is **rotated 90
degrees** and occupies panel **x 48..94, y 5..95** — its local x axis now runs
down the panel and its local y axis runs across it. Assembly rails fill
**y 0..5 and y 95..100**. A **48 x 22 mm fiducial coupon** sits at
**x 0..48, y 5..27**.

### 7.1 The rule

**Route each board entirely inside its own outline. Never route across a
V-score line and never route into a rail or the coupon.**

The two boards are electrically separate on the panel on purpose: every net
name there carries an extra `A_` or `B_` prefix (plus the reference numbers
are renumbered 1xx for board A parts and 2xx for board B parts), precisely so
KiCad does not think board A's ground and board B's ground are the same net
and demand a track between them. **If you see a ratsnest line crossing
x = 48, something is wrong with the netlist, not with your routing** — fix the
prefix, don't route the connection.

### 7.2 Clear the V-scores by the fab's minimum

The three V-scores are **y = 5, y = 95 and x = 48**, each running the full
width or height of the panel. Keep clear of every one of them:

* **Copper: at least 0.40 mm from a score line.**
* **Component bodies: at least 1.00 mm from a score line.**

**`tools/check_geometry.py` already asserts both of these for the placement**
the generator produces. It cannot see what you draw during routing — tracks,
pours and vias are entirely on the person routing to keep clear.

**The one deliberate exception** is the six HDMI sockets, which are flush
with a board edge or a score line by design — that is the whole point of
putting a socket's front edge on the panel boundary. Board A's `IN` socket's
shell-leg copper comes to **0.55 mm of the x = 48 score**, inside the 0.40 mm
copper rule but with nothing spare. **Do not add copper there.**

### 7.3 Pours stay per board

**The generator already emits each board's four planes (ground on L1/F.Cu/
B.Cu, +3V3 on L3) over that board's own outline, and only that board's own
outline.** Do not replace them with one panel-wide pour. A pour that crosses
the V-score ties the two boards' grounds together electrically and leaves
copper sitting on the score line, which is exactly what section 7.1 says not
to do.

### 7.4 The mouse bites

**One routed channel, 2.00 mm wide, at y = 27..29** (the panel's only real
milling, out of the coupon side, so board A itself stays exactly 66.00 mm
tall). It has **four tabs**, at x **0..4, 12..17, 28..33 and 43.5..48**, and
**sixteen perforations, 0.50 mm diameter on a 1.00 mm pitch, centred on the
y = 29 break line**.

* **Keep copper away from the sixteen perforations by the normal hole
  clearance.**
* **Keep all four tabs completely free of tracks.** They get snapped off; a
  track through one is a track that gets torn.

### 7.5 After snapping: file the nubs

The perforations leave nubs of about 0.3 mm on the break edge. **Board A's
back edge, after separation, faces the HL2's magjack, whose clearance drops
from 1.0 mm to 0.7 mm with the board fitted.** Filing those nubs flat is a
**required assembly step**, not a cosmetic one — write it into the build
procedure, because it will not show up in any drawing or DRC.

### 7.6 Snap order

**The two rails first, then the x = 48 score, then the mouse bites.** Board
A's mini HDMI bodies overhang the y = 95 score by 0.50 mm into the top rail,
so taking that rail off first keeps the connectors clear of everything else
you do afterward.

### 7.7 Assembly service and the fab conversation

JLCPCB's **Economic** assembly service panelises by mouse-bite separations
only; **Standard** allows either mouse-bite or V-cut. This panel mixes both
(three V-scores and one mouse-bite break). **Confirm with JLCPCB before
ordering that they will accept the mix**; the fallback, if they will not, is
two separate orders — one per board, from the `hl2-bridge/` and
`tang-bridge/` projects directly.

---

## 8. DRC before you export

Run all of these, on **all three projects** (`hl2-bridge/`, `tang-bridge/`
and `panel/`), and expect zero:

1. **Clearance and track width** against the section 1.3 rules.
2. **Differential pair** rules: width, gap, and intra-pair length delta
   under 0.15 mm on every pair.
3. **Unrouted / unconnected nets: zero.** rev C's freshly generated projects
   start at **334** unconnected items on board A, **302** on board B and
   **499** on the panel. Those are the numbers KiCad's DRC reports before a
   single track is drawn, so each one is that project's own progress bar -
   watch it fall to zero. (The panel is fewer than 334 + 302 = 636 because
   the two boards' zones fill and connect a lot of the ground and power pads
   that DRC counts separately when each board is poured on its own.) Watch particularly for
   the nets that only appear on not-fitted parts - `VBIAS`, the AC-coupling
   capacitor nets, and the two unfitted `AUX` termination positions per board
   are real nets with real pads and they must be connected even though
   nothing is soldered to them.
4. **Copper to board edge 0.30 mm**, on `hl2-bridge/` and `tang-bridge/`
   against their real board edges. The mini HDMI shell pads are already at
   0.55 mm; nothing else should be anywhere near.
5. **On `panel/`: copper at least 0.40 mm from every V-score, component
   bodies at least 1.00 mm, and no track or pour crossing a score line at
   all** (section 7.2). This is the one check the geometry checker cannot do
   for you.
6. **On `panel/`: the two boards' nets are still separate.** No ratsnest line
   should cross x = 48. If one appears, it means a net lost its `A_`/`B_`
   prefix somewhere, not that a track is missing (section 7.1).
7. **On `panel/`: the routed channel and its sixteen perforations are
   intact**, with no copper closer than the normal hole clearance and no
   track through any of the four tabs (section 7.4).
8. **Solder mask sliver / minimum dam.** It will complain about the mini HDMI
   pads, whose 0.17 mm gap gives a 0.07 mm dam. **That one is expected and
   allowed** - it is the manufacturer's land pattern, and the KiCad footprint
   carries the `allow_soldermask_bridges` attribute to say so. Every *other*
   mask complaint is real.
9. **Plane integrity, by eye**: hide every layer except In1.Cu and look at it.
   On `hl2-bridge/` and `tang-bridge/` it should be one unbroken sheet of
   copper with nothing but via antipads in it. **On `panel/`, check this
   per board**: board A's ground pour should be one unbroken sheet within its
   own outline, board B's the same within its own outline, and the two should
   not touch anywhere. Then show the top layer too and check that no pair
   crosses an antipad row.
10. **Silkscreen over pads**, and check the socket labels — **`OUT`, `AUX`,
    `IN`** on both boards now, not rev B's `OUT 1`/`OUT 2`/`IN` or
    `IN 1`/`IN 2`/`OUT` — and the **`OUT GOES TO IN. AUX GOES TO AUX`** text
    are still legible after routing. Those labels stop somebody destroying a
    driver.

---

## 9. Export and ordering

**The panel (`panel/`) is what gets ordered.** The individual projects
(`hl2-bridge/`, `tang-bridge/`) exist for routing and bring-up, not for
placing an order, unless section 7.7's fallback applies.

### 9.1 Gerbers

EasyEDA Pro: **Fabrication > PCB Fabrication File (Gerber)**, from the
`panel/` project, which hands the order straight to JLCPCB. Confirm in the
order form:

| | |
|---|---|
| Layers | 4 |
| Thickness | 1.6 mm |
| Impedance control | **yes**, and name the stackup you designed to |
| Surface finish | ENIG if you can afford it - the mini HDMI's 0.23 mm pads solder more reliably on flat gold than on HASL |
| Copper weight | 1 oz outer / 0.5 oz inner (the default) |
| Min track/spacing | 0.127 mm |
| **Different designs in this file** | **2** |
| Remove order number | "specify a location" and put it on the bottom silkscreen |

### 9.2 BOM and CPL

The gerbers, BOM and CPL all come from `panel/` now — do not assemble from
the two individual projects' BOM/CPL files, which describe only one board
each. `panel-bom.csv` is the authoritative list. Columns: `Designator, Value,
Footprint, LCSC, MfrPart, Populate, Function, Note`.

**Every row whose `Populate` column says `DNP` must be marked "do not
place".** These are not decoration: fitting the AC-coupling capacitors
without also fitting the VBIAS network, fitting the direct-LVDS links on
board B, or fitting all four `AUX` termination positions instead of the two a
board's shipped role calls for, will stop the board working. The KiCad files
carry the DNP attribute - check it survived the import, part by part, before
you order assembly.

For the CPL, EasyEDA Pro generates it from your own placement, so it is
correct by construction. If you route in KiCad instead, use the Fabrication
Toolkit plugin, which writes JLCPCB's column order and picks up the `LCSC`
field.

### 9.3 Assembly

* **Standard PCBA**, not Economic, if you want JLCPCB to fit the through-hole
  headers and the connector shell legs — and see section 7.7: this panel's
  mixed V-score/mouse-bite panelisation needs Standard's more flexible rule
  in the first place, or a two-order fallback. Economic assembly is SMT-only,
  which on these boards means hand-soldering three (or six, on the panel)
  HDMI sockets' worth of shell legs plus every header.
* The LVDS drivers, receivers, the translators and buffer, and the ESD arrays
  are **Extended** parts, so expect the per-unique-Extended-part handling fee.
* **Assemble the top side only.** The only bottom-side parts are the HL2 /
  J14 sockets, which are through-hole and which you may well prefer to fit
  yourself anyway so you can check the fit against the real hardware first.
* **Order boards in multiples of 5** even for two sets.

### 9.4 Before you order: print the templates

`templates/` holds 1:1 PDFs of both boards. **Print
`hl2-bridge-1to1-TOP-fit-check.pdf` at 100 % (not "fit to page"), measure the
50 mm calibration rule on it, and only then lay it on the Hermes-Lite 2** with
the DB1 and DB12 holes over the headers. Do the same with
`tang-bridge-1to1-TOP-fit-check.pdf` on the Tang dock - **board B's J14
position is unverified** and this print is how you find out before spending
money (`DESIGN_NOTES.md` 6.5).

---

## 10. What to do if it does not work

In the order I would try them:

| Symptom | Look at |
|---|---|
| Nothing at all, no cable detected on `OUT`/`IN` | `*_HPD`: low means a cable is plugged in. Check the `RX MODE` jumper on both boards. (`AUX` has no HPD signal at all — it is detected by clock activity in the gateware, not by a pin, `PINMAP.md` 2.3.) |
| The `AUX` link does not come up, but `OUT`/`IN` are fine | Check both boards' ROLE straps. **Two boards strapped the same role is harmless but non-functional**: LVDS driver fights LVDS driver, which just garbles both directions - nothing is stressed, the link simply does not work (`PINMAP.md` 2.4). One board must read ROLE A, the other ROLE B. |
| The `AUX` G2 direction misbehaves at speed | First suspect: the uFL stub on the HL2's **PIN_72**, which this board cannot remove (`PINMAP.md` 6.2). Also check the HL2's own jumper **J25** — it must be **CLOSED**, or the `AUX` G2 clock net is dead outright, not just noisy. |
| The Gowin's delay sweep finds no eye on one forward lane | that lane's pair - a broken plane under it, or the necked fan-out too long. |
| Sweep finds no eye on *any* forward lane | the `OUT` clock. Scope board A's **`TP_HL2_CLK`** (the divided clock, after the 100R/660R divider, into the translator) and **`TP_DRVI_O_CLK`** (the translator's output into the driver). |
| Works cold, fails warm, or fails on one HL2 and not another | the 2.5 V threshold. Scope an HL2 output at U1's A-side pin; `DESIGN_NOTES.md` 3.2 has the numbers and the eight bypass links let you take the translator out of circuit. |
| Reverse lanes error but forward is clean | HL2 DB1 pins 11/15/17 are the tightest single-ended path on either board - 307.2 Mbit/s into a 1 k pull-up and an LED. `DESIGN_NOTES.md` 2.1. |
| Board B's status UART (the `IN` socket's SCL, landing on J14 pin 19) is garbled or dead | Check the Gowin constraint for that pin is **`IO_TYPE=LVTTL33`**, not `LVCMOS33`. `LVCMOS33`'s 2.0 V threshold leaves zero guaranteed margin against the HL2's 2.5 V driver; `LVTTL33`'s 1.7 V leaves 300 mV. `PINMAP.md` 5, note on pin 19. |
| The radio's noise floor rises when the link runs | intra-pair skew and pour stitching. Sections 4.1 and 5.3. Try lifting a cable shield at one of the 0 R shell links. |

rev B's fault-finding table had an entry for a slow single-ended command wire
dropping bytes above 10-25 Mbit/s. **That entry is gone**: rev C's control
channel is the differential, source-synchronous `AUX` cable, not a single
unshielded wire, so that failure mode no longer exists.
