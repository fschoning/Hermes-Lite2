# gowin-bridge status (branch `gowin-bridge-pcb`)

Last updated 2026-09-12. Worktree `G:\proj\worktrees\Hermes-Lite2-gowin-bridge-pcb`.

## Done and validated

| Item | State |
|---|---|
| `PINMAP.md` | Complete. Every wire of both cables, both HL2 headers, all 16 used Tang J14 pins with ball and Gowin IO name, the direct-LVDS bypass table, and ready-to-paste Gowin `IO_LOC`/`IO_PORT` constraints. Committed first so the FPGA worker can read it. |
| `hl2-bridge` schematic | **Complete. Loads in KiCad, ERC 0 errors.** 118 parts, 86 nets. Every part carries `LCSC`, `MFR`, `Note` and `Description` properties. |
| `tang-bridge` schematic | **Complete. Loads in KiCad, ERC 0 errors.** 118 parts, 79 nets. |
| Both `.kicad_pcb` | Board outline, 4-layer stackup (signal / GND / power / signal), net list, all footprints placed, ground and power zones. **Schematic/PCB parity: 0 issues on both boards.** No tracks: routing is left to the user. |
| Project-local libraries | `gowin-bridge.kicad_sym` and `gowin-bridge.pretty/` in each project folder, so neither project depends on the user's KiCad library version. |
| BOM | `<board>-bom.csv` per board, one line per part, with LCSC numbers, populate/DNP flag, function and note. |
| Generator | `tools/gen_gowin_bridge.py` + `tools/kisexp.py`. One netlist description produces schematic, PCB and BOM, so they cannot drift. Re-run with `python tools/gen_gowin_bridge.py`. |
| Verified pinouts | DS90LV047A from TI SNLS044D, DS90LV048A from TI SNLS045C (pin-function tables read from the datasheet PDFs). All other symbols and land patterns come from the stock KiCad libraries. |
| KiCad toolchain | `winget install KiCad.KiCad` succeeded without admin and installed **KiCad 10.0.6** at `C:\Users\franz\AppData\Local\Programs\KiCad\10.0`. `kicad-cli.exe` works and was used for every ERC/DRC run quoted here. Files are written in KiCad 8 format (`version 20231120` / `20240108`). |

## Partial / not done

| Item | State | Why |
|---|---|---|
| PCB routing | **Not done.** No tracks on either board. | By decision: the user will route in JLCPCB's EasyEDA Pro editor. DRC therefore still reports ~220 unconnected items per board plus zone/pad overlaps that disappear once zones are set up for a routed board. |
| Gerber / CPL export | Not done. | Needs a routed board. Steps are in `README.md`. |
| DVI receptacle sourcing | **Unverified.** No DVI-D receptacle was found in the LCSC catalogue by search. The footprint used is the stock KiCad `DVI-D_Molex_74320-4004_Horizontal` (right-angle, through-hole, with a Molex drawing link), which is a real and verified land pattern. | LCSC search pages would not render for the tool. Assume the user hand-solders the two DVI sockets per board. |
| Mechanical fit of board A in the standard enclosure | **Proven impossible for two right-angle DVI sockets.** See `DESIGN_NOTES.md` section 6 for the numbers. Board A is 80 x 66 mm with a 48 x 66 mm arm inside the filter-board corridor and a 32 x 19 mm tab that overhangs it. | Two DVI-D sockets are 37.8 mm wide each; the N2ADR filter board leaves a 48 mm corridor. |
| Board B mechanical position on the dock | **"User must verify by measurement."** No Tang dock board file or mechanical drawing was obtained. | The Sipeed download tree was not reachable in the time available. `tang-bridge` places its J14 socket at local (6.0, 8.0) for pin 1; the user must check that against the real dock. A 1:1 print template was not produced. |
| Cost estimate for 2 and 5 sets | Not written up. | Per-line LCSC numbers are in the BOMs; the totals still have to be added. |

## Exact next steps to resume

1. `cd G:\proj\worktrees\Hermes-Lite2-gowin-bridge-pcb\hardware\companions\gowin-bridge`
2. Open `hl2-bridge/hl2-bridge.kicad_pro` in KiCad 8/10, or import the schematic into EasyEDA Pro (`README.md` section 3).
3. Route board A. Use the layout guide in `DESIGN_NOTES.md` section 7: 100 ohm differential pairs on the outer layers over the layer-2 ground plane, 0.2 mm trace / 0.13 mm gap, intra-pair length match 0.2 mm, terminations within 5 mm of the receiver pins.
4. Confirm the two DVI receptacle part numbers with the supplier and, if the part differs from Molex 74320-4004, replace `gowin-bridge.pretty/DVI-D_Molex_74320-4004_Horizontal.kicad_mod` with the vendor land pattern.
5. Measure the Tang dock: distance from the J14 hole row to the board edge and to the PMOD sockets, then adjust `board_b()`'s J14 socket position in `tools/gen_gowin_bridge.py` and re-run the generator.
6. Add the BOM cost totals for 2 and 5 sets.
7. Anything that changes a net must be changed in `tools/gen_gowin_bridge.py` and regenerated, not hand-edited in the KiCad files, and `PINMAP.md` must be updated in the same commit.

## Validation commands used

```
set KC=C:\Users\franz\AppData\Local\Programs\KiCad\10.0\bin\kicad-cli.exe
%KC% sch erc --severity-error -o hl2-bridge/erc.rpt  hl2-bridge/hl2-bridge.kicad_sch
%KC% pcb drc --severity-error --schematic-parity --refill-zones ^
     -o hl2-bridge/drc.rpt hl2-bridge/hl2-bridge.kicad_pcb
```
