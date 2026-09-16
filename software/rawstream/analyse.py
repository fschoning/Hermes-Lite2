#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Franz Schöning, https://www.schoning.com
"""analyse.py -- offline analysis of rawcap captures from the HL2 raw ADC Ethernet stream.

Capture format (must match rawcap's --save, see rawcap/src/receive.rs and
rawcap/src/protocol.rs): rawcap saves the PACKED payload bytes (frame headers stripped,
12-bit samples packed 2-per-3-bytes, big-endian, exactly as they arrive on the wire) to
<file>, plus a small JSON sidecar <file>.json stating the format and the nominal ADC rate
(76.8 MSPS). This script unpacks that packing itself -- it does not expect pre-unpacked
int16 samples. If you have raw int16 samples from somewhere else (e.g. a capture saved by
different tooling), use --raw-int16 to skip the unpack step.

Subcommands:
  spectrum   FFT one capture: Blackman-Harris window, averaged over many segments. Prints
             noise floor (dBFS and dBFS/Hz), strongest spurs, and (with --tone) the
             signal-generator tone's frequency and amplitude.
  compare    Compare two captures (e.g. quiet vs full-Ethernet-load): prints the floor
             difference in dB and any spur in the second capture that is >6 dB above its
             floor and wasn't in the first -- the plan's §4.6 pass/fail criteria (<1 dB
             floor rise, no new spur >6 dB above floor).

Examples:
  python analyse.py spectrum capture.bin --tone
  python analyse.py compare quiet.bin loaded.bin
"""

import argparse
import json
import os
import sys

import numpy as np

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAVE_MPL = True
except Exception:
    HAVE_MPL = False

ADC_RATE_DEFAULT = 76_800_000.0
FULL_SCALE = 2047.0  # 12-bit two's complement positive full scale; 0 dBFS reference


# =====================================================================================
# Capture loading / unpack -- MUST match rawcap/src/protocol.rs unpack_samples_i16 and
# pack_pair exactly (2 samples per 3 bytes, big-endian: a[11:4], {a[3:0],b[11:8]}, b[7:0]).
# If the gateware/rawcap wire format changes, change ONLY this block to match.
# =====================================================================================

def unpack_12bit_be(payload: np.ndarray) -> np.ndarray:
    """payload: 1-D uint8 array whose length is a multiple of 3. Returns int16 samples,
    sign-extended from 12 bits, in wire order."""
    n_triples = payload.size // 3
    payload = payload[: n_triples * 3].reshape(n_triples, 3).astype(np.uint16)
    b0, b1, b2 = payload[:, 0], payload[:, 1], payload[:, 2]
    a = (b0 << 4) | (b1 >> 4)
    b = ((b1 & 0x0F) << 8) | b2
    out = np.empty(n_triples * 2, dtype=np.uint16)
    out[0::2] = a
    out[1::2] = b
    # sign-extend 12 -> 16 bit
    out = out.astype(np.int16)
    neg = (out & 0x0800) != 0
    out = np.where(neg, out | np.int16(-4096), out)  # 0xF000 as signed = -4096
    return out.astype(np.int16)


def load_capture(path: str, raw_int16: bool, adc_rate: float):
    """Returns (samples: np.int16 array, adc_rate: float, meta: dict)."""
    meta = {}
    sidecar = path + ".json"
    if raw_int16:
        samples = np.fromfile(path, dtype="<i2")
        return samples, adc_rate, meta
    if os.path.exists(sidecar):
        with open(sidecar, "r") as f:
            meta = json.load(f)
        rate = float(meta.get("adc_rate_sps", adc_rate))
    else:
        rate = adc_rate
    raw = np.fromfile(path, dtype=np.uint8)
    samples = unpack_12bit_be(raw)
    return samples, rate, meta


# =====================================================================================
# Spectrum analysis
# =====================================================================================

def averaged_spectrum(samples: np.ndarray, adc_rate: float, segment_size: int, max_segments: int):
    """Blackman-Harris windowed, averaged power spectrum (one-sided).
    Returns (freqs_hz, power_dbfs_per_bin)."""
    n = samples.size
    n_segs = min(max_segments, n // segment_size)
    if n_segs < 1:
        raise ValueError(f"capture too short: {n} samples, need at least {segment_size}")
    window = _blackman_harris(segment_size)  # numpy has no builtin 4-term Blackman-Harris
    win_gain = np.sum(window) / segment_size  # coherent gain, for amplitude correction
    win_power = np.sum(window ** 2) / segment_size  # for power/noise correction

    acc = np.zeros(segment_size // 2 + 1)
    x = samples.astype(np.float64)
    for i in range(n_segs):
        seg = x[i * segment_size : (i + 1) * segment_size]
        seg = seg * window
        spec = np.fft.rfft(seg)
        acc += (np.abs(spec) ** 2)
    acc /= n_segs

    # Normalise to dBFS: a full-scale sine (amplitude FULL_SCALE) windowed and FFT'd has a
    # peak bin magnitude of FULL_SCALE * segment_size * win_gain / 2 (one-sided, excluding
    # DC/Nyquist doubling). Use that as the 0 dBFS reference for signal bins.
    ref = (FULL_SCALE * segment_size * win_gain / 2.0) ** 2
    power_dbfs = 10.0 * np.log10(np.maximum(acc, 1e-30) / ref)

    freqs = np.fft.rfftfreq(segment_size, d=1.0 / adc_rate)
    return freqs, power_dbfs, win_power


def _blackman_harris(n):
    # 4-term minimum 4-sample Blackman-Harris, in case this numpy build lacks the builtin.
    a0, a1, a2, a3 = 0.35875, 0.48829, 0.14128, 0.01168
    k = np.arange(n)
    return (
        a0
        - a1 * np.cos(2 * np.pi * k / (n - 1))
        + a2 * np.cos(4 * np.pi * k / (n - 1))
        - a3 * np.cos(6 * np.pi * k / (n - 1))
    )


def noise_floor_dbfs(freqs, power_dbfs, band_hz=None, spur_exclude_db=6.0):
    """Median floor over a band, with bins more than spur_exclude_db above the running
    median treated as spurs and excluded (two-pass)."""
    if band_hz is not None:
        lo, hi = band_hz
        mask = (freqs >= lo) & (freqs <= hi)
    else:
        mask = np.ones_like(freqs, dtype=bool)
        mask[0] = False  # exclude DC
    vals = power_dbfs[mask]
    med = np.median(vals)
    keep = vals < (med + spur_exclude_db)
    if keep.sum() >= max(8, int(0.5 * vals.size)):
        med = np.median(vals[keep])
    return med


def find_spurs(freqs, power_dbfs, floor_db, above_db=6.0, max_spurs=15, exclude_hz=0.0):
    """Local maxima more than above_db above the floor, excluding a small window (Hz)
    around DC and, if given, around exclude_hz (the wanted tone)."""
    spurs = []
    n = power_dbfs.size
    for i in range(2, n - 2):
        if exclude_hz and abs(freqs[i] - exclude_hz) < (freqs[1] - freqs[0]) * 3:
            continue
        if freqs[i] < 1000:  # skip near-DC
            continue
        v = power_dbfs[i]
        if v - floor_db < above_db:
            continue
        if v >= power_dbfs[i - 1] and v >= power_dbfs[i + 1] and v >= power_dbfs[i - 2] and v >= power_dbfs[i + 2]:
            spurs.append((freqs[i], v))
    spurs.sort(key=lambda t: -t[1])
    return spurs[:max_spurs]


def find_tone(freqs, power_dbfs, search_band_hz=None):
    if search_band_hz is not None:
        lo, hi = search_band_hz
        mask = (freqs >= lo) & (freqs <= hi)
    else:
        mask = freqs > 1000
    idx = np.where(mask)[0]
    if idx.size == 0:
        return None
    best = idx[np.argmax(power_dbfs[idx])]
    return freqs[best], power_dbfs[best]


def phase_continuity_check(samples: np.ndarray, adc_rate: float, tone_hz: float, half_window: int = 2000, n_boundaries: int = 200, boundary_spacing: int = None):
    """Sanity check for dropped/duplicated samples inside the gateware: fit a sine to
    windows either side of evenly spaced 'boundaries' through the capture and look for
    phase jumps. This is an approximation (real frame boundaries aren't known once the
    header has been stripped by rawcap's --save) -- see README's assumption list."""
    n = samples.size
    if boundary_spacing is None:
        boundary_spacing = max(1, n // (n_boundaries + 1))
    jumps = []
    t = np.arange(2 * half_window) / adc_rate
    for b in range(boundary_spacing, n - half_window, boundary_spacing):
        seg = samples[b - half_window : b + half_window].astype(np.float64)
        if seg.size < 2 * half_window:
            continue
        # Fit a*cos + b*sin via least squares (linear in the two unknowns).
        w = 2 * np.pi * tone_hz
        c = np.cos(w * t)
        s = np.sin(w * t)
        A = np.stack([c, s], axis=1)
        coef, *_ = np.linalg.lstsq(A, seg, rcond=None)
        phase = np.arctan2(coef[1], coef[0])
        jumps.append(phase)
    if len(jumps) < 2:
        return None
    jumps = np.unwrap(jumps)
    diffs = np.diff(jumps)
    return float(np.std(diffs)), float(np.max(np.abs(diffs - np.median(diffs))))


# =====================================================================================
# CLI
# =====================================================================================

def cmd_spectrum(args):
    samples, adc_rate, meta = load_capture(args.file, args.raw_int16, args.adc_rate)
    print(f"loaded {samples.size} samples from {args.file} ({samples.size / adc_rate:.3f} s at {adc_rate/1e6:.4f} MSPS)")
    if meta:
        print(f"sidecar metadata: {meta}")

    freqs, power_dbfs, win_power = averaged_spectrum(samples, adc_rate, args.segment_size, args.max_segments)
    bin_hz = freqs[1] - freqs[0]

    floor_db = noise_floor_dbfs(freqs, power_dbfs, band_hz=(args.band_lo, args.band_hi))
    floor_db_per_hz = floor_db - 10.0 * np.log10(bin_hz)
    print(f"segments averaged: {min(args.max_segments, samples.size // args.segment_size)}, bin width {bin_hz:.2f} Hz")
    print(f"noise floor over {args.band_lo/1e6:.1f}-{args.band_hi/1e6:.1f} MHz: {floor_db:.2f} dBFS/bin, {floor_db_per_hz:.2f} dBFS/Hz")

    tone_freq = None
    if args.tone:
        found = find_tone(freqs, power_dbfs, search_band_hz=(args.tone_search_lo, args.tone_search_hi))
        if found:
            tone_freq, tone_db = found
            print(f"strongest peak in search band: {tone_freq/1e6:.6f} MHz at {tone_db:.2f} dBFS")

    spurs = find_spurs(freqs, power_dbfs, floor_db, above_db=args.spur_above_db, exclude_hz=tone_freq or 0.0)
    print(f"spurs > {args.spur_above_db} dB above floor (excluding the tone, top {len(spurs)}):")
    for f, v in spurs:
        print(f"  {f/1e6:10.4f} MHz  {v:8.2f} dBFS  ({v - floor_db:+.1f} dB above floor)")

    if args.phase_check and args.tone:
        pc = phase_continuity_check(samples, adc_rate, tone_freq or args.phase_tone_hz)
        if pc:
            std, worst = pc
            print(f"phase continuity: std of inter-window phase diff = {std:.4f} rad, worst deviation = {worst:.4f} rad")
            print("  (large jumps here suggest dropped/duplicated samples inside the gateware; see README's assumption about frame boundaries)")

    if args.png and HAVE_MPL:
        _save_spectrum_png(freqs, power_dbfs, floor_db, spurs, args.png, adc_rate)
        print(f"saved {args.png}")
    elif args.png:
        print("matplotlib not installed; skipping PNG, text output only")


def _save_spectrum_png(freqs, power_dbfs, floor_db, spurs, path, adc_rate):
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(freqs / 1e6, power_dbfs, linewidth=0.5)
    ax.axhline(floor_db, color="green", linestyle="--", label=f"floor {floor_db:.1f} dBFS")
    for f, v in spurs:
        ax.plot(f / 1e6, v, "rx")
    ax.set_xlabel("MHz")
    ax.set_ylabel("dBFS")
    ax.set_title("Averaged spectrum (Blackman-Harris)")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def cmd_compare(args):
    s1, r1, _ = load_capture(args.quiet_file, args.raw_int16, args.adc_rate)
    s2, r2, _ = load_capture(args.loaded_file, args.raw_int16, args.adc_rate)
    f1, p1, _ = averaged_spectrum(s1, r1, args.segment_size, args.max_segments)
    f2, p2, _ = averaged_spectrum(s2, r2, args.segment_size, args.max_segments)

    floor1 = noise_floor_dbfs(f1, p1, band_hz=(args.band_lo, args.band_hi))
    floor2 = noise_floor_dbfs(f2, p2, band_hz=(args.band_lo, args.band_hi))
    diff = floor2 - floor1
    print(f"{args.quiet_file}: floor {floor1:.2f} dBFS over {args.band_lo/1e6:.1f}-{args.band_hi/1e6:.1f} MHz")
    print(f"{args.loaded_file}: floor {floor2:.2f} dBFS over {args.band_lo/1e6:.1f}-{args.band_hi/1e6:.1f} MHz")
    print(f"floor difference (loaded - quiet): {diff:+.2f} dB  [pass: < 1.0 dB rise]")

    spurs1 = set(round(f, -3) for f, _ in find_spurs(f1, p1, floor1, above_db=args.spur_above_db))
    spurs2 = find_spurs(f2, p2, floor2, above_db=args.spur_above_db)
    new_spurs = [(f, v) for f, v in spurs2 if round(f, -3) not in spurs1]
    print(f"new spurs in {args.loaded_file} not present (within 1 kHz) in {args.quiet_file}, >{args.spur_above_db} dB above floor:")
    if not new_spurs:
        print("  none  [pass]")
    else:
        for f, v in new_spurs:
            print(f"  {f/1e6:10.4f} MHz  {v:8.2f} dBFS  ({v - floor2:+.1f} dB above floor)  [FAIL if this persists]")

    passed = diff < 1.0 and len(new_spurs) == 0
    print(f"RESULT: {'PASS' if passed else 'FAIL'}")

    if args.png and HAVE_MPL:
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(f1 / 1e6, p1, linewidth=0.5, label=os.path.basename(args.quiet_file), alpha=0.8)
        ax.plot(f2 / 1e6, p2, linewidth=0.5, label=os.path.basename(args.loaded_file), alpha=0.8)
        ax.set_xlabel("MHz")
        ax.set_ylabel("dBFS")
        ax.set_title(f"Quiet vs loaded (floor diff {diff:+.2f} dB)")
        ax.legend()
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        fig.savefig(args.png, dpi=120)
        plt.close(fig)
        print(f"saved {args.png}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--raw-int16", action="store_true", help="capture is already unpacked little-endian int16, not packed 12-bit")
    common.add_argument("--adc-rate", type=float, default=ADC_RATE_DEFAULT, help="ADC sample rate in Hz if no .json sidecar is present")
    common.add_argument("--segment-size", type=int, default=1_048_576, help="FFT segment length in samples")
    common.add_argument("--max-segments", type=int, default=64, help="max segments to average")
    common.add_argument("--band-lo", type=float, default=1e6, help="noise-floor band low edge, Hz")
    common.add_argument("--band-hi", type=float, default=30e6, help="noise-floor band high edge, Hz")
    common.add_argument("--spur-above-db", type=float, default=6.0, help="spur threshold above floor, dB")
    common.add_argument("--png", type=str, default=None, help="save a PNG plot here (needs matplotlib)")

    sp = sub.add_parser("spectrum", parents=[common], help="FFT one capture")
    sp.add_argument("file")
    sp.add_argument("--tone", action="store_true", help="report the strongest peak as a signal-generator tone")
    sp.add_argument("--tone-search-lo", type=float, default=1e6)
    sp.add_argument("--tone-search-hi", type=float, default=30e6)
    sp.add_argument("--phase-check", action="store_true", help="run the frame-boundary phase-continuity check")
    sp.add_argument("--phase-tone-hz", type=float, default=10_000_000.0, help="tone frequency for --phase-check if --tone didn't find one")
    sp.set_defaults(func=cmd_spectrum)

    cp = sub.add_parser("compare", parents=[common], help="compare quiet vs loaded captures")
    cp.add_argument("quiet_file")
    cp.add_argument("loaded_file")
    cp.set_defaults(func=cmd_compare)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
