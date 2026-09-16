// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Franz Schöning, https://www.schoning.com
//
//! `--aux-rate`: aux data channel test (docs/rawfront/PROTOCOL.md).
//!
//! A sender thread sends aux packets (UDP port 1027) carrying the aux byte pattern at a set
//! rate. A receiver thread takes the radio's aux packets on the same socket and checks both
//! parts of each: the echo of the PC's bytes (checked against the pattern, resynchronising
//! after gaps) and the radio-generated counter stream (checked against its offset). The radio
//! reports its own checker results for the PC -> radio direction in every aux packet header.
//! Works alone (`--aux-only`, no sample stream) or next to the RX stream and `--duplex`.

use crate::hl2::Hl2Control;
use crate::protocol::{self, RadioAuxHeader};
use crate::winsys;
use socket2::{Domain, SockAddr, Socket, Type};
use std::collections::VecDeque;
use std::net::{IpAddr, SocketAddr, UdpSocket};
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

#[derive(Clone, Debug)]
pub struct AuxOptions {
    pub local_ip: IpAddr,
    pub hl2_ip: IpAddr,
    /// PC -> radio payload rate in Mbit/s (0 = no PC data, address announcements only).
    pub pc_rate_mbit: f64,
    /// Radio counter stream rate in Mbit/s (0 = off).
    pub radio_rate_mbit: f64,
    /// Radio echoes the PC's bytes.
    pub echo: bool,
    /// PC payload bytes per aux packet.
    pub packet_size: usize,
}

impl AuxOptions {
    /// Register 0x32 counter stream rate in bytes per millisecond.
    pub fn counter_bytes_per_ms(&self) -> u32 {
        (self.radio_rate_mbit * 125.0).round().clamp(0.0, 65535.0) as u32
    }
}

// ---------------------------------------------------------------------------------------------
// Echo checker

/// Checks a byte stream that should be the aux pattern with gaps (bytes lost before they were
/// echoed) but no reordering. Keeps 8 bytes of lookahead so it can resynchronise anywhere.
#[derive(Default)]
pub struct EchoChecker {
    pos: Option<u32>,
    buf: VecDeque<u8>,
    pub bytes: u64,
    pub bad: u64,
    pub gaps: u64,
    pub gap_bytes: u64,
    pub backward: u64,
    pub unsynced: u64,
}

impl EchoChecker {
    /// Offset the next checked byte is expected to have, if in sync.
    pub fn next_offset(&self) -> Option<u32> {
        self.pos
    }

    /// Bytes were lost between the radio and the PC: forget the position so the next
    /// resynchronisation is not counted as a gap before the radio.
    pub fn desync(&mut self) {
        self.unsynced += self.buf.len() as u64;
        self.buf.clear();
        self.pos = None;
    }

    pub fn feed(&mut self, data: &[u8]) {
        self.bytes += data.len() as u64;
        self.buf.extend(data.iter().copied());
        self.process(false);
    }

    /// Check the last (< 8) bytes too.
    pub fn finish(&mut self) {
        self.process(true);
    }

    fn process(&mut self, flush: bool) {
        loop {
            // fast path while in sync
            if let Some(mut p) = self.pos {
                while let Some(&b) = self.buf.front() {
                    if b != protocol::aux_pattern_byte(p) {
                        break;
                    }
                    self.buf.pop_front();
                    p = p.wrapping_add(1);
                }
                self.pos = Some(p);
            }
            if self.buf.is_empty() || (self.buf.len() < 8 && !flush) {
                return;
            }
            let mut head = [0u8; 8];
            let n = self.buf.len().min(8);
            for (k, h) in head.iter_mut().take(n).enumerate() {
                *h = self.buf[k];
            }
            match protocol::aux_pattern_locate(&head[..n]) {
                Some(o) => {
                    if let Some(p) = self.pos {
                        let d = o.wrapping_sub(p);
                        if d < 1 << 31 {
                            self.gaps += 1;
                            self.gap_bytes += d as u64;
                        } else {
                            self.backward += 1;
                        }
                    }
                    self.pos = Some(o);
                }
                None => {
                    self.buf.pop_front();
                    match self.pos {
                        Some(p) => {
                            self.bad += 1;
                            self.pos = Some(p.wrapping_add(1));
                        }
                        None => self.unsynced += 1,
                    }
                }
            }
        }
    }
}

// ---------------------------------------------------------------------------------------------
// Shared counters

#[derive(Default)]
pub struct AuxStats {
    // PC sender
    pub sent_pkts: AtomicU64,
    pub sent_bytes: AtomicU64,
    pub send_errors: AtomicU64,
    pub slips: AtomicU64,
    // PC receiver
    pub rx_pkts: AtomicU64,
    pub rx_bytes: AtomicU64,
    pub lost_pkts: AtomicU64,
    pub reordered: AtomicU64,
    pub counter_bytes: AtomicU64,
    pub counter_bad: AtomicU64,
    pub counter_gaps: AtomicU64,
    pub counter_gap_bytes: AtomicU64,
    pub echo_bytes: AtomicU64,
    pub echo_bad: AtomicU64,
    pub echo_gaps: AtomicU64,
    pub echo_gap_bytes: AtomicU64,
    pub echo_link_lost_bytes: AtomicU64,
    pub echo_unsynced: AtomicU64,
    pub echo_backward: AtomicU64,
    pub lat_sum_us: AtomicU64,
    pub lat_cnt: AtomicU64,
    pub lat_max_us: AtomicU64,
    pub lat_max_all_us: AtomicU64,
    // radio reported (latest)
    pub have_radio: AtomicBool,
    pub r_pkts: AtomicU64,
    pub r_lost: AtomicU64,
    pub r_bad: AtomicU64,
    pub r_bytes: AtomicU64,
    pub r_ovf: AtomicU64,
    pub r_fill_max: AtomicU64,
    pub r_wait_max_us: AtomicU64,
    pub r_wait_max_all_us: AtomicU64,
    pub r_starved: AtomicU64,
}

fn load(a: &AtomicU64) -> u64 {
    a.load(Ordering::Relaxed)
}

// ---------------------------------------------------------------------------------------------
// Run

type SendLog = Arc<Mutex<VecDeque<(u32, Instant)>>>;

pub struct AuxRun {
    pub opts: AuxOptions,
    pub stats: Arc<AuxStats>,
    ctrl: Hl2Control,
    tx_running: Arc<AtomicBool>,
    rx_running: Arc<AtomicBool>,
    tx: Option<std::thread::JoinHandle<()>>,
    rx: Option<std::thread::JoinHandle<()>>,
    started: Instant,
    prev: (u64, u64, u64, u64, Instant),
}

/// Open the aux socket, announce it to the radio, turn register 0x32 on and start both threads.
pub fn start(opts: AuxOptions) -> std::io::Result<AuxRun> {
    let domain = match opts.local_ip {
        IpAddr::V4(_) => Domain::IPV4,
        IpAddr::V6(_) => Domain::IPV6,
    };
    let sock = Socket::new(domain, Type::DGRAM, None)?;
    let _ = sock.set_recv_buffer_size(32 * 1024 * 1024);
    let _ = sock.set_send_buffer_size(8 * 1024 * 1024);
    sock.bind(&SockAddr::from(SocketAddr::new(opts.local_ip, 0)))?;
    sock.connect(&SockAddr::from(SocketAddr::new(opts.hl2_ip, protocol::PORT_AUX)))?;
    let sock: UdpSocket = sock.into();
    sock.set_read_timeout(Some(Duration::from_millis(200)))?;

    // The radio sends aux packets to the address and port that last sent to port 1027.
    sock.send(&protocol::build_aux_pc_header(0, 0, 0, protocol::AUX_FLAG_HELLO))?;
    std::thread::sleep(Duration::from_millis(20));
    let ctrl = Hl2Control::new(opts.hl2_ip);
    let reg = protocol::reg_aux_value(true, opts.echo, opts.radio_rate_mbit > 0.0, opts.counter_bytes_per_ms());
    ctrl.set_aux(reg)?;
    println!(
        "rawcap: aux on (register 0x32 = 0x{reg:08x}): PC -> radio {:.1} Mbit/s in {}-byte packets, echo {}, radio counter stream {:.1} Mbit/s ({} bytes/ms), port {}",
        opts.pc_rate_mbit,
        opts.packet_size,
        if opts.echo { "on" } else { "off" },
        opts.radio_rate_mbit,
        opts.counter_bytes_per_ms(),
        protocol::PORT_AUX
    );

    let stats = Arc::new(AuxStats::default());
    let log: SendLog = Arc::new(Mutex::new(VecDeque::new()));
    let tx_running = Arc::new(AtomicBool::new(true));
    let rx_running = Arc::new(AtomicBool::new(true));

    let rx = {
        let sock = sock.try_clone()?;
        let stats = stats.clone();
        let log = log.clone();
        let running = rx_running.clone();
        std::thread::Builder::new().name("rawcap-aux-rx".into()).spawn(move || receiver_loop(sock, &stats, &log, &running))?
    };
    let tx = {
        let stats = stats.clone();
        let running = tx_running.clone();
        let o = opts.clone();
        std::thread::Builder::new().name("rawcap-aux-tx".into()).spawn(move || sender_loop(sock, o, &stats, &log, &running))?
    };
    let now = Instant::now();
    Ok(AuxRun {
        opts,
        stats,
        ctrl,
        tx_running,
        rx_running,
        tx: Some(tx),
        rx: Some(rx),
        started: now,
        prev: (0, 0, 0, 0, now),
    })
}

fn sender_loop(sock: UdpSocket, opts: AuxOptions, stats: &AuxStats, log: &SendLog, running: &AtomicBool) {
    winsys::raise_current_thread_priority();
    let size = opts.packet_size.clamp(1, 8900);
    let mut buf = vec![0u8; protocol::AUX_PC_HEADER_LEN + size];
    let t0 = Instant::now();
    let mut last_hello = t0;
    if opts.pc_rate_mbit <= 0.0 {
        while running.load(Ordering::Relaxed) {
            std::thread::sleep(Duration::from_millis(50));
            if last_hello.elapsed() >= Duration::from_millis(500) {
                let _ = sock.send(&protocol::build_aux_pc_header(0, 0, 0, protocol::AUX_FLAG_HELLO));
                last_hello = Instant::now();
            }
        }
        return;
    }
    let interval = size as f64 * 8.0 / (opts.pc_rate_mbit * 1e6);
    let mut next_s = 0.0f64;
    let mut seq: u32 = 0;
    let mut off: u32 = 0;
    while running.load(Ordering::Relaxed) {
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
        if now_s - next_s > 0.020 {
            stats.slips.fetch_add(1, Ordering::Relaxed);
            next_s = now_s;
        }
        buf[..protocol::AUX_PC_HEADER_LEN].copy_from_slice(&protocol::build_aux_pc_header(seq, off, size as u16, 0));
        protocol::fill_aux_pattern(&mut buf[protocol::AUX_PC_HEADER_LEN..], off);
        let t = Instant::now();
        match sock.send(&buf) {
            Ok(_) => {
                stats.sent_pkts.fetch_add(1, Ordering::Relaxed);
                stats.sent_bytes.fetch_add(size as u64, Ordering::Relaxed);
            }
            Err(_) => {
                stats.send_errors.fetch_add(1, Ordering::Relaxed);
            }
        }
        if let Ok(mut l) = log.lock() {
            l.push_back((off, t));
            while l.len() > 50_000 || l.front().is_some_and(|(_, ts)| t.duration_since(*ts) > Duration::from_secs(5)) {
                l.pop_front();
            }
        }
        seq = seq.wrapping_add(1);
        off = off.wrapping_add(size as u32);
        next_s += interval;
    }
}

fn receiver_loop(sock: UdpSocket, stats: &AuxStats, log: &SendLog, running: &AtomicBool) {
    winsys::raise_current_thread_priority();
    let mut buf = vec![0u8; 65536];
    let mut chk = EchoChecker::default();
    let mut last_seq: Option<u32> = None;
    let mut exp_echo: Option<u32> = None;
    let mut exp_counter: Option<u32> = None;
    let store = |chk: &EchoChecker| {
        stats.echo_bytes.store(chk.bytes, Ordering::Relaxed);
        stats.echo_bad.store(chk.bad, Ordering::Relaxed);
        stats.echo_gaps.store(chk.gaps, Ordering::Relaxed);
        stats.echo_gap_bytes.store(chk.gap_bytes, Ordering::Relaxed);
        stats.echo_unsynced.store(chk.unsynced, Ordering::Relaxed);
        stats.echo_backward.store(chk.backward, Ordering::Relaxed);
    };
    while running.load(Ordering::Relaxed) {
        let n = match sock.recv(&mut buf) {
            Ok(n) => n,
            Err(e) if e.kind() == std::io::ErrorKind::WouldBlock || e.kind() == std::io::ErrorKind::TimedOut => continue,
            // ICMP port unreachable etc. on a connected UDP socket: keep going
            Err(_) => continue,
        };
        let now = Instant::now();
        let data = &buf[..n];
        let Some(h) = RadioAuxHeader::parse(data) else { continue };
        stats.rx_pkts.fetch_add(1, Ordering::Relaxed);
        stats.rx_bytes.fetch_add(n as u64, Ordering::Relaxed);

        if let Some(p) = last_seq {
            let d = h.seq.wrapping_sub(p.wrapping_add(1));
            if h.seq == 0 {
                // radio restarted aux: new offsets
                exp_echo = None;
                exp_counter = None;
                chk.desync();
            } else if d != 0 {
                if d < 1 << 31 {
                    stats.lost_pkts.fetch_add(d as u64, Ordering::Relaxed);
                } else {
                    stats.reordered.fetch_add(1, Ordering::Relaxed);
                }
            }
        }
        last_seq = Some(h.seq);

        // radio-reported PC -> radio checker
        stats.have_radio.store(true, Ordering::Relaxed);
        stats.r_pkts.store(h.rx_packets as u64, Ordering::Relaxed);
        stats.r_lost.store(h.rx_lost as u64, Ordering::Relaxed);
        stats.r_bad.store(h.rx_bad as u64, Ordering::Relaxed);
        stats.r_bytes.store(h.rx_bytes as u64, Ordering::Relaxed);
        stats.r_ovf.store(h.rx_overflows as u64, Ordering::Relaxed);
        stats.r_fill_max.fetch_max(h.fifo_fill as u64, Ordering::Relaxed);
        stats.r_wait_max_us.fetch_max(h.wait_us as u64, Ordering::Relaxed);
        stats.r_wait_max_all_us.fetch_max(h.wait_us as u64, Ordering::Relaxed);
        stats.r_starved.store(h.starved as u64, Ordering::Relaxed);

        let e0 = protocol::AUX_RADIO_HEADER_LEN;
        let e1 = e0 + h.echo_len as usize;
        let c1 = e1 + h.counter_len as usize;

        // ---- echo ----
        // Every packet carries the echo offset, also with no echo bytes: a lost packet with echo
        // bytes shows here even when the next one has none.
        if let Some(x) = exp_echo {
            if h.echo_offset != x {
                let d = h.echo_offset.wrapping_sub(x);
                if d < 1 << 31 {
                    stats.echo_link_lost_bytes.fetch_add(d as u64, Ordering::Relaxed);
                }
                chk.desync();
            }
        }
        if h.echo_len > 0 {
            chk.feed(&data[e0..e1]);
            store(&chk);
            // latency: when was the packet holding the newest checked byte sent?
            if let Some(p) = chk.next_offset() {
                let last = p.wrapping_sub(1);
                if let Ok(l) = log.lock() {
                    let i = l.partition_point(|(o, _)| *o <= last);
                    if i > 0 {
                        let (o, t) = l[i - 1];
                        if last.wrapping_sub(o) < 65536 {
                            let us = now.duration_since(t).as_micros() as u64;
                            stats.lat_sum_us.fetch_add(us, Ordering::Relaxed);
                            stats.lat_cnt.fetch_add(1, Ordering::Relaxed);
                            stats.lat_max_us.fetch_max(us, Ordering::Relaxed);
                            stats.lat_max_all_us.fetch_max(us, Ordering::Relaxed);
                        }
                    }
                }
            }
        }
        exp_echo = Some(h.echo_offset.wrapping_add(h.echo_len as u32));

        // ---- counter stream ----
        if h.counter_len > 0 {
            if let Some(x) = exp_counter {
                if h.counter_offset != x {
                    stats.counter_gaps.fetch_add(1, Ordering::Relaxed);
                    let d = h.counter_offset.wrapping_sub(x);
                    if d < 1 << 31 {
                        stats.counter_gap_bytes.fetch_add(d as u64, Ordering::Relaxed);
                    }
                }
            }
            let bad = data[e1..c1]
                .iter()
                .enumerate()
                .filter(|(k, &b)| b != protocol::aux_pattern_byte(h.counter_offset.wrapping_add(*k as u32)))
                .count();
            stats.counter_bad.fetch_add(bad as u64, Ordering::Relaxed);
            stats.counter_bytes.fetch_add(h.counter_len as u64, Ordering::Relaxed);
            exp_counter = Some(h.counter_offset.wrapping_add(h.counter_len as u32));
        }
    }
    chk.finish();
    store(&chk);
}

impl AuxRun {
    /// One status line; call about once a second.
    pub fn print_line(&mut self) {
        let s = &self.stats;
        let now = Instant::now();
        let dt = now.duration_since(self.prev.4).as_secs_f64().max(1e-3);
        let (sent, ctr, echo, rxb) = (load(&s.sent_bytes), load(&s.counter_bytes), load(&s.echo_bytes), load(&s.rx_bytes));
        let mbit = |b: u64, p: u64| (b.saturating_sub(p)) as f64 * 8.0 / dt / 1e6;
        let lat_cnt = s.lat_cnt.swap(0, Ordering::Relaxed);
        let lat_sum = s.lat_sum_us.swap(0, Ordering::Relaxed);
        println!(
            "  AUX: PC sent {:>5.1} Mbit/s | radio got pkts={} lost={} bad={} ovf={} fifo_max={} wait_max={}us starved={} | PC got {:>5.1} Mbit/s lost_pkts={} | counter {:>5.1} Mbit/s bad={} gap_bytes={} | echo {:>5.1} Mbit/s bad={} gaps={} ({} bytes) link_lost={} lat mean {:.2} max {:.2} ms",
            mbit(sent, self.prev.0),
            load(&s.r_pkts),
            load(&s.r_lost),
            load(&s.r_bad),
            load(&s.r_ovf),
            s.r_fill_max.swap(0, Ordering::Relaxed),
            s.r_wait_max_us.swap(0, Ordering::Relaxed),
            load(&s.r_starved),
            mbit(rxb, self.prev.3),
            load(&s.lost_pkts),
            mbit(ctr, self.prev.1),
            load(&s.counter_bad),
            load(&s.counter_gap_bytes),
            mbit(echo, self.prev.2),
            load(&s.echo_bad),
            load(&s.echo_gaps),
            load(&s.echo_gap_bytes),
            load(&s.echo_link_lost_bytes),
            if lat_cnt > 0 { lat_sum as f64 / lat_cnt as f64 / 1000.0 } else { 0.0 },
            s.lat_max_us.swap(0, Ordering::Relaxed) as f64 / 1000.0,
        );
        self.prev = (sent, ctr, echo, rxb, now);
    }

    /// Stop sending, let the echo drain, turn register 0x32 off, stop receiving.
    pub fn stop(mut self) -> AuxResult {
        let send_secs = self.started.elapsed().as_secs_f64();
        self.tx_running.store(false, Ordering::Relaxed);
        if let Some(t) = self.tx.take() {
            let _ = t.join();
        }
        // Echo FIFO holds at most 4,096 bytes; the radio sends it within a few ms even between
        // raw frames. Wait until the echo count stops rising.
        let mut last = u64::MAX;
        // The radio reports its receive counters in its own aux packets, so also wait for a few
        // of those after the last PC packet.
        for i in 0..20 {
            std::thread::sleep(Duration::from_millis(100));
            let e = load(&self.stats.echo_bytes) + load(&self.stats.echo_unsynced);
            if e == last && i >= 3 {
                break;
            }
            last = e;
        }
        if let Err(e) = self.ctrl.clear_aux() {
            println!("rawcap: warning: could not clear aux register 0x32 ({e})");
        }
        std::thread::sleep(Duration::from_millis(200));
        self.rx_running.store(false, Ordering::Relaxed);
        if let Some(t) = self.rx.take() {
            let _ = t.join();
        }
        AuxResult { opts: self.opts.clone(), stats: self.stats.clone(), send_secs }
    }
}

pub struct AuxResult {
    pub opts: AuxOptions,
    pub stats: Arc<AuxStats>,
    pub send_secs: f64,
}

/// Print the aux summary. Returns true if every tested direction passed.
pub fn print_summary(r: &AuxResult) -> bool {
    let s = &r.stats;
    let o = &r.opts;
    let secs = r.send_secs.max(1e-3);
    let sent = load(&s.sent_bytes);
    println!("---- AUX summary ----");
    println!(
        "PC -> radio:  sent {} packets, {} payload bytes ({:.2} Mbit/s over {:.1} s), send errors {}, pacing slips {}",
        load(&s.sent_pkts),
        sent,
        sent as f64 * 8.0 / secs / 1e6,
        secs,
        load(&s.send_errors),
        load(&s.slips)
    );
    println!(
        "  radio counted: packets={} bytes={} lost packets={} bad bytes={} echo FIFO overflows={}",
        load(&s.r_pkts),
        load(&s.r_bytes),
        load(&s.r_lost),
        load(&s.r_bad),
        load(&s.r_ovf)
    );
    let ctr = load(&s.counter_bytes);
    println!(
        "radio -> PC:  aux packets received={} lost (sequence gaps)={} reordered={} | radio send wait max {} us, starved packets {}",
        load(&s.rx_pkts),
        load(&s.lost_pkts),
        load(&s.reordered),
        load(&s.r_wait_max_all_us),
        load(&s.r_starved)
    );
    println!(
        "  counter stream: asked {:.2} Mbit/s, got {} bytes ({:.2} Mbit/s), bad bytes={} gaps={} ({} bytes)",
        o.radio_rate_mbit,
        ctr,
        ctr as f64 * 8.0 / secs / 1e6,
        load(&s.counter_bad),
        load(&s.counter_gaps),
        load(&s.counter_gap_bytes)
    );
    let echo = load(&s.echo_bytes);
    let lat_max = load(&s.lat_max_all_us);
    println!(
        "  echo: {} bytes back of {} sent, bad={} gaps before echo={} ({} bytes) lost radio->PC={} bytes, unsynced={} backward={} | latency max {:.2} ms",
        echo,
        sent,
        load(&s.echo_bad),
        load(&s.echo_gaps),
        load(&s.echo_gap_bytes),
        load(&s.echo_link_lost_bytes),
        load(&s.echo_unsynced),
        load(&s.echo_backward),
        lat_max as f64 / 1000.0
    );

    let have = s.have_radio.load(Ordering::Relaxed);
    let mut all = have;
    if !have {
        println!("AUX: no aux packets from the radio (is hl2b5up_raw running?)");
    }
    if o.pc_rate_mbit > 0.0 {
        let pass = have
            && load(&s.r_lost) == 0
            && load(&s.r_bad) == 0
            && load(&s.r_ovf) == 0
            && load(&s.send_errors) == 0
            && load(&s.r_bytes) == sent & 0xffff_ffff
            && sent > 0;
        println!(
            "AUX PC -> radio PASS/FAIL (radio got every byte: zero lost packets, bad bytes, overflows): {}",
            if pass { "PASS" } else { "FAIL" }
        );
        all &= pass;
        if o.echo {
            let pass = have
                && load(&s.echo_bad) == 0
                && load(&s.echo_gaps) == 0
                && load(&s.echo_link_lost_bytes) == 0
                && load(&s.echo_backward) == 0
                && echo == sent;
            println!(
                "AUX echo round trip PASS/FAIL (every byte back, in order, unchanged): {}",
                if pass { "PASS" } else { "FAIL" }
            );
            all &= pass;
        }
    }
    if o.radio_rate_mbit > 0.0 || (o.pc_rate_mbit > 0.0 && o.echo) {
        let pass = have
            && load(&s.lost_pkts) == 0
            && load(&s.reordered) == 0
            && load(&s.counter_bad) == 0
            && load(&s.counter_gap_bytes) == 0
            && (o.radio_rate_mbit <= 0.0 || ctr > 0);
        println!(
            "AUX radio -> PC PASS/FAIL (zero lost aux packets, counter stream complete and unchanged): {}",
            if pass { "PASS" } else { "FAIL" }
        );
        all &= pass;
    }
    println!(
        "(Aux packets lost in the PC network card count as lost here; compare with the card's ReceivedDiscardedPackets.)"
    );
    all
}

/// `--aux-only`: aux channel with no sample stream, for `seconds` (or until Ctrl-C).
pub fn run_standalone(opts: AuxOptions, seconds: Option<f64>) -> std::io::Result<bool> {
    let mut run = start(opts)?;
    let t0 = Instant::now();
    let mut last = Instant::now();
    loop {
        std::thread::sleep(Duration::from_millis(20));
        if last.elapsed() >= Duration::from_secs(1) {
            run.print_line();
            last = Instant::now();
        }
        if winsys::ctrlc_pressed() {
            println!("rawcap: stopping (Ctrl-C)");
            break;
        }
        if seconds.is_some_and(|s| t0.elapsed().as_secs_f64() >= s) {
            break;
        }
    }
    let r = run.stop();
    Ok(print_summary(&r))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn pattern(off: u32, len: usize) -> Vec<u8> {
        let mut v = vec![0u8; len];
        protocol::fill_aux_pattern(&mut v, off);
        v
    }

    #[test]
    fn echo_clean_stream_in_odd_chunks() {
        let mut c = EchoChecker::default();
        let data = pattern(1000, 10_000);
        for chunk in data.chunks(333) {
            c.feed(chunk);
        }
        c.finish();
        assert_eq!((c.bad, c.gaps, c.unsynced, c.backward), (0, 0, 0, 0));
        assert_eq!(c.bytes, 10_000);
        assert_eq!(c.next_offset(), Some(11_000));
    }

    #[test]
    fn echo_gap_and_bad_byte() {
        let mut c = EchoChecker::default();
        c.feed(&pattern(0, 1024));
        c.feed(&pattern(2048, 1021)); // one PC packet of 1,024 bytes lost before the echo
        let mut p = pattern(3069, 1024);
        p[500] ^= 0x40;
        c.feed(&p);
        c.feed(&pattern(4093, 5)); // a section shorter than the 8-byte lookahead
        c.feed(&pattern(5000, 100));
        c.finish();
        assert_eq!(c.bad, 1);
        assert_eq!(c.gaps, 2);
        assert_eq!(c.gap_bytes, 1024 + (5000 - 4098));
        assert_eq!(c.unsynced, 0);
    }

    #[test]
    fn echo_desync_after_link_loss_is_not_a_gap() {
        let mut c = EchoChecker::default();
        c.feed(&pattern(0, 800));
        c.desync();
        c.feed(&pattern(1600, 800));
        c.finish();
        assert_eq!((c.bad, c.gaps), (0, 0));
    }

    #[test]
    fn echo_garbage_counts_bad() {
        let mut c = EchoChecker::default();
        c.feed(&pattern(0, 64));
        c.feed(&[0xffu8; 16]);
        c.feed(&pattern(80, 64));
        c.finish();
        assert_eq!(c.bad, 16);
        assert_eq!(c.gaps, 0);
    }

    #[test]
    fn counter_rate_register() {
        let o = AuxOptions {
            local_ip: "0.0.0.0".parse().unwrap(),
            hl2_ip: "0.0.0.0".parse().unwrap(),
            pc_rate_mbit: 10.0,
            radio_rate_mbit: 50.0,
            echo: true,
            packet_size: 1024,
        };
        assert_eq!(o.counter_bytes_per_ms(), 6250);
    }
}
