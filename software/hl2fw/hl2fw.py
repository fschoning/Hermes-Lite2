#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Franz Schöning, https://www.schoning.com
"""Firmware tool for the Hermes-Lite 2 soft CPU images (hl2b5up_cpu: VexRiscv rv32i, hl2b5up_neo: NEORV32
rv32imc). Standard library only.

Loads programs into the CPU's RAM through the layer-1 register bridge (no CPU involved, the CPU is
held in reset while loading), starts them, saves them to the flash sector 0x1F0000 so the boot ROM
starts them at power-up, and shows the console. Memory map, registers and the boot flow:
docs/rawfront/RISCV.md. The memory map is the same; the tool reads the
core from SYS_INFO and refuses programs with compressed instructions on the rv32i core.

Examples (radio 169.254.19.221, PC address 169.254.202.183):
  hl2fw.py --ip 169.254.19.221 --ifaddr 169.254.202.183 status
  hl2fw.py --ip ... run demo.elf              load into RAM, start it, show the console
  hl2fw.py --ip ... save demo.elf --version 2 load, write to the flash sector (boot ROM checks CRC)
  hl2fw.py --ip ... console                   console viewer (Ctrl-C to quit)
  hl2fw.py --ip ... rom                       restart the CPU and stay in the boot ROM
  hl2fw.py --ip ... boot                      restart the CPU and let the boot ROM start saved firmware
  hl2fw.py --ip ... halt | resume | reset
  hl2fw.py --ip ... erase                     erase the saved firmware (ROM must be idle: use rom first)
  hl2fw.py --ip ... load demo.bin --addr 0x800   load only, CPU stays in reset

gdb instead of this tool: riscv-none-elf-gdb demo.elf -ex "target remote udp:169.254.19.221:1027".
Use one of the two at a time: the radio answers the PC address and port that sent to it last.
"""

import argparse
import os
import select
import socket
import struct
import sys
import time
import zlib

PORT = 1027
EB_MAGIC = 0x4E6F
EB_MAX = 64

SYS_ID = 0x40010000
SYS_INFO = 0x40010004
SYS_CTRL = 0x40010008
SYS_BOOT_ADDR = 0x4001000C
SYS_FW_STATUS = 0x40010010
SYS_FW_RESULT = 0x40010014
SYS_MS = 0x40010018
SYS_IRQ_EN = 0x40010020
SYS_IRQ_PEND = 0x40010024
SYS_LED = 0x40010028
SYS_STATUS = 0x4001002C
PKT_RX_WR = 0x40020000
PKT_RX_RD = 0x40020004
PKT_TX_LEN = 0x40020008
PKT_COUNT = 0x4002000C
FL_CMD = 0x40030008
REG_VERSION = 0x40000004
REG_TEMP = 0x40003000

CTRL_RESET, CTRL_HALT, CTRL_STAY_ROM, CTRL_BOOT_RAM = 1, 2, 4, 8
ID_CPU = 0x52563332
APP_BASE = 0x800

FW_STATES = {1: "boot ROM busy", 2: "boot ROM idle", 3: "application running", 4: "stopped (trap or gdb)"}
FW_RESULTS = {0: "ok", 1: "bad arguments", 2: "CRC mismatch (RAM differs from the file)", 3: "flash error",
              4: "verify error", 5: "flash locked (network flashing started since power-up)",
              6: "no saved firmware", 7: "saved firmware not valid",
              8: "saved firmware is for another CPU (header format)"}
CORES = {1: "VexRiscv rv32i", 2: "NEORV32 rv32imc"}
SIGNALS = {2: "SIGINT (Ctrl-C / gdb attach)", 4: "SIGILL (illegal instruction)", 5: "SIGTRAP (breakpoint)",
           11: "SIGSEGV (other exception)"}


class Radio:
    def __init__(self, ip, ifaddr, port=PORT, quiet_console=False):
        self.addr = (ip, port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((ifaddr or "", 0))
        self.quiet_console = quiet_console
        self.console_seen = b""

    # ---------------------------------------------------------------- receive
    def _handle(self, data):
        """Console datagrams are printed; returns Etherbone replies."""
        if len(data) >= 2 and data[0] == 0x01 and data[1] == ord("C"):
            self.console_seen += data[2:]
            if not self.quiet_console:
                sys.stdout.write(data[2:].decode("latin-1"))
                sys.stdout.flush()
            return None
        if len(data) >= 8 and struct.unpack(">H", data[:2])[0] == EB_MAGIC:
            return data
        return None

    def poll(self, timeout):
        end = time.monotonic() + timeout
        while True:
            left = end - time.monotonic()
            if left <= 0:
                return None
            if not select.select([self.sock], [], [], left)[0]:
                return None
            data, _ = self.sock.recvfrom(4096)
            r = self._handle(data)
            if r is not None:
                return r

    # ---------------------------------------------------------------- Etherbone
    @staticmethod
    def _packet(wbase=None, writes=(), reads=()):
        p = struct.pack(">HBB4x", EB_MAGIC, 0x10, 0x44) + struct.pack(">BBBB", 0, 0x0F, len(writes), len(reads))
        if writes:
            p += struct.pack(">I", wbase) + b"".join(struct.pack(">I", v & 0xFFFFFFFF) for v in writes)
        if reads:
            p += struct.pack(">I", 0) + b"".join(struct.pack(">I", a) for a in reads)
        return p

    def read(self, addrs, attempts=5):
        addrs = list(addrs)
        out = []
        for i in range(0, len(addrs), EB_MAX):
            chunk = addrs[i:i + EB_MAX]
            for _ in range(attempts):
                while self.poll(0) is not None:
                    pass
                self.sock.sendto(self._packet(reads=chunk), self.addr)
                r = self.poll(0.5)
                if r is not None and len(r) == 16 + 4 * len(chunk):
                    out += list(struct.unpack(">%dI" % len(chunk), r[16:]))
                    break
            else:
                raise IOError("no reply from the register bridge at %s:%d" % self.addr)
        return out

    def rd(self, addr):
        return self.read([addr])[0]

    def wr(self, addr, value, attempts=5):
        """Write one register and read it back in the same request (the reply confirms delivery)."""
        for _ in range(attempts):
            while self.poll(0) is not None:
                pass
            self.sock.sendto(self._packet(addr, [value], [addr]), self.addr)
            r = self.poll(0.5)
            if r is not None and len(r) == 20:
                return struct.unpack(">I", r[16:])[0]
        raise IOError("no reply from the register bridge at %s:%d" % self.addr)

    def write_words(self, base, words, attempts=5):
        """Write consecutive words and read them back in the same request (the bridge does writes
        before reads; 48 words keep the request inside the bridge's 512-byte buffer)."""
        n = 48
        for i in range(0, len(words), n):
            chunk = words[i:i + n]
            a = base + 4 * i
            for _ in range(attempts):
                while self.poll(0) is not None:
                    pass
                self.sock.sendto(self._packet(a, chunk, [a + 4 * k for k in range(len(chunk))]), self.addr)
                r = self.poll(0.5)
                ok = r is not None and len(r) == 16 + 4 * len(chunk)
                if ok and list(struct.unpack(">%dI" % len(chunk), r[16:])) == chunk:
                    break
            else:
                raise IOError("RAM write at 0x%08x does not read back" % a)

    # ---------------------------------------------------------------- boot ROM control datagrams
    def ctrl(self, cmd, *args):
        self.sock.sendto(bytes([0x01, ord(cmd)]) + b"".join(struct.pack("<I", a & 0xFFFFFFFF) for a in args), self.addr)


# -------------------------------------------------------------------- images

def load_image(path, addr, core=None):
    """Returns (load address, bytes, entry). ELF32 RISC-V: PT_LOAD segments; anything else: raw binary."""
    data = open(path, "rb").read()
    if data[:4] != b"\x7fELF":
        a = APP_BASE if addr is None else addr
        return a, data, a
    if data[4] != 1 or data[5] != 1:
        sys.exit("%s: only 32-bit little-endian ELF files" % path)
    e_entry, e_phoff = struct.unpack_from("<II", data, 24)
    if core == 1 and struct.unpack_from("<I", data, 36)[0] & 1:     # e_flags EF_RISCV_RVC
        sys.exit("%s uses compressed instructions; the VexRiscv core of this image runs rv32i only" % path)
    e_phentsize, e_phnum = struct.unpack_from("<HH", data, 42)
    segs = []
    for i in range(e_phnum):
        p_type, p_offset, p_vaddr, p_paddr, p_filesz, p_memsz = struct.unpack_from("<IIIIII", data, e_phoff + i * e_phentsize)
        if p_type == 1 and p_filesz:
            segs.append((p_paddr, data[p_offset:p_offset + p_filesz]))
    if not segs:
        sys.exit("%s: no loadable segments" % path)
    lo = min(s[0] for s in segs)
    hi = max(s[0] + len(s[1]) for s in segs)
    img = bytearray(hi - lo)
    for a, b in segs:
        img[a - lo:a - lo + len(b)] = b
    return lo, bytes(img), e_entry


def words_of(img):
    img = img + b"\x00" * (-len(img) % 4)
    return list(struct.unpack("<%dI" % (len(img) // 4), img)), img


# -------------------------------------------------------------------- commands

def check_cpu(r):
    ident = r.rd(SYS_ID)
    if ident != ID_CPU:
        sys.exit("no CPU system on this image (0x40010000 reads 0x%08x; needs hl2b5up_cpu or hl2b5up_neo)" % ident)


def ram_limit(r):
    return ((r.rd(SYS_INFO) >> 8) & 0xFF) << 10


def fw_state_text(v):
    s = FW_STATES.get(v >> 24, "unknown")
    if v >> 24 == 4:
        s += ", " + SIGNALS.get(v & 0xFF, "signal %d" % (v & 0xFF))
    return s


def result_text(v):
    op = chr(v >> 24) if 0x41 <= v >> 24 <= 0x5A else "?"
    return "%s: %s" % ({"S": "save", "E": "erase", "B": "boot"}.get(op, "none"), FW_RESULTS.get(v & 0xFF, "code %d" % (v & 0xFF)))


def do_load(r, path, addr):
    lo, img, entry = load_image(path, addr, r.rd(SYS_INFO) >> 24)
    words, img = words_of(img)
    end = lo + len(img)
    if lo < APP_BASE or end > ram_limit(r):
        sys.exit("image 0x%08x-0x%08x outside the application RAM 0x%08x-0x%08x" % (lo, end, APP_BASE, ram_limit(r)))
    ctrl = r.rd(SYS_CTRL)
    r.wr(SYS_CTRL, ctrl | CTRL_RESET)
    t0 = time.monotonic()
    r.write_words(lo, words)
    print("loaded %s: %d bytes at 0x%08x, entry 0x%08x, CRC-32 %08x, %.2f s (CPU held in reset)"
          % (os.path.basename(path), len(img), lo, entry, zlib.crc32(img), time.monotonic() - t0))
    return lo, img, entry


def release(r, ctrl, timeout=10.0):
    """Restart the CPU with the given control bits and wait until the boot ROM has started (it drops
    datagrams that arrive before that). Returns the firmware state."""
    r.wr(SYS_CTRL, ctrl | CTRL_RESET)
    r.wr(SYS_FW_STATUS, 0)
    r.wr(SYS_CTRL, ctrl)
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        v = r.rd(SYS_FW_STATUS)
        if v >> 24 >= 2:
            return v
        r.poll(0.02)
    return r.rd(SYS_FW_STATUS)


def wait_state(r, state, timeout=5.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        v = r.rd(SYS_FW_STATUS)
        if v >> 24 == state:
            return v
        r.poll(0.05)
    return r.rd(SYS_FW_STATUS)


def console_loop(r, seconds=None):
    r.ctrl("A")
    last = time.monotonic()
    end = None if seconds is None else time.monotonic() + seconds
    try:
        while end is None or time.monotonic() < end:
            r.poll(0.2)
            if time.monotonic() - last > 2.0:
                r.ctrl("K")
                last = time.monotonic()
    except KeyboardInterrupt:
        print()


def cmd_status(r, args):
    check_cpu(r)
    v = r.read([SYS_INFO, SYS_CTRL, SYS_BOOT_ADDR, SYS_FW_STATUS, SYS_FW_RESULT, SYS_MS, SYS_IRQ_EN, SYS_IRQ_PEND,
                SYS_LED, SYS_STATUS, PKT_RX_WR, PKT_RX_RD, PKT_TX_LEN, PKT_COUNT, FL_CMD, REG_VERSION, REG_TEMP])
    info, ctrl, boot, fws, fwr, ms, irqen, irqp, led, st, rxw, rxr, txl, cnt, fl, ver, temp = v
    print("CPU system    %s, ROM %d kB, RAM %d kB, gateware %d.%d marker 0x%02X" % (CORES.get(info >> 24, "core %d" % (info >> 24)),
          (info >> 16) & 0xFF, (info >> 8) & 0xFF, ver >> 24, (ver >> 16) & 0xFF, (ver >> 8) & 0xFF))
    flags = [n for b, n in ((1, "RESET"), (2, "HALT"), (4, "stay-in-ROM"), (8, "boot-RAM")) if ctrl & b]
    print("control       0x%x %s, boot address 0x%08x, CPU %s%s, resets %d" % (ctrl, " ".join(flags) or "(run)", boot,
          "in reset" if st & (1 << 16) else "running", " but HALTED" if st & (1 << 17) else "", st & 0xFFFF))
    print("firmware      %s (0x%08x); last result %s (0x%08x)" % (fw_state_text(fws), fws, result_text(fwr), fwr))
    print("uptime        %.3f s; IRQ enable 0x%x pending 0x%x; LED 0x%x" % (ms / 1000.0, irqen, irqp, led))
    print("packets       ring write %d read %d; transmit %s; sent %d, receive ring drops %d" % (rxw, rxr,
          "busy" if txl & (1 << 31) else "idle", cnt >> 16, cnt & 0xFFFF))
    print("flash         %s" % ("locked (network flashing since power-up)" if fl & 4 else "available"))
    print("temperature   %.1f C" % ((3.26 * temp / 4096 - 0.5) / 0.01))


def cmd_load(r, args):
    check_cpu(r)
    do_load(r, args.file, args.addr)


def cmd_run(r, args):
    check_cpu(r)
    lo, img, entry = do_load(r, args.file, args.addr)
    r.wr(SYS_BOOT_ADDR, entry)
    release(r, CTRL_BOOT_RAM)
    print("started at 0x%08x; console (Ctrl-C to quit):" % entry)
    console_loop(r, args.seconds)


def cmd_save(r, args):
    check_cpu(r)
    lo, img, entry = do_load(r, args.file, args.addr)
    crc = zlib.crc32(img)
    v = release(r, CTRL_STAY_ROM)
    if v >> 24 != 2:
        sys.exit("boot ROM not idle after restart (%s)" % fw_state_text(v))
    r.wr(SYS_FW_RESULT, 0)                  # the ROM writes the result here
    r.ctrl("A")
    r.poll(0.2)
    r.ctrl("S", lo, len(img), entry, args.version, crc)
    t0 = time.monotonic()
    while time.monotonic() - t0 < 60:
        r.poll(0.2)
        v = r.rd(SYS_FW_RESULT)
        if v >> 24 == ord("S"):
            break
    else:
        sys.exit("no save result within 60 s")
    print("\nsave %s in %.1f s: %d bytes, version 0x%08x, CRC-32 %08x" % (FW_RESULTS.get(v & 0xFF, "?"),
          time.monotonic() - t0, len(img), args.version, crc))
    if v & 0xFF:
        sys.exit(1)
    print("The CPU stays in the boot ROM now; 'hl2fw.py boot' restarts it into the saved firmware.")


def cmd_erase(r, args):
    check_cpu(r)
    if r.rd(SYS_FW_STATUS) >> 24 != 2:
        sys.exit("the boot ROM must be idle: run 'hl2fw.py rom' first")
    r.wr(SYS_FW_RESULT, 0)
    r.ctrl("A")
    r.ctrl("E")
    t0 = time.monotonic()
    while time.monotonic() - t0 < 30:
        r.poll(0.2)
        v = r.rd(SYS_FW_RESULT)
        if v >> 24 == ord("E"):
            print("erase: %s" % FW_RESULTS.get(v & 0xFF, "?"))
            sys.exit(0 if v & 0xFF == 0 else 1)
    sys.exit("no erase result within 30 s")


def restart(r, mode, args):
    check_cpu(r)
    v = release(r, mode)
    print("CPU restarted: %s" % fw_state_text(v))
    if args.seconds != 0:
        console_loop(r, args.seconds if args.seconds is not None else 3.0)


def cmd_rom(r, args):
    restart(r, CTRL_STAY_ROM, args)


def cmd_boot(r, args):
    restart(r, 0, args)


def cmd_reset(r, args):
    ctrl = r.rd(SYS_CTRL) & ~CTRL_HALT
    r.wr(SYS_CTRL, ctrl | CTRL_RESET)
    if not args.hold:
        r.wr(SYS_CTRL, ctrl & ~CTRL_RESET)
    print("CPU %s" % ("held in reset" if args.hold else "restarted"))


def cmd_halt(r, args):
    check_cpu(r)
    r.wr(SYS_CTRL, r.rd(SYS_CTRL) | CTRL_HALT)
    print("CPU halted (bus frozen, state kept)")


def cmd_resume(r, args):
    check_cpu(r)
    r.wr(SYS_CTRL, r.rd(SYS_CTRL) & ~(CTRL_HALT | CTRL_RESET))
    print("CPU running")


def cmd_console(r, args):
    check_cpu(r)
    console_loop(r, args.seconds)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ip", required=True, help="radio IP address")
    ap.add_argument("--ifaddr", default="", help="local IP address to send from")
    ap.add_argument("--port", type=int, default=PORT)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def num(s):
        return int(s, 0)

    sub.add_parser("status")
    for name in ("load", "run", "save"):
        p = sub.add_parser(name)
        p.add_argument("file")
        p.add_argument("--addr", type=num, default=None, help="load address for a raw binary (default 0x800)")
        if name == "run":
            p.add_argument("--seconds", type=float, default=None, help="stop the console after this many seconds")
        if name == "save":
            p.add_argument("--version", type=num, default=1, help="version number stored in the header")
    p = sub.add_parser("console")
    p.add_argument("--seconds", type=float, default=None)
    for name in ("rom", "boot"):
        p = sub.add_parser(name)
        p.add_argument("--seconds", type=float, default=None, help="console time after the restart (default 3, 0 = none)")
    p = sub.add_parser("reset")
    p.add_argument("--hold", action="store_true", help="keep the CPU in reset")
    sub.add_parser("halt")
    sub.add_parser("resume")
    sub.add_parser("erase")
    args = ap.parse_args()

    r = Radio(args.ip, args.ifaddr, args.port)
    globals()["cmd_" + args.cmd](r, args)


if __name__ == "__main__":
    main()
