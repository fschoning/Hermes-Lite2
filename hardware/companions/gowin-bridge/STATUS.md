# gowin-bridge status (branch `gowin-bridge-pcb`, rev B)

Last updated 2026-09-12. Worktree `G:\proj\worktrees\Hermes-Lite2-gowin-bridge-pcb`.

rev B replaced rev A's two dual-link DVI-D sockets per board with three HDMI
sockets per board, and made the HL2-side board symmetric so two radios can
link to each other with the same board. The rev A design is in git history.

> ## rev C is APPROVED and PART-BUILT. Read this first.
>
> **`PINMAP.md` is rev C and is committed.** It is the authoritative pin map and
> the FPGA side can be brought into line with it now.
>
> **The two board projects in this tree are still rev B**, and are still
> self-consistent: ERC 0, schematic/PCB parity 0, and both checkers pass. They
> have deliberately NOT been half-regenerated, because a board that fails its
> own checkers is worse than one revision behind.
>
> **What remains is listed under "rev C: remaining work" below, with every
> decision already settled**, so it can be executed without re-deriving
> anything: the netlist, the panel project, the checker extension, four
> document updates and the costing.

---

## Done and validated

| Item | State |
|---|---|
| `PINMAP.md` rev B | Complete, committed on its own first so the FPGA worker can read it. Both socket types, all three cable configurations, both HL2 headers, all 16 used Tang J14 pins with ball and Gowin IO name, the direct-LVDS table, and paste-ready `IO_LOC`/`IO_PORT` constraints. |
| **A wiring error inherited from rev A, found and fixed** | rev A (and the rev B brief) had **DB12 pins 5 and 6 swapped**: PIN_88 is DB12 pin **6** and PIN_89 is DB12 pin **5**, per `hardware/hl/hermeslite.net`. rev A's KiCad files were wired wrong. Also corrected: the LEDs on DB1 pins 9/11/15/17 are **1 k pull-ups to +3V3** through the LED, not 1 k to ground, which reverses the sign of the load on the receiver. |
| Connector selection | **Both are real, stocked LCSC parts with datasheet land patterns.** Board A: XKB A71-05H4-111N1 mini HDMI Type C, LCSC **C2682170**, hybrid mount (19 SMT contacts, four THT shell legs in plated slots, two THT locating pegs), 2,217 in stock. Board B: Amphenol ICC 10029449-111RLF, LCSC **C427307**, 3,324 in stock, **10,000 mating cycles**. |
| Board A footprint | **Generated from the XKB recommended-layout drawing**, the only mini HDMI drawing found that dimensions its pattern relative to the PCB edge. Numbers are in `MINI_HDMI` in the generator with their source. |
| Board B footprint | **Stock KiCad `HDMI_A_Amphenol_10029449-x01xLF_Horizontal`, used unchanged** after re-checking every value against Amphenol drawing 10029449 rev Y sheet 3: pads, pitch, span, the deliberate 0.25 mm contact-field offset, all four shell-hole positions and both hole spacings. |
| `hl2-bridge` schematic | **Complete. Loads in KiCad 10, ERC 0 violations.** 148 parts (111 fitted), 86 nets. Every part carries `LCSC`, `MFR`, `Note` and `Description`. |
| `tang-bridge` schematic | **Complete. ERC 0 violations.** 168 parts (112 fitted), 85 nets. |
| Both `.kicad_pcb` | Board outline, 4-layer stackup (signal / GND plane / power plane / signal), full netlist, every footprint placed, ground and power zones, a `+2V5` island on board A. **Schematic/PCB parity: 0 issues on both.** DRC reports only unconnected items (278 and 306), which is the routing that is deliberately left to the user. |
| `ROUTING.md` | **New.** EasyEDA Pro import, stackup, the 100 ohm trace geometry with the calculation, JLCPCB rules, net classes, routing order, both connector fan-outs in detail, length-matching numbers with the physics, via and plane rules, where each passive goes relative to the receiver, pour and stitching, the DRC list, export and assembly, and a fault-finding table. |
| Board A socket geometry | **Verified twice.** `tools/check_geometry.py` recomputes the DB1/DB12 hole grid independently from `hermeslite.kicad_pcb` and confirms all 26 holes; then the Excellon export was read back and confirms the same, **including the bottom-side x-mirroring trap** — there is no hole at the un-mirrored x = 1.00. |
| Mechanical arithmetic | **Three mini HDMI sockets fit the 48 mm corridor with room to spare** (11.20 mm bodies, 6.20 mm between them, 0.55 mm copper to the board edge). Board A is now a plain rectangle entirely inside the filter-board corridor — rev A's L-shaped board with a tab overhanging the filter board is gone. Height down from ~26 mm to 15.74 mm, so stacking a DB1 companion now works. `DESIGN_NOTES.md` 6. |
| 2.5 V threshold | **Resolved and justified**: one SN74AVC8T245 in front of all eight LVDS driver inputs gives 370 mV of guaranteed margin instead of 0 mV, with forward clock A brought into the same package through a 150 R / 470 R divider so clock and data share one propagation delay. The unguaranteed direct-connection argument is documented with its numbers and eight bypass links are fitted for it. `DESIGN_NOTES.md` 3. |
| AC-coupling option | Present on all 12 received pairs, selectable by 0 R links, **defaulting to DC-coupled**. Values sized and the assumptions stated. `DESIGN_NOTES.md` 4. |
| 1:1 print templates | **Done** (rev A did not have these). `templates/` has a top and a mirrored-bottom PDF per board, each with a 50 mm calibration rule on `Dwgs.User` so a scaled print is detectable. |
| Generator and checkers | `tools/gen_gowin_bridge.py` produces schematic, PCB, libraries and BOM for both boards from one netlist description, so they cannot drift. Two checkers are new: `tools/check_geometry.py` verifies placement and the HL2 hole grid, and `tools/check_netlist.py` asserts the header pin maps against `PINMAP.md` and **proves the OUT-to-IN symmetry** by walking all three cables signal by signal. Both pass. Two latent bugs in `tools/kisexp.py` fixed along the way: oval drills emitted the word "oval" where a number belonged, and a courtyard circle measured as zero-height, which silently collapsed the placer. |
| KiCad toolchain | KiCad **10.0.6** at `C:\Users\franz\AppData\Local\Programs\KiCad\10.0`. `kicad-cli.exe` was used for every ERC, DRC, drill and PDF result quoted here. Files are written in KiCad 8 format. |

---

## Partial / not done

| Item | State | What is needed |
|---|---|---|
| **PCB routing** | **Not done, by decision.** No tracks on either board. | The user routes in JLCPCB's EasyEDA Pro editor. `ROUTING.md` is the procedure. |
| **BOM cost totals** | **Not done.** Only the two connectors are priced ($0.4593 and $0.5081 at qty 10, read 12 Sep 2026). | Quote these LCSC numbers at qty 10 and qty 100: **C201946** (DS90LV047A), **C87137** (DS90LV048A), **C81461** (SN74AVC4T245PWR), **C53535** (SN74AVC8T245PWR), **C138714** (TPD4E05U06DQAR, 17 off across both boards), **C194395**, **C6186**, **C5361769**, **C124413**, **C50982**, **C2337**, and the passives **C17168 C1525 C25744 C25076 C21190 C25092 C25741 C25746 C25117 C52923 C15525 C25867 C25900 C1555**. Watch for reel-only minimum order quantities on the passives, which dominate a two-board build. Then add JLCPCB's board price for 48x66 and 90x46 4-layer at qty 5, plus setup, stencil and per-unique-Extended-part fees. |
| **Gerber / CPL export** | Not done. | Needs a routed board. Steps are in `ROUTING.md` 8. |
| **Mini HDMI pin-1 end** | **UNVERIFIED and it is the highest-risk item on the board.** | The XKB drawing labels pin 1 on its front view but not on its land-pattern view. The footprint assumes **pin 1 at the +x end**. Check against the part in hand; if wrong, set `MINI_HDMI['pin1_at_plus_x'] = False` and regenerate. Getting it wrong makes the board scrap. |
| **Mini HDMI cable boot width** | **UNVERIFIED, and it is the one thing that could still stop three cables plugging in at once.** No manufacturer publishes it; about fifteen were checked. | Measure the boots on the cables you will use. Estimates are 15.6 mm (proportional scaling from the published full-size boot) to 17.3 mm (same absolute wall thickness) against **17.40 mm of pitch** — so it fits either way, but the pessimistic case leaves 0.08 mm. `DESIGN_NOTES.md` 6.3 has four fallbacks, one of which (running the gateware's existing 3-lane geometry on the outer two sockets) needs no board change at all. |
| **Board B's position on the Tang dock** | **Still "verify by measurement".** No dock board file, drawing or 3D model was obtained. | Print `templates/tang-bridge-1to1-TOP-fit-check.pdf` at 100 %, measure its 50 mm rule, offer it up. Check the distance from the J14 hole row to the board edge, the clearance to the PMOD sockets, and **which end of J14 is pin 1**. Then change `board_b()`'s J14 position and regenerate. |
| **HL2 +3V3 spare current** | **Unverified** — the regulator was not identified in `Power.sch`. | Measure the HL2's 3.3 V rail with board A plugged in. Board A needs ~112 mA. `DESIGN_NOTES.md` 5.1. |
| Slow-line data rate | 10-25 Mbit/s is reasoning, not measurement. | Bench-measure before the gateware relies on a number. This is a real reduction from rev A's 307.2 Mbit/s command channel and it is the price of using HDMI's four pairs. |

`DESIGN_NOTES.md` section 9 is the full list of 14 unverified items with the
section that discusses each.

---

## BOM defects found by a live LCSC price check (12 Sep 2026) - MUST FIX

A price lookup against LCSC's live catalogue found that **six of the part
numbers in the committed BOMs are wrong or unbuyable.** These are defects in
rev B as it stands. They were found before any money was spent, which is the
point of checking, but nothing should be ordered until they are resolved.

| Line | What the BOM says | What LCSC actually has | Severity |
|---|---|---|---|
| **Quad LVDS driver** | `C201946`, TI DS90LV047ATM/NOPB | **Zero stock at LCSC and absent from JLCPCB's assembly library.** Only third-party marketplace sellers have it, at $2.65-3.27. | **Blocking.** Two per board A, one per board B. There is no board without it. |
| SN74AVC8T245PWR | `C53535` | **Number does not exist.** The correct one is **`C465742`**, 16,677 in stock, $0.93 at qty 10. | Blocking, trivially fixed. |
| 2x3 female header (HL2 DB12) | `C124413`, described as 2x3 | LCSC ships that number as a **1x4 single-row** socket | Wrong part; needs a real 2x3. |
| 2x20 female header (Tang J14) | `C50982` | Exists but **zero stock**, and not in JLCPCB's library | Needs an alternative. |
| 2x10 stack-through header (HL2 DB1) | `C5361769` | **Number does not exist.** | Needs a real long-tail 2x10, or the stack-through feature sourced elsewhere. |
| 470 R 0402 | `C25117` | Real part with stock, but **not in JLCPCB's assembly library** | Hand-fit one 0402, or find a Basic equivalent. |

Four further numbers point at parts that are real but not the value or package
the BOM claimed: `C21190` is 0603 not 0402, `C25746` is **113 k not 150 R**,
`C25867` is **1.5 k not 1k8**, and `C1555` is **22 pF not 33 pF**.

**The design has been reworked on paper so those four values are not needed at
all**, using only values whose numbers the price check confirmed. Not applied
yet, because applying it means regenerating and that is on hold:

* **HPD pull-down 1 k -> 100 R** (`C25076`, confirmed). Against the 10 k
  pull-up at the far end the detect level improves from 0.30 V to 0.033 V, at
  0.33 mA of idle current.
* **`VBIAS` divider 1k8 / 1k0 -> 10 k / 4k7** (`C25744` / `C25900`, both
  confirmed). 1.055 V instead of 1.18 V, still mid-range for the DS90LV048A's
  0.05-2.35 V input common mode. The divider carries no steady current, because
  the per-leg bias resistors sit in common mode, so its higher 3.2 k Thevenin
  impedance costs nothing; it stays bypassed with 100 nF.
* **Clock-A divider 150 R / 470 R -> 100 R / 470 R** (`C25076` plus the single
  470 R line above). Recomputed: high level **2.61 V** (980 mV over the
  translator's 1.63 V threshold, 390 mV under its 3.0 V absolute maximum),
  **5.55 mA** from PIN_98 (inside its 8 mA drive setting), Thevenin 82.5 ohm,
  edge contribution 0.73 ns. Better on every count than 150/470, and it needs
  one unusual value instead of two.
* **Slow-line damper 33 pF -> 22 pF** (`C1555`, which is what that number
  really is). A not-fitted option anyway; 22 pF into 100 R is 2.2 ns.

After that rework the entire passive set is **0R, 22R, 100R, one value in the
300-680 ohm range, 4k7, 10k, 100k, 22pF, 100nF, 1uF and 10uF 0805** - eleven
values, ten of them with price-checked numbers.

### Every defect now has a resolution (looked up 12 Sep 2026)

**No redesign is needed. One footprint question remains open.** Apply these
when regeneration is unblocked:

| Line | Change to | Stock | Price at 10 | JLCPCB library |
|---|---|---|---|---|
| **Quad LVDS driver** | `C201946` -> **`C206491`**, DS90LV047A**TMX**/NOPB | 1,312 | $1.8396 | **yes**, Extended |
| SN74AVC8T245PWR | `C53535` -> **`C465742`** | 16,677 | $0.9296 | yes |
| 2x20 female (Tang J14) | `C50982` -> **`C5124634`**, BOOMELE 2.54-2*20P, vertical | 11,945 | $0.3305 | **yes**, Extended |
| 2x10 female (HL2 DB1) | `C5361769` -> **`C42431860`**, JXTCONN PM2.54-2X10P-H85, vertical | 3,405 | $0.1921 | yes, Extended |
| 300-680 R 0402 | `C25117` -> **`C25104`**, 330 R | 742,400 | $0.44 / 100 | **yes, Basic** |
| 2x3 female (HL2 DB12) | `C124413` -> `C99515` **is the wrong variant, see below** | 375 | $0.1417 | no (through hole) |

**The blocking item turned out to be trivial.** The quad LVDS driver is the
*same TI silicon and the same pinout* under a different LCSC catalogue number -
`C206491` is the TMX (tape-and-reel) suffix of the identical DS90LV047A in
SOIC-16. Nothing to redraw: the symbol, the footprint and every pin assignment
stay exactly as they are, and it is in JLCPCB's library. Only the BOM line
number changes.

**Still open: the 2x3 female header must be VERTICAL, and the part found is
not.** `C99515`'s "Holes Direction" field reads **Side**, i.e. right-angle
entry. Board A's DB12 socket sits on the underside and plugs straight down onto
a male header on the radio, so it has to be **top entry**. A vertical 2x3
2.54 mm female socket still needs finding. It is a hand-soldered through-hole
part either way, so this blocks ordering but not layout - the footprint
(`PinSocket_2x03_P2.54mm_Vertical`) is already the right one.

**Confirmed: LCSC stocks no long-tail 2x10 socket at all** - all seven 2x10
female listings are ordinary ~3.2 mm pin length. So the **stack-through feature
has to be sourced outside LCSC**, and `C42431860` is the fallback ordinary
socket for anyone who does not want to stack a companion board. This is a
documentation change to `README.md` section 4 when rev C lands: the stack-through
header is no longer a JLCPCB line item.

**Clock-A divider, final values.** With 330 R being the Basic part in that
range, the divider becomes **100 R series plus 660 R shunt (two 330 R in
series)** rather than 100 R / 470 R - every part then a JLCPCB Basic part:

| | |
|---|---|
| High level at the translator A input | 3.3 x 660 / (660 + 100 + 25) = **2.77 V** |
| Margin over the 1.63 V threshold | **1.14 V** |
| Headroom under the 3.0 V absolute maximum | **230 mV** |
| Current from PIN_98 | **4.2 mA**, comfortably inside its 8 mA drive setting (100 R / 330 R would have drawn 7.25 mA and forced the pin to 16 mA) |
| Thevenin impedance | 87 ohm |
| Edge contribution into the translator's ~4 pF | **0.77 ns** |
| Low level with the HL2 FPGA unconfigured | (3.3 - 1.7) x 660 / (1000 + 100 + 660) = **0.60 V**, under the 0.875 V limit |

**All ten kept passives are confirmed Basic parts in JLCPCB's library**:
`C17168` 0R, `C1525` 100nF, `C25744` 10k, `C25076` 100R, `C25092` 22R,
`C25741` 100k, `C25900` 4k7, `C52923` 1uF, `C15525` 10uF 0805, `C1555` 22pF.

**Cost, now that the driver has a price.** Per board at qty 10, silicon and
connectors only:

| | Board A | Board B |
|---|---|---|
| Quad LVDS drivers | 2 x $1.8396 = $3.68 | 1 x $1.8396 = $1.84 |
| Quad LVDS receivers | 1 x $1.4348 = $1.43 | 2 x $1.4348 = $2.87 |
| Translators | $0.93 + $0.31 = $1.24 | - |
| ESD arrays | 8 x $0.0874 = $0.70 | 9 x $0.0874 = $0.79 |
| LDOs | $0.056 + $0.22 = $0.28 | $0.22 |
| HDMI sockets | 3 x $0.4593 = $1.38 | 3 x $0.5081 = $1.52 |
| Headers and sockets | ~$0.65 | ~$0.65 |
| **Subtotal per board** | **~$9.36** | **~$7.89** |

Plus, per order and not per board: **bare boards $7.00 for five of either size**
($13.00 for ten), **passives about $6.50** in reel minimums however few are
used, and assembly from $8.18 setup + $1.53 stencil + $3.07 per unique Extended
part (Economic) upward.

**So for 2 sets:** boards $14.00 (two lots of five, the minimum) + passives
$6.50 + silicon 2 x ($9.36 + $7.89) = $34.50, giving **about $55 in parts and
bare boards**, before assembly and shipping. Assembly roughly doubles it:
Economic PCBA on both boards is 2 x ($8.18 + $1.53) plus about 8 unique
Extended parts x $3.07 x 2 boards, i.e. **$68 or so**, and shipping about $28
(unconfirmed for Germany).

**For 5 sets:** boards $14.00 (five of each is still one lot each) + passives
$6.50 + silicon 5 x $17.25 = $86.25, giving **about $107 in parts and bare
boards**. Assembly setup does not scale with quantity, so the same ~$68 covers
it. **Roughly $200 all-in for five sets against roughly $150 for two** - the
marginal set costs about $17, and almost all of the money is setup.

These totals exclude the vertical 2x3 header (not yet sourced) and the
stack-through socket (not available at LCSC at all).

### What the price check did confirm

| | |
|---|---|
| Bare boards, **both** sizes, 4 layer, 1.6 mm, HASL | **$7.00 for 5, $13.00 for 10** (a live JLCPCB promotional tier, not list price) |
| ENIG instead of HASL | **+$16.80** at qty 5 |
| Shipping | about **$28** DHL Express - **but the quote tool could not be forced off its United States default**, so treat it as indicative for Germany |
| Assembly, Economic | $8.18 setup + $1.53 stencil + **$3.07 per unique Extended part** |
| Assembly, Standard, single side | $25.56 setup + $8.21 stencil + $1.53 per part, Basic or Extended |
| Through-hole assembly | supported: $0.0164 per joint plus $3.58 per order |
| Minimum assembly quantity | **2 boards** |
| Mini HDMI, XKB A71-05H4-111N1, `C2682170` | 2,217 in stock, **$0.4593** at 10, $0.3498 at 100 |
| Full-size HDMI, Amphenol 10029449-111RLF, `C427307` | 3,324 in stock, **$0.5081** at 10, $0.3950 at 100 |
| Quad LVDS receiver, `C87137` | 1,585 in stock, **$1.4348** at 10 |
| SN74AVC4T245PWR, `C81461` | 29,575 in stock, **$0.3096** |
| ESD array, `C138714` | 43,815 in stock, **$0.0874** |
| 2.5 V LDO, `C194395` | 42,120 in stock, **$0.0561** |
| AMS1117-3.3, `C6186` | in stock, **$0.2198**, Basic |

**Every passive is minimum-order 100 pieces** (50 for the 1 uF), reel only, at
$0.28 to $2.59 for the whole batch. For a two-board build the passives cost
roughly **$6.50 in minimum batches no matter how few are used**, which is the
biggest surprise in the costing and the reason a per-piece estimate would have
misled.

**The cost total is still not final**, because the driver and three headers have
no price. What can be said: bare boards $7 for five of each; the priced silicon
and connectors come to roughly **$12 per board A and $9 per board B** at qty 10,
*excluding the driver*; plus about $6.50 of minimum-batch passives per order;
plus assembly fees from the table above.

---

## rev C: settled design, and the remaining work

`PINMAP.md` rev C holds the full pin map. What follows is everything else that
was decided, so that building it needs no fresh analysis.

### Settled: the strap circuit

**One 1x3 header (`ROLE`) with a single shunt, plus one single-gate inverter**
(74LVC1G04 class, SOT-23-5) producing `ROLE_N`, plus a **10 k pull-up on
`ROLE_N`**. On both boards.

The brief's two-link / double-pole proposal was rejected and why is recorded in
`PINMAP.md` 2.4: any independently-settable pair allows "both levels low",
which enables the G2 translator port while the gateware believes it is ROLE B
and is driving those pins as outputs - CMOS against CMOS on PIN_72 and PIN_80.
One shunt plus one inverter makes the complement a property of the circuit. The
pull-up direction is chosen so a missing or dead inverter **disables** the
auxiliary link rather than enabling contention.

**The inverter is the one part still needing an LCSC number.** A single-gate
inverter in SOT-23-5 is a commodity; it was not price-checked with the rest.

What `ROLE` / `ROLE_N` drive:

| | ROLE A | ROLE B |
|---|---|---|
| G1 driver pair `EN` = `ROLE` | enabled | tri-stated |
| G2 driver pair `EN` = `ROLE_N` | tri-stated | enabled |
| Translator port carrying G1 toward the HL2, `OE` = `ROLE` | disabled | enabled |
| Translator port carrying G2 toward the HL2, `OE` = `ROLE_N` | enabled | disabled |
| 100 R termination, **fitted or not, not switched** | fit on G2 | fit on G1 |

### Settled: the chip complement

Board A needs **three enable domains on the driver side** (always-on for `OUT`,
`ROLE` for AUX G1, `ROLE_N` for AUX G2) and the DS90LV047A has one enable per
package, so:

| | Board A | Board B |
|---|---|---|
| Quad LVDS drivers | **3** (`OUT` 4 ch; AUX G1 2 ch; AUX G2 2 ch) | **3** (same split) |
| Quad LVDS receivers | **2** (`IN` 4 ch, gated by cable detect; AUX 4 ch, always on) | **2** |
| SN74AVC8T245, 2.5 V -> 3.3 V | **1**, all 8 channels used: `OUT` clock and 3 lanes, plus all 4 AUX pins | - |
| SN74AVC4T245, 3.3 V -> 2.5 V | **2**: U7 port 1 = `IN` clock + strap read (always on), port 2 = AUX G2 (`OE` = `ROLE_N`); U8 port 1 = AUX G1 (`OE` = `ROLE`), port 2 unused | - |
| Single-gate inverter | **1** | **1** |
| LDOs | 2 (one DNP) | 1 |

The **receivers never need disabling for direction** - a receiver is
high-impedance on the line, and it is the *translator output* that must
tri-state. That is what keeps the receiver count at two.

### Settled: the panel, 94 x 100 mm

Only one arrangement fits the bracket: **board B rotated 90 degrees**, side by
side with board A. Every other combination exceeds 100 mm (board B unrotated is
138 mm wide side by side, 112 mm tall stacked; board A rotated gives 156 mm).

```
  y 100  +-------------------------+--------+   <- top rail, V-score at y = 95
   95    |  board A  48 x 66       | board  |
         |  socket edge at y = 95  |   B    |
         |  (V-scored: clean edge, |        |
         |   no nubs)              | 46 x 90|
   29    +-------------------------+ rotated|
         |  coupon 48 x 24         | socket |
         |  fiducials + label      | edge at|
    5    +-------------------------+ x = 94 |   <- bottom rail, V-score at y = 5
    0    +-------------------------+--------+
         x 0                     48       94
                                  ^
                       V-score at x = 48, full height
```

* **Three V-scores** - y = 5, y = 95, x = 48 - each straight, edge to edge, with
  material on both sides for its whole length.
* **One routed separation with mouse bites**, between board A and the coupon at
  y = 29. That is board A's **back** edge, not a socket edge. The ~0.3 mm nubs
  reduce its clearance to the HL2 magjack from 1.0 mm to 0.7 mm; file them flat
  after snapping.
* Both socket edges land on outer panel edges or on a V-score, so **no nubs
  anywhere a plug goes**.
* Rails are on the **y axis**, where 10 mm was spare; the x axis had only 6 mm.
* **If the fab queries the panel, the fallback is two separate orders** at
  roughly $40 more, which goes in `README.md`.

### Settled: AUX runs at a divided rate

**38.4 MHz DDR = 76.8 Mbit/s per lane**, not 153.6 MHz DDR. The G2 return clock
is on an ordinary I/O that cannot feed a PLL, so the sampling phase cannot be
adjusted; at a 13.02 ns unit interval it does not need to be. The hardware stays
capable of 307.2 Mbit/s. A control channel needs kilobits, so this costs
nothing real. **Do not** try to reclaim the two clock lanes by timing AUX data
off cable 1's or cable 2's clock: the inter-cable phase is unknown, and it would
add risk for bandwidth that is not needed. Recorded as a possible future
gateware-only optimisation.

### The two hand-soldered sockets, sourced

Neither exists at LCSC, confirmed by search, so both are **do-not-place with
their footprints kept**:

| Part | Where to buy |
|---|---|
| **Vertical 2x3 2.54 mm female socket** (HL2 DB12) | LCSC has **none** - their vertical female headers start at 2x4. Buy a 2x4 and cut it down, or source a 2x3 elsewhere. |
| **2x10 2.54 mm female socket, long tails** (HL2 DB1 stack-through) | **Samtec SSQ-120-01-G-D** (Mouser 612-SSQ-120-01-G-D) or **SSQ-120-01-T-D** (Digi-Key SAM1183-20-ND), ~10 mm tails; or **Phoenix Enterprises HWS16492**, $0.99, 10.5 mm tails. Also Harwin M20 series. |

Also needed and in stock if the strap is built as a header rather than links:
2x3 male vertical header `C5116479` (in JLCPCB's library) and jumper shunts
`C5305`.

### rev C: remaining work, in order

1. **Regenerate both boards** from the settled netlist above. Board A now
   carries 10 ICs on 48 x 66 mm, so expect the autoplacer regions to need
   widening and two or three DRC iterations, as rev B did.
2. **Add the panel project**, a third KiCad project from the same generator:
   both boards' parts transformed into panel coordinates, merged netlist with
   prefixed reference designators, the three V-score lines on a fabrication
   layer, the routed coupon separation, three fiducials and the panel label.
3. **Extend `tools/check_netlist.py`**: re-point the socket tables at the rev C
   roles, and add a strap check that asserts `ROLE` and `ROLE_N` are driven
   only by the header and the inverter, that no translator `OE` is tied to a
   constant, and that **no combination of the single shunt can enable a
   translator port toward a pin the gateware drives** - the contention case.
4. **Extend `tools/check_geometry.py`** for the panel: every part inside its own
   board's outline, nothing crossing a V-score line, and the panel bounding box
   within 100 x 100 mm.
5. **Update `README.md`** (three cables, the strap and how to set it, the panel
   and that the order form's "different designs in this file" field must be
   **2**, the two hand-soldered sockets with the parts above, the two-order
   fallback), **`DESIGN_NOTES.md`** (why every lane is 307.2 Mbit/s, the margin
   table at that rate, the AUX divided-rate reasoning, the strap analysis, the
   panel arithmetic), **`ROUTING.md`** (307.2 Mbit/s everywhere, the AUX
   fan-out, panel routing and the V-score keep-outs) and this file.
6. **Price the assembled panel for 2 and 3 panels.**


---

## Exact next steps to resume

0. **Read the rev C pause note at the top of this file.** If the auxiliary
   direction decision has arrived, rev C comes before everything below. If it
   has not, the BOM defects above can be fixed independently and should be.
1. `cd G:\proj\worktrees\Hermes-Lite2-gowin-bridge-pcb\hardware\companions\gowin-bridge`
2. `python tools/gen_gowin_bridge.py`, then `python tools/check_geometry.py`
   and `python tools/check_netlist.py`. Both checkers must print `OK`. Nothing
   below should start until they do.
3. **Print both `templates/*-1to1-TOP-fit-check.pdf` at 100 %**, measure the
   50 mm rule, and offer them up to the HL2 and to the Tang dock. Fix anything
   that does not line up in the generator, not in the KiCad files.
4. **Buy one mini HDMI cable and measure its boot with calipers.** If it is
   over 17.4 mm wide, decide between the four options in `DESIGN_NOTES.md` 6.3
   before doing any layout work.
5. **Settle the mini HDMI pin-1 end** — buy one connector, or get the SOFNG
   drawing (LCSC C136421), which does label its land pattern.
6. Route board A in EasyEDA Pro following `ROUTING.md`. Do the three mini HDMI
   fan-outs first; everything else has room.
7. Route board B. It is much easier.
8. Price the BOM (the part list is in the table above) and add the totals to
   `README.md` section 8.
9. Order. `ROUTING.md` 8.
10. Bring-up order: check the 3.3 V rail, then scope `TP_HL2_CLKA` and
    `TP_DRVI_O1_CLK`, then run the Gowin's delay sweep, then the reverse link.
    `ROUTING.md` 9 is the fault-finding table.

**Anything that changes a net must be changed in `tools/gen_gowin_bridge.py`
and regenerated, never hand-edited in the KiCad files, and `PINMAP.md` must be
updated in the same commit.**

---

## The FPGA side has to change to match

`gateware/variants/hl2b5up_gowinlink/gowinlink_pins.tcl` on branch
`gowin-link` (worktree `G:\proj\worktrees\Hermes-Lite2-gowin-link`) is marked
PROVISIONAL and says to come into line with this file once it is published. It
now needs:

* **`gl_aux_out` on PIN_87 becomes the second forward clock.** It is no longer
  a spare output driven low; it must carry a copy of the 76.8 MHz forward
  clock, generated from the same `altddio_out` structure as clock A on PIN_98
  so both clocks and all six data lanes come out of identical I/O registers.
* **Lanes 0,1,2 (PIN_72, 76, 77) and lanes 3,4,5 (PIN_80, 83, 85) are now in
  two separate cables**, each with its own clock. On the Gowin side that means
  two forward clock domains — `link_clk_a` on U20 and `link_clk_b` on Y18 —
  with each cable's three lanes clocked by its own, and the two 6-bit halves of
  a sample rejoined after per-lane alignment.
* **The command channel's rate drops** from 307.2 Mbit/s on a differential pair
  to roughly 10-25 Mbit/s on a single-ended cable wire.
* **DB12 pins 5 and 6:** the tcl's comment block already had these the right
  way round (PIN_88 = DB12 pin 6, PIN_89 = DB12 pin 5). rev A of `PINMAP.md`
  did not. No tcl change needed, but do not "fix" it to match rev A.
* The Gowin `.cst` needs the full pin list in `PINMAP.md` section 5.2, which is
  paste-ready.

---

## Validation commands used

```
set KC=C:\Users\franz\AppData\Local\Programs\KiCad\10.0\bin\kicad-cli.exe

python tools/gen_gowin_bridge.py
python tools/check_geometry.py
python tools/check_netlist.py

%KC% sch erc --severity-error -o hl2-bridge/hl2-bridge-erc.rpt hl2-bridge/hl2-bridge.kicad_sch
%KC% pcb drc --severity-error --schematic-parity --refill-zones ^
     -o hl2-bridge/hl2-bridge-drc.rpt hl2-bridge/hl2-bridge.kicad_pcb

%KC% pcb export drill --format excellon --drill-origin absolute ^
     --excellon-units mm --excellon-separate-th -o drl/ hl2-bridge/hl2-bridge.kicad_pcb

%KC% pcb export pdf --mode-single --scale 1 --black-and-white --drill-shape-opt 2 ^
     --exclude-value --layers "Edge.Cuts,Dwgs.User,F.SilkS,F.Cu,F.Fab" ^
     -o templates/hl2-bridge-1to1-TOP-fit-check.pdf hl2-bridge/hl2-bridge.kicad_pcb
```

Results at the time of writing: **ERC 0 violations on both boards, schematic/PCB
parity 0 issues on both, `check_geometry.py` OK on both**, and the drill
readback confirms every DB1, DB12, shell-leg and locating-peg hole.
