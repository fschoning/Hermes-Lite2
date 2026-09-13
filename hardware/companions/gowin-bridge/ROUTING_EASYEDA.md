# gowin-bridge rev D — routing in EasyEDA Pro and ordering from JLCPCB

> **13 Sep 2026: the board is no longer placed.** It is prepared for Quilter
> instead: only the connectors, the sockets, the fiducials and the holes
> have a position, and every other part waits off the board. Follow
> `QUILTER.md`. Use this guide only on a board that has already been
> placed — for example one Quilter sent back — for the routing rules, the
> stack, the pair list and the JLCPCB order. Board facts below are
> updated: **64.50 × 92.00 mm, no rails, the two ends joined by three mouse-bite tabs across a 2 mm slot, holes over the radio's FPGA, AD9866 and T2** (`DESIGN_NOTES.md` §13),
> the pair net class is now called `differentialpair`, and every
> clearance in the file is already 0.15 mm.

For the owner, routing this board by hand. Strictly procedural: one action per
step. Do not change the schematic, the placement or the board outline —
`bridge/bridge.kicad_pcb` and `bridge/bridge.kicad_sch` are generated and
validated; only the copper is yours to draw.

Source files read: `ROUTING.md`, `PINMAP.md`, `DESIGN_NOTES.md`, `STATUS.md`,
`COST.md`, `bridge/bridge.kicad_pcb`, `bridge/bridge.kicad_pro`,
`bridge/bridge.kicad_sch`, `panel-endcap/panel-endcap.kicad_pcb`. Worktree
`G:\proj\worktrees\Hermes-Lite2-gowin-bridge-pcb`, branch `gowin-bridge-pcb`,
commit `d390bca` (plus `c72c498` for the panel).

---

## 0. Quick reference — keep this on screen while routing

| | |
|---|---|
| **Layer stack** | 4 layer, 1.6 mm. Top (L1) signal / In1 (L2) **solid GND** / In2 (L3) power / Bottom (L4) signal. JLCPCB stackup name: **JLC04161H-7628 ("Standard")** |
| **Stack dielectrics** | L1 Cu 0.035 mm — prepreg 7628 **0.2104 mm** (εr 4.4) — L2 Cu 0.0152 mm — core **1.065 mm** (εr 4.6) — L3 Cu 0.0152 mm — prepreg 7628 **0.2104 mm** (εr 4.4) — L4 Cu 0.035 mm. Finished ≈1.59 mm ±10% |
| **100 Ω differential pair** | **Width 0.25 mm (9.8 mil), gap 0.20 mm (8 mil), TOP LAYER ONLY, referenced to L2 (GND).** Target only — impedance is not guaranteed on this order |
| **Bottom-layer differential pairs** | **NOT ALLOWED.** L4's only adjacent plane is L3, the power layer, which is split. See §3 |
| **Default single-ended track** | 0.25 mm (9.8 mil), clearance 0.15 mm (5.9 mil) |
| **Power track (+3V3, +2V5, DB1_3V3, VLVDS, VLVDS_F)** | 0.6 mm (23.6 mil), clearance 0.2 mm (7.9 mil) |
| **Default via** | 0.3 mm drill / 0.6 mm pad |
| **Differential-pair via** | 0.25 mm drill / **0.45 mm pad minimum** (below 0.45 mm JLCPCB's cheap tier ends) |
| **General clearance** | **0.15 mm everywhere**, JLCPCB's manufacturing floor. The KiCad file now says 0.15 mm on every class and board-wide (it said 0.13 mm before 13 Sep 2026). Set EasyEDA's rules to the same |
| **Length-match groups** | Forward group, reverse group: **±2.5 mm**, each group of 4 pairs matched to itself. Aux clock/data: **±2.5 mm** (derived, same lane rate). Duplicate clock, spare: no requirement. Full table in §4 |
| **Tab and cut-out copper setback** | **1.0 mm** from every tab and every cut-out edge; pair tracks **2.0 mm** from a cut-out |
| **M3 U-notch keepout** | 0.3 mm copper clearance |
| **Board** | 64.50 × 92.00 mm, one continuous outline: radio end above, Gowin end below, joined by three 5 mm mouse-bite tabs across a 2 mm slot; no V-score, no rails |
| **Order** | 4 layer, 1.6 mm, lead-free HASL, 1 oz outer / 0.5 oz inner, no impedance control, 5 pcs, **one design**, Single PCB |

---

## 1. Getting the design into EasyEDA Pro

Steps below follow EasyEDA Pro's own current published guide, "Import KiCad"
(prodocs.easyeda.com/en/import-export/import-kicad/, read 13 Sep 2026). That
page states EasyEDA Pro imports KiCad projects packaged as a zip using
KiCad's own archive function, and that after import "it will automatically
rebuild and copper area. The result of copper area will be different, please
check carefully" — their words, not a guess.

1. On the machine with KiCad, open `bridge/bridge.kicad_pro` in KiCad 10.
2. In KiCad, use KiCad's own project-archive/packaging function (do **not**
   zip the folder yourself in File Explorer — EasyEDA's doc is explicit that
   this must be KiCad's built-in packaging, because it also pulls in the
   footprint and symbol libraries the schematic uses).
3. This produces a `.zip` of the project.
4. Open `https://pro.easyeda.com/editor` (no login needed to reach the start
   page; you will need an account to save).
5. On the EasyEDA Pro start page, click **Import KiCad**.
6. Select the `.zip` file from step 3.
7. Wait for the import to finish. EasyEDA Pro rebuilds copper pours on
   import — the next three steps check that it rebuilt them correctly.

### 1.1 What to check immediately after import

8. Open the imported PCB. Zoom to fit (View menu or scroll-wheel).
9. **Board outline.** Confirm you see **one continuous outline**, 64.50 mm
   wide × 92.00 mm tall, with no gaps or duplicate edges. `STATUS.md` and
   `DESIGN_NOTES.md` §11.6 both state this is one design with one outline —
   if the import shows two separate boards or a broken loop, the import did
   not preserve the outline and must be redone from a fresh archive.
10. **The tabs.** Confirm a 2 mm slot across the board between the radio end
    (above) and the Gowin end (below), crossed by three 5 mm tabs, each with a
    row of eight 0.5 mm unplated holes along both ends' edges. There is no
    V-score and there are no rails. If the holes came through as plated, or
    vanished, redo the import.
11. **The two internal holes.** Confirm the 1.1 mm unplated locating-peg hole
    (radio end) and the M3 spacer hole under the Gowin-end connector housing
    (`DESIGN_NOTES.md` §11.3, ~3.2 mm minimum) both came through as
    non-plated holes, not vanished or turned into plated vias.
12. **The M3 U-notch** (radio end), **the notch over the radio's FPGA** (local
    x 24.00–50.20 from the top edge to y 25.10) and **the cut-out over the
    AD9866, T2 and the jumper window** (local x 34.09–57.00, y 30.00–56.25) —
    confirm all are still open (not filled with copper or silkscreen).
13. **Footprints.** Right-click a handful of parts you know are unusual —
    the SlimSAS connector (J1 or J101), the 2×18 header footprint, the U-notch
    mounting area — and confirm the pads look correct against the KiCad 1:1
    PDF (`templates/bridge-1to1-TOP-fit-check.pdf`). KiCad-to-EasyEDA
    footprint import is the single most common source of silent breakage:
    custom pad shapes, slotted holes and courtyard-only graphics sometimes
    drop or simplify.
14. **Nets.** Open the left panel's Nets list. Confirm the net count is in
    the right range — `STATUS.md` states 173 nets in the generated design. A
    materially different count means nets merged or split on import (most
    often two same-named nets on different sheets merging, or a net losing
    its name and becoming `Net-(...)`).
15. **Compare the netlist against the schematic**, not just against KiCad.
    Top Menu → Design → **Import Changes from PCB** is EasyEDA Pro's
    parity check — it flags anything the PCB has that the schematic does
    not, and vice versa. Run it now, before routing, as well as again in
    §8. See §8 for what a clean result looks like.

### 1.2 Things that typically break in a KiCad→EasyEDA import, and the fix

16. **Internal (negative) plane layers.** EasyEDA Pro's inner layers are
    drawn negative-film in the editor (copper is removed where lines are
    drawn) even though KiCad's In1/In2 are positive zones. The import
    translates this, but always **manually rebuild** the plane layers after
    import (right-click the copper on In1 and In2, "Rebuild Plane Zone" — see
    §6) rather than trusting the auto-converted fill.
17. **Split planes.** KiCad's zone-with-keepout technique for splitting In2
    into `+3V3` and `+2V5` regions does not have a 1:1 EasyEDA equivalent.
    After import, re-draw the split using EasyEDA's own "divide the inner
    plane layer with a broken line, then rebuild" method (§6.3) rather than
    assuming the imported shapes are correct. There is no pre-drawn +2V5
    island any more: it assumed the old placement. Draw the +2V5 area on
    In2 round wherever U1, U2, U3 and U12 ended up.
18. **Net classes / design rules.** KiCad's three net classes (`Default`,
    `differentialpair`, `Power`, defined in `bridge/bridge.kicad_pro`) may or may not
    survive import as EasyEDA Design Rules. Do not assume they did — set them
    by hand per §3 regardless.
19. **Differential pairs.** The 32 pair legs (16 pairs × 2 ends, all on net
    class `differentialpair`) may not come through as EasyEDA "differential pair"
    objects even if the individual nets import correctly. Create them by
    hand per §4.2 — do not rely on auto-detection alone; verify every pair
    exists in the Differential Pair Manager before routing.
20. **Courtyard / assembly-layer graphics and 3D bodies** on the SlimSAS
    connector and headers commonly drop silently. Not electrically important,
    but check the top/bottom assembly layers still show outlines for J1,
    J101 and the SlimSAS keep-out zones you'll want visible while routing.

---

## 2. Layer stack

The stack ROUTING.md specifies — 4 layer, 1.6 mm, top signal / inner-1 solid
ground / inner-2 power / bottom signal — is JLCPCB's own standard 4-layer
1.6 mm construction, catalogued on their impedance/stackup page
(jlcpcb.com/impedance, read 13 Sep 2026) as **JLC04161H-7628**, the entry
marked **"Standard"** (their word) with finished thickness 1.59 mm ±10%. It
is also the stackup JLCPCB uses whether or not you pay for impedance control
— paying only tightens the tolerance and adds a mandatory pre-production
check, it does not change which physical stackup you get by default.

| Layer | Material | Thickness |
|---|---|---|
| L1 — Top (F.Cu) | Copper, 1 oz | 0.035 mm |
| — | Prepreg, 7628, εr 4.4 | 0.2104 mm |
| L2 — In1 (GND) | Copper, 0.5 oz | 0.0152 mm |
| — | Core, εr 4.6 | 1.065 mm |
| L3 — In2 (power) | Copper, 0.5 oz | 0.0152 mm |
| — | Prepreg, 7628, εr 4.4 | 0.2104 mm |
| L4 — Bottom (B.Cu) | Copper, 1 oz | 0.035 mm |

Source: jlcpcb.com/impedance, "4-Layer Impedance Control Stackup" table,
entry **"JLC04161H-7628 (Standard/Finished thickness 1.59mm±10%)"**, read
13 Sep 2026.

**Steps to set it in EasyEDA Pro:**

1. Top Menu → **Tools → Layer Manager**.
2. Confirm 4 copper layers exist: L1 (Top), L2, L3, L4 (Bottom). If not,
   use the "add layer" function inside Layer Manager to reach 4.
3. Set L2's layer type to **Internal Plane Layer** (this is the solid
   ground — do this so it behaves as a negative-film plane, not a routed
   signal layer).
4. Set L3's layer type to **Internal Plane Layer** as well (the power
   layer — see §6 for how it gets split into +3V3 and +2V5).
5. In the same Layer Manager window, open **Physical Stacking**.
6. Set overall board thickness to **1.6 mm**.
7. Enter the seven layer thicknesses from the table above (copper and
   dielectric) so the physical stack matches JLC04161H-7628. Note EasyEDA
   Pro's own documentation states this physical-stacking setting is
   currently for record only and does not drive Gerber export — you still
   select the stackup again by name at order time (§9) — but it does drive
   the 3D preview and any impedance-aware routing the tool offers, so set it
   correctly anyway.
8. Do not enable "Impedance Control" purchasing at order time (§9) — this
   stackup and these target widths are what you get by default.

---

## 3. Design rules — exact numbers to type in

### 3.1 The 100 Ω differential pair target

Computed live on JLCPCB's own Impedance Calculator
(jlcpcb.com/pcb-impedance-calculator, read 13 Sep 2026) against the
JLC04161H-7628 stackup above, 1 oz outer / 0.5 oz inner copper, differential
pair (non-coplanar) microstrip, top layer (L1) referenced to L2 (GND), gap
fixed at 8 mil:

| | |
|---|---|
| Target differential impedance | 100 Ω |
| **Trace width (solved)** | **8.89 mil = 0.226 mm** |
| **Gap (held)** | **8.00 mil = 0.203 mm** |
| Calculator's result | 100.06 Ω differential, εr(eff) 2.927 |

The project's own KiCad net class `differentialpair` (called `LVDS100` before 13 Sep 2026; in `bridge/bridge.kicad_pro`,
already used to reach 0 DRC violations pre-routing) specifies **width
0.25 mm / gap 0.20 mm** — within a few percent of the calculator's ideal.
**Use 0.25 mm width / 0.20 mm gap** — round numbers, already proven, close
enough given impedance is not guaranteed on this order anyway (below).

**Bottom layer (L4): not usable for these pairs, stated plainly.** L4's only
adjacent copper is L3, the power plane — and L3 is split into a `+3V3` pour
and a `+2V5` island (local x 8–33, y 1–12 at the radio end, `DESIGN_NOTES.md`
§4). ROUTING.md's rule 1 requires "every differential pair references
[the solid ground]" and rule 3 requires routing "over In1.Cu" — a pair on L4
cannot satisfy either, because its physical reference is L3, not L2, and L3
is not solid. **Route all 32 differential pair legs, both ends, on L1 (top)
only.** Reserve L4 for single-ended nets (JTAG, sidebands, the short
HL2-local runs) and for ground/power stitching vias down to L2/L3.

**Impedance is a target, not a promise.** JLCPCB's Economic tier as ordered
(§9) includes no impedance control and no pre-production impedance
verification — `COST.md` §5.1 explains that paying for it ($33.88 including
the mandatory file check) is not worth it for a 307.2 Mbit/s link whose own
connector is already specified 85 Ω ±10%. Hit the 0.25 mm / 0.20 mm numbers
as your target; do not expect a guarantee.

### 3.2 Other track widths, via sizes and clearance

Sourced from `bridge/bridge.kicad_pro`'s net classes (`Default`, `differentialpair`,
`Power`) — the values already used to reach 0 DRC violations in KiCad —
cross-checked against JLCPCB's published capability minimums
(jlcpcb.com/capabilities/pcb-capabilities, read 13 Sep 2026).

| | Value | Source / note |
|---|---|---|
| Default signal track width | **0.25 mm (9.8 mil)** | `Default` net class |
| Default clearance | **0.15 mm (5.9 mil)** | `Default` net class. Matches JLCPCB's stated minimum trace/clearance (0.15/0.15 mm, 1 oz, under solder mask) exactly — do not go narrower |
| **differentialpair clearance** | **0.15 mm** | Raised in the KiCad file on 13 Sep 2026 from 0.13 mm, which was below JLCPCB's published floor of 0.15 mm. Board-wide `min_clearance` is 0.15 mm too |
| Default via | **0.3 mm drill / 0.6 mm pad** | `Default` net class. JLCPCB's cheapest via tier is 0.3 mm drill (no upcharge); 0.6 mm pad is larger than their paired 0.4–0.45 mm suggestion, which only adds annular-ring margin, not cost |
| **Differential-pair via** | **0.25 mm drill / 0.45 mm pad minimum** | `differentialpair` net class. JLCPCB's own capability note: "0.2 mm or 0.25 mm hole size with via diameter less than 0.45 mm will cost more" — keep the pad at 0.45 mm or larger to stay in the no-upcharge band |
| **+3V3 / DB1_3V3 / VLVDS / VLVDS_F power track** | **0.6 mm (23.6 mil)** | `Power` net class. Carries the board's 350 mA design figure (`DESIGN_NOTES.md` §4.1). By IPC-2221 (1 oz external, 10 °C rise — the same convention `DESIGN_NOTES.md` §6.2 uses), 350 mA only needs ≈0.07 mm to stay under a 10 °C rise, so 0.6 mm is headroom against IR drop, not a heating minimum |
| **+2V5 power track** | **0.6 mm (23.6 mil)**, same `Power` class | Carries the 50 mA design figure. By the same IPC-2221 method this needs a negligible fraction of a mil for heating — 0.6 mm is far more than required; keep it for consistency and to stay clear of the 0.15 mm manufacturing floor with margin |

**Steps to set these in EasyEDA Pro:**

1. Top Menu → **Design → Design Rules**.
2. Under **Track Rules**, set the default track width to **0.25 mm** (min/max
   as you see fit, e.g. min 0.15 mm, max 0.6 mm).
3. Under **Via Size Rules**, set the default via to **0.3 mm drill / 0.6 mm
   pad**.
4. Under **Safe Spacing Rules**, set the board-wide default clearance to
   **0.15 mm** (not 0.13 mm).
5. Under **Network Rules**, create a net class (right-click in the network
   list → create new network class) named `differentialpair`. Assign it: track width
   0.25 mm, clearance **0.15 mm**,
   via 0.25 mm drill / 0.45 mm pad. Assign every one of the 32 differential
   pair legs (both ends — see the net list in §4.1) to this class.
6. Create a second net class `Power`, track width 0.6 mm, clearance 0.2 mm.
   Assign `+3V3`, `+2V5`, `DB1_3V3`, `VLVDS`, `VLVDS_F` to it.
7. Leave every other net on the default rule.

---

## 4. Net classes and differential pairs

### 4.1 Every differential pair, both ends, with connector positions

Net names below are taken directly from `bridge/bridge.kicad_pcb` and cross-
checked against `bridge/bridge.kicad_sch` — every name exists in the
schematic. "Pos" is the shared SFF-8654 connector position number — the
radio-end connector (J1) and the Gowin-end connector (J101) are the same
part in the same footprint, so position numbers line up directly between the
two tables.

**Radio end (J1). Row A = this board drives. Row B = this board receives.**

| Pos | P net | N net | What |
|---|---|---|---|
| 2/3 | A_AUXCLK_P | A_AUXCLK_N | aux clock, driven |
| 5/6 | A_AUXDAT_P | A_AUXDAT_N | aux data, driven |
| 14/15 | A_FWDCLK_P | A_FWDCLK_N | **forward clock**, driven |
| 17/18 | A_ADCD0_P | A_ADCD0_N | ADC data 0, driven |
| 20/21 | A_ADCD1_P | A_ADCD1_N | ADC data 1, driven |
| 23/24 | A_ADCD2_P | A_ADCD2_N | ADC data 2, driven |
| 32/33 | A_DUPCLK_P | A_DUPCLK_N | duplicate forward clock, driven |
| 35/36 | A_SPARE_P | A_SPARE_N | spare, driven; nothing at the far Gowin end |
| 2/3 | B_AUXCLK_P | B_AUXCLK_N | aux clock, received |
| 5/6 | B_AUXDAT_P | B_AUXDAT_N | aux data, received |
| 14/15 | B_REVCLK_P | B_REVCLK_N | **reverse clock**, received |
| 17/18 | B_TXD0_P | B_TXD0_N | transmit data 0, received |
| 20/21 | B_TXD1_P | B_TXD1_N | transmit data 1, received |
| 23/24 | B_TXD2_P | B_TXD2_N | transmit data 2, received |
| 32/33 | B_DUPCLK_P | B_DUPCLK_N | duplicate reverse clock, received |
| 35/36 | B_SPARE_P | B_SPARE_N | spare, received; receiver output unconnected |

**Gowin end (J101), from `PINMAP.md` §11.3. Same Pos numbers, mapped to J14
pin numbers on the dock side for reference.**

| Pos | J14 | P net | N net | What |
|---|---|---|---|---|
| 2/3 | 27/28 | G_A_AUXCLK_P | G_A_AUXCLK_N | aux clock, driven |
| 5/6 | 21/22 | G_A_AUXDAT_P | G_A_AUXDAT_N | aux data, driven |
| 9/10 | — | G_A_REVCLK_P | G_A_REVCLK_N | **reverse clock, driven** — Pos 9/10 is a dedicated pair position at this end, not 14/15 |
| 14/15 | 19/20 | G_B_FWDCLK_P | G_B_FWDCLK_N | **forward clock, received** |
| 17/18 | 17/18 | G_B_ADCD0_P | G_B_ADCD0_N | ADC data 0, received |
| 20/21 | 15/16 | G_B_ADCD1_P | G_B_ADCD1_N | ADC data 1, received |
| 23/24 | 13/14 | G_B_ADCD2_P | G_B_ADCD2_N | ADC data 2, received |
| 32/33 | 31/32 | G_B_DUPCLK_P | G_B_DUPCLK_N | duplicate forward clock, received |
| 35/36 | 39/40, 37/38, 35/36 | G_A_TXD0/1/2 | — | transmit data 0–2, driven — see note below |
| 35/36 | — | G_A_SPARE_P | G_A_SPARE_N | spare, not wired at this end |

**Read this table carefully — the Gowin end is not a simple mirror by
position number.** Unlike the radio end (where position 14/15 alone carries
both the driven and received member of a functional pair), the Gowin end's
forward clock and reverse clock live on *different* position pairs (14/15
received vs 9/10 driven), because J14 only offers two true clock-capable
pairs (§11.3 of `PINMAP.md`) and the tool assigns them by clock function, not
by SFF-8654 position symmetry. Route from the net names, not from position
number alone, for the Gowin end.

### 4.2 Length-matched groups and tolerance

`ROUTING.md` states the forward group's tolerance directly: **≈2.5 mm**
(≈15 ps, under 0.5% of the 3.2552 ns unit interval at 153.6 MHz DDR). The
reverse group gets "the same rule, same tolerance" — ROUTING.md's own words.
The other groups' tolerances are **derived** here, not assumed, because
ROUTING.md does not state them directly:

- **Auxiliary group (clock + data):** `PINMAP.md` §0 and `DESIGN_NOTES.md`
  §1 both state the auxiliary channel runs at the same 307.2 Mbit/s per lane,
  153.6 MHz DDR, 3.2552 ns unit interval as the forward/reverse groups —
  there is nothing electrically different about it. Applying ROUTING.md's
  own stated budget (2.5 mm ≈ 0.5% of the unit interval) to the same unit
  interval gives the same **±2.5 mm** target for AUXCLK-to-AUXDAT matching.
- **Duplicate clock and spare:** ROUTING.md states no matching requirement
  for these directly ("no matching requirement at all").

| Group | Members | Radio end Pos | Gowin end Pos | Tolerance |
|---|---|---|---|---|
| Forward (radio drives / Gowin receives) | FWDCLK, ADCD0, ADCD1, ADCD2 | 14/15, 17/18, 20/21, 23/24 (driven, radio) | 14/15, 17/18, 20/21, 23/24 (received, Gowin) | **±2.5 mm**, matched within each end's group of 4 |
| Reverse (Gowin drives / radio receives) | REVCLK, TXD0, TXD1, TXD2 | 14/15, 17/18, 20/21, 23/24 (received, radio) | 9/10 + 35/36,37/38,39/40 (driven, Gowin) | **±2.5 mm**, matched within each end's group of 4 |
| Auxiliary (clock + data, each end) | AUXCLK, AUXDAT | 2/3, 5/6 | 2/3, 5/6 | **±2.5 mm** (derived above) |
| Duplicate clock | DUPCLK | 32/33 | 32/33 | none |
| Spare | SPARE | 35/36 | 35/36 (radio only — not wired at Gowin end) | none |

Note the forward and reverse groups are matched **within themselves**, not
against each other — ROUTING.md is explicit that the forward group's skew
only has to match the other three forward-group pairs, and likewise for
reverse. Do not spend effort matching forward-group length against
reverse-group length.

### 4.3 Steps to define pairs and matching in EasyEDA Pro

1. Top Menu → **Design → Differential Pair Manager**.
2. Use **automatically generate differential pairs** — EasyEDA Pro matches
   by common net-name prefix with differing `_P`/`_N` suffix, which is
   exactly this project's naming convention. It should find all 32 pairs
   (16 radio-end + 16 Gowin-end, spares included).
3. Manually verify the count: 16 pairs at the radio end (§4.1's first table)
   and 16 at the Gowin end (§4.1's second table, including the not-wired
   `G_A_SPARE` pair which still needs ESD/test-pad copper even though it
   carries no signal).
4. For every pair, confirm **P is on the lower-numbered contact** in both
   rows — this project's own `tools/check_netlist.py` asserts this in KiCad;
   EasyEDA gives you no equivalent automatic check, so verify by eye against
   §4.1's tables as you place each pair's route.
5. Top Menu → **Design → Design Rules → Network Rules → DifferentialPair**
   (right-click to create, per EasyEDA's own doc). Create one rule named
   `FWD_REV_GROUP` with target gap 0.20 mm, width 0.25 mm (§3.1).
6. Create a **Network Length** rule (same Design Rules dialog, under Track
   Rules / Network Length) for the forward group's four P-legs (or N-legs —
   pick one leg per pair consistently), setting a common target length with
   tolerance **±2.5 mm**. EasyEDA's net-length rule shows green when a
   routed net is inside the rule and red outside it — use this as your
   real-time matching indicator while routing.
7. Repeat step 6 for the reverse group (own target length, ±2.5 mm) and for
   the auxiliary group at each end (own target length, ±2.5 mm, derived
   above).
8. Optionally use **Design → Pad Pair Group Manager** to also see live
   pad-to-pad length for each pair in the net tree while you route — this is
   a convenience on top of the Network Length rule, not a replacement.
9. When routing each pair, use **Top Menu → Route → Differential Pair
   Routing**. Watch the upper-right cursor indicator (enable it at Settings →
   PCB Settings → General if it is not already on) for real-time rule
   compliance.
10. After routing a matched group, use **Top Menu → Route → Differential
    Pair Equal Length Tuning** on whichever pair(s) are short, with **Arc 90
    degrees** corners (the most common choice, i.e. serpentine/trombone) to
    bring each pair to the group's common target length within ±2.5 mm.

---

## 5. Routing order

Follow `ROUTING.md` §1's four non-negotiable rules and §2's order, expanded
into concrete EasyEDA Pro steps.

### 5.1 The four rules, unchanged

1. **In1 (L2) is solid ground. Nothing crosses it.** Do not route on L2, do
   not use it as a routed signal layer, do not let a via field starve it
   under the connector footprint.
2. **Every single-ended net touching an HL2 header pin stays under 25 mm.**
   The translators and LVDS silicon sit in local x 9–53, y 12–34, next to
   DB1 and DB12, specifically so this is achievable.
3. **Each received pair's 100 Ω termination goes within 5 mm of the
   receiver pins** — eight terminations, at U6/U7 (DS90LV048A receivers).
4. **Each ESD array goes within 5 mm of the SlimSAS contacts**, on the
   connector side of terminations/series resistors/buffers, shortest
   possible ground return — twelve arrays total (both ends).

### 5.2 Route order — radio end

1. **The four forward-group pairs**: A_FWDCLK, A_ADCD0, A_ADCD1, A_ADCD2,
   Pos 14/15, 17/18, 20/21, 23/24. Route on **L1 only**. Start at U1/U4's
   output pins (the driver side), end at the SlimSAS J1 pads. Length-match
   within the group to ±2.5 mm (§4.2/§4.3). Vias: none if you can avoid
   them — ROUTING.md wants the forward group to "ideally never change
   layer." If a via is unavoidable, use the §3.2 diff-pair via spec and
   place a ground stitching via (to L2) immediately beside it.
2. **The four reverse-group pairs**: B_REVCLK, B_TXD0, B_TXD1, B_TXD2, same
   position numbers, row B. Same layer, same via rule, same ±2.5 mm
   target. These run from the SlimSAS J1 pads to U3/receiver inputs.
3. **The auxiliary pairs**: A_AUXCLK/A_AUXDAT (Pos 2/3, 5/6) and
   B_AUXCLK/B_AUXDAT, same positions. Match clock to data within each
   direction, ±2.5 mm (§4.2). Not matched against the forward/reverse
   groups.
4. **The duplicate clock pair** (Pos 32/33) and **the spare pair** (Pos
   35/36). No length-matching rule. Duplicate clock goes to U5 channel 1;
   spare goes to U5 channel 4 out and U7 channel 4 in, and no further.
5. **The 12 ESD arrays, then the 8 terminations.** Do this now, before
   single-ended routing claims the space near the connector. Each ESD
   array: within 5 mm of its SlimSAS contact, on the connector side of
   everything else on that net. Each termination (100 Ω differential
   resistor, one per received pair — 8 total): within 5 mm of the
   receiver pins on U6/U7, never at a driver output.
6. **The single-ended HL2 nets**, under 25 mm each (rule 2). Route these on
   whichever layer is convenient (L1 or L4) — this is where L4 earns its
   keep, since it is not usable for differential pairs. Start with
   `HL2_FWD_CLK_RAW` → R1/R2 (the 100 Ω/470 Ω divider) → `HL2_FWD_CLK` → U1:
   this is the tightest single-ended path on the board (0.53 ns edge into
   the translator), so route it first and shortest, avoid vias on it if you
   can.
7. **The 16 sideband conductors**: `SB_PRSNT_IN/OUT`, `SB_TCK_IN`,
   `SB_TMS_IN`, `SB_TDI_IN`, `SB_TDO_OUT`, `SB_AUXIO0..3_IN/OUT`, plus the
   two undriven-on-purpose contacts (`SB_NC9`, `SB_NC29` in the board
   file — these still get ESD clamps, no further routing).
   All slow (DC to 24 MHz). Default single-ended track width (§3.2).
8. **The JTAG run from CN1 (J4) to the connector** — `J_TCK`, `J_TMS`,
   `J_TDI`, `J_TDO` to/from the gated buffer, then `SB_TCK_IN`/`SB_TMS_IN`/
   `SB_TDI_IN`/`SB_TDO_OUT` onward — about 59 mm, deliberately allowed to be
   long (0.085 ns added electrical length against a 41.7 ns TCK period at
   24 MHz). Route this last among the signal nets; it is the least
   time-critical run on the board.
9. **Power** — see §6.

### 5.3 Route order — Gowin end (no active silicon, route this as fully as the radio end)

The Gowin end is passive: the SlimSAS connector, 12 ESD arrays, 9 resistors,
and a hand-soldered 2×18 straight to J14 positions 5–40. There is no
translator, driver or receiver chip to route around, so the routing is
mechanically simpler but must not be treated as an afterthought — every
pair still needs its ESD array and its length match.

1. **The forward-received group**: G_B_FWDCLK, G_B_ADCD0, G_B_ADCD1,
   G_B_ADCD2 (Pos 14/15, 17/18, 20/21, 23/24, J14 pins 19/20, 17/18, 15/16,
   13/14). Route **L1 only**, straight from the SlimSAS J101 pads to the
   2×18 header pads. Match within the group, ±2.5 mm.
2. **The reverse-driven group**: G_A_REVCLK (Pos 9/10, J14 9/10),
   G_A_TXD0/1/2 (Pos 35/36 physically, J14 39/40, 37/38, 35/36 — see the
   note in §4.1, these are *not* all on the same SFF-8654 position as each
   other). Route L1, match within the group, ±2.5 mm.
3. **The auxiliary pairs**: G_A_AUXCLK/G_A_AUXDAT (J14 27/28, 21/22),
   G_B_AUXCLK/G_B_AUXDAT (J14 23/24, 25/26). Match clock to data, ±2.5 mm.
4. **The duplicate pair** G_B_DUPCLK (Pos 32/33, J14 31/32) and the
   **not-wired spare** G_A_SPARE (Pos 35/36) — no matching requirement.
   The spare pair still needs its ESD array; leave the J14 end on a test
   pad, unconnected to the header, per `PINMAP.md` §11.4.
5. **The 12 ESD arrays** at this end (shared part number with the radio
   end, already on the BOM at no extra Extended-part fee — `COST.md` §2).
   Same 5 mm-of-the-connector-contact rule as §5.1 rule 4.
6. **The receiver termination footprints** — `DESIGN_NOTES.md` §11.1
   states Gowin's on-die 100 Ω input termination is the primary plan, with
   seven **not-fitted** external 100 Ω footprints (C25076, on the BOM as
   DNP) as the fallback per received pair. Place these footprints within
   5 mm of the J14 pads even though they are not populated — so the option
   exists without a respin.
7. **The 6 sideband/JTAG single-ended nets**: `G_SB_PRSNT_IN/OUT`,
   `G_TCK_DRV`/`G_SB_TCK_OUT`, `G_TMS_DRV`/`G_SB_TMS_OUT`,
   `G_TDI_DRV`/`G_SB_TDI_OUT`, `G_TDO_RD`/`G_SB_TDO_IN`. Route directly
   from SlimSAS pads through their series resistors (R101/103/104/106/107/108,
   330 Ω or 1 kΩ per `PINMAP.md` §11.3) to the J14 header pads. No length
   requirement (JTAG here runs no faster than 24 MHz).
8. **Ground** — `G_GND`, the single ground contact this end has (J14 pin
   12) plus the SlimSAS shell-ground net. See §6.2.

---

## 6. Power and ground

### 6.1 Ground (L2, In1)

1. Confirm L2 is set to **Internal Plane Layer** (§2).
2. Assign net `GND` to the whole L2 copper at the **radio end**.
3. Assign net `G_GND` to the whole L2 copper at the **Gowin end** — these
   are two electrically separate pours, joined only through the single
   `G_GND` conductor on J14 pin 12 and the cable, not through the PCB
   copper (`DESIGN_NOTES.md` §11.6: "ground pours are per end"). Draw a
   dividing broken line across L2 along the slot between the two ends (see
   §6.3 for the technique) so the plane rebuild keeps them separate.
4. **Stitch the connector's ground contacts.** Both SlimSAS connectors give
   you a ground pin between every differential pair — positions 1, 4, 7, 13,
   16, 19, 22, 25, 31, 34, 37 in both rows (26 contacts total). Place a
   stitching via from each of these pads down to L2 (use Layer Manager's
   Place Suture Vias function on the plane zone, or place vias by hand).
5. **Stitch the board edges.** Place ground stitching vias around the board
   perimeter at roughly 5–10 mm spacing, keeping the §7 mechanical keepouts
   clear.
6. Rebuild the plane: click the L2 copper, then use the Rebuild Plane Zone
   function (§1.1, step 16).

### 6.2 Power (L3, In2) — radio end only; the Gowin end carries no power net

1. Confirm L3 is set to **Internal Plane Layer**.
2. The Gowin end's L3 copper is unused for power (J14 supplies no 3.3 V or
   2.5 V — `PINMAP.md` §11.1, "J14 has no 3.3 V pin, only 5 V and ground").
   Either leave the Gowin-end L3 area as an extension of the ground pour
   (tie it to `G_GND`) or leave it unfilled — do not assign it `+3V3`.
3. At the radio end, split L3 into two regions using a **broken line** (not
   a wire — EasyEDA Pro's Layer Manager doc is explicit that internal-plane
   splits must use the broken-line primitive):
   a. Draw a closed broken-line boundary around local x 8–33, y 1–12 (the
      `+2V5` island — it must reach U1's and U2's VCCA, U3's VCCB, U12's
      output and the `SL_VLVDS` link, per `ROUTING.md` §4).
   b. Assign net `+2V5` to the copper inside that boundary.
   c. Assign net `+3V3` to the remaining L3 copper at the radio end.
4. Rebuild the plane (right-click the copper → rebuild, or Shift+B to
   rebuild all copper).
5. Route the `DB1_3V3` → FB1 → `P3V3_FB` → L1 → `+3V3` trunk as an explicit
   0.6 mm track (§3.2) from the DB1 header pads through FB1 and the 4.7 µH
   inductor L1 to the point where it lands on the L3 `+3V3` pour, with the
   100 µF tantalum C29 at L1's `+3V3` end (§7.1) — this short run is the one
   place power needs an explicit trace rather than riding the plane.
6. Place the two 10 µF bulk capacitors: one on the DB1 side of FB1, one on
   the `+3V3` (pour) side, per `ROUTING.md` §4.

### 6.3 Decoupling and ferrite placement

1. Place all 22 × 100 nF decouplers **one per supply pin, on the same side
   of the board as the pin they decouple**, with a straight via down to
   the plane (no shared via between two capacitors).
2. Place FB1 (the 3.3 V ferrite bead) directly in the `DB1_3V3` → `+3V3`
   path, close to the DB1 header, per §6.2 step 5.
3. U12 (the 2.5 V LDO) needs no thermal relief — it dissipates 40 mW
   (`DESIGN_NOTES.md` §4.2) — a standard SOT-23-5 land pattern is enough.

### 6.4 How to split an inner plane layer in EasyEDA Pro (reference)

From EasyEDA Pro's own Layer Manager documentation (prodocs.easyeda.com,
read 13 Sep 2026):

1. Switch the active layer to the internal plane layer (L2 or L3).
2. Draw a closed loop using the broken-line/wire tool — it must be a
   complete closed loop, not an open line.
3. Assign the desired net to the enclosed region via the PlaneZone
   properties panel (right panel, after clicking the copper).
4. Click **Rebuild Plane Zone** (or Shift+B for all copper) to regenerate
   the fill.
5. Repeat for each additional net region needed.

---

## 7. Mechanical keepouts

From `ROUTING.md` §5, unchanged — do not move any of these, they are
generated from the HL2's own geometry and re-checked by
`tools/check_geometry.py`:

| | |
|---|---|
| The three HL2 sockets (J2/DB1, J3/DB12, J4/CN1) | Bottom side, fixed hole positions. Do not move |
| SlimSAS connector J1 | Local (10.40, 46.00) at the radio end — load-bearing, do not move toward the middle of the edge |
| **M3 U-notch** | Local x 1.30–4.70, y 61.95 to the top edge. **Keep copper 0.3 mm clear of it** |
| **Cut-outs over the radio** | The FPGA notch, local x 24.00–50.20 from the top edge to y 25.10, and the cut-out over the AD9866, T2, jumper DB6 and header DB3, local x 34.09–57.87, y 30.00–56.25 (step at x 48.00 down to y 34.01). **Nothing within 1 mm of either; pair tracks 2 mm off; fast tracks 3 mm off (§7.1)** |
| **J5, the JTAG pass-through** | Top side, **pin 1 at local (51.40, 30.80), rotation 90** (horizontal, just below J4) since 13 Sep 2026. Keep ~20 × 12 mm clear above it and 15 mm of height for a USB Blaster's 10-way IDC socket |
| **1.1 mm locating peg** | Local (4.04, 2.12) — optional, into HL2 MH6 |
| **Gowin-end M3 spacer hole** | Under the connector housing, ~3.2 mm — do not route copper through it; it is a mechanical clearance hole, not electrical |

**The break-off tabs.** Nothing crosses the slot or a tab: the two ends share
no net. The KiCad file carries rule areas that keep tracks, vias and pours
1 mm clear of each tab and every part 5 mm clear of each row of mouse-bite
holes (`DESIGN_NOTES.md` §13.2).

1. After routing, zoom to each tab.
2. Confirm no track, pad or copper-pour edge within 1 mm of the tab or its
   holes, and no part within 5 mm of a row of holes.
3. Confirm the pours on L2/L3 respect this too — plane fills are copper.
4. Confirm every SMD capacitor lies parallel to the slot (0 or 180 degrees).

### 7.1 Noise layout rules at the radio end (approved 13 Sep 2026)

These keep our fast signals away from the radio's receiver. Full reasoning:
`DESIGN_NOTES.md` §14.4. **Fast nets** are every radio-end pair (`A_*`, `B_*`)
plus `HL2_FWD_CLK_RAW`, `HL2_FWD_CLK`, `HL2_ADC_D0..2`, `HL2_AUX_CLK_OUT`,
`HL2_AUX_DAT_OUT`, `HL2_REV_CLK`, `HL2_AUX_CLK_IN`, `HL2_AUX_DAT_IN`,
`HL2_TX_D0..2`, every `DI_*`, `RX_*` and `X_*25` net, `LA_CLK` and `LA_PUMP`.

1. **Bottom layer (B.Cu) at the radio end: ground pour only.** Pour `GND` over
   the whole radio end on B.Cu. Route **no track** on B.Cu anywhere at the
   radio end; pads of the three bottom sockets are the only other copper.
2. **No fast track over the radio's FPGA, AD9866 or T2.** Keep every fast track
   3 mm or more from the FPGA notch and from the main cut-out. The only place a
   track may pass between the FPGA notch and the main cut-out (the 2.9 mm neck
   at local y 26.1–29.0) is a slow one: JTAG, enables, pull-ups.
3. **Fast tracks at least 3 mm from any board edge**, outer edge and cut-outs
   alike. In EasyEDA Pro put the fast nets in their own net class and give
   that class a 3 mm clearance to the board outline in the design rules (the
   exact menu name was not checked); otherwise check it by eye and with
   `check_geometry.py` after export.
4. **No track within 3 mm of DB3 pins 3 and 4**, at local (54.60, 39.82) and
   (54.60, 37.28): the AD9866's receive input. Any net, any layer.
5. **Ground stitching vias every 5 mm or less round each cut-out.** The
   KiCad file already carries 48 of them on `GND`, 1.6 mm outside the cut
   edges (largest gap 4.44 mm). Keep them. If the import drops them, place
   0.6/0.3 mm `GND` vias 1.6 mm outside each cut edge, no more than 4.5 mm
   apart, and no part within 2.2 mm of a cut edge.
6. **Place L1 (4.7 µH) and C29 (100 µF tantalum) within 8 mm of DB1 pins
   19/20**, and return C29 to ground next to DB1 pins 13/14.
7. **Place U11 within 5 mm of U1**, and C27, D13, D14 within 3 mm of U11: the
   link-alive detector's clock stub must be short.
8. **Place C30 within 3 mm of R_SHELL and C101 within 3 mm of R117** (both
   not fitted).

After routing, `python tools/check_geometry.py <board>` checks rules 1–8 on
the exported KiCad board, and KiCad DRC with `bridge/bridge.kicad_dru` next
to the board checks rule 3.

---

## 8. Checks before ordering

### 8.1 DRC

1. Top Menu → **Design → Check DRC**. Fix every error shown in the bottom
   DRC panel before proceeding — click an error to locate it on the board.
2. **Must read zero** violations of: clearance (now ≥0.15 mm everywhere,
   §3.2), track width (min 0.15 mm / max per net class), via size, and
   unrouted nets (should be exactly 0 — `STATUS.md` records 468 unconnected
   items at handover; every one must be routed).
3. Turn on **Design → Real-Time DRC** while doing any final touch-up
   routing, so new violations surface immediately.
4. Top Menu → **Design → Clear Errors** only after you have reviewed every
   item — do not clear-then-forget.

### 8.2 Length-matching report

5. Open the left-panel net tree, differential pair group. Confirm every
   pair in the forward group, reverse group and both auxiliary groups (§4.2)
   shows green (within its ±2.5 mm target), not red.
6. Spot-check with the Pad Pair Group Manager (§4.3 step 8) for the
   forward-group and reverse-group pairs specifically — these are the two
   groups where a miss actually breaks the link (skew on the forward group
   corrupts the receive data; skew on the reverse group corrupts what the
   far end receives).

### 8.3 Visual checks DRC will not catch

7. **A pair split across layers.** Click each of the 32 differential pair
   legs in turn and confirm both P and N of every pair are on **L1**, not
   one on L1 and one on L4. DRC checks clearance and connectivity, not
   "are both legs on the same layer" — this is a manual check.
8. **P and N swapped.** For every pair, confirm P is the lower-numbered
   connector contact in both rows (§4.1's tables) — getting this backwards
   on one pair inverts one lane (recoverable in gateware, per `PINMAP.md`
   §1.1, but confirm anyway rather than relying on that fallback).
9. **Termination and ESD placement.** Re-measure: are all 8 terminations
   (radio end) within 5 mm of their receiver pins, and are all 12+12 ESD
   arrays within 5 mm of their SlimSAS contacts? A DRC pass does not check
   distance-to-function, only electrical rules.
10. **Ground plane continuity.** Zoom across the whole L2 pour at both ends
    and confirm no via field or keepout has isolated a pocket of ground —
    especially under the SlimSAS connector's dense pad field.
11. **The +2V5 island.** Confirm it is still exactly local x 8–33, y 1–12 at
    the radio end and reaches every pin that needs it (U1/U2 VCCA, U3 VCCB,
    U12 output, `SL_VLVDS` link) — an import or a plane rebuild can
    silently shrink or merge it.

### 8.4 Final netlist comparison

12. Top Menu → **Design → Import Changes from PCB** (or, from the
    schematic side, **Design → Import Changes from PCB** — EasyEDA Pro's
    doc names this the PCB→schematic parity check). Run it.
13. A clean result shows **no added, removed or reassigned nets** — only
    component-attribute differences are even possible to carry across this
    check, per EasyEDA's own documentation, so any *net* difference reported
    here means the PCB and schematic have diverged and must be reconciled
    before ordering. Do not proceed to §9 with an unresolved netlist
    difference.

---

## 9. Ordering from EasyEDA Pro to JLCPCB

### 9.1 The main board (`bridge/`)

1. From the EasyEDA Pro editor, use the JLCPCB ordering integration (or
   export Gerber/drill files and upload at cart.jlcpcb.com — either path
   reaches the same order form).
2. **Base Material**: FR-4.
3. **Layers**: 4.
4. **Dimensions**: 64.50 × 92.00 mm.
5. **PCB Qty**: 5.
6. **Different Design**: enter what JLCPCB said in answer to the question in
   `DESIGN_NOTES.md` §13.2. The two ends carry different copper and snap
   apart, which JLCPCB's own rule may count as two designs; ask first.
7. **Delivery Format**: **Single PCB**. Do **not** select "Panel by
   Customer" — the owner has decided this ships as one board, snapped apart
   by hand after assembly, not panelized by the fab.
8. **PCB Thickness**: 1.6 mm.
9. **PCB Color**: green (or your preference — no cost or lead-time reason
   to change it for this board).
10. **Silkscreen**: white (default).
11. **Surface Finish**: **Lead-Free HASL**.
12. **Outer Copper Weight**: **1 oz**. **Inner Copper Weight**: **0.5 oz**
    (this is JLCPCB's own default inner weight, matching §2's stackup).
13. Leave **Impedance Control** off / not selected.
14. **Min via hole size/diameter**: leave at the default (cheapest) tier,
    0.3 mm / 0.4–0.45 mm — matches §3.2's default via. Do not select a
    tighter tier unless you specifically need the 0.25 mm differential-pair
    via at a smaller pad than 0.45 mm (you do not, per §3.2).
15. Confirm **Board Outline Tolerance**: ±0.2 mm (Regular) is fine — this
    board has no tolerance-critical outline features beyond what
    `check_geometry.py` already validated in KiCad.
16. Enable **PCB Assembly**.
17. Assembly tier: **Economic** (this is what `COST.md`'s whole cost model
    is built on — Standard/Advanced tiers cost more for no benefit here).
18. **Assembly Side**: top only — check this against the generated BOM;
    every populated part in this design is on the top side (the four
    hand-fitted through-hole sockets/headers are owner-soldered, not on the
    assembly BOM at all, per `DESIGN_NOTES.md` §7).
19. Upload the BOM and CPL (placement) files EasyEDA Pro exports for
    assembly.
20. **Check the BOM against `COST.md`'s part list before confirming**: every
    LCSC part number in `COST.md` §7 (radio end) and §2 (Gowin end) must
    appear, at the quantities given there, and JLCPCB's BOM checker must
    recognise every one of them (a red/unmatched line means a part number
    typo or a since-discontinued LCSC listing — stop and fix it, do not
    let JLCPCB substitute).
21. Confirm the **placement (CPL) file** shows every part at a sane
    rotation and side before finalizing — JLCPCB's on-site preview will
    flag obviously wrong rotations, but silent 180°-symmetric-footprint
    errors (some MOSFETs, some ESD arrays) will not be caught automatically.

### 9.2 The front panel (`panel-endcap/panel-endcap.kicad_pcb`) — second cart item

1. Add a second item to the same cart (do not merge it into the main
   board's order — it is a separate, unrelated PCB).
2. **Base Material**: FR-4. **Layers**: 2.
3. **Dimensions**: 106 × 55 mm.
4. **PCB Qty**: 5.
5. **Different Design**: 1. **Delivery Format**: Single PCB.
6. **PCB Thickness**: 1.6 mm (matches the main board and the enclosure's
   other panels — confirm this is what `panel-endcap.kicad_pcb`'s own
   `(thickness ...)` setting says before ordering, since this file was not
   specified as 1.6 mm in the brief and should be checked, not assumed).
7. **Surface Finish / other options**: leave at JLCPCB's defaults unless
   the owner specifies otherwise — this panel carries no components and no
   signal integrity requirement.
8. **PCB Assembly**: leave **off**. This panel is not assembled.
9. **Color and silkscreen — live quote, read from JLCPCB's instant-quote
   form 13 Sep 2026, 5 pieces, 2-layer, 106 × 55 mm, no assembly:**

| Configuration | PCB build time | Calculated price |
|---|---|---|
| **Default green, white silkscreen** | 2 days | **$6.80** ($4.00 engineering fee + $2.80 board) |
| **Black solder mask, white silkscreen** | 3 days (one day longer than green) | **$6.80** — identical price |

Black solder mask costs nothing extra at this size and quantity — it only
adds one day to the fab's stated build time. Silkscreen defaults to white
automatically under a black mask (JLCPCB's own form note: "For most colors,
the silkscreen is printed white. Only for white solder mask is the
silkscreen printed [in another colour]"), so no separate silkscreen-colour
selection is needed either way.

10. Shipping is combined across both cart items at checkout — the
    per-item "$27.63 DHL" figure shown during quoting is an
    estimate-in-isolation, not what you'll actually pay once both items
    are in one cart; the real combined shipping charge appears at
    checkout after both items are added.

---

## 9.5 The test points (eleven)

Cut from 73 on 13 Sep 2026. Each one is there for the bring-up sequence or
the fault-finding table in `ROUTING.md`.

| Net | End | Why |
|---|---|---|
| `GND` | radio | scope ground clip (2 mm through-hole pad) |
| `+3V3` | radio | the rail after the input bead |
| `+2V5` | radio | the 2.5 V regulator output, the translators' low side |
| `SB_PRSNT_IN` | radio | presence detect: is a powered far end there? |
| `JTAG_EN_N` | radio | JTAG over the cable, after the link-alive gate: must read HIGH at power-up and with stock gateware |
| `AUXIO_EN_N` | radio | the drive enable straight from the radio's gateware (LOW under stock gateware, which is why it is gated) |
| `AUXIO_OE_N` | radio | the drive buffer's real enable after the link-alive and presence gates: HIGH unless the gateware, `LINK_ALIVE` and presence all allow it |
| `LINK_ALIVE` | radio | the link-alive detector: about 2.2 V only while the forward clock runs and a far end is present |
| `HL2_FWD_CLK` | radio | forward clock after the divider: expect 2.50 V high |
| `HL2_REV_CLK` | radio | reverse clock as it enters the radio's FPGA pin 88 |
| `G_GND` | Gowin | scope ground clip (2 mm through-hole pad) |

The Gowin end has no receiver of its own (the FPGA receives), so there is no
forward clock to probe on it.

---

## 10. NOT FOUND — flagged for the owner, not invented

- **Default single-ended track width and clearance as a *deliberate design
  choice*.** The 0.25 mm / 0.15 mm values used throughout this guide come
  from `bridge/bridge.kicad_pro`'s `Default` net class (the values the
  generator/placement tooling actually used), not from a stated rule in
  ROUTING.md or DESIGN_NOTES.md. Treat them as "what was already there and
  passed DRC," not as a value the owner chose for a stated reason.
- **`panel-endcap.kicad_pcb`'s board thickness.** Not independently
  re-verified against a stated 1.6 mm requirement in the brief — §9.2 step 6
  asks you to check the file's own setting before ordering rather than
  assuming it matches the main board.
- **The exact PCB build-time / price delta for anything beyond the two
  color configurations quoted live in §9.2** — e.g. white solder mask,
  other silkscreen colors — was not queried; the two rows shown are the
  only two the brief asked for.
