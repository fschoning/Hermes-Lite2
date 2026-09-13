# gowin-bridge — Hermes Lite 2 SlimSAS bridge, rev D

**One design with two ends, on one board.** One schematic, one PCB, one BOM,
one project directory. The **radio end** plugs onto the Hermes-Lite 2; the
**Gowin end** plugs onto a Tang Mega 138K dock's J14. They are made together
and snapped apart. Two radio ends and one cable make a radio-to-radio link; a
radio end, a Gowin end and one cable make a radio-to-FPGA link.

The radio end:
A flat companion board that plugs onto the HL2's **DB1** (2×10), **DB12** (2×3)
and **CN1** (2×5 JTAG) headers and carries **one SlimSAS SFF-8654 8i
receptacle** on its front edge. A single $15 cable carries 16 differential
pairs and 16 sideband conductors.

| | |
|---|---|
| Board | radio end **64.50 × 64.88 mm**, 4 layer, 1.6 mm, HASL. HL2 x 70.00→134.50, y 73.37→138.25. The whole board, both ends, is **64.50 × 92.00 mm**, no rails, the ends joined by three mouse-bite tabs |
| Underside | 11.04 mm above the HL2's top surface (10.92 mm measured on the owner's radio), on 2.54 mm sockets and one M3 screw; holes over the radio's FPGA, AD9866 and T2 |
| Connector | Amphenol ICC **U10A474240T**, LCSC **C5432262** |
| Cable | 10Gtek **CAB-8654/8654-8i-P**, 8i to 8i, 0.5 m, **$15** |
| Lane rate | DDR at 153.6 MHz = **307.2 Mbit/s**, three lanes each way |
| Payload | **921.6 Mbit/s** each way = the complete raw 12-bit 76.8 MSPS ADC stream, plus a full-duplex auxiliary channel at the same rate |
| Parts | both ends: 184, of which **152 fitted**; 176 nets; **24 placed part numbers**, 16 Basic, 7 Extended and 1 Preferred Extended; eleven test points |
| Cost | **$162.43** for five assembled boards, both ends, delivered: **$32.49 per complete link** |
| State | schematic generated and validated; **prepared for Quilter**: fixed parts locked, everything else waiting off the board (`QUILTER.md`); **not placed, not routed** |

---

## The documents, and which to read first

| | |
|---|---|
| **`STATUS.md`** | **Start here.** What is built, what changed from rev C and why, the four numbers that were blocking the order, three corrections to the brief, six deliberate departures from it, everything unverified, and the next steps in order |
| `PINMAP.md` | **The pin contract.** Every HL2 header pin, all 74 connector contacts, the crossover, the lane and sideband maps, the AUXIO group, the enables, and the paste-ready Quartus block. Authoritative; `tools/check_netlist.py` asserts it |
| `DESIGN_NOTES.md` | Why, with the numbers. Data rates, the 2.5 V threshold problem and the part that does not exist, termination and edge rates, **the power budget**, **the ESD decision**, the mechanical argument, parts sourcing, the JTAG contention answer, and everything unverified |
| `COST.md` | The order total in the categories the fab actually bills, what could be cut and what it saves, and what is not verified in the numbers |
| `ROUTING.md` | The routing rules for whoever lays this out, in the order they matter |

---

## Files

```
bridge/                 the ONE KiCad project
  bridge.kicad_sch      schematic, ERC 0 violations
  bridge.kicad_pcb      fixed parts locked, the rest staged off the board;
                        placement regions and keepouts; DRC 0, parity 0
  bridge.kicad_pro      project file, with the differentialpair and Power
                        net classes
quilter-upload/         the three KiCad 10 files to upload to Quilter
  bridge-bom.csv        BOM with LCSC numbers and a Populate column
  gowin-bridge.kicad_sym, gowin-bridge.pretty/   project-local libraries
templates/              1:1 print templates for offering up to the radio
panel-endcap/           the re-cut front end panel - SEE THE WARNING BELOW
tools/
  gen_gowin_bridge.py   generates everything above from one netlist description
  check_netlist.py      asserts the pin maps, the crossover and the safety props
  check_geometry.py     asserts the locked parts, the land patterns and,
                        on a returned board, the placement and routing rules
  cost_model.py         computes the order total from the generated BOM and PCB
  kisexp.py             the KiCad s-expression reader/writer
```

**Anything that changes a net must be changed in `tools/gen_gowin_bridge.py`
and regenerated, never hand-edited in the KiCad files, and `PINMAP.md` must be
updated in the same commit.**

## To rebuild and validate

```
cd hardware/companions/gowin-bridge
python tools/gen_gowin_bridge.py
python tools/check_geometry.py     # must print OK
python tools/check_netlist.py      # must print OK
python tools/cost_model.py         # the order total
# bridge/bridge.kicad_dru is picked up by DRC: fast nets 3 mm from every edge

set KC=C:\Users\franz\AppData\Local\Programs\KiCad\10.0\bin\kicad-cli.exe
%KC% sch erc --severity-error -o bridge/bridge-erc.rpt bridge/bridge.kicad_sch
%KC% pcb drc --severity-error --schematic-parity --refill-zones ^
     -o bridge/bridge-drc.rpt bridge/bridge.kicad_pcb
```

---

## The front end panel

`panel-endcap/panel-endcap.kicad_pcb` (55 mm case, rev C) has the SlimSAS
opening at **panel x 120.30–144.30 = HL2 y 107.30–131.30**, centred on the
connector, 24.00 × 10.40 mm at 12.39–22.79 mm above the HL2's top surface.
Nine stock vent holes had to go where the opening landed; nine were put back
above it on 13 Sep 2026, so the vent area is the stock 73.7 mm². Order it
separately as a bare PCB. `G:/proj/Hermes-Lite2/franz-claude-analysis/HL2_END_PANEL.md`
has the derivation, clearances and strength check.

**Not compatible:** the repo's DB9 adapter board (`hardware/companions/db9/`)
cannot be fitted with this board; its wires land on DB1 pins our socket
covers. Run a Hardrock-50 from the N2ADR HL2 IO board instead
(`DESIGN_NOTES.md` §14.7).

## The Gowin end

A passive board: the same SlimSAS connector, 12 ESD arrays, 9 resistors and a
hand-fitted 2×18 onto J14 positions 5–40. Bank 4 of the Gowin FPGA drives and
receives true LVDS at its 3.3 V supply. Placed at the 40 mm case position.
`PINMAP.md` §11, `DESIGN_NOTES.md` §11, `gowin_end_j14.cst`.

## To order

JLCPCB, **Economic** assembly, **5 boards**, 4 layer, 1.6 mm, lead-free HASL,
green, 1 oz, delivered as a single PCB with the tabs unbroken. It is one
64.50 × 92.00 mm board with one outline and no rails; the two ends are joined
by three mouse-bite tabs. Ask JLCPCB first whether that counts as one design
(`DESIGN_NOTES.md` §13.2). Do not buy impedance control — `COST.md` §4 explains why.
`COST.md` §1 is the line-by-line.

Then hand-solder, per board: the DB1 2×10 socket and the DB12 2×3 socket and
the CN1 2×5 socket on the **underside**, the JTAG pass-through 2×5 header on
the **top**, and **the connector's four 2.2 mm shell tails**.

**Before any of that, buy one cable and ohmmeter it.** The whole one-design
argument rests on the cable crossing row A onto row B, and 10Gtek publish no
wiring diagram for this part. `STATUS.md` has the test.

**And do not fit or remove the board with the radio powered** — the hot-plug
inrush is about 22 A for 3.3 µs. It is on the silkscreen.
