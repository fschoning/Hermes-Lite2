// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Franz Schöning, https://www.schoning.com
//
//! `--duplex`: PC -> HL2 TX frame sender (docs/rawfront/PROTOCOL.md).
//!
//! Sends the counter pattern on UDP port 1026 at the radio's ADC rate while the receive path
//! runs. Pacing is closed loop on the radio's own report: every version 2 raw frame carries the
//! radio TX FIFO fill level, and a PI controller trims the send rate (in ppm around 76.8 MSPS)
//! to hold the fill at the target (12,000 of 16,384 samples by default). That locks the PC's send rate to the
//! radio's ADC clock without knowing either crystal's error.

use crate::protocol;
use crate::stats::Stats;
use crate::winsys;
use socket2::{Domain, SockAddr, Socket, Type};
use std::net::{IpAddr, SocketAddr};
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::Arc;
use std::time::{Duration, Instant};

/// Send time of every TX frame (by sequence number, modulo the table size), for `--echo` latency:
/// the receiver maps an echoed sample's TX index back to the frame that carried it.
pub struct SendTimes {
    /// Common time base with the receive thread's timestamps.
    pub epoch: Instant,
    /// TX samples per frame (TX frame k starts at index k * samples).
    pub samples: AtomicU64,
    times: Vec<AtomicU64>,
}

pub const SEND_TIMES_SLOTS: usize = 1 << 17; // about 10 s of jumbo frames

impl SendTimes {
    pub fn new(epoch: Instant) -> SendTimes {
        SendTimes { epoch, samples: AtomicU64::new(0), times: (0..SEND_TIMES_SLOTS).map(|_| AtomicU64::new(0)).collect() }
    }

    fn record(&self, seq: u32, ns: u64) {
        self.times[seq as usize % SEND_TIMES_SLOTS].store(ns | 1, Ordering::Relaxed);
    }

    /// Send time (ns since epoch) of the frame holding TX sample `tx_index`, if recorded.
    pub fn sent_ns(&self, tx_index: i64) -> Option<u64> {
        let n = self.samples.load(Ordering::Relaxed);
        if n == 0 || tx_index < 0 {
            return None;
        }
        let t = self.times[(tx_index as u64 / n) as usize % SEND_TIMES_SLOTS].load(Ordering::Relaxed);
        if t == 0 { None } else { Some(t) }
    }
}

pub struct SenderOptions {
    pub local_ip: IpAddr,
    pub hl2_ip: IpAddr,
    pub samples_per_frame: u16,
    pub sndbuf: usize,
    pub target_fill: f64,
    /// Scale on the nominal 76.8 MSPS (emulator testing at reduced rate). 1.0 on a real radio.
    pub rate_fraction: f64,
    /// Send TX datagrams with a zero UDP checksum (the HL2 does not check it).
    pub no_udp_checksum: bool,
    /// `--echo`: record each frame's send time.
    pub send_times: Option<Arc<SendTimes>>,
}

/// Controller constants. Plant: d(fill)/dt = 76.8 * (trim_ppm - clock_offset_ppm) samples/s.
/// Kp = 0.026 ppm/sample gives a 0.5 s time constant; the integral removes the constant clock
/// offset between PC and radio with a zero at Ki/Kp = 0.5 /s.
const KP_PPM_PER_SAMPLE: f64 = 0.026;
const KI_PPM_PER_SAMPLE_S: f64 = 0.013;
const TRIM_LIMIT_PPM: f64 = 1000.0;
const CONTROL_PERIOD: Duration = Duration::from_millis(50);
const NOMINAL_RATE: f64 = 76_800_000.0;

/// PI rate trim on the radio-reported FIFO fill.
pub struct Pacer {
    pub target_fill: f64,
    integ: f64,
    pub trim_ppm: f64,
}

impl Pacer {
    pub fn new(target_fill: f64) -> Pacer {
        Pacer { target_fill, integ: 0.0, trim_ppm: 0.0 }
    }

    /// Feed the mean fill over the last `dt` seconds; returns the new trim in ppm.
    pub fn update(&mut self, mean_fill: f64, dt: f64) -> f64 {
        let err = self.target_fill - mean_fill; // positive: FIFO too empty -> send faster
        self.integ = (self.integ + KI_PPM_PER_SAMPLE_S * err * dt).clamp(-TRIM_LIMIT_PPM, TRIM_LIMIT_PPM);
        self.trim_ppm = (KP_PPM_PER_SAMPLE * err + self.integ).clamp(-TRIM_LIMIT_PPM, TRIM_LIMIT_PPM);
        self.trim_ppm
    }
}

pub fn spawn(opts: SenderOptions, stats: Arc<Stats>, running: Arc<AtomicBool>) -> std::io::Result<std::thread::JoinHandle<()>> {
    let domain = match opts.local_ip {
        IpAddr::V4(_) => Domain::IPV4,
        IpAddr::V6(_) => Domain::IPV6,
    };
    let sock = Socket::new(domain, Type::DGRAM, None)?;
    if let Err(e) = sock.set_send_buffer_size(opts.sndbuf) {
        println!("rawcap: warning: set_send_buffer_size failed: {e}");
    }
    println!(
        "rawcap: TX socket SO_SNDBUF requested={} granted={} bytes",
        opts.sndbuf,
        sock.send_buffer_size().unwrap_or(0)
    );
    if opts.no_udp_checksum {
        match winsys::set_udp_nochecksum(&sock) {
            Ok(()) => println!("rawcap: TX socket UDP checksum off (UDP_NOCHECKSUM)"),
            Err(e) => println!("rawcap: warning: UDP_NOCHECKSUM failed: {e}"),
        }
    }
    sock.bind(&SockAddr::from(SocketAddr::new(opts.local_ip, 0)))?;
    sock.connect(&SockAddr::from(SocketAddr::new(opts.hl2_ip, protocol::PORT_TX)))?;

    std::thread::Builder::new()
        .name("rawcap-tx".into())
        .spawn(move || sender_loop(sock, opts, &stats, &running))
}

fn sender_loop(sock: Socket, opts: SenderOptions, stats: &Stats, running: &AtomicBool) {
    winsys::raise_current_thread_priority();

    // Wait for the stream to be up (first raw frame received) before sending.
    while running.load(Ordering::Relaxed) && stats.frames_total.load(Ordering::Relaxed) == 0 {
        std::thread::sleep(Duration::from_millis(1));
    }
    if !running.load(Ordering::Relaxed) {
        return;
    }

    let n = opts.samples_per_frame;
    let frame_len = protocol::TX_HEADER_LEN + protocol::packed_len(n as usize);
    let mut buf = vec![0u8; frame_len];
    let base_rate = NOMINAL_RATE * opts.rate_fraction;

    let mut seq: u32 = 0;
    let mut idx: u64 = 0;
    let mut pacer = Pacer::new(opts.target_fill);
    if let Some(st) = &opts.send_times {
        st.samples.store(n as u64, Ordering::Relaxed);
    }
    let mut trim_ppm = 0.0f64;

    let t0 = Instant::now();
    let mut next_s = 0.0f64; // schedule time of the next frame, seconds since t0
    let mut last_ctrl = t0;
    let mut max_late = 0.0f64;
    let mut playing_seen = false;

    stats.tx_started.store(true, Ordering::Relaxed);

    while running.load(Ordering::Relaxed) {
        // ---- wait until this frame's slot ----
        let mut now_s = t0.elapsed().as_secs_f64();
        if now_s < next_s {
            if next_s - now_s > 0.002 {
                std::thread::sleep(Duration::from_secs_f64(next_s - now_s - 0.0015));
            }
            while now_s < next_s {
                std::hint::spin_loop();
                now_s = t0.elapsed().as_secs_f64();
            }
        }
        let late = now_s - next_s;
        if late > max_late {
            max_late = late;
        }
        if late > 0.020 {
            // More than 20 ms behind: do not burst to catch up (that would overflow the radio
            // FIFO); count a slip and restart the schedule from now.
            stats.tx_pacing_slips.fetch_add(1, Ordering::Relaxed);
            next_s = now_s;
        }

        // ---- build and send ----
        buf[..protocol::TX_HEADER_LEN].copy_from_slice(&protocol::build_tx_header(seq, idx, n));
        protocol::fill_tx_pattern(&mut buf[protocol::TX_HEADER_LEN..], idx, n);
        if let Some(st) = &opts.send_times {
            st.record(seq, st.epoch.elapsed().as_nanos() as u64);
        }
        match sock.send(&buf) {
            Ok(w) => {
                stats.tx_frames_sent.fetch_add(1, Ordering::Relaxed);
                stats.tx_bytes_sent.fetch_add(w as u64, Ordering::Relaxed);
            }
            Err(_) => {
                // The frame is gone either way: the radio sees a sequence gap.
                stats.tx_send_errors.fetch_add(1, Ordering::Relaxed);
            }
        }
        seq = seq.wrapping_add(1);
        idx += n as u64;
        next_s += n as f64 / (base_rate * (1.0 + trim_ppm * 1e-6));

        // ---- closed-loop trim ----
        let now = Instant::now();
        if now.duration_since(last_ctrl) >= CONTROL_PERIOD {
            let dt = now.duration_since(last_ctrl).as_secs_f64();
            last_ctrl = now;
            let sum = stats.rtx_fill_sum.swap(0, Ordering::Relaxed);
            let cnt = stats.rtx_fill_cnt.swap(0, Ordering::Relaxed);
            let playing = stats.rtx_flags.load(Ordering::Relaxed) as u8 & protocol::TX_FLAG_DAC_PLAYING != 0;
            if playing {
                playing_seen = true;
            }
            if cnt > 0 && playing_seen {
                trim_ppm = pacer.update(sum as f64 / cnt as f64, dt);
                stats.tx_trim_milli_ppm.store((trim_ppm * 1000.0) as i64, Ordering::Relaxed);
            }
            stats.tx_max_late_us.fetch_max((max_late * 1e6) as u64, Ordering::Relaxed);
            max_late = 0.0;
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Deterministic plant: radio DAC clock offset, FIFO integrating the rate difference, a
    /// per-frame ripple on the measurement and one 50 ms control period of measurement delay.
    fn run_plant(offset_ppm: f64, start_fill: f64, target: f64, secs: f64) -> (f64, f64, f64) {
        let mut p = Pacer::new(target);
        let dt = CONTROL_PERIOD.as_secs_f64();
        let mut fill = start_fill;
        let mut measured = fill;
        let mut worst_late = 0.0f64;
        let steps = (secs / dt) as usize;
        for i in 0..steps {
            let ripple = if i % 2 == 0 { 466.0 } else { -466.0 };
            let trim = p.update(measured + ripple, dt);
            // samples/s gained = rate * (trim - offset) ppm
            fill += NOMINAL_RATE * (trim - offset_ppm) * 1e-6 * dt;
            measured = fill;
            if i as f64 * dt > secs / 2.0 {
                worst_late = worst_late.max((fill - target).abs());
            }
        }
        (fill, p.trim_ppm, worst_late)
    }

    #[test]
    fn pacer_locks_to_clock_offset() {
        for &offset in &[-200.0, -30.0, 0.0, 45.0, 300.0] {
            let (fill, trim, worst) = run_plant(offset, 8192.0, 12000.0, 20.0);
            assert!((fill - 12000.0).abs() < 50.0, "offset {offset}: fill {fill}");
            // the last update includes one ripple sample: Kp * 466 = 12 ppm
            assert!((trim - offset).abs() < 13.0, "offset {offset}: trim {trim}");
            assert!(worst < 500.0, "offset {offset}: second-half deviation {worst}");
        }
    }

    #[test]
    fn pacer_step_does_not_overshoot_the_fifo() {
        // Start near empty with a 100 ppm offset: the fill must never exceed the FIFO depth.
        let mut p = Pacer::new(12000.0);
        let dt = CONTROL_PERIOD.as_secs_f64();
        let mut fill = 1000.0f64;
        let mut max_fill = 0.0f64;
        for _ in 0..400 {
            let trim = p.update(fill, dt);
            fill += NOMINAL_RATE * (trim - 100.0) * 1e-6 * dt;
            max_fill = max_fill.max(fill);
        }
        assert!(max_fill < protocol::TX_FIFO_DEPTH as f64 - 1500.0, "max fill {max_fill}");
    }
}
