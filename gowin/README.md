# Tang Mega 138K side of the HL2 <-> Gowin link

Specification: `gateware/gowinlink/LINK_SPEC.md`. HL2 side: `gateware/rtl/gowinlink/` and the
Quartus variant `gateware/variants/hl2b5up_gowinlink/`.

## Layout

| Path | Content |
|---|---|
| `rtl/` | Gowin-only RTL (`gl_top.v` is the top; `gl_top_l3.v` the 3-lane fallback wrapper). Shared modules live in `../gateware/rtl/gowinlink/`. |
| `proj/` | `build.tcl` for `gw_sh`, `gowinlink.cst` (pins — the only file with pin locations), `gowinlink.sdc`, and the `_l3` pair for the 3-lane fallback |
| `sim/` | Icarus testbenches and `run_sim.sh` |
| `tools/gen_console_fmt.py` | generates `rtl/gl_console_fmt.vh` and `rtl/gl_console_fields.vh` (console line layout) |

Build products (`proj/impl/`, `sim/build/`) are ignored by git.

## Build (Gowin EDA 1.9.11.03 Education, command line)

```
cd gowin/proj
C:\Gowin\Gowin_V1.9.11.03_Education\Gowin_V1.9.11.03_Education_x64\IDE\bin\gw_sh.exe build.tcl      # 6 lanes (default)
C:\Gowin\...\gw_sh.exe build.tcl 3                                                                  # 3-lane fallback
```

Results: `impl/pnr/gowinlink.fs` (bitstream), `impl/pnr/gowinlink.tr.html` / `.tr` (timing
report), `impl/pnr/gowinlink.rpt.html` (place and route, resource usage). Program the board
with the Gowin Programmer or `openFPGALoader -b tangmega138k impl/pnr/gowinlink.fs`.

Pins are provisional until `hardware/companions/gowin-bridge/PINMAP.md` is published; edit
`proj/gowinlink.cst` (and `_l3`) to match. The `.cst` has a commented block for true-LVDS
forward inputs (Bank 4 on-die termination) instead of the default 3.3 V CMOS.

## Simulate (Icarus Verilog from oss-cad-suite)

```
cd gowin/sim
./run_sim.sh            # tb_uart, tb_rev, tb_link LANES=6, tb_link LANES=3
./run_sim.sh link 6     # one full-link run (about 10 minutes)
```

Each testbench prints `PASS` or `FAIL: n errors`. `tb_link` also echoes the Gowin console
lines. Paths to `iverilog`, `vvp` and the Gowin `prim_sim.v` are variables at the top of
`run_sim.sh`.

## Cable bit-error test on hardware

1. Program both boards (HL2: `hl2b5up_gowinlink`, this: `gowinlink.fs`), connect both cables,
   power the dock from 12 V or two USB ports.
2. Open the dock's USB-UART (the BL616 virtual COM port, second interface) at 115200 8N1.
   The help line appears at power-up; one status line per second follows.
3. Sequence at power-up: `rev=1` shows the HL2 has aligned the reverse link (the command
   channel works); `st=4` shows the forward link trained (automatic 250 ms after that).
   `tap`/`eye` give the chosen delay tap and the eye width in 12.5 ps taps per lane; an eye
   below about 40 taps (0.5 ns) on any lane means that lane is marginal.
4. `err` (per forward lane) and `re` (per reverse lane, from the HL2) count PRBS mismatches
   (3 per bit error); `words` counts samples. Leave it running; `r` resets, `p` restarts PRBS.
5. `l` switches to live ADC data (`x` sends a test tuning command through the link and the
   HL2 command bus), `c` runs the counter check (`werr` and `rw` must stay 0), `o` puts a
   76.8 MHz square wave on every forward lane for a scope check, `s` toggles the scrambler,
   `t` retrains, `h` prints the command list.

If `clk=0`: no forward clock at U20. If `pll=0`: the Gowin PLL is not locked to it. If
`st=1` (second one) is 0: no status frames from the HL2 (status UART or HL2 build problem).
If `rev` stays 0 with `rst=3x`: the HL2 cannot align the reverse lanes — check the 90-degree
phase of the forwarded reverse clock (`gl_pll.v`) with a scope at the HL2 header.
