# hl2b5up_raw: HL2 raw front-end image

Gateware for Hermes-Lite 2 build 5 and later: every ADC sample over the HL2's own gigabit Ethernet, TX samples
back, register access to every radio function, a NEORV32 RISC-V CPU and a transmit interlock in logic.
Discovery marker 0xD1, 0 receivers.

**Experimental; transmit untested on real RF. Read `docs/rawfront/SAFETY.md` first.**

Build (the boot ROM in `bootrom.mif` comes from `python firmware/hl2neo/build.py`):

```
quartus_sh --flow compile hermeslite -c hermeslite
```

Flash `build/hermeslite.rbf` (or `hl2b5up_raw.rbf` from the release assets) with
`software/hl2flash/hl2flash.py`. Documentation: `docs/rawfront/README.md`.
