# gowin-bridge cost analysis — why rev C costs more than rev B, and what could be cut

Written 2026-09-12 in answer to a direct challenge: rev B was quoted at about
$150 for two sets and about $200 for five; rev C at $199.70 and $287.70.
Combining the two boards onto one panel should have *reduced* cost by paying
setup once instead of twice, and the only functional addition was the
bidirectional third cable, which is a handful of cheap parts. A 33 % rise
needs explaining line by line.

**Every table here is produced by `tools/cost_model.py`**, which counts the
parts, joints and unique part numbers out of the generated BOMs and PCBs
rather than having them typed in, so the arithmetic cannot drift from the
boards. Re-run it when a price moves:

```
REVB_DIR=<dir with rev B's files from git a15d05a> python tools/cost_model.py
```

---

## 0. The short answer

**The rise is real but it is half what it looks like, and it is almost
entirely one line.**

| | |
|---|---|
| rev C, two sets | **$199.70** |
| rev B **as published** | **$149.82** |
| apparent rise | **+$49.88** |
| **of which rev B's own figure was an undercount of rev B's own design** | **$29.49** |
| **of which is a real rev C increase** | **$20.39** |

rev B's $150 never counted the per-joint placement fees, the hand-soldering
base fee, or the second shipment that two separate orders require. Restated on
the same basis as rev C, **rev B's own design costs $179.31**.

**And the whole of the remaining $20.39 is the bare-PCB line, plus a bit.**
The bare PCB went from $14.00 to $52.42, an increase of **$38.42**;
everything else combined went *down* by **$18.03**. So panelising did do what
it was supposed to do on the assembly side — it is the price of the bare panel
that ate the saving and more.

**The bidirectional third cable cost $18.74 at two sets.** That is the feature,
priced. It added no board area at all: both boards are exactly the same size
in rev C as in rev B.

> ### The one figure that decides everything
>
> **Bare PCB, 5 pieces, 4 layer, 1.6 mm, lead-free HASL:**
> **$7.00 each for 48 x 66 mm and for 90 x 46 mm, against $52.42 for
> 94 x 100 mm.**
>
> The $7.00 figures were recorded as *"a live JLCPCB promotional tier, not
> list price"*. The $52.42 was quoted with **"Different designs in this file"
> set to 2**.
>
> A 94 x 100 mm board is 2.3 times the area of a 90 x 46 mm one, and a 7.5
> times price jump is not an area effect. It is either the promotional tier
> having a size cap the panel exceeds, or a surcharge for declaring two
> designs, or both. **PENDING VERIFICATION — see section 6.** If it turns out
> to be the multi-design declaration or a cap the panel could duck under, this
> whole cost question disappears and rev C becomes *cheaper* than rev B.

---

## 1. Line by line, in the categories the fab actually bills

Three columns, and the middle one is the honest comparator:

* **rev B as published** — the figure in `STATUS.md` at the time, reproduced
  from its own itemisation.
* **rev B restated** — rev B's own netlist and its own two-separate-orders
  plan, but with rev C's complete set of charge categories, today's verified
  unit prices, and the part numbers corrected where rev B's did not exist.
* **rev C** — the panel, Economic assembly.

**Which of the two rev B columns is trustworthy: the restated one.** rev B as
published is not a like-for-like comparator and should not be used, for three
reasons stated plainly:

1. It **omitted three charge categories entirely** — the per-joint SMT fee,
   the per-joint through-hole fee, and the $3.58-per-order hand-soldering base
   fee.
2. It **assumed one shipment for two separate orders.** Two orders normally
   means two shipments.
3. Its BOM **could not have been ordered.** Three of its LCSC part numbers do
   not exist (the 8-bit translator, the 2x10 socket and, as described, the 2x3
   socket), and two more are real but absent from JLCPCB's assembly library
   (the quad LVDS driver, which also had zero stock, and a 470 R resistor).
   The restated column substitutes the corrected numbers into the same slots.

### 1a. Two assembled sets

| charge category | rev B as published | rev B restated | rev C | delta (restated → rev C) |
|---|---|---|---|---|
| bare PCB, 5 pcs | $14.00 | $14.00 | $52.42 | **+$38.42** |
| assembly setup | $16.36 (2 orders) | $16.36 | $8.18 | −$8.18 |
| stencil | $3.06 (2 orders) | $3.06 | $1.53 | −$1.53 |
| panel fee (file holds >1 design) | $0.00 | $0.00 | $8.21 | **+$8.21** |
| loading, Extended — 16 vs 12 uniques at $3.07 | $49.12 | $49.12 | $36.84 | **−$12.28** |
| loading, Basic — free on Economic | $0.00 | $0.00 | $0.00 | $0.00 |
| SMT joints — 655 vs 789 per set at $0.0016 | *not counted* | $2.10 | $2.52 | +$0.43 |
| through-hole joints — 109 vs 89 per set at $0.0164 | *not counted* | $3.58 | $2.92 | −$0.66 |
| hand-soldering base fee, per order | *not counted* | $7.16 | $3.58 | −$3.58 |
| reel-only minimum batches | $6.50 | $8.06 | $8.73 | +$0.67 |
| silicon and connectors, 2 sets | $32.78 | $32.78 | $47.78 | **+$15.00** |
| sockets bought retail, 2 sets | $0.00 | $0.00 | $5.44 | +$5.44 |
| shipping | $28.00 (1 shipment) | $43.10 (2 shipments) | $21.55 | **−$21.55** |
| **TOTAL** | **$149.82** | **$179.31** | **$199.70** | **+$20.39** |

The deltas sum to $20.39, which is the headline difference. They are computed,
not reconciled by hand.

### 1b. Five assembled sets

| charge category | rev B as published | rev B restated | rev C | delta |
|---|---|---|---|---|
| bare PCB, 5 pcs | $14.00 | $14.00 | $52.42 | **+$38.42** |
| assembly setup | $16.36 | $16.36 | $8.18 | −$8.18 |
| stencil | $3.06 | $3.06 | $1.53 | −$1.53 |
| panel fee | $0.00 | $0.00 | $8.21 | +$8.21 |
| loading, Extended, 16 vs 12 | $49.12 | $49.12 | $36.84 | −$12.28 |
| SMT joints, 5 sets | *not counted* | $5.24 | $6.31 | +$1.07 |
| through-hole joints, 5 sets | *not counted* | $8.94 | $7.30 | −$1.64 |
| hand-soldering base fee | *not counted* | $7.16 | $3.58 | −$3.58 |
| reel-only minimum batches | $6.50 | $8.06 | $8.73 | +$0.67 |
| silicon and connectors, 5 sets | $81.95 | $81.95 | $119.45 | **+$37.50** |
| sockets bought retail, 5 sets | $0.00 | $0.00 | $13.60 | +$13.60 |
| shipping | $28.00 | $43.10 | $21.55 | **−$21.55** |
| **TOTAL** | **$198.99** | **$236.99** | **$287.70** | **+$50.71** |

At five sets the silicon delta triples to $37.50 and the fixed-fee savings do
not, so the gap widens. That is arithmetic, not a surprise: the third cable
costs its parts once per set.

### 1c. Where the money actually went, ranked

Against **rev B restated**, at two sets:

| | |
|---|---|
| bare PCB | **+$38.42** |
| silicon and connectors (the third cable, mostly) | **+$15.00** |
| panel fee for declaring two designs | +$8.21 |
| two sockets now bought retail instead of from the fab | +$5.44 |
| reel minimums, joints | +$1.10 |
| **subtotal of increases** | **+$68.17** |
| one shipment instead of two | **−$21.55** |
| Extended loading fees paid once instead of twice | **−$12.28** |
| one setup, one stencil, one hand-solder base fee instead of two | −$13.29 |
| through-hole joints (fewer, because two sockets left the fab's BOM) | −$0.66 |
| **subtotal of savings** | **−$47.78** |
| **net** | **+$20.39** |

---

## 2. Does panelising save money or cost it?

**It saves $9.70, at both two sets and five** — and the margin is thin enough
that it is not worth arguing with the fab about.

| | ONE panel | TWO separate orders | delta |
|---|---|---|---|
| bare PCB, 5 pcs | $52.42 | $14.00 | **+$38.42** |
| assembly setup | $8.18 | $16.36 | −$8.18 |
| stencil | $1.53 | $3.06 | −$1.53 |
| panel fee (>1 design) | $8.21 | $0.00 | **+$8.21** |
| Extended loading — 12 uniques vs 19 | $36.84 | $58.33 | **−$21.49** |
| hand-soldering base fee | $3.58 | $7.16 | −$3.58 |
| shipping | $21.55 | $43.10 | **−$21.55** |
| identical on both (parts, joints, reel minimums, retail sockets) | $67.39 | $67.39 | $0.00 |
| **TOTAL, two sets** | **$199.70** | **$209.40** | **−$9.70** |

**The two things that make the panel win are not the ones you would expect.**

* **Duplicated loading fees, −$21.49.** Two separate orders pay a $3.07
  loading fee for each Extended part *on each board*. Board A has 10 unique
  Extended parts and board B has 9, so two orders pay **19** fees. On the
  panel it is one order with **12** unique Extended parts, because seven parts
  are common to both boards: the quad LVDS driver, the quad LVDS receiver, the
  4-bit gated buffer, the quad ESD array, the single-gate inverter and both
  pin headers. Section 2b lists them. That saving alone is more than twice the
  panel fee.
* **One shipment instead of two, −$21.55.** **This is the whole margin.**
  If the two separate orders can be combined into one shipment — which JLCPCB
  will sometimes do for orders placed together, but which is **unverified** —
  then two orders come to **$187.85 and beat the panel by $11.85.**

So the honest verdict: **panelising is a wash.** It wins by $9.70 if you pay
two shipments, and loses by $11.85 if you do not. Both boards' individual
projects are kept, so either route is available.

### 2a. The rails and the coupon are not the problem

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

The 22.3 % overhead looks like the answer and it is not, for two reasons.

**The coupon costs nothing.** Board B rotated is **90 mm tall**, and two 5 mm
rails make the panel **100 mm** whatever else happens. Board A is only **66 mm**
tall, so the 48 x 24 mm strip beneath it is dead space the panel has to carry
anyway. The coupon fills 1056 of those 1152 mm². **Deleting it would not make
the panel one millimetre smaller.**

**The rails are 940 mm², 10 % of the panel.** Dropping them would make the
panel 94 x 90 mm. Whether that saves anything depends entirely on which price
bracket each size lands in, which is the pending question in section 6 — and
JLCPCB normally wants rails for an assembly job, so this is probably not
available anyway. **Unverified.**

**And JLCPCB does not price by area; it prices in size brackets.** A 2.3 times
area increase producing a 7.5 times price increase is a bracket boundary, not
a per-square-millimetre charge. Which is why section 6 matters more than this
section does.

### 2b. The seven Extended parts that two separate orders pay for twice

| Extended part | LCSC | on board A | on board B | |
|---|---|---|---|---|
| 1x2 pin header | `C52016390` | yes | yes | both (paid twice) |
| 1x3 pin header | `C52016391` | yes | yes | both (paid twice) |
| 2.5 V LDO | `C194395` | yes | — | one board |
| 2x20 socket (Tang J14) | `C5124634` | — | yes | one board |
| 4-bit gated buffer | `C81461` | yes | yes | both (paid twice) |
| 8-bit level translator | `C465742` | yes | — | one board |
| full-size HDMI socket | `C427307` | — | yes | one board |
| mini HDMI socket | `C2682170` | yes | — | one board |
| quad ESD array | `C138714` | yes | yes | both (paid twice) |
| quad LVDS driver | `C206491` | yes | yes | both (paid twice) |
| quad LVDS receiver | `C87137` | yes | yes | both (paid twice) |
| single-gate inverter | `C7827` | yes | yes | both (paid twice) |

**12 unique Extended parts on the panel, one $3.07 fee each = $36.84.**
**10 on board A plus 9 on board B = 19 fees if ordered separately = $58.33.**
The 7 parts marked "both" are the whole difference: $21.49.

---

## 3. What the bidirectional third cable actually cost

Separated from everything else that changed between rev B and rev C.

### 3a. Attributable to the third cable

| Added | Qty per set | Unit | Per set |
|---|---|---|---|
| Quad LVDS drivers — board A goes 2→3, board B goes 1→3 | 3 | $1.8396 | $5.52 |
| Quad LVDS receiver — board A gains the auxiliary receiver | 1 | $1.4348 | $1.43 |
| 4-bit gated buffers — one per board, to tri-state the auxiliary receive path | 2 | $0.3096 | $0.62 |
| Single-gate inverters — one per board, for the strap complement | 2 | $0.0865 | $0.17 |
| Quad ESD array — board A goes 8→9, for the third socket's pins | 1 | $0.0874 | $0.09 |
| **Parts, per set** | | | **$7.83** |

Plus **one extra unique Extended part** — the inverter — at **$3.07, once per
order**.

| | |
|---|---|
| **Third cable, 2 sets** | **$18.74** |
| Third cable, 3 sets | $26.57 |
| Third cable, 5 sets | $42.24 |

**Extra board area: zero.** Board A is 48 x 66 mm and board B is 90 x 46 mm in
both revisions. The third socket and five extra chips fitted in the space rev
B already had.

**Extra joints: +134 surface-mount and −20 through-hole per set**, which is
+$0.43 and −$0.66 at two sets — a net *saving* of $0.23, because two
through-hole sockets left the fab's BOM at the same time.

### 3b. NOT attributable to the third cable

| Increase | Amount at 2 sets | What it really is |
|---|---|---|
| **Bare PCB** | **+$38.42** | Panelising, and a price bracket. Nothing to do with the third cable. |
| **Panel fee** | **+$8.21** | Panelising. |
| **Two sockets bought retail** | **+$5.44** | The part-number correction. rev B believed the vertical 2x3 socket and the long-tail 2x10 socket were buyable from LCSC. Neither is. They now cost $2.72 a set from Mouser and Phoenix Enterprises instead of $0.33 a set from the fab. |
| **Two extra Extended parts** | **+$6.14** | The part-number correction, *not* the strap. rev B listed the pin headers as one 1x40 strip (one Extended part). JLCPCB's BOM matcher will not accept a 40-pin part against a 3-pin footprint, so it became two discrete parts — 1x3 and 1x2 — and both are Extended. |
| **Reel minimums** | **+$0.67** | Two more minimum-order batches, for the 0805 zero-ohm link and the two header part numbers. |
| Joint and hand-solder fees | *see 1a* | Categories rev B never counted. |

**A fact worth stating, because it defuses the obvious complaint:** the number
of unique **Extended** parts on the panel is **12**, and rev B's two boards, if
they had been panelised, would also have been **12**. The strap inverter's
$3.07 was paid for exactly by two non-existent socket part numbers leaving the
fab's BOM. **The strap circuit is loading-fee neutral.**

---

## 4. What could be cut, ranked by what it saves

Figures at **two assembled sets**. Everything here is counted from the BOMs by
`tools/cost_model.py`, not estimated.

| # | Cut | Saves | What is lost |
|---|---|---|---|
| 1 | **Ship Global Standard Direct Line instead of DHL Express** | **$14.63** | 9–13 days instead of 2–4. No design change at all. |
| 2 | **Hand-fit the seven pin headers instead of having the fab place them** | **$8.04** | You solder 19 through-hole pins per set. Saves two Extended loading fees ($6.14), two reel minimums ($1.28) and 38 joints ($0.62). Buy a 1x40 strip for about $0.16 and snap it. This is the best value-per-effort cut on the list. |
| 3 | **Hand-fit the Tang dock's 2x20 socket too** | **$5.04** | You solder 40 more through-hole pins per set. Saves one Extended loading fee ($3.07), the part ($0.66) and 80 joints ($1.31). You are already told to solder the mating male header into the dock, so the skill is assumed. Note: the $3.58 hand-soldering base fee does **not** go away, because the six HDMI sockets are hybrid-mount and their four through-hole shell legs each still need soldering — 30 joints per set. Whether JLCPCB will solder those legs at all is **unverified**; if they will not, the base fee disappears too (a further $3.58) and you solder them, but the connectors then rely on their surface-mount contacts alone until you do. |
| 4 | **Replace the Extended single-gate inverter with a Basic-tier equivalent** | **$3.19** | Possibly nothing — see 4a. Saves one Extended loading fee ($3.07) plus the per-piece difference. |
| 5 | **Merge the 0805 zero-ohm links into 0402** | **$0.45** | One reel minimum. Basic loading is free, so that is all it saves — and it makes lifting a cable shield by hand harder. **Not worth it.** |
| 6 | **Drop the AC-coupling option footprints** | **~$0.30** | The only escape route if the link turns out to need AC coupling. The option's 32 parts per set use only two part numbers: 100 nF, which is already placed as decoupling, and 4k7, which is **never placed** and therefore carries no loading fee — only a reel minimum. **Do not cut this. It is almost free.** |
| 7 | **Drop all 82 test points per set** | **$0.00** | All bring-up visibility, for nothing. Test points have no part number, so no part cost, no loading fee and no joint fee. **This is a non-item.** |
| 8 | **Shrink or delete the fiducial coupon** | **$0.00** | Nothing is saved: board B rotated already sets the panel's 100 mm height (section 2a). **Non-item.** |
| 9 | **Consolidate resistor and capacitor values** | **$0.00** | Nothing is saved on Economic assembly. There are only **10 distinct placed passive part numbers** per set, **all of them Basic**, and **Basic loading is free**. The 0 Ω links alone account for 35 of the placed passives but they are one part number (two, counting the 0805 one). On **Standard** assembly, where every part costs $1.53, each value removed would save $1.53 — but Standard is the wrong service for this job anyway. **The suspicion that "34 and 50 resistors are probably many distinct values" is not borne out: they are seven values.** |
| 10 | **Abandon the panel for two separate orders** | **−$9.70** (costs more), **or +$11.85** if the two orders can be combined into one shipment | Nothing functional. See section 2. |

### 4a. Can the Extended inverter be avoided? Three routes, assessed

**Route 1 — build the inverter from a spare gate already on the board.**
**No.** Board A's second 4-bit translator has two unused channels, but they are
non-inverting buffers. The LVDS drivers do have complementary outputs, but they
are current-mode differential outputs with a 1.2 V common mode and a ±175 mV
swing into a 100 Ω load — they cannot drive a CMOS enable pin. The LVDS
receivers have no inverting output. There is nothing on either board that
inverts.

**Route 2 — a strap circuit that needs no complement at all.** **Half
possible, and the half that works is worth knowing.** The DS90LV047A driver has
**both** an active-high `EN` and an active-low `EN*`, so the two drivers could
be gated from a single strap net with no inverter: G1's `EN` on the strap and
G2's `EN*` on the same strap. But the host-facing buffer is an
SN74AVC4T245, which offers only an **active-low** `OE` per port, so one of its
two ports still needs the complement. A part offering both enable polarities,
or a pair such as the 74LVC125A (active-low) plus the 74LVC126A (active-high),
would remove the need — at the cost of two packages instead of one, which is
worse. **So the complement is genuinely required, but only by the buffers.**

**Route 3 — invert with a discrete transistor instead of a logic gate.**
**This is the real answer, if a Basic-tier device exists.** One N-channel
MOSFET — gate on the strap net, source to ground, drain on the complement,
using the **10 kΩ pull-up that is already fitted** as its load — inverts a DC
level perfectly well. Speed is irrelevant: this net changes only when a human
moves a jumper.

What a transistor does *not* give you, stated honestly: a logic gate
guarantees its output levels and its input threshold over temperature and
supply, and gives defined noise immunity. A MOSFET inverter gives an output
low of a few tens of millivolts (better than a gate) and an output high pulled
to exactly 3.3 V through 10 kΩ (also fine, since the loads are CMOS enable
pins drawing nanoamps), but its input threshold is a device parameter spread
over a range rather than a specified fraction of the supply. **For a jumper
level that is either 0 V or 3.3 V, none of that matters.** And the safe
failure direction is preserved exactly: device missing or dead, the pull-up
takes the complement high, which disables the host-facing port.

**PENDING: whether JLCPCB lists any Basic-tier single-gate logic IC, or a
Basic-tier logic-level N-MOSFET in SOT-23.** See section 6.

---

## 5. The cheapest credible configuration for two working sets

Starting from the design exactly as it stands, changing nothing electrical:

| | |
|---|---|
| rev C panel, Economic assembly, DHL Express | **$199.70** |
| − ship Global Standard Direct Line instead (9–13 days) | −$14.63 |
| − hand-fit the seven pin headers (19 pins per set) | −$8.04 |
| − hand-fit the Tang dock 2x20 socket (40 pins per set) | −$5.04 |
| **Cheapest without touching the schematic** | **$171.99** |
| − replace the Extended inverter with a Basic-tier part, **if one exists** | −$3.19 |
| **Cheapest with one part substitution** | **$168.80** |

**And the prize that dwarfs all of them:** if the bare panel can be bought at
anything like the $7.00-for-5 tier the two small boards were quoted at, that
one line falls by **$45.42**. On its own that takes two sets from $199.70 to
**$154.28**; combined with the three cuts above it gives **$126.57**. That
single question is worth more than every cut in section 4 put together, which
is why it is the first thing in section 6.

For comparison, **five sets** at the same settings is
$287.70 − $14.63 − $8.04 − $5.04 = **$259.99, or $52 each** against $86 each
for two. The fixed fees dominate at these quantities, so if more than two sets
will ever be wanted, five is much better value than three — and ordering
exactly three is the worst option of all, because JLCPCB's Economic service
only offers 2 or 5 assembled out of a 5-board run and asking for three forces
the dearer Standard tier.

---

## 6. What is not verified

| Item | Why it matters | Status |
|---|---|---|
| **The bare-PCB price brackets.** What 5 pieces of a 94 x 100 mm 4-layer board costs with 1 design declared versus 2; what the two small boards cost at list rather than promotional price; and at what size the cheap 4-layer tier stops applying. | **This is worth more than everything else on this page.** It is $38.42 of a $20.39 net increase. | **PENDING.** A live check was in progress when this was written. |
| **Whether a Basic-tier inverter or a Basic-tier logic-level N-MOSFET exists in JLCPCB's library.** | $3.19, and it removes the last Extended part that exists only for the strap. | **PENDING.** |
| **Whether two separate orders can be combined into one shipment.** | $21.55, and it flips the panel-versus-two-orders verdict. | **Unverified.** |
| **The per-joint fees.** JLCPCB publishes $0.0016 per surface-mount joint and $0.0164 per through-hole joint, but will not compute the total without a login and an uploaded placement file. The joint counts here — 789 surface-mount and 89 through-hole per panel — were counted from the board files. | About $5.44 of $199.70. Does not change any decision. | Rates published; total not quoted. |
| **Whether JLCPCB accepts a panel mixing V-scores with one mouse-bite separation.** Their Economic service states mouse-bite only; Standard allows either. | If refused, the fallback is two separate orders, which section 2 prices at $9.70 more. | **Unverified.** Ask before paying. |
| **Whether the rails can be dropped**, making the panel 94 x 90 mm. | 940 mm², and possibly a price bracket. | **Unverified.** Probably not available for an assembly job. |
| **Shipping from Mouser and from Phoenix Enterprises to Germany** for the two retail sockets. | Not in any total here. | **Unverified.** |
| **The reel-minimum figure for rev B** ($8.06) is estimated from its larger passive set; rev C's $8.73 is itemised from LCSC's own batch prices. | $0.67. Negligible. | Estimated for rev B only. |

---

## 7. Sources

| Figure | Source |
|---|---|
| Bare PCB prices, shipping options | JLCPCB instant quote form, German store, read 12 Sep 2026 |
| Assembly setup, stencil, panel fee, per-unique-part loading fees, per-joint rates, hand-soldering base fee | JLCPCB's published PCBA pricing page, read 12 Sep 2026 |
| Basic versus Extended classification, per part | JLCPCB's own parts library search, read 12 Sep 2026 |
| Unit prices, stock, minimum order quantities | LCSC product pages, read 12 Sep 2026 |
| Retail socket prices | Mouser (Samtec SSQ-103-02-S-D) and Phoenix Enterprises (HWS16492), read 12 Sep 2026 |
| Part counts, joint counts, unique-part counts, board areas | Counted from the generated BOMs and PCBs by `tools/cost_model.py` |
| rev B's figures | `STATUS.md` at git commit `5c62b90`; rev B's BOMs and PCBs at git commit `a15d05a` |
