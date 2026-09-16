# HL2 raw front end: every ADC sample over the radio's own gigabit Ethernet

`hl2b5up_raw` is gateware for the Hermes-Lite 2 (build 5 and later) that turns the radio into a raw RF front
end. It sends every 12-bit sample of the AD9866 at 76.8 million samples per second to a client over the HL2's
own Ethernet port, takes 12-bit transmit samples back at the same rate, and gives the client register access
to every radio function. All signal processing happens in the client. A small RISC-V CPU inside the FPGA
handles slow control, and a hardware interlock in logic owns every transmit output.

> **Experimental. The transmit path has never been tested on real RF.** You are responsible for anything the
> radio transmits and for holding a licence for it. The register bridge, the debugger and network flashing are
> open to anyone on the network: use a direct cable. Read [SAFETY.md](SAFETY.md).

![raw stream on the test radio](images/rawcap_stream.png)

## Documents

| Document | For |
|---|---|
| [SAFETY.md](SAFETY.md) | transmit safety disclaimer and network security note: read first |
| [TOOLCHAIN.md](TOOLCHAIN.md) | install the tools; build gateware and firmware; timing to expect; simulation; flashing; network card setup; building rawcap |
| [PROTOCOL.md](PROTOCOL.md) | specification for client builders: discovery, start/stop, frame formats, TX samples and pacing, echo, aux channel, register bridge and full register map, transmit interlock, message layer |
| [RISCV.md](RISCV.md) | the CPU: memory map, boot ROM, gdb, `hl2fw.py`, writing firmware, the radio health console example |
| [TOOLS.md](TOOLS.md) | the reference PC tools, including the one-command noise test |
| [RECOVERY.md](RECOVERY.md) | failed flash, back to stock gateware, factory boot, JTAG |
| [RESULTS.md](RESULTS.md) | what was tested and how, noise measurements, what was not tested, features left out, known limits |
| [HISTORY.md](HISTORY.md) | the intermediate test images this was built through |
| [AGENT_PROMPT.md](AGENT_PROMPT.md) | a starting prompt for an AI coding agent working on this project |

## What it does

| Function | Where it runs |
|---|---|
| Every ADC sample to the client, 12-bit, 76.8 MSPS, about 12,900 UDP frames a second at 9,000-byte jumbo frames, with sequence numbers, a 48-bit sample index, overflow flags and the transmit-safety byte in every frame | logic |
| TX samples from the client at 76.8 MSPS into a 16,384-sample FIFO, played one per ADC clock; the FIFO fill in every raw frame header for clock-drift pacing | logic |
| Echo mode: the played TX samples come back in the RX stream, for bandwidth and latency tests without RF | logic |
| Register bridge (Etherbone format): every register, I2C device, the command bus and the CPU's memory, with or without a working CPU | logic |
| Transmit interlock: lease that must be renewed every 100 ms, over-temperature, TX inhibit input, CPU watchdog, maximum key-down time, relay and PA sequencing, trips that latch until cleared | logic |
| Aux byte channel in the gaps between raw frames (about 50 Mbit/s from the radio beside the full stream) | logic |
| Discovery, network flashing, reboot | logic (stock HL2 code) |
| NEORV32 RISC-V CPU with boot ROM, network console, gdb over UDP, firmware saved in flash | logic + firmware |
| Message layer: reliable requests, I2C scans, telemetry, events | firmware |

Tested on the radio: 0 lost frames and 0 bad samples at the full rate; echo at 905 Mbit/s to the radio and
927 Mbit/s back at the same time with every sample matching; 0.55 ms average round trip; no amateur band's
noise floor moved by more than 0.1 dB with streaming on. Details and the untested parts: [RESULTS.md](RESULTS.md).

## Why it is built this way

### The goal

The HL2 is a good RF front end (AD9866 12-bit ADC and DAC, filters, preamp, 5 W PA) with a small FPGA that is
full. The plan behind this work is to move all processing to a larger FPGA board (a Sipeed Tang Mega 138K Pro)
and use the HL2 only for RF. The first step, this release, streams to a PC so the link, the protocol and the
radio side can be tested before the far side exists.

### The HL2's own Ethernet port instead of a new link board

The raw stream is 921.6 Mbit/s. Two custom link designs were worked out first: a board carrying LVDS lanes
over a SlimSAS cable, and a fibre link with serialiser chips. Both need a custom surface-mount board. The
SlimSAS connector is rated for only 250 matings, and the serialiser chips were hard to buy.

The HL2 already has a gigabit PHY that its gateware drives at 1000 Mbit/s full duplex. With 9,000-byte jumbo
frames the samples need 931 Mbit/s on the wire, which fits with about 7 % to spare, in both directions at
once. The cost is a network cable. The price: the PC or far-side board loses the HL2's port for anything else
(it needs its own second network port), nothing is retransmitted, the aux channel beside the stream is limited
to about 50 Mbit/s, and the Ethernet activity could add receiver noise. The noise question was measured on
every step of the work ([RESULTS.md](RESULTS.md#receiver-noise-with-full-rate-streaming)).

The samples travel as ordinary UDP datagrams through the stock HL2 network stack rather than raw Ethernet
frames. That keeps discovery, network flashing and gain commands working, lets a PC receive with a plain
socket and Wireshark decode the traffic, and costs 0.3 % overhead at jumbo size.

### Receivers removed

The openHPSDR receivers, their decimation filters and the IQ and bandscope FIFOs did processing that now
belongs to the client. Removing them freed about 6,800 logic elements, 20 of the 66 memory blocks and all 56
DSP blocks. Memory blocks are the scarce resource on the EP4CE22; the CPU, the 16,384-sample TX FIFO and the
register bridge fit only because of this.

### A CPU inside, and why NEORV32 rather than VexRiscv

Slow control (I2C devices, telemetry, events, reliable requests) is easier and safer close to the hardware
than across the link, and must keep working when the far side is busy or restarting. A soft RISC-V core runs
that control; everything time-critical stays in logic.

The first CPU was VexRiscv in its smallest pre-generated configuration (rv32i). It worked, but used all 66
memory blocks, and every pre-generated VexRiscv with compressed instructions also carries caches that cost 8-10
more memory blocks. Generating a custom configuration needs Java, SBT and the SpinalHDL build. Its minimal
core also lacked `wfi` and `mscratch` and reported breakpoints as illegal instructions, all worked around in
the boot ROM.

NEORV32 replaced it: rv32imc without caches, maintained VHDL that Quartus Prime Lite builds directly, standard
traps, `wfi`, BSD licence and very good documentation. Compressed code halved program size (the demo went from
1,068 to 564 bytes), the boot ROM shrank from 6 kB to 4 kB and two memory blocks came free, for about 700 more
logic elements. The same configuration converts to Verilog with GHDL so the Icarus Verilog testbenches still
run.

### Firmware not baked into the gateware

Only a small, stable boot ROM is in the bitstream. Programs load into RAM over the network in well under a
second through the register bridge or gdb, without a 4-minute gateware build and without reflashing, and can
be saved to a spare flash sector that the boot ROM starts at power-up. Gateware and firmware can change at
different speeds, a broken program never blocks the radio (the bridge can halt the CPU or keep it in the ROM),
and network flashing does not involve the CPU at all.

### Safety in logic, not in firmware

A client, a CPU or a cable can fail at any time, so no software is trusted to switch transmit off:

- One logic block is the only driver of the PA supply, PA bias, op-amp supply, both T/R relays and the AD9866
  transmit data. Nothing else in the image can drive those pins.
- Transmit needs a permission lease the client renews at least every 100 ms. A dead client, CPU or cable stops
  transmit within one lease.
- Over-temperature (read by logic from the slow ADC), a stale temperature reading, the TX inhibit input, a
  CPU watchdog and a maximum key-down time each cut transmit. Cut-offs while transmitting latch until cleared.
- Relays switch 10 ms before the PA on key-down and 10 ms after it on key-up.
- Limits can only be tightened by software (the temperature limit cannot be raised above 55 °C).
- Writes to the PA bias pots are refused unless unlocked with a key.
- Spare output pins that could key an external amplifier are held at their idle levels.
- The interlock state is copied into every raw frame header, so the far side sees a trip within one frame
  without asking the CPU.

## Quick start

1. Read [SAFETY.md](SAFETY.md). Dummy load on the antenna connector, direct cable to the PC.
2. Set up the network card ([TOOLCHAIN.md](TOOLCHAIN.md#8-network-card-setup)).
3. Flash `hl2b5up_raw.rbf` from the release assets with the radio stopped:
   `python software/hl2flash/hl2flash.py --ifaddr <pc-ip> flash hl2b5up_raw.rbf`.
   Discovery then shows `receivers 0 ... diag image 0xD1`.
4. Save the message-layer firmware ([RISCV.md](RISCV.md#saving-firmware)).
5. Build rawcap and stream: `rawcap --ip <radio-ip> --local-ip <pc-ip> --ip-mtu 9000 --mode pattern --seconds 20`.
6. Back to stock at any time: [RECOVERY.md](RECOVERY.md#2-back-to-stock-gateware).

## Licences

| Part | Licence |
|---|---|
| Gateware (`gateware/`), including the new modules and testbenches | GPL-2.0-or-later, like the rest of the HL2 gateware ([LICENSES/GPL-2.0.txt](../../LICENSES/GPL-2.0.txt)) |
| RISC-V firmware (`firmware/hl2neo`) and the PC tools listed in [TOOLS.md](TOOLS.md) | Apache-2.0 ([LICENSES/Apache-2.0.txt](../../LICENSES/Apache-2.0.txt)) |
| NEORV32 (`gateware/rtl/neorv32/core`) | BSD-3-Clause, unchanged ([LICENSE.neorv32](../../gateware/rtl/neorv32/LICENSE.neorv32)) |

New source files carry an SPDX licence identifier. Stock HL2 files changed by this work keep their original
headers and authors, with a "Modified 2026" line.

## Credits

- **Hermes-Lite 2**: Steve Haynal, KF7O, and the Hermes-Lite contributors: the hardware, and the gateware this
  is built on. The gateware itself descends from the openHPSDR Hermes and Metis designs (Phil Harman VK6APH,
  Alex Shovkoplyas VE3NEA and others).
- **Jim Ahlstrom, N2ADR**: Quisk, whose Hermes-Lite 2 flashing code is the basis of the network flashing
  packets `hl2flash.py` uses (through `software/hermeslite/hermeslite.py`); the HL2 filter and IO boards.
- **NEORV32**: Stephan Nolting and contributors, `https://github.com/stnolting/neorv32`.
- **VexRiscv**: SpinalHDL contributors; used in an earlier development step.
- **openHPSDR**: the protocol 1 discovery, command and flashing formats kept in this image.
- **LiteX/LiteEth**: the Etherbone packet format of the register bridge.
- **This work**: Franz Schöning, https://www.schoning.com.
