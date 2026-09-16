# Recovery guide

The HL2 flash holds two gateware images: a **factory image** at the start of the flash, written at
manufacture and never touched by network flashing, and the **application image** at 0x100000, which network
flashing replaces. At power-up the FPGA loads the application image; if that fails to configure, it falls
back to the factory image. This image also keeps saved CPU firmware in the last flash sector,
0x1F0000-0x1FFFFF.

Tools: `software/hl2flash/hl2flash.py` (Python standard library only). Replace the addresses with yours:
`--ifaddr` is the PC's address on the radio's network.

```
python software/hl2flash/hl2flash.py --ifaddr 169.254.202.183 discover
```

| Discovery shows | The radio runs |
|---|---|
| `receivers 0 ... diag image 0xD1` | this image, `hl2b5up_raw` |
| `receivers 4`, no diag marker | a stock image or the factory image |
| nothing | no gateware answering (see below) |

## 1. A flash failed or the new image does not start

Symptom: `hl2flash.py flash` stopped with an error, or it ended with "the radio restarted but reports the
same version and receiver count as before", or discovery shows `receivers 4` and no marker after flashing
this image.

1. **Power-cycle the radio** (off, wait a few seconds, on). A radio that fell back to its factory image
   ignores new flashes until a full power cycle.
2. Run `discover`. If it shows `receivers 4` without a marker, the factory image is running because the
   application image is invalid.
3. Flash again, radio stopped:

   ```
   python software/hl2flash/hl2flash.py --ifaddr 169.254.202.183 flash hl2b5up_raw.rbf
   ```

4. It should end with `SUCCESS: radio restarted with gateware 74.2, 0 receivers.` and discovery shows marker
   0xD1.

The erase and programming run entirely in gateware and do not use the CPU, so a crashed or halted CPU does not
block flashing (tested on the radio).

## 2. Back to stock gateware

The stock stable image is in this repository (`gateware/bitfiles/stable/latest` names the folder):

```
python software/hl2flash/hl2flash.py --ifaddr 169.254.202.183 flash --stable
```

or any `.rbf` from the Hermes-Lite 2 releases, or Quisk's gateware update with the radio stopped. Stop any
raw stream first (`rawcap --ip <radio> --clear-raw-mode` also turns raw mode off).

**Flashing stock or any other image erases the saved CPU firmware.** The stock network erase clears the last
flash sector as well. Only flashes done while `hl2b5up_raw` is running keep it (this image stops its erase
before 0x1F0000). After returning to `hl2b5up_raw` from another image, save the firmware again
([RISCV.md](RISCV.md#saving-firmware)). The message-layer firmware is `firmware/hl2neo/build/msg.elf`, or
`msg.elf` from the release assets.

## 3. The radio does not answer at all: factory boot

Force the factory image at power-up: **ground both the tip and the ring of the key jack** (a 3.5 mm stereo
plug with tip, ring and sleeve shorted together), then power up. The factory image ignores the application
image and answers discovery. Remove the plug, then flash as in section 1 or 2. Power-cycle afterwards.

If discovery still finds nothing, check the network first: link LEDs on both ends, the PC's address in the
same subnet (a direct cable without DHCP gives both ends 169.254.x.x addresses; the radio takes about 15 s to
choose one), and `--ifaddr` naming the right network card.

## 4. Last resort: JTAG

With a USB-Blaster on the HL2's JTAG header (CN1) and Quartus Prime Lite:

- **Volatile:** load `gateware/variants/<variant>/build/hermeslite.sof` with the Quartus Programmer. The
  image runs until power-off and changes nothing in flash. Then network-flash a good `.rbf`.
- **Permanent (only if the factory image itself is damaged):** a `.jic` file programs the flash directly.
  The `.cof` in `gateware/boards/hl2b5up/ep4ce22.cof` (used by `make` in a variant folder) builds a
  single-image `.jic` at address 0: **it replaces the factory image.** Use it only when nothing else works,
  and only with a known-good stock image.

## 5. CPU and firmware problems (gateware fine)

| Problem | Way out |
|---|---|
| Application hangs, crashes or floods the console | `hl2fw.py rom` (restart into the boot ROM, saved firmware not started), or `hl2fw.py halt` |
| Saved firmware crashes at every start | `hl2fw.py rom`, then `hl2fw.py erase`, then save a good one |
| CPU or boot ROM dead | the bridge still works: `hl2fw.py reset --hold`; network flashing does not use the CPU |
| CPU watchdog fired (transmit cut off) | kick it from firmware, or `hl2bus.py wdog-disarm` if no firmware runs |
| Interlock trip latched | fix the cause, then `hl2bus.py clear-trips` |
| Raw mode left on after a crashed client | `rawcap --ip <radio> --clear-raw-mode`, or reboot: `hl2flash.py reboot` |

Commands are in [TOOLS.md](TOOLS.md) and [RISCV.md](RISCV.md).
