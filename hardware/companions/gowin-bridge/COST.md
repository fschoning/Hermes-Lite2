# gowin-bridge cost analysis — why rev C costs more than rev B, and what could be cut

Written 2026-09-12 in answer to a direct challenge: rev B was quoted at about
$150 for two sets and about $200 for five; rev C at nearly $200 and $288.
Combining the two boards onto one panel should have *reduced* cost by paying
setup once instead of twice, and the only functional addition was the
bidirectional third cable, which is a handful of cheap parts. A 33 % rise
needed explaining line by line.

**Every table here is produced by `tools/cost_model.py`**, which counts the
parts, joints and unique part numbers out of the generated BOMs and PCBs
rather than having them typed in, so the arithmetic cannot drift from the
boards. Re-run it when a price moves:

```
REVB_DIR=<dir with rev B's files from git a15d05a> python tools/cost_model.py
```

---

## 0. The short answer

**The 33 % rise is not real. It is 3.7 %.**

| | two sets |
|---|---|
| rev C | **$196.58** |
| rev B **as published** | $149.82 |
| apparent rise | +$46.76 |
| **of which rev B's own figure understated rev B's own design** | **$39.69** |
| **rev B restated on the same basis** | **$189.51** |
| **real rise** | **+$7.07** |

rev B's $150 never counted the per-joint placement fees, the $3.58-per-order
hand-soldering base fee, or the second shipment that two separate orders need,
and it booked the bare boards at a promotional price that excluded the
lead-free finish surcharge. Restated honestly, **rev B's own design costs
$189.51 and rev C costs $7.07 more** — for a whole extra bidirectional cable.

**And panelising does save money: $16.83.** The instinct behind it was right.

**The bidirectional third cable cost $15.64 at two sets.** It added **no board
area at all** — both boards are exactly the same size in rev C as in rev B —
and, after swapping the strap inverter for a Basic-tier MOSFET, **no extra
per-part assembly fee either.**

---

## 1. The bare-PCB question, settled

This was the one line worth chasing, and it is now answered from JLCPCB's live
quote form (US store, 12 September 2026, 4 layer, 1.6 mm, 5 pieces, lead-free
HASL, green, 1 oz):

| Board | Designs declared | Price | What the quote panel itemised |
|---|---|---|---|
| 94 x 100 mm (the panel) | **1** | **$12.20** | Special Offer $7.00 + surface finish $5.20 |
| 94 x 100 mm (the panel) | **2** | **$52.42** | Engineering fee $25.00 + **Panel $16.42** + surface finish $5.20 + board $5.80 |
| 48 x 66 mm (board A) | 1 | **$12.10** | Special Offer $7.00 + surface finish $5.10 |
| 90 x 46 mm (board B) | 1 | **$12.10** | Special Offer $7.00 + surface finish $5.10 |

**The $40.22 gap between one design and two splits into two charges:**

* **$16.42 is a PCB-side "Panel" charge**, levied for holding more than one
  design in the file. It is flat: identical at 5 pieces and at 10.
* **$23.80 is the loss of the flat promotional tier.** A multi-design file
  cannot use JLCPCB's "Single PCB" delivery mode, and the flat rate only
  exists in that mode. Forcing "Panel by Customer" delivery with *one* design
  already costs $36.00, which isolates this half of the charge cleanly.

**It is not a size effect, and shrinking the panel would save nothing.** The
flat tier survives while both dimensions stay under 100 mm, and **94 x 100 mm
qualifies** — quoted at $12.20 with one design. The cliff is at 100 x 100 mm,
where the form removes "Single PCB" delivery entirely and the price becomes
$36.40; 100 x 150 mm is $39.50. **The panel is already on the cheap side of
that cap.** There is no dimension to give back and nothing to gain by trying.

**rev B's $7.00 was real but incomplete.** The promotional price reproduces
exactly, at $7.00 for both small boards. The $12.10 figures are that $7.00
plus the lead-free HASL surcharge of about $5.10, which rev B's costing had
omitted. So rev B's bare-PCB line should have been **$24.20, not $14.00** —
and that correction alone accounts for $10.20 of the $39.69 by which rev B
understated itself.

### 1a. Two other prices worth knowing before ordering

| Option | Cost | |
|---|---|---|
| **Impedance control** | **+$33.88** | $32.84 for the impedance-control line plus a **mandatory** $1.04 production-file check that cannot be declined. On a $52.42 board that is a 65 % surcharge. `README.md` section 7 and `ROUTING.md` both currently say to order impedance-controlled, and that advice predates knowing the price. **At $33.88 it is a decision, not a default.** See section 5, item 3. |
| **ENIG instead of lead-free HASL** | **+$12.30** | Confirmed. Worth considering for the mini HDMI's 0.23 mm pads. |
| **Leaded HASL instead of lead-free** | **−$5.20** | The promotional $7.00 tier is priced for leaded HASL. If leaded is acceptable the panel drops to $47.22. |

---

## 2. Line by line, in the categories the fab actually bills

Three columns, and the middle one is the honest comparator:

* **rev B as published** — the figure in `STATUS.md` at the time, reproduced
  from its own itemisation.
* **rev B restated** — rev B's own netlist and its own two-separate-orders
  plan, but with rev C's complete set of charge categories, today's verified
  prices, and part numbers corrected where rev B's did not exist.
* **rev C** — the panel, Economic assembly.

**Only the restated column is a fair comparator,** for four reasons:

1. It **omitted three charge categories entirely** — the per-joint SMT fee,
   the per-joint through-hole fee, and the hand-soldering base fee.
2. It **booked the bare boards at $7.00 each**, which is the promotional price
   *before* the lead-free finish surcharge. The real figure is $12.10 each.
3. It **assumed one shipment for two separate orders.**
4. Its BOM **could not have been ordered.** Three of its LCSC part numbers do
   not exist, and two more are real but absent from JLCPCB's assembly library.
   The restated column substitutes the corrected numbers into the same slots.

### 2a. Two assembled sets

| charge category | rev B as published | rev B restated | rev C | delta (restated → rev C) |
|---|---|---|---|---|
| bare PCB, 5 pcs | $14.00 | $24.20 | $52.42 | **+$28.22** |
| assembly setup | $16.36 (2 orders) | $16.36 | $8.18 | −$8.18 |
| stencil | $3.06 (2 orders) | $3.06 | $1.53 | −$1.53 |
| assembly panel fee (file holds >1 design) | $0.00 | $0.00 | $8.21 | **+$8.21** |
| loading, Extended — 16 vs 11 uniques at $3.07 | $49.12 | $49.12 | $33.77 | **−$15.35** |
| loading, Basic — free on Economic | $0.00 | $0.00 | $0.00 | $0.00 |
| SMT joints — 655 vs 781 per set at $0.0016 | *not counted* | $2.10 | $2.50 | +$0.40 |
| through-hole joints — 109 vs 89 per set at $0.0164 | *not counted* | $3.58 | $2.92 | −$0.66 |
| hand-soldering base fee, per order | *not counted* | $7.16 | $3.58 | −$3.58 |
| reel-only minimum batches | $6.50 | $8.06 | $8.73 | +$0.67 |
| silicon and connectors, 2 sets | $32.78 | $32.78 | $47.75 | **+$14.97** |
| sockets bought retail, 2 sets | $0.00 | $0.00 | $5.44 | +$5.44 |
| shipping | $28.00 (1 shipment) | $43.10 (2 shipments) | $21.55 | **−$21.55** |
| **TOTAL** | **$149.82** | **$189.51** | **$196.58** | **+$7.07** |

The deltas are computed and they sum to $7.07.

**A confidence check on the reconstruction.** The "as published" column is
re-derived from rev B's own itemisation, not copied from its headline. It comes
to **$149.82** against the "about $150" rev B claimed, and at five sets to
**$198.99** against its "roughly $200". Both land within a dollar, so the
reconstruction is sound and the differences that follow are real.

### 2b. Five assembled sets

| charge category | rev B as published | rev B restated | rev C | delta |
|---|---|---|---|---|
| bare PCB, 5 pcs | $14.00 | $24.20 | $52.42 | **+$28.22** |
| assembly setup | $16.36 | $16.36 | $8.18 | −$8.18 |
| stencil | $3.06 | $3.06 | $1.53 | −$1.53 |
| assembly panel fee | $0.00 | $0.00 | $8.21 | +$8.21 |
| loading, Extended, 16 vs 11 | $49.12 | $49.12 | $33.77 | −$15.35 |
| SMT joints, 5 sets | *not counted* | $5.24 | $6.25 | +$1.01 |
| through-hole joints, 5 sets | *not counted* | $8.94 | $7.30 | −$1.64 |
| hand-soldering base fee | *not counted* | $7.16 | $3.58 | −$3.58 |
| reel-only minimum batches | $6.50 | $8.06 | $8.73 | +$0.67 |
| silicon and connectors, 5 sets | $81.95 | $81.95 | $119.39 | **+$37.43** |
| sockets bought retail, 5 sets | $0.00 | $0.00 | $13.60 | +$13.60 |
| shipping | $28.00 | $43.10 | $21.55 | **−$21.55** |
| **TOTAL** | **$198.99** | **$247.19** | **$284.50** | **+$37.31** |

At five sets the third cable's parts are paid five times and the fixed-fee
savings are not, so the gap widens to $37.31 — of which **$39.10 is the third
cable itself.** Everything else nets to slightly *less* than rev B.

### 2c. Where the money went, ranked

Against **rev B restated**, at two sets:

| | |
|---|---|
| bare PCB — the two-design charge and the lost flat tier | **+$28.22** |
| silicon and connectors — the third cable, almost entirely | **+$14.97** |
| assembly-side panel fee for declaring two designs | +$8.21 |
| two sockets now bought retail instead of from the fab | +$5.44 |
| reel minimums and SMT joints | +$1.07 |
| **increases** | **+$57.91** |
| one shipment instead of two | **−$21.55** |
| Extended loading fees paid once instead of twice | **−$15.35** |
| one setup, one stencil, one hand-solder base fee instead of two | −$13.29 |
| through-hole joints — fewer, because two sockets left the fab's BOM | −$0.66 |
| **savings** | **−$50.85** |
| **net** | **+$7.07** |

---

## 3. Does panelising save money or cost it?

**It saves $16.83, at both two sets and five.**

| | ONE panel | TWO separate orders | delta |
|---|---|---|---|
| bare PCB, 5 pcs | $52.42 | $24.20 | **+$28.22** |
| assembly setup | $8.18 | $16.36 | −$8.18 |
| stencil | $1.53 | $3.06 | −$1.53 |
| assembly panel fee (>1 design) | $8.21 | $0.00 | **+$8.21** |
| Extended loading — 11 uniques vs 17 | $33.77 | $52.19 | **−$18.42** |
| hand-soldering base fee | $3.58 | $7.16 | −$3.58 |
| shipping | $21.55 | $43.10 | **−$21.55** |
| identical on both (parts, joints, reel minimums, retail sockets) | $67.34 | $67.34 | $0.00 |
| **TOTAL, two sets** | **$196.58** | **$213.41** | **−$16.83** |

**The two things that make the panel win are not the obvious ones.**

* **Duplicated per-part loading fees, −$18.42.** Two separate orders pay a
  $3.07 fee for each Extended part *on each board*: **9 on board A plus 8 on
  board B = 17 fees.** The panel is one order with **11** unique Extended
  parts, because six are common to both boards. That saving alone is more than
  twice the $8.21 assembly panel fee.
* **One shipment instead of two, −$21.55.** **If the two separate orders can
  be combined into one shipment — which JLCPCB will sometimes do for orders
  placed together, but which is unverified — two orders come to $191.86 and
  beat the panel by $4.72.** At that point it is a coin toss and either route
  is fine. Both individual projects are kept for exactly this reason.

**Both panel fees are real and separate.** There is a **$16.42 PCB-side**
"Panel" charge (inside the $52.42 above) and an **$8.21 assembly-side** panel
fee, confirmed on JLCPCB's own pricing page as "applicable when the number of
panelized designs > 1". Ordering fabrication and assembly together with two
designs pays both, once each.

### 3a. The six Extended parts that two separate orders pay for twice

| Extended part | LCSC | board A | board B | |
|---|---|---|---|---|
| quad LVDS driver | `C206491` | yes | yes | **both — paid twice** |
| quad LVDS receiver | `C87137` | yes | yes | **both — paid twice** |
| 4-bit gated buffer | `C81461` | yes | yes | **both — paid twice** |
| quad ESD array | `C138714` | yes | yes | **both — paid twice** |
| 1x3 pin header | `C52016391` | yes | yes | **both — paid twice** |
| 1x2 pin header | `C52016390` | yes | yes | **both — paid twice** |
| 8-bit level translator | `C465742` | yes | — | one board |
| 2.5 V LDO | `C194395` | yes | — | one board |
| mini HDMI socket | `C2682170` | yes | — | one board |
| full-size HDMI socket | `C427307` | — | yes | one board |
| 2x20 socket (Tang J14) | `C5124634` | — | yes | one board |

**11 unique Extended parts on the panel at $3.07 each = $33.77. 9 + 8 = 17
fees if ordered separately = $52.19.** The six shared parts are the whole
difference: **$18.42**.

### 3b. The rails and the coupon are not the problem

| | area |
|---|---|
| panel, 94 x 100 | 9400 mm² |
| board A, 48 x 66 | 3168 mm² |
| board B, 90 x 46 | 4140 mm² |
| **useful** | **7308 mm²** |
| **overhead** | **2092 mm², 22.3 % of the panel** |
| — two 5 mm rails, 2 x 94 x 5 | 940 mm² |
| — fiducial coupon, 48 x 22 | 1056 mm² |
| — routed separation channel, 48 x 2 | 96 mm² |

The 22.3 % overhead looks like the answer and it is not, for three reasons.

**The coupon costs nothing.** Board B rotated is **90 mm tall**, and two 5 mm
rails make the panel **100 mm** whatever else happens. Board A is only **66 mm**
tall, so the 48 x 24 mm strip beneath it is dead space the panel carries
anyway. The coupon fills 1056 of those 1152 mm². **Deleting it would not make
the panel one millimetre smaller.**

**JLCPCB does not price this board by area.** Section 1 settles it: at one
design the 94 x 100 panel and the 48 x 66 board cost within ten cents of each
other. Area is simply not the variable.

**And the panel is already inside the size cap**, so there is no bracket to
duck under by shrinking.

---

## 4. What the bidirectional third cable actually cost

### 4a. Attributable to the third cable

| Added | Qty per set | Unit | Per set |
|---|---|---|---|
| Quad LVDS drivers — board A goes 2→3, board B goes 1→3 | 3 | $1.8396 | $5.52 |
| Quad LVDS receiver — board A gains the auxiliary receiver | 1 | $1.4348 | $1.43 |
| 4-bit gated buffers — one per board, to tri-state the auxiliary receive path | 2 | $0.3096 | $0.62 |
| N-MOSFET strap inverters — one per board | 2 | $0.0800 | $0.16 |
| Quad ESD array — board A goes 8→9, for the third socket's pins | 1 | $0.0874 | $0.09 |
| **Parts, per set** | | | **$7.82** |

| | |
|---|---|
| **Third cable, 2 sets** | **$15.64** |
| Third cable, 3 sets | $23.46 |
| Third cable, 5 sets | $39.10 |

**Extra unique Extended parts: zero.** The strap's inverter is a **Basic-tier
MOSFET**, so it carries no per-part loading fee at all (section 5a).

**Extra board area: zero.** Board A is 48 x 66 mm and board B is 90 x 46 mm in
both revisions. The third socket and five extra chips fitted in the space rev B
already had.

**Extra joints: +126 surface-mount and −20 through-hole per set**, which is
+$0.40 and −$0.66 at two sets — a net *saving* of $0.26, because two
through-hole sockets left the fab's BOM at the same time.

### 4b. NOT attributable to the third cable

| Increase | At 2 sets | What it really is |
|---|---|---|
| **Bare PCB** | **+$28.22** | The two-design declaration. Nothing to do with the third cable, and nothing to do with size. |
| **Assembly panel fee** | **+$8.21** | Panelising. |
| **Two sockets bought retail** | **+$5.44** | The part-number correction. rev B believed the vertical 2x3 socket and the long-tail 2x10 socket were buyable from LCSC. Neither is. |
| **Two extra Extended parts** | **+$6.14** | The part-number correction, *not* the strap. rev B listed the pin headers as one 1x40 strip; JLCPCB's BOM matcher will not accept a 40-pin part against a 3-pin footprint, so it became two discrete parts, both Extended. |
| **Reel minimums** | **+$0.67** | Two more minimum-order batches, for the 0805 zero-ohm link and the two header part numbers. |
| Joint and hand-solder fees | *see 2a* | Categories rev B never counted. |

---

## 5. What could be cut, ranked by what it saves

Figures at **two assembled sets**, counted from the BOMs by
`tools/cost_model.py`.

| # | Cut | Saves | What is lost |
|---|---|---|---|
| 1 | **✅ DONE — the Extended single-gate inverter is now a Basic-tier MOSFET** | **$3.11** | Nothing measurable. Applied in this revision; section 5a examines it point by point. |
| 2 | **Do not pay for impedance control** | **$33.88** | The fab's *guarantee* that the 100 Ω differential pairs land on 100 Ω, and the measurement report. $32.84 for the control plus a mandatory $1.04 file check — a 65 % surcharge on a $52.42 board, and **the largest single line on this list.** Against buying it: the geometry in `ROUTING.md` is designed to JLCPCB's published `JLC04161H-7628` stackup, every pair is externally terminated in 100 Ω, and the signals cross 2 m of cable, so a ±10 % trace impedance is very unlikely to be what fails. **This is an open decision, not a recommendation** — `README.md` and `ROUTING.md` still say to buy it, and that advice was written before the price was known. |
| 3 | **Ship Global Standard Direct Line instead of DHL Express** | **$14.63** | 9–13 days instead of 2–4. No design change at all. |
| 4 | **Hand-fit the seven pin headers instead of having the fab place them** | **$8.04** | You solder 19 through-hole pins per set. Saves two Extended loading fees ($6.14), two reel minimums ($1.28) and 38 joints ($0.62). Buy a 1x40 strip for about $0.16 and snap it. Best value-per-effort cut on the list. |
| 5 | **Hand-fit the Tang dock's 2x20 socket too** | **$5.04** | You solder 40 more through-hole pins per set. Saves one Extended loading fee ($3.07), the part ($0.66) and 80 joints ($1.31). You are already told to solder the mating male header into the dock. The $3.58 hand-soldering base fee does **not** go away: the six HDMI sockets are hybrid-mount and their four through-hole shell legs each still need soldering, 30 joints per set. Whether JLCPCB will solder those legs at all is **unverified**; if not, the base fee goes too (a further $3.58) and you solder them, but the connectors then rely on their surface-mount contacts alone until you do. |
| 6 | **Leaded HASL instead of lead-free** | **$5.20** | RoHS compliance, and a finish that is slightly less pleasant to rework by hand. The $7.00 promotional tier is priced for leaded. |
| 7 | **Merge the 0805 zero-ohm links into 0402** | **$0.45** | One reel minimum, and that is all: Basic loading is free. It also makes lifting a cable shield by hand harder. **Not worth it.** |
| 8 | **Drop the AC-coupling option footprints** | **~$0.30** | The only escape route if the link turns out to need AC coupling. The option's 32 parts per set use only two part numbers: 100 nF, already placed as decoupling, and 4k7, which is **never placed** and so carries no loading fee — only a reel minimum. **Do not cut this. It is almost free.** |
| 9 | **Drop all 82 test points per set** | **$0.00** | All bring-up visibility, for nothing. Test points have no part number: no part cost, no loading fee, no joint fee. **Non-item.** |
| 10 | **Shrink or delete the fiducial coupon** | **$0.00** | Nothing is saved. Board B rotated already sets the panel's 100 mm height, and the panel is already inside the size cap (sections 1 and 3b). **Non-item.** |
| 11 | **Consolidate resistor and capacitor values** | **$0.00** | Nothing on Economic assembly. There are only **10 distinct placed passive part numbers** per set, **all Basic**, and **Basic loading is free**. The 35 zero-ohm links are two part numbers, not many. On **Standard** assembly each value removed would save $1.53 — but Standard is the wrong service here. **The suspicion that "34 and 50 resistors are probably many distinct values" is not borne out: they are seven values.** |
| 12 | **Abandon the panel for two separate orders** | **−$16.83** (costs more), or **+$4.72** if the two orders can be combined into one shipment | Nothing functional. See section 3. |

### 5a. The inverter swap, applied — and what it gives up

**No 74x1G04, 1G00, 1G02, 1G14 or 1G07 of any brand, family or package is a
Basic part in JLCPCB's library** — checked across all ten manufacturers they
list. One logic gate would therefore have cost the $3.07
per-unique-Extended-part fee on the Economic tier, which is what we are on.

Replaced with **one N-channel MOSFET: Alpha & Omega AO3400A, LCSC C20917,
SOT-23, Basic tier, about 890,000 in stock, about $0.08.** Gate on `ROLE`,
source to ground, drain on `ROLE_N`, loaded by the **10 kΩ pull-up that was
already fitted**. Pin 1 gate, pin 2 source, pin 3 drain.

**Saving: $3.11** — the $3.07 loading fee plus $0.013 of parts, and one fewer
unique Extended part on the panel, 12 down to 11.

**Why the 2N7002 was rejected** even though it is cheaper: its gate threshold
is specified up to **2.5 V**, too close to a 3.3 V drive. The AO3400A's is
**1.45 V maximum**, leaving **1.85 V of margin** — a genuine logic-level part.

**What is given up, point by point:**

* **`ROLE_N`'s high state is now passive**, supplied by the 10 kΩ pull-up
  rather than actively driven. **Acceptable**: `ROLE_N` drives only CMOS enable
  inputs — one LVDS driver `EN` and one translator `OE` per board — whose input
  leakage is nanoamps to a few microamps. At a worst case of 20 µA the pull-up
  drops 0.2 V, giving 3.1 V against enable thresholds around 2.0 V.
* **The pull-up's rise time is slow.** **Irrelevant**: `ROLE_N` is a static
  level set once by a jumper and never switched in operation. Nothing on either
  board ever sees an edge on it.
* **The low state is better, not worse.** The MOSFET's on-resistance is tens of
  milliohms, so with 0.33 mA flowing through the 10 kΩ load the drain sits
  within microvolts of ground — cleaner than a logic gate's specified output
  low. Standing current is unchanged: a logic inverter pulling the same node
  down through the same pull-up drew the same 0.33 mA.
* **No hysteresis regression.** The part it replaces, SN74LVC1G04, is a
  **plain** inverter with no Schmitt input either, so nothing is lost. And
  `ROLE` is never in transition: it is hard 3.3 V or hard 0 V through a shunt,
  or 0 V through the 100 kΩ pull-down when no shunt is fitted.
* **The fail-safe direction is unchanged**, which is the point that matters
  most. A missing, dead or unpowered device leaves `ROLE_N` pulled **high** by
  the 10 kΩ resistor, which **disables** the auxiliary port facing the host.
  That is the auxiliary-disabled state: the link fails to work and nothing is
  stressed. It can never enable a port.
* **Power-up is also safe, and this is new.** The MOSFET stays off until its
  gate passes about 1.45 V, so during the supply ramp `ROLE_N` is held high by
  the pull-up — again the auxiliary-disabled state.
* **What is genuinely weaker:** the input threshold is a device parameter with
  a manufacturing spread, rather than a specified fraction of the supply rail
  as a logic gate guarantees. For a jumper level that is either 0 V or 3.3 V,
  with 1.85 V of margin to the worst-case threshold, this does not matter.

`tools/check_netlist.py` was updated for it and still proves the contention
case impossible on both boards, enumerating both strap states. It now also
checks that the source is grounded — a MOSFET inverter only inverts with its
source at ground.

### 5b. Why a strap with no complement at all is not available

Worth recording, since it is the obvious thing to try. The DS90LV047A driver
has **both** an active-high `EN` and an active-low `EN*`, so the two LVDS
drivers *could* be gated from a single strap net with no inverter at all. But
the host-facing buffer is an SN74AVC4T245, which offers only an **active-low**
`OE` per port, so one of its two ports still needs the complement. A pair such
as the 74LVC125A (active-low enables) plus the 74LVC126A (active-high) would
remove the need, at the cost of two packages instead of one. **The complement
is genuinely required, and only by the buffers.** One MOSFET is the cheapest
way to produce it.

---

## 6. The cheapest credible configuration for two working sets

| | |
|---|---|
| rev C panel, Economic assembly, DHL Express, **with** impedance control | **$230.46** |
| − skip impedance control (section 5, item 2 — read it before deciding) | −$33.88 |
| **As costed everywhere else in this repository** | **$196.58** |
| − ship Global Standard Direct Line instead (9–13 days) | −$14.63 |
| − hand-fit the seven pin headers (19 pins per set) | −$8.04 |
| − hand-fit the Tang dock 2x20 socket (40 pins per set) | −$5.04 |
| **Cheapest with a lead-free finish** | **$168.87** |
| − leaded HASL instead of lead-free | −$5.20 |
| **Cheapest overall** | **$163.67** |

Nothing in that list changes a single net. The schematic is untouched.

**Five sets** at the same settings is $284.50 − $14.63 − $8.04 − $5.04 =
**$256.79, or $51 each**, against **$84 each** for two. The fixed fees dominate
at these quantities, so if more than two sets will ever be wanted, five is much
better value than three — and ordering exactly three is the worst option of
all, because JLCPCB's Economic service appears to offer only 2 or 5 assembled
out of a 5-board run, which forces the dearer Standard tier. **That limit is
unverified** — see section 7.

---

## 7. What is not verified

| Item | Why it matters | Status |
|---|---|---|
| **Whether a two-design file is billed as ONE assembly job or TWO.** JLCPCB's published pages do not say. Every table here assumes one job plus the $8.21 panel surcharge. | **The largest remaining uncertainty.** If it is two jobs — two setups and two stencils, $9.71 more — the panel's $16.83 advantage falls to about $7; if the loading fees were duplicated too, the panel would lose outright. | **Unverified.** Ask before ordering. |
| **Whether Economic assembly really offers only 2 or 5 units** out of a 5-board fabrication run, with no 3. | Decides whether three sets can avoid the Standard tier. | **Unverified.** A third-party guide is consistent with it; JLCPCB's own pages do not state it and the live form could not be driven far enough to see the selector. |
| **Whether two separate orders can be combined into one shipment.** | $21.55, and it flips section 3's verdict from "the panel saves $16.83" to "two orders save $4.72". | **Unverified.** |
| **Whether impedance control is worth $33.88 here.** | The largest optional cost in the order, and two documents currently recommend buying it. | **Open decision**, not merely unverified. |
| **That Basic parts carry no feeder fee on Economic.** JLCPCB's pricing page lists only the $3.07 Extended fee, with no Basic line at all. Consistent with free, but it is an inference. | Every total here rests on it. If Basic parts were chargeable, add 12 × whatever the fee is. | **Inferred, not quoted.** |
| **The per-joint fees.** Both rates were confirmed on JLCPCB's own pricing page, but they will not compute the total without a login and an uploaded placement file. The counts — 781 surface-mount and 89 through-hole per panel — were counted from the board files. | About $5.42 of $196.58. Changes nothing. | Rates confirmed; total not quoted. |
| **Whether JLCPCB will accept a panel mixing V-scores with one mouse-bite separation.** Their FAQ says, verbatim: *"For Economic assembly, please panelize your boards with mouse-bites. for Standard assembly, you can panelize with mouse-bites or V-cut."* | If refused for Economic, the fallback is two separate orders, which section 3 prices at $16.83 more. | **Rule confirmed; willingness to waive it not confirmed.** Ask before paying. |
| **Whether JLCPCB will solder the hybrid-mount HDMI sockets' through-hole shell legs.** | $3.58, and whether the connectors arrive mechanically secured. | **Unverified.** |
| **Shipping from Mouser and from Phoenix Enterprises to Germany** for the two retail sockets. | Not in any total here. | **Unverified.** |
| **The AO3400A's exact price and stock**, which came in as "about $0.08, about 890,000 in stock". Its Basic classification, SOT-23 package, pinout and 1.45 V maximum threshold were all confirmed. | About $0.01. Negligible. | Price approximate. |
| **The reel-minimum figure for rev B** ($8.06) is estimated from its larger passive set; rev C's $8.73 is itemised from LCSC's own batch prices. | $0.67. Negligible. | Estimated for rev B only. |

---

## 8. Sources

| Figure | Source |
|---|---|
| Bare PCB prices at every size and design count, the size cap, impedance control, ENIG, shipping options | JLCPCB instant quote form, US store, read 12 Sep 2026 |
| Assembly setup, stencil, panel fee, per-unique-part loading fees, per-joint rates, hand-soldering base fee, the $0.48-per-board minimum assembly charge | `https://jlcpcb.com/help/article/pcb-assembly-price`, read 12 Sep 2026 |
| The Economic mouse-bite-only panelisation rule | `https://jlcpcb.com/help/article/pcb-assembly-faqs` question 11, read 12 Sep 2026 |
| Basic versus Extended classification, per part | JLCPCB's own parts library search, read 12 Sep 2026 |
| Unit prices, stock, minimum order quantities | LCSC product pages, read 12 Sep 2026 |
| Retail socket prices | Mouser (Samtec SSQ-103-02-S-D) and Phoenix Enterprises (HWS16492), read 12 Sep 2026 |
| Part counts, joint counts, unique-part counts, board areas | Counted from the generated BOMs and PCBs by `tools/cost_model.py` |
| rev B's figures | `STATUS.md` at git commit `5c62b90`; rev B's BOMs and PCBs at git commit `a15d05a` |
