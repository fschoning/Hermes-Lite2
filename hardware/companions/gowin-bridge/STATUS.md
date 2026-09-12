# gowin-bridge status (branch `gowin-bridge-pcb`, rev C)

Last updated 2026-09-12. Worktree `G:\proj\worktrees\Hermes-Lite2-gowin-bridge-pcb`.

**rev C is built.** All three KiCad projects — board A, board B and the
production panel — are generated, self-consistent and validated. rev B's
asymmetric link and rev A's dual-link DVI-D design are in git history.

| | |
|---|---|
| `hl2-bridge` | 177 parts (135 fitted), 98 nets. **ERC 0, DRC 0 violations, schematic/PCB parity 0.** |
| `tang-bridge` | 161 parts (121 fitted), 82 nets. **ERC 0, DRC 0 violations, parity 0.** |
| `panel` | 341 parts (256 fitted), 181 nets. **ERC 0, DRC 0 violations, parity 0.** |
| `tools/check_geometry.py` | **OK** on all three, including the panel's V-score and per-board containment checks |
| `tools/check_netlist.py` | **OK** — socket symmetry, all five cables, and the strap contention proof |

DRC reports only unconnected items (334, 302 and 499), which is the routing
that is deliberately left to be done in EasyEDA Pro.

**What is NOT done: the routing, and the four physical measurements.** Neither
can be done from here. They are listed under "Next steps".

---

## What rev C is

Three HDMI cables. **Every lane DDR at 153.6 MHz = 307.2 Mbit/s, in both
directions**, 3 lanes each way, so each direction carries the complete
921.6 Mbit/s = 12 bits x 76.8 MSPS ADC stream. The third cable is a
**bidirectional, full-duplex, differential auxiliary channel** whose direction
is set by a board strap, which is what makes one board design work at either
end of any cable.

rev B's asymmetry bought nothing: both directions carried the same
921.6 Mbit/s and the reverse direction needed 307.2 Mbit/s per lane anyway, so
deferring that rate to one direction hid the risk instead of removing it.

---

## Done and validated

| Item | State |
|---|---|
| `PINMAP.md` rev C | Complete and authoritative. Every signal, both HL2 headers, all 15 used Tang J14 pins with ball and Gowin IO name, the strap, the direct-LVDS table, and paste-ready `IO_LOC` / `IO_PORT` and Quartus constraint blocks. Corrected during this pass: the panel size (94 x 100, not 94 x 90), which socket's SCL feeds Tang J14 pin 19, and board B's strap-gated buffer. |
| **The ROLE strap** | One 1x3 header with ONE shunt plus one single-gate inverter, on both boards. `ROLE_N` carries a **10 k pull-UP** so a missing or dead inverter *disables* a host-facing port rather than enabling one; `ROLE` carries a 100 k pull-down so "no shunt" is a defined state and never a floating CMOS input. The single-gate inverter is **LCSC C7827**, TI SN74LVC1G04DBVR, SOT-23-5, 150,495 in stock, in JLCPCB's library as an **Extended** part. There is no Basic-tier 74LVC1G04 in SOT-23-5 from any of the ten manufacturers JLCPCB lists, so the ~$3 unique-Extended-part fee is unavoidable for this one chip. |
| **The contention proof** | `check_netlist.py` now asserts the invariant that makes the design safe: **for each auxiliary group, the LVDS driver's active-HIGH enable and the host-facing buffer port's active-LOW OE are the SAME NET.** A group is therefore either driven onto the cable or driven toward the host, never both, for any level on that net including a stuck one. The checker enumerates both strap states on both boards and prints the result. |
| Chip complement | Board A carries **10 fitted ICs** (was 7 in rev B): three LVDS drivers (`OUT` always on, auxiliary G1 gated by `ROLE`, G2 by `ROLE_N`), two receivers, one 8-bit and two 4-bit translators, a 2.5 V LDO and the inverter — plus a not-fitted 3.3 V LDO. Board B carries **8**: two receivers, three drivers, one strap-gated buffer, an LDO and the inverter. |
| **The panel** | A third KiCad project, generated from the same part lists so it cannot drift. 94.00 x 100.00 mm, two designs, board B rotated 90 degrees. Three V-scores at y = 5, y = 95 and x = 48, each edge to edge with material on both sides for its whole length — asserted arithmetically by the checker, not by eye. One routed separation with mouse bites at y = 29, four tabs, 16 perforations of 0.50 mm confirmed by reading the Excellon export back. 5 mm assembly rails, a 48 x 22 mm fiducial coupon, three fiducials. |
| Connector selection | Both are real, stocked LCSC parts with datasheet land patterns. Board A: XKB A71-05H4-111N1 mini HDMI Type C, **C2682170**, hybrid mount, 2,217 in stock. Board B: Amphenol ICC 10029449-111RLF, **C427307**, 3,324 in stock, 10,000 mating cycles. |
| Board A footprint | Generated from the XKB recommended-layout drawing, the only mini HDMI drawing found that dimensions its pattern relative to the PCB edge. |
| Board B footprint | Stock KiCad `HDMI_A_Amphenol_10029449-x01xLF_Horizontal`, used unchanged after re-checking every value against Amphenol drawing 10029449 rev Y sheet 3. |
| Board A socket geometry | **Verified three times.** `check_geometry.py` recomputes the DB1/DB12 hole grid independently from `hermeslite.kicad_pcb` and confirms all 26 holes on the standalone board; it now confirms them again after the panel transform; and the Excellon export was read back and agrees, **including the bottom-side x-mirroring trap**. |
| Mechanical arithmetic | Three mini HDMI sockets fit the 48 mm corridor with room to spare (11.20 mm bodies, 6.20 mm between them, 0.55 mm copper to the board edge). Board A is a plain rectangle entirely inside the corridor the N2ADR filter board leaves free. Height 15.74 mm, so stacking a DB1 companion works. |
| 2.5 V threshold | Resolved and justified: one SN74AVC8T245 in front of all eight signals that feed an LVDS driver input gives 370 mV of guaranteed margin instead of 0 mV, with the `OUT` clock brought into the same package through a **100 R / 660 R divider** so clock and data share one propagation delay. Eight bypass links are fitted for the unguaranteed direct-connection fallback. |
| AC-coupling option | Present on the four **received** `IN` pairs on each board, selectable by 0 R links, defaulting to DC-coupled, with a new **10 k / 4k7** `VBIAS` divider giving 1.055 V. Deliberately **not** offered on the auxiliary pairs: a series capacitor on a bidirectional pair leaves the far end's common mode undefined, and a series link on a driven pair is an impedance discontinuity. |
| Strap-selected termination | Four 100 R differential termination positions on the auxiliary pairs, of which two are fitted — the two the board receives in its shipped role. Board A ships ROLE A and terminates the D1 and D2 pairs; board B ships ROLE B and terminates the CLK and D0 pairs. |
| 1:1 print templates | Regenerated for both boards and **added for the panel**: a top and a mirrored-bottom PDF each, with a 50 mm calibration rule on `Dwgs.User` so a scaled print is detectable. |
| **The BOM is now buyable** | Every LCSC number was checked against the live catalogue. Six numbers in rev B were wrong, non-existent or unbuyable and four more pointed at a different value or package than the BOM claimed. All are fixed. See "BOM defects found and fixed". |
| Cost | Priced end to end for **2 and 3 assembled panels** in `README.md` section 8: **$199.70** and **$251.45** respectively, all in, including shipping to Germany and the two hand-soldered sockets. |
| Generator and checkers | `tools/gen_gowin_bridge.py` produces schematic, PCB, libraries and BOM for all three projects from one netlist description. `check_geometry.py` verifies placement, the HL2 hole grid and the whole panel layout; `check_netlist.py` asserts the header pin maps, walks all five cables, and proves the strap cannot produce contention. |
| KiCad toolchain | KiCad **10.0.6** at `C:\Users\franz\AppData\Local\Programs\KiCad\10.0`. `kicad-cli.exe` produced every ERC, DRC, drill and PDF result quoted here. Files are written in KiCad 8 format. |

---

## Two defects found in the written specification, and fixed

Both were found by building the design rather than reading it, and both are
reported here with the numbers rather than quietly worked around.

### 1. Board B had no way to tri-state its auxiliary receive path

The rev C write-up gave board B two LVDS receivers, no translator, and an
**always-on 4-channel auxiliary receiver**, on the reasoning that "the
receivers never need disabling for direction — it is the translator output that
must tri-state."

**That reasoning is board A's.** Board A tri-states its auxiliary receive path
inside the level translator it needs anyway for the HL2's 2.5 V bank pins.
Board B has no level shifting to do, so it had nothing to tri-state in. Its
always-on receiver's outputs for the group it *drives* would then land on the
two Gowin pins the gateware drives as outputs in that role — **CMOS against
CMOS, tens of milliamps, which is exactly the failure `PINMAP.md` 2.4 exists to
prevent.**

Board B therefore carries **one SN74AVC4T245PWR (C81461, $0.3096 at qty 10)
with both rails tied to 3.3 V**, used purely as two independently gated
2-channel buffers: port 1 = auxiliary G1 toward the Gowin, enabled by `ROLE`;
port 2 = G2 toward the Gowin, enabled by `ROLE_N`. It adds **no new unique
part**, because board A already carries two of them. A 74LVC125A quad buffer
with four independent enables would do the same job in one smaller, cheaper
package but would have added a unique part to the panel, so it was not taken.

The invariant is now identical on both boards, which is what let the checker be
written once.

### 2. The 10 uF bulk capacitor was the wrong package and the wrong voltage

`C15525` was in the BOM as "10uF 0805". It is not: it is Samsung
CL05A106MQ5NUNC, 10 uF **6.3 V** X5R in **0402**. That is the wrong package for
the 0805 pads it had been assigned, and 6.3 V would have lost most of its
capacitance to DC bias on the two 5 V input bulk positions.

Replaced by **C15850**, Samsung CL21A106KAYNNNE, 10 uF **25 V** X5R **0805**,
confirmed **Basic** in JLCPCB's library, 2,760,420 in stock, $0.085 at its
minimum order quantity of 20.

---

## BOM defects found and fixed

A live LCSC and JLCPCB price check found that **six part numbers in the rev B
BOM were wrong or unbuyable**, and four more pointed at a real part that was
not the value or package the BOM claimed. Every one is now resolved with a
number that was read off a live page.

| Line | rev B had | rev C has | Why |
|---|---|---|---|
| Quad LVDS driver | `C201946` | **`C206491`** DS90LV047A**TMX**/NOPB | `C201946` has zero stock at LCSC and is absent from JLCPCB's library. `C206491` is the same TI silicon and the same pinout under the tape-and-reel suffix, so nothing was redrawn. $1.8396 at qty 10, 1,312 in stock, Extended. |
| 8-bit translator | `C53535` | **`C465742`** | `C53535` does not exist. $0.9296, 16,677 in stock. |
| 2x20 female header (Tang J14) | `C50982` | **`C5124634`** BOOMELE 2.54 2x20P vertical | `C50982` exists but has zero stock and is not in JLCPCB's library. $0.3305, 11,945 in stock. |
| 2x10 female header (HL2 DB1) | `C5361769` | **`C42431860`** JXTCONN PM2.54-2X10P-H85 | `C5361769` does not exist. And LCSC stocks **no long-tail 2x10 socket at all**, so the stack-through feature is sourced outside LCSC and `C42431860` is the fallback ordinary socket. $0.1921, 3,405 in stock. |
| 470 R 0402 | `C25117` | **330 R `C25104`** | `C25117` is real but not in JLCPCB's library. 330 R is a **Basic** part with 742,400 in stock, so the clock divider was recomputed around it. |
| 10 uF bulk | `C15525` | **`C15850`** | Wrong package and wrong voltage; see above. |
| 2x3 female header (HL2 DB12) | `C124413` | **hand-soldered, no LCSC line** | `C124413` ships as a 1x4 single-row socket. LCSC has no vertical 2x3 female socket at all — theirs start at 2x4, and the 2x3 they list (`C99515`) is side entry, which cannot work on a socket that plugs straight down. |
| **0 ohm jumper in 0805** | `C17168` | **`C17477`** UNI-ROYAL 0805W8F0000T5E | Found during this pass. `C17168` is a 0 ohm **0402**; the six socket-shell links are 0805, so it was the wrong part on those pads. `C17477` is 2 A rated, 6,045,800 in stock, and the only **Basic** 0805 zero-ohm jumper in JLCPCB's library. |
| **1x3 and 1x2 pin headers** | `C2337` | **`C52016391`** and **`C52016390`** | Found during this pass. `C2337` is a 1x**40** strip, and JLCPCB's BOM matcher will not accept a 40-pin part against a 3-pin footprint. Both replacements are hanxia PH254 series, through-hole, straight. Both are **Extended**: no Basic 2.54 mm through-hole 1x2 or 1x3 vertical header exists in JLCPCB's library at all. |

Four further rev B numbers pointed at the wrong thing: `C21190` is 0603 not
0402, `C25746` is **113 k not 150 R**, `C25867` is **1.5 k not 1k8**, and
`C1555` is **22 pF not 33 pF**. The design was reworked so none of those values
is needed, using only values whose numbers were confirmed.

**The whole passive set is now eleven values, all confirmed JLCPCB Basic
parts:** 0R, 22R, 100R, 330R, 4k7, 10k, 100k, 22pF, 100nF, 1uF and 10uF 25V
0805.

### The numbers the divider rework produced

| | |
|---|---|
| `OUT` clock divider | **100 R series + 660 R shunt** (two 330 R in series) |
| High level at the translator A input | 3.3 x 660 / (660 + 100 + 25) = **2.77 V** |
| Margin over the 1.63 V threshold | **1.14 V** |
| Headroom under the 3.0 V absolute maximum | **230 mV** |
| Current from PIN_98 | **4.2 mA**, inside its 8 mA drive setting (100 R / 330 R would have drawn 7.25 mA and forced the pin to 16 mA) |
| Thevenin impedance | **87 ohm** |
| Edge contribution into the translator's ~4 pF | **0.77 ns** |
| Low level with the HL2 FPGA unconfigured | (3.3 - 1.7) x 660 / (1000 + 100 + 660) = **0.60 V**, under the 0.875 V limit |
| `VBIAS` divider (AC-coupling option only) | **10 k / 4k7**, giving 3.3 x 4.7 / 14.7 = **1.055 V**, mid-range for the receiver's 0.05 - 2.35 V input common mode |
| HPD pull-down | **100 R**, against the far end's 10 k, giving a detect level of **0.033 V** at 0.33 mA of idle current |
| Slow-line ringing damper | **22 pF**, not fitted. 22 pF into 100 R is 2.2 ns |

---

## The auxiliary rate decision, and the optimisation deliberately not taken

**The gateware should clock the auxiliary lanes at a divided rate — 38.4 MHz
DDR = 76.8 Mbit/s per lane is the suggested starting point — not at 153.6 MHz
DDR.**

The reason is PIN_72. The auxiliary G2 return clock arrives on an ordinary I/O,
not a dedicated clock input, because both of the HL2's dedicated clock inputs
are spent: PIN_88 on the reverse link and PIN_89 on the strap read. A regular
I/O can drive the Cyclone IV global clock network but **cannot feed a PLL
input**, so the sampling phase cannot be adjusted. At 76.8 Mbit/s the unit
interval is **13.02 ns**, so PIN_80's 1.49 ns edge and whatever static phase
error the cable and the clock network contribute are a small fraction of it and
no adjustment is needed. At 307.2 Mbit/s the unit interval is **3.2552 ns** and
the sampling phase would have to be right by luck.

**The hardware is capable of 307.2 Mbit/s each way** and nothing on the board
limits it to less. This is a gateware choice that can be revisited once the
real phase is measured. A control channel needs kilobits, so 76.8 Mbit/s is
already four orders of magnitude more than the job requires.

**One optimisation was considered and deliberately rejected.** The two
auxiliary clock lanes could be reclaimed by timing the auxiliary data off cable
1's or cable 2's clock instead, doubling the auxiliary payload. It was not done
because the inter-cable phase is unknown and it would add risk for bandwidth
that is not needed. It is recorded here as a possible future **gateware-only**
optimisation — it needs no board change — so that whoever wants it later knows
it was rejected on risk rather than overlooked.

---

## Everything unverified

`DESIGN_NOTES.md` has the full list with the section that discusses each. The
ones that could stop the build:

| Item | Why it matters | How to settle it |
|---|---|---|
| **Mini HDMI pin-1 end** | **The highest-risk item on the board.** The XKB drawing labels pin 1 on its front view but not on its land-pattern view. The footprint assumes **pin 1 at the +x end**. Getting it wrong makes the board scrap. | Buy one connector and look, or get the SOFNG drawing (LCSC C136421), which does label its land pattern. Then set `MINI_HDMI['pin1_at_plus_x'] = False` and regenerate if it is wrong. |
| **Mini HDMI cable boot width** | The one thing that could still stop three cables plugging in at once. Estimates run 15.6 to 17.3 mm against **17.40 mm of pitch**, so it fits either way, but the pessimistic case leaves 0.08 mm. | Buy one cable and measure the boot with calipers. The two-radio configuration uses only the outer two sockets, 34.80 mm apart, so it is never affected. |
| **Board B's position on the Tang dock** | No dock board file, drawing or 3D model was obtained. Which end of J14 is pin 1 is also unconfirmed. | Print `templates/tang-bridge-1to1-TOP-fit-check.pdf` at 100 %, measure its 50 mm rule, offer it up. Then change `board_b()`'s J14 position and regenerate. |
| **HL2 +3V3 spare current** | rev B estimated board A at ~112 mA. Board A now carries **three more ICs**, so that figure needs recomputing and then measuring. The HL2's regulator was never identified in `Power.sch`. | Recompute from the datasheets, then measure the HL2's 3.3 V rail with board A plugged in. |
| **Whether JLCPCB accepts this panel** | Their Economic assembly service states a panelisation rule of **mouse-bite separations only**; Standard allows mouse-bite or V-cut. This panel mixes three V-scores with one mouse-bite separation. | Ask the fab before paying. The fallback is two separate orders at roughly $40 more, which `README.md` section 7 documents. |
| **PIN_80's edge rate** | 1.49 ns is a calculation, not a datasheet guarantee. The Cyclone IV handbook permits a VREF pin as a regular I/O when its bank carries no VREF-based standard and warns only qualitatively of "reduced performance of toggle rate and tCO", with no numeric limit published anywhere. | Scope it. It sets the real ceiling on the auxiliary channel. |
| **The uFL stub on PIN_72** | The auxiliary G2 clock net also lands on uFL pad CL8 on the HL2, an unterminated stub no bridge board can remove. In ROLE B the HL2 drives a 153.6 MHz clock out through it, which is the worst case of the four auxiliary pins. HL2 jumper **J25 must be closed** or that lane is dead entirely. | If only the G2 direction misbehaves at speed, this is the first suspect. Board A's cuttable link `SL_D0` isolates board A from the net but does not remove the stub. |
| **The 0.10 mm body overhang at the panel's x = 94 edge** | Board B's Type A connector bodies reach 0.10 mm past the outer panel edge. No copper is outside the outline, so DRC is clean. | Confirm with the fab. |
| **The exact assembly fee** | JLCPCB will not compute the solder-joint fee without a login and an uploaded position file. The per-joint rates are from their published schedule and the joint counts (789 SMT, 89 through-hole per panel) were counted from the board files here. | It is about $5 out of $195, so it does not change the decision. |
| **Shipping for the two hand-soldered sockets** | Not checked from Mouser or from Phoenix Enterprises to Germany. | Check at the point of ordering. |
| **The auxiliary channel's real rate** | 76.8 Mbit/s is a reasoned starting point, not a measurement. | Bench-measure before the gateware relies on a number. |

---

## Next steps, in order

1. `cd G:\proj\worktrees\Hermes-Lite2-gowin-bridge-pcb\hardware\companions\gowin-bridge`
2. `python tools/gen_gowin_bridge.py`, then `python tools/check_geometry.py`
   and `python tools/check_netlist.py`. Both must print `OK`. Nothing below
   should start until they do.
3. **Print `templates/hl2-bridge-1to1-TOP-fit-check.pdf` and
   `templates/tang-bridge-1to1-TOP-fit-check.pdf` at 100 %**, measure the 50 mm
   rule, and offer them up to the HL2 and to the Tang dock. Fix anything that
   does not line up **in the generator**, not in the KiCad files.
4. **Buy one mini HDMI cable and measure its boot with calipers.** If it is
   over 17.40 mm wide, decide what to do before any layout work.
5. **Settle the mini HDMI pin-1 end.** Buy one connector, or get the SOFNG
   drawing (LCSC C136421).
6. **Ask JLCPCB whether they will accept a panel that mixes V-scores with one
   mouse-bite separation** for the assembly service you intend to use.
7. Route the panel in EasyEDA Pro following `ROUTING.md`. Do the three mini
   HDMI fan-outs first, then the four auxiliary pairs — those are the ones
   where a driver output and a receiver input meet at one node and the stubs
   have to be short. Everything else has room.
8. Order. `README.md` section 7, and remember that the order form's **"Different
   designs in this file" field must be set to 2**.
9. Bring-up order: check the 3.3 V rail; scope `TP_HL2_CLK` (the divided `OUT`
   clock) and `TP_DRVI_O_CLK` (the translator output into the driver); read
   `TP_ROLE` and `TP_ROLE_N` and confirm they are complementary; run the
   Gowin's delay sweep; then the reverse link; then the auxiliary link.
   `ROUTING.md` has the fault-finding table.

**Anything that changes a net must be changed in `tools/gen_gowin_bridge.py`
and regenerated, never hand-edited in the KiCad files, and `PINMAP.md` must be
updated in the same commit.**

---

## The FPGA side has to change to match

`gateware/variants/hl2b5up_gowinlink/gowinlink_pins.tcl` on branch
`gowin-link` (worktree `G:\proj\worktrees\Hermes-Lite2-gowin-link`) is marked
PROVISIONAL. `PINMAP.md` section 4.5 is the paste-ready Quartus block and
section 5.2 the paste-ready Gowin `.cst` block. What changes:

* **The forward link moves to 3 lanes at 307.2 Mbit/s** on PIN_76, 77 and 83
  with the clock on PIN_98 — the `GL_LANES = 3` geometry the gateware has
  already simulated, on new pins. The 6-lane geometry is gone.
* **The reverse link is unchanged in shape** — PIN_99, 100, 101 with the clock
  on PIN_88 — but every lane is now 307.2 Mbit/s.
* **PIN_89 becomes the ROLE strap read**, an input. It was the slow command
  input in rev B. `gl_role` HIGH = ROLE A.
* **PIN_72, 80, 85 and 87 become four BIDIRECTIONAL auxiliary pins**, and
  PIN_72 and PIN_80 are used as inputs for the first time in any revision.
  **The gateware MUST set all four directions from the strap it reads on
  PIN_89.** That is what makes a wrongly set strap harmless, and it is the one
  part of the safety argument the hardware cannot enforce on its own.
* **The auxiliary G2 clock on PIN_72 must go to a global clock network, not to
  a PLL input**, which a regular I/O cannot feed.
* On the Gowin side, `link_slow_in` on J14 pin 19 (ball V20) **must** be
  `IO_TYPE=LVTTL33`, not `LVCMOS33`: it is driven by an HL2 2.5 V output down
  an unshielded wire, and LVCMOS33's 2.0 V threshold would leave zero
  guaranteed margin where LVTTL33's 1.7 V leaves 300 mV.
* **DB12 pins 5 and 6:** the tcl's comment block already had these the right
  way round (PIN_88 = DB12 pin 6, PIN_89 = DB12 pin 5). rev A of `PINMAP.md`
  did not. Do not "fix" it to match rev A.

---

## Validation commands used

```
set KC=C:\Users\franz\AppData\Local\Programs\KiCad\10.0\bin\kicad-cli.exe

python tools/gen_gowin_bridge.py
python tools/check_geometry.py
python tools/check_netlist.py

%KC% sch erc --severity-error -o panel/panel-erc.rpt panel/panel.kicad_sch
%KC% pcb drc --severity-error --schematic-parity --refill-zones ^
     -o panel/panel-drc.rpt panel/panel.kicad_pcb

%KC% pcb export drill --format excellon --drill-origin absolute ^
     --excellon-units mm --excellon-separate-th -o drl/ panel/panel.kicad_pcb

%KC% pcb export pdf --mode-single --scale 1 --black-and-white --drill-shape-opt 2 ^
     --exclude-value --layers "Edge.Cuts,Eco1.User,Dwgs.User,F.SilkS,F.Cu,F.Fab" ^
     -o templates/panel-1to1-TOP-fit-check.pdf panel/panel.kicad_pcb
```

Results at the time of writing, for all three projects: **ERC 0 violations,
DRC 0 violations, schematic/PCB parity 0 issues, both checkers OK.** The drill
read-back confirms every DB1, DB12, shell-leg and locating-peg hole, and all
16 mouse-bite perforations at 0.50 mm on the y = 29 break line.
