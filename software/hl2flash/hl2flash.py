#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Franz Schöning, https://www.schoning.com
"""Standalone Hermes Lite 2 gateware flasher. Python 3 standard library only.

Uses the same openHPSDR erase/program packets as software/hermeslite/hermeslite.py
(update_gateware, based on Quisk code by Jim N2ADR). Network update only rewrites the
application image; the factory image in flash is never touched.

  python hl2flash.py --ifaddr 169.254.1.1 discover
  python hl2flash.py --ifaddr 169.254.1.1 flash path/to/hl2b5up_xxx.rbf
  python hl2flash.py --ifaddr 169.254.1.1 flash --stable      # latest stable hl2b5up_main
"""

import argparse
import os
import select
import socket
import struct
import sys
import time

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
STABLE_DIR = os.path.join(REPO, "gateware", "bitfiles", "stable")
RBF_HEADER = bytes([0xFF] * 32 + [0x6A, 0xF7, 0xF7, 0xF7])


def decode(data):
    """Decode a 60-byte HL2 response. Returns dict or None."""
    if len(data) < 60 or data[0:2] != b"\xef\xfe":
        return None
    return {
        "type": data[2],
        "mac": ":".join("%02x" % b for b in data[3:9]),
        "gateware": "%d.%d" % (data[0x09], data[0x15]),
        "receivers": data[0x13],
        "board_id": data[0x14] & 0x3F,
        "diag_id": data[0x0C],   # 0 in stock and factory images; nonzero only in diagnostic builds
    }


def discover(ifaddr, timeout=1.5):
    """Broadcast openHPSDR discovery on ports 1025 and 1024. Returns list of (ip, info)."""
    found = {}
    for port in (1025, 1024):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        s.bind((ifaddr or "", 0))
        s.sendto(bytes([0xEF, 0xFE, 0x02] + [0] * 57), ("255.255.255.255", port))
        while select.select([s], [], [], timeout)[0]:
            data, addr = s.recvfrom(1024)
            info = decode(data)
            if info and addr[0] != ifaddr:
                found.setdefault(addr[0], info)
        s.close()
        if found:
            break
    return sorted(found.items())


class Radio:
    def __init__(self, ip, ifaddr):
        self.ip = ip
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((ifaddr or "", 0))

    def send(self, msg, timeout=2.0, attempts=3):
        for _ in range(attempts):
            self.sock.sendto(msg, (self.ip, 1024))
            end = time.monotonic() + timeout
            while True:
                left = end - time.monotonic()
                if left <= 0 or not select.select([self.sock], [], [], left)[0]:
                    break
                data, addr = self.sock.recvfrom(1024)
                if addr[0] == self.ip:
                    return decode(data)
        return None


def pick_radio(args):
    radios = discover(args.ifaddr)
    if args.ip:
        radios = [r for r in radios if r[0] == args.ip]
    if not radios:
        sys.exit("ERROR: no Hermes Lite 2 found%s." % (" at " + args.ip if args.ip else ""))
    if len(radios) > 1:
        sys.exit("ERROR: several radios found, choose one with --ip: " + ", ".join(r[0] for r in radios))
    return radios[0]


def show(ip, info):
    state = {2: "stopped", 3: "RUNNING"}.get(info["type"], "type %d" % info["type"])
    diag = "  diag image 0x%02X" % info["diag_id"] if info["diag_id"] else ""
    print("HL2 at %s  MAC %s  gateware %s  board %d  receivers %d  %s%s"
          % (ip, info["mac"], info["gateware"], info["board_id"], info["receivers"], state, diag))


def stable_rbf():
    with open(os.path.join(STABLE_DIR, "latest")) as f:
        version = f.read().strip()
    return os.path.join(STABLE_DIR, version, "hl2b5up_main", "hl2b5up_main.rbf")


def cmd_discover(args):
    radios = discover(args.ifaddr)
    if not radios:
        sys.exit("No Hermes Lite 2 found.")
    for ip, info in radios:
        show(ip, info)


def cmd_flash(args):
    path = stable_rbf() if args.stable else args.file
    if not path:
        sys.exit("ERROR: give an .rbf file or --stable.")
    if not path.lower().endswith(".rbf") or not os.path.isfile(path):
        sys.exit("ERROR: %s is not an existing .rbf file." % path)
    with open(path, "rb") as f:
        image = f.read()
    if image[:36] != RBF_HEADER:
        sys.exit("ERROR: %s does not start with a valid .rbf header." % path)

    ip, info = pick_radio(args)
    show(ip, info)
    if info["type"] != 2:
        sys.exit("ERROR: the radio is running. Stop the SDR program (or rawcap) first.")
    if "hl2b%d" % info["board_id"] not in os.path.basename(path) and not args.force:
        sys.exit("ERROR: radio board ID %d does not match file name %s (use --force to override)."
                 % (info["board_id"], os.path.basename(path)))

    blocks = (len(image) + 255) // 256
    print("File %s\n  %d bytes, %d blocks" % (path, len(image), blocks))
    if not args.yes:
        if input("Flash this file? Type yes: ").strip().lower() != "yes":
            sys.exit("Cancelled, nothing written.")

    radio = Radio(ip, args.ifaddr)
    print("Erasing application image (takes a few seconds)...")
    resp = radio.send(bytes([0xEF, 0xFE, 0x03, 0x02] + [0] * 56), timeout=10.0, attempts=1)
    if resp is None or resp["type"] != 3:
        sys.exit("ERROR: erase failed (%s). The radio still boots its factory image." %
                 ("no reply" if resp is None else "reply type %d" % resp["type"]))

    head = bytes([0xEF, 0xFE, 0x03, 0x01]) + struct.pack(">L", blocks)
    for block in range(blocks):
        chunk = image[block * 256:(block + 1) * 256]
        chunk += b"\xff" * (256 - len(chunk))
        resp = radio.send(head + chunk, timeout=10.0, attempts=1)
        if resp is None or resp["type"] != 4:
            sys.exit("\nERROR: programming failed at block %d of %d (%s). Power-cycle and flash again; "
                     "if the radio does not answer, power up with the key jack tip and ring grounded."
                     % (block, blocks, "no reply" if resp is None else "reply type %d" % resp["type"]))
        if block % 50 == 0 or block == blocks - 1:
            print("\r  programmed %d / %d blocks" % (block + 1, blocks), end="", flush=True)
    print("\nProgramming done. Waiting for the radio to restart...")
    wait_for_restart(args.ifaddr, ip, info)


def wait_for_restart(ifaddr, ip, before):
    """Wait for the radio to drop off the network and come back, then compare with `before`."""
    went_away = False
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        radios = [r for r in discover(ifaddr, timeout=0.7) if r[0] == ip or r[1]["mac"] == before["mac"]]
        if not radios:
            went_away = True
            continue
        if not went_away:
            continue
        rip, rinfo = radios[0]
        show(rip, rinfo)
        if (rinfo["gateware"], rinfo["receivers"], rinfo["diag_id"]) == (before["gateware"], before["receivers"], before["diag_id"]):
            print("WARNING: the radio restarted but reports the same version and receiver count as before.\n"
                  "  If the new image should differ, it failed to start and the radio fell back to its\n"
                  "  factory image. The factory image then ignores new flashes until a full power cycle.")
            sys.exit(2)
        print("SUCCESS: radio restarted with gateware %s, %d receivers." % (rinfo["gateware"], rinfo["receivers"]))
        return
    if not went_away:
        sys.exit("WARNING: the radio never restarted after programming. Power-cycle it and run discover.")
    sys.exit("WARNING: radio did not come back within 90 s. Power-cycle it and run discover.")


def cmd_reboot(args):
    ip, info = pick_radio(args)
    show(ip, info)
    if info["type"] != 2:
        sys.exit("ERROR: the radio is running; it only reboots when stopped.")
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind((args.ifaddr or "", 0))
    s.sendto(bytes([0xEF, 0xFE, 0x05, 0x7F, 0x3A << 1, 0, 0, 0, 1] + [0] * 51), (ip, 1025))
    print("Reboot sent. Waiting for the radio to restart...")
    wait_for_restart(args.ifaddr, ip, dict(info, gateware=None))


def main():
    p = argparse.ArgumentParser(description="Standalone Hermes Lite 2 gateware flasher.")
    p.add_argument("--ifaddr", help="local IP of the network card the radio is on, e.g. 169.254.1.1")
    p.add_argument("--ip", help="radio IP, if more than one radio answers")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("discover", help="list radios with gateware version")
    sub.add_parser("reboot", help="reboot a stopped radio over the network")
    f = sub.add_parser("flash", help="flash an .rbf file")
    f.add_argument("file", nargs="?", help=".rbf file to flash")
    f.add_argument("--stable", action="store_true", help="flash the latest stable hl2b5up_main from this repo")
    f.add_argument("--yes", action="store_true", help="do not ask for confirmation")
    f.add_argument("--force", action="store_true", help="skip the board-ID file name check")
    args = p.parse_args()
    {"discover": cmd_discover, "flash": cmd_flash, "reboot": cmd_reboot}[args.cmd](args)


if __name__ == "__main__":
    main()
