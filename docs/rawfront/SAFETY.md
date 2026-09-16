# Transmit safety and network security

## Transmit safety disclaimer

**This is experimental gateware. Its transmit path has never been tested on real RF.**

- On the one radio it was tested on, the transmitter was **never keyed**: no permission with the key bit
  was ever given, the PA and T/R relays were never switched, and the AD9866 transmit DAC was only exercised
  in simulation. The relay and PA sequencing, the DAC output, and the interlock's trips while keyed are
  simulation results only ([RESULTS.md](RESULTS.md)).
- The gateware gives a client full control of transmit samples, TX gain, PA enable and the bias pots.
  A client bug, a wrong sample stream or a wrong register value can put a strong or badly distorted
  signal on the air, overheat the PA, or damage the radio or whatever is connected to it.
- The hardware interlock ([PROTOCOL.md](PROTOCOL.md#9-transmit-interlock)) is a safety net, not a
  guarantee. It cuts transmit when its lease is not renewed, on over-temperature, on the TX inhibit input,
  when the CPU watchdog fires and after the maximum key-down time. It does not check what you transmit,
  where, or at what power.
- **You are responsible** for everything this radio transmits: for holding a licence that covers the
  frequencies, modes and power you use, for spectral purity (use the HL2's low-pass filters and a filter
  board appropriate for the band), and for testing into a dummy load before connecting an antenna.
- No warranty. See the licences ([README.md](README.md#licences)).

Recommended first steps if you want to transmit:

1. Test with echo mode first (register 0x31 = 5): it exercises the full TX sample path without driving the
   DAC.
2. Use a dummy load and a power meter or attenuator plus spectrum analyser, never an antenna.
3. Start with TX gain low (register 0x09 [31:28]) and PA enable off (register 0x09 bit 19 = 0): the DAC
   output then only reaches the low-level path.
4. Tighten the limits for your tests: LEASE_MS, MAXKEY_S (for example 10 s) and TEMP_LIMIT.
5. Watch the safety byte in every raw frame and stop your sender when bit 7 (trip) or bit 6
   (over-temperature) appears.

## Network security

**The register bridge, the gdb stub, the console and network flashing are open to anyone who can send UDP
packets to the radio.** There is no authentication and no sender filter.

Anyone on the same network can:

- read and write every register the bridge reaches, including the transmit permission, the command bus
  (PA enable, TX gain), I2C (bias pots after writing the unlock key) and the CPU's memory;
- halt, reset or reprogram the CPU, and erase or replace the saved firmware;
- flash any gateware image over the network (the same as stock HL2 gateware, which also accepts network
  flashing from anyone);
- start the stream and point it at another address.

Use the radio only on a **dedicated direct cable** to the computer or FPGA board that drives it, or on an
isolated network with no other users. Do not bridge that port to a LAN, Wi-Fi or the internet, and do not
forward any of its UDP ports. The HL2 receive path also checks no Ethernet CRC, so a noisy or shared link
can deliver corrupted commands.

This release does not change the gateware for either point: they are documented limits.
