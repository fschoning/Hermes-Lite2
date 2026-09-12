# gowin-bridge — two adapter PCBs for a 12-bit / 76.8 MSPS link between a Hermes Lite 2 and a Sipeed Tang Mega 138K

Two boards and **three HDMI cables** carry the Hermes Lite 2's raw ADC stream
to an external Gowin GW5AST-138 FPGA, carry the same bandwidth back, and carry
a fast full-duplex control channel. The same HL2-side board also links **two
HL2 radios directly to each other**, with no Gowin at all, and in that case
each radio sends the other its **complete raw ADC stream**.

* **Board A — `hl2-bridge/`** plugs onto the HL2's **DB1** (2x10) and **DB12**
  (3x2) headers. Three **mini HDMI (Type C)** sockets, left to right:
  `OUT`, `AUX`, `IN`. 48.00 x 66.00 mm, 4 layer.
* **Board B — `tang-bridge/`** plugs onto the Tang Mega 138K dock's **J14**
  (2x40, Bank 4). Three **full-size HDMI (Type A)** sockets, left to right:
  `IN`, `AUX`, `OUT`. 90.00 x 46.00 mm, 4 layer.
* **The panel — `panel/`** is both boards on one **94.00 x 100.00 mm**
  V-scored production panel. **This is what you order.** The two individual
  projects are kept so you can work on one board at a time, and as the fallback
  if the fab will not take the panel.

Revision **C**. rev B had three sockets per board but an asymmetric link; rev A
had two dual-link DVI-D sockets. Both are in git history.

| Document | What is in it |
|---|---|
| **`PINMAP.md`** | The authoritative wire-by-wire map. The FPGA gateware constraints must match it exactly. |
| **`ROUTING.md`** | Step-by-step routing instructions for EasyEDA Pro, with the numbers, including the panel. |
| **`DESIGN_NOTES.md`** | Signal-integrity assumptions, the strap circuit and its failure analysis, the 2.5 V threshold resolution, the mechanical and panel arithmetic, the power budget, and everything unverified. |
| **`STATUS.md`** | What is done, what is unverified, exact next steps. |
| **`templates/`** | 1:1 printable PDFs to offer up to the real hardware **before ordering**. |

---

## 1. Two rules

**`OUT` goes to `IN`. `AUX` goes to `AUX`.**

Never `OUT` to `OUT` (two drivers fighting) and never `IN` to `IN` (no driver
at all). Neither mistake damages anything, but neither works.

What makes this simple is that **the role belongs to the socket, not to pins
inside it.** An `OUT` socket drives all four pairs; an `IN` socket receives all
four pairs; the pair ordering and the slow-wire pin are identical on both. So a
straight pin-1-to-pin-1 cable joins any `OUT` to any `IN` and every signal
lands on its counterpart — which is what lets one board design sit at **both**
ends of a two-radio link.

`AUX` is the same trick applied to a bidirectional cable. Its four pairs are
split into two fixed groups, **G1** (the clock pair and the data 0 pair) and
**G2** (the data 1 pair and the data 2 pair), and a **strap on the board**
decides which group that board drives. A straight cable maps G1 to G1 and G2 to
G2, so **any two boards work provided one is strapped ROLE A and the other
ROLE B.** Section 5 says how to set it.

**`OUT` and `IN` are the two OUTER sockets on both boards.** That is
deliberate: the two-radio case uses only those two, so it never has three cable
boots side by side.

---

## 2. The three ways to use it

### 2a. HL2 to Gowin — three cables

```
radio  OUT  ==mini-to-full-size==>  IN   Tang dock
radio  AUX  <=mini-to-full-size=>   AUX  Tang dock
radio  IN   <=mini-to-full-size==   OUT  Tang dock
```

Board A ships strapped **ROLE A** and board B strapped **ROLE B**, so out of
the box this configuration needs no jumper changes at all.

* **Forward and reverse: 3 data lanes each way, every lane DDR at 153.6 MHz =
  307.2 Mbit/s.** 3 x 307.2 = **921.6 Mbit/s = 12 bits x 76.8 MSPS**, the
  entire ADC stream with no compression and no framing overhead, in each
  direction. Each cable carries its own copy of the clock, so the cables'
  lengths do not have to match.
* **Control channel: the `AUX` cable, differential, source-synchronous, full
  duplex.** One clock and one data lane each way. The hardware is good for
  307.2 Mbit/s each way; the gateware should start at a divided rate of
  38.4 MHz DDR = **76.8 Mbit/s** each way, and `DESIGN_NOTES.md` explains why.
  Either number is four orders of magnitude more than a control channel needs.

### 2b. Two HL2 radios back to back — two cables

Fit a board A in each radio and cross two **mini-to-mini** cables between the
two **outer** sockets:

```
radio 1  OUT  ==mini-to-mini==>  IN   radio 2
radio 2  OUT  ==mini-to-mini==>  IN   radio 1
```

**Each radio sends the other its complete raw ADC stream, 921.6 Mbit/s, and
receives the other's.** That is six times the 153.6 Mbit/s of the HL2's own
one-pair DB12 two-radio link, and it is the full stream rather than a
subsampled one.

Each radio's `AUX` socket stays empty, and with no auxiliary cable the `ROLE`
strap does nothing, so leave both boards' straps alone.

This needs a future HL2 gateware variant on both radios. **No board change and
no jumper change:** each radio's `IN` socket already feeds the received clock
and three data lanes onto its own DB1/DB12 pins exactly as in case 2a.

### 2c. Two HL2 radios back to back — three cables

As 2b, plus a third mini-to-mini cable between the two `AUX` sockets, which
adds a 307.2 Mbit/s control channel each way. This is the one case where you
**must** change a strap: **move one radio's board A `ROLE` shunt from 1-2 to
2-3**, so one board is ROLE A and the other ROLE B. Get it wrong and the
auxiliary link simply does not come up; nothing is damaged.

For **coherent** two-radio operation the HL2's existing clock-chip coax link
(CL8/CL2) is still required. Board A does not affect it — but note that DB1
pin 1 shares a net with the uFL pad CL8 through the HL2's own jumper **J25**,
so J25 must stay closed. If a builder needs DB1 pin 1 free, cut solder link
**R1** on board A.

---

## 3. Which cables to buy

| For | Cable | How many |
|---|---|---|
| HL2 to Gowin (case 2a) | **mini HDMI (Type C) male to full-size HDMI (Type A) male** — the commonest camera / tablet cable | **3** |
| HL2 to HL2 (case 2b) | **mini HDMI (Type C) male to mini HDMI (Type C) male** — less common, but sold as a camera cable | **2** |
| HL2 to HL2 with the control channel (case 2c) | the same mini-to-mini | **3** |

Any length up to a few metres is electrically fine. Every standard HDMI cable
is straight-through, and a commercial mini-to-full-size cable wires **signal to
signal, not pin number to pin number** — which is why board A can use Type C
and board B Type A with no crossover anywhere.

**Measure the moulded plastic boot on the mini HDMI end with calipers before
you commit to the board.** Three mini HDMI sockets sit on a 17.40 mm pitch,
which is the widest the 48 mm board allows, and **nobody publishes the boot
width** — it is somewhere between 15.6 and 17.3 mm depending on the brand.
Under the optimistic estimate there is 1.8 mm between adjacent boots; under the
pessimistic one, 0.08 mm. `DESIGN_NOTES.md` has the arithmetic and the
fallbacks if your cables are fat. **Case 2b uses only the outer two sockets,
34.80 mm apart, so it can never be affected.**

Do **not** buy a cable with a moulded right-angle plug unless you have checked
which way it bends: the sockets are at the board edge with 12 mm of vertical
room.

---

## 4. What you have to solder

### 4a. On the existing hardware

| Board | What | Why |
|---|---|---|
| Hermes Lite 2 | A 2x10 0.1" male pin header at **DB1**, if not already fitted. Makerfabs-built boards normally ship with DB1 stuffed. | Board A's main connection. |
| Hermes Lite 2 | A 3x2 0.1" male pin header at **DB12**. Marked "do not install" in the HL2 BOM, so this one almost certainly has to be added. | Carries the status UART out, one auxiliary data lane, the ROLE strap read and the reverse clock. |
| Hermes Lite 2 | Check that jumper **J25** is closed. | The auxiliary G2 clock reaches FPGA PIN_72 only through it. |
| Hermes Lite 2 | A custom rear endcap with one **52.2 x 12.0 mm slot**. The endcaps are 0.8 mm PCBs (`hardware/enclosure/endcaps/`). | The three cables come out of the RF end of the case. |
| Tang Mega 138K dock | A 2x20 0.1" male pin header at **J14** ("SDRAM1 CONN.", top edge next to the PMOD sockets). Ships as bare plated holes. | Board B's only connection. |
| Tang Mega 138K dock | A short ground wire from a PMOD socket's GND pin to board B's `GND AUX` header (J6). | J14 has exactly one ground pin and that is not enough for eight CMOS outputs switching at up to 307 Mbit/s. **Not optional in practice.** |

Nothing on either existing board is modified or removed.

### 4b. Two parts on board A that you buy and solder yourself

Both are through-hole sockets on the underside of board A, both are marked
**do not place** in the BOM with their footprints kept, and **neither exists at
LCSC** — that was confirmed by search, which is why they are not JLCPCB line
items.

| What | Where to buy | Price |
|---|---|---|
| **Vertical (top-entry) 2x3 2.54 mm female socket**, for HL2 DB12. LCSC's vertical female headers start at 2x4, and the 2x3 they do list (C99515) is **side entry**, which cannot work: board A's DB12 socket plugs straight down onto a male header on the radio. | **Samtec SSQ-103-02-S-D** — Mouser 200-SSQ10302SD. Only about 19 were in stock when this was checked, so confirm before relying on it. Alternatively buy a 2x4 and cut it down. | about **EUR 1.49** each |
| **2x10 2.54 mm female socket with long (~10 mm) tails**, for the DB1 stack-through. LCSC stocks no long-tail 2x10 socket at all — all seven of their 2x10 female listings are ordinary ~3.2 mm pins. | **Phoenix Enterprises HWS16492** (10.5 mm tails, gold, sold explicitly for board stacking), or **Samtec SSQ-110-03-T-D** / **SSQ-110-23-L-D** from Mouser (the SSQ-**110** family is the 2x10 one, with a 0.394 inch = 10.0 mm tail). | **$0.99** each for the Phoenix part |

> **An earlier note in this repository named Samtec SSQ-120-01-G-D and
> SSQ-120-01-T-D. Those are the wrong parts.** They are 2x**20**, not 2x10, and
> their tail is 2.64 mm, not 10 mm. Use the SSQ-**110** family.

If you never intend to stack a companion board on top of board A, the ordinary
short-pin vertical 2x10 socket **LCSC C42431860** (JXTCONN PM2.54-2X10P-H85,
$0.1921 at qty 10) fits the same holes and can go in the JLCPCB order.

**Clip ten tails flush before fitting the long-tail socket.** The stack-through
must carry only DB1 positions **7, 8, 10, 12, 13, 14, 16, 18, 19 and 20** —
the HL2's 2.5 V rail, the two CW/PTT pins, two grounds, SCL1/SDA1 and the two
+3V3 pins. Positions **1, 2, 3, 4, 5, 6, 9, 11, 15 and 17** carry the link and
must be **physically absent** above the board, so a stacked companion cannot
reach them. The silkscreen says so on both sides.

---

## 5. Jumpers, links and options

### 5a. The `ROLE` strap — the one that matters

**One 1x3 header with ONE shunt.** Board A's is **J9**, board B's is **J7**.

| Shunt | Meaning |
|---|---|
| **1-2** | **ROLE A** — this board drives auxiliary group G1 (the clock and data 0 pairs) and receives G2. |
| **2-3** | **ROLE B** — this board drives G2 (the data 1 and data 2 pairs) and receives G1. |
| none | ROLE B, by a 100 k pull-down. A defined state, not a floating one. |

**Board A ships 1-2 (ROLE A). Board B ships 2-3 (ROLE B).** So the
HL2-to-Gowin case needs no change. The only time you touch it is case 2c, two
radios with an auxiliary cable, where one of the two board As must be moved
to 2-3.

A single-gate inverter next to the header produces the complement, so the two
levels can never disagree. **Nothing you can do with this shunt damages
anything.** Get it wrong on both boards and the auxiliary link does not come
up; the two fixed-direction cables are unaffected. `DESIGN_NOTES.md` has the
full failure analysis, and `tools/check_netlist.py` proves it from the netlist.

**If you move a strap permanently, move two 100 R terminations with it.** Each
auxiliary pair has a 100 R differential termination position, and only the two
for the pairs that board **receives** should be fitted. Board A ships with the
D1 and D2 pairs terminated; board B with the CLK and D0 pairs.

### 5b. Everything else

| Board | Ref | Default | What it does |
|---|---|---|---|
| A | **J6** `3V3 SRC` | shunt on **1-2** | 1-2 takes the board's 3.3 V from HL2 DB1 pins 19/20. 2-3 takes it from U10, the on-board LDO fed by the `IN` socket's HDMI +5 V pin — which needs U10 and `SL_5V` fitted, and both are not fitted by default. |
| A | **J7** `RX MODE` | shunt on **2-3** | 2-3 = the `IN` receiver is enabled only while a cable is plugged into `IN`, so the HL2's LED pins are never driven with no cable. 1-2 = force off. No shunt = always on. Does **not** affect the auxiliary receiver, which is always on and safely so. |
| A | **R1** `SL_D0` | fitted | Cut to isolate board A from DB1 pin 1, the net that reaches uFL pad CL8 through the HL2's jumper J25. |
| A | 8 translator bypass links | **not fitted** | Bypass the SN74AVC8T245 level translator entirely. Only for the bench experiment in `DESIGN_NOTES.md`; if you fit them, remove U1 and both 330 R divider legs too. |
| A | `SL_VLVDS` | not fitted | Reference the translators' 2.5 V side to the HL2's own `Vlvds` rail (DB1 pins 7/8) instead of U9. Do not fit together with U9. |
| A | `SL_5V` + **U10** | not fitted | The HDMI +5 V supply path. Read `DESIGN_NOTES.md` before fitting: there is no 5 V source at all in the two-radio configurations. |
| A, B | AC-coupling parts on the four **received** `IN` pairs | **not fitted** | Per pair: two 100 nF capacitors and two 4k7 bias resistors, plus one shared 10 k / 4k7 `VBIAS` divider. Boards ship **DC-coupled** through 0 R links. Deliberately **not** offered on the auxiliary pairs — a series capacitor on a bidirectional pair leaves the far end's common mode undefined. |
| B | 22 pF on the slow line | not fitted | Fit if the unterminated cable wire rings enough to double-clock the receiver. |
| B | **J5** `RX MODE` | shunt on **2-3** | Same scheme as board A's J7, for the `IN` receiver. Move to 1-2 for the direct-LVDS experiment. |
| B | **J6** `GND AUX` | — | Fit the ground wire. See section 4a. |
| B | 12 direct-LVDS links | **not fitted** | Route the six received pairs straight into the Gowin's Bank 4 differential pairs with no receiver chip. `PINMAP.md` 5.3 lists what you lose: the whole `OUT` socket and the whole auxiliary G2 direction. |
| B | `SL_5V_OUT` | not fitted | Puts the dock's 5 V on the `OUT` socket so board A could run from it. |

---

## 6. Importing into JLCPCB's EasyEDA Pro editor

The projects are written in KiCad 8 format and open in KiCad 8, 9 and 10.
**`ROUTING.md` is the full procedure**; the import itself is:

1. EasyEDA Pro: **File > Import > KiCad**.
2. Select `panel/panel.kicad_sch`, and point it at the project folder so it
   picks up `gowin-bridge.kicad_sym` and `gowin-bridge.pretty/` — both are
   inside the schematic's own folder, which is why the libraries were made
   project-local.
3. Check the import report. Every part meant for JLCPCB assembly should arrive
   with its `LCSC` property filled in; that is the field EasyEDA Pro uses to
   match a component to a JLCPCB assembly part. The two hand-fitted
   through-hole sockets deliberately have no LCSC number.
4. **Check the DNP flags survived.** 69 parts on the panel are marked "do not
   place" and they are not decoration.
5. **Design > Update PCB** to push the netlist into a new PCB document, and
   import `panel/panel.kicad_pcb` as well to get the placement, the outline,
   the V-score lines and the mouse bites.

Nothing is routed. Routing is `ROUTING.md`, and the rule there that matters
most is: **route each board entirely inside its own outline, and never across a
V-score line.**

---

## 7. Ordering

**Print the templates and check the fit first.** `templates/` holds 1:1 PDFs.
Print at 100 %, measure the 50 mm calibration rule on the paper, then lay
`hl2-bridge-1to1-TOP-fit-check.pdf` on the Hermes Lite 2 and
`tang-bridge-1to1-TOP-fit-check.pdf` on the Tang dock. **Board B's J14
position is still a guess** and this print is how you find out cheaply.
`panel-1to1-TOP-fit-check.pdf` shows the whole panel with its V-score lines.

Then, on JLCPCB's order form:

1. **Upload the gerbers for `panel/`, not for the two individual boards.**
2. **Set "Different designs in this file" to 2.** This is the field people
   miss. The panel holds two different designs, JLCPCB charges a panel fee for
   it ($8.21), and declaring 1 design declares the board to be something it
   is not.
3. 4 layer, 1.6 mm, **94 x 100 mm**, impedance-controlled, and name the stackup
   you designed to. ENIG rather than HASL if affordable — the mini HDMI's
   0.23 mm pads solder more reliably on flat gold — which costs **$12.30 more
   at quantity 5**.
4. **Quantity: 5.** That is JLCPCB's minimum for a board this size, whether you
   want two assembled or three.
5. **Assembly: top side only.** The minimum assembly quantity is 2.
6. **BOM and CPL** come from `panel/panel-bom.csv` and the position file you
   export. The BOM is authoritative, including which parts are DNP.

### Two warnings about this panel

**JLCPCB's Economic assembly service states a panelisation rule of mouse-bite
separations only; Standard allows mouse-bite or V-cut.** This panel uses three
V-scores and one mouse-bite separation, so it mixes both. **Confirm it with the
fab before paying.** This is unverified.

**Economic assembly only offers 2 or 5 boards assembled out of a 5-board run —
there is no 3.** Standard has a free-entry box for 2 to 5. So if you want
exactly three assembled you are pushed onto the more expensive service, which
is why the three-panel total below jumps by more than one panel's worth of
parts.

**If the fab queries the panel, the fallback is two separate orders** — board A
on its own and board B on its own, from the `hl2-bridge/` and `tang-bridge/`
projects, which are kept for exactly this reason. Expect it to cost roughly
**$40 more**, mostly because the assembly setup, stencil and per-unique-part
fees are then paid twice.

---

## 8. Cost

All prices read from JLCPCB's and LCSC's live pages on **12 September 2026**.
Dollar figures are JLCPCB's US-store prices; euro figures were quoted with the
German store selected and are converted at the rate the two stores' own
numbers imply.

### 8a. What is on one panel

| Part | LCSC | Per panel | Unit | Per panel |
|---|---|---|---|---|
| Quad LVDS driver DS90LV047ATMX | C206491 | 6 | $1.8396 | $11.04 |
| Quad LVDS receiver DS90LV048A | C87137 | 4 | $1.4348 | $5.74 |
| 8-bit translator SN74AVC8T245PWR | C465742 | 1 | $0.9296 | $0.93 |
| 4-bit translator SN74AVC4T245PWR | C81461 | 3 | $0.3096 | $0.93 |
| Single-gate inverter SN74LVC1G04DBVR | C7827 | 2 | $0.0865 | $0.17 |
| Quad ESD array TPD4E05U06DQAR | C138714 | 18 | $0.0874 | $1.57 |
| 2.5 V LDO ME6211C25M5G | C194395 | 1 | $0.0561 | $0.06 |
| AMS1117-3.3 | C6186 | 1 fitted (+1 not fitted) | $0.2198 | $0.22 |
| Mini HDMI Type C, XKB A71-05H4-111N1 | C2682170 | 3 | $0.4593 | $1.38 |
| Full-size HDMI Type A, Amphenol 10029449-111RLF | C427307 | 3 | $0.5081 | $1.52 |
| 2x20 vertical female header, for the Tang dock's J14 | C5124634 | 1 | $0.3305 | $0.33 |
| **Silicon and connectors, per panel** | | | | **$23.89** |

**Minimum-order batches are the surprise in this costing.** Sixteen line items
are reel-only with a minimum order far above what one or two panels use, so
they cost the same whether you build one panel or five:

| | Minimum | Batch cost |
|---|---|---|
| Eleven passive values — 0R 0402, 22R, 100R, 330R, 4k7, 10k, 100k, 22pF, 100nF, 1uF, 10uF 25V 0805 | 100 each (50 for the 1 uF, 20 for the 10 uF) | **$6.50** |
| 0 ohm jumper in **0805**, C17477 — a different part number from the 0402 one, because they are different packages | 100 | $0.45 |
| 1x3 vertical pin header, C52016391 | 20 | $0.48 |
| 1x2 vertical pin header, C52016390 | 50 | $0.80 |
| Jumper shunts for the straps and the option headers, C5305 | 50 | $0.50 |
| **Total, once per order** | | **$8.73** |

**Unique parts, which is what drives the assembly fee: 23 distinct LCSC numbers
are placed, 12 Extended and 11 Basic.** (The jumper shunts are pushed on by
hand and are not a placed part.) Economic assembly charges **$3.07 per
unique Extended part** and nothing for a Basic one; Standard charges **$1.53
for every part**, Basic or Extended. Two of the twelve Extended parts are the
pin headers, and that is unavoidable: **no Basic 2.54 mm through-hole 1x2 or
1x3 vertical header exists in JLCPCB's library at all**, and neither does a
Basic 74LVC1G04 in SOT-23-5, from any manufacturer they list.

### 8b. Two panels assembled — about $200

Five bare boards, two of them populated, **Economic** assembly.

| | |
|---|---|
| 5 bare boards, 94 x 100 mm, 4 layer, lead-free HASL (the minimum order) | $52.42 |
| Assembly setup | $8.18 |
| Panel fee, because the file holds 2 designs | $8.21 |
| Stencil | $1.53 |
| 12 unique Extended parts x $3.07 | $36.84 |
| Hand-soldering base fee | $3.58 |
| SMT joints, 789 per panel x 2 x $0.0016 | $2.52 |
| Through-hole joints, 89 per panel x 2 x $0.0164 | $2.92 |
| Silicon and connectors, 2 x $23.89 | $47.78 |
| Minimum-order batches, once | $8.73 |
| Shipping to Germany, DHL Express (EUR 18.58) | $21.55 |
| Vertical 2x3 socket you solder yourself, 2 off (EUR 1.49 each) | $3.46 |
| Long-tail 2x10 socket you solder yourself, 2 off ($0.99 each) | $1.98 |
| **Total** | **$199.70** |

### 8c. Three panels assembled — about $251

Five bare boards, three populated. **Standard** assembly, because Economic will
not sell you three.

| | |
|---|---|
| 5 bare boards | $52.42 |
| Assembly setup | $25.56 |
| Panel fee, 2 designs | $8.21 |
| Stencil | $8.21 |
| 23 unique parts x $1.53 — Standard charges for Basic parts too | $35.19 |
| Hand-soldering base fee | $3.58 |
| SMT joints, 789 per panel x 3 x $0.0016 | $3.79 |
| Through-hole joints, 89 per panel x 3 x $0.0164 | $4.38 |
| Silicon and connectors, 3 x $23.89 | $71.67 |
| Minimum-order batches, once | $8.73 |
| Shipping to Germany, DHL Express | $21.55 |
| Vertical 2x3 socket, 3 off | $5.19 |
| Long-tail 2x10 socket, 3 off | $2.97 |
| **Total** | **$251.45** |

### 8d. What that means

* **Two panels: $199.70. Three panels: $251.45.** The third panel costs
  **$51.75**, of which only about **$29** is the panel's own parts, joints and
  sockets — the rest is the service-tier jump that asking for exactly three
  forces.
* **If you want more than two, order five, not three.** Five populated stays on
  Economic and pays exactly the same fixed fees as two: **$287.70 for five,
  which is $58 each, against $100 each for two.** Almost all of the money is
  setup.
* **Cheaper shipping saves about $15.** Global Standard Direct Line was
  EUR 5.97 against DHL Express's EUR 18.58, at 9 to 13 days instead of 2 to 4.
* **ENIG instead of lead-free HASL costs $12.30 more** at quantity 5, and the
  mini HDMI's 0.23 mm pads solder more reliably on flat gold.
* **The one figure here that is not a quote** is the solder-joint fee. JLCPCB
  will not compute it without a login and an uploaded position file, so the
  $0.0016 and $0.0164 per-joint rates come from their published fee schedule,
  and the 789 surface-mount and 89 through-hole joints per panel were counted
  from the board files in this directory. It is about $5 out of $200, so it
  does not change the picture.
* **Nothing here includes shipping from Mouser or Phoenix Enterprises** for the
  two hand-soldered sockets. That is unverified.

---

## 9. Regenerating the projects

All three projects are generated from one netlist description. **Do not
hand-edit the KiCad files** — change `tools/gen_gowin_bridge.py`, re-run it,
and update `PINMAP.md` in the same commit:

```
cd hardware/companions/gowin-bridge
python tools/gen_gowin_bridge.py     # writes all three projects
python tools/check_geometry.py       # placement, the HL2 hole grid, the panel
python tools/check_netlist.py        # socket symmetry, the cables, the strap
```

**Both checkers must print `OK` before anything is committed.**

**`check_geometry.py`** reads the generated PCBs back and verifies that every
pad and courtyard is on the board, that nothing overlaps, and that **board A's
DB1 and DB12 socket holes land on the Hermes Lite 2's own hole grid**,
recomputed independently from `hardware/hl/hermeslite.kicad_pcb` rather than
copied from the generator. On the panel it additionally checks that every part
lies wholly inside its own board, coupon or rail; that no copper comes within
0.40 mm and no component body within 1.00 mm of a V-score line; that each of
the three V-scores runs edge to edge with material on both sides for its whole
length; and that the panel fits inside 100 x 100 mm.

**`check_netlist.py`** exports the netlists and verifies four things ERC cannot
see: that the HL2 DB1/DB12 and Tang J14 header pins carry exactly the nets
`PINMAP.md` says (and that every other J14 pin is electrically open, so the
dock's PMOD sockets and camera FPC stay usable); that **all six sockets share
one signal-to-role mapping**, by walking each cable signal by signal; that the
auxiliary socket is **self-complementary**, so group G1 lands on group G1; and
that **no state of either board's ROLE strap can make a buffer drive a pin the
gateware is also driving**, which is the one failure this design must not have.
Its HDMI pin tables are retyped from the specification rather than imported
from the generator, so the two can disagree and be caught.

UUIDs are derived from reference designators, so regenerating produces no
spurious diff. **Once you start routing in KiCad or EasyEDA Pro, stop
regenerating the PCB.**

Three single constants are worth knowing about, because they are the ones you
are most likely to need:

| Constant | In | Why you would change it |
|---|---|---|
| `MINI_HDMI['pin1_at_plus_x']` | `tools/gen_gowin_bridge.py` | **Check this before sending gerbers.** If the socket's pin 1 is at the other end, every signal lands on the wrong cable wire. |
| `MINI_PITCH` | same | If your cables' boots are wider than 17.40 mm. |
| `HL2_ORIGIN` | same | Slides board A along the HL2's corridor, trading filter-board clearance against cable-boot clearance at the extrusion wall. |
