# gowin-bridge status (branch `gowin-bridge-pcb`, rev D)

Last updated 2026-09-13. Worktree
`G:\proj\worktrees\Hermes-Lite2-gowin-bridge-pcb`.

**rev D is built. ONE DESIGN.** One schematic, one PCB, one BOM, one project
directory. rev C's two designs, three HDMI cables, upright riser card and
production panel are in git history and are superseded.

| | |
|---|---|
| `bridge/` | **165 parts (148 fitted), 116 nets.** ERC **0**, DRC **0** violations, schematic/PCB parity **0** |
| `tools/check_netlist.py` | **OK** — three header pin maps, all 74 connector contacts, the crossover walked, the mirroring contract, the radio-to-radio JTAG proof, the four enable pull-ups, all 48 conductors clamped, one design |
| `tools/check_geometry.py` | **OK** — every pad and courtyard inside the outline, no courtyard overlaps, no different-net pad closer than the clearance floor, all three HL2 socket grids match the radio, and all 78 SlimSAS pads recomputed from SFF-8654 Table A-1 |

DRC reports 328 unconnected items, which is the routing that is deliberately
left to be done in EasyEDA Pro.

**What is NOT done: the routing, and four physical measurements.** Neither can
be done from here.

---

## What rev D is

**One flat board, one cable.**

A SlimSAS SFF-8654 8i receptacle on the front edge carries **16 differential
pairs and 16 sideband conductors** over a single $15 cable. Every data lane is
DDR at 153.6 MHz = **307.2 Mbit/s**, three lanes each way, so each direction
carries the complete **921.6 Mbit/s** raw 12-bit 76.8 MSPS ADC stream, plus a
full-duplex auxiliary channel at the same rate.

**One design works at both ends because the cable crosses the rows.** SFF-9402
Rev 1.1 implementation note 16 and its Tables 6-2 and 6-3 define the 8i-to-8i
cable as a full crossover: contact A(n) at one end reaches contact B(n) at the
other, for all 37 positions, sidebands included. So the board drives row A and
listens on row B, and the identical board at the far end drives its row A into
this board's row B. Nothing is strapped and nothing is configured.

**And the row assignments are function-mirrored**, so radio-to-radio works with
no configuration at all: forward clock faces reverse clock, ADC data 0/1/2 face
transmit data 0/1/2, aux clock faces aux clock, aux data faces aux data.
`check_netlist.py` asserts that contract row by row and walks the whole cable
to prove it.

---

## The eight things that changed from rev C, and why

| | |
|---|---|
| **1. Three mini HDMI sockets and the riser card are gone.** | One SlimSAS 8i receptacle replaces them: 16 pairs where three HDMI cables gave 12, one 25.95 mm cable boot where three needed 52.1 mm, 9.90 mm above a flat board where the HDMI scheme needed an upright fin 8–28 mm tall with a right-angle soldered joint. The 970 N·mm tipping moment collapses to almost nothing even though the insertion force rises from 44.1 N to 55.5 N |
| **2. The ROLE strap is gone entirely** — no header, no shunt, no MOSFET inverter, no complement. | rev C needed it because the auxiliary lanes were bidirectional. In rev D every lane has a fixed direction and the crossover handles transmit meeting receive, so nothing needs a role. Its two surviving users — the AUXIO drive direction and JTAG over the cable — are now **gateware-controlled DC levels on FPGA pins 80 and 72**, each pulled UP at both ends of its translator so that pulled-up-is-disabled survives no gateware, an unconfigured FPGA, a missing translator and an unsoldered HL2 jumper. That is a **stronger** safety property than rev C's, because there is no longer a complementary pair whose two halves could disagree |
| **3. JTAG over the cable is new**, and it is gated, with a structural proof rather than just an enable. | Two sideband positions are deliberately left undriven, so in a radio-to-radio link **no radio can reach another radio's TCK or TMS at all**, whatever the enable does |
| **4. The board grew to reach CN1** and now extends HL2 x 70.00 → 134.50, y 73.30 → 138.25 = **64.50 × 64.95 mm** |
| **5. The connector is NOT in front of DB1**, and that was a hard finding, not a preference. | A right-angle receptacle lands its contacts 12.35–15.35 mm inboard and DB12's six holes are at 13.50 and 16.04 mm — through the middle of a 0.60 mm pitch pad field. No setback clears it. The connector moved along the edge to HL2 y 119.30, which works because the panel opens out with height |
| **6. ESD protects every conductor**, all 48, in twelve 0.5 pF arrays. rev C protected a subset with eight |
| **7. The board makes its own 2.5 V**, instead of offering the radio's Vlvds as the default | the radio's 2.5 V LDO is a 200 mA SOT-23-5 with perhaps 50 mA spare, and the rail it would brown out is the FPGA bank supply carrying the ADC data |
| **8. The production panel is gone.** | One design has nothing to snap apart. Order quantity 5 as five separate boards, which also dodges the $16.42 multi-design panel charge and the $23.80 loss of the flat promotional PCB tier |

---

## The four numbers that were blocking the order

### Power, and it is comfortable

| | |
|---|---|
| **This board on +3V3** | **299 mA computed, 350 mA design figure** |
| **This board on 2.5 V** | **41 mA computed, 50 mA design figure** — and it makes that rail itself, from +3V3, so the radio's Vlvds sees nothing |
| The radio's +3V3 | one **ST1S10PHR** buck, 3 A chip through a **2.4 A** inductor, with the designer's own annotation **"<=1.5A"** beside it on Power.sch, and an estimated **450 mA** of existing load |
| **Spare against that 1.5 A note** | **about 1.05 A. This board is 33 % of it** |
| Copper to DB1 pins 19/20 | **no series element of any kind** — no bead, resistor, fuse or TVS — narrowest segment 1.25 mm on an external layer, good for **2.8 A** |
| The radio's 2.5 V | **TPS73025DBVR**, a 200 mA LDO in SOT-23-5, already carrying the Ethernet RGMII I/O supply, four PLL supplies and VCCIO5, with the designer's note "150 mA sufficient for all 2.5V use" and an estimated 75 mA of existing load |
| **Spare there** | **50 mA safely, 125 mA as an absolute ceiling.** Which is exactly this board's need, which is why it does not take it |
| Inrush at power-up | 21.7 µF over the radio's ~1 ms soft start = **72 mA** of charging current. Nothing |
| Inrush on hot plug | **about 22 A for a 3.3 µs time constant.** **Do not fit or remove the board with the radio powered** — it is on the silkscreen, and it is why the bulk is 10 µF per rail and not 100 µF |

`DESIGN_NOTES.md` §4 has every term with its source, and labels the four
estimates that make up most of the radio's 450 mA as estimates.

### ESD: protect everything

**TPD4E05U06DQAR (LCSC C138714), 0.5 pF per channel, 12 arrays, 48 channels,
$0.84 a board plus one $3.07 loading fee.** 0.5 pF against a 100 Ω pair is
25 ps of added rise time on a 3.2552 ns unit interval — 0.8 %, electrically
free. No ESD array of any channel count is Basic tier in JLCPCB's library, and
the four Basic TVS parts that do exist are SMA/SMB power diodes that would not
clamp a 3.3 V line and would destroy a 307 Mbit/s lane. The 6- and 8-channel
alternatives are 1.6 pF and 9 pF, three to eighteen times over budget.

### The role strap: gone

Its only surviving user was going to be the AUXIO direction, and that is now a
gateware-driven DC level with a pull-up, which is simpler and safer than a
strap plus an inverter. See change 2 above and `PINMAP.md` §8.

### JTAG contention: a buffer, not just resistors

Series resistors bound the current but leave the level undefined, and an
undefined TCK can walk a TAP controller into an arbitrary state. **Both are
fitted**: a gated buffer whose enable is pulled up (so a locally plugged USB
Blaster always meets a tri-stated output, not a driver) and 330 Ω in series
(which bounds a fight to about 8 mA and costs 5 ns against a 41.7 ns TCK
period). `DESIGN_NOTES.md` §8.

---

## Three corrections to the brief, found by building it

### 1. Pins 90, 91, 103 and 104 are not the LED pins

Read out of `hardware/hl/hermeslite.net`: **the four indicator LEDs D2–D5 are
on FPGA pins 98, 99, 100 and 101** (DB1 pins 9, 11, 15, 17), each through a
1 kΩ resistor R71–R74 to +3V3. The 1.4 mA sink figure in the brief is correct
and belongs to those pins. **rev D's link already owns all four**, so the LEDs
become link-activity indicators whether anyone wants them to or not, and the
1.4 mA sink lands on this board's LVDS receiver outputs (which is in spec:
DS90LV048A VOL ≤ 0.25 V at 2 mA).

What pins 90, 91, 103 and 104 actually are: **CW/PTT ring and tip**, each with
a 2.2 kΩ pull-up and a **1 µF capacitor to ground** giving a 2.2 ms time
constant, and **the I2C1 bus** with 4.7 kΩ pull-ups on which sits **U6, the IDT
5P49V5923 VersaClock that generates the radio's master clock**. The mechanism
the brief asked for is built on them anyway, because remote keying and remote
clock-generator access are genuinely useful — but the default is read-only and
the DRIVE path needs a deliberate gateware assertion.

### 2. HL2 R2, R3 and R4 are pull-ups, not series resistors

`HL2_MECHANICAL_ENVELOPE.md` §12.1 called them "the existing series resistors
on TMS, TDI and TCK". The netlist says they are **10 kΩ pull-ups to +3V3**.
Nothing on the HL2 is in series with those three lines, so every series
resistor in the JTAG path is this board's.

### 3. Two SFF document titles in the brief are wrong

SFF-9402 Rev 1.1 is *Multi-Protocol Internal Cable Pinouts for SAS and/or
PCIe*, not "Multilane Copper Cable Assemblies". SFF-9400 Rev 1.1 is *Universal
4/8X Pinouts*, not "Multilane Copper Connector and Cable Assembly Overview".
This matters if anyone tries to search for them. And SFF-8654 itself contains
**no signal names at all** — its §3.1 delegates every signal assignment to
those two documents.

---

## Six deliberate departures from the brief

Each is argued where it lives; the table is so none of them is a surprise.

| Brief | What was done | Where |
|---|---|---|
| duplicate forward clock on a **spare channel of the same driver chip** | on the second driver, U5 channel 1 | `PINMAP.md` §5.2 — a quad driver has four channels and the forward group is five signals |
| JTAG on pairs 14–16 plus one more | JTAG on four **sideband** conductors | `DESIGN_NOTES.md` §9 — the mirroring rule consumes the 16 pairs as eight full-duplex lanes and seven are spoken for |
| FPGA pin 72 unused so J25 need not be soldered | pin 72 carries a DC enable level, and J25 stays **optional** | `PINMAP.md` §8 |
| bidirectional translator channels with **direction control** | two one-way paths, with an enable on the DRIVE path only | `PINMAP.md` §7 — the READ path then physically cannot drive an HL2 pin |
| series resistor "roughly 100 Ω" | **330 Ω** | `PINMAP.md` §7 — 7.4 mA worst case against the Cyclone IV's 25 mA sink limit, 3.4× of margin; 100 Ω gives 15.4 mA and 1.6× |
| "snapped apart after manufacture" | one design, five separate boards | `COST.md` §4 — with one design there is nothing to snap, and it saves $40.22 of PCB charges |

---

## Everything unverified

`DESIGN_NOTES.md` §10 has the full list. The ones that could stop the build:

| Item | Why it matters | How to settle it |
|---|---|---|
| **The cable's pin wiring** | The whole one-design argument rests on the A(n)↔B(n) crossover, and **10Gtek publish no wiring diagram for this part** — not the product page, not the catalogue, not the family datasheet. It is inferred from SFF-9402's own text and tables plus two third-party production drawings that match them exactly | **Buy one cable and ohmmeter it** before committing to fabrication. Confirm a contact in one plug's row A reaches the **other** row, same number, at the far end. Five minutes on a cable you are buying anyway |
| **The connector's front-face setback** | The one land-pattern dimension in no document I could read. The footprint's setback is 10.40 mm, derived, ±0.5 mm. It sets where the panel window goes, not whether the board works | Open Amphenol's drawing for U10A474240T — their server refuses automated fetching — or measure a part. Then cut the panel window |
| **M2, the 3.5 mm KEY jack's height**, and **M3, the clock SMAs' height** | Both sit **under** the board in the connector's y span. Expected 6–10 mm and 3–8 mm against an 11.04 mm underside | Callipers. M2 with and without a plug fitted |
| **HL2 R17** | 100 Ω wired between the DB12 pin 5 and pin 6 nets on the radio; if fitted it shorts the auxiliary clock input to the reverse clock input. **Not populated on the owner's radio** — a build prerequisite for anyone else | Look at the radio |
| **The three-socket tolerance stack** | J4 is the third rigid 2.54 mm socket on one board, 54.19 mm from DB1. §12.2 of the mechanical report puts the worst case at **±0.8 mm** against **±0.35 mm** comfortable | Print `templates/bridge-1to1-TOP-fit-check.pdf` at 100 %, measure its rule, offer it up. **The fallback needs no board change:** leave J4 off and run a flying 10-way IDC ribbon from CN1 to J5, which carries the same ten nets |
| **Whether JLCPCB will solder the connector's four through-hole shell tails** | $3.91, and whether the connector arrives mechanically anchored against 55.5 N of insertion force | Ask before paying. The costing assumes the owner does them |
| **Whether the Cyclone IV C8 fabric can capture 307.2 Mbit/s DDR** on ordinary bank-6 inputs | Gates every received lane. One input register per IOE, so DDR input needs soft logic at 153.6 MHz | Timing closure in Quartus, then the bench. No board change can fix it |

---

## The front end panel is at the wrong position for rev D

`panel-endcap/` was generated in an earlier pass, before rev D established
where the connector can actually go. **Its opening is at panel x 88.65-112.65
= HL2 y 75.65-99.65, in front of DB1** - the one place a right-angle SlimSAS
receptacle cannot sit, because DB12's six through-holes land in the middle of
its 0.60 mm pitch pad field.

**The opening must move +31.65 mm in panel x**, to **panel x 120.30-144.30 =
HL2 y 107.30-131.30**, centred on HL2 y 119.30. Its **vertical** position and
its size are already correct: 24.00 x 10.40 mm with 1 mm corner fillets at
panel y 74.91-85.31 = 12.39 to 22.79 mm above the HL2's top surface, which is
0.25 mm of clearance per side on a 23.50 x 9.90 mm shell standing on this
board's 12.64 mm top surface.

**One thing to resolve while moving it:** `endcaplib:speakervent` at panel
(145.50, 81.70) rotated 90 degrees has holes reaching to about panel x 140.5,
so it overlaps the new opening's x span. Move the vent or trim it.

That edit was deliberately **not** made here - it is panel layout, and layout
is a separate session's job. `franz-claude-analysis/HL2_END_PANEL.md` holds the
original derivation and its y-position conclusion is superseded.

---

## Next steps, in order

1. `cd G:\proj\worktrees\Hermes-Lite2-gowin-bridge-pcb\hardware\companions\gowin-bridge`
2. `python tools/gen_gowin_bridge.py`, then `python tools/check_geometry.py`
   and `python tools/check_netlist.py`. Both must print `OK`. Nothing below
   should start until they do.
3. **Buy one cable and ohmmeter it.** $15, and it is the one thing that could
   invalidate the architecture.
4. **Get Amphenol's drawing for U10A474240T** and check the front-face setback
   before cutting the panel.
5. **Print `templates/bridge-1to1-TOP-fit-check.pdf` at 100 %**, measure the
   30 mm rule on it, and offer it up to the radio — DB1, DB12 and CN1 at once.
   Fix anything that does not line up **in the generator**, not in the KiCad
   files.
6. **Measure M2 and M3**, the KEY jack and the clock SMAs.
7. **Check that HL2 R17 is not fitted.**
8. Route the board in EasyEDA Pro. The order that matters: the eight received
   pairs' 100 Ω terminations within 5 mm of the receiver pins; the twelve ESD
   arrays within 5 mm of the connector contacts; every single-ended HL2 net
   under 25 mm; the four forward-group pairs length-matched to each other.
9. **Move the front end panel's opening** +31.65 mm in panel x, and deal with
   the speaker vent. See the section above.
10. Order. `COST.md` §1. The order form's "different designs in this file"
    field is **1**.
11. Bring-up order: check the 3.3 V and 2.5 V rails; scope `TP_HL2_FWD_CLK_RAW`
    and `TP_HL2_FWD_CLK` (either side of the divider) and `TP_DI_FWDCLK` (the
    translator output into the driver); read `TP_SB_PRSNT_IN` with and without
    a cable; confirm `TP_JTAG_EN_N` and `TP_AUXIO_EN_N` both read HIGH with no
    gateware loaded — **that is the safety check and it should be done first**;
    then the forward link, then the reverse link, then the auxiliary link, then
    JTAG over the cable.

**Anything that changes a net must be changed in `tools/gen_gowin_bridge.py`
and regenerated, never hand-edited in the KiCad files, and `PINMAP.md` must be
updated in the same commit.**

---

## The FPGA side has to change to match

`gateware/variants/hl2b5up_gowinlink/gowinlink_pins.tcl` on branch
`gowin-link` (worktree `G:\proj\worktrees\Hermes-Lite2-gowin-link`) is marked
PROVISIONAL. `PINMAP.md` §9 is the paste-ready Quartus block. What changes from
rev C:

* **The ROLE strap read on PIN_89 is gone.** PIN_89 is now the auxiliary clock
  input.
* **PIN_72 and PIN_80 become two DC enable OUTPUTS**, active low, and they must
  **power up and stay high** until the gateware deliberately asserts them.
* **PIN_72, 80, 85 and 87 are no longer bidirectional.** All four have a fixed
  direction, which removes rev C's whole four-pin direction-from-strap
  requirement.
* **PIN_90, 91, 103 and 104 join the map** as the AUXIO group, and the gateware
  **must tri-state all four before asserting `gl_auxio_en_n`.**
* **PIN_98 needs its 8 mA drive strength**, not the 4 mA default: the new
  100 Ω / 470 Ω divider draws 5.8 mA.
* **DB12 pins 5 and 6:** the tcl's comment block already had these the right
  way round (PIN_88 = DB12 pin 6, PIN_89 = DB12 pin 5). Do not "fix" it to
  match rev A of `PINMAP.md`, which was wrong.

---

## What is still missing from the project

**A Gowin-side board.** rev D is the HL2-side design, and everything in the
brief — the pin allocation, the JTAG header, the spare-pin group, the power
budget, the board outline — is HL2-side. Two of these boards and one cable make
a radio-to-radio link today. A radio-to-Gowin link needs a Tang-dock board with
a SlimSAS receptacle wired to the mirror of `PINMAP.md` §5 and §6, and that is
not in this revision. rev C's `tang-bridge` project is in git history and its
J14 pin choices are still valid, but its connector, its sockets and its
direction logic all change.

---

## Validation commands used

```
set KC=C:\Users\franz\AppData\Local\Programs\KiCad\10.0\bin\kicad-cli.exe

python tools/gen_gowin_bridge.py
python tools/check_geometry.py
python tools/check_netlist.py

%KC% sch erc --severity-error -o bridge/bridge-erc.rpt bridge/bridge.kicad_sch
%KC% pcb drc --severity-error --schematic-parity --refill-zones ^
     -o bridge/bridge-drc.rpt bridge/bridge.kicad_pcb

%KC% pcb export drill --format excellon --drill-origin absolute ^
     --excellon-units mm --excellon-separate-th -o drl/ bridge/bridge.kicad_pcb

%KC% pcb export pdf --mode-single --scale 1 --black-and-white --drill-shape-opt 2 ^
     --exclude-value --layers "Edge.Cuts,Eco1.User,Dwgs.User,F.SilkS,F.Cu,F.Fab" ^
     -o templates/bridge-1to1-TOP-fit-check.pdf bridge/bridge.kicad_pcb
```

Results at the time of writing: **ERC 0 violations, DRC 0 violations,
schematic/PCB parity 0 issues, both checkers OK.** KiCad **10.0.6**; files are
written in KiCad 8 format.
