// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Franz Schöning, https://www.schoning.com
//
//! Shared, atomics-only stats block updated by the checker thread and printed once a second
//! by the main thread.

use std::sync::atomic::{AtomicBool, AtomicI64, AtomicU64, Ordering};

#[derive(Default)]
pub struct Stats {
    pub frames_total: AtomicU64,
    pub bytes_total: AtomicU64,
    pub lost_frames: AtomicU64,   // from sequence-number gaps
    pub lost_samples: AtomicU64,  // from sample-index gaps (more precise than lost_frames)
    pub reordered_or_dup: AtomicU64,
    pub bad_samples: AtomicU64,   // counter-pattern mismatches (pattern mode only)
    pub ring_drops: AtomicU64,    // producer couldn't get a free ring slot
    pub hl2_overflow_events: AtomicU64, // latest overflow_count value seen from the HL2 header
    pub hl2_overflow_frames: AtomicU64, // frames seen with the overflow flag set
    pub hl2_gap_frames: AtomicU64, // frames seen with the gap flag set (one per FIFO resync)
    pub fifo_high_water: AtomicU64,     // latest / max fifo high-water mark seen
    // Frames carrying the "PREVIOUS frame had a full-scale sample" flag (docs/rawfront/PROTOCOL.md flag bit
    // 2 -- this reports the frame before the one it's set on). In test-pattern mode this fires
    // regularly and is expected, not a fault: the pattern counter passes 0x7FF/0x800 every 4096
    // samples.
    pub adc_clip_frames: AtomicU64,
    pub max_queued_bytes: AtomicU64, // socket receive queue high-water (FIONREAD)
    pub samples_total: AtomicU64,    // sum of samples_in_frame across all received frames
    /// Transmit-safety status byte (header byte 3): latest value, OR of all values, changes.
    pub safety_last: AtomicU64,
    pub safety_any: AtomicU64,
    pub safety_changes: AtomicU64,

    // ---- duplex (--duplex): radio-reported TX sink status, latest values from v2 headers ----
    pub duplex: AtomicBool,
    pub v2_frames: AtomicU64,
    pub rtx_frames: AtomicU64,
    pub rtx_lost: AtomicU64,
    pub rtx_bad: AtomicU64,
    pub rtx_fill: AtomicU64,
    pub rtx_unf: AtomicU64,
    pub rtx_ovf: AtomicU64,
    pub rtx_flags: AtomicU64,
    /// Fill min/max since the printer last reset them.
    pub rtx_fill_min: AtomicU64,
    pub rtx_fill_max: AtomicU64,
    /// Fill sum/count since the pacer last took them (closed-loop pacing input).
    pub rtx_fill_sum: AtomicU64,
    pub rtx_fill_cnt: AtomicU64,

    // ---- duplex: PC sender ----
    pub tx_frames_sent: AtomicU64,
    pub tx_bytes_sent: AtomicU64,
    pub tx_send_errors: AtomicU64,
    pub tx_pacing_slips: AtomicU64,
    /// Current rate trim, in units of 0.001 ppm.
    pub tx_trim_milli_ppm: AtomicI64,
    /// Largest lateness of a frame against its schedule, in microseconds, since last print.
    pub tx_max_late_us: AtomicU64,
    /// Set by the sender when it sends its first frame.
    pub tx_started: AtomicBool,

    // ---- echo (--echo, hl2b5up_raw): the RX stream carries the TX samples the radio played ----
    pub echo: AtomicBool,
    pub v3_frames: AtomicU64,
    /// Frames whose header offset was valid.
    pub echo_frames: AtomicU64,
    /// Echoed samples equal to the TX sample at RX index + offset.
    pub echo_good: AtomicU64,
    /// Zeros: written while the radio played nothing (TX FIFO refilling).
    pub echo_zero: AtomicU64,
    /// Mismatches in a frame whose offset differs from the previous frame's (samples written before
    /// the change); not counted as errors.
    pub echo_unsettled: AtomicU64,
    /// Mismatches with a steady offset: errors.
    pub echo_bad: AtomicU64,
    pub echo_off_changes: AtomicU64,
    pub echo_offset: AtomicI64,
    /// Round-trip latency (TX frame send to RX frame receive), microseconds.
    pub lat_sum_us: AtomicU64,
    pub lat_cnt: AtomicU64,
    pub lat_min_us: AtomicU64,
    pub lat_max_us: AtomicU64,
    /// Latest interlock trip byte and echo flags byte (version 3 header bytes 47 and 46).
    pub trips_last: AtomicU64,
    pub echo_flags_last: AtomicU64,
}

impl Stats {
    pub fn new() -> Self {
        let s = Stats::default();
        s.rtx_fill_min.store(u64::MAX, Ordering::Relaxed);
        s.lat_min_us.store(u64::MAX, Ordering::Relaxed);
        s
    }

    pub fn snapshot_and_reset_persecond(&self, prev: &PerSecond) -> PerSecond {
        let frames = self.frames_total.load(Ordering::Relaxed);
        let bytes = self.bytes_total.load(Ordering::Relaxed);
        let tx_bytes = self.tx_bytes_sent.load(Ordering::Relaxed);
        let tx_frames = self.tx_frames_sent.load(Ordering::Relaxed);
        PerSecond {
            frames,
            bytes,
            d_frames: frames.saturating_sub(prev.frames),
            d_bytes: bytes.saturating_sub(prev.bytes),
            tx_bytes,
            tx_frames,
            d_tx_bytes: tx_bytes.saturating_sub(prev.tx_bytes),
            d_tx_frames: tx_frames.saturating_sub(prev.tx_frames),
        }
    }

    pub fn radio_tx(&self) -> RadioTx {
        RadioTx {
            frames: self.rtx_frames.load(Ordering::Relaxed),
            lost: self.rtx_lost.load(Ordering::Relaxed),
            bad: self.rtx_bad.load(Ordering::Relaxed),
            unf: self.rtx_unf.load(Ordering::Relaxed),
            ovf: self.rtx_ovf.load(Ordering::Relaxed),
        }
    }
}

#[derive(Default, Clone, Copy)]
pub struct PerSecond {
    pub frames: u64,
    pub bytes: u64,
    pub d_frames: u64,
    pub d_bytes: u64,
    pub tx_bytes: u64,
    pub tx_frames: u64,
    pub d_tx_bytes: u64,
    pub d_tx_frames: u64,
}

/// Radio-reported TX error counters at one moment.
#[derive(Default, Clone, Copy, Debug)]
pub struct RadioTx {
    pub frames: u64,
    pub lost: u64,
    pub bad: u64,
    pub unf: u64,
    pub ovf: u64,
}

/// Print one status line. Called once a second from the main thread.
pub fn print_line(s: &Stats, delta: &PerSecond) {
    let mbit_s = (delta.d_bytes as f64 * 8.0) / 1_000_000.0;
    println!(
        "frames/s={:>7} Mbit/s={:>7.1} lost_frames={:>6} lost_samples={:>9} reorder/dup={:>4} bad_samples={:>8} hl2_ovf_flagged={:>5} hl2_ovf_count={:>5} hl2_gap_frames={:>5} fifo_hw={:>6} adc_clip_frames={:>5} ring_drops={:>5} max_queued_bytes={:>9} safety={}",
        delta.d_frames,
        mbit_s,
        s.lost_frames.load(Ordering::Relaxed),
        s.lost_samples.load(Ordering::Relaxed),
        s.reordered_or_dup.load(Ordering::Relaxed),
        s.bad_samples.load(Ordering::Relaxed),
        s.hl2_overflow_frames.load(Ordering::Relaxed),
        s.hl2_overflow_events.load(Ordering::Relaxed),
        s.hl2_gap_frames.load(Ordering::Relaxed),
        s.fifo_high_water.load(Ordering::Relaxed),
        s.adc_clip_frames.load(Ordering::Relaxed),
        s.ring_drops.load(Ordering::Relaxed),
        s.max_queued_bytes.load(Ordering::Relaxed),
        crate::protocol::safety_text(s.safety_last.load(Ordering::Relaxed) as u8),
    );
    if s.duplex.load(Ordering::Relaxed) {
        let fmin = s.rtx_fill_min.swap(u64::MAX, Ordering::Relaxed);
        let fmax = s.rtx_fill_max.swap(0, Ordering::Relaxed);
        let (fmin, fmax) = if fmin == u64::MAX { (0, 0) } else { (fmin, fmax) };
        let flags = s.rtx_flags.load(Ordering::Relaxed) as u8;
        println!(
            "  TX: sent frames/s={:>6} Mbit/s={:>6.1} trim={:>+8.2}ppm max_late={:>6}us slips={:>3} send_err={:>3} | radio: frames={:>9} lost={:>4} bad={:>6} fill={:>5} (min {:>5} max {:>5}) unf={:>3} ovf={:>3} dac={}",
            delta.d_tx_frames,
            (delta.d_tx_bytes as f64 * 8.0) / 1_000_000.0,
            s.tx_trim_milli_ppm.load(Ordering::Relaxed) as f64 / 1000.0,
            s.tx_max_late_us.swap(0, Ordering::Relaxed),
            s.tx_pacing_slips.load(Ordering::Relaxed),
            s.tx_send_errors.load(Ordering::Relaxed),
            s.rtx_frames.load(Ordering::Relaxed),
            s.rtx_lost.load(Ordering::Relaxed),
            s.rtx_bad.load(Ordering::Relaxed),
            s.rtx_fill.load(Ordering::Relaxed),
            fmin,
            fmax,
            s.rtx_unf.load(Ordering::Relaxed),
            s.rtx_ovf.load(Ordering::Relaxed),
            if flags & crate::protocol::TX_FLAG_DAC_PLAYING != 0 { "playing" } else { "waiting" },
        );
    }
    if s.echo.load(Ordering::Relaxed) {
        let cnt = s.lat_cnt.load(Ordering::Relaxed);
        println!(
            "  ECHO: offset={:>7} ({}) good={:>11} zero={:>8} unsettled={:>7} BAD={:>6} offset changes={:>3} | round trip ms avg {:>6.2} min {:>6.2} max {:>6.2} | trips=0x{:02X}",
            s.echo_offset.load(Ordering::Relaxed),
            if s.echo_flags_last.load(Ordering::Relaxed) as u8 & crate::protocol::ECHO_F_VALID != 0 { "valid" } else { "not valid" },
            s.echo_good.load(Ordering::Relaxed),
            s.echo_zero.load(Ordering::Relaxed),
            s.echo_unsettled.load(Ordering::Relaxed),
            s.echo_bad.load(Ordering::Relaxed),
            s.echo_off_changes.load(Ordering::Relaxed),
            if cnt > 0 { s.lat_sum_us.load(Ordering::Relaxed) as f64 / cnt as f64 / 1000.0 } else { 0.0 },
            if cnt > 0 { s.lat_min_us.load(Ordering::Relaxed) as f64 / 1000.0 } else { 0.0 },
            s.lat_max_us.load(Ordering::Relaxed) as f64 / 1000.0,
            s.trips_last.load(Ordering::Relaxed),
        );
    }
}

/// Echo summary (--echo). Returns true when every echoed sample with a steady offset matched.
pub fn print_echo_summary(s: &Stats, elapsed_secs: f64, radio_at_end: &RadioTx) -> bool {
    let sent = s.tx_frames_sent.load(Ordering::Relaxed);
    let tx_bytes = s.tx_bytes_sent.load(Ordering::Relaxed);
    let rx_bytes = s.bytes_total.load(Ordering::Relaxed);
    let good = s.echo_good.load(Ordering::Relaxed);
    let bad = s.echo_bad.load(Ordering::Relaxed);
    let cnt = s.lat_cnt.load(Ordering::Relaxed);
    println!("---- echo summary (PC -> radio TX samples -> radio RX stream -> PC) ----");
    if elapsed_secs > 0.0 {
        println!(
            "PC -> radio:        {:.1} Mbit/s UDP payload ({} frames sent, radio received {}, radio counted {} lost, {} not accounted)",
            tx_bytes as f64 * 8.0 / elapsed_secs / 1e6,
            sent,
            radio_at_end.frames,
            radio_at_end.lost,
            sent.saturating_sub(radio_at_end.frames + radio_at_end.lost)
        );
        println!(
            "radio -> PC:        {:.1} Mbit/s UDP payload ({} frames, {} lost on the way, {} samples lost)",
            rx_bytes as f64 * 8.0 / elapsed_secs / 1e6,
            s.frames_total.load(Ordering::Relaxed),
            s.lost_frames.load(Ordering::Relaxed) + s.ring_drops.load(Ordering::Relaxed),
            s.lost_samples.load(Ordering::Relaxed)
        );
    }
    println!(
        "radio TX sink:      underflows {} (zeros echoed while refilling), overflows {}, final fill {}",
        radio_at_end.unf, radio_at_end.ovf, s.rtx_fill.load(Ordering::Relaxed)
    );
    println!(
        "echoed samples:     {} matched, {} zeros, {} unsettled (frames around an offset change), {} BAD; {} of {} frames had a valid offset, {} offset changes",
        good,
        s.echo_zero.load(Ordering::Relaxed),
        s.echo_unsettled.load(Ordering::Relaxed),
        bad,
        s.echo_frames.load(Ordering::Relaxed),
        s.v3_frames.load(Ordering::Relaxed),
        s.echo_off_changes.load(Ordering::Relaxed)
    );
    if cnt > 0 {
        println!(
            "round trip:         avg {:.2} ms, min {:.2} ms, max {:.2} ms over {} frames (PC sends a TX frame -> PC receives the RX frame starting with its first sample; includes the radio TX FIFO dwell, fill / 76.8 MSPS: {:.2} ms at the last fill before the sender stopped)",
            s.lat_sum_us.load(Ordering::Relaxed) as f64 / cnt as f64 / 1000.0,
            s.lat_min_us.load(Ordering::Relaxed) as f64 / 1000.0,
            s.lat_max_us.load(Ordering::Relaxed) as f64 / 1000.0,
            cnt,
            s.rtx_fill.load(Ordering::Relaxed) as f64 / 76_800.0
        );
    } else {
        println!("round trip:         no measurement (no complete frame with a steady offset)");
    }
    // A sample corrupted on its way to the radio is counted by the radio's own TX checker and comes back
    // corrupted in the echo: those mismatches belong to the PC -> radio direction.
    println!(
        "corrupted samples:  PC -> radio {} (radio TX checker), echo mismatches {} ({} not explained by the PC -> radio direction)",
        radio_at_end.bad,
        bad,
        bad.saturating_sub(radio_at_end.bad)
    );
    let pass = good > 0 && bad <= radio_at_end.bad;
    println!(
        "ECHO PASS/FAIL (echoed samples seen; every mismatch with a steady offset is a sample the radio already received corrupted): {}",
        if pass { "PASS" } else { "FAIL" }
    );
    pass
}

/// Duplex result inputs gathered by receive::run.
pub struct DuplexSummary {
    /// Radio counters when the lock-in period ended (None = run shorter than lock-in).
    pub at_lock: Option<RadioTx>,
    /// Radio counters when the PC sender stopped.
    pub at_end: RadioTx,
    /// Seconds between lock-in end and sender stop.
    pub measured_secs: f64,
    pub lock_in_secs: f64,
}

/// Print the summary. Returns true if everything passed (RX, and TX when duplex).
pub fn print_summary(s: &Stats, elapsed_secs: f64, duplex: Option<&DuplexSummary>) -> bool {
    let frames = s.frames_total.load(Ordering::Relaxed);
    let bytes = s.bytes_total.load(Ordering::Relaxed);
    println!("---- summary ----");
    println!("elapsed:            {:.1} s", elapsed_secs);
    println!("frames received:    {}", frames);
    println!("bytes received:     {} ({:.1} MB)", bytes, bytes as f64 / 1e6);
    if elapsed_secs > 0.0 {
        println!("mean frames/s:      {:.1}", frames as f64 / elapsed_secs);
        println!("mean Mbit/s:        {:.1}", (bytes as f64 * 8.0) / elapsed_secs / 1e6);
    }
    println!("lost frames:        {}", s.lost_frames.load(Ordering::Relaxed));
    println!("lost samples:       {}", s.lost_samples.load(Ordering::Relaxed));
    println!("reordered/dup:      {}", s.reordered_or_dup.load(Ordering::Relaxed));
    println!("bad pattern samples:{}", s.bad_samples.load(Ordering::Relaxed));
    println!("ring drops:         {}", s.ring_drops.load(Ordering::Relaxed));
    println!("HL2 overflow frames:{}", s.hl2_overflow_frames.load(Ordering::Relaxed));
    println!("HL2 overflow count (last):{}", s.hl2_overflow_events.load(Ordering::Relaxed));
    println!("HL2 gap frames (resyncs):{}", s.hl2_gap_frames.load(Ordering::Relaxed));
    println!("FIFO high water:    {}", s.fifo_high_water.load(Ordering::Relaxed));
    println!("ADC clip frames (flag describes the PREVIOUS frame): {}", s.adc_clip_frames.load(Ordering::Relaxed));
    println!("max queued bytes:   {}", s.max_queued_bytes.load(Ordering::Relaxed));
    println!(
        "TX safety status:   last {}, bits seen {}, changes {}",
        crate::protocol::safety_text(s.safety_last.load(Ordering::Relaxed) as u8),
        crate::protocol::safety_text(s.safety_any.load(Ordering::Relaxed) as u8),
        s.safety_changes.load(Ordering::Relaxed)
    );
    let samples = s.samples_total.load(Ordering::Relaxed) + s.lost_samples.load(Ordering::Relaxed);
    if elapsed_secs > 0.0 && samples > 0 {
        let measured_rate = samples as f64 / elapsed_secs;
        let ppm = (measured_rate - 76_800_000.0) / 76_800_000.0 * 1e6;
        println!(
            "measured ADC rate:  {:.1} samples/s ({:+.1} ppm vs nominal 76.8 MSPS; received plus lost, \
             over wall-clock time including start-up)",
            measured_rate, ppm
        );
    }
    let lost = s.lost_frames.load(Ordering::Relaxed) + s.ring_drops.load(Ordering::Relaxed);
    let rx_pass = frames > 0 && lost == 0 && s.bad_samples.load(Ordering::Relaxed) == 0;
    let verdict = if frames == 0 {
        "FAIL (no frames received)"
    } else if rx_pass {
        "PASS"
    } else {
        "FAIL"
    };
    println!("PASS/FAIL (frames received, zero lost frames & zero bad samples): {}", verdict);

    let Some(d) = duplex else {
        return rx_pass;
    };
    let sent = s.tx_frames_sent.load(Ordering::Relaxed);
    let tx_bytes = s.tx_bytes_sent.load(Ordering::Relaxed);
    println!("---- TX (PC -> radio) summary ----");
    println!("TX frames sent:     {}", sent);
    if elapsed_secs > 0.0 {
        println!("TX mean Mbit/s:     {:.1} (UDP payload, over the whole run)", (tx_bytes as f64 * 8.0) / elapsed_secs / 1e6);
    }
    println!("TX send errors:     {}", s.tx_send_errors.load(Ordering::Relaxed));
    println!("TX pacing slips:    {}", s.tx_pacing_slips.load(Ordering::Relaxed));
    println!("TX final trim:      {:+.2} ppm", s.tx_trim_milli_ppm.load(Ordering::Relaxed) as f64 / 1000.0);
    println!("v2 frames seen:     {}", s.v2_frames.load(Ordering::Relaxed));
    let e = d.at_end;
    println!(
        "radio at sender stop: frames received={} lost={} bad samples={} underflows={} overflows={}",
        e.frames, e.lost, e.bad, e.unf, e.ovf
    );
    let tx_pass = match d.at_lock {
        None => {
            println!("TX PASS/FAIL: FAIL (run ended before the {:.0} s lock-in finished)", d.lock_in_secs);
            false
        }
        Some(l) => {
            let dl = e.lost.saturating_sub(l.lost);
            let db = e.bad.saturating_sub(l.bad);
            let du = e.unf.saturating_sub(l.unf);
            let dov = e.ovf.saturating_sub(l.ovf);
            let dfr = e.frames.saturating_sub(l.frames);
            println!(
                "after {:.0} s lock-in ({:.1} s measured): radio frames received={} ({:.0} frames/s) lost={} bad={} underflows={} overflows={}",
                d.lock_in_secs,
                d.measured_secs,
                dfr,
                if d.measured_secs > 0.0 { dfr as f64 / d.measured_secs } else { 0.0 },
                dl,
                db,
                du,
                dov
            );
            // The radio must have counted (nearly) every frame the PC sent: this catches a radio
            // that silently ignores TX frames. Frames sent in the last few ms may not be in the
            // last received header yet.
            let counted_ok = e.frames > 0 && e.frames + e.lost + 200 >= sent;
            if !counted_ok {
                println!("radio counted {} received + {} lost of {} sent", e.frames, e.lost, sent);
            }
            let pass = dl == 0 && db == 0 && du == 0 && dov == 0 && dfr > 0 && counted_ok;
            println!(
                "TX PASS/FAIL (after lock-in: zero lost TX frames, zero bad samples, zero underflow/overflow): {}",
                if pass { "PASS" } else { "FAIL" }
            );
            pass
        }
    };
    println!("(RX losses on the PC network card are reported above and do not affect the TX verdict.)");
    rx_pass && tx_pass
}
