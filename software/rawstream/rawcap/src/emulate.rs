// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Franz Schöning, https://www.schoning.com
//
//! `--emulate`: a sender that behaves enough like the real HL2 raw-stream gateware to test
//! rawcap's receive path with no radio attached. Listens for the same discovery / register /
//! start / stop packets a real HL2 would see, and streams correctly formatted frames (counter
//! pattern or a synthetic tone) to whoever sent start, at a configurable pace.
//!
//! Duplex (register 0x31, docs/rawfront/PROTOCOL.md): TX frames on port 1026 go into a software model of the
//! radio's TX sink -- sequence and pattern checks, and a 16,384-sample FIFO drained on the wall
//! clock at 76.8 MSPS x rate-fraction x (1 + dac-ppm) -- and raw frames carry version 2 headers
//! with its status, so `rawcap --duplex` and its pacing loop can be tested on loopback.
//!
//! Echo (register 0x31 bit 2, hl2b5up_raw docs/rawfront/PROTOCOL.md): raw frames carry version 3 headers and the
//! samples are the TX counter pattern at a fixed offset from the RX index while the modelled DAC plays
//! (zeros while it refills); the offset is taken again after an underflow, a lost TX frame or an
//! overflow, as the gateware does. Enough to test `rawcap --echo` on loopback.
//!
//! Limitations vs the real HL2 (documented in README.md's assumption list too):
//!   - No real FIFO: "quiet-capture" mode is accepted but streamed continuously rather than
//!     bursted, and overflow/FIFO-high-water fields are always reported as zero.
//!   - Pacing is done by spin-waiting on the wall clock, so hitting the full 921.6 Mbit/s
//!     sample rate depends on the host CPU and the loopback/NIC path, not on real silicon.

use crate::protocol;
use std::net::{IpAddr, SocketAddr, UdpSocket};
use std::sync::atomic::{AtomicBool, AtomicU16, AtomicU32, AtomicU64, Ordering};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

pub struct EmulateOptions {
    pub bind_ip: IpAddr,
    pub tone_hz: f64,
    pub tone_amp_fraction: f64, // 0..1 of full-scale 12-bit (2047)
    pub gap_every: Option<u64>, // deliberately drop one frame every N frames, for testing gap detection
    pub rate_fraction: f64,     // scale factor on the 76.8 MSPS pacing clock; 1.0 = full rate
    pub dac_ppm: f64,           // emulated TX DAC clock error (duplex)
    pub seconds: Option<f64>,
}

/// Software model of the duplex image's TX sink (rtl/txsink.v).
struct TxSink {
    frames: u32,
    lost: u32,
    bad: u32,
    unf: u16,
    ovf: u16,
    have_seq: bool,
    exp_seq: u32,
    buffered: f64,
    playing: bool,
    ovf_active: bool,
    last: Instant,
    rate: f64,
    /// TX index just after the last sample received.
    last_end: u64,
    /// A lost frame or an overflow since the echo offset was taken.
    resync: bool,
    /// Echo offset (TX index minus RX index) while playing.
    echo_off: Option<i64>,
}

impl TxSink {
    fn new(rate: f64) -> TxSink {
        TxSink {
            frames: 0,
            lost: 0,
            bad: 0,
            unf: 0,
            ovf: 0,
            have_seq: false,
            exp_seq: 0,
            buffered: 0.0,
            playing: false,
            ovf_active: false,
            last: Instant::now(),
            rate,
            last_end: 0,
            resync: false,
            echo_off: None,
        }
    }

    fn advance(&mut self) {
        let now = Instant::now();
        let dt = now.duration_since(self.last).as_secs_f64();
        self.last = now;
        if self.playing {
            self.buffered -= dt * self.rate;
            if self.buffered < 0.0 {
                self.buffered = 0.0;
                self.playing = false;
                self.echo_off = None;
                self.unf = self.unf.saturating_add(1);
            }
        }
    }

    fn frame(&mut self, h: &protocol::TxHeader, payload: &[u8]) {
        self.advance();
        self.frames = self.frames.wrapping_add(1);
        if self.have_seq && h.seq != self.exp_seq && h.seq > self.exp_seq {
            self.lost = self.lost.wrapping_add(h.seq - self.exp_seq);
            self.resync = true;
        }
        self.have_seq = true;
        self.exp_seq = h.seq.wrapping_add(1);
        let n = (h.samples as usize).min(payload.len() / 3 * 2);
        let mut v = (h.first_sample_index % 4096) as u16;
        for pair in payload[..n / 2 * 3].chunks_exact(3) {
            let a = ((pair[0] as u16) << 4) | (pair[1] as u16 >> 4);
            let b = (((pair[1] & 0x0f) as u16) << 8) | pair[2] as u16;
            if a != v {
                self.bad = self.bad.saturating_add(1);
            }
            if b != ((v + 1) & 0x0fff) {
                self.bad = self.bad.saturating_add(1);
            }
            v = (v + 2) & 0x0fff;
        }
        self.buffered += n as f64;
        self.last_end = h.first_sample_index + n as u64;
        let depth = protocol::TX_FIFO_DEPTH as f64;
        if self.buffered > depth {
            self.resync = true;
            if !self.ovf_active {
                self.ovf = self.ovf.saturating_add(1);
            }
            self.ovf_active = true;
            self.buffered = depth;
        } else {
            self.ovf_active = false;
        }
        if !self.playing && self.buffered >= depth / 2.0 {
            self.playing = true;
        }
    }

    /// Echo offset for an RX frame starting at `rx_index`, or None while nothing plays.
    fn echo_offset(&mut self, rx_index: u64) -> Option<i64> {
        self.advance();
        if !self.playing {
            return None;
        }
        if self.echo_off.is_none() || self.resync {
            self.resync = false;
            let play = self.last_end as f64 - self.buffered;
            self.echo_off = Some(play as i64 - rx_index as i64);
        }
        self.echo_off
    }

    fn status(&mut self, active: bool) -> protocol::TxStatus {
        self.advance();
        let mut flags = 0;
        if active {
            flags |= protocol::TX_FLAG_ACTIVE;
            if self.playing {
                flags |= protocol::TX_FLAG_DAC_PLAYING;
            }
        }
        protocol::TxStatus {
            frames: self.frames,
            lost_frames: self.lost,
            bad_samples: self.bad,
            fifo_fill: self.buffered as u16,
            underflows: self.unf,
            overflows: self.ovf,
            flags,
        }
    }
}

#[derive(Default)]
struct RawMode {
    enable: bool,
    test_pattern: bool,
    quiet_capture: bool,
    samples_per_frame: u16,
}

pub fn run(opts: EmulateOptions, stop_flag: Arc<AtomicBool>) -> std::io::Result<()> {
    println!(
        "rawcap --emulate: listening on {} ports {} (discovery/registers) and {} (start/stop)",
        opts.bind_ip,
        protocol::PORT_CMD,
        protocol::PORT_START_STOP
    );

    let mode = Arc::new(Mutex::new(RawMode {
        enable: false,
        test_pattern: true,
        quiet_capture: false,
        samples_per_frame: 968,
    }));
    let stream_dest: Arc<Mutex<Option<SocketAddr>>> = Arc::new(Mutex::new(None));
    let duplex_on = Arc::new(AtomicBool::new(false));
    let duplex_reg = Arc::new(AtomicU32::new(0));
    let dac_rate = 76_800_000.0 * opts.rate_fraction.max(0.001) * (1.0 + opts.dac_ppm * 1e-6);
    let sink = Arc::new(Mutex::new(TxSink::new(dac_rate)));
    let streaming = Arc::new(AtomicBool::new(false));
    let generation = Arc::new(AtomicU32::new(0)); // bumped on each start, so the stream thread resets seq/index

    let frames_sent = Arc::new(AtomicU64::new(0));
    let bytes_sent = Arc::new(AtomicU64::new(0));
    let gaps_injected = Arc::new(AtomicU64::new(0));
    let last_frame_size = Arc::new(AtomicU16::new(0));

    // ---- port 1025: discovery + register writes ----
    let sock_1025 = UdpSocket::bind(SocketAddr::new(opts.bind_ip, protocol::PORT_CMD))?;
    {
        let mode = mode.clone();
        let duplex_on = duplex_on.clone();
        let duplex_reg = duplex_reg.clone();
        std::thread::Builder::new()
            .name("emu-ctrl-1025".into())
            .spawn(move || ctrl_1025_loop(sock_1025, mode, duplex_on, duplex_reg))?;
    }

    // ---- port 1026: duplex TX frames ----
    let sock_1026 = UdpSocket::bind(SocketAddr::new(opts.bind_ip, protocol::PORT_TX))?;
    {
        let sink = sink.clone();
        let duplex_on = duplex_on.clone();
        let streaming = streaming.clone();
        std::thread::Builder::new()
            .name("emu-tx-1026".into())
            .spawn(move || tx_1026_loop(sock_1026, sink, duplex_on, streaming))?;
    }

    // ---- port 1024: start/stop ----
    let sock_1024 = UdpSocket::bind(SocketAddr::new(opts.bind_ip, protocol::PORT_START_STOP))?;
    {
        let stream_dest = stream_dest.clone();
        let streaming = streaming.clone();
        let generation = generation.clone();
        let sink = sink.clone();
        std::thread::Builder::new()
            .name("emu-ctrl-1024".into())
            .spawn(move || ctrl_1024_loop(sock_1024, stream_dest, streaming, generation, sink, dac_rate))?;
    }

    // ---- streaming thread ----
    let send_sock = UdpSocket::bind(SocketAddr::new(opts.bind_ip, 0))?;
    {
        let mode = mode.clone();
        let stream_dest = stream_dest.clone();
        let streaming = streaming.clone();
        let generation = generation.clone();
        let frames_sent = frames_sent.clone();
        let bytes_sent = bytes_sent.clone();
        let gaps_injected = gaps_injected.clone();
        let last_frame_size = last_frame_size.clone();
        let sink = sink.clone();
        let duplex_on = duplex_on.clone();
        let duplex_reg = duplex_reg.clone();
        std::thread::Builder::new()
            .name("emu-stream".into())
            .spawn(move || {
                stream_loop(
                    send_sock,
                    sink,
                    duplex_on,
                    duplex_reg,
                    mode,
                    stream_dest,
                    streaming,
                    generation,
                    opts.tone_hz,
                    opts.tone_amp_fraction,
                    opts.gap_every,
                    opts.rate_fraction,
                    frames_sent,
                    bytes_sent,
                    gaps_injected,
                    last_frame_size,
                );
            })?;
    }

    // ---- main thread: once/sec status, honour --seconds / Ctrl-C / stop_flag ----
    let start = Instant::now();
    let mut prev_frames = 0u64;
    let mut prev_bytes = 0u64;
    loop {
        std::thread::sleep(Duration::from_secs(1));
        let f = frames_sent.load(Ordering::Relaxed);
        let b = bytes_sent.load(Ordering::Relaxed);
        let df = f - prev_frames;
        let db = b - prev_bytes;
        prev_frames = f;
        prev_bytes = b;
        let active = streaming.load(Ordering::Relaxed);
        println!(
            "emulate: streaming={} frames/s={} Mbit/s={:.1} gaps_injected={} frame_bytes={}",
            active,
            df,
            (db as f64 * 8.0) / 1_000_000.0,
            gaps_injected.load(Ordering::Relaxed),
            last_frame_size.load(Ordering::Relaxed)
        );
        if crate::winsys::ctrlc_pressed() || stop_flag.load(Ordering::Relaxed) {
            println!("rawcap --emulate: stopping");
            break;
        }
        if let Some(secs) = opts.seconds {
            if start.elapsed().as_secs_f64() >= secs {
                break;
            }
        }
    }

    println!(
        "rawcap --emulate summary: frames_sent={} bytes_sent={} gaps_injected={}",
        frames_sent.load(Ordering::Relaxed),
        bytes_sent.load(Ordering::Relaxed),
        gaps_injected.load(Ordering::Relaxed)
    );
    Ok(())
}

fn tx_1026_loop(sock: UdpSocket, sink: Arc<Mutex<TxSink>>, duplex_on: Arc<AtomicBool>, streaming: Arc<AtomicBool>) {
    sock.set_read_timeout(Some(Duration::from_secs(1))).ok();
    let _ = socket2::SockRef::from(&sock).set_recv_buffer_size(64 * 1024 * 1024);
    let mut buf = vec![0u8; crate::ring::MAX_FRAME];
    loop {
        match sock.recv_from(&mut buf) {
            Ok((n, _)) => {
                if !(duplex_on.load(Ordering::Relaxed) && streaming.load(Ordering::Relaxed)) {
                    continue;
                }
                if let Some(h) = protocol::parse_tx_header(&buf[..n]) {
                    sink.lock().unwrap().frame(&h, &buf[protocol::TX_HEADER_LEN..n]);
                }
            }
            Err(e) if e.kind() == std::io::ErrorKind::WouldBlock || e.kind() == std::io::ErrorKind::TimedOut => {}
            Err(e) => {
                eprintln!("emulate: tx 1026 recv error: {e}");
            }
        }
    }
}

fn ctrl_1025_loop(sock: UdpSocket, mode: Arc<Mutex<RawMode>>, duplex_on: Arc<AtomicBool>, duplex_reg: Arc<AtomicU32>) {
    sock.set_read_timeout(Some(Duration::from_secs(1))).ok();
    let mut buf = [0u8; 128];
    loop {
        match sock.recv_from(&mut buf) {
            Ok((n, from)) if n >= 3 && buf[0] == 0xEF && buf[1] == 0xFE => {
                match buf[2] {
                    0x02 => {
                        // Discovery request -> send a plausible fake discovery response so
                        // `rawcap --discover` also works against the emulator on loopback.
                        let resp = build_fake_discovery_response();
                        let _ = sock.send_to(&resp, from);
                    }
                    0x05 if n >= 9 => {
                        // Register write: EF FE 05 7F <addr<<1> <4-byte BE value> ...
                        let addr = buf[4] >> 1;
                        let value = u32::from_be_bytes([buf[5], buf[6], buf[7], buf[8]]);
                        if addr == protocol::REG_ADDR_RAWMODE {
                            let mut m = mode.lock().unwrap();
                            m.enable = value & protocol::REG_RAW_ENABLE != 0;
                            m.test_pattern = value & protocol::REG_RAW_TEST_PATTERN != 0;
                            m.quiet_capture = value & protocol::REG_RAW_QUIET_CAPTURE != 0;
                            // docs/rawfront/PROTOCOL.md: gateware rounds down to even, 0 means 968, values
                            // above 7,680 are cut to 7,680 -- match that here for fidelity.
                            let requested = ((value >> 16) & 0xffff) as u16;
                            let (clamped, _) = protocol::clamp_samples_per_frame(requested);
                            m.samples_per_frame = clamped;
                            println!(
                                "emulate: raw-mode register set: enable={} test_pattern={} quiet_capture={} samples/frame={} (requested {})",
                                m.enable, m.test_pattern, m.quiet_capture, m.samples_per_frame, requested
                            );
                        }
                        if addr == protocol::REG_ADDR_DUPLEX {
                            let on = value & protocol::REG_DUPLEX_ENABLE != 0;
                            duplex_on.store(on, Ordering::SeqCst);
                            duplex_reg.store(value, Ordering::SeqCst);
                            println!(
                                "emulate: duplex register set: {on}{}",
                                if value & protocol::REG_DUPLEX_ECHO != 0 { " (echo)" } else { "" }
                            );
                        }
                        let resp = build_fake_discovery_response();
                        let _ = sock.send_to(&resp, from);
                    }
                    _ => {}
                }
            }
            Ok(_) => {}
            Err(e) if e.kind() == std::io::ErrorKind::WouldBlock || e.kind() == std::io::ErrorKind::TimedOut => {}
            Err(e) => {
                eprintln!("emulate: ctrl 1025 recv error: {e}");
                break;
            }
        }
    }
}

fn ctrl_1024_loop(
    sock: UdpSocket,
    stream_dest: Arc<Mutex<Option<SocketAddr>>>,
    streaming: Arc<AtomicBool>,
    generation: Arc<AtomicU32>,
    sink: Arc<Mutex<TxSink>>,
    dac_rate: f64,
) {
    sock.set_read_timeout(Some(Duration::from_secs(1))).ok();
    let mut buf = [0u8; 128];
    loop {
        match sock.recv_from(&mut buf) {
            Ok((n, from)) if n >= 4 && buf[0] == 0xEF && buf[1] == 0xFE && buf[2] == 0x04 => {
                if buf[3] & 0x01 != 0 {
                    *stream_dest.lock().unwrap() = Some(from);
                    *sink.lock().unwrap() = TxSink::new(dac_rate);
                    generation.fetch_add(1, Ordering::SeqCst);
                    streaming.store(true, Ordering::SeqCst);
                    println!("emulate: start received from {from}, streaming");
                } else {
                    streaming.store(false, Ordering::SeqCst);
                    println!("emulate: stop received from {from}");
                }
            }
            Ok(_) => {}
            Err(e) if e.kind() == std::io::ErrorKind::WouldBlock || e.kind() == std::io::ErrorKind::TimedOut => {}
            Err(e) => {
                eprintln!("emulate: ctrl 1024 recv error: {e}");
                break;
            }
        }
    }
}

#[allow(clippy::too_many_arguments)]
fn stream_loop(
    sock: UdpSocket,
    sink: Arc<Mutex<TxSink>>,
    duplex_on: Arc<AtomicBool>,
    duplex_reg: Arc<AtomicU32>,
    mode: Arc<Mutex<RawMode>>,
    stream_dest: Arc<Mutex<Option<SocketAddr>>>,
    streaming: Arc<AtomicBool>,
    generation: Arc<AtomicU32>,
    tone_hz: f64,
    tone_amp_fraction: f64,
    gap_every: Option<u64>,
    rate_fraction: f64,
    frames_sent: Arc<AtomicU64>,
    bytes_sent: Arc<AtomicU64>,
    gaps_injected: Arc<AtomicU64>,
    last_frame_size: Arc<AtomicU16>,
) {
    let mut seq: u32 = 0;
    let mut sample_index: u64 = 0;
    let mut sample_phase: u16 = 0; // for the counter pattern
    let mut tone_phase: f64 = 0.0;
    let mut frame_count_since_start: u64 = 0;
    let mut last_generation = 0u32;
    let mut next_send = Instant::now();

    let mut frame_buf = vec![0u8; crate::ring::MAX_FRAME];

    loop {
        if !streaming.load(Ordering::Relaxed) {
            std::thread::sleep(Duration::from_millis(2));
            continue;
        }
        let gen = generation.load(Ordering::Relaxed);
        if gen != last_generation {
            // Fresh start: reset counters and mark the next frame as "first frame".
            last_generation = gen;
            seq = 0;
            sample_index = 0;
            sample_phase = 0;
            tone_phase = 0.0;
            frame_count_since_start = 0;
            next_send = Instant::now();
        }

        let (enable, test_pattern, quiet_capture, samples_per_frame) = {
            let m = mode.lock().unwrap();
            (m.enable, m.test_pattern, m.quiet_capture, m.samples_per_frame.max(2) & !1)
        };
        let dest = *stream_dest.lock().unwrap();
        let dest = match dest {
            Some(d) if enable => d,
            _ => {
                std::thread::sleep(Duration::from_millis(2));
                continue;
            }
        };

        // Pace to the (possibly scaled) 76.8 MSPS ADC clock: one frame every
        // samples_per_frame / (76_800_000 * rate_fraction) seconds. Spin rather than
        // thread::sleep for the last stretch: Windows' sleep granularity (~15 ms) is too
        // coarse for jumbo-frame pacing (~78 us/frame) let alone 1500-byte pacing (~12.6 us).
        let interval = Duration::from_secs_f64(samples_per_frame as f64 / (76_800_000.0 * rate_fraction.max(0.001)));
        let now = Instant::now();
        if now < next_send {
            let remaining = next_send - now;
            if remaining > Duration::from_micros(500) {
                std::thread::sleep(remaining - Duration::from_micros(200));
            }
            while Instant::now() < next_send {
                std::hint::spin_loop();
            }
        }
        next_send += interval;
        // If we've fallen far behind (e.g. loopback/CPU can't keep up), don't try to burst-
        // catch-up forever: resync so the reported rate reflects what was actually achieved.
        if Instant::now() > next_send + Duration::from_millis(50) {
            next_send = Instant::now() + interval;
        }

        frame_count_since_start += 1;
        let inject_gap = gap_every.map(|g| frame_count_since_start % g == 0).unwrap_or(false);

        let mut flags = 0u8;
        if test_pattern {
            flags |= protocol::FLAG_TEST_PATTERN;
        }
        if quiet_capture {
            flags |= protocol::FLAG_QUIET_CAPTURE;
        }
        if seq == 0 {
            flags |= protocol::FLAG_FIRST_FRAME;
        }

        if inject_gap {
            // Simulate a genuinely lost UDP packet: advance seq/sample_index as if the frame
            // had been built and sent, but never call send_to. The next real frame's header
            // will show the resulting sequence and sample-index gap.
            gaps_injected.fetch_add(1, Ordering::Relaxed);
            seq = seq.wrapping_add(1);
            sample_index += samples_per_frame as u64;
            if test_pattern {
                sample_phase = ((sample_phase as u32 + samples_per_frame as u32) % 4096) as u16;
            }
            continue;
        }

        let echo = duplex_on.load(Ordering::Relaxed) && duplex_reg.load(Ordering::Relaxed) & protocol::REG_DUPLEX_ECHO != 0;
        if echo {
            let (st, off) = {
                let mut s = sink.lock().unwrap();
                let off = s.echo_offset(sample_index);
                let mut st = s.status(true);
                st.flags |= protocol::TX_FLAG_ECHO;
                (st, off)
            };
            let e = protocol::EchoInfo {
                offset: off.unwrap_or(0),
                flags: protocol::ECHO_F_ECHO | if off.is_some() { protocol::ECHO_F_VALID } else { 0 },
                trips: 0,
            };
            let header = protocol::build_header_v3(flags & !protocol::FLAG_TEST_PATTERN, seq, sample_index, samples_per_frame, &st, &e);
            frame_buf[..protocol::HEADER_LEN_V3].copy_from_slice(&header);
            let mut w = protocol::HEADER_LEN_V3;
            for k in 0..(samples_per_frame as u64 / 2) {
                let (a, b) = match off {
                    Some(o) => {
                        let t = sample_index as i64 + 2 * k as i64 + o;
                        ((t & 0xfff) as u16, ((t + 1) & 0xfff) as u16)
                    }
                    None => (0, 0),
                };
                frame_buf[w..w + 3].copy_from_slice(&protocol::pack_pair(a, b));
                w += 3;
            }
            let _ = sock.send_to(&frame_buf[..w], dest);
            frames_sent.fetch_add(1, Ordering::Relaxed);
            bytes_sent.fetch_add(w as u64, Ordering::Relaxed);
            last_frame_size.store(w as u16, Ordering::Relaxed);
            seq = seq.wrapping_add(1);
            sample_index += samples_per_frame as u64;
            continue;
        }

        let mut w = if duplex_on.load(Ordering::Relaxed) {
            let st = sink.lock().unwrap().status(true);
            let header = protocol::build_header_v2(flags, seq, sample_index, samples_per_frame, &st);
            frame_buf[..protocol::HEADER_LEN_V2].copy_from_slice(&header);
            protocol::HEADER_LEN_V2
        } else {
            let header = protocol::build_header(flags, seq, sample_index, samples_per_frame, 0, 0);
            frame_buf[..protocol::HEADER_LEN].copy_from_slice(&header);
            protocol::HEADER_LEN
        };
        for _ in 0..(samples_per_frame / 2) {
            let (a, b) = if test_pattern {
                let a = sample_phase;
                let b = (sample_phase.wrapping_add(1)) & 0x0fff;
                sample_phase = (sample_phase.wrapping_add(2)) & 0x0fff;
                (a, b)
            } else {
                let a = tone_sample(tone_phase, tone_amp_fraction);
                tone_phase += tone_hz / 76_800_000.0;
                let b = tone_sample(tone_phase, tone_amp_fraction);
                tone_phase += tone_hz / 76_800_000.0;
                if tone_phase > 1.0 {
                    tone_phase -= 1.0;
                }
                (a, b)
            };
            let bytes = protocol::pack_pair(a, b);
            frame_buf[w..w + 3].copy_from_slice(&bytes);
            w += 3;
        }

        let _ = sock.send_to(&frame_buf[..w], dest);
        frames_sent.fetch_add(1, Ordering::Relaxed);
        bytes_sent.fetch_add(w as u64, Ordering::Relaxed);
        last_frame_size.store(w as u16, Ordering::Relaxed);

        seq = seq.wrapping_add(1);
        sample_index += samples_per_frame as u64;
    }
}

#[inline]
fn tone_sample(phase_cycles: f64, amp_fraction: f64) -> u16 {
    let amp = (amp_fraction.clamp(0.0, 0.98) * 2047.0) as f64;
    let v = (amp * (2.0 * std::f64::consts::PI * phase_cycles).sin()).round() as i32;
    (v as i16 as u16) & 0x0fff
}

fn build_fake_discovery_response() -> [u8; protocol::RESPONSE_LEN] {
    let mut buf = [0u8; protocol::RESPONSE_LEN];
    buf[0] = 0xEF;
    buf[1] = 0xFE;
    buf[2] = 0x02;
    // Fake locally-administered MAC so it's obviously not a real HL2.
    buf[3..9].copy_from_slice(&[0x02, 0x00, 0x00, 0x52, 0x41, 0x57]); // "RAW" in the low bytes
    buf[0x09] = 99; // gateware major: 99 marks "this is rawcap --emulate, not real gateware"
    buf[0x15] = 0;
    buf[0x0a] = 6; // radio_id: HL2
    buf[0x13] = 1; // receivers
    buf
}
