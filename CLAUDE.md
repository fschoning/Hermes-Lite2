# Instructions for AI coding agents

This repository is a fork of the Hermes-Lite 2 project. The work described here is the **HL2 raw front end**:
gateware variant `hl2b5up_raw`, its NEORV32 firmware and its PC tools. Everything else is upstream Hermes-Lite 2
and should stay as it is unless the task says otherwise.

Start with `docs/rawfront/README.md`. The specification is `docs/rawfront/PROTOCOL.md`.

## Hard rules

- **Never key the transmitter on hardware.** Do not set the key bit in TX_PERMIT (`hl2bus.py permit --key`,
  writes of 0x5458_0001 or with bits 1-2 set to 0x4004_0004, the message layer's TX_PERMIT with flags), do not
  enable PA enable (command 0x09 bit 19) together with a permission, and do not switch the T/R relay. Echo mode
  (register 0x31 = 5) and the test pattern are fine. Real-DAC mode (register 0x31 bit 1) stays off on hardware.
- **Never write the bias pots or the configuration EEPROM** (I2C bus 2 address 0x2C) and never write the
  BIAS_UNLOCK key, unless the owner asks for exactly that.
- **Network flashing only.** Flash application images with `software/hl2flash/hl2flash.py`. Never program a
  `.jic` over JTAG and never touch the factory image. If the radio comes back on its factory image (discovery
  shows no marker and 4 receivers), stop that line of work and report; a power cycle is needed.
- Leave the radio running `hl2b5up_raw` (marker 0xD1) with the message-layer firmware saved and booted
  (`hl2fw.py save firmware/hl2neo/build/msg.elf --version 0x00030001`, then `hl2fw.py boot`).
- Do not change operating-system network settings without the owner's approval.
- Do not push branches or tags, create releases, or add CI unless asked.
- Only one tool may talk to UDP port 1027 at a time (bridge, gdb, console, messages share it).
- The repository is public: never commit private notes, logs, captures, build outputs, absolute paths of your
  machine, e-mail addresses or local network details other than the documented 169.254.x.x examples.

## Layout

| Path | What |
|---|---|
| `gateware/variants/hl2b5up_raw/` | the Quartus project (`hermeslite.qsf`, top `hermeslite.v`, `bootrom.mif`, `seed_try.sh`) |
| `gateware/rtl/rawstream.v` | raw sample sender |
| `gateware/rtl/txsink.v` | TX sample sink, echo, real DAC path |
| `gateware/rtl/auxchan.v` | aux byte channel |
| `gateware/rtl/hl2bus.v` | Etherbone register bridge, status block, command merge |
| `gateware/rtl/hl2cpu.v` | CPU system: bus, RAM/ROM, system block, packet interface |
| `gateware/rtl/hl2io.v` | front-end register block and transmit interlock |
| `gateware/rtl/neorv32/` | NEORV32 v1.13.5 (core unchanged, BSD), HL2 configuration, Verilog conversion |
| `gateware/rtl/hermeslite_core.v`, `control.v`, `ethernet/*` | stock files with this work's changes, selected by parameters |
| `gateware/sim/{front,cpu,rawstream}/` | Icarus Verilog testbenches (`run.sh`) |
| `firmware/hl2neo/` | boot ROM, demo, message-layer firmware (`msg`), health console example; `build.py` |
| `software/rawstream/` | `rawcap` (Rust), `noisetest.py`, `analyse.py`, `nic_setup.ps1` |
| `software/hl2bus`, `hl2msg`, `hl2fw`, `hl2console`, `hl2flash` | Python tools (standard library) |
| `docs/rawfront/` | all documentation |

## Build and test

```
python firmware/hl2neo/build.py
cd gateware/variants/hl2b5up_raw && quartus_sh --flow compile hermeslite -c hermeslite    # ~4 min
sh gateware/sim/front/run.sh ilk          # and i2c, msg, echo; sim/cpu asmi, neo; sim/rawstream
cd software/rawstream/rawcap && cargo build --release && cargo test --release
```

- After any RTL change, check `build/hermeslite.sta.summary`: all setup and hold slacks positive except the
  stock `clock_txoutputfast` path (-0.257 ns). The Ethernet send clock is placement-sensitive; try seeds with
  `seed_try.sh` if it goes negative. Memory blocks are nearly full (64 of 66).
- After a boot ROM change, rebuild the bitstream (the ROM is inside it).
- After changing `neorv32_hl2.vhd`, run `gateware/rtl/neorv32/convert.sh`.
- Run the testbenches that cover the files you changed.
- The unchanged release source reproduces the released `.rbf` (SHA-256 starts 9219973f).

## On the radio

Test setup: radio 169.254.19.221, PC 169.254.202.183 (`--ifaddr` / `--local-ip`).

```
python software/hl2flash/hl2flash.py --ifaddr 169.254.202.183 discover
python software/hl2flash/hl2flash.py --ifaddr 169.254.202.183 flash <file>.rbf --force --yes
software/rawstream/rawcap/target/release/rawcap.exe --ip 169.254.19.221 --local-ip 169.254.202.183 --ip-mtu 9000 --mode pattern --seconds 10
software/rawstream/rawcap/target/release/rawcap.exe --ip 169.254.19.221 --local-ip 169.254.202.183 --ip-mtu 9000 --echo --seconds 10
python software/hl2bus/hl2bus.py --ip 169.254.19.221 --ifaddr 169.254.202.183 front
python software/hl2fw/hl2fw.py --ip 169.254.19.221 --ifaddr 169.254.202.183 run firmware/hl2neo/build/health.elf
python software/hl2fw/hl2fw.py --ip 169.254.19.221 --ifaddr 169.254.202.183 boot
```

Recovery: `docs/rawfront/RECOVERY.md`. A stopped CPU (gdb) fires the CPU watchdog; that only cuts transmit.

## Documentation style

Plain English, short sentences, tables for registers and results. Say what was tested on hardware, what only in
simulation, and what not at all. Keep `docs/rawfront/PROTOCOL.md` in step with the RTL in the same commit.
