# gowin-bridge cost, rev D

**One design.** Five assembled boards, one order, one shipment.

---

## 0. The short answer

| | |
|---|---|
| **Five assembled boards, all in, delivered to Germany** | **$132.43** |
| Per board | **$26.49** |
| Plus one 10Gtek CAB-8654/8654-8i-P cable, 0.5 m | **$15.00** |
| Plus the through-hole parts the owner fits himself, for five boards | **about $5** |
| **Total for a working radio-to-radio link with three spare boards** | **about $153** |

For comparison: rev C's two assembled panels came to **$196.58** and produced
**two** complete links from four boards of two different designs, needing six
mini-HDMI cables. rev D produces **two** complete links from four of its five
boards, with one spare, on **one** cable per link.

**Where the money is, in order:** the components ($66.49, half of it three
chip types), the six Extended-part loading fees ($18.42), shipping ($21.55),
the bare boards ($12.10) and the assembly setup ($9.71). The 519 solder joints
per board cost **83 cents**.

---

## 1. Line by line, in the categories the fab actually bills

JLCPCB, **Economic** assembly, one design, five pieces, 4 layer, 1.6 mm,
lead-free HASL, green, 1 oz. Prices read from JLCPCB's own published schedule
and its instant-quote form.

| Charge | Basis | Cost |
|---|---|---|
| Bare PCB, 64.50 × 64.95 mm, 5 pcs, one design | $7.00 special-offer tier + $5.10 lead-free HASL surcharge | **$12.10** |
| Assembly setup fee | per order | **$8.18** |
| Stencil | per order | **$1.53** |
| **Unique Extended part loading, 6 × $3.07** | per unique Extended part per order | **$18.42** |
| SMT solder joints, 519 per board × 5 | at $0.0016 | **$4.15** |
| Through-hole joints, factory | **none** — see §1.1 | **$0.00** |
| Hand-soldering base fee | not incurred, because there are no factory through-hole joints | **$0.00** |
| Components, 5 x $13.30 | section 2 | **$66.49** |
| Shipping, one shipment to Germany | | **$21.55** |
| **Total** | | **$132.43** |

### 1.1 Two through-hole decisions, and what they save

**The SlimSAS connector has four 2.2 mm through-hole shell tails** on an
otherwise surface-mount part. They are the mechanical anchors that take the
55.5 N insertion force, so they matter. Whether JLCPCB will solder them at all
on an SMD-flagged part is **unverified** — rev C flagged the same question
about the HDMI sockets' shell legs and never got an answer.

**The costing above assumes the owner solders them.** If JLCPCB does them
instead, add 20 joints at $0.0164 = $0.33 **plus the $3.58 hand-soldering base
fee**, so **$3.91**. Either way the board is fine: it arrives with its 74
surface-mount contacts reflowed and holds together; the tails are what stop the
connector being levered off after a hundred insertions.

**Every other through-hole part is hand-fitted, and that is where a real saving
is.** Each distinct through-hole part number is an Extended part to JLCPCB —
**no Basic 2.54 mm through-hole header or socket exists in their library at
all** — so five hand-soldered part numbers would have cost **5 × $3.07 =
$15.35** in loading fees alone, plus their joints, plus the base fee. They cost
the owner about $2 of parts and half an hour instead.

| Hand-fitted | LCSC | 5 boards |
|---|---|---|
| DB1 2×10 female socket, underside | C42431860 | $0.96 |
| DB12 2×3 female socket, underside | **not at LCSC** — their vertical female headers start at 2×4 and the 2×3 they list (C99515) is side entry, which cannot work on a socket that plugs straight down. Buy a 2×4 and cut it down | ~$0.50 |
| CN1 2×5 female socket, underside | C492399 | $0.43 |
| JTAG pass-through 2×5 male header | C492422, or C2977596 for a keyed boxed header | $0.34 |
| Ground-clip 1×2 header | C52016390 | $0.08 |
| M3 screws and 11.04 mm standoffs | outside LCSC | ~$2.00 |
| The connector's four shell tails | part of the connector | $0 |

---

## 2. The components, per board

Seventeen part numbers are placed. **Eleven are Basic and six are Extended**,
and it is the six Extended ones that carry the $18.42.

| Part | LCSC | Tier | Qty | $ @10 | Line |
|---|---|---|---|---|---|
| **SlimSAS 8i 74P right-angle receptacle** | C5432262 | Ext | 1 | 3.17 | **3.17** |
| **Quad LVDS driver DS90LV047A** | C206491 | Ext | 2 | 1.84 | **3.68** |
| **Quad LVDS receiver DS90LV048A** | C87137 | Ext | 2 | 1.43 | **2.86** |
| **Translator/buffer SN74AVC4T245** | C81461 | Ext | 7 | 0.3096 | **2.17** |
| **ESD array TPD4E05U06, 0.5 pF** | C138714 | Ext | 12 | 0.0698 | **0.84** |
| 10 µF 25 V 0805 | C15850 | Basic | 3 | 0.085 | 0.26 |
| 100 nF 0402 | C1525 | Basic | 22 | 0.0046 | 0.10 |
| **2.5 V LDO ME6211C25M5G-N** | C194395 | Ext | 1 | 0.0561 | **0.06** |
| 10 kΩ 0402 | C25744 | Basic | 18 | 0.0031 | 0.06 |
| 330 Ω 0402 | C25104 | Basic | 8 | 0.0044 | 0.04 |
| 100 Ω 0402 | C25076 | Basic | 9 | 0.0029 | 0.03 |
| 0 Ω 0402 | C17168 | Basic | 7 | 0.0028 | 0.02 |
| Ferrite bead 120 Ω / 2 A 0603 | C14709 | Basic | 1 | 0.0159 | 0.02 |
| 1 µF 0402 | C52923 | Basic | 1 | 0.0097 | 0.01 |
| 0 Ω 0805 | C17477 | Basic | 1 | 0.0045 | 0.01 |
| 470 Ω 0402, 1 kΩ 0402 | C25117, C11702 | Basic | 1 each | — | 0.01 |
| **Per board** | | | | | **$13.30** |

**The five lines in bold are 91 % of it.** Three chip types — the connector,
the two LVDS packages — are **$9.71 of $13.30**, and there is nothing to do
about any of them: §7 of `DESIGN_NOTES.md` records that no Basic-tier quad
LVDS part exists in JLCPCB's library from any manufacturer, and no Basic ESD
array of any channel count either.

Nine not-fitted parts appear on the BOM as DNP lines and cost nothing: four
sockets and headers, `R_CLKSEL_B`, `R_DRVEN_PRSNT`, `R_JTAG_FORCE`,
`SL_VLVDS` and `FB2`.

---

## 3. The one part number that is a deliberate cost decision

**All seven translators and gated buffers are the same SN74AVC4T245.** That is
not tidiness; it is $4 a order.

JLCPCB's assembly library contains **no Basic-tier buffer, driver, receiver or
transceiver of any family from any manufacturer.** The whole 244 octal family,
the 125 and 126 quad families and the entire Buffers/Drivers/Receivers/
Transceivers category were swept twice; the complete Basic **logic** range
turns out to be two chips — a hex Schmitt inverter and a shift register. So
every additional logic part number costs its own $3.07.

| Route | Fees | Silicon | Total |
|---|---|---|---|
| **7 × SN74AVC4T245 (chosen)** | **1 × $3.07** | **$2.17** | **$5.24** |
| 74LVC244A octal + 74LVC125A quad | 2 × $3.07 | ~$0.30 | $6.44 |
| 74LVC244A only, if the gating could be squeezed into two 4-bit groups | 1 × $3.07 | $0.17 | $3.24 |

The third row is the only cheaper option and it does not fit: the design needs
three distinct (direction, enable) groups — four always-on read channels plus
TDO, four channels gated by the AUXIO enable, and three gated by the JTAG
enable — which is seven ports, and an octal 244's two 4-bit groups cannot
express it. Two 244s would cost the same fee as seven '245s and more silicon,
in bigger packages.

The same argument retires rev C's AO3400A MOSFET inverter: there is no longer
a complementary level to generate, so the part is gone along with the strap
that needed it.

---

## 4. What rev D removed, and what it cost to remove it

| | rev C | rev D | Saving |
|---|---|---|---|
| Designs to fabricate | 2 + a panel project | **1** | the $16.42 multi-design panel charge and the $23.80 loss of the flat promotional tier — **$40.22** at the PCB stage alone |
| Cables per link | 3 mini HDMI | **1 SlimSAS** | two cables, and the boot-width risk that went with three |
| Connectors per board | 3 | **1** | |
| Upright riser section and its right-angle soldered joint | required | **gone** | |
| ROLE strap: 1×3 header, shunt, MOSFET, 10 k, 100 k | fitted | **gone** | $0.11 of parts, one Extended header fee, and an entire failure-mode analysis |
| Production panel: rails, coupon, three V-scores, mouse bites | a whole third KiCad project | **gone** | and with it the unanswered question of whether JLCPCB would accept a panel mixing V-scores with a mouse-bite separation |
| AC-coupling option and VBIAS divider | 8 links + 2 resistors, not fitted | **gone** | not needed on a fixed-direction link |
| Strap-selected terminations | 4 positions, 2 fitted | **8 fitted, all fixed** | direction is no longer a variable |
| ICs per board | 10 fitted on board A, 8 on board B | **13 fitted** | more chips, fewer boards |
| Shipments | 1 (panel) or 2 (separate orders) | **1** | |

**What rev D added:** the SlimSAS connector at $3.17 against three mini HDMI at
about $2.40 the set, four more translator packages ($1.24) to build the AUXIO
and JTAG paths, and eight more ESD arrays because rev D protects **every**
conductor rather than rev C's subset ($0.56).

---

## 5. What could be cut, ranked by what it saves

| | Change | Saves | What it costs you |
|---|---|---|---|
| 1 | **Leaded HASL instead of lead-free** | **$5.20** | RoHS. The $7.00 promotional PCB tier is priced for leaded |
| 2 | **DS90LV047A in TSSOP-16 (C87097) instead of SOIC-16** | **$4.30** over five boards | $0.43 each. Same silicon, same pinout, smaller package. SOIC-16 was kept for thermal margin — the drivers dissipate the most on the board — and for higher stock (1,741 against 1,099) |
| 3 | **Drop the 2.5 V LDO and take Vlvds instead** (fit `SL_VLVDS` and `FB2`, remove U12) | **$3.35** — one Extended fee and $0.28 of silicon | Do not. §4.2 of `DESIGN_NOTES.md`: the board's 50 mA is the *whole* of the radio's conservative 2.5 V headroom, and the rail it would brown out is the FPGA bank supply carrying the ADC data |
| 4 | **Drop the spare lane's ESD array** and the two spare sideband clamps | **$0.21** | One array, and two conductors that leave the enclosure unclamped. Not worth thinking about |
| 5 | **Order 2 boards instead of 5** | **$39.90** of components | You get one link and no spares. The fixed charges ($60.25) do not move, so the per-board cost rises from $26.49 to **$46.34** |
| 6 | **Order 10 boards** | nothing per board worth naming | components rise $66.49 to $132.98 and joints $4.15 to $8.30, so the total goes to $203.06 and the per-board cost **falls to $20.31**. Economic assembly is capped at 30 pieces per design |

**Do 1 and 2 if you want the money. Do not do 3.**

### 5.1 Impedance control: a decision, not a default

JLCPCB charges **$32.84** for impedance control plus a **mandatory** $1.04
production-file check — **$33.88**, which is a 26 % surcharge on this whole
order and nearly three times the bare-board price.

**Do not take it.** At 307.2 Mbit/s with a 3.2552 ns unit interval, on a
4-layer 1.6 mm stack-up with a solid ground plane directly under the pairs, an
uncontrolled 100 Ω target that lands anywhere between 85 and 115 Ω gives a
reflection coefficient under 8 % — and the connector itself is specified
**85 Ω ±10**, so an 8 % mismatch is already present at the interface by
design. The cable is 100 Ω twinax qualified to 24 Gb/s. Nothing in the chain
needs the guarantee.

ENIG instead of lead-free HASL is **+$12.30** and is a more defensible spend
than impedance control: the SlimSAS contacts are 0.35 mm wide on a 0.60 mm
pitch, which is where a lumpy HASL finish actually bites.

---

## 6. What is not verified in these numbers

| Item | Worth | Status |
|---|---|---|
| **Whether JLCPCB will solder the connector's four through-hole shell tails** | $3.91, and whether the connector arrives mechanically anchored | **Unverified.** Same question rev C asked about the HDMI shell legs and never got answered |
| **The exact solder-joint fee** | a few dollars | JLCPCB will not compute it without a login and an uploaded position file. The 519 joints were counted from the board file here |
| **JLCPCB's own fee schedule disagrees with itself** | pennies | Two of their pages, both dated 9 September 2026, give setup as $8.18 and $8.00 and the SMT joint rate as $0.0016 and $0.0017. Both are live official text; neither was picked over the other for any reason but consistency with rev C |
| **Whether C14709 is really Basic** | $3.07 | Its tier does not print on JLCPCB's own part page; the Basic call comes from the parts database, which matched on every part where a cross-check was possible |
| **Whether Preferred Extended really is fee-exempt on Economic** | $3.07 per such part | JLCPCB says so in their FAQ, but Preferred Extended and plain Extended both print as "Extended" on their part pages. No part in this BOM depends on it |
| **Shipping for the hand-fitted parts** | not in any total here | Whoever you buy the sockets, standoffs and the 2×4-cut-down-to-2×3 from |
| **The cable price** | $15.00 is 10Gtek's current store price, down from a $25.00 list | Check at the point of ordering, and buy it early — §10 of `DESIGN_NOTES.md` wants it ohmmetered before fabrication |

---

## 7. Sources

| | |
|---|---|
| Bare PCB prices, the size cap, impedance control, ENIG, shipping | JLCPCB instant-quote form, US store, read 12 September 2026 (carried forward from rev C, where the 64.5 × 65 mm case was quoted directly as $7.00 + $5.10) |
| Assembly setup, stencil, per-unique-part loading fee, per-joint rates, hand-soldering base fee, the 30-piece Economic cap, through-hole support | `https://jlcpcb.com/help/article/pcb-assembly-price` and `https://jlcpcb.com/help/article/pcb-assembly-faqs`, both read 13 September 2026 |
| Every component price and tier | LCSC product pages and JLCPCB part pages, read 13 September 2026 |
| Cable | `https://store.10gtek.com/24g-internal-slimsas-sff-8654-to-sff-8654-8i-cable-sas-4-0-100-ohm-0-5-1-meter/p-8475` |
| Joint counts | counted from `bridge/bridge.kicad_pcb` — 519 SMT joints and 4 through-hole across 97 factory-placed parts |
