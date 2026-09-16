# Development history: the intermediate test images

`hl2b5up_raw` was built in steps. Each step was a separate test image, flashed and tested on the radio before
the next one started. Only the final image is part of this release; the intermediate images were removed
because everything they added is in `hl2b5up_raw`. This page explains them, because code comments and
parameter names still refer to them.

Every image reported its own marker in discovery byte 0x0C, so a flash could be confirmed from the network.

| Step | Image | Marker | What it added | What the step showed |
|---|---|---|---|---|
| 1 | `hl2b5up_rawlite` | - | Raw sample sender (`rtl/rawstream.v`) beside a reduced normal HL2 (2 receivers, no transmitter): register 0x30, 20-byte header, test pattern, quiet capture, 16,384-sample FIFO | Every sample reaches a PC at 76.8 MSPS with 0 bad samples. All losses were in the PC's network card. Streaming at full rate does not raise the noise floor in the amateur bands |
| 1a | `hl2b5up_diag_a`, `_b`, `_c` | 0xA1, 0xB1, 0xC1 | Small variations of step 1, to find why the first flash came back as the factory image | The radio was already sitting in factory fallback; a power cycle was needed. Nothing wrong with the image |
| 2 | `hl2b5up_duplex` | 0xD2 | TX sample sink on port 1026 with a virtual DAC and a pattern checker; 40-byte version 2 header with TX counters; receive path widened from 11-bit to 16-bit lengths so jumbo UDP datagrams arrive whole | Both directions at once, 0 lost TX frames. The PC card in use could not send 12,864 jumbo frames/s; a different port could |
| 3 | `hl2b5up_aux` | 0xA5 | Aux byte channel on port 1027 in the gaps between raw frames (register 0x32) | About 50 Mbit/s radio to PC beside the full stream; up to 200 Mbit/s PC to radio; no sample disturbed |
| 4 | `hl2b5up_front` | 0xF1 | Receivers and IQ/bandscope FIFOs removed; Etherbone register bridge; transmit-safety byte in header byte 3; slow ADC read also while streaming | Freed about 6,800 logic elements, 20 memory blocks and all 56 DSP elements. Bridge worked during full-rate streaming |
| 5 | `hl2b5up_cpu` | 0xC2 | Soft CPU (VexRiscv "Min", rv32i), boot ROM with console and gdb stub, RAM loading through the bridge, saved firmware in flash sector 0x1F0000 | gdb, saving and booting firmware worked. Used all 66 memory blocks. CPU activity did not change the noise floor |
| 6 | `hl2b5up_neo` | 0xC3 | NEORV32 rv32imc replaced VexRiscv; single step through a step interrupt; 25 MHz CPU clock | Smaller code (demo 564 bytes instead of 1,068), 4 kB ROM instead of 6 kB, 2 memory blocks free. Again no noise change |
| 7 | **`hl2b5up_raw`** | **0xD1** | Transmit interlock in logic, front-end register block (0x4004_0000), real DAC path, echo mode, 48-byte version 3 header, message-layer firmware | This release. Results in [RESULTS.md](RESULTS.md) |

Parameter names in `gateware/rtl/hermeslite_core.v` follow the steps: `RAWSTREAM`, `DUPLEX`, `AUX`,
`RADIO = 0`, `HL2BUS`, `CPU` / `CORE`, `RAWFRONT`. Setting them differently still builds the earlier
configurations, but only `hl2b5up_raw` was rebuilt and tested with the final shared files.

The VexRiscv core option (`hl2cpu.v` `CORE = 1`) is still in the RTL but its core file
(`rtl/cpu/VexRiscv_Min.v`, MIT licence, from the `pythondata-cpu-vexriscv` package) is not in this release.
Why VexRiscv was replaced: [README.md](README.md#a-cpu-inside-and-why-neorv32-rather-than-vexriscv).

Stock HL2 images (`hl2b5up_main` and the others in `gateware/variants`) are unchanged by this work, except
that they now build with the shared files changed here. Their parameters keep the stock behaviour; they were
not rebuilt or retested.
