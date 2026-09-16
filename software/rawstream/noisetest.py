#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Franz Schöning, https://www.schoning.com
"""noisetest.py -- one-command receiver noise test for the HL2 raw front-end image: does streaming at full
rate over the radio's own Ethernet port raise the noise floor or add spurs?

For each RX gain it:
  1. sets the gain (openHPSDR command 0x0A on UDP port 1025),
  2. captures real ADC samples three times with rawcap:
       quiet   quiet-capture mode: the radio records 8,192 contiguous samples (its FIFO depth) while its Ethernet sender is
               idle, then sends them (so the samples were taken with no send traffic)
       loaded  the normal full-rate stream (about 930 Mbit/s on the wire while the samples are taken)
       repeat  quiet-capture again: shows how much the result moves between two identical captures
  3. averages spectra with 4,096-sample segments (18.75 kHz bins). Frames are exactly 4,096 samples
     (--ip-mtu 6192), so every segment is one received frame and a lost frame never splices two pieces of
     signal into one segment,
  4. reports, per amateur band below Nyquist (38.4 MHz) and per other notable block, the median floor of the
     band (spurs excluded) and the change loaded - quiet and repeat - quiet in dB. A whole-band median is
     NOT used for the verdict: an Ethernet-related rise confined to a few MHz is invisible in it,
  5. lists spurs more than 6 dB above their band floor that appear in the loaded capture but not in quiet,
  6. writes a PNG (spectra, band shading, per-band differences) and a Markdown table.

Needs: numpy, matplotlib; rawcap built (software/rawstream/rawcap, cargo build --release); a NIC with jumbo
frames of at least 6,210 bytes (Windows "Jumbo Frame" 9014). Put a 50-ohm dummy load on the antenna port.

Example:
  python noisetest.py --ip 169.254.19.221 --local-ip 169.254.202.183 --gain 20 --gain 48 --out noise_out

Verdict per gain: PASS if no amateur band moves more than --band-limit dB (default 1.0) and no new spur more
than 6 dB above the floor appears in an amateur band. Other blocks are reported, not judged.
"""

import argparse
import datetime
import json
import os
import shutil
import socket
import subprocess
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
FS = 76_800_000.0
NYQUIST = FS / 2
SEG = 4096
FULL_SCALE = 2047.0

# Amateur bands (IARU region-independent outer edges, MHz). 6 m (50-54 MHz) is above Nyquist: it aliases to
# 22.8-26.8 MHz and cannot be measured separately without the HL2's own filters, so it is not listed.
BANDS = [
    ("160 m", 1.800, 2.000), ("80 m", 3.500, 4.000), ("60 m", 5.250, 5.450), ("40 m", 7.000, 7.300),
    ("30 m", 10.100, 10.150), ("20 m", 14.000, 14.350), ("17 m", 18.068, 18.168), ("15 m", 21.000, 21.450),
    ("12 m", 24.890, 24.990), ("10 m", 28.000, 29.700),
]
# Other blocks worth watching (reported, not judged)
BLOCKS = [
    ("0.5-1.7 MHz (MW broadcast)", 0.5, 1.7),
    ("15.0-17.5 MHz (Ethernet-sensitive)", 15.0, 17.5),
    ("19.4-19.8 MHz (250 - 3x76.8 MHz)", 19.4, 19.8),
    ("24.8-25.2 MHz (CPU clock 25 MHz)", 24.8, 25.2),
    ("28.4-28.8 MHz (125 - 76.8 MHz)", 28.4, 28.8),
    ("30-38 MHz (above 10 m)", 30.0, 38.0),
    ("1-30 MHz (whole HF, reference only)", 1.0, 30.0),
]


def blackman_harris(n):
    k = np.arange(n)
    return (0.35875 - 0.48829 * np.cos(2 * np.pi * k / (n - 1)) + 0.14128 * np.cos(4 * np.pi * k / (n - 1))
            - 0.01168 * np.cos(6 * np.pi * k / (n - 1)))


def unpack(path):
    """rawcap --save file: packed 12-bit samples, 2 per 3 bytes, big-endian (docs/rawfront/PROTOCOL.md)."""
    raw = np.fromfile(path, dtype=np.uint8)
    n = raw.size // 3
    t = raw[:n * 3].reshape(n, 3).astype(np.int32)
    a = (t[:, 0] << 4) | (t[:, 1] >> 4)
    b = ((t[:, 1] & 0x0F) << 8) | t[:, 2]
    s = np.empty(n * 2, dtype=np.int32)
    s[0::2], s[1::2] = a, b
    return np.where(s & 0x800, s - 4096, s).astype(np.int16)


def spectrum(samples, max_segments):
    n = min(max_segments, samples.size // SEG)
    if n < 10:
        raise SystemExit("capture too short: %d samples" % samples.size)
    w = blackman_harris(SEG)
    ref = (FULL_SCALE * SEG * (w.sum() / SEG) / 2.0) ** 2
    acc = np.zeros(SEG // 2 + 1)
    for i in range(0, n, 256):
        k = min(256, n - i)
        seg = samples[i * SEG:(i + k) * SEG].astype(np.float64).reshape(k, SEG) * w
        acc += (np.abs(np.fft.rfft(seg, axis=1)) ** 2).sum(axis=0)
    p = 10 * np.log10(np.maximum(acc / n, 1e-30) / ref)
    return np.fft.rfftfreq(SEG, 1 / FS), p, n


def band_floor(f, p, lo, hi):
    """Median of the band's bins, then again without bins more than 6 dB above that median."""
    m = (f >= lo * 1e6) & (f <= hi * 1e6)
    v = p[m]
    med = np.median(v)
    keep = v < med + 6.0
    if keep.sum() >= max(2, v.size // 2):
        med = np.median(v[keep])
    return med, m


def spurs(f, p, lo, hi, floor, above=6.0):
    idx = np.where((f >= lo * 1e6) & (f <= hi * 1e6))[0]
    out = set()
    for i in idx:
        if 2 <= i < p.size - 2 and p[i] - floor > above and p[i] >= p[i - 1] and p[i] >= p[i + 1]:
            out.add(int(i))
    return out


def set_gain(ip, local_ip, db):
    code = 0x40 | (db + 12)
    pkt = bytes([0xEF, 0xFE, 0x05, 0x7F, 0x0A << 1, 0, 0, 0, code]) + bytes(51)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind((local_ip or "", 0))
    s.settimeout(0.5)
    for _ in range(5):
        s.sendto(pkt, (ip, 1025))
        try:
            data, _ = s.recvfrom(1024)
            if data[:2] == b"\xef\xfe":
                return code
        except socket.timeout:
            pass
    raise SystemExit("no reply to the RX gain command from %s" % ip)


def capture(args, path, quiet):
    cmd = [args.rawcap, "--ip", args.ip, "--local-ip", args.local_ip, "--ip-mtu", "6192", "--mode", "adc",
           "--seconds", str(args.seconds + 1.0), "--save", path, "--save-seconds", str(args.seconds)]
    if quiet:
        cmd.insert(-4, "--quiet-capture")
    t0 = time.monotonic()
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(path):
        sys.stdout.write(r.stdout[-2000:] + r.stderr[-2000:])
        raise SystemExit("rawcap failed (%s)" % " ".join(cmd))
    summary = [l for l in r.stdout.splitlines() if "frames" in l.lower() and ("lost" in l.lower() or "received" in l.lower())]
    print("    %-7s %5.1f s, %s" % ("quiet" if quiet else "loaded", time.monotonic() - t0,
                                    summary[-1].strip() if summary else "%d bytes" % os.path.getsize(path)))


def analyse_gain(args, db, files):
    specs = {}
    for name, path in files.items():
        f, p, n = spectrum(unpack(path), args.max_segments)
        specs[name] = p
        print("    %-7s %d segments averaged" % (name, n))
    rows = []
    for kind, table in (("band", BANDS), ("block", BLOCKS)):
        for label, lo, hi in table:
            fq, _ = band_floor(f, specs["quiet"], lo, hi)
            fl, _ = band_floor(f, specs["loaded"], lo, hi)
            fr, _ = band_floor(f, specs["repeat"], lo, hi)
            new = sorted(spurs(f, specs["loaded"], lo, hi, fl) - spurs(f, specs["quiet"], lo, hi, fq)
                         - spurs(f, specs["repeat"], lo, hi, fr))
            rows.append(dict(kind=kind, label=label, lo=lo, hi=hi, quiet=fq, loaded_d=fl - fq, repeat_d=fr - fq,
                             new_spurs=[(f[i] / 1e6, specs["loaded"][i] - fl) for i in new]))
    return f, specs, rows


def verdict(rows, limit):
    bad = [r for r in rows if r["kind"] == "band" and (abs(r["loaded_d"]) > limit or r["new_spurs"])]
    return "PASS" if not bad else "FAIL (%s)" % ", ".join(r["label"] for r in bad)


def table_text(rows):
    lines = ["| Band or block | MHz | Quiet floor (dBFS/bin) | Loaded - quiet (dB) | Repeat - quiet (dB) | New spurs > 6 dB |",
             "|---|---|---|---|---|---|"]
    for r in rows:
        sp = ", ".join("%.3f MHz +%.1f dB" % s for s in r["new_spurs"]) or "none"
        lines.append("| %s | %.3f-%.3f | %.1f | %+.2f | %+.2f | %s |" % (r["label"], r["lo"], r["hi"], r["quiet"],
                                                                     r["loaded_d"], r["repeat_d"], sp))
    return "\n".join(lines)


def plot(path, db, f, specs, rows, title):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, (ax, bx) = plt.subplots(2, 1, figsize=(12, 8.5), gridspec_kw={"height_ratios": [3, 2]})
    mhz = f / 1e6
    ax.plot(mhz, specs["quiet"], lw=0.6, color="#1f77b4", label="quiet capture (sender idle)")
    ax.plot(mhz, specs["loaded"], lw=0.6, color="#d62728", alpha=0.75, label="full-rate stream")
    for label, lo, hi in BANDS:
        ax.axvspan(lo, hi, color="#2ca02c", alpha=0.15, lw=0)
    ax.axvspan(15.0, 17.5, color="#ff7f0e", alpha=0.10, lw=0)
    ax.set_xlim(0, NYQUIST / 1e6)
    lo_y = np.percentile(specs["quiet"][10:], 1) - 5
    ax.set_ylim(lo_y, max(lo_y + 40, np.percentile(specs["quiet"][10:], 99.9) + 10))
    ax.set_xlabel("MHz (green: amateur bands, orange: 15.0-17.5 MHz block)")
    ax.set_ylabel("dBFS per 18.75 kHz bin")
    ax.set_title(title)
    ax.legend(loc="upper right")
    ax.grid(alpha=0.3)
    labels = [r["label"].split(" (")[0] for r in rows]
    x = np.arange(len(rows))
    bx.bar(x - 0.2, [r["loaded_d"] for r in rows], 0.4, color="#d62728", label="loaded - quiet")
    bx.bar(x + 0.2, [r["repeat_d"] for r in rows], 0.4, color="#7f7f7f", label="repeat quiet - quiet")
    bx.axhline(1.0, color="k", ls=":", lw=0.8)
    bx.axhline(-1.0, color="k", ls=":", lw=0.8)
    bx.set_xticks(x)
    bx.set_xticklabels(labels, rotation=35, ha="right", fontsize=8)
    bx.set_ylabel("floor change, dB")
    bx.legend(loc="upper left")
    bx.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ip", required=True, help="radio IP")
    ap.add_argument("--local-ip", required=True, help="local IP of the network card the radio is on")
    ap.add_argument("--gain", type=int, action="append", help="RX gain in dB, -12 to 48 (repeatable; default 48)")
    ap.add_argument("--seconds", type=float, default=2.0, help="seconds saved per capture (default 2)")
    ap.add_argument("--max-segments", type=int, default=20000, help="segments averaged per capture (default 20000)")
    ap.add_argument("--band-limit", type=float, default=1.0, help="PASS limit for an amateur band's floor change, dB")
    ap.add_argument("--out", default="noisetest_out", help="output folder (captures, PNG, Markdown)")
    ap.add_argument("--keep", action="store_true", help="keep the capture files (about 23 MB per second each)")
    ap.add_argument("--rawcap", default=None, help="rawcap executable (default: rawcap/target/release/rawcap[.exe])")
    args = ap.parse_args()
    gains = args.gain or [48]
    for g in gains:
        if not -12 <= g <= 48:
            raise SystemExit("--gain must be -12 to 48 dB")
    if args.rawcap is None:
        exe = os.path.join(HERE, "rawcap", "target", "release", "rawcap" + (".exe" if os.name == "nt" else ""))
        args.rawcap = exe if os.path.exists(exe) else shutil.which("rawcap")
    if not args.rawcap:
        raise SystemExit("rawcap not found: build it (cd rawcap; cargo build --release) or pass --rawcap")
    os.makedirs(args.out, exist_ok=True)

    report = ["# HL2 noise test %s" % datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "",
              "Radio %s. Captures of %.1f s each, 4,096-sample segments (18.75 kHz bins), median floor per band "
              "with spurs excluded. Quiet = quiet-capture mode (sender idle while sampling); loaded = full-rate "
              "stream; repeat = a second quiet capture." % (args.ip, args.seconds), ""]
    results = {}
    for db in gains:
        print("RX gain %d dB (command 0x0A = 0x%02X)" % (db, set_gain(args.ip, args.local_ip, db)))
        time.sleep(0.5)
        files = {}
        for name, quiet in (("quiet", True), ("loaded", False), ("repeat", True)):
            files[name] = os.path.join(args.out, "gain%d_%s.bin" % (db, name))
            capture(args, files[name], quiet)
        f, specs, rows = analyse_gain(args, db, files)
        v = verdict(rows, args.band_limit)
        png = os.path.join(args.out, "noise_gain%d.png" % db)
        plot(png, db, f, specs, rows, "HL2 raw front end, RX gain %d dB: quiet capture vs full-rate stream" % db)
        text = table_text(rows)
        print(text)
        print("RESULT gain %d dB: %s" % (db, v))
        print("plot: %s" % png)
        report += ["## RX gain %d dB: %s" % (db, v), "", text, "", "![noise gain %d](noise_gain%d.png)" % (db, db), ""]
        results[db] = dict(verdict=v, rows=rows)
        if not args.keep:
            for p in files.values():
                for q in (p, p + ".json"):
                    if os.path.exists(q):
                        os.remove(q)
    with open(os.path.join(args.out, "noisetest.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(report) + "\n")
    with open(os.path.join(args.out, "noisetest.json"), "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=1)
    print("report: %s" % os.path.join(args.out, "noisetest.md"))


if __name__ == "__main__":
    main()
