# gowin-bridge — two adapter PCBs for a 12-bit / 76.8 MSPS link between a Hermes Lite 2 and a Sipeed Tang Mega 138K

Two boards and **three HDMI cables** carry the Hermes Lite 2's raw ADC stream
to an external Gowin GW5AST-138 FPGA, and a reverse stream back. The same
HL2-side board also links **two HL2 radios directly to each other** with two
cables and no Gowin at all.

* **Board A — `hl2-bridge/`** plugs onto the HL2's **DB1** (2x10) and **DB12**
  (3x2) headers. Three **mini HDMI (Type C)** sockets: `OUT 1`, `OUT 2`, `IN`.
  48.00 x 66.00 mm, 4 layer.
* **Board B — `tang-bridge/`** plugs onto the Tang Mega 138K dock's **J14**
  (2x40, Bank 4). Three **full-size HDMI (Type A)** sockets: `IN 1`, `IN 2`,
  `OUT`. 90.00 x 46.00 mm, 4 layer.

| Document | What is in it |
|---|---|
| **`PINMAP.md`** | The authoritative wire-by-wire map. The FPGA gateware constraints must match it exactly. |
| **`ROUTING.md`** | Step-by-step routing instructions for EasyEDA Pro, with the numbers. |
| **`DESIGN_NOTES.md`** | Signal-integrity assumptions, the 2.5 V threshold resolution, the mechanical arithmetic, the power budget, and everything unverified. |
| **`STATUS.md`** | What is done, what is partial, exact next steps. |
| **`templates/`** | 1:1 printable PDFs to offer up to the real hardware **before ordering**. |

---

## 1. Always connect OUT to IN

That is the whole rule, and it is the reason the sockets are labelled the way
they are. **Never OUT to OUT** (two drivers fighting each other) and **never
IN to IN** (no driver at all).

The trick that makes this work is that **the role belongs to the socket, not to
pins inside it**. An `OUT` socket drives all four pairs and the slow wire; an
`IN` socket receives all four pairs and the slow wire; the pair ordering and
the slow-wire pin are identical on both. So a straight pin-1-to-pin-1
mini-to-mini cable joins any OUT to any IN and everything lands where it
should — which is what lets one board design sit at **both** ends of a
two-radio link. `PINMAP.md` section 1.

---

## 2. The two ways to use it

### 2a. HL2 to Gowin — three cables

```
radio  OUT 1  ==>  IN 1   Tang dock
radio  OUT 2  ==>  IN 2   Tang dock
radio  IN     <==  OUT    Tang dock
```

Forward: two cables, three data lanes each at 153.6 Mbit/s, plus **its own copy
of the 76.8 MHz clock in each cable** so the two cables' lengths do not have to
match. 6 x 153.6 = **921.6 Mbit/s = 12 bits x 76.8 MSPS**, the entire ADC
stream with no compression and no framing overhead.

Reverse: one cable, three lanes at 307.2 Mbit/s, also 921.6 Mbit/s, plus the
153.6 MHz reverse clock and the command channel.

### 2b. Two HL2 radios back to back — two cables, no Gowin

Fit a board A in each radio and cross two **mini-to-mini** cables:

```
radio 1  OUT 1  ==>  IN  radio 2
radio 2  OUT 1  ==>  IN  radio 1
```

Each radio's **`OUT 2` stays empty.** Each direction carries one clock plus
three data lanes at 153.6 Mbit/s, so **460.8 Mbit/s each way — three times the
153.6 Mbit/s of the HL2's existing one-pair DB12 two-radio link.**

The same hardware would carry the full 921.6 Mbit/s if the gateware clocked
those three lanes at 153.6 MHz DDR instead of 76.8 MHz (307.2 Mbit/s per lane),
which is the `GL_LANES = 3` geometry the gateware already has. That runs into
the tightest single-ended margin on the board, though — see `DESIGN_NOTES.md`
section 2.1 — so 460.8 Mbit/s is the number to design to.

This needs a future HL2 gateware variant on both radios. No board change and
no jumper change: each radio's `IN` socket already feeds the forwarded clock
and three data lanes onto its own DB1/DB12 pins exactly as in case 2a.

For **coherent** two-radio operation the HL2's existing clock-chip coax link
(CL8/CL2) is still required. Board A does not affect it — but note that DB1
pin 1 shares a net with the uFL pad CL8 through the HL2's own jumper J25, so
J25 must stay closed (`PINMAP.md` 7.2). If a builder needs DB1 pin 1 free, cut
solder link **R1** on board A.

---

## 3. Which cables to buy

| For | Cable | Note |
|---|---|---|
| HL2 to Gowin (3 off) | **mini HDMI (Type C) male to full-size HDMI (Type A) male** | The commonest camera / tablet cable. Any length up to a few metres is electrically fine. |
| HL2 to HL2 (2 off) | **mini HDMI (Type C) male to mini HDMI (Type C) male** | Less common than the mini-to-full-size, but sold as a camera cable. Must be straight-through, which every standard cable is. |

**Measure the moulded plastic boot on the mini HDMI end with calipers before
you commit to the board.** Three mini HDMI sockets sit on a 17.40 mm pitch,
which is the widest the 48 mm board allows, and **nobody publishes the boot
width** — it is somewhere between 15.6 and 17.3 mm depending on the brand.
Under the optimistic estimate there is 1.8 mm between adjacent boots; under the
pessimistic one, 0.08 mm. `DESIGN_NOTES.md` section 6.3 has the arithmetic and
four fallbacks if your cables are fat. The two-radio configuration uses only
the outer two sockets, 34.80 mm apart, so it can never be affected.

Do **not** buy a cable with a moulded right-angle plug unless you have checked
which way it bends: the sockets are at the board edge with 12 mm of vertical
room.

---

## 4. What you have to solder

Only through-hole headers, and only on the **existing** boards. The bridge
boards themselves come assembled from JLCPCB.

| Board | What | Why |
|---|---|---|
| Hermes Lite 2 | A 2x10 0.1" male pin header at **DB1**, if not already fitted. Makerfabs-built boards normally ship with DB1 stuffed. | Board A's main connection. |
| Hermes Lite 2 | A 3x2 0.1" male pin header at **DB12**. Marked "do not install" in the HL2 BOM, so this one almost certainly has to be added. | Carries the status UART, the second forward clock, and the two input-only pins that take the reverse clock and the command channel. |
| Hermes Lite 2 | Check that jumper **J25** is closed. | Forward lane 0 reaches FPGA PIN_72 only through it. |
| Hermes Lite 2 | A custom rear endcap with one **52.2 x 12.0 mm slot**. The endcaps are 0.8 mm PCBs (`hardware/enclosure/endcaps/`). | The three cables come out of the RF end of the case. `DESIGN_NOTES.md` 6.5. |
| Tang Mega 138K dock | A 2x20 0.1" male pin header at **J14** ("SDRAM1 CONN.", top edge next to the PMOD sockets). Ships as bare plated holes. | Board B's only connection. |
| Tang Mega 138K dock | A short ground wire from a PMOD socket's GND pin to board B's `GND AUX` header (J6). | J14 has exactly one ground pin and that is not enough for eight CMOS outputs switching at up to 307 Mbit/s. **Not optional in practice.** |

Nothing on either existing board is modified or removed.

**On board A you may also want to clip the stack-through tails** of DB1
positions 1-6, 9, 11, 15 and 17 before stacking any other companion board on
top. Those ten positions carry link signals; the silkscreen says so.

---

## 5. Jumpers, links and options

| Board | Ref | Default | What it does |
|---|---|---|---|
| A | **J6** `3V3 SRC` | shunt on **1-2** | 1-2 takes the board's 3.3 V from HL2 DB1 pins 19/20. 2-3 takes it from U7, the on-board LDO fed by the `IN` socket's HDMI +5 V pin — which needs U7 and `SL_5V` fitted, and both are not fitted by default. |
| A | **J7** `RX MODE` | shunt on **2-3** | 2-3 = the `IN` receiver is enabled only while a cable is plugged into `IN`, so the HL2's LED pins are never driven with no cable. 1-2 = force off. No shunt = always on. |
| A | **R1** `SL_D0` | fitted | Cut to isolate board A from DB1 pin 1, the net that reaches uFL pad CL8 through the HL2's jumper J25. |
| A | `SL_BYP1..8` | **not fitted** | Eight links that bypass the SN74AVC8T245 level translator. Only for the bench experiment in `DESIGN_NOTES.md` 3.3; if you fit them, remove U1 and the 470 R divider leg too. |
| A | `SL_VLVDS` | not fitted | Reference the translators' 2.5 V side to the HL2's own `Vlvds` rail (DB1 pins 7/8) instead of U6. Do not fit together with U6. |
| A | `SL_5V` + **U7** | not fitted | The HDMI +5 V supply path. Read `DESIGN_NOTES.md` 5.1 before fitting: there is no 5 V source at all in the two-radio configuration. |
| A, B | AC-coupling parts | **not fitted** | Per received pair: two 100 nF capacitors and two 4k7 bias resistors, plus one shared 1k8/1k0 `VBIAS` divider. Boards ship **DC-coupled** through 0 R links. `DESIGN_NOTES.md` 4 says why, and what has to be true of the gateware first. |
| A, B | 33 pF on the slow line | not fitted | Fit if the unterminated cable wire rings enough to double-clock the receiver. |
| B | **J5** `RX MODE` | shunt on **2-3** | Same scheme as board A's J7, for both `IN` receivers. Move to 1-2 for the direct-LVDS experiment. |
| B | **J6** `GND AUX` | — | Fit the ground wire. See section 4. |
| B | direct-LVDS links | **not fitted** | 14 links that route the received pairs straight into the Gowin's Bank 4 differential pairs with no receiver chip. `PINMAP.md` 5.3 lists what you lose: the whole `OUT` socket. |
| B | `SL_5V_OUT` | not fitted | Puts the dock's 5 V on the `OUT` socket so board A could run from it. |

---

## 6. Importing into JLCPCB's EasyEDA Pro editor

The projects are written in KiCad 8 format and open in KiCad 8, 9 and 10.
**`ROUTING.md` is the full procedure**; the import itself is:

1. EasyEDA Pro: **File > Import > KiCad**.
2. Select `hl2-bridge/hl2-bridge.kicad_sch`, and point it at the project folder
   so it picks up `gowin-bridge.kicad_sym` and `gowin-bridge.pretty/` — both
   are inside the schematic's own folder, which is why the libraries were made
   project-local.
3. Check the import report. Every part should arrive with its `LCSC` property
   filled in; that is the field EasyEDA Pro uses to match a component to a
   JLCPCB assembly part.
4. **Check the DNP flags survived.** 31 parts on board A and 51 on board B are
   marked "do not place" and they are not decoration — `ROUTING.md` 8.2.
5. **Design > Update PCB** to push the netlist into a new PCB document, and
   import `hl2-bridge.kicad_pcb` as well to get the placement and outline.
6. Repeat for `tang-bridge/`.

Neither board has a single track. Routing is `ROUTING.md`.

---

## 7. Ordering

**Print the templates and check the fit first.** `templates/` holds 1:1 PDFs.
Print at 100 %, measure the 50 mm calibration rule on the paper, then lay
`hl2-bridge-1to1-TOP-fit-check.pdf` on the Hermes Lite 2 and
`tang-bridge-1to1-TOP-fit-check.pdf` on the Tang dock. **Board B's J14
position is a guess** and this print is how you find out cheaply.

Then:

1. **Boards.** 4 layer, 1.6 mm, impedance-controlled, ENIG if affordable (the
   mini HDMI's 0.23 mm pads solder more reliably on flat gold than on HASL).
   Multiples of 5.
2. **Assembly.** **Standard PCBA**, not Economic, if you want JLCPCB to fit the
   through-hole headers and the connector shell legs — Economic is SMT-only.
   Top side only; the only bottom-side parts are the two HL2 sockets and board
   B's J14 socket, which are through-hole and which you may prefer to fit
   yourself after checking the fit.
3. **BOM.** `<board>-bom.csv` in each project folder is authoritative, including
   which parts are DNP.
4. **Cost.** See section 8.

The LVDS drivers, receivers, both translators and the ESD arrays are
**Extended** LCSC parts, so expect the per-unique-Extended-part handling fee.

---

## 8. Cost

Per-line LCSC numbers are in `<board>-bom.csv`. Verified unit prices, read on
12 September 2026:

| Part | LCSC | Per board | Unit price at qty 10 |
|---|---|---|---|
| Mini HDMI Type C, XKB A71-05H4-111N1 | C2682170 | 3 (board A) | $0.4593 |
| Full-size HDMI Type A, Amphenol 10029449-111RLF | C427307 | 3 (board B) | $0.5081 |

So the connectors alone are **$1.38 per board A and $1.52 per board B**.

Everything else — the two LVDS drivers, three receivers, two translators, 17
ESD arrays, three LDOs, the four headers and roughly 200 passives across the
two boards — has **not been priced**, and the total also depends on JLCPCB's
setup, stencil and Extended-part fees, which change. `STATUS.md` lists this as
an open item with the exact part list to quote.

What can be said without a quote: the only parts likely to cost more than a
few cents each are the **DS90LV047A** and **DS90LV048A** (TI, Extended) and
the **SN74AVC8T245**. Everything else is commodity.

---

## 9. Regenerating the projects

Both projects are generated from one netlist description. **Do not hand-edit
the KiCad files** — change `tools/gen_gowin_bridge.py`, re-run it, and update
`PINMAP.md` in the same commit:

```
cd hardware/companions/gowin-bridge
python tools/gen_gowin_bridge.py     # writes both projects
python tools/check_geometry.py       # placement and the HL2 hole grid
python tools/check_netlist.py        # the pin maps and the OUT-to-IN symmetry
```

**`check_geometry.py`** reads the generated PCBs back and verifies that every
pad and courtyard is on the board, that nothing overlaps, and that **board A's
DB1 and DB12 socket holes land on the Hermes Lite 2's own hole grid**,
recomputed independently from `hardware/hl/hermeslite.kicad_pcb` rather than
copied from the generator.

**`check_netlist.py`** exports both netlists and verifies the two things ERC
cannot see: that the HL2 DB1/DB12 and Tang J14 header pins carry exactly the
nets `PINMAP.md` says (and that every other J14 pin is electrically open, so
the dock's PMOD sockets and camera FPC stay usable), and that **all six
sockets share one signal-to-role mapping**, by walking each of the three
cables signal by signal and confirming every one lands on its counterpart.
Its HDMI pin tables are retyped from the specification rather than imported
from the generator, so the two can disagree and be caught.

Run both after any change.

UUIDs are derived from reference designators, so regenerating produces no
spurious diff. **Once you start routing in KiCad or EasyEDA Pro, stop
regenerating the PCB.**

Three single constants are worth knowing about, because they are the ones you
are most likely to need:

| Constant | In | Why you would change it |
|---|---|---|
| `MINI_HDMI['pin1_at_plus_x']` | `tools/gen_gowin_bridge.py` | **Check this before sending gerbers.** If the socket's pin 1 is at the other end, every signal lands on the wrong cable wire. `DESIGN_NOTES.md` 7.1. |
| `MINI_PITCH` | same | If your cables' boots are wider than 17.40 mm. |
| `HL2_ORIGIN` | same | Slides board A along the HL2's corridor, trading filter-board clearance against cable-boot clearance at the extrusion wall. |
