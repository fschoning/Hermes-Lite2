# Starting prompt for an AI coding agent

Copy the text below into a new agent session opened at the repository root, then add the task.

---

You are working on the Hermes-Lite 2 raw front end in this repository: gateware variant
`gateware/variants/hl2b5up_raw` for the Hermes-Lite 2 (Intel Cyclone IV EP4CE22, Quartus Prime Lite 20.1.1),
NEORV32 RISC-V firmware in `firmware/hl2neo`, and PC tools in `software/`. The radio streams every 12-bit ADC
sample at 76.8 MSPS over its own gigabit Ethernet port as UDP, takes TX samples back, and exposes all radio
functions through an Etherbone register bridge, with a transmit interlock in logic.

Before you change anything, read in this order:

1. `CLAUDE.md` (hard rules, layout, build and test commands).
2. `docs/rawfront/SAFETY.md` (transmit safety and network security).
3. `docs/rawfront/README.md` (what the design is and why it is built this way).
4. `docs/rawfront/PROTOCOL.md` (wire formats and register map: the specification).
5. For CPU or firmware work: `docs/rawfront/RISCV.md`. For builds, timing and simulation:
   `docs/rawfront/TOOLCHAIN.md`. For what has and has not been tested: `docs/rawfront/RESULTS.md`.
   For names of earlier test images in comments: `docs/rawfront/HISTORY.md`.

Rules that always apply:

- Never key the transmitter, enable the PA, switch the T/R relay, turn on real-DAC mode, or write the PA bias
  pots on hardware. Echo mode and the test pattern are allowed.
- Flash only application images over the network with `software/hl2flash/hl2flash.py`; never JTAG `.jic`,
  never the factory image. If the radio falls back to its factory image, stop and report.
- Leave the radio running `hl2b5up_raw` with the message-layer firmware saved and booted.
- Keep FPGA memory-block use and Ethernet clock timing in view: check `build/hermeslite.sta.summary` after every
  RTL change and run the testbenches that cover what you changed.
- Update `docs/rawfront/PROTOCOL.md` in the same commit as any wire-format or register change, and
  `docs/rawfront/RESULTS.md` with anything tested on hardware.
- Do not push, tag or publish. Do not commit logs, captures, build outputs or machine-specific paths.
- Report what you ran on the radio, what passed only in simulation, and what you did not test.

Task:
