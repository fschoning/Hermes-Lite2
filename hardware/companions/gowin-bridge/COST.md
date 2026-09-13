# gowin-bridge cost, rev D — one board, both ends

**One design, one board, one order.** Each board carries one radio end and one
Gowin end inside a single outline, joined by three mouse-bite tabs and snapped apart
after assembly. The order is five boards, so five of each and five complete
links. Every figure below comes out of `tools/cost_model.py`, which counts
parts and solder joints from the generated BOM and PCB.

---

## 0. The short answer

Updated 13 Sep 2026 for the risk-review fixes (`DESIGN_NOTES.md` §14).

| | |
|---|---|
| **Order total, five boards, delivered to Germany** | **$162.43** (was $154.84) |
| **One complete link: one radio end plus one Gowin end** | **$32.49** (was $30.97) |
| **The Gowin half**: the Gowin end's parts and joints, five boards | **$21.92** (was $21.91; R103 is now 10 kΩ) |
| The radio-only order it is compared with (rev D, five radio ends, before the fixes) | $132.43 |

Plus, outside the order, per link: the $15.00 cable, $0.86 of hand-fitted
sockets for the radio end, and about $1.05 of stacking parts and a spacer for
the Gowin end.

**What the fixes added: $7.59 on the order.**

| | On the order |
|---|---|
| One new Extended feeder fee: L1, the 4.7 µH filter inductor | $3.07 |
| Radio-end parts, 5 × $0.84: five AO3400A, two RB751V-40, the 100 µF tantalum, L1, two capacitors, eight resistors (the detector discharge, three pull-ups and four input holds) | $4.18 |
| Radio-end solder joints, 5 × 43 × $0.0016 | $0.34 |

**No fee for the detector diodes.** The RB751V-40 (C7502691) is JLCPCB
**Preferred Extended**, which is exempt from the feeder fee on Economic
assembly. The review had assumed a $3.07 fee for it.

**Not fitted, no cost:** the two 10 nF shell-bond capacitors (C30, C101) and
the 0 Ω bypass across L1 (R_LBYP). R_DRVEN_ON and R_DRVEN_PRSNT swapped
roles, so the count is unchanged.

**The board is 64.50 × 92.00 mm**, inside the 100 × 100 mm size band for the
promotional board price, so the board quote is unchanged — unless JLCPCB
counts the two tabbed ends as two designs (`DESIGN_NOTES.md` §13.2). The live
quote gives $7.00 for five boards plus $5.10 for lead-free HASL.

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
| Unique Extended part numbers with a feeder fee, **7** × $3.07 | **$21.49** |
| Shipping, one DHL shipment to Germany | $21.55 |
| **Subtotal, once per order** | **$64.85** |

### 1.2 Paid per board

| Charge | Each | × 5 |
|---|---|---|
| Components, radio end | $14.23 | $71.13 |
| Components, Gowin end | $4.04 | $20.21 |
| SMT joints, radio end, 567 | $0.91 | $4.54 |
| SMT joints, Gowin end, 214 | $0.34 | $1.71 |
| **Subtotal, per board** | **$19.52** | **$97.58** |

| | |
|---|---|
| **Order total** | **$162.43** |
| **Per link** | **$32.49** |

No factory through-hole joints and no hand-soldering fee: every through-hole
socket and header is fitted by the owner.

---

## 2. The Gowin end's parts

| Part | LCSC | Tier | Qty | Unit | Line |
|---|---|---|---|---|---|
| SlimSAS 8i 74P right angle, Amphenol U10A474240T | C5432262 | Ext, **already on the order** | 1 | $3.17 (10+) | $3.17 |
| ESD array TPD4E05U06DQAR | C138714 | Ext, **already on the order** | 12 | $0.0696 (50+) | $0.84 |
| 330 Ω 0402 | C25104 | Basic | 4 | $0.0044 | $0.02 |
| 1 kΩ 0402 | C11702 | Basic | 2 | $0.0022 | $0.00 |
| 10 kΩ 0402 (R103 moved here from 1 kΩ on 13 Sep 2026) | C25744 | Basic | 3 | $0.0031 | $0.01 |
| 0 Ω 0805 | C17477 | Basic | 1 | $0.0045 | $0.00 |
| **Per Gowin end** | | | | | **$4.04** |

Not fitted, no cost: seven 100 Ω optional terminations (C25076) and the
10 nF shell-bond capacitor C101 (C1710).

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

Twenty-four placed part numbers on the whole board since 13 Sep 2026: sixteen
Basic, seven Extended with a fee (the whole $21.49), and one Preferred
Extended with no fee.

| Part | LCSC | Tier | Qty | $ each | Line |
|---|---|---|---|---|---|
| SlimSAS 8i receptacle | C5432262 | Ext | 1 | 3.17 | 3.17 |
| DS90LV047A quad LVDS driver | C206491 | Ext | 2 | 1.84 | 3.68 |
| DS90LV048A quad LVDS receiver | C87137 | Ext | 2 | 1.43 | 2.86 |
| SN74AVC4T245 translator/buffer | C81461 | Ext | 7 | 0.3096 | 2.17 |
| TPD4E05U06 ESD array | C138714 | Ext | 12 | 0.0696 | 0.84 |
| ME6211C25 2.5 V LDO | C194395 | Ext | 1 | 0.0561 | 0.06 |
| **SWPA4030S4R7NT 4.7 µH inductor, the 3.3 V filter (new)** | C193025 | **Ext** | 1 | 0.0856 | 0.09 |
| **RB751V-40 Schottky, the link-alive detector (new)** | C7502691 | **Preferred Ext, no fee** | 2 | 0.0148 | 0.03 |
| AO3400A N-MOSFET: the AUXIO interlock Q1 and **Q2–Q6 (new)** | C20917 | Basic | 6 | 0.0853 | 0.51 |
| **TAJB107K006RNJ 100 µF tantalum, the 3.3 V filter (new)** | C16133 | Basic | 1 | 0.2574 | 0.26 |
| Basic passives and bead (including the new 10 pF, 10 nF, 100 kΩ and seven 10 kΩ) | 14 numbers | Basic | 83 | — | 0.57 |
| **Per radio end** | | | | | **$14.23** |

`DESIGN_NOTES.md` §7 has the full list and why no cheaper part exists for any
of the Extended ones.

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
| **Stock of C193025**, the 4.7 µH inductor | the build | about 2,000 in stock on 13 Sep 2026; an order needs 5. Alternative SWPA4020S100MT (C82398) |
| **The RB751V-40's Preferred tier** | $3.07 | read from the JLCPCB library mirror jlcsearch.tscircuit.com (is_preferred), because JLCPCB's own part page does not show the tier to a fetch; JLCPCB's assembly FAQ confirms Preferred Extended parts carry no feeder fee. Check the tier in the JLCPCB BOM tool at upload |

---

## 6. Sources

| | |
|---|---|
| Bare PCB | JLCPCB instant quote, cart.jlcpcb.com, read 13 Sep 2026. Entered: FR-4, 4 layers, 64.5 × 100 mm, PCB qty 5, product type industrial/consumer, **one design, delivery format "Single PCB"**, 1.6 mm, green, white silkscreen, FR4 TG135, **lead-free HASL**, 1 oz outer, 0.5 oz inner, no specified stackup, plugged vias (the 4-layer default), 0.3 mm minimum via, ±0.2 mm outline tolerance, mark on PCB "Remove Mark" (form default, no charge), flying-probe test, 3–4 day build. Returned: special offer (board) $7.00, via covering $0.00, surface finish $5.10, build time $0.00, **calculated price $12.10** |
| Assembly fees | jlcpcb.com/help/article/pcb-assembly-price, read 13 Sep 2026: Economic setup $8.18, stencil $1.53, SMT joint $0.0016, through-hole joint $0.0164, hand soldering $3.58 per order, Extended feeder $3.07 |
| Rails | Removed 13 Sep 2026. jlcpcb.com/capabilities/pcb-assembly-capabilities lists edge rails as "Not necessary" for Economic PCBA; jlcpcb.com/help/article/pcb-assembly-faqs-part-2 asks for traces and components more than 0.3 mm from the edge |
| Gowin-end part prices and stock | LCSC product pages read 13 Sep 2026: C5432262 **189 in stock** (re-read 13 Sep 2026, unchanged; the order needs 10), $3.17 at 10+; C138714 45,175, $0.0696 at 50+; C25744, C11702, C25104, C17477, C25076 all in stock at the prices above; C55160396, C41376109, C42372542 |
| AO3400A | LCSC C20917, read 13 Sep 2026: 461,420 in stock, $0.0853 at 5+; jlcpcb.com/partdetail/C20917: **Basic** |
| Parts added 13 Sep 2026 | JLCPCB library (via jlcsearch.tscircuit.com) and LCSC product pages, read 13 Sep 2026. C7502691 RB751V-40: 628,950 in stock on LCSC, $0.0148 first JLCPCB break, Preferred Extended. C193025 SWPA4030S4R7NT: 1,958 in stock, $0.0856, Extended. C16133 TAJB107K006RNJ: $0.2574, Basic (LCSC retail $0.5261 at 2+). C32949 10 pF C0G: $0.0069, Basic. C15195 10 nF 0402: $0.0035, Basic. C1710 10 nF 0805: $0.0094, Basic. C25741 100 kΩ: 7,417,100 in stock, $0.0028. C25744 10 kΩ: $0.0029–0.0031, Basic. Preferred-part fee rule: jlcpcb.com/help/article/pcb-assembly-faqs |
| Radio-end baseline | `COST.md` as committed in 8405702, $132.43 |
| Joint counts | `tools/cost_model.py`, counted from `bridge/bridge.kicad_pcb` |
