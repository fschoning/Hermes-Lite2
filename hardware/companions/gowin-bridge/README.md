# gowin-bridge — two adapter PCBs for a 12-bit / 76.8 MSPS link between a Hermes Lite 2 and a Sipeed Tang Mega 138K

Two boards and two dual-link DVI-D cables carry the HL2's raw ADC stream to an
external Gowin GW5AST-138 FPGA and a reverse stream back.

* **Board A — `hl2-bridge/`** plugs onto the HL2's **DB1** (2x10) and **DB12** (3x2)
  headers. It drives cable 1 and receives cable 2.
* **Board B — `tang-bridge/`** plugs onto the Tang Mega 138K dock's **J14**
  (2x20, Bank 4). It receives cable 1 and drives cable 2.
* **`PINMAP.md`** is the authoritative wire-by-wire map. The FPGA gateware
  constraints must match it exactly.
* **`DESIGN_NOTES.md`** has the signal-integrity assumptions, the power budget,
  the mechanical clearances and everything that is unverified.
* **`STATUS.md`** says what is finished and what is not.

Both boards are **4-layer**: signal / ground / power / signal.

---

## 1. What the user has to solder

Only through-hole headers, on the **existing** boards. The bridge boards
themselves come assembled from JLCPCB, except the DVI sockets (see section 4).

| Board | What | Why |
|---|---|---|
| Hermes Lite 2 | A 2x10 0.1" male pin header at **DB1**, if not already fitted. Makerfabs-built boards normally ship with DB1 stuffed. | Board A's main connection. |
| Hermes Lite 2 | A 3x2 0.1" male pin header at **DB12**. Marked "do not install" in the HL2 BOM, so this one almost certainly has to be added. | Carries the status UART, the aux line and the two input-only pins that take the reverse clock and the fast serial lane. |
| Tang Mega 138K dock | A 2x20 0.1" male pin header at **J14** ("SDRAM1 CONN.", top edge next to the PMOD sockets). Ships as bare plated holes. | Board B's only connection. |
| Tang Mega 138K dock | Optionally a short ground wire from a PMOD socket's GND pin to board B's `GND AUX` header (J6). | J14 has exactly one ground pin. |

Nothing on either existing board is modified or removed.

---

## 2. The two ways to use board A

Board A is symmetric: seven independent LVDS **driver** channels feed the
socket labelled **OUT / FWD**, and seven independent LVDS **receiver** channels
are fed from the socket labelled **IN / REV**. Nothing is shared between a
driver channel and a receiver channel, so the same board works in either role.

**Always connect OUT to IN.** Never OUT to OUT.

### 2a. HL2 to Gowin (the main case)

```
HL2 --[board A]-- OUT/FWD ==cable 1==> IN/FWD --[board B]-- Tang dock J14
HL2 --[board A]-- IN/REV  <=cable 2== OUT/REV --[board B]-- Tang dock J14
```

### 2b. Two HL2 radios back to back (no Gowin)

Fit a board A in each radio and cross the two cables:

```
radio 1  OUT/FWD  ==cable 1==>  radio 2  IN/REV
radio 2  OUT/FWD  ==cable 2==>  radio 1  IN/REV
```

This needs a future HL2 gateware variant on both radios. On the receive side
each radio gets the forwarded 76.8 MHz clock plus six data lanes on its own
DB1/DB12 pins, exactly as in case 2a — no board change, no jumper change.
Cable pairs 4 and 5 are unused in this mode because the HL2 has no further
input pins; their receiver channels are still populated (they share a quad
package) and their outputs land on test points TP25/TP26.

For **coherent** two-radio operation the HL2's existing clock-chip coax link
(CL8/CL2) is still required and is not affected by board A. If a builder needs
DB1 pin 1 for that clock instead, cut solder link **R1** on board A, which
isolates board A from DB1 pin 1 (the net that reaches uFL pad CL8 through the
HL2's own jumper J25).

---

## 3. Importing into JLCPCB's EasyEDA Pro editor

The projects are written in KiCad 8 format. EasyEDA Pro reads KiCad files.

1. In EasyEDA Pro: **File > Import > KiCad**.
2. Select `hl2-bridge/hl2-bridge.kicad_sch`. When asked, also point it at the
   project folder so it picks up `gowin-bridge.kicad_sym` and
   `gowin-bridge.pretty/`; both are inside the same folder as the schematic,
   which is why the libraries were made project-local.
3. Check the import report. Every part should arrive with its `LCSC` property
   filled in — that is the field EasyEDA Pro uses to match the component to a
   JLCPCB assembly part. Parts whose `Populate` column in the BOM says `DNP`
   must be marked "do not place" in EasyEDA Pro; the KiCad files already carry
   the DNP attribute but check it survived the import.
4. **Design > Update PCB** to push the netlist into a new PCB document.
5. Import `hl2-bridge/hl2-bridge.kicad_pcb` as well if you want the placement
   and the board outline; otherwise draw the outline from the coordinates in
   `DESIGN_NOTES.md` section 6 and place by hand.
6. Repeat for `tang-bridge/`.

### Board setup in EasyEDA Pro

* **Layers:** 4. Assign **F.Cu = signal, layer 2 = GND plane, layer 3 = power
  plane, B.Cu = signal**. Do not let the inner layers become signal layers —
  the whole point of four layers here is an unbroken ground reference under
  every differential pair.
* **Stackup:** JLCPCB's standard 4-layer 1.6 mm stackup (0.2 mm core /
  1.065 mm prepreg / 0.2 mm core, 1 oz outer, 0.5 oz inner). With that stackup
  a 100 ohm differential pair on an outer layer over the layer-2 ground plane
  is roughly **0.20 mm trace width with a 0.13 mm gap**; confirm with EasyEDA
  Pro's impedance calculator against the exact stackup JLCPCB quotes you.

### DRC rules to set before routing

| Rule | Value | Why |
|---|---|---|
| Minimum trace width | 0.127 mm | JLCPCB 4-layer capability |
| Minimum clearance | 0.13 mm | JLCPCB 4-layer capability |
| Minimum via | 0.45 mm pad / 0.25 mm drill | JLCPCB standard |
| Trace to board edge | 0.3 mm | |
| Differential pair, LVDS nets | 0.20 mm width, 0.13 mm gap, 100 ohm | every `C1_*_P`/`C1_*_N` and `C2_*_P`/`C2_*_N` net |
| Intra-pair length match | **0.2 mm** | keeps skew under 1.5 ps, negligible against a 3.26 ns unit interval |
| Inter-pair length match | 2 mm is plenty | each lane is independently delay-adjusted in the FPGA |
| Power tracks | 0.6 mm minimum | board A draws up to ~150 mA at 3.3 V |

The KiCad projects already define net classes `LVDS100` (all DVI pair nets),
`Power` and `Default` with these numbers, and assign every pair net to
`LVDS100`, so if the import carries net classes across you get them for free.

---

## 4. Ordering from JLCPCB

1. **Gerbers.** In KiCad: `File > Fabrication Outputs > Gerbers`, all copper
   layers plus F/B silkscreen, F/B mask, Edge.Cuts; then
   `Fabrication Outputs > Drill Files` (Excellon, 2:4 metric, PTH+NPTH in one
   file). Zip the lot. In EasyEDA Pro: `Fabrication > PCB Fabrication File
   (Gerber)` does the same and hands the order straight to JLCPCB.
2. **BOM and CPL.** In KiCad the JLCPCB plugin (`Tools > External Plugins >
   Fabrication Toolkit`, install from the Plugin and Content Manager) writes
   `bom.csv` and `positions.csv` in JLCPCB's expected column order and picks up
   the `LCSC` field. Without the plugin: `File > Fabrication Outputs >
   Component Placement (.pos)` for the CPL and `Tools > Generate BOM` for the
   BOM, then rename the columns to `Comment, Designator, Footprint, LCSC Part #`
   and `Designator, Mid X, Mid Y, Layer, Rotation`.
   `<board>-bom.csv` in each project folder is already in a usable form and is
   the authoritative list, including which parts are DNP.
3. **Assembly service.** Choose **Economic PCBA** if every part resolves to a
   Basic or Preferred Extended part; the LVDS drivers, receivers, translator
   and ESD arrays are Extended parts, so expect the Extended-part handling fee.
   Select **Standard PCBA** if you also want JLCPCB to fit the through-hole
   headers; economic assembly is SMT-only.
4. **Through-hole parts.** The 2.54 mm sockets and the 1x3 / 2x2 headers can be
   fitted by JLCPCB under Standard PCBA. **The two DVI-D receptacles were not
   found in the LCSC catalogue** — order them separately (any DVI-D dual-link
   24+1 female, right-angle, through-hole receptacle matching the Molex
   74320-4004 land pattern) and solder them yourself. They are large
   through-hole parts with generous pads; this is an easy hand-solder job.
5. **Quantity.** Order boards in multiples of 5 (JLCPCB's minimum) even if you
   only need two sets.

---

## 5. Jumpers and links

| Board | Ref | Default | What it does |
|---|---|---|---|
| A | **J6** `3V3 SRC` | shunt on **1-2** | 1-2 takes the board's 3.3 V from HL2 DB1 pins 19/20. 2-3 takes it from the on-board LDO fed by the DVI +5 V line. |
| A | **J5** `RX MODE` | shunt on **2-3** | 2-3 = the cable-2 receivers are enabled only while cable 2 is plugged in (so the HL2's LED pins are never driven with no cable). 1-2 = force the receivers off. No shunt = always on. |
| A | **R1** `SL_D0` | fitted | Cut to isolate board A from DB1 pin 1, the HL2's PLL clock-output net. |
| A | **R20** `SL_FSER` / **R21** `SL_CMD` | R20 fitted, R21 not | Selects what drives HL2 PIN_89: the framed fast-serial lane (R20) or the slow command UART (R21). Never both. |
| A | **R36** `SL_VLVDS` | not fitted | Fit instead of U6 to take the level translator's 2.5 V reference from the HL2's own Vlvds rail on DB1 pins 7/8. |
| A | **J7** | not fitted | Header on the two spare reverse-lane receiver outputs. |
| B | **J4** `RX MODE` | shunt on **2-3** | Same scheme as board A's J5. Move to 1-2 to tri-state the cable-1 receivers, which is what the direct-LVDS experiment needs. |
| B | **R10…R23** | none fitted | The 14 direct-LVDS bypass links. Fitting them routes the cable-1 DVI pairs straight to the Gowin Bank 4 differential pairs; see `PINMAP.md` section 4.3 for what you lose. |
| B | **R60, R61** | not fitted | Optionally drive the two spare cable-2 lanes from J14 pins 40 and 39. |
| B | **J5** | not fitted | Drive the two spare cable-2 lanes from a flying lead instead. |

---

## 6. Regenerating the projects

Both projects are generated from one netlist description. **Do not hand-edit the
KiCad files** — change `tools/gen_gowin_bridge.py` and re-run it, and update
`PINMAP.md` in the same commit:

```
cd hardware/companions/gowin-bridge
python tools/gen_gowin_bridge.py
```

This rewrites the schematic, the PCB (placement and nets only, no tracks), the
project file, the project-local libraries and the BOM for both boards. UUIDs are
derived from the reference designators, so regenerating produces no spurious
diff. Once you start routing in KiCad or EasyEDA Pro, stop regenerating the PCB.
