# Routing the two gowin-bridge boards in EasyEDA Pro

Written for someone who is comfortable with a PCB editor but is not a
high-speed specialist. It is specific to these two boards: where their hard
bits are, what the numbers actually are, and what you can safely ignore.

The KiCad projects contain **placement, nets, board outline, stackup and
zones, and no tracks at all**. Everything below is the routing.

Read `PINMAP.md` for what connects to what and `DESIGN_NOTES.md` for why.

---

## 0. The short version

| | Board A (`hl2-bridge`) | Board B (`tang-bridge`) |
|---|---|---|
| Size | 48.00 x 66.00 mm, 4 layer | 90.00 x 46.00 mm, 4 layer |
| Differential pairs to route | **16** (4 per socket x 3, two of them in two segments) | **12** |
| Fastest signal | 307.2 Mbit/s (the three reverse lanes) | 307.2 Mbit/s (the three reverse lanes) |
| The hard bit | **fanning out three 19-pin 0.40 mm-pitch mini HDMI footprints** | nothing, really - it has room |
| Time to expect | an evening | an hour or two |

Two things decide whether this board works, and neither is the trace
impedance:

1. **Every pair must have unbroken ground on layer 2 directly underneath it,
   for its whole length.** Nothing else you do matters as much.
2. **Every single-ended trace between an HL2 header pin and a chip input, or
   between a chip output and a J14 pin, must be under 25 mm.** These are the
   only unterminated fast nets on either board.

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
and the reflection from a 10 % mismatch at that length is invisible at a 1 ns
edge rate.

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
| `LVDS100` | every `*_P` / `*_N` net | 0.25 mm | 0.13 mm | **0.25 / 0.20 mm** |
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

Every pair net is named `<socket>_<lane>_P` / `<socket>_<lane>_N`, so
EasyEDA Pro's automatic pair detection finds all of them with no manual
pairing. The received pairs exist in **two segments** either side of the
AC-coupling option, and both segments follow the same convention:

```
connector  I_CLK_P  ---[ Cc || 0R link ]---  I_CLK_RX_P  --- receiver
           I_CLK_N  ---[ Cc || 0R link ]---  I_CLK_RX_N  --- receiver
```

Treat each segment as its own pair. The link/capacitor pads break the
coupling for about 1.5 mm; that is unavoidable and electrically harmless
(section 3.5).

---

## 2. Route in this order

The order matters because the mini HDMI fan-out has no freedom and
everything else has plenty.

1. **Board A: fan out the three mini HDMI footprints.** Section 3.1. Do this
   before anything else; it fixes where the pairs enter the board.
2. **Board B: fan out the three Type A footprints.** Section 3.2. Easier.
3. **The received pairs**, connector to receiver, as short as you can, with
   the termination resistor at the receiver end. Board A has 4, board B has 8.
   These are the pairs where length actually matters, because they carry
   307.2 Mbit/s on board A and because the receiver's input threshold is the
   most easily upset thing on either board.
4. **The driven pairs**, driver to connector. Board A has 8, board B has 4.
   These can be long; the driver does not care.
5. **The single-ended fast nets.** Board A: HL2 header pin -> U1 A-side, and
   U4 receiver output -> HL2 header pin. Board B: J14 pin -> driver input, and
   receiver output -> J14 pin. **All under 25 mm**, all on the bottom layer or
   the top, never crossing a pair.

   **Give `HL2_D3` (DB1 pin 4 to U1) the shortest of the seven.** That HL2 pin
   is `VREFB5N0` and carries about 21 pF of pin capacitance instead of the
   usual 7 pF, which already costs it 46 % of its unit interval in rise time
   (`DESIGN_NOTES.md` 2.2). It is the one single-ended net on board A where
   millimetres matter; the other six have three times the margin.
6. **Power.** 0.60 mm minimum, and see section 6.
7. **The slow lines, HPD, +5 V and the test points.** Route these loosely,
   last, anywhere.
8. **Pour and stitch.** Section 5.

---

## 3. The fan-outs

### 3.1 Board A: three mini HDMI footprints at 0.40 mm pitch

This is the whole difficulty of board A. Each socket has **19 pads, 0.23 mm
wide, 1.20 mm long, on a 0.40 mm pitch, leaving 0.17 mm between pads**, in one
row 7.15 mm in from the board edge.

**The good news, and it is very good news: Type C puts the two legs of every
pair on adjacent pads, with a ground pad between pairs.**

| pad | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| | GND | **D2+** | **D2-** | GND | **D1+** | **D1-** | GND | **D0+** | **D0-** | GND | **CLK+** | **CLK-** |

So the fan-out is: pair, ground, pair, ground, pair, ground, pair. Do this:

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
SCL, +5 V and HPD are slow: route them out on 0.25 mm with no impedance
control, on whichever side is convenient.

The four shell legs sit in plated slots at x = +/-5.425 mm from each socket
centre and the two locating pegs are Ø0.99 mm holes at +/-3.75 mm. **Ring each
socket's shell slots with ground vias** - the shell is the cable's shield
return and it needs a low-inductance path to the plane, not a single trace.

**The outermost copper on board A is a shell-leg pad 0.55 mm from the board
edge.** That is inside JLCPCB's 0.30 mm rule but it is the tightest place on
the board; don't add anything out there.

### 3.2 Board B: three Type A footprints at 0.50 mm pitch

Easier in every way - 0.50 mm pitch, 0.30 mm pads, and the board has room -
but the pin ordering is **worse** than Type C for fan-out, because Type A puts
the shield pad *between* the two legs of each pair:

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
have no copper. Pads 15 (SCL), 18 (+5 V) and 19 (HPD) are slow.

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

### 3.4 How far pairs must stay from everything else

| From | To | Minimum | Why |
|---|---|---|---|
| pair edge | any other net | **0.60 mm** (3x the 0.20 mm pair gap) | crosstalk falls roughly as the square of separation; 3x the intra-pair gap puts the coupling 10x below the intra-pair coupling |
| pair edge | another pair's edge | **0.75 mm** | as above, plus the neighbour is also a fast edge |
| pair edge | ground pour | **0.60 mm**, or cut the pour away | a pour 0.2 mm from a 0.25/0.20 pair pulls the differential impedance down by roughly 15 % |
| a 307.2 Mbit/s reverse pair | the 76.8 MHz forward clock pair | **as far as the board allows** | the forward clock is the timing reference for the whole forward link; noise on it becomes jitter on all six data lanes |

Board B has one specific crosstalk problem worth care: **on J14 the A (even)
pins carry received signals and the B (odd) pins carry transmitted ones, on
adjacent header pins**, because only 16 usable pins exist (`PINMAP.md` 5.1).
Over the short run from the socket to the chips, a 307.2 Mbit/s output sits
2.54 mm from a 153.6 Mbit/s input. Route the two groups on opposite layers
where you can, and put a grounded via fence between them where you cannot.

### 3.5 Where the passives go, relative to the receiver

For each received pair, the order from the connector inwards is fixed:

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

The Gowin receiver retimes **every forward lane independently**: an `IODELAY`
per lane with 256 taps of 12.5 ps, a total adjustment range of about
**3.2 ns**, swept at power-up until each lane's eye is centred
(`gateware/gowinlink/LINK_SPEC.md` sections 6.1 and 6.2).

Budgeting half that range for board and cable skew gives 1.6 ns, which at
6.0 ps/mm is **265 mm of permissible lane-to-lane mismatch**.

Board A's longest pair is about 45 mm and its shortest about 20 mm. That 25 mm
spread is **150 ps, which is 4.7 % of the adjustment range.** It is nothing.

**So: do not add a single serpentine anywhere for lane-to-lane matching.** Do
not match a data lane to its clock either - the clock is the reference the
`IODELAY` sweep moves the data against, so board skew between clock and data
is exactly what the sweep is for.

The reverse direction is looser still. The HL2 has no per-lane delay
adjustment, but it has a word-alignment search that absorbs up to +/-8 bit
positions (`LINK_SPEC` 6.3), and a bit is 3.26 ns, so the tolerance is tens of
nanoseconds. Within a bit you want skew under about 0.5 ns, which is 83 mm.
Also nothing.

The one thing that *does* consume the adjustment range is the fixed offset the
level translator adds, and that is handled on the schematic rather than in the
layout: forward clock A goes through the same SN74AVC8T245 package as the data
so they share one propagation delay (`DESIGN_NOTES.md` 3.2). Don't defeat that
by routing the clock a very different length from the data - keep it within,
say, 20 mm of the data lanes, which happens naturally.

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
* **Board B's AMS1117 (U4) tab**: flood it to the layer-3 plane with at least
  six 0.3 mm thermal vias. It dissipates (5.0 - 3.3) x 0.106 = **0.18 W**, or 0.25 W with every chip at its datasheet maximum.
* **Board B has exactly one ground pin on J14 (pin 12).** Give it the widest,
  shortest possible connection to the plane - a via right at the pad, plus a
  ring of vias around it - and fit the ground wire to the `GND AUX` header J6.
  That wire is not optional in practice (`DESIGN_NOTES.md` 5).

### 5.4 Layer 3, the power plane

* Board A: mostly `+3V3`, with a **`+2V5` island** covering U1 and U5 (it is
  already drawn in the KiCad file at local x 13-27, y 2-28). The island is a
  cut in the +3V3 plane, not in the ground plane, so it costs nothing - but
  check that no pair runs over the island's boundary on the top layer anyway,
  because it is free to avoid.
* Board B: `+3V3` throughout.
* Keep every decoupling capacitor's ground via within 1 mm of its pad.

---

## 6. Power and the slow nets: route these loosely

* **0.60 mm minimum** on `+3V3`, `+2V5`, `DB1_3V3`, `LDO3V3` and `P5V_*`.
  Board A draws about 112 mA and board B about 106 mA (`DESIGN_NOTES.md` 5),
  so current is not the issue - inductance to the decoupling capacitors is.
* Get `DB1_3V3` from DB1 pins 19/20 to the J6 shunt to the plane in as few
  millimetres as possible, with the 100 nF entry capacitor right at the header.
* **The slow lines** (`*_SLOW`), **HPD** (`*_HPD`), **+5 V pins** and all the
  test points have no timing requirement worth respecting. 0.25 mm, anywhere,
  any layer. The only rule: **do not run a slow line alongside a pair for more
  than a few millimetres**, because the slow lines go out on an unshielded
  cable conductor and will happily carry away whatever they pick up.
* `RXEN_N` is a DC level. Ignore it.

---

## 7. DRC before you export

Run all of these, and expect zero:

1. **Clearance and track width** against the section 1.3 rules.
2. **Differential pair** rules: width, gap, and intra-pair length delta
   under 0.15 mm on every pair.
3. **Unrouted / unconnected nets: zero.** The KiCad files start with 278
   unconnected items on board A and 306 on board B; that number is your
   progress bar and it must reach zero. Watch particularly for the nets that
   only appear on not-fitted parts - `VBIAS` and the AC-coupling capacitor
   nets are real nets with real pads and they must be connected even though
   nothing is soldered to them.
4. **Copper to board edge 0.30 mm.** The mini HDMI shell pads are already at
   0.55 mm; nothing else should be anywhere near.
5. **Solder mask sliver / minimum dam.** It will complain about the mini HDMI
   pads, whose 0.17 mm gap gives a 0.07 mm dam. **That one is expected and
   allowed** - it is the manufacturer's land pattern, and the KiCad footprint
   carries the `allow_soldermask_bridges` attribute to say so. Every *other*
   mask complaint is real.
6. **Plane integrity, by eye**: hide every layer except In1.Cu and look at it.
   It should be one unbroken sheet of copper with nothing but via antipads in
   it. Then show the top layer too and check that no pair crosses an antipad
   row.
7. **Silkscreen over pads**, and check the six socket labels (`OUT 1`,
   `OUT 2`, `IN` / `IN 1`, `IN 2`, `OUT`) and the `OUT goes to IN` text are
   still legible after routing. Those labels stop somebody destroying a
   driver.

---

## 8. Export and ordering

### 8.1 Gerbers

EasyEDA Pro: **Fabrication > PCB Fabrication File (Gerber)**, which hands the
order straight to JLCPCB. Confirm in the order form:

| | |
|---|---|
| Layers | 4 |
| Thickness | 1.6 mm |
| Impedance control | **yes**, and name the stackup you designed to |
| Surface finish | ENIG if you can afford it - the mini HDMI's 0.23 mm pads solder more reliably on flat gold than on HASL |
| Copper weight | 1 oz outer / 0.5 oz inner (the default) |
| Min track/spacing | 0.127 mm |
| Remove order number | "specify a location" and put it on the bottom silkscreen |

### 8.2 BOM and CPL

`<board>-bom.csv` in each project folder is the authoritative list. Columns:
`Designator, Value, Footprint, LCSC, MfrPart, Populate, Function, Note`.

**Every row whose `Populate` column says `DNP` must be marked "do not place".**
There are 31 of them on board A and 51 on board B, and they are not
decoration: fitting the AC-coupling capacitors without also fitting the VBIAS
network, or fitting the direct-LVDS links on board B, will stop the board
working. The KiCad files carry the DNP attribute - check it survived the
import, part by part, before you order assembly.

For the CPL, EasyEDA Pro generates it from your own placement, so it is
correct by construction. If you route in KiCad instead, use the Fabrication
Toolkit plugin, which writes JLCPCB's column order and picks up the `LCSC`
field.

### 8.3 Assembly

* **Standard PCBA**, not Economic, if you want JLCPCB to fit the through-hole
  headers and the connector shell legs. Economic assembly is SMT-only, which
  on these boards means you hand-solder three HDMI sockets' worth of shell
  legs per board plus every header.
* The LVDS drivers, receivers, both translators and the ESD arrays are
  **Extended** parts, so expect the per-unique-Extended-part handling fee.
* **Assemble the top side only.** The only bottom-side parts are the HL2 /
  J14 sockets, which are through-hole and which you may well prefer to fit
  yourself anyway so you can check the fit against the real hardware first.
* **Order boards in multiples of 5** even for two sets.

### 8.4 Before you order: print the templates

`templates/` holds 1:1 PDFs of both boards. **Print
`hl2-bridge-1to1-TOP-fit-check.pdf` at 100 % (not "fit to page"), measure the
50 mm calibration rule on it, and only then lay it on the Hermes-Lite 2** with
the DB1 and DB12 holes over the headers. Do the same with
`tang-bridge-1to1-TOP-fit-check.pdf` on the Tang dock - **board B's J14
position is unverified** and this print is how you find out before spending
money (`DESIGN_NOTES.md` 6.5).

---

## 9. What to do if it does not work

In the order I would try them:

| Symptom | Look at |
|---|---|
| Nothing at all, no cable detected | `*_HPD`: low means a cable is plugged in. Check the `RX MODE` jumper on both boards. |
| The Gowin's delay sweep finds no eye on one lane | that lane's pair - a broken plane under it, or the necked fan-out too long. Lane 0 on board A is also the suspect if it is *only* lane 0: that net carries the HL2's uFL stub CL8 (`PINMAP.md` 7.2). |
| Sweep finds no eye on *any* lane | the forward clock. Scope `TP_HL2_CLKA` and `TP_DRVI_O1_CLK`. |
| Works cold, fails warm, or fails on one HL2 and not another | the 2.5 V threshold. Scope an HL2 output at the translator's A-side pin; `DESIGN_NOTES.md` 3.2 has the numbers and the eight bypass links let you take the translator out of circuit. |
| Reverse lanes error but forward is clean | HL2 DB1 pins 11/15/17 are the tightest single-ended path on either board - 307.2 Mbit/s into a 1 k pull-up and an LED. `DESIGN_NOTES.md` 2.1. |
| The radio's noise floor rises when the link runs | intra-pair skew and pour stitching. Sections 4.1 and 5.3. Try lifting a cable shield at one of the 0 R shell links. |
| The command channel drops bytes | expected above roughly 10-25 Mbit/s; it is a single unshielded wire now. `PINMAP.md` 3.3. Fit the 33 pF ringing damper. |
