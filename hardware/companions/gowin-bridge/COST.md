# gowin-bridge cost, rev D — the whole panel

**One design, one panel, one order.** Each panel is one radio end and one Gowin
end; the order is five panels, so five of each and five complete links. Every
figure below comes out of `tools/cost_model.py`, which counts parts and solder
joints from the generated BOM and PCB.

---

## 0. The short answer

| | |
|---|---|
| **The Gowin half costs $68.56** | the whole order minus the radio-only order |
| **Order total, five panels, delivered to Germany** | **$200.99** |
| **One complete link: one radio end plus one Gowin end** | **$40.20** |
| The radio-only order it replaces (rev D, five radio ends) | $132.43 |

Plus, outside the order, per link: the $15.00 cable, $0.86 of hand-fitted
sockets for the radio end, and about $1.05 of stacking parts and a spacer for
the Gowin end.

**Where the $68.56 goes:**

| | |
|---|---|
| The fab's charges for a panel carrying **two different outlines** (its order form calls this "Different Design: 2"): PCB engineering fee $25.00 + PCB panel charge $16.42 + loss of the single-outline $7.00 promotional board price, net of the $4.00 panel board price, and the assembly panel fee $8.21 | **$46.63** |
| Gowin-end components, 5 × $4.04 | $20.20 |
| Gowin-end solder joints, 5 × 214 × $0.0016 | $1.71 |
| The radio end re-counted at today's prices | $0.02 |

**The Gowin end adds no new Extended part number**, so no new $3.07 fee: its
connector and its ESD arrays are the radio end's own part numbers, and its
resistors are Basic. **Two-thirds of the Gowin half is the fab's charge for a
panel with two different outlines, not parts.**

**Does the panel leave the 100 × 100 mm price band?** It is **64.50 × 100.07
mm**, 0.07 mm over. **It costs nothing**: JLCPCB's live quote gives the
panel the identical $50.52 at 99.67 mm and at 101 mm. The band only matters
when the file holds a single outline.

---

## 1. Line by line

JLCPCB, **Economic** assembly, 5 panels, 4 layer, 1.6 mm, lead-free HASL,
green, 1 oz, **"Different Design: 2", "Panel by Customer"**, no impedance
control.

### 1.1 Paid once per order

| Charge | Cost |
|---|---|
| Bare PCB: engineering fee, panel with two outlines | $25.00 |
| Bare PCB: panel charge, panel with two outlines | $16.42 |
| Bare PCB: lead-free HASL | $5.10 |
| Bare PCB: board, 5 panels | $4.00 |
| **Bare PCB subtotal** (live quote, 13 Sep 2026) | **$50.52** |
| Assembly setup | $8.18 |
| Stencil | $1.53 |
| Assembly panel fee, panel with two outlines | $8.21 |
| Unique Extended part numbers, 6 × $3.07 | $18.42 |
| Shipping, one DHL shipment to Germany | $21.55 |
| **Subtotal, once per order** | **$108.41** |

### 1.2 Paid per panel

| Charge | Each | × 5 |
|---|---|---|
| Components, radio end | $13.30 | $66.52 |
| Components, Gowin end | $4.04 | $20.20 |
| SMT joints, radio end, 519 | $0.83 | $4.15 |
| SMT joints, Gowin end, 214 | $0.34 | $1.71 |
| **Subtotal, per panel** | **$18.52** | **$92.58** |

| | |
|---|---|
| **Order total** | **$200.99** |
| **Per link** | **$40.20** |

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

Unchanged from rev D except two prices. Seventeen part numbers: eleven Basic,
six Extended, and the six Extended are the whole $18.42.

| Part | LCSC | Tier | Qty | $ each | Line |
|---|---|---|---|---|---|
| SlimSAS 8i receptacle | C5432262 | Ext | 1 | 3.17 | 3.17 |
| DS90LV047A quad LVDS driver | C206491 | Ext | 2 | 1.84 | 3.68 |
| DS90LV048A quad LVDS receiver | C87137 | Ext | 2 | 1.43 | 2.86 |
| SN74AVC4T245 translator/buffer | C81461 | Ext | 7 | 0.3096 | 2.17 |
| TPD4E05U06 ESD array | C138714 | Ext | 12 | 0.0696 | 0.84 |
| ME6211C25 2.5 V LDO | C194395 | Ext | 1 | 0.0561 | 0.06 |
| Basic passives and bead | 11 numbers | Basic | 70 | — | 0.52 |
| **Per radio end** | | | | | **$13.30** |

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
| **The assembly panel fee on a customer panel** | $8.21 | JLCPCB's assembly price page lists "Panel fee (multiple designs) $8.21"; the quote form will only itemise it after the files are uploaded |
| **Shipping** | a few dollars | $21.55 is rev D's Germany quote for one board size. The panel is heavier; the quote form estimates by weight after upload |
| **Whether JLCPCB will solder the SlimSAS shell tails** | $4.24 | 8 tails per panel × 5 × $0.0164 + the $3.58 hand-soldering fee, if they do. The costing assumes the owner does |
| **Whether JLCPCB accepts V-scores that cross the two 3.4 mm notches** | nothing, or a re-panel | ask at order time |
| **Stock of C55160396**, the 5.0 mm socket for scheme 1 | $0.45 a link | 10 in stock on 13 Sep 2026 |

---

## 6. Sources

| | |
|---|---|
| Bare PCB | JLCPCB instant quote, cart.jlcpcb.com, read 13 Sep 2026: 4 layer, 64.50 × 99.67 mm and 64.50 × 101 mm, 5 pcs, "Different Design" 2, "Panel by Customer", lead-free HASL: engineering fee $25.00, panel $16.42, surface finish $5.10, board $4.00. The same form gives $12.10 for the radio end alone |
| Assembly fees | jlcpcb.com/help/article/pcb-assembly-price, read 13 Sep 2026: Economic setup $8.18, stencil $1.53, SMT joint $0.0016, through-hole joint $0.0164, hand soldering $3.58 per order, **panel fee (multiple designs) $8.21**, Extended feeder $3.07 |
| Gowin-end part prices and stock | LCSC product pages read 13 Sep 2026: C5432262 189 in stock, $3.17 at 10+; C138714 45,175, $0.0696 at 50+; C25744, C11702, C25104, C17477, C25076 all in stock at the prices above; C5124634, C50980, C55160396, C41376109, C42372542, C19184331, C2682207 |
| Radio-end baseline | `COST.md` as committed in 8405702, $132.43 |
| Joint counts | `tools/cost_model.py`, counted from `bridge/bridge.kicad_pcb` |
