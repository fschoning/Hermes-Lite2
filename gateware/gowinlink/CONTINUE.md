# Continuing the HL2 <-> Tang Mega 138K link work by hand

Written 2026-09-12 at the pause point. Read this first, then `STATUS.md` (exact errors), then
`LINK_SPEC.md` (how the link works). Everything below is on branch `gowin-link` in the worktree
`G:\proj\worktrees\Hermes-Lite2-gowin-link`. The PCB design is on branch `gowin-bridge-pcb` in
`G:\proj\worktrees\Hermes-Lite2-gowin-bridge-pcb` (folder `hardware/companions/gowin-bridge/`).
Neither branch is merged into `master` or pushed.

---

## 1. What the system is

The HL2's Cyclone IV streams its raw 12-bit ADC samples (76.8 MSPS, 921.6 Mbit/s) to a Sipeed
Tang Mega 138K (Gowin GW5AST-138) which will do all SDR processing and talk to the PC over its
own gigabit Ethernet using the openHPSDR protocol. Two fab-assembled bridge boards and two
dual-link DVI cables carry the signals:

| Cable | Direction | Pairs | Content |
|---|---|---|---|
| 1 "FWD" | HL2 -> Gowin | clock + 6 data | 76.8 MHz forwarded clock; 6 lanes DDR, 2 bits per lane per clock (153.6 Mbit/s per lane) = 12 bits per sample |
| 1 DDC lines | HL2 -> Gowin | 2 slow wires | status UART (PIN_86, 115200 8N1) and a spare aux line (PIN_87) |
| 2 "REV" | Gowin -> HL2 | clock + 3 data + 1 | 153.6 MHz forwarded clock (90 deg late), 3 lanes DDR at 307.2 Mbit/s (future TX samples), 1 pair = fast serial 76.8 Mbit/s carrying the command words |
| 2 spare | | 2 pairs | unused, DNP on the boards |

HL2 FPGA pins (all in `gateware/variants/hl2b5up_gowinlink/gowinlink_pins.tcl`):
forward data `gl_d[5:0]` = PIN_72, 76, 77, 80, 83, 85 (2.5 V bank 5); forward clock `gl_clk` =
PIN_98 (3.3 V, was LED D2); reverse clock in `gl_rev_clk` = PIN_88; reverse data `gl_rev[2:0]` =
PIN_99, 100, 101; fast serial in `gl_fs_rxd` = PIN_89; status out `gl_status_txd` = PIN_86;
aux out `gl_aux_out` = PIN_87.
Gowin pins: `gowin/proj/gowinlink.cst`, matching `hardware/companions/gowin-bridge/PINMAP.md`
rev A (all on the dock's J14 header, forward clock on ball U20).

Commands from the Gowin to the HL2 are the HL2's own openHPSDR command words (address + 32-bit
data). On the HL2 they are merged onto the internal command bus next to the Ethernet path, so
every existing HL2 function (ADC gain, attenuator, filters, PTT, frequency-driven band decode,
the Pico IO board's I2C data) keeps working when the Gowin forwards the PC's commands.

---

## 2. Tools (all installed, all on the user PATH; open a NEW terminal after login)

| Tool | Path | Check |
|---|---|---|
| Quartus Prime Lite 20.1.1 (Cyclone IV E) | `C:\intelFPGA_lite\20.1.1\quartus\bin64` | `quartus_sh --version` |
| Gowin EDA Education 1.9.11.03 | `C:\Gowin\Gowin_V1.9.11.03_Education\Gowin_V1.9.11.03_Education_x64\IDE\bin` | `gw_sh` then `exit` |
| Icarus Verilog, GTKWave, Yosys, openFPGALoader | `C:\tools\oss-cad-suite\bin` | `iverilog -V` |
| Verilator | same bundle | call `verilator_bin.exe` (the `verilator` wrapper is broken by Git's Perl) |
| Sipeed Gowin programmer | `C:\tools\gowin-programmer\bin\programmer_cli.exe` | needs `PYTHONUTF8=1` and `PYTHONIOENCODING=utf-8` in the environment |
| KiCad 10 | installed by winget during the session | `kicad-cli version` |

Git Bash is used for the simulation script; PowerShell for everything else works too.

---

## 3. Repository layout (worktree `Hermes-Lite2-gowin-link`)

```
gateware/gowinlink/LINK_SPEC.md          the specification (bit mapping, PRBS, training, frames)
gateware/gowinlink/STATUS.md             exact state, errors and next steps at the pause
gateware/gowinlink/CONTINUE.md           this file
gateware/rtl/gowinlink/*.v               modules shared by both sides and HL2-only modules
gateware/rtl/hermeslite_core.v           HL2 core, link integrated behind GOWINLINK / GL_LANES
gateware/variants/hl2b5up_gowinlink/     Quartus project for the HL2 (6 lanes): hermeslite.qsf,
                                         gowinlink_pins.tcl, timing_gowinlink.sdc, Makefile
gateware/variants/hl2b5up_gowinlink3/    same, 3-lane fallback (only if 6 lanes ever fail)
gowin/rtl/*.v                            Gowin-only modules; gl_top.v is the top
gowin/proj/build.tcl, gowinlink.cst/.sdc gw_sh build script, pins, timing
gowin/sim/run_sim.sh, tb_*.v             Icarus testbenches (self-checking, print PASS/FAIL)
gowin/tools/gen_console_fmt.py           generates the console line layout include files
gowin/README.md                          Gowin build, simulation and hardware console guide
```

Build products (`gowin/proj/impl/`, `gowin/sim/build/`, the variant's `db/`, `output_files/`)
are git-ignored.

---

## 4. Step-by-step continuation

### Step 1. Confirm the simulations (30 minutes)

```
cd /g/proj/worktrees/Hermes-Lite2-gowin-link/gowin/sim
./run_sim.sh uart        # must print PASS
./run_sim.sh rev         # must print PASS
./run_sim.sh link 6      # about 10 minutes; last line PASS or FAIL, one ok:/FAIL: line per check
./run_sim.sh link 3      # never run yet
```

State at the pause: `uart`, `rev` and the new fast forward-only test `fwd` PASS
(`./run_sim.sh fwd`, seconds). The forward-training failure seen earlier had a real cause:
Gowin's IDDR model delivers the falling-edge bit as the newer one, the opposite of what the
data plane assumed; the bit order is swapped in `gl_lane_rx.v` (commit e0b20c4) and `tb_fwd`
now aligns with 0 mismatches at every tap. A full `link 6` run with that fix was started at
the very end of the session; its result is in `gowin/sim/build/tb_link_6.log`. One follow-up
before trusting hardware: the trainer's automatic pair-swap retry did not fire in the failed
run and should be understood (`gl_train.v`, LINK_SPEC.md 6.4).
Waveforms: add `$dumpfile/$dumpvars` in `tb_link.v` and open the `.vcd` with `gtkwave`.

### Step 2. Gowin build to a bitstream with clean timing (half a day)

```
cd /g/proj/worktrees/Hermes-Lite2-gowin-link/gowin/proj
gw_sh build.tcl
```

Synthesis passes. Place and route stops on `gowinlink.sdc` lines 19-21: the
`create_generated_clock ... [get_pins {pll_i/pll_i/CLKOUTn}]` object names do not resolve
(`ERROR (TA2003)`). Two ways to fix, pick one:

1. Delete lines 19-21 and 23 and let Gowin derive the PLL output clocks automatically from the
   PLL primitive (it does this when the PLL input `fwd_clk` is constrained). Run the build,
   open `impl/pnr/gowinlink.tr` (text timing report) and read the names Gowin gave the derived
   clocks; then re-add the `set_clock_groups` line and the `set_output_delay` lines using those
   names.
2. Keep the lines and find the real hierarchical pin names: after synthesis, search
   `impl/gwsynthesis/gowinlink.vg` for the PLL instance (module `PLLA` or `PLL`, instance
   under `pll_i`) and use the exact instance path and output pin names (`CLKOUT0/1/2`).

Then iterate on the timing report until there are no setup or hold violations on the
153.6 MHz and 76.8 MHz domains. Places that may need attention: the IDDR capture registers
(`gl_lane_rx.v`), the 2:1 gearbox, and the reverse ODDR outputs (`gl_rev_tx.v`). If the
tool reports the reverse output skew constraint (lines 34-37) as violated, relax it to
+/-1.0 ns first; the HL2 receiver tolerates that.

Outputs: `impl/pnr/gowinlink.fs` (bitstream), `impl/pnr/gowinlink.tr.html` (timing),
`impl/pnr/gowinlink.rpt.html` (resources).

### Step 3. Quartus build of the HL2 variant to an .rbf (half a day)

```
cd /g/proj/worktrees/Hermes-Lite2-gowin-link/gateware/variants/hl2b5up_gowinlink
quartus_sh --flow compile hermeslite -c hermeslite 2>&1 | tee quartus_build.log
```

Analysis and synthesis passes. The fitter had failed on PIN_98 being assigned twice
(`io_led_d2` and `gl_clk`); the LED port was removed from the variant top, but the build was
not rerun. Expect next:

- `timing_gowinlink.sdc` refers to PLL node names that are guesses (lines 16, 18, 34). If the
  Timing Analyzer reports them as not found, open the compiled project in Quartus, use
  Timing Analyzer > Name Finder (or `quartus_sta -t` with `get_pins`) to find the real names of
  the AD9866 PLL output clocks and of the new `rxpll` output, and paste them in.
- Check `output_files/hermeslite.sta.rpt` for negative slack. The only fast paths the link
  adds are register-to-pin on the six DDR outputs and the clock lane, and pin-to-register on
  the three reverse inputs; both use the fast I/O registers so they should close.
- Resource usage: the link adds a few hundred logic cells and one PLL; the EP4CE22 has room.

Then `make` in the variant directory produces `build/hermeslite.rbf`-style outputs via
`quartus_cpf` (see the Makefile); the `.rbf` is what the HL2 bootloader flashes. Flash it the
usual HL2 way (the firmware-update function in Quisk or SparkSDR, or the `hl2_update`-type
scripts described in the repo's gateware README). Keep a copy of the stock `.rbf` to recover.

### Step 4. Program the Gowin board

```
openFPGALoader -b tangmega138k gowin/proj/impl/gowinlink.fs
```

or `programmer_cli.exe` from the Sipeed programmer (run `programmer_cli.exe --scan-cables`
first; install the USB driver from `C:\tools\gowin-programmer\driver\` when the board is
plugged in for the first time).

### Step 5. Hardware bring-up: the cable bit-error test

Prerequisites: both bridge boards assembled (see the PCB worktree's README), the 3x2 header
soldered into DB12 on the HL2 and a 2x20 header into J14 on the Tang dock, both DVI cables
connected OUT-to-IN, the dock powered from 12 V (one USB cable is not enough per Sipeed).

1. Open the dock's USB-UART (BL616 virtual COM port, the second interface) at 115200 8N1.
   A help line prints at power-up, then one status line per second.
2. `rev=1` means the HL2 aligned the reverse link, so the command channel works. `st=4` means
   the forward link trained. `tap` and `eye` give the chosen delay tap and eye width per lane
   in 12.5 ps steps; an eye under about 40 taps (0.5 ns) on any lane is marginal.
3. `err` (forward, per lane) and `re` (reverse, per lane, reported by the HL2) count PRBS
   mismatches (3 per bit error). `words` counts samples. Leave it running for minutes;
   zero errors is the pass criterion. `r` resets counters, `p` restarts PRBS mode.
4. `l` switches to live ADC data; `x` sends a test tuning command through the link and the
   HL2 command bus; `c` runs the counter check (`werr` and `rw` must stay 0); `o` puts a
   76.8 MHz square wave on every forward lane for a scope; `s` toggles the scrambler;
   `t` retrains; `h` prints the command list.
5. Diagnosis: `clk=0` means no forward clock at ball U20; `pll=0` means the Gowin PLL is not
   locked to it; the second `st` field 0 means no status frames from the HL2; `rev` stuck at 0
   with `rst=3x` means the HL2 cannot align the reverse lanes, so check the 90-degree phase
   of the forwarded reverse clock (`gl_pll.v`) with a scope at the HL2 header.
6. Also measure the receiver noise floor with a 50 ohm load on the antenna, link idle versus
   link running, to quantify the added RF noise.

### Step 6. Phase B: make the Gowin the radio (weeks)

Order of work once the link is proven on hardware:
1. Port the HL2's Ethernet stack and openHPSDR protocol (`gateware/rtl/ethernet/`, the
   discovery/command/data packet modules in `hermeslite_core.v`) onto the Gowin with an RGMII
   interface to the dock's RTL8211F PHY (Sipeed's UDP example project shows the PHY bring-up).
2. Port the receiver DSP (`receiver.v`, CIC and FIR decimation, the mixer/NCO) from the HL2
   gateware; the Gowin has 298 multipliers versus the Cyclone's 66, so more receivers and
   wider filters are possible.
3. Forward the PC's command words to the HL2 over the fast serial channel (frequency, PTT,
   gain, attenuator, filters), and relay the HL2's status frames into the protocol's
   response fields.
4. Then TX: DUC on the Gowin, samples back over cable 2's three reverse lanes, HL2 side
   feeding the AD9866 TX path (that HL2 code is not written yet).
5. Later ideas (documented in `franz-claude-analysis/KF7O_EXPANSION_IDEAS.md`): predistortion,
   wideband capture to DDR3, coherent two-radio operation (two HL2s, each with a bridge board,
   linked by the two cables directly), RISC-V control and web UI.

---

## 5. Known gaps and decisions to revisit

- Gowin PLL static 90-degree phase for the reverse clock (`gl_pll.v`, `CLKOUT2_PE_COARSE=2`)
  is unverified on silicon; the HL2 receiver PLL (`gowinlink_rxpll.v`) has a `PHASE_PS` trim.
- The cable-present pin (`LINK_PRESENT`, Gowin ball T20) is wired but unused.
- The fast-serial receiver may count one corrupted packet several times while re-hunting.
- `tb_link` LANES=3 was never run; the 3-lane variant is only a fallback.
- HL2 side: the four LED pins are consumed by the link, so the front LEDs are dark in this
  variant; the HL2's UART/fan/ATU/envelope functions on DB1 pins 1-6 are unavailable.
- PCB open items (see the PCB worktree's `STATUS.md`): two DVI sockets do not fit inside the
  standard enclosure together with the N2ADR filter board (76 mm needed, 50 mm free; an
  L-shaped board with an overhanging tab is drafted, three options listed); the Tang J14
  position on the dock is unverified; DVI-D receptacles are not stocked at LCSC (hand-solder);
  the HL2 +3.3 V spare current is unverified (a jumper selects DVI +5 V instead).

## 6. Housekeeping

- Commit on the branch as you go; merge `gowin-link` and `gowin-bridge-pcb` into `master` only
  when the link works on hardware. Remove each worktree (`git worktree remove`) after its
  branch is merged.
- `franz-claude-analysis/` in the main checkout holds the research reports (untracked). The
  folder `gateware/docs/` there is an accidental duplicate of three of them and can be deleted.
