# gowin-bridge rev D — placing and routing with Quilter

One action per step. Do them in order.

Upload files: `quilter-upload/bridge.kicad_pro`, `quilter-upload/bridge.kicad_sch`,
`quilter-upload/bridge.kicad_pcb`. KiCad 10 format. Made from `bridge/` by
`kicad-cli pcb upgrade` and `sch upgrade`; regenerate them the same way after
any change.

---

## A. Upload

1. Open quilter.ai and start a new layout job.
2. Upload the three files above in one go. Do not zip them. Do not upload a folder.
3. On the preview page, confirm the parser reports no errors.
4. Confirm one board outline, 64.50 × 90.00 mm, with a notch at the top right, a small U-notch at the bottom left and one rectangular window.
5. Confirm these parts sit inside the board: J1, J2, J3, J4, J5, J101, J102, FID1, FID2, FID3 and the hole MB1. Quilter keeps them where they are.
6. Confirm the other 142 parts sit off the board to the right. Quilter places those.
7. Confirm five dotted placement regions: `REGION_RADIO`, `REGION_RADIO_HDR`, `REGION_RADIO_ESD`, `REGION_GOWIN`, `REGION_GOWIN_ESD`.
8. Confirm ten keepouts: `KEEPOUT_VSCORE_COPPER`, `KEEPOUT_J5_IDC_L`, `_R`, `_T`, `_B`, `KEEPOUT_UNDER_SMA`, `KEEPOUT_UNDER_KEYJACK`, `KEEPOUT_J14_POS1_4_VIAS`, `KEEPOUT_J14_POS1_4_BOTTOM`, `KEEPOUT_UNDER_DOCK_J9`.
9. If step 3, 4, 7 or 8 fails, stop and write down what the preview shows.

## B. Placement regions (Quilter needs the parts typed in)

10. `REGION_RADIO_ESD` — add: `D1, D2, D3, D4, D5, D6, D7, D8, D9, D10, D11, D12`
11. `REGION_RADIO_HDR` — add: `R1, R2, R3, R4, R5, R6, R11, R12, R13, R14, R15, R16, R18, R21, R22, R23, R24, R25, R26, R39, R40, R41, R42, R_CLKSEL_A, R_CLKSEL_B, U1, U2, U3, U6, U8, U9`
12. `REGION_RADIO` — add: `C1, C2, C3, C4, C5, C6, C7, C8, C9, C10, C11, C12, C13, C14, C15, C16, C17, C18, C19, C20, C21, C22, C23, C24, C25, C26, FB1, FB2, Q1, R7, R8, R9, R10, R17, R19, R20, R27, R28, R29, R30, R31, R32, R33, R34, R35, R36, R37, R38, R43, R44, R_DRVEN_ON, R_DRVEN_PRSNT, R_SHELL, SL_VLVDS, TP1, TP2, TP3, TP4, TP5, TP6, TP7, TP8, TP9, U4, U5, U7, U10, U11, U12`
13. `REGION_GOWIN_ESD` — add: `D101, D102, D103, D104, D105, D106, D107, D108, D109, D110, D111, D112`
14. `REGION_GOWIN` — add: `R101, R102, R103, R104, R105, R106, R107, R108, R109, R110, R111, R112, R113, R114, R115, R116, R117, TP101`
15. Confirm the five lists total 142 parts and every region is on the top layer. That is what keeps every part on the top side.

## C. Stackup and fabricator

16. Choose the stackup from the input files: 4 layers, 1.6 mm, In1 named `GND`, In2 named `PWR`.
17. If it is not offered, choose JLCPCB 4-layer 1.6 mm standard, and do step 58 later.
18. Set minimum trace width 0.15 mm.
19. Set minimum trace clearance 0.15 mm.
20. Set minimum drill 0.25 mm.
21. Set minimum annular ring 0.10 mm.
22. Set minimum edge-to-copper clearance 0.30 mm.

## D. Circuit comprehension

23. Differential pairs: confirm the radio end's 16 pairs, `A_*_P/N` and `B_*_P/N`.
24. Confirm the Gowin end's 16 pairs, `G_A_*_P/N` and `G_B_*_P/N`.
25. Add by hand any of the 32 that is missing. Write down which ones were missing.
26. Set every pair to 100 Ω differential, 50 Ω single-ended.
27. Set carrier frequency 0.31 GHz on every pair.
28. In the constraints step, override every pair to width 0.25 mm, gap 0.20 mm.
29. Power nets: `+3V3` 500 mA, power pour on.
30. `+2V5` 100 mA, power pour on.
31. `DB1_3V3` 500 mA, no pour.
32. `VLVDS` and `VLVDS_F` 100 mA, no pour.
33. Bypass capacitors: confirm each is on this pin, and fix any that is not:

| Cap | Pin | Cap | Pin | Cap | Pin |
|---|---|---|---|---|---|
| C1 | U1 pin 1 | C8 | U5 pin 4 | C15 | U10 pin 1 |
| C2 | U1 pin 16 | C9 | U6 pin 13 | C16 | U10 pin 16 |
| C3 | U2 pin 1 | C10 | U7 pin 13 | C17 | U11 pin 1 |
| C4 | U2 pin 16 | C11 | U8 pin 1 | C18 | U11 pin 16 |
| C5 | U3 pin 1 | C12 | U8 pin 16 | C19 | U12 pin 1 |
| C6 | U3 pin 16 | C13 | U9 pin 1 | C20 | U12 pin 5 |
| C7 | U4 pin 4 | C14 | U9 pin 16 | | |

34. Preserved pours: add `GND_PLANE_RADIO`.
35. Preserved pours: add `GND_PLANE_GOWIN`.
36. Proximity constraints: `D1` to `D12` each within 5 mm of `J1`.
37. Proximity constraints: `D101` to `D112` each within 5 mm of `J101`.
38. Proximity constraints: `R39, R40, R41, R42` each within 5 mm of `U6`.
39. Proximity constraints: `R37, R38, R43, R44` each within 5 mm of `U7`.
40. Proximity constraints: `R110` to `R116` each within 5 mm of `J102`.
41. Submit the job.

## E. When candidates come back

42. Download the best candidate into a new folder `bridge-quilter/`. Never over `bridge/`.
43. Copy `quilter-upload/bridge.kicad_sch` and `bridge.kicad_pro` into the same folder.
44. Run `python tools/check_geometry.py bridge-quilter/bridge.kicad_pcb`. It must end in `OK`.
45. In its output, confirm: locked parts at their documented positions.
46. Confirm: ESD arrays, worst gap 5 mm or less.
47. Confirm: terminations, worst gap 5 mm or less.
48. Confirm: decoupling, worst gap 3 mm or less.
49. Confirm: HL2 header nets, longest 25 mm or less.
50. Confirm: no pair net has track off the top layer, and nothing is routed on In1.
51. Confirm each length group spreads 2.5 mm or less: radio forward, radio reverse, radio aux out, radio aux in, and the four Gowin groups.
52. Run `python tools/check_netlist.py`. It must end in `OK`.
53. Run KiCad DRC on the returned board with schematic parity: `kicad-cli pcb drc --severity-error --schematic-parity --refill-zones bridge-quilter/bridge.kicad_pcb`.
54. Confirm 0 violations, 0 unconnected items, 0 parity issues.
55. Open the board in KiCad. Look at In2: confirm a `+2V5` area reaches U1 pin 1, U2 pin 1, U3 pin 16 and U12 pin 5.
56. Look at In1: confirm each end's ground plane is unbroken under the pairs.
57. Look at the score line: confirm no track, via or pour crosses it and no part is within 5 mm of it.
58. If step 17 was needed, confirm the downloaded board's stackup still reads 0.2104 / 1.065 / 0.2104 mm before ordering.
59. Anything that fails: write it down, loosen or fix the constraint, and resubmit with **Replace Files**.

## What Quilter cannot be told, so steps 44–57 check it

| Rule | Why it is a check |
|---|---|
| Pairs on the top layer only | Quilter cannot restrict a pair to a layer |
| Length matching within 2.5 mm per group | Quilter's timing and skew constraint is not released |
| ESD and terminations within 5 mm | only as in-app proximity constraints (steps 36–40), not from the file |
| HL2 header nets under 25 mm | no length limit for single-ended nets; the header region only makes it likely |
| Decoupling at the pin | detected from pin names; the schematic joins pins by labels, not wires |
| No copper across the score | a keepout in the file; Quilter documents keepouts but not score lines |
| No part within 5 mm of the score | the placement regions stop short of it; Quilter documents no score handling |
