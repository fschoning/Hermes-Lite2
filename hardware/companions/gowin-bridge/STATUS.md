# gowin-bridge status (branch `gowin-bridge-pcb`, rev B)

Last updated 2026-09-12. Worktree `G:\proj\worktrees\Hermes-Lite2-gowin-bridge-pcb`.

rev B replaced rev A's two dual-link DVI-D sockets per board with three HDMI
sockets per board, and made the HL2-side board symmetric so two radios can
link to each other with the same board. The rev A design is in git history.

> ## rev C is PAUSED. Read this first.
>
> **The boards and `PINMAP.md` in this tree are rev B and are self-consistent.**
> A rev C re-allocation was specified and analysed but **deliberately not
> implemented**, because the requirement changed mid-analysis: the auxiliary
> (third) socket must also work radio-to-radio, which makes it symmetric, and
> that changes its hardware rather than just its pin map. The "rev C" section
> below records what was settled and what the open decision is.
>
> **Nothing from rev C has been applied.** No netlist change, no regeneration,
> no `PINMAP.md` edit. Resume by reading the rev C section, then the auxiliary
> direction decision when it arrives.
>
> **Separately and more urgently: the BOM has six defective part numbers and
> one unbuildable part.** See "BOM defects" below. That applies to rev B as it
> stands today and must be fixed before anything is ordered, independently of
> rev C.

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

**A follow-up lookup is running** for the blocking items: an in-stock quad LVDS
driver (ideally pin-compatible with the DS90LV047A's SOIC-16 pinout, otherwise
its pinout so the symbol and footprint can be redrawn), the three header parts,
and a 470 R that JLCPCB stocks as a Basic part.

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

## rev C: specified, analysed, NOT implemented

The change requested was to make **every lane 307.2 Mbit/s DDR in both
directions** - the gateware's already-simulated 3-lane geometry - instead of
rev B's asymmetric six-lanes-out / three-lanes-back, and to spend the freed pins
on a third socket carrying a **fast bidirectional control channel** in place of
the 10-25 Mbit/s single-ended wire.

**What was settled and is worth keeping:**

* **The OUT and IN sockets keep the rev B symmetry mechanism unchanged**, so
  the two-radio case becomes the **full 921.6 Mbit/s raw stream each way**
  instead of rev B's 460.8. That is the main reason to do rev C at all.
* **The forward lanes move off PIN_80.** With pins freed, forward data becomes
  PIN_76, PIN_77 and PIN_83, so the 21 pF VREF pin no longer carries a fast
  forward lane. That removes the second-tightest path in rev B by itself.
* **PIN_72 and PIN_80 become inputs**, which is new in every revision.
  Confirmed permissible: `LINK_WIRING_VERIFICATION.md` 4b quotes the Cyclone IV
  handbook that a VREF pin may be a regular I/O when its bank carries no
  VREF-based standard, and HL2 bank 5 carries only `2.5 V`. The handbook adds
  only a qualitative warning - "reduced performance of toggle rate and tCO
  because of higher pin capacitance" - with **no numeric toggle-rate limit
  published anywhere**, so a calculation is the only guide that exists.
* **Both new inputs need the translator**, for the same reason as PIN_88/89:
  `LINK_WIRING_VERIFICATION.md` section 5 establishes that the PCI clamp is on
  by default and clamps toward VCCIO, so a 3.3 V receiver output held high
  against a 2.5 V bank injects DC into the HL2's 2.5 V rail through the clamp,
  into an LDO output through a ferrite. With a **mixed-direction** auxiliary
  socket this was free: PIN_88, PIN_89, PIN_72 and PIN_80 are exactly four
  channels, and the SN74AVC4T245 already on the board has exactly four.
* **Tang J14 allocation worked out with one pin spare** (pin 36, U17), against
  rev B's exact fit with none. The forward clock stays on pin 20 (U20,
  `SGCLKT_5` and `BPLL2/3 CLKIN0`, the PLL reference) and the auxiliary clock
  lands on pin 32 (Y18, `MGCLKT_4`), also clock-capable. **All six received
  pairs keep the A/T leg of a true differential pair**, so the future
  no-receiver-chip variant works for every one of them; rev B could not manage
  that for one lane.
* **Chip count for a mixed-direction auxiliary socket:** board A goes to two
  quad drivers plus two quad receivers (rev B had two plus one) and board B the
  same, so one extra package per board and no change to the translators.

**Margin at 307.2 Mbit/s** (unit interval 3.255 ns), which is the rate every
lane would run at:

| Path | rev B | rev C | Note |
|---|---|---|---|
| LVDS driver / receiver, 400 Mbit/s rating | 38 % forward, 77 % reverse | **77 % everywhere** | fine, and it is the rate the reverse lanes already needed |
| Forward lanes through the SN74AVC8T245, 380 Mbit/s rating | 40 % | **81 %** | **the one thing rev C makes worse.** Six channels instead of none at that utilisation. The eight bypass links remain the escape, at the price of the guaranteed voltage margin they were added to buy - the two escapes are mutually exclusive. |
| Reverse / auxiliary inputs through the SN74AVC4T245, 380 Mbit/s | 81 % on two channels | **81 % on three** | unchanged in kind |
| Receiver output into the HL2 LED pins | 51 % of UI in rise time | **51 %**, unchanged | still the tightest single-ended path |
| Forward lane on PIN_80 (21 pF) | 46 % of UI | **gone** - PIN_80 becomes a slow auxiliary input instead | a real improvement |
| PIN_80 as a 307.2 Mbit/s input, 27 pF total | - | **46 % of UI** (rise 1.49 ns), comfortable to about 135 Mbit/s | the new worst pin, deliberately on the least critical signal |
| PIN_72 as a 307.2 Mbit/s input, ~16 pF plus the uFL stub | - | **27 % of UI** (rise 0.88 ns) | fine; the CL8 stub is now driven by our receiver rather than the FPGA |
| Gowin per-lane delay adjustment | 3.2 ns over a 6.51 ns UI = **0.49 UI** | 3.2 ns over a 3.255 ns UI = **0.98 UI** | **better.** A sweep that spans a whole unit interval is guaranteed to contain an eye edge; at half a UI it was not. |

**Why it is blocked.** Making the auxiliary socket work radio-to-radio means it
must be symmetric, and a symmetric socket needs a driver **and** a receiver on
all four pairs, with the driver tri-stated while receiving, plus a
switchable-direction translation path and a direction signal. Consequences
already worked out:

* **No extra LVDS packages.** Four auxiliary driver channels plus four for the
  OUT socket is exactly two quad drivers; the same for receivers. The
  DS90LV047A's `EN`/`EN` pins tri-state its outputs, so a driver and a receiver
  can share connector pins, and the receiver's 100 ohm termination is what the
  driver wants to see anyway.
* **One extra translator package.** The 2.5 V-to-3.3 V direction fits exactly:
  four OUT channels plus four auxiliary channels is the eight the
  SN74AVC8T245 has. The 3.3 V-to-2.5 V direction does not: PIN_88, PIN_89 and
  four auxiliary pairs is six channels against the SN74AVC4T245's four, and its
  output must now tri-state when the HL2 drives the shared pin.
* **The direction signal is the real problem, and it is the decision to make.**
  The HL2 has no spare pin - all 14 are allocated. So the direction has to come
  from the auxiliary socket's unused SCL wire (which still needs an HL2 pin to
  drive it, and there is none), or be implicit in a half-duplex protocol with no
  wire at all, or the auxiliary socket drops from four symmetric pairs to fewer.
* **PIN_72 and PIN_80 get worse as bidirectional pins than as inputs**: PIN_80's
  21 pF now loads an HL2 output as well as a receiver output, and PIN_72's uFL
  stub is driven from both ends at different times.

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
