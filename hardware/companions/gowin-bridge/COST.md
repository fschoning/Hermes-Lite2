# gowin-bridge cost, rev D — one board, both ends

**One design, one board, one order.** Each board carries one radio end and one
Gowin end inside a single outline, joined by three mouse-bite tabs and snapped apart
after assembly. The order is five boards, so five of each and five complete
links. Every figure below comes out of `tools/cost_model.py`, which counts
parts and solder joints from the generated BOM and PCB.

---

## 0. The short answer

| | |
|---|---|
| **Order total, five boards, delivered to Germany** | **$154.84** |
| **One complete link: one radio end plus one Gowin end** | **$30.97** |
| **The Gowin half** | **$22.41** over the radio-only order |
| The radio-only order it replaces (rev D, five radio ends) | $132.43 |

Plus, outside the order, per link: the $15.00 cable, $0.86 of hand-fitted
sockets for the radio end, and about $1.05 of stacking parts and a spacer for
the Gowin end.

**Where the $22.41 goes:**

| | |
|---|---|
| Bare PCB: the 64.50 × 92.00 mm board costs the same $12.10 as the radio end alone | $0.00 |
| Gowin-end components, 5 × $4.04 | $20.20 |
| Gowin-end solder joints, 5 × 214 × $0.0016 | $1.71 |
| The radio end re-counted: the AUXIO fail-safe (5 × one AO3400A and one 10 kΩ, plus their joints) and today's prices | $0.50 |

**The Gowin end adds no new Extended part number**, so no new $3.07 fee: its
connector and its ESD arrays are the radio end's own part numbers, and its
resistors are Basic. The AUXIO fail-safe on the radio end adds one Basic
MOSFET, so no fee either.

**The board is 64.50 × 92.00 mm** since the rails came off and the V-score
became three mouse-bite tabs on 13 Sep 2026 (it was quoted at 64.50 × 100.00
mm), inside the 100 × 100 mm size band for the promotional board price, so the
quote is unchanged — unless JLCPCB counts the two tabbed ends as two designs
(`DESIGN_NOTES.md` §13.2). The live quote gives $7.00 for five boards plus $5.10
for lead-free HASL.

---

## 1. Line by line

JLCPCB, **Economic** assembly, 5 boards, 4 layer, 1.6 mm, lead-free HASL,
green, 1 oz outer, **one design, single PCB**, no impedance control.

### 1.1 Paid once per order

| Charge | Cost |
|---|---|
| Bare PCB: board, 5 pieces, 64.50 × 92.00 mm (quoted at 64.50 × 100.00, same promotional band) | $7.00 |
| Bare PCB: lead-free HASL | $5.10 |
| **Bare PCB subtotal** (live quote, 13 Sep 2026) | **$12.10** |
| Assembly setup | $8.18 |
| Stencil | $1.53 |
| Unique Extended part numbers, 6 × $3.07 | $18.42 |
| Shipping, one DHL shipment to Germany | $21.55 |
| **Subtotal, once per order** | **$61.78** |

### 1.2 Paid per board

| Charge | Each | × 5 |
|---|---|---|
| Components, radio end | $13.39 | $66.96 |
| Components, Gowin end | $4.04 | $20.20 |
| SMT joints, radio end, 524 | $0.84 | $4.19 |
| SMT joints, Gowin end, 214 | $0.34 | $1.71 |
| **Subtotal, per board** | **$18.61** | **$93.06** |

| | |
|---|---|
| **Order total** | **$154.84** |
| **Per link** | **$30.97** |

No factory through-hole joints and no hand-soldering fee: every through-hole
socket and header is fitted by the owner.

---

## 2. The Gowin end's parts

| Part | LCSC | Tier | Qty | Unit | Line |
|---|---|---|---|---|---|
| SlimSAS 8i 74P right angle, Amphenol U10A474240T | C5432262 | Ext, **already on the order** | 1 | $3.17 (10+) | $3.17 |
| ESD array TPD4E05U06DQAR | C138714 | Ext, **already on the order** | 12 | $0.0696 (50+) | $0.84 |
| 330 Ω 0402 | C25104 | Basic | 4 | $0.0044 | $0.02 |
| 1 kΩ 0402 | C11702 | Basic | 3 | $0.0022 | $0.01 |
| 10 kΩ 0402 | C25744 | Basic | 2 | $0.0031 | $0.01 |
| 0 Ω 0805 | C17477 | Basic | 1 | $0.0045 | $0.00 |
| **Per Gowin end** | | | | | **$4.04** |

Not fitted, no cost: seven 100 Ω optional terminations (C25076).

**Stock to watch:** C5432262 now shows **189** in stock, down from 483 on
12 September. An order needs 10.

### 2.1 Hand-fitted on the Gowin end, per link

The geometry is the same for both mounting schemes; only these parts differ.

| Scheme | Dock J14 positions 5–40 | Adapter | Spacer | Per link |
|---|---|---|---|---|
| **1 — dock on a carrier plate**, stack 7.0–7.5 mm | 2×18 female 5.0 mm, KH-2.54FH-2X18P-H5.0, **C55160396**, $0.45, **only 10 in stock** | 2×18 male HC-PZ254-11.5L-2X18PZ, **C41376109**, $0.19, fitted upside down | M3 × 7 mm, about $0.40 | **$1.04** |
| **2 — dock on the case floor**, stack 11.0 mm | 2×18 male, **C41376109**, $0.19 | 2×18 female 8.5 mm, HX PM2.54-2x18P ZC, **C42372542**, $0.47 | M3 × 11 mm, about $0.40 | **$1.06** |

---

## 3. The radio end's parts

Unchanged from rev D except two prices and the AUXIO fail-safe (one AO3400A
MOSFET and one 10 kΩ, both Basic). Eighteen part numbers: twelve Basic, six
Extended, and the six Extended are the whole $18.42.

| Part | LCSC | Tier | Qty | $ each | Line |
|---|---|---|---|---|---|
| SlimSAS 8i receptacle | C5432262 | Ext | 1 | 3.17 | 3.17 |
| DS90LV047A quad LVDS driver | C206491 | Ext | 2 | 1.84 | 3.68 |
| DS90LV048A quad LVDS receiver | C87137 | Ext | 2 | 1.43 | 2.86 |
| SN74AVC4T245 translator/buffer | C81461 | Ext | 7 | 0.3096 | 2.17 |
| TPD4E05U06 ESD array | C138714 | Ext | 12 | 0.0696 | 0.84 |
| ME6211C25 2.5 V LDO | C194395 | Ext | 1 | 0.0561 | 0.06 |
| Basic passives and bead | 11 numbers | Basic | 71 | — | 0.52 |
| AO3400A N-MOSFET, the AUXIO presence interlock | C20917 | Basic | 1 | 0.0853 | 0.09 |
| **Per radio end** | | | | | **$13.39** |

`DESIGN_NOTES.md` §7 has the full list and why no cheaper part exists for any
of the Extended six.

---

## 4. What could be cut

| | Change | Saves on this order | Cost to you |
|---|---|---|---|
| 1 | Leaded HASL instead of lead-free | $5.10 | RoHS |
| 2 | DS90LV047A in TSSOP-16 (C87097) instead of SOIC-16 | $4.30 | a little thermal margin |
| 3 | Global Standard shipping instead of DHL | $14.63 | 9–13 days instead of 2–4 |

**Impedance control stays off:** $33.88 including its mandatory file check,
for a 307.2 Mbit/s link whose connector is itself 85 Ω ±10. `DESIGN_NOTES.md`
§3.

---

## 5. Not verified in these numbers

| Item | Worth | Status |
|---|---|---|
| **Shipping** | a few dollars | $21.55 is rev D's Germany quote with assembly, kept unchanged. The bare-PCB quote page on 13 Sep 2026 estimated DHL at $27.63 for 0.23 kg; the real figure comes after the files are uploaded |
| **Whether JLCPCB will solder the SlimSAS shell tails** | $4.24 | 8 tails per board × 5 × $0.0164 + the $3.58 hand-soldering fee, if they do. The costing assumes the owner does |
| **Whether JLCPCB counts the two tabbed ends as two designs, and drops the promotional board price** | a different-design fee and the board at full price; not quoted | ask before ordering, `DESIGN_NOTES.md` §13.2 |
| **Stock of C55160396**, the 5.0 mm socket for scheme 1 | $0.45 a link | 10 in stock on 13 Sep 2026 |

---

## 6. Sources

| | |
|---|---|
| Bare PCB | JLCPCB instant quote, cart.jlcpcb.com, read 13 Sep 2026. Entered: FR-4, 4 layers, 64.5 × 100 mm, PCB qty 5, product type industrial/consumer, **one design, delivery format "Single PCB"**, 1.6 mm, green, white silkscreen, FR4 TG135, **lead-free HASL**, 1 oz outer, 0.5 oz inner, no specified stackup, plugged vias (the 4-layer default), 0.3 mm minimum via, ±0.2 mm outline tolerance, mark on PCB "Remove Mark" (form default, no charge), flying-probe test, 3–4 day build. Returned: special offer (board) $7.00, via covering $0.00, surface finish $5.10, build time $0.00, **calculated price $12.10** |
| Assembly fees | jlcpcb.com/help/article/pcb-assembly-price, read 13 Sep 2026: Economic setup $8.18, stencil $1.53, SMT joint $0.0016, through-hole joint $0.0164, hand soldering $3.58 per order, Extended feeder $3.07 |
| Rails | Removed 13 Sep 2026. jlcpcb.com/capabilities/pcb-assembly-capabilities lists edge rails as "Not necessary" for Economic PCBA; jlcpcb.com/help/article/pcb-assembly-faqs-part-2 asks for traces and components more than 0.3 mm from the edge |
| Gowin-end part prices and stock | LCSC product pages read 13 Sep 2026: C5432262 **189 in stock** (re-read 13 Sep 2026, unchanged; the order needs 10), $3.17 at 10+; C138714 45,175, $0.0696 at 50+; C25744, C11702, C25104, C17477, C25076 all in stock at the prices above; C55160396, C41376109, C42372542 |
| AO3400A | LCSC C20917, read 13 Sep 2026: 461,420 in stock, $0.0853 at 5+; jlcpcb.com/partdetail/C20917: **Basic** |
| Radio-end baseline | `COST.md` as committed in 8405702, $132.43 |
| Joint counts | `tools/cost_model.py`, counted from `bridge/bridge.kicad_pcb` |
