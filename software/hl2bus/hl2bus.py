#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Franz Schöning, https://www.schoning.com
"""Register access to the Hermes-Lite 2 front-end images (hl2b5up_front, hl2b5up_raw) over the network.

Talks to the layer-1 register bridge in the gateware (no CPU involved) on UDP port 1027 using
the Etherbone packet format (the LiteX/LiteEth Wishbone-over-UDP format). Standard library only.
Register map and protocol: docs/rawfront/PROTOCOL.md; the raw front-end register block
(transmit interlock, command bus, I2C, LEDs, fan, inputs) at 0x4004_0000: docs/rawfront/PROTOCOL.md.

Examples:
  hl2bus.py --ip 169.254.19.221 --ifaddr 169.254.202.183 dump
  hl2bus.py --ip 169.254.19.221 read 0x40000000 4
  hl2bus.py --ip 169.254.19.221 write 0x40000008 0xCAFEF00D
  hl2bus.py --ip 169.254.19.221 rxgain 20
  hl2bus.py --ip 169.254.19.221 scratch-test
  hl2bus.py --ip 169.254.19.221 front                      raw front-end register block, decoded
  hl2bus.py --ip 169.254.19.221 scan 2                     I2C address probes on bus 2 (read-only)
  hl2bus.py --ip 169.254.19.221 i2c 2 0x20 0x09 --read     4 bytes from register 0x09 of 0x20 on bus 2
  hl2bus.py --ip 169.254.19.221 cmd 0x0a 0x54              command bus: RX gain code 0x54
"""

import argparse
import socket
import struct
import sys
import time

PORT = 1027
MAGIC = 0x4E6F
MAX_WORDS = 64          # gateware limit per record

REG_ID = 0x40000000
REG_VERSION = 0x40000004
REG_SCRATCH = 0x40000008
REG_CAPS = 0x4000000C
REG_EB_REQUESTS = 0x40000010
REG_EB_DROPS = 0x40000014
REG_EB_BUS_ERRORS = 0x40000018
REG_RX_GAIN = 0x40002000
REG_TEMP = 0x40003000
REG_FWD = 0x40003004
REG_REV = 0x40003008
REG_BIAS = 0x4000300C
REG_INPUTS = 0x40004000
REG_TX_STATUS = 0x40007000

ID_VALUE = 0x484C3242   # "HL2B"

# raw front-end register block (hl2b5up_raw, rtl/hl2io.v)
IO = 0x40040000
IO_ID, IO_TX_PERMIT, IO_ILK_STATUS, IO_ILK_CLEAR = IO + 0x00, IO + 0x04, IO + 0x08, IO + 0x0C
IO_LEASE_MS, IO_MAXKEY_S, IO_TEMP_LIMIT, IO_KEYTIME = IO + 0x10, IO + 0x14, IO + 0x18, IO + 0x1C
IO_WDOG, IO_WDOG_MS, IO_WDOG_DISARM = IO + 0x20, IO + 0x24, IO + 0x28
IO_CMD_DATA, IO_CMD_ADDR, IO_I2C_XFER, IO_I2C_STATUS, IO_I2C_RDATA = IO + 0x2C, IO + 0x30, IO + 0x34, IO + 0x38, IO + 0x3C
IO_BIAS_UNLOCK, IO_LED, IO_FAN, IO_INPUTS, IO_ADC_SEQ = IO + 0x40, IO + 0x44, IO + 0x48, IO + 0x4C, IO + 0x50
IO_ID_VALUE = 0x494F3031
PERMIT_KEY, CLEAR_KEY, WDOG_KEY, BIAS_KEY = 0x54580000, 0x434C5452, 0x57444F47, 0x42494153
ILK_BITS = ["TX-ON", "PA-STAGE-ON", "lease-valid", "tx-requested", "TRIP-LATCHED", "cut-off-present", "key-bit"]
REASONS = ["lease-expired-while-keyed", "over-temperature", "tx-inhibit", "cpu-watchdog", "max-key-down", "temperature-stale"]
PIN_BITS = ["tip", "ring", "cn8", "cn9", "cn10", "db1-2", "db1-5", "link-rx0", "link-rx1", "tp2", "tp7", "tp8", "tp9"]

SAFETY_BITS = ["tx-forced-off", "PA-KEYED", "host-mox", "ptt-in", "key-in", "tx-inhibit", "OVER-TEMP", "bit7"]
# hl2b5up_raw: bit 0 = transmit off, bit 2 = transmit requested, bit 6 = over-temperature cut-off, bit 7 = trip latched
SAFETY_BITS_RAW = ["tx-off", "PA-KEYED", "tx-requested", "ptt-in", "key-in", "tx-inhibit", "OVER-TEMP", "TRIP-LATCHED"]
INPUT_BITS = ["key-in", "ptt-in", "tx-inhibit", "over-temp", "tx-keyed"]
CAPS_BITS = ["receivers", "transmitter", "raw-stream", "duplex", "aux", "cpu", "raw-front-end"]


class BusError(Exception):
    pass


def build_packet(writes_base=None, writes=(), reads=(), probe=False):
    """One Etherbone packet with one record. Big-endian as on the wire."""
    if probe:
        return struct.pack(">HBB4x", MAGIC, 0x11, 0x44)
    head = struct.pack(">HBB4x", MAGIC, 0x10, 0x44)
    rec = struct.pack(">BBBB", 0x00, 0x0F, len(writes), len(reads))
    body = b""
    if writes:
        body += struct.pack(">I", writes_base) + b"".join(struct.pack(">I", v & 0xFFFFFFFF) for v in writes)
    if reads:
        body += struct.pack(">I", 0) + b"".join(struct.pack(">I", a) for a in reads)
    return head + rec + body


class HL2Bus:
    def __init__(self, ip, ifaddr=None, port=PORT, timeout=0.5, retries=3):
        self.addr = (ip, port)
        self.timeout = timeout
        self.retries = retries
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((ifaddr or "", 0))
        self.sock.settimeout(timeout)

    def _drain(self):
        self.sock.setblocking(False)
        try:
            while True:
                self.sock.recvfrom(65536)
        except (BlockingIOError, OSError):
            pass
        finally:
            self.sock.settimeout(self.timeout)

    def _exchange(self, pkt, expect_len, check):
        """Send pkt and wait for an Etherbone reply of expect_len bytes. Reads are idempotent, so
        a lost request or reply is simply sent again."""
        for _ in range(self.retries):
            self._drain()
            self.sock.sendto(pkt, self.addr)
            deadline = time.monotonic() + self.timeout
            while time.monotonic() < deadline:
                try:
                    data, src = self.sock.recvfrom(65536)
                except socket.timeout:
                    break
                if src[0] != self.addr[0] or len(data) < 8 or data[0:2] != b"\x4e\x6f":
                    continue            # aux channel packets or other traffic
                if len(data) == expect_len and check(data):
                    return data
        raise BusError("no Etherbone reply from %s:%d" % self.addr)

    def probe(self):
        data = self._exchange(build_packet(probe=True), 8, lambda d: d[2] & 0x02)
        return data

    def read_many(self, addrs):
        out = []
        for i in range(0, len(addrs), MAX_WORDS):
            chunk = addrs[i:i + MAX_WORDS]
            n = len(chunk)
            data = self._exchange(build_packet(reads=chunk), 16 + 4 * n, lambda d: d[10] == n and d[11] == 0)
            out += list(struct.unpack(">%dI" % n, data[16:16 + 4 * n]))
        return out

    def read(self, addr, count=1):
        return self.read_many([addr + 4 * i for i in range(count)])

    def write(self, addr, values, verify=False):
        """Write consecutive words. With verify, the same packet reads them back (one reply)."""
        values = list(values)
        for i in range(0, len(values), MAX_WORDS):
            chunk = values[i:i + MAX_WORDS]
            base = addr + 4 * i
            if verify:
                reads = [base + 4 * j for j in range(len(chunk))]
                n = len(reads)
                data = self._exchange(build_packet(base, chunk, reads), 16 + 4 * n, lambda d: d[10] == n)
                back = list(struct.unpack(">%dI" % n, data[16:16 + 4 * n]))
                if back != [v & 0xFFFFFFFF for v in chunk]:
                    raise BusError("verify failed at 0x%08X: wrote %s, read %s"
                                   % (base, ["0x%08X" % v for v in chunk], ["0x%08X" % v for v in back]))
            else:
                self.sock.sendto(build_packet(base, chunk), self.addr)   # no reply for writes (as LiteEth)


def bits(value, names):
    s = [n for i, n in enumerate(names) if value & (1 << i)]
    return ", ".join(s) if s else "none"


def temperature_c(code):
    # as software/hermeslite/hermeslite.py: 3.26 V reference, 10 mV/degC, 0.5 V offset
    return (3.26 * (code / 4096.0) - 0.5) / 0.01


def cmd_dump(bus, args):
    names = [
        (REG_ID, "id"), (REG_VERSION, "version"), (REG_SCRATCH, "scratch"), (REG_CAPS, "capabilities"),
        (REG_EB_REQUESTS, "bridge requests"), (REG_EB_DROPS, "bridge drops"),
        (REG_EB_BUS_ERRORS, "bridge bus errors"), (REG_RX_GAIN, "rx gain"), (REG_TEMP, "temperature"),
        (REG_FWD, "forward power"), (REG_REV, "reverse power"), (REG_BIAS, "bias current"),
        (REG_INPUTS, "inputs"), (REG_TX_STATUS, "tx safety status"),
    ]
    vals = bus.read_many([a for a, _ in names])
    for (addr, name), v in zip(names, vals):
        extra = ""
        if addr == REG_ID:
            extra = "HL2B ok" if v == ID_VALUE else "UNEXPECTED"
        elif addr == REG_VERSION:
            extra = "gateware %d.%d, diag marker 0x%02X, register map %d" % (v >> 24, (v >> 16) & 0xFF, (v >> 8) & 0xFF, v & 0xFF)
        elif addr == REG_CAPS:
            extra = bits(v, CAPS_BITS)
        elif addr == REG_RX_GAIN:
            if v & 0x100:
                g = v & 0x7F
                extra = "last command 0x%02X = %d dB" % (g, (g & 0x3F) - 12) if g & 0x40 else "last command 0x%02X" % g
            else:
                extra = "no RX gain command since power-up"
            if v & 0x80000000:
                extra += ", bridge write pending"
        elif addr == REG_TEMP:
            extra = "%.1f degC" % temperature_c(v)
        elif addr == REG_INPUTS:
            extra = bits(v, INPUT_BITS)
        elif addr == REG_TX_STATUS:
            extra = bits(v, SAFETY_BITS)
        print("0x%08X  %-18s 0x%08X  %s" % (addr, name, v, extra))


def cmd_read(bus, args):
    vals = bus.read(args.addr, args.count)
    for i, v in enumerate(vals):
        print("0x%08X  0x%08X" % (args.addr + 4 * i, v))


def cmd_write(bus, args):
    bus.write(args.addr, args.values, verify=not args.no_verify)
    print("wrote %d word(s) at 0x%08X%s" % (len(args.values), args.addr, "" if args.no_verify else ", read back OK"))


def cmd_rxgain(bus, args):
    if not -12 <= args.db <= 48:
        sys.exit("RX gain must be -12 to 48 dB")
    code = 0x40 | (args.db + 12)
    bus.write(REG_RX_GAIN, [code])
    for _ in range(20):
        time.sleep(0.05)
        v = bus.read(REG_RX_GAIN)[0]
        if not v & 0x80000000 and (v & 0x17F) == (0x100 | code):
            print("RX gain %d dB (command 0x0A = 0x%02X) reached the command bus" % (args.db, code))
            return
    sys.exit("RX gain register reads 0x%08X, expected 0x%03X" % (v, 0x100 | code))


def cmd_scratch_test(bus, args):
    old = bus.read(REG_SCRATCH)[0]
    for v in (0xCAFEF00D, 0x00000000, 0xFFFFFFFF, 0x5A5AA5A5, old):
        bus.write(REG_SCRATCH, [v], verify=True)
    before = bus.read(REG_EB_BUS_ERRORS)[0]
    bus.write(REG_ID, [0])                        # read-only: must be refused
    id_after, errs = bus.read_many([REG_ID, REG_EB_BUS_ERRORS])
    if id_after != ID_VALUE or errs != before + 1:
        sys.exit("read-only check failed: id 0x%08X, bus errors %d -> %d" % (id_after, before, errs))
    print("scratch write/read OK; write to the read-only ID register refused (bus errors %d -> %d)" % (before, errs))


def decode_ilk(v):
    trips = [REASONS[i] for i in range(6) if v >> (8 + i) & 1]
    cuts = [REASONS[i] if i else "no-lease" for i in range(6) if v >> (16 + i) & 1]
    cfg = [n for i, n in enumerate(["pa-enable", "tr-disable", "vna"]) if v >> (24 + i) & 1]
    return "%s | trips: %s | cut-offs: %s | command 0x09: %s" % (bits(v & 0xFF, ILK_BITS), ", ".join(trips) or "none",
                                                                  ", ".join(cuts) or "none", ", ".join(cfg) or "none")


def cmd_front(bus, args):
    names = ["id", "tx permit", "interlock", "clear", "lease ms", "max key-down s", "temperature limit", "key-down time",
             "watchdog", "watchdog ms", "disarm", "cmd data", "cmd addr", "i2c xfer", "i2c status", "i2c data",
             "bias unlock", "led", "fan", "inputs", "adc cycles"]
    vals = bus.read(IO, len(names))
    for i, (name, v) in enumerate(zip(names, vals)):
        if name in ("clear", "disarm", "i2c xfer"):
            continue
        extra = ""
        if name == "id":
            extra = "IO01 ok" if v == IO_ID_VALUE else "UNEXPECTED (not a raw front-end image?)"
        elif name == "tx permit":
            extra = "last permission bits: " + bits(v, ["key", "ptt-keys", "cw-keys"])
        elif name == "interlock":
            extra = decode_ilk(v)
        elif name == "temperature limit":
            extra = "%.1f degC" % temperature_c(v)
        elif name == "key-down time":
            extra = "%d.%03d s" % (v >> 10, v & 0x3FF)
        elif name == "watchdog":
            extra = "%s%s, %d ms left" % ("FIRED, " if v >> 31 else "", "armed" if v >> 30 & 1 else "not armed", v & 0xFFFF)
        elif name == "cmd addr":
            extra = "%s, %d commands sent, last 0x%02X" % ("busy" if v >> 31 else "idle", v >> 8 & 0xFF, v & 0x3F)
        elif name == "i2c status":
            extra = "%s | done %d, refused or dropped %d" % (
                bits(v & 0x1F, ["busy", "last-nack", "last-refused-bias-guard", "last-dropped-busy", "request-pending"]),
                v >> 16 & 0xFF, v >> 24)
        elif name == "bias unlock":
            extra = "UNLOCKED" if v & 1 else "locked"
        elif name == "led":
            extra = "override %s, on %s" % (bits(v & 15, ["D2", "D3", "D4", "D5"]), bits(v >> 4 & 15, ["D2", "D3", "D4", "D5"]))
        elif name == "fan":
            extra = "minimum duty %d/16, HDL fan state %d%s" % (v & 15, v >> 8 & 7, ", band volts on the fan pin" if v >> 11 & 1 else "")
        elif name == "inputs":
            extra = "pins high: %s | active (debounced): %s" % (bits(v & 0x1FFF, PIN_BITS), bits(v >> 16, ["key", "ptt", "tx-inhibit"]))
        print("0x%08X  %-18s 0x%08X  %s" % (IO + 4 * i, name, v, extra))
    sb = bus.read(REG_TX_STATUS)[0]
    print("0x%08X  %-18s 0x%08X  %s" % (REG_TX_STATUS, "safety byte", sb, bits(sb, SAFETY_BITS_RAW)))


def wait_injector(bus, timeout=1.0):
    deadline = time.monotonic() + timeout
    while bus.read(IO_CMD_ADDR)[0] >> 31:
        if time.monotonic() > deadline:
            raise BusError("command injector busy")
        time.sleep(0.002)


def i2c_xfer(bus, bus_no, addr, reg=0, value=0, read=False, probe=False, timeout=1.0):
    """One I2C transfer through the register block. Returns (status, data): status 'ok', 'nack', 'refused'
    (bias guard), 'dropped' (I2C engine busy) or 'timeout'; data = bytes read (first byte in the low bits,
    a probe's byte in the top bits)."""
    st = bus.read(IO_I2C_STATUS)[0]
    done, ref = st >> 16 & 0xFF, st >> 24
    word = (bus_no << 30 | (1 << 24 if read or probe else 0) | (1 << 23 if probe else 0) | (addr & 0x7F) << 16
            | (reg & 0xFF) << 8 | (value & 0xFF))
    wait_injector(bus, timeout)
    bus.write(IO_I2C_XFER, [word], verify=False)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        st, data = bus.read_many([IO_I2C_STATUS, IO_I2C_RDATA])
        if st >> 16 & 0xFF != done:
            return ("nack" if st & 2 else "ok"), data
        if st >> 24 != ref:
            return ("refused" if st & 4 else "dropped"), 0
        time.sleep(0.002)
    return "timeout", 0


def cmd_i2c(bus, args):
    status, data = i2c_xfer(bus, args.bus, args.addr, args.reg, args.value or 0, read=args.read, probe=args.probe)
    if args.read or args.probe:
        b = data.to_bytes(4, "little")
        print("bus %d 0x%02X: %s, bytes read %s" % (args.bus, args.addr, status, (b[3:4] if args.probe else b).hex(" ")))
    else:
        print("bus %d 0x%02X register 0x%02X <- 0x%02X: %s" % (args.bus, args.addr, args.reg, args.value or 0, status))
    if status not in ("ok",):
        sys.exit(1)


def cmd_scan(bus, args):
    found = []
    for a in range(args.first, args.last + 1):
        status, _ = i2c_xfer(bus, args.bus, a, probe=True)
        if status == "ok":
            found.append(a)
        elif status != "nack":
            print("0x%02X: %s" % (a, status))
    print("bus %d: %d device(s) acknowledge: %s" % (args.bus, len(found), " ".join("0x%02X" % a for a in found) or "none"))


def cmd_cmd(bus, args):
    wait_injector(bus)
    n0 = bus.read(IO_CMD_ADDR)[0] >> 8 & 0xFF
    bus.write(IO_CMD_DATA, [args.value], verify=True)
    bus.write(IO_CMD_ADDR, [args.addr], verify=False)
    wait_injector(bus)
    v = bus.read(IO_CMD_ADDR)[0]
    ok = (v >> 8 & 0xFF) == (n0 + 1) & 0xFF and (v & 0x3F) == args.addr
    print("command 0x%02X = 0x%08X %s" % (args.addr, args.value, "on the command bus" if ok else "NOT sent (0x%08X)" % v))
    if not ok:
        sys.exit(1)


def cmd_led(bus, args):
    bus.write(IO_LED, [args.value], verify=True)
    print("LED register 0x%02X" % args.value)


def cmd_fan(bus, args):
    bus.write(IO_FAN, [args.duty & 15], verify=False)
    time.sleep(0.05)
    print("fan register 0x%08X" % bus.read(IO_FAN)[0])


def cmd_clear_trips(bus, args):
    bus.write(IO_ILK_CLEAR, [CLEAR_KEY], verify=False)
    time.sleep(0.05)
    print("interlock: " + decode_ilk(bus.read(IO_ILK_STATUS)[0]))


def cmd_wdog_disarm(bus, args):
    bus.write(IO_WDOG_DISARM, [1], verify=False)
    time.sleep(0.05)
    v = bus.read(IO_WDOG)[0]
    print("watchdog %s%s" % ("FIRED, " if v >> 31 else "", "armed" if v >> 30 & 1 else "not armed"))


def cmd_permit(bus, args):
    """Renew the transmit permission every 50 ms for a while. Without --key nothing transmits (lease only)."""
    end = time.monotonic() + args.seconds
    while time.monotonic() < end:
        bus.write(IO_TX_PERMIT, [PERMIT_KEY | (1 if args.key else 0)], verify=False)
        time.sleep(0.05)
    print("interlock while renewing: " + decode_ilk(bus.read(IO_ILK_STATUS)[0]))


def cmd_probe(bus, args):
    data = bus.probe()
    print("probe reply: %s" % data.hex(" "))


def main():
    p = argparse.ArgumentParser(description="HL2 front-end image register access (Etherbone over UDP port 1027).")
    p.add_argument("--ip", required=True, help="radio IP")
    p.add_argument("--ifaddr", help="local IP of the network card the radio is on")
    p.add_argument("--port", type=int, default=PORT)
    p.add_argument("--timeout", type=float, default=0.5)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("probe", help="Etherbone probe")
    sub.add_parser("dump", help="read and decode all registers")
    r = sub.add_parser("read", help="read words")
    r.add_argument("addr", type=lambda x: int(x, 0))
    r.add_argument("count", type=int, nargs="?", default=1)
    w = sub.add_parser("write", help="write words (read back unless --no-verify)")
    w.add_argument("addr", type=lambda x: int(x, 0))
    w.add_argument("values", type=lambda x: int(x, 0), nargs="+")
    w.add_argument("--no-verify", action="store_true")
    g = sub.add_parser("rxgain", help="set RX gain in dB (-12 to 48) through the bridge")
    g.add_argument("db", type=int)
    sub.add_parser("scratch-test", help="scratch write/read and read-only refusal test")
    sub.add_parser("front", help="hl2b5up_raw: decode the front-end register block and the safety byte")
    i = sub.add_parser("i2c", help="hl2b5up_raw: one I2C transfer (bus 1 clock chip, 2 filters/bias/IO board, 3 slow ADC: probe only)")
    i.add_argument("bus", type=int, choices=[1, 2, 3])
    i.add_argument("addr", type=lambda x: int(x, 0))
    i.add_argument("reg", type=lambda x: int(x, 0), nargs="?", default=0)
    i.add_argument("value", type=lambda x: int(x, 0), nargs="?")
    i.add_argument("--read", action="store_true", help="write the register pointer, read 4 bytes")
    i.add_argument("--probe", action="store_true", help="address only, one byte read (read-only)")
    sc = sub.add_parser("scan", help="hl2b5up_raw: address-only probes (read-only)")
    sc.add_argument("bus", type=int, choices=[1, 2, 3])
    sc.add_argument("--first", type=lambda x: int(x, 0), default=0x08)
    sc.add_argument("--last", type=lambda x: int(x, 0), default=0x77)
    c = sub.add_parser("cmd", help="hl2b5up_raw: put an openHPSDR command register write on the command bus")
    c.add_argument("addr", type=lambda x: int(x, 0))
    c.add_argument("value", type=lambda x: int(x, 0))
    le = sub.add_parser("led", help="hl2b5up_raw: LED register ([3:0] override D2..D5, [7:4] on)")
    le.add_argument("value", type=lambda x: int(x, 0))
    f = sub.add_parser("fan", help="hl2b5up_raw: minimum fan duty 0..15 (16ths, 15 = on)")
    f.add_argument("duty", type=int)
    sub.add_parser("clear-trips", help="hl2b5up_raw: clear latched interlock trips whose cause is gone")
    sub.add_parser("wdog-disarm", help="hl2b5up_raw: disarm the CPU watchdog and clear 'fired'")
    pm = sub.add_parser("permit", help="hl2b5up_raw: renew the transmit permission every 50 ms (no key: nothing transmits)")
    pm.add_argument("--seconds", type=float, default=1.0)
    pm.add_argument("--key", action="store_true", help="also request transmit (KEYS THE TRANSMITTER)")
    args = p.parse_args()

    bus = HL2Bus(args.ip, args.ifaddr, args.port, args.timeout)
    try:
        {"probe": cmd_probe, "dump": cmd_dump, "read": cmd_read, "write": cmd_write,
         "rxgain": cmd_rxgain, "scratch-test": cmd_scratch_test, "front": cmd_front, "i2c": cmd_i2c, "scan": cmd_scan,
         "cmd": cmd_cmd, "led": cmd_led, "fan": cmd_fan, "clear-trips": cmd_clear_trips, "wdog-disarm": cmd_wdog_disarm,
         "permit": cmd_permit}[args.cmd](bus, args)
    except BusError as e:
        sys.exit("ERROR: %s" % e)


if __name__ == "__main__":
    main()
