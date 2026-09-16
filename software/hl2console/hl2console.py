#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Franz Schöning, https://www.schoning.com
"""Network console for firmware on the Hermes-Lite 2 raw front-end image (hl2b5up_raw). Standard library only.

Shows the boot ROM console (datagrams 0x01 'C' + text from UDP port 1027) and sends command lines to an
application that reads them, such as the radio health console example (firmware/hl2neo/health): each line
goes out as one datagram, 0x02 followed by the text. Protocol: docs/rawfront/RISCV.md.

Examples (radio 169.254.19.221, PC address 169.254.202.183):
  hl2console.py --ip 169.254.19.221 --ifaddr 169.254.202.183                interactive (Ctrl-C or "quit")
  hl2console.py --ip 169.254.19.221 --cmd "scan" --cmd "status" --wait 4     send commands, print, exit
  hl2console.py --ip 169.254.19.221 --seconds 10                             only listen

The radio answers the PC address and port that sent to port 1027 last: do not run gdb, hl2fw.py or hl2bus.py
at the same time.
"""

import argparse
import select
import socket
import sys
import threading
import time

PORT = 1027


class Console:
    def __init__(self, ip, ifaddr, port=PORT):
        self.addr = (ip, port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((ifaddr or "", 0))

    def attach(self, replay):
        """0x01 'A' attaches the console (and leaves gdb mode); the boot ROM then replays the last 256 bytes
        it kept. Without replay that output is read and dropped."""
        self.sock.sendto(b"\x01A", self.addr)
        self.pump(0.5, show=replay)

    def send_line(self, text):
        self.sock.sendto(b"\x02" + text.encode("ascii", "replace")[:94], self.addr)

    def pump(self, seconds, show=True):
        """Print console output for this many seconds."""
        end = time.monotonic() + seconds
        while True:
            left = end - time.monotonic()
            if left <= 0:
                return
            if not select.select([self.sock], [], [], min(left, 0.2))[0]:
                continue
            data, src = self.sock.recvfrom(2048)
            if show and src[0] == self.addr[0] and len(data) >= 2 and data[0] == 0x01 and data[1] == ord("C"):
                sys.stdout.write(data[2:].decode("latin-1"))
                sys.stdout.flush()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ip", required=True, help="radio IP address")
    ap.add_argument("--ifaddr", default="", help="local IP address to send from")
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--cmd", action="append", default=[], help="command line to send (repeatable); exit afterwards")
    ap.add_argument("--wait", type=float, default=2.0, help="seconds of output to show after each --cmd (default 2)")
    ap.add_argument("--seconds", type=float, default=None, help="listen this long, then exit")
    ap.add_argument("--replay", action="store_true", help="show the output the boot ROM kept before attaching")
    args = ap.parse_args()

    con = Console(args.ip, args.ifaddr, args.port)
    con.attach(args.replay)

    if args.cmd or args.seconds is not None:
        for c in args.cmd:
            con.send_line(c)
            con.pump(args.wait)
        if args.seconds:
            con.pump(args.seconds)
        return

    lines = []
    lock = threading.Lock()

    def reader():
        for text in sys.stdin:
            with lock:
                lines.append(text.rstrip("\r\n"))

    threading.Thread(target=reader, daemon=True).start()
    print("console for %s:%d; type commands (help), Ctrl-C or quit to exit" % con.addr)
    try:
        while True:
            con.pump(0.1)
            with lock:
                pending, lines[:] = lines[:], []
            for text in pending:
                if text.strip() in ("quit", "exit"):
                    return
                con.send_line(text)
    except KeyboardInterrupt:
        print()


if __name__ == "__main__":
    main()
