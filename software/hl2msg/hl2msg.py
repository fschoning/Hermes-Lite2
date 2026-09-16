#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Franz Schöning, https://www.schoning.com
"""Message-layer client for the Hermes-Lite 2 raw front-end image (hl2b5up_raw) with its firmware
(firmware/hl2neo/msg). Standard library only.

Talks to the firmware on UDP port 1027 (datagrams starting "HM"): reliable requests (executed exactly
once: repeated requests get the cached response), unreliable requests (transmit permission renewal),
telemetry and reliable events. Protocol and message set: docs/rawfront/PROTOCOL.md.
Everything here also works without the firmware through the register bridge (software/hl2bus/hl2bus.py).

Examples (radio 169.254.19.221, PC address 169.254.202.183):
  hl2msg.py --ip 169.254.19.221 --ifaddr 169.254.202.183 hello
  hl2msg.py --ip ... read 0x40040000 4
  hl2msg.py --ip ... scan 2
  hl2msg.py --ip ... i2c 2 0x20 --read 0x09
  hl2msg.py --ip ... cmd 0x0a 0x5f
  hl2msg.py --ip ... telemetry --seconds 3
  hl2msg.py --ip ... permit --seconds 2          renew the permission without key (nothing transmits)
  hl2msg.py --ip ... loss-test --drop 0.2 --count 200
"""

import argparse
import os
import random
import select
import socket
import struct
import sys
import time

PORT = 1027
F_RELIABLE, F_ACK_VALID, F_RESET = 1, 2, 4
C_SYS, C_REG, C_I2C, C_RF, C_TELEMETRY, C_EVENT = 0, 1, 2, 3, 5, 6
STATUS = {0: "ok", 0x10: "unknown request", 0x11: "bad length", 0x12: "refused", 0x13: "busy"}
I2C_STATUS = {0: "ok", 1: "nack", 2: "refused (bias guard)", 3: "dropped (I2C busy)", 4: "timeout"}
ILK_BITS = ["TX-ON", "PA-STAGE-ON", "lease-valid", "tx-requested", "TRIP-LATCHED", "cut-off-present", "key-bit"]
REASONS = ["lease-expired-while-keyed", "over-temperature", "tx-inhibit", "cpu-watchdog", "max-key-down", "temperature-stale"]


class MsgError(Exception):
    pass


def bits(v, names):
    s = [n for i, n in enumerate(names) if v >> i & 1]
    return ", ".join(s) if s else "none"


def decode_ilk(v):
    trips = [REASONS[i] for i in range(6) if v >> (8 + i) & 1]
    cuts = [REASONS[i] if i else "no-lease" for i in range(6) if v >> (16 + i) & 1]
    return "%s | trips: %s | cut-offs: %s" % (bits(v & 0xFF, ILK_BITS), ", ".join(trips) or "none", ", ".join(cuts) or "none")


def temperature_c(code):
    return (3.26 * (code / 4096.0) - 0.5) / 0.01


class Session:
    """One message-layer session. drop_tx / drop_rx simulate datagram loss (probability 0..1)."""

    def __init__(self, ip, ifaddr=None, port=PORT, drop_tx=0.0, drop_rx=0.0):
        self.addr = (ip, port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((ifaddr or "", 0))
        self.seq = random.randint(1, 60000)
        self.first = True
        self.tag = 0
        self.drop_tx = drop_tx
        self.drop_rx = drop_rx
        self.boot_id = None
        self.ev_seq = 0
        self.telemetry = []
        self.events = []
        self.sent = self.dropped_tx = self.dropped_rx = self.retransmits = 0
        self.tries = 6

    # ------------------------------------------------------------------ wire
    def _header(self, flags, seq, payload):
        return struct.pack("<2sBBIHHHH", b"HM", 1, flags | F_ACK_VALID, 0, seq & 0xFFFF, self.ev_seq & 0xFFFF,
                           len(payload), 0) + payload

    def _send(self, data):
        self.sent += 1
        if self.drop_tx and random.random() < self.drop_tx:
            self.dropped_tx += 1
            return
        self.sock.sendto(data, self.addr)

    def _recv(self, timeout):
        """Next HM packet (flags, seq, ack, payload) or None. Telemetry and events are handled here."""
        end = time.monotonic() + timeout
        while True:
            left = end - time.monotonic()
            if left <= 0 or not select.select([self.sock], [], [], left)[0]:
                return None
            data, src = self.sock.recvfrom(2048)
            if len(data) < 16 or data[:2] != b"HM" or src[0] != self.addr[0]:
                continue
            if self.drop_rx and random.random() < self.drop_rx:
                self.dropped_rx += 1
                continue
            _, ver, flags, boot, seq, ack, n, _ = struct.unpack_from("<2sBBIHHHH", data)
            payload = data[16:16 + n]
            if self.boot_id is not None and boot != self.boot_id:
                print("hl2msg: radio firmware restarted (boot id %08x -> %08x)" % (self.boot_id, boot))
            self.boot_id = boot
            if payload[:1] == bytes([C_TELEMETRY]):
                self.telemetry.append((time.monotonic(), payload[6:]))
                continue
            if payload[:1] == bytes([C_EVENT]):
                if flags & F_RELIABLE:
                    if seq != self.ev_seq:
                        self.events.append((time.monotonic(), payload[6:]))
                    self.ev_seq = seq
                    self._send(self._header(0, 0, b""))          # bare ACK
                continue
            return flags, seq, ack, payload

    @staticmethod
    def parse_messages(payload):
        out, i = [], 0
        while i + 6 <= len(payload):
            cls, op, tag, n = struct.unpack_from("<BBHH", payload, i)
            out.append((cls, op, tag, payload[i + 6:i + 6 + n]))
            i += 6 + n
        return out

    def request(self, cls, op, body=b"", reliable=True, first_wait=0.05, tries=None):
        """Send one request, return (status, response body without status)."""
        self.tag = (self.tag + 1) & 0xFFFF
        msg = struct.pack("<BBHH", cls, op, self.tag, len(body)) + body
        if reliable:
            self.seq = (self.seq + 1) & 0xFFFF or 1
            pkt = self._header(F_RELIABLE | (F_RESET if self.first else 0), self.seq, msg)
        else:
            pkt = self._header(0, 0, msg)
        wait = first_wait
        tries = tries or self.tries
        for attempt in range(tries):
            if attempt:
                self.retransmits += 1
            self._send(pkt)
            end = time.monotonic() + wait
            while True:
                r = self._recv(max(0.0, end - time.monotonic()))
                if r is None:
                    break
                flags, seq, ack, payload = r
                if reliable and ack != self.seq:
                    continue
                for c, o, t, b in self.parse_messages(payload):
                    if c == cls and o == op | 0x80 and t == self.tag:
                        self.first = False
                        return b[0], b[1:]
            wait = min(wait * 2, 0.8)
        raise MsgError("no response to class %d op %d after %d tries" % (cls, op, tries))

    def poll(self, seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self._recv(end - time.monotonic())

    # ------------------------------------------------------------------ requests
    def hello(self):
        st, b = self.request(C_SYS, 1)
        proto, gw, fw, caps, maxpay, tele, io = struct.unpack_from("<B2xIIIHHI", b)
        return dict(status=st, protocol=proto, gateware=gw, firmware=fw, caps=caps, max_payload=maxpay,
                    telemetry_ms=tele, io_id=io)

    def read(self, addr, count=1):
        st, b = self.request(C_REG, 1, struct.pack("<IB", addr, count))
        if st:
            raise MsgError("read 0x%08x: %s" % (addr, STATUS.get(st, st)))
        return list(struct.unpack("<%dI" % count, b[:4 * count]))

    def write(self, addr, values):
        st, b = self.request(C_REG, 2, struct.pack("<I%dI" % len(values), addr, *values))
        return st, b[0] if b else 0

    def i2c(self, bus, addr, reg=0, value=0, read=False, probe=False):
        st, b = self.request(C_I2C, 1, struct.pack("<BBBBB", bus, addr, (1 if read else 0) | (2 if probe else 0), reg, value),
                             first_wait=0.3)
        if st:
            raise MsgError("i2c: %s" % STATUS.get(st, st))
        return b[0], struct.unpack_from("<I", b, 1)[0]

    def scan(self, bus, first=0x08, last=0x77):
        st, b = self.request(C_I2C, 2, struct.pack("<BBB", bus, first, last), first_wait=2.0, tries=3)
        found = [a for a in range(first, last + 1) if b[a // 8] >> (a % 8) & 1]
        return st, found

    def cmd(self, addr, value):
        st, _ = self.request(C_RF, 4, struct.pack("<BI", addr, value))
        return st

    def permit(self, flags=0):
        st, b = self.request(C_RF, 1, bytes([flags]), reliable=False, tries=1)
        return st, struct.unpack_from("<I", b)[0]

    def clear_trips(self):
        st, b = self.request(C_RF, 2)
        return st, struct.unpack_from("<I", b)[0]

    def set_telemetry(self, period_ms):
        return self.request(C_SYS, 3, struct.pack("<H", period_ms))[0]


def decode_telemetry(t):
    count, ms, temp, fwd, rev, bias, inputs, ilk, i2c, fan, keytime, misc = struct.unpack_from("<IIHHHHIIIIII", t)
    return ("#%d t=%d ms temp %.1f C (code %d) fwd %d rev %d bias %d | inputs 0x%05x | interlock %s | i2c done %d | fan 0x%03x | "
            "safety 0x%02x" % (count, ms, temperature_c(temp), temp, fwd, rev, bias, inputs, decode_ilk(ilk), i2c >> 16 & 0xFF,
                               fan, misc & 0xFF))


# ---------------------------------------------------------------------------- commands

def cmd_hello(s, a):
    h = s.hello()
    gw = h["gateware"]
    print("firmware %08x, protocol %d, gateware %d.%d marker 0x%02X, capabilities 0x%X, max payload %d, telemetry %d ms, "
          "register block %s, boot id %08x" % (h["firmware"], h["protocol"], gw >> 24, gw >> 16 & 0xFF, gw >> 8 & 0xFF, h["caps"],
                                                h["max_payload"], h["telemetry_ms"], "IO01" if h["io_id"] == 0x494F3031 else hex(h["io_id"]),
                                                s.boot_id))


def cmd_read(s, a):
    for i, v in enumerate(s.read(a.addr, a.count)):
        print("0x%08X  0x%08X" % (a.addr + 4 * i, v))


def cmd_write(s, a):
    st, n = s.write(a.addr, a.values)
    print("%s, %d word(s) written" % (STATUS.get(st, st), n))


def cmd_i2c(s, a):
    if a.write is not None:
        st, d = s.i2c(a.bus, a.addr, a.write[0], a.write[1])
    elif a.read is not None:
        st, d = s.i2c(a.bus, a.addr, a.read, read=True)
    else:
        st, d = s.i2c(a.bus, a.addr, probe=True)
    print("bus %d 0x%02X: %s, data %s" % (a.bus, a.addr, I2C_STATUS.get(st, st), d.to_bytes(4, "little").hex(" ")))


def cmd_scan(s, a):
    st, found = s.scan(a.bus, a.first, a.last)
    print("bus %d: %s%s" % (a.bus, " ".join("0x%02X" % x for x in found) or "none", "" if st == 0 else " (%s)" % STATUS.get(st, st)))


def cmd_cmd(s, a):
    print("command 0x%02X = 0x%08X: %s" % (a.addr, a.value, STATUS.get(s.cmd(a.addr, a.value), "?")))


def cmd_telemetry(s, a):
    s.hello()
    s.poll(a.seconds)
    for t, body in s.telemetry:
        print(decode_telemetry(body))
    print("%d telemetry packets in %.1f s" % (len(s.telemetry), a.seconds))


def cmd_events(s, a):
    s.hello()
    s.poll(a.seconds)
    for t, body in s.events:
        ilk, inputs, ms = struct.unpack_from("<III", body)
        print("event t=%d ms: interlock %s | debounced inputs %s" % (ms, decode_ilk(ilk), bits(inputs >> 16, ["key", "ptt", "tx-inhibit"])))


def cmd_permit(s, a):
    s.hello()
    end = time.monotonic() + a.seconds
    ilk = 0
    while time.monotonic() < end:
        try:
            st, ilk = s.permit(0)
        except MsgError:
            pass
        time.sleep(0.05)
    print("interlock while renewing (no key): " + decode_ilk(ilk))


def cmd_loss_test(s, a):
    """Reliable command-bus writes with datagram loss both ways: every command must execute exactly once.
    Counts the injector's command counter (register block CMD_ADDR [15:8]) before and after without loss."""
    clean = Session(a.ip, a.ifaddr)
    before = clean.read(0x40040030)[0] >> 8 & 0xFF
    del clean
    s.drop_tx = s.drop_rx = a.drop
    s.tries = 12
    ok = 0
    t0 = time.monotonic()
    for i in range(a.count):
        if s.cmd(0x0A, a.value) == 0:
            ok += 1
    dt = time.monotonic() - t0
    s.drop_tx = s.drop_rx = 0.0
    after = s.read(0x40040030)[0] >> 8 & 0xFF
    executed = (after - before) & 0xFF
    print("%d commands in %.1f s with %.0f %% loss each way: %d answered ok, %d executed on the radio (counter mod 256), "
          "%d datagrams sent, %d dropped going out, %d responses dropped, %d retransmissions"
          % (a.count, dt, a.drop * 100, ok, executed, s.sent, s.dropped_tx, s.dropped_rx, s.retransmits))
    good = ok == a.count and executed == a.count % 256
    print("LOSS TEST %s (each command executed exactly once)" % ("PASS" if good else "FAIL"))
    if not good:
        sys.exit(1)


def main():
    p = argparse.ArgumentParser(description="HL2 raw front-end message-layer client (firmware on UDP port 1027).")
    p.add_argument("--ip", required=True)
    p.add_argument("--ifaddr")
    p.add_argument("--port", type=int, default=PORT)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("hello")
    r = sub.add_parser("read")
    r.add_argument("addr", type=lambda x: int(x, 0))
    r.add_argument("count", type=int, nargs="?", default=1)
    w = sub.add_parser("write")
    w.add_argument("addr", type=lambda x: int(x, 0))
    w.add_argument("values", type=lambda x: int(x, 0), nargs="+")
    i = sub.add_parser("i2c", help="probe by default; --read REG (4 bytes) or --write REG VALUE")
    i.add_argument("bus", type=int, choices=[1, 2, 3])
    i.add_argument("addr", type=lambda x: int(x, 0))
    i.add_argument("--read", type=lambda x: int(x, 0))
    i.add_argument("--write", type=lambda x: int(x, 0), nargs=2)
    sc = sub.add_parser("scan")
    sc.add_argument("bus", type=int, choices=[1, 2, 3])
    sc.add_argument("--first", type=lambda x: int(x, 0), default=0x08)
    sc.add_argument("--last", type=lambda x: int(x, 0), default=0x77)
    c = sub.add_parser("cmd")
    c.add_argument("addr", type=lambda x: int(x, 0))
    c.add_argument("value", type=lambda x: int(x, 0))
    t = sub.add_parser("telemetry")
    t.add_argument("--seconds", type=float, default=2.0)
    e = sub.add_parser("events")
    e.add_argument("--seconds", type=float, default=5.0)
    pm = sub.add_parser("permit", help="renew the transmit permission without key (nothing transmits)")
    pm.add_argument("--seconds", type=float, default=1.0)
    lt = sub.add_parser("loss-test")
    lt.add_argument("--drop", type=float, default=0.2)
    lt.add_argument("--count", type=int, default=100)
    lt.add_argument("--value", type=lambda x: int(x, 0), default=0x5F, help="RX gain command value repeated (default 0x5F)")
    a = p.parse_args()
    s = Session(a.ip, a.ifaddr, a.port)
    try:
        {"hello": cmd_hello, "read": cmd_read, "write": cmd_write, "i2c": cmd_i2c, "scan": cmd_scan, "cmd": cmd_cmd,
         "telemetry": cmd_telemetry, "events": cmd_events, "permit": cmd_permit, "loss-test": cmd_loss_test}[a.cmd](s, a)
    except MsgError as ex:
        sys.exit("hl2msg: %s" % ex)


if __name__ == "__main__":
    main()
