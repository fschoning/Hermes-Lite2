# gowinlink — work-in-progress status (branch gowin-link)

Updated: 2026-09-12 13:30 (session may be cut off; resume from here).

## Done and verified
- Spec: `gateware/gowinlink/LINK_SPEC.md` (final geometry: 6-lane 76.8 MHz DDR forward + forwarded
  clock; 3-lane 153.6 MHz DDR reverse with Gowin-forwarded 90-degree clock; fast serial
  Gowin->HL2 carrying commands; status UART HL2->Gowin; 3-lane forward fallback).
- RTL, both sides, written and compiling under Icarus: `gateware/rtl/gowinlink/*.v` (shared +
  HL2), `gowin/rtl/*.v` (Gowin).
- `gowin/sim/tb_uart.v`: PASS (UART, CRC-8 framer, fast serial incl. corrupted packet).
- `gowin/sim/tb_rev.v`: PASS (reverse chain: alignment, verification, PRBS, counter).
- Gowin synthesis (gw_sh) of gl_top LANES=6 passes; place & route was blocked only by the
  `.cst` attribute `HYSTERESIS=NONE` (illegal in 1.9.11.03; `OFF` is accepted — fixed, rerun pending).
- Quartus 20.1.1 now has Cyclone IV E device support; variant `gateware/variants/hl2b5up_gowinlink`
  created (hermeslite.v, qsf, pins tcl, sdc); `hermeslite_core.v` integrated (GOWINLINK parameter).

## Failing / unverified right now
- `gowin/sim/tb_link.v` (full link, LANES=6): first run failed because the ALIGN pattern word
  counter advanced mid-word for 2-cycle words (fixed in gowinlink_tx_lanes.v, verified by tb_rev)
  and because the Ethernet scoreboard queue overflowed after 1024 commands (fixed). A rerun
  was in progress (about 10 minutes of wall time). Run: `cd gowin/sim && ./run_sim.sh link 6`.
- LANES=3 full-link run not yet executed: `./run_sim.sh link 3`.
- Gowin P&R + timing not yet seen: `cd gowin/proj && gw_sh build.tcl` (check impl/pnr/*.tr).
- Quartus build of the variant was started (`quartus_sh --flow compile` in the variant dir,
  log `quartus_build.log`); first attempt failed on `set` in the .qsf (fixed); result of the
  second attempt unknown. Expect port/name errors in hermeslite_core.v integration or SDC
  names (`timing_gowinlink.sdc` uses instance names that must match the fitter's).

## Next steps
1. Read tb_link_6 result (`gowin/sim/build/tb_link_6.log`), fix, then run LANES=3.
2. Gowin: `gw_sh build.tcl`, read `impl/pnr/gowinlink.tr` for violations; fix; then `build.tcl 3`.
3. Quartus: read `quartus_build.log`; fix compile errors; check timing (output_files/*.sta.rpt);
   confirm the .rbf is produced; report Fmax/slack numbers.
4. Update pins when `hardware/companions/gowin-bridge/PINMAP.md` appears.
