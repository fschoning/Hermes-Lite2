// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Franz Schöning, https://www.schoning.com
//
//! Receive orchestration: socket setup, recv thread, checker thread, optional save-to-file,
//! and the once-a-second status line.

use crate::auxchan;
use crate::duplex;
use crate::protocol;
use crate::ring::{Ring, MAX_FRAME};
use crate::stats::{self, DuplexSummary, PerSecond, Stats};
use crate::winsys;
use socket2::{Domain, Socket, Type};
use std::io::Write;
use std::net::{IpAddr, SocketAddr, UdpSocket};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

pub struct ReceiveOptions {
    pub seconds: Option<f64>, // None = run until Ctrl-C / stop_flag
    pub save_path: Option<String>,
    pub save_seconds: Option<f64>,
    pub pattern_mode: bool,
    pub ring_slots: usize,
    /// `--duplex`: run the TX sender alongside the receiver.
    pub duplex: Option<DuplexRun>,
    /// `--aux-rate`: run the aux channel test alongside.
    pub aux: Option<auxchan::AuxOptions>,
    /// `--echo`: check the echoed TX samples and measure round-trip latency (needs `duplex`).
    pub echo: bool,
}

pub struct DuplexRun {
    pub sender: duplex::SenderOptions,
    /// Radio TX errors in the first `lock_in_secs` after the sender starts do not count.
    pub lock_in_secs: f64,
}

/// Open, size and bind the socket used for both sending start/stop and receiving the stream.
/// Must be called and bound BEFORE start is sent (see protocol.rs A3 / the plan's ICMP rule).
pub fn open_socket(local_ip: IpAddr, requested_rcvbuf: usize) -> std::io::Result<UdpSocket> {
    let domain = match local_ip {
        IpAddr::V4(_) => Domain::IPV4,
        IpAddr::V6(_) => Domain::IPV6,
    };
    let sock = Socket::new(domain, Type::DGRAM, None)?;
    if let Err(e) = sock.set_recv_buffer_size(requested_rcvbuf) {
        println!("rawcap: warning: set_recv_buffer_size failed: {e}");
    }
    let granted = sock.recv_buffer_size().unwrap_or(0);
    println!(
        "rawcap: requested SO_RCVBUF={} bytes, granted={} bytes ({:.1} MB)",
        requested_rcvbuf,
        granted,
        granted as f64 / 1e6
    );
    sock.bind(&SocketAddr::new(local_ip, 0).into())?;
    // Read timeout so the recv thread notices shutdown promptly even with no traffic.
    sock.set_read_timeout(Some(Duration::from_secs(2)))?;
    Ok(sock.into())
}

/// Run the receive+check loop for `opts.seconds` (or until `stop_flag` is set / Ctrl-C).
/// `sock` must already be open (and, for a real HL2 run, start already sent by the caller).
pub fn run(sock: UdpSocket, opts: ReceiveOptions, stop_flag: Arc<AtomicBool>) -> std::io::Result<(Arc<Stats>, bool)> {
    let ring = Arc::new(Ring::new(opts.ring_slots));
    let stats = Arc::new(Stats::new());
    let epoch = Instant::now();
    let send_times = if opts.echo { Some(Arc::new(duplex::SendTimes::new(epoch))) } else { None };
    stats.echo.store(opts.echo, Ordering::Relaxed);
    let running = Arc::new(AtomicBool::new(true));
    let tx_running = Arc::new(AtomicBool::new(true));

    let save_until = opts.save_seconds.map(|s| Instant::now() + Duration::from_secs_f64(s));
    let save_file: Option<Arc<Mutex<std::fs::File>>> = match &opts.save_path {
        Some(path) => Some(Arc::new(Mutex::new(std::fs::File::create(path)?))),
        None => None,
    };
    let save_bytes_written = Arc::new(std::sync::atomic::AtomicU64::new(0));

    // ---- recv thread: nothing but recv_from into the ring ----
    let recv_ring = ring.clone();
    let recv_stats = stats.clone();
    let recv_running = running.clone();
    let recv_sock = sock.try_clone()?;
    let recv_thread = std::thread::Builder::new()
        .name("rawcap-recv".into())
        .spawn(move || {
            winsys::raise_current_thread_priority();
            let mut scratch = [0u8; MAX_FRAME];
            while recv_running.load(Ordering::Relaxed) {
                match recv_sock.recv_from(&mut scratch) {
                    Ok((n, _from)) => {
                        let queued = winsys::fionread(&recv_sock);
                        recv_stats.max_queued_bytes.fetch_max(queued as u64, Ordering::Relaxed);
                        let ts = epoch.elapsed().as_nanos() as u64;
                        if let Some((idx, buf)) = recv_ring.try_reserve() {
                            buf[..n].copy_from_slice(&scratch[..n]);
                            recv_ring.publish(idx, n, ts);
                        } else {
                            recv_ring.drops.fetch_add(1, Ordering::Relaxed);
                        }
                    }
                    Err(e)
                        if e.kind() == std::io::ErrorKind::WouldBlock
                            || e.kind() == std::io::ErrorKind::TimedOut =>
                    {
                        continue;
                    }
                    Err(e) => {
                        eprintln!("rawcap: recv error: {e}");
                        break;
                    }
                }
            }
        })?;

    // ---- checker thread: sequence/index/pattern checks, save-to-file ----
    let chk_ring = ring.clone();
    let chk_stats = stats.clone();
    let chk_running = running.clone();
    let chk_save_file = save_file.clone();
    let chk_save_bytes = save_bytes_written.clone();
    let pattern_mode = opts.pattern_mode;
    let chk_send_times = send_times.clone();
    let checker_thread = std::thread::Builder::new()
        .name("rawcap-check".into())
        .spawn(move || {
            checker_loop(
                &chk_ring,
                &chk_stats,
                &chk_running,
                pattern_mode,
                &chk_save_file,
                &chk_save_bytes,
                save_until,
                chk_send_times.as_deref(),
            );
        })?;

    // ---- optional TX sender ----
    let mut lock_in_secs = 0.0;
    let tx_thread = match opts.duplex {
        Some(mut d) => {
            stats.duplex.store(true, Ordering::Relaxed);
            lock_in_secs = d.lock_in_secs;
            d.sender.send_times = send_times.clone();
            Some(duplex::spawn(d.sender, stats.clone(), tx_running.clone())?)
        }
        None => None,
    };
    let mut aux_run = match opts.aux {
        Some(a) => Some(auxchan::start(a)?),
        None => None,
    };
    let mut tx_start: Option<Instant> = None;
    let mut at_lock: Option<(stats::RadioTx, Instant)> = None;

    // ---- main thread: print once/sec, honour --seconds / Ctrl-C / stop_flag ----
    let start = Instant::now();
    let mut prev = PerSecond::default();
    let mut last_print = Instant::now();
    loop {
        std::thread::sleep(Duration::from_millis(20));
        if tx_thread.is_some() {
            if tx_start.is_none() && stats.tx_started.load(Ordering::Relaxed) {
                tx_start = Some(Instant::now());
            }
            if let Some(t) = tx_start {
                if at_lock.is_none() && t.elapsed().as_secs_f64() >= lock_in_secs {
                    at_lock = Some((stats.radio_tx(), Instant::now()));
                    println!("rawcap: TX lock-in finished, radio counters from here on must not change");
                }
            }
        }
        if last_print.elapsed() >= Duration::from_secs(1) {
            let delta = stats.snapshot_and_reset_persecond(&prev);
            stats::print_line(&stats, &delta);
            if let Some(a) = aux_run.as_mut() {
                a.print_line();
            }
            prev = delta;
            std::io::stdout().flush().ok();
            last_print = Instant::now();
        }
        if winsys::ctrlc_pressed() || stop_flag.load(Ordering::Relaxed) {
            println!("rawcap: stopping (Ctrl-C or stop requested)");
            break;
        }
        if let Some(secs) = opts.seconds {
            if start.elapsed().as_secs_f64() >= secs {
                break;
            }
        }
    }

    // Stop the TX sender first and take the radio's counters at that moment: once TX frames stop,
    // the radio FIFO drains and its underflow count rises, which is not a fault. Then keep
    // receiving briefly so the last headers arrive.
    // Aux first: its echo drains while the sample stream is still running.
    let aux_result = aux_run.map(|a| a.stop());
    let mut duplex_summary = None;
    if let Some(t) = tx_thread {
        let stop_at = Instant::now();
        // Let the latest headers (reported within a frame or two) catch up to the last frames sent.
        std::thread::sleep(Duration::from_millis(5));
        tx_running.store(false, Ordering::Relaxed);
        let _ = t.join();
        let at_end = stats.radio_tx();
        std::thread::sleep(Duration::from_millis(300));
        duplex_summary = Some(DuplexSummary {
            measured_secs: at_lock.map(|(_, t)| stop_at.duration_since(t).as_secs_f64()).unwrap_or(0.0),
            at_lock: at_lock.map(|(r, _)| r),
            at_end,
            lock_in_secs,
        });
    }

    running.store(false, Ordering::Relaxed);
    let _ = recv_thread.join();
    let _ = checker_thread.join();

    let mut pass = stats::print_summary(&stats, start.elapsed().as_secs_f64(), duplex_summary.as_ref());
    if opts.echo {
        let at_end = duplex_summary.as_ref().map(|d| d.at_end).unwrap_or_default();
        pass &= stats::print_echo_summary(&stats, start.elapsed().as_secs_f64(), &at_end);
    }
    if let Some(r) = &aux_result {
        pass &= auxchan::print_summary(r);
    }

    if let Some(path) = &opts.save_path {
        let bytes = save_bytes_written.load(Ordering::Relaxed);
        let sidecar = format!("{path}.json");
        let json = format!(
            "{{\n  \"format\": \"packed_payload_be_12bit_2per3bytes\",\n  \"adc_rate_sps\": 76800000,\n  \"payload_bytes\": {bytes},\n  \"note\": \"Payload bytes only, headers stripped, frames concatenated in arrival order. Unpack 2 samples per 3 bytes, big-endian, as in rawcap/src/protocol.rs unpack_samples_i16 and analyse.py.\"\n}}\n"
        );
        std::fs::write(&sidecar, json)?;
        println!("rawcap: saved {bytes} bytes of packed payload to {path}, sidecar {sidecar}");
    }

    Ok((stats, pass))
}

/// Echo checker state carried across frames.
#[derive(Default)]
struct EchoState {
    prev_offset: Option<i64>,
}

#[allow(clippy::too_many_arguments)]
fn checker_loop(
    ring: &Ring,
    stats: &Stats,
    running: &AtomicBool,
    pattern_mode: bool,
    save_file: &Option<Arc<Mutex<std::fs::File>>>,
    save_bytes_written: &Arc<std::sync::atomic::AtomicU64>,
    save_until: Option<Instant>,
    send_times: Option<&duplex::SendTimes>,
) {
    let mut last_seq: Option<u32> = None;
    let mut last_index_end: Option<u64> = None;
    let mut samples_buf: Vec<i16> = Vec::with_capacity(6000);
    let mut echo_state = EchoState::default();

    while running.load(Ordering::Relaxed) {
        match ring.try_pop() {
            Some((idx, data)) => {
                let ts = ring.ts(idx);
                process_one(
                    data,
                    &mut last_seq,
                    &mut last_index_end,
                    &mut samples_buf,
                    pattern_mode,
                    stats,
                    save_file,
                    save_bytes_written,
                    save_until,
                );
                if let Some(st) = send_times {
                    check_echo(data, ts, st, &mut echo_state, &mut samples_buf, stats);
                }
                ring.release(idx);
            }
            None => {
                std::thread::sleep(Duration::from_micros(200));
            }
        }
    }
}

#[allow(clippy::too_many_arguments)]
fn process_one(
    data: &[u8],
    last_seq: &mut Option<u32>,
    last_index_end: &mut Option<u64>,
    samples_buf: &mut Vec<i16>,
    pattern_mode: bool,
    stats: &Stats,
    save_file: &Option<Arc<Mutex<std::fs::File>>>,
    save_bytes_written: &Arc<std::sync::atomic::AtomicU64>,
    save_until: Option<Instant>,
) {
    let header = match protocol::FrameHeader::parse(data) {
        Some(h) => h,
        None => return,
    };
    let payload = &data[header.header_len..];

    // ---- duplex: radio TX sink status (version 2 frames) ----
    if let Some(tx) = header.tx {
        stats.v2_frames.fetch_add(1, Ordering::Relaxed);
        stats.rtx_frames.store(tx.frames as u64, Ordering::Relaxed);
        stats.rtx_lost.store(tx.lost_frames as u64, Ordering::Relaxed);
        stats.rtx_bad.store(tx.bad_samples as u64, Ordering::Relaxed);
        stats.rtx_unf.store(tx.underflows as u64, Ordering::Relaxed);
        stats.rtx_ovf.store(tx.overflows as u64, Ordering::Relaxed);
        stats.rtx_flags.store(tx.flags as u64, Ordering::Relaxed);
        let fill = tx.fifo_fill as u64;
        stats.rtx_fill.store(fill, Ordering::Relaxed);
        stats.rtx_fill_min.fetch_min(fill, Ordering::Relaxed);
        stats.rtx_fill_max.fetch_max(fill, Ordering::Relaxed);
        stats.rtx_fill_sum.fetch_add(fill, Ordering::Relaxed);
        stats.rtx_fill_cnt.fetch_add(1, Ordering::Relaxed);
    }

    // ---- transmit-safety status byte ----
    let safety = header.safety as u64;
    if stats.frames_total.load(Ordering::Relaxed) > 0 && stats.safety_last.load(Ordering::Relaxed) != safety {
        stats.safety_changes.fetch_add(1, Ordering::Relaxed);
    }
    stats.safety_last.store(safety, Ordering::Relaxed);
    stats.safety_any.fetch_or(safety, Ordering::Relaxed);

    stats.frames_total.fetch_add(1, Ordering::Relaxed);
    stats.bytes_total.fetch_add(data.len() as u64, Ordering::Relaxed);
    stats.samples_total.fetch_add(header.samples_in_frame as u64, Ordering::Relaxed);

    // ---- sequence-number continuity ----
    if let Some(prev) = *last_seq {
        let expected = prev.wrapping_add(1);
        if header.seq != expected {
            if header.seq > expected {
                stats.lost_frames.fetch_add((header.seq - expected) as u64, Ordering::Relaxed);
            } else {
                stats.reordered_or_dup.fetch_add(1, Ordering::Relaxed);
            }
        }
    }
    *last_seq = Some(header.seq);

    // ---- sample-index continuity ----
    let this_end = header.first_sample_index + header.samples_in_frame as u64;
    if let Some(expected_start) = *last_index_end {
        if header.first_sample_index > expected_start {
            let skipped_samples = header.first_sample_index - expected_start;
            stats.lost_samples.fetch_add(skipped_samples, Ordering::Relaxed);
        } else if header.first_sample_index < expected_start {
            stats.reordered_or_dup.fetch_add(1, Ordering::Relaxed);
        }
    }
    *last_index_end = Some(this_end);

    // ---- HL2-reported overflow / clip / FIFO high-water ----
    if header.is_overflow() {
        stats.hl2_overflow_frames.fetch_add(1, Ordering::Relaxed);
    }
    if header.is_gap() {
        stats.hl2_gap_frames.fetch_add(1, Ordering::Relaxed);
    }
    stats.hl2_overflow_events.store(header.overflow_count as u64, Ordering::Relaxed);
    stats.fifo_high_water.fetch_max(header.fifo_high_water as u64, Ordering::Relaxed);
    // adc_clip_frames counts frames carrying the clip flag; per docs/rawfront/PROTOCOL.md that flag
    // describes the PREVIOUS frame's samples, not this one's (see is_adc_clip_prev_frame's
    // doc comment). In pattern mode this fires regularly and is expected, not a fault.
    if header.is_adc_clip_prev_frame() {
        stats.adc_clip_frames.fetch_add(1, Ordering::Relaxed);
    }

    // ---- counter-pattern check (pattern mode only; not in echo mode: the samples are the echo) ----
    let echo_mode = header.tx.map(|t| t.flags & protocol::TX_FLAG_ECHO != 0).unwrap_or(false);
    let pattern_mode = pattern_mode && !echo_mode;
    // docs/rawfront/PROTOCOL.md "Test pattern": sample k of this frame equals (first_sample_index + k) mod
    // 4096. Checked directly against the header's own index field (protocol::expected_pattern_
    // value), not reconstructed by carrying a running value across frames -- that way a lost or
    // reordered frame can't cascade into spurious mismatches on every frame after it.
    if pattern_mode {
        samples_buf.clear();
        protocol::unpack_samples_i16(payload, samples_buf);
        for (k, &s) in samples_buf.iter().enumerate() {
            let v = (s as u16) & 0x0fff;
            let expected = protocol::expected_pattern_value(header.first_sample_index, k);
            if v != expected {
                stats.bad_samples.fetch_add(1, Ordering::Relaxed);
            }
        }
    }

    // ---- optional save-to-file (packed payload bytes, headers stripped) ----
    if let Some(f) = save_file {
        let still_saving = match save_until {
            Some(deadline) => Instant::now() < deadline,
            None => true,
        };
        if still_saving {
            if let Ok(mut file) = f.lock() {
                if file.write_all(payload).is_ok() {
                    save_bytes_written.fetch_add(payload.len() as u64, Ordering::Relaxed);
                }
            }
        }
    }
}

/// `--echo`: every sample of a frame with a valid offset must be the TX counter-pattern sample with index
/// (RX index + offset), or 0 while the radio played nothing. Mismatches in a frame whose offset differs
/// from the previous frame's are samples written before the offset changed (after an underflow, a lost
/// TX frame or an overflow) and are counted apart. Round trip: receive time of this frame minus the send
/// time of the TX frame that carried its first echoed sample.
fn check_echo(
    data: &[u8],
    ts_ns: u64,
    send_times: &duplex::SendTimes,
    state: &mut EchoState,
    samples_buf: &mut Vec<i16>,
    stats: &Stats,
) {
    let header = match protocol::FrameHeader::parse(data) {
        Some(h) => h,
        None => return,
    };
    let (tx, echo) = match (header.tx, header.echo) {
        (Some(t), Some(e)) => (t, e),
        _ => return,
    };
    stats.v3_frames.fetch_add(1, Ordering::Relaxed);
    stats.trips_last.store(echo.trips as u64, Ordering::Relaxed);
    stats.echo_flags_last.store(echo.flags as u64, Ordering::Relaxed);
    if tx.flags & protocol::TX_FLAG_ECHO == 0 || echo.flags & protocol::ECHO_F_VALID == 0 {
        state.prev_offset = None;
        return;
    }
    stats.echo_frames.fetch_add(1, Ordering::Relaxed);
    let off = echo.offset;
    let steady = state.prev_offset == Some(off);
    if state.prev_offset.is_some() && !steady {
        stats.echo_off_changes.fetch_add(1, Ordering::Relaxed);
    }
    stats.echo_offset.store(off, Ordering::Relaxed);

    samples_buf.clear();
    protocol::unpack_samples_i16(&data[header.header_len..], samples_buf);
    let (mut good, mut zero, mut unsettled, mut bad) = (0u64, 0u64, 0u64, 0u64);
    for (k, &s) in samples_buf.iter().enumerate() {
        let v = (s as u16) & 0x0fff;
        let tx_index = header.first_sample_index as i64 + k as i64 + off;
        if tx_index >= 0 && v == (tx_index as u64 & 0x0fff) as u16 {
            good += 1;
        } else if v == 0 {
            zero += 1;
        } else if !steady {
            unsettled += 1;
        } else {
            bad += 1;
        }
    }
    if bad > 0 && std::env::var("RAWCAP_ECHO_DEBUG").is_ok() {
        let v0 = (samples_buf[0] as u16 & 0x0fff) as i64;
        let vl = (samples_buf[samples_buf.len() - 1] as u16 & 0x0fff) as i64;
        let first_idx = header.first_sample_index as i64;
        println!(
            "echo-debug BAD: rx seq {} idx {} off {} prev {:?} good {} zero {} bad {} | first sample {} (data offset mod 4096 {}), last {} (data offset mod 4096 {}) | fill {} unf {} ovf {} flags {:02x} b46 {:02x}",
            header.seq, first_idx, off, state.prev_offset, good, zero, bad,
            v0, (v0 - first_idx).rem_euclid(4096), vl, (vl - first_idx - samples_buf.len() as i64 + 1).rem_euclid(4096),
            tx.fifo_fill, tx.underflows, tx.overflows, tx.flags, echo.flags
        );
    }
    stats.echo_good.fetch_add(good, Ordering::Relaxed);
    stats.echo_zero.fetch_add(zero, Ordering::Relaxed);
    stats.echo_unsettled.fetch_add(unsettled, Ordering::Relaxed);
    stats.echo_bad.fetch_add(bad, Ordering::Relaxed);

    // latency only from frames whose samples all match (a zero sample matches a pattern value of 0)
    if steady && zero == 0 && unsettled == 0 && bad == 0 && good as usize == samples_buf.len() {
        if let Some(sent) = send_times.sent_ns(header.first_sample_index as i64 + off) {
            if ts_ns > sent {
                let us = (ts_ns - sent) / 1000;
                if std::env::var("RAWCAP_ECHO_DEBUG").is_ok() && (us < 80 || us > 5_000) {
                    let n = send_times.samples.load(Ordering::Relaxed);
                    let txi = header.first_sample_index as i64 + off;
                    println!(
                        "echo-debug: rx seq {} idx {} off {} -> tx idx {} (frame {}) lat {} us good {} zero {} unsettled {} fill {} flags {:02x}",
                        header.seq, header.first_sample_index, off, txi, txi as u64 / n.max(1), us, good, zero, unsettled, tx.fifo_fill, tx.flags
                    );
                }
                stats.lat_sum_us.fetch_add(us, Ordering::Relaxed);
                stats.lat_cnt.fetch_add(1, Ordering::Relaxed);
                stats.lat_min_us.fetch_min(us, Ordering::Relaxed);
                stats.lat_max_us.fetch_max(us, Ordering::Relaxed);
            }
        }
    }
    state.prev_offset = Some(off);
}
