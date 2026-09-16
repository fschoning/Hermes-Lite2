Hermes-Lite 2.x
===============

See the main [Hermes-Lite Web Page](http://www.hermeslite.com) for the latest links and details.

This is a work in progress to create a low-cost software defined amateur radio HF transceiver based on a [broadband modem chip](http://www.analog.com/en/broadband-products/broadband-codecs/ad9866/products/product.html) and the [Hermes SDR](http://openhpsdr.org/wiki/index.php?title=HERMES) project.

HL2 raw front end (this fork)
-----------------------------

This fork adds `hl2b5up_raw`, experimental gateware that turns the Hermes-Lite 2 into a raw RF front end: every
12-bit ADC sample at 76.8 MSPS goes to a client over the HL2's own gigabit Ethernet port, transmit samples come
back at the same rate, a register bridge reaches every radio function, a small NEORV32 RISC-V CPU handles slow
control, and a hardware interlock in logic owns every transmit output.

**Experimental. The transmit path has never been tested on real RF. You are responsible for anything the radio
transmits and for holding the licence it needs. The register bridge, debugger and network flashing are open to
anyone on the network: use a direct cable.** See [docs/rawfront/SAFETY.md](docs/rawfront/SAFETY.md).

Documentation: [docs/rawfront/README.md](docs/rawfront/README.md). Gateware: `gateware/variants/hl2b5up_raw`,
firmware: `firmware/hl2neo`, PC tools: `software/rawstream`, `software/hl2bus`, `software/hl2msg`,
`software/hl2fw`, `software/hl2console`, `software/hl2flash`.

Licences: gateware GPL-2.0-or-later; the raw front-end firmware and PC tools Apache-2.0; NEORV32 BSD-3-Clause
([LICENSES](LICENSES)). Raw front-end work by Franz Schöning, https://www.schoning.com, building on the
Hermes-Lite 2 by Steve Haynal KF7O and contributors, Quisk by Jim Ahlstrom N2ADR, NEORV32 by Stephan Nolting,
and the openHPSDR protocol.
