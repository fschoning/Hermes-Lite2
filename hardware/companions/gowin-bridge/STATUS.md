# gowin-bridge status (branch `gowin-bridge-pcb`, rev B)

Last updated 2026-09-12. Worktree `G:\proj\worktrees\Hermes-Lite2-gowin-bridge-pcb`.

rev B replaced rev A's two dual-link DVI-D sockets per board with three HDMI
sockets per board, and made the HL2-side board symmetric so two radios can
link to each other with the same board. The rev A design is in git history.

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
| Generator and checker | `tools/gen_gowin_bridge.py` produces schematic, PCB, libraries and BOM for both boards from one netlist description, so they cannot drift. `tools/check_geometry.py` is new and verifies the result. Two latent bugs in `tools/kisexp.py` fixed along the way: oval drills emitted the word "oval" where a number belonged, and a courtyard circle measured as zero-height, which silently collapsed the placer. |
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

## Exact next steps to resume

1. `cd G:\proj\worktrees\Hermes-Lite2-gowin-bridge-pcb\hardware\companions\gowin-bridge`
2. `python tools/gen_gowin_bridge.py && python tools/check_geometry.py` — both
   boards must print `OK`. Nothing below should start until they do.
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
