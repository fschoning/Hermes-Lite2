// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Franz Schöning, https://www.schoning.com
//
// This module is the complete wire-format API on purpose (see module doc below); a few
// items (is_test_pattern/is_quiet_capture/is_first_frame, packed_len,
// ip_mtu_for_nic_jumbo_setting) aren't called by rawcap's own CLI yet but are exercised by
// tests or documented for nic_setup.ps1/README.md callers to use directly.
#![allow(dead_code)]

//! =====================================================================================
//! WIRE FORMAT — Hermes-Lite 2 raw ADC Ethernet stream
//!
//! This is the ONLY place wire-format details are allowed to live in this program.
//!
//! The wire format is specified in docs/rawfront/PROTOCOL.md and implemented in
//! gateware/rtl/rawstream.v, txsink.v and auxchan.v. If they change, EDIT ONLY THIS FILE to
//! match: nothing outside this module should need to change.
//!
//! Facts this module relies on (checked against docs/rawfront/PROTOCOL.md and the RTL):
//!   A1. Frame header fields are big-endian on the wire.
//!   A2. The mode/frame-size register is address 0x30 on command port 1025, written with a
//!       60-byte command packet: `EF FE 05 7F <addr<<1> <4-byte-BE value> <51 zero bytes>`
//!       (docs/rawfront/PROTOCOL.md "Register write"), same format `hermeslite.py:command()` uses.
//!   A3. Start/stop packets are 64 bytes: `EF FE 04 <flags>` + 60 zero bytes, sent to port 1024
//!       from the socket that will receive the stream (docs/rawfront/PROTOCOL.md "Start and stop"). Flags
//!       byte bit 0 = run, bit 7 = watchdog off.
//!   A4. Samples/frame sits in register bits 31:16, rounded down to even by the gateware itself.
//!       A register value of 0 is defined to mean 968 (not "zero samples"); values above 7,680
//!       are clamped to 7,680 by the gateware. rawcap clamps and warns on its own side too (see
//!       `clamp_samples_per_frame`) so the reported "expected frames/s" stays honest.
//!   A5. Discovery and register-write response packets are 60 bytes and start with `EF FE`,
//!       matching `software/hermeslite/hermeslite.py` `decode()` (unmodified by the raw-stream
//!       gateware — docs/rawfront/PROTOCOL.md doesn't touch discovery).
//!   A6. Sample packing is big-endian, 2 samples -> 3 bytes: `a[11:4]`, `{a[3:0],b[11:8]}`,
//!       `b[7:0]`. Samples are sign-extended 12-bit two's complement ADC values; the wire itself
//!       carries raw 12-bit fields, sign extension happens only when unpacking here.
//!   A7. Test pattern: sample k of a frame whose header says first-sample-index I equals
//!       `(I + k) mod 4096` (docs/rawfront/PROTOCOL.md "Test pattern") — checked directly against the
//!       header's own index field, not reconstructed by carrying state across frames.
//! =====================================================================================

/// Bytes of frame header before the packed samples start (version 1 frames).
pub const HEADER_LEN: usize = 20;
/// Header length of version 2 frames: the duplex image (`hl2b5up_duplex`, docs/rawfront/PROTOCOL.md) sends these
/// while duplex mode (register 0x31 bit 0) is on. Bytes 0-19 are the version 1 header, bytes
/// 20-39 the radio's TX sink status (`TxStatus`).
pub const HEADER_LEN_V2: usize = 40;
/// Header length of version 3 frames: the raw front-end image (`hl2b5up_raw`, docs/rawfront/PROTOCOL.md) sends these
/// while duplex is on. Bytes 0-39 as version 2, bytes 40-45 the echo offset (TX sample index minus RX
/// sample index of the echoed samples, 48-bit two's complement), byte 46 flags (`ECHO_F_*`), byte 47
/// the transmit interlock's latched trip reasons.
pub const HEADER_LEN_V3: usize = 48;

pub const FRAME_MAGIC: u8 = 0xA5;
pub const FRAME_VERSION: u8 = 0x01;
pub const FRAME_VERSION_DUPLEX: u8 = 0x02;
pub const FRAME_VERSION_RAWFRONT: u8 = 0x03;

// ---- Header flags byte (offset 2) --------------------------------------------------------
pub const FLAG_TEST_PATTERN: u8 = 1 << 0;
/// A FIFO overflow happened since start. Sticky: stays set for the rest of the run.
pub const FLAG_OVERFLOW: u8 = 1 << 1;
/// docs/rawfront/PROTOCOL.md: "A sample in the **previous** frame was at full scale (0x7FF or 0x800)" — this
/// bit describes the frame BEFORE the one carrying it, not the current frame. In test-pattern
/// mode this is set regularly and is expected (the pattern counter passes through 0x7FF/0x800
/// every 4096 samples) — it is not a fault indicator there, only meaningful in ADC/tone mode.
pub const FLAG_ADC_CLIP_PREV_FRAME: u8 = 1 << 2;
pub const FLAG_QUIET_CAPTURE: u8 = 1 << 3;
pub const FLAG_FIRST_FRAME: u8 = 1 << 4;
/// docs/rawfront/PROTOCOL.md flags table, bit 5: "Samples are missing between the previous frame and this
/// one (after an overflow, or between quiet-capture blocks)". Set on exactly the one frame that
/// follows a FIFO-overflow or quiet-capture resync; cleared again on the next frame. Distinct
/// from FLAG_OVERFLOW, which stays set for the whole run once tripped.
pub const FLAG_GAP: u8 = 1 << 5;

// ---- Transmit-safety status byte (offset 3) ----------------------------------------------
// Images before hl2b5up_front sent 0 here. A slow level from the radio's logic, copied into
// every frame header (docs/rawfront/PROTOCOL.md, "Transmit-safety status").
/// Transmit off: forced off in logic (raw images without a transmitter), or the interlock's outputs off
/// (hl2b5up_raw).
pub const SAFETY_TX_FORCED_OFF: u8 = 1 << 0;
/// A PA, T/R relay or bias output is driven.
pub const SAFETY_PA_KEYED: u8 = 1 << 1;
/// The PC's openHPSDR MOX/PTT bit is set (hl2b5up_raw: transmit requested, lease valid and keyed).
pub const SAFETY_HOST_MOX: u8 = 1 << 2;
/// PTT input (key jack ring) closed.
pub const SAFETY_PTT_IN: u8 = 1 << 3;
/// Key input (key jack tip) closed.
pub const SAFETY_KEY_IN: u8 = 1 << 4;
/// TX inhibit input (CN8) active.
pub const SAFETY_TX_INHIBIT: u8 = 1 << 5;
/// Over-temperature: the radio disabled transmit.
pub const SAFETY_OVER_TEMP: u8 = 1 << 6;
/// hl2b5up_raw: a transmit interlock trip is latched (reasons in version 3 header byte 47 and the
/// register block).
pub const SAFETY_TRIP: u8 = 1 << 7;

/// Short text for a transmit-safety status byte, e.g. "0x01 tx-forced-off".
pub fn safety_text(b: u8) -> String {
    let names = [
        (SAFETY_TX_FORCED_OFF, "tx-off"),
        (SAFETY_PA_KEYED, "PA-KEYED"),
        (SAFETY_HOST_MOX, "tx-request"),
        (SAFETY_PTT_IN, "ptt-in"),
        (SAFETY_KEY_IN, "key-in"),
        (SAFETY_TX_INHIBIT, "tx-inhibit"),
        (SAFETY_OVER_TEMP, "OVER-TEMP"),
        (SAFETY_TRIP, "TRIP"),
    ];
    let mut s = format!("0x{:02X}", b);
    for (bit, name) in names {
        if b & bit != 0 {
            s.push(' ');
            s.push_str(name);
        }
    }
    s
}

// ---- UDP ports --------------------------------------------------------------------------
/// openHPSDR start/stop command port (`EF FE 04 xx`).
pub const PORT_START_STOP: u16 = 1024;
/// Discovery + general register-write command port.
pub const PORT_CMD: u16 = 1025;
/// PC -> HL2 TX sample frames (duplex image only, docs/rawfront/PROTOCOL.md).
pub const PORT_TX: u16 = 1026;

// ---- openHPSDR start/stop (docs/rawfront/PROTOCOL.md "Start and stop") --------------------------------
/// Full packet length: `EF FE 04 <flags>` + 60 zero bytes.
pub const START_STOP_LEN: usize = 64;

const START_STOP_FLAG_RUN: u8 = 1 << 0;
const START_STOP_FLAG_WATCHDOG_OFF: u8 = 1 << 7;

fn build_start_stop_packet(flags: u8) -> [u8; START_STOP_LEN] {
    let mut buf = [0u8; START_STOP_LEN];
    buf[0] = 0xEF;
    buf[1] = 0xFE;
    buf[2] = 0x04;
    buf[3] = flags;
    buf
}

/// Run + watchdog-off. Watchdog must be off because rawcap does not keep sending C&C frames
/// while the stream runs.
pub fn cmd_start() -> [u8; START_STOP_LEN] {
    build_start_stop_packet(START_STOP_FLAG_RUN | START_STOP_FLAG_WATCHDOG_OFF)
}

pub fn cmd_stop() -> [u8; START_STOP_LEN] {
    build_start_stop_packet(0)
}

// ---- Discovery (matches software/hermeslite/hermeslite.py discover_by_port) -------------
pub const DISCOVERY_REQUEST_LEN: usize = 60;
pub const RESPONSE_LEN: usize = 60;

pub fn build_discovery_request() -> [u8; DISCOVERY_REQUEST_LEN] {
    let mut buf = [0u8; DISCOVERY_REQUEST_LEN];
    buf[0] = 0xEF;
    buf[1] = 0xFE;
    buf[2] = 0x02;
    buf
}

/// Decoded discovery/response packet. Only the fields rawcap actually uses are kept; see
/// `hermeslite.py:decode()` for the full field list if more are ever needed.
#[derive(Debug, Clone)]
pub struct DiscoveryResponse {
    pub mac: [u8; 6],
    pub gateware_major: u8,
    pub gateware_minor: u8,
    pub board_id: u8,
    pub receivers: u8,
}

pub fn parse_discovery_response(buf: &[u8]) -> Option<DiscoveryResponse> {
    if buf.len() < RESPONSE_LEN {
        return None;
    }
    if buf[0] != 0xEF || buf[1] != 0xFE {
        return None;
    }
    let mut mac = [0u8; 6];
    mac.copy_from_slice(&buf[3..9]);
    Some(DiscoveryResponse {
        mac,
        gateware_major: buf[0x09],
        gateware_minor: buf[0x15],
        board_id: buf[0x14] & 0x3f,
        receivers: buf[0x13],
    })
}

// ---- Register write (mode / frame size), address 0x30 on PORT_CMD -----------------------
pub const REG_ADDR_RAWMODE: u8 = 0x30;

pub const REG_RAW_ENABLE: u32 = 1 << 0;
pub const REG_RAW_TEST_PATTERN: u32 = 1 << 1;
pub const REG_RAW_QUIET_CAPTURE: u32 = 1 << 2;

/// docs/rawfront/PROTOCOL.md: "0 means 968" — a literal 0 in the register's samples-per-frame field is
/// defined by the gateware to mean the default, not "zero samples".
pub const DEFAULT_SAMPLES_PER_FRAME: u16 = 968;
/// docs/rawfront/PROTOCOL.md: "Values above 7,680 are cut to 7,680" — the FIFO-depth-derived hardware
/// ceiling, regardless of what the PC asks for.
pub const MAX_SAMPLES_PER_FRAME: u16 = 7_680;
/// The largest samples-per-frame a standard Windows "9014" jumbo-frame NIC setting can carry
/// (IP MTU 9000, docs/rawfront/PROTOCOL.md's own frame-size table). Asking for more needs a NIC configured
/// for a bigger jumbo frame than the common 9014 default.
pub const MAX_SAMPLES_PER_FRAME_STANDARD_JUMBO: u16 = 5_968;

/// Clamp a requested samples-per-frame to what the gateware will actually use, per
/// docs/rawfront/PROTOCOL.md: round down to even, treat 0 as `DEFAULT_SAMPLES_PER_FRAME`, and cut anything
/// over `MAX_SAMPLES_PER_FRAME`. Returns `(value_the_gateware_will_use, was_clamped)`.
pub fn clamp_samples_per_frame(requested: u16) -> (u16, bool) {
    let even = requested & !1;
    if even == 0 {
        return (DEFAULT_SAMPLES_PER_FRAME, requested != DEFAULT_SAMPLES_PER_FRAME);
    }
    if even > MAX_SAMPLES_PER_FRAME {
        return (MAX_SAMPLES_PER_FRAME, true);
    }
    (even, even != requested)
}

/// Build the 32-bit value for the raw-mode register: enable/test-pattern/quiet-capture bits
/// plus samples-per-frame in bits 31:16. Does NOT clamp — call `clamp_samples_per_frame` first
/// so the caller knows if/why the value changed and can warn the user.
pub fn reg_raw_value(enable: bool, test_pattern: bool, quiet_capture: bool, samples_per_frame: u16) -> u32 {
    debug_assert!(samples_per_frame % 2 == 0, "samples per frame must be even");
    let mut v: u32 = 0;
    if enable {
        v |= REG_RAW_ENABLE;
    }
    if test_pattern {
        v |= REG_RAW_TEST_PATTERN;
    }
    if quiet_capture {
        v |= REG_RAW_QUIET_CAPTURE;
    }
    v |= (samples_per_frame as u32) << 16;
    v
}

// ---- Duplex register, address 0x31 (docs/rawfront/PROTOCOL.md) --------------------------------------------
pub const REG_ADDR_DUPLEX: u8 = 0x31;
/// Bit 0: TX sink on. Only active while raw streaming is running.
pub const REG_DUPLEX_ENABLE: u32 = 1 << 0;
/// hl2b5up_raw: bit 1 real DAC (TX samples to the AD9866 while the interlock allows transmit).
pub const REG_DUPLEX_REAL: u32 = 1 << 1;
/// hl2b5up_raw: bit 2 echo (the played TX samples replace the ADC samples in the RX stream; the DAC is
/// never driven).
pub const REG_DUPLEX_ECHO: u32 = 1 << 2;

/// The register value that turns raw mode fully off (docs/rawfront/PROTOCOL.md: "Raw mode off (normal HL2)
/// | 0x00000000"). Used on exit/stop so Quisk or other software isn't left receiving raw frames
/// instead of normal IQ data.
pub fn reg_raw_off() -> u32 {
    0
}

/// Build the 60-byte register-write command packet, matching `hermeslite.py:command()`:
/// `EF FE 05 7F <addr<<1> <4-byte-BE value> <51 zero bytes>`.
pub fn build_command_packet(addr: u8, value: u32) -> [u8; RESPONSE_LEN] {
    let mut buf = [0u8; RESPONSE_LEN];
    buf[0] = 0xEF;
    buf[1] = 0xFE;
    buf[2] = 0x05;
    buf[3] = 0x7F;
    buf[4] = addr << 1;
    buf[5..9].copy_from_slice(&value.to_be_bytes());
    buf
}

// ---- Stream frame header (plan §2.4) -----------------------------------------------------
#[derive(Debug, Clone, Copy, Default)]
pub struct FrameHeader {
    pub flags: u8,
    /// Transmit-safety status byte (header byte 3, SAFETY_* bits; 0 in older images).
    pub safety: u8,
    pub seq: u32,
    pub first_sample_index: u64, // 48-bit value, stored widened
    pub samples_in_frame: u16,
    /// FIFO overflow events since start. Saturates (stops counting) at 65,535.
    pub overflow_count: u16,
    /// Highest FIFO fill since start, in samples. docs/rawfront/PROTOCOL.md: range is 0-16,384 inclusive
    /// (the FIFO is 16,384 samples deep in `hl2b5up_rawlite`, and a full FIFO is a valid,
    /// observable reading) — not 0-16,383. (8,192 deep in `hl2b5up_duplex`.)
    pub fifo_high_water: u16,
    /// 20 for version 1 frames, 40 for version 2 (duplex) frames.
    pub header_len: usize,
    /// Radio TX sink status, in version 2 and 3 frames.
    pub tx: Option<TxStatus>,
    /// Echo offset, flags and interlock trips, only in version 3 frames.
    pub echo: Option<EchoInfo>,
}

/// Bytes 40-47 of a version 3 frame (hl2b5up_raw, docs/rawfront/PROTOCOL.md).
#[derive(Debug, Clone, Copy, Default, PartialEq)]
pub struct EchoInfo {
    /// TX sample index minus RX sample index of the echoed samples (valid with ECHO_F_VALID).
    pub offset: i64,
    pub flags: u8,
    /// Latched transmit interlock trip reasons (bit 0 lease, 1 over-temperature, 2 TX inhibit,
    /// 3 CPU watchdog, 4 max key-down, 5 stale temperature reading).
    pub trips: u8,
}

pub const ECHO_F_VALID: u8 = 1 << 0;
pub const ECHO_F_ECHO: u8 = 1 << 1;
pub const ECHO_F_REAL: u8 = 1 << 2;
pub const ECHO_F_DAC_DRIVEN: u8 = 1 << 3;
pub const ECHO_F_TRIP: u8 = 1 << 4;
pub const ECHO_F_LEASE: u8 = 1 << 5;
pub const ECHO_F_TX_ON: u8 = 1 << 6;

impl EchoInfo {
    pub fn parse(b: &[u8]) -> EchoInfo {
        let mut o = [0u8; 8];
        o[2..8].copy_from_slice(&b[0..6]);
        let raw = u64::from_be_bytes(o);
        let offset = if raw & (1 << 47) != 0 { raw as i64 - (1i64 << 48) } else { raw as i64 };
        EchoInfo { offset, flags: b[6], trips: b[7] }
    }

    pub fn to_bytes(&self) -> [u8; HEADER_LEN_V3 - HEADER_LEN_V2] {
        let mut b = [0u8; HEADER_LEN_V3 - HEADER_LEN_V2];
        b[0..6].copy_from_slice(&((self.offset as u64) & 0xffff_ffff_ffff).to_be_bytes()[2..8]);
        b[6] = self.flags;
        b[7] = self.trips;
        b
    }
}

/// Radio-side TX sink status carried in bytes 20-39 of a version 2 frame (docs/rawfront/PROTOCOL.md).
/// All counters restart at 0 when streaming starts.
#[derive(Debug, Clone, Copy, Default, PartialEq)]
pub struct TxStatus {
    /// TX frames with a valid header received on port 1026.
    pub frames: u32,
    /// TX frames missing according to sequence-number gaps.
    pub lost_frames: u32,
    /// Samples at the virtual DAC that did not match the counter pattern.
    pub bad_samples: u32,
    /// TX FIFO fill in samples (FIFO depth 16,384).
    pub fifo_fill: u16,
    /// Times the virtual DAC found the FIFO empty (it then refills to half before playing).
    pub underflows: u16,
    /// Times a TX frame arrived with the FIFO full (samples dropped).
    pub overflows: u16,
    /// Bit 0 duplex active, bit 1 virtual DAC playing.
    pub flags: u8,
}

pub const TX_FLAG_ACTIVE: u8 = 1 << 0;
pub const TX_FLAG_DAC_PLAYING: u8 = 1 << 1;
/// hl2b5up_raw: register 0x31 real-DAC bit, echo bit.
pub const TX_FLAG_REAL: u8 = 1 << 2;
pub const TX_FLAG_ECHO: u8 = 1 << 3;

impl TxStatus {
    pub fn parse(b: &[u8]) -> TxStatus {
        TxStatus {
            frames: u32::from_be_bytes([b[0], b[1], b[2], b[3]]),
            lost_frames: u32::from_be_bytes([b[4], b[5], b[6], b[7]]),
            bad_samples: u32::from_be_bytes([b[8], b[9], b[10], b[11]]),
            fifo_fill: u16::from_be_bytes([b[12], b[13]]),
            underflows: u16::from_be_bytes([b[14], b[15]]),
            overflows: u16::from_be_bytes([b[16], b[17]]),
            flags: b[18],
        }
    }

    pub fn to_bytes(&self) -> [u8; HEADER_LEN_V2 - HEADER_LEN] {
        let mut b = [0u8; HEADER_LEN_V2 - HEADER_LEN];
        b[0..4].copy_from_slice(&self.frames.to_be_bytes());
        b[4..8].copy_from_slice(&self.lost_frames.to_be_bytes());
        b[8..12].copy_from_slice(&self.bad_samples.to_be_bytes());
        b[12..14].copy_from_slice(&self.fifo_fill.to_be_bytes());
        b[14..16].copy_from_slice(&self.underflows.to_be_bytes());
        b[16..18].copy_from_slice(&self.overflows.to_be_bytes());
        b[18] = self.flags;
        b
    }
}

// ---- PC -> HL2 TX frames (duplex image, port 1026, docs/rawfront/PROTOCOL.md) --------------------------------
pub const TX_HEADER_LEN: usize = 16;
pub const TX_MAGIC: u8 = 0x5A;
pub const TX_VERSION: u8 = 0x01;
/// TX header flags byte bit 0: payload is the counter pattern (informational; the radio always
/// checks the pattern).
pub const TX_FLAG_PATTERN: u8 = 1 << 0;
/// Depth of the radio's TX FIFO in the duplex image.
pub const TX_FIFO_DEPTH: u16 = 16_384;

/// TX frame header: magic, version, flags, 0, 32-bit sequence number, 48-bit index of the
/// first sample, 16-bit sample count. Big-endian. Samples follow, packed like RX frames.
pub fn build_tx_header(seq: u32, first_sample_index: u64, samples: u16) -> [u8; TX_HEADER_LEN] {
    let mut b = [0u8; TX_HEADER_LEN];
    b[0] = TX_MAGIC;
    b[1] = TX_VERSION;
    b[2] = TX_FLAG_PATTERN;
    b[4..8].copy_from_slice(&seq.to_be_bytes());
    b[8..14].copy_from_slice(&first_sample_index.to_be_bytes()[2..8]);
    b[14..16].copy_from_slice(&samples.to_be_bytes());
    b
}

/// Parsed TX frame header (used by the emulator).
#[derive(Debug, Clone, Copy)]
pub struct TxHeader {
    pub seq: u32,
    pub first_sample_index: u64,
    pub samples: u16,
}

pub fn parse_tx_header(b: &[u8]) -> Option<TxHeader> {
    if b.len() < TX_HEADER_LEN || b[0] != TX_MAGIC || b[1] != TX_VERSION {
        return None;
    }
    let mut idx = [0u8; 8];
    idx[2..8].copy_from_slice(&b[8..14]);
    Some(TxHeader {
        seq: u32::from_be_bytes([b[4], b[5], b[6], b[7]]),
        first_sample_index: u64::from_be_bytes(idx),
        samples: u16::from_be_bytes([b[14], b[15]]),
    })
}

/// Samples per frame for a given IP MTU and header length (20 or 40 for RX frames, 16 for TX
/// frames), rounded down to an even count.
pub fn samples_per_frame_for_ip_mtu_hdr(ip_mtu: usize, header_len: usize) -> u16 {
    let samples_payload = ip_mtu.saturating_sub(28).saturating_sub(header_len);
    ((samples_payload / 3) * 2).min(u16::MAX as usize) as u16
}

/// Fill a TX frame payload (after the header) with the counter pattern: sample k is
/// (first_sample_index + k) mod 4096. Returns the number of bytes written.
pub fn fill_tx_pattern(out: &mut [u8], first_sample_index: u64, samples: u16) -> usize {
    let mut v = (first_sample_index % 4096) as u16;
    let mut w = 0;
    for _ in 0..(samples / 2) {
        let a = v;
        let b = (v + 1) & 0x0fff;
        v = (v + 2) & 0x0fff;
        out[w] = (a >> 4) as u8;
        out[w + 1] = (((a & 0x0f) << 4) | (b >> 8)) as u8;
        out[w + 2] = (b & 0xff) as u8;
        w += 3;
    }
    w
}

impl FrameHeader {
    /// Parse a frame header from the start of a UDP payload. Returns None if too short or the
    /// magic/version bytes don't match (i.e. not a rawstream frame).
    pub fn parse(buf: &[u8]) -> Option<FrameHeader> {
        if buf.len() < HEADER_LEN {
            return None;
        }
        if buf[0] != FRAME_MAGIC {
            return None;
        }
        let (header_len, tx, echo) = match buf[1] {
            FRAME_VERSION => (HEADER_LEN, None, None),
            FRAME_VERSION_DUPLEX if buf.len() >= HEADER_LEN_V2 => {
                (HEADER_LEN_V2, Some(TxStatus::parse(&buf[HEADER_LEN..HEADER_LEN_V2])), None)
            }
            FRAME_VERSION_RAWFRONT if buf.len() >= HEADER_LEN_V3 => (
                HEADER_LEN_V3,
                Some(TxStatus::parse(&buf[HEADER_LEN..HEADER_LEN_V2])),
                Some(EchoInfo::parse(&buf[HEADER_LEN_V2..HEADER_LEN_V3])),
            ),
            _ => return None,
        };
        let flags = buf[2];
        let safety = buf[3];
        let seq = u32::from_be_bytes([buf[4], buf[5], buf[6], buf[7]]);
        // 48-bit first-sample index, bytes 8..14
        let mut idx_bytes = [0u8; 8];
        idx_bytes[2..8].copy_from_slice(&buf[8..14]);
        let first_sample_index = u64::from_be_bytes(idx_bytes);
        let samples_in_frame = u16::from_be_bytes([buf[14], buf[15]]);
        let overflow_count = u16::from_be_bytes([buf[16], buf[17]]);
        let fifo_high_water = u16::from_be_bytes([buf[18], buf[19]]);
        Some(FrameHeader {
            flags,
            safety,
            seq,
            first_sample_index,
            samples_in_frame,
            overflow_count,
            fifo_high_water,
            header_len,
            tx,
            echo,
        })
    }

    pub fn is_test_pattern(&self) -> bool {
        self.flags & FLAG_TEST_PATTERN != 0
    }
    pub fn is_overflow(&self) -> bool {
        self.flags & FLAG_OVERFLOW != 0
    }
    /// True if a sample in the PREVIOUS frame (not this one) was at full scale. See
    /// `FLAG_ADC_CLIP_PREV_FRAME`'s doc comment.
    pub fn is_adc_clip_prev_frame(&self) -> bool {
        self.flags & FLAG_ADC_CLIP_PREV_FRAME != 0
    }
    pub fn is_quiet_capture(&self) -> bool {
        self.flags & FLAG_QUIET_CAPTURE != 0
    }
    pub fn is_first_frame(&self) -> bool {
        self.flags & FLAG_FIRST_FRAME != 0
    }
    pub fn is_gap(&self) -> bool {
        self.flags & FLAG_GAP != 0
    }
}

/// Number of payload bytes needed to carry `n` packed 12-bit samples (2 samples -> 3 bytes,
/// rounded up for an odd trailing sample though the plan says frame sizes are always even).
pub fn packed_len(n_samples: usize) -> usize {
    (n_samples * 3 + 1) / 2
}

/// Unpack 12-bit samples packed 2-per-3-bytes, big-endian: `a[11:4]`, `{a[3:0],b[11:8]}`,
/// `b[7:0]`. Appends sign-extended i16 values to `out`. Any odd leftover byte is ignored.
pub fn unpack_samples_i16(payload: &[u8], out: &mut Vec<i16>) {
    let pairs = payload.len() / 3;
    out.reserve(pairs * 2);
    for i in 0..pairs {
        let b0 = payload[i * 3] as u16;
        let b1 = payload[i * 3 + 1] as u16;
        let b2 = payload[i * 3 + 2] as u16;
        let a = (b0 << 4) | (b1 >> 4);
        let b = ((b1 & 0x0f) << 8) | b2;
        out.push(sign_extend_12(a));
        out.push(sign_extend_12(b));
    }
}

#[inline]
pub fn sign_extend_12(v: u16) -> i16 {
    let v = v & 0x0fff;
    if v & 0x0800 != 0 {
        (v | 0xf000) as i16
    } else {
        v as i16
    }
}

/// Expected test-pattern value for sample `k` (0-based) of a frame whose header says the first
/// sample's index is `first_sample_index` — docs/rawfront/PROTOCOL.md "Test pattern": `(I + k) mod 4096`.
/// Anchored to the header's own index field on purpose, not to a running count carried across
/// frames, so a checker doesn't need to reconstruct state across lost/reordered frames.
#[inline]
pub fn expected_pattern_value(first_sample_index: u64, k: usize) -> u16 {
    ((first_sample_index + k as u64) % 4096) as u16
}

/// Pack two 12-bit values (as produced by the test-pattern generator, or from real samples)
/// into 3 bytes, matching the on-wire order. Used by the --emulate sender.
#[inline]
pub fn pack_pair(a: u16, b: u16) -> [u8; 3] {
    let a = a & 0x0fff;
    let b = b & 0x0fff;
    [
        (a >> 4) as u8,
        (((a & 0x0f) << 4) | (b >> 8)) as u8,
        (b & 0xff) as u8,
    ]
}

/// Samples per frame for a given IP MTU (the "IP MTU" column of the plan's rate table, §2.5),
/// rounded down to an even count so the 2-samples-per-3-bytes packing has no leftover sample.
/// Verified against the plan's own table: 1500 -> 968, 4074 -> 2684, 9000 -> 5968.
///   udp_payload_max = ip_mtu - 28          (20-byte IP header + 8-byte UDP header)
///   samples_payload  = udp_payload_max - HEADER_LEN
///   samples_per_frame = floor(samples_payload / 3) * 2
pub fn samples_per_frame_for_ip_mtu(ip_mtu: usize) -> u16 {
    let udp_payload_max = ip_mtu.saturating_sub(28);
    let samples_payload = udp_payload_max.saturating_sub(HEADER_LEN);
    let pairs = samples_payload / 3;
    // Saturate before the u16 cast: an absurd --ip-mtu (bigger than any real jumbo frame) must
    // not silently wrap around to a small number here -- `clamp_samples_per_frame` (called by
    // every caller) will clamp this down to MAX_SAMPLES_PER_FRAME (7,680) anyway, but it must
    // see the true oversized value to do that, not a wrapped-around small one.
    (pairs * 2).min(u16::MAX as usize) as u16
}

/// A Windows NIC "Jumbo Frame" setting (e.g. 9014) is the total frame size including the
/// 14-byte Ethernet header; IP MTU is that minus 14. The "no jumbo" case is the odd one out:
/// Windows just uses the standard 1500 IP MTU directly, there is no separate NIC setting for
/// it. Caller should pass 1500 directly for that case rather than through this function.
pub fn ip_mtu_for_nic_jumbo_setting(nic_setting: usize) -> usize {
    nic_setting.saturating_sub(14)
}

/// Expected frame rate for a given samples-per-frame, at the nominal 76.8 MSPS ADC rate.
pub fn expected_frames_per_sec(samples_per_frame: u16) -> f64 {
    76_800_000.0 / samples_per_frame as f64
}

/// Build a full frame header (20 bytes) for the --emulate sender.
#[allow(clippy::too_many_arguments)]
pub fn build_header(
    flags: u8,
    seq: u32,
    first_sample_index: u64,
    samples_in_frame: u16,
    overflow_count: u16,
    fifo_high_water: u16,
) -> [u8; HEADER_LEN] {
    let mut buf = [0u8; HEADER_LEN];
    buf[0] = FRAME_MAGIC;
    buf[1] = FRAME_VERSION;
    buf[2] = flags;
    buf[3] = 0;
    buf[4..8].copy_from_slice(&seq.to_be_bytes());
    let idx_bytes = first_sample_index.to_be_bytes(); // 8 bytes, top 2 unused (48-bit field)
    buf[8..14].copy_from_slice(&idx_bytes[2..8]);
    buf[14..16].copy_from_slice(&samples_in_frame.to_be_bytes());
    buf[16..18].copy_from_slice(&overflow_count.to_be_bytes());
    buf[18..20].copy_from_slice(&fifo_high_water.to_be_bytes());
    buf
}

/// Build a version 2 (duplex) header for the --emulate sender.
pub fn build_header_v2(
    flags: u8,
    seq: u32,
    first_sample_index: u64,
    samples_in_frame: u16,
    tx: &TxStatus,
) -> [u8; HEADER_LEN_V2] {
    let mut buf = [0u8; HEADER_LEN_V2];
    buf[..HEADER_LEN].copy_from_slice(&build_header(flags, seq, first_sample_index, samples_in_frame, 0, 0));
    buf[1] = FRAME_VERSION_DUPLEX;
    buf[HEADER_LEN..].copy_from_slice(&tx.to_bytes());
    buf
}

/// Build a version 3 (raw front-end) header for the --emulate sender.
pub fn build_header_v3(
    flags: u8,
    seq: u32,
    first_sample_index: u64,
    samples_in_frame: u16,
    tx: &TxStatus,
    echo: &EchoInfo,
) -> [u8; HEADER_LEN_V3] {
    let mut buf = [0u8; HEADER_LEN_V3];
    buf[..HEADER_LEN_V2].copy_from_slice(&build_header_v2(flags, seq, first_sample_index, samples_in_frame, tx));
    buf[1] = FRAME_VERSION_RAWFRONT;
    buf[HEADER_LEN_V2..].copy_from_slice(&echo.to_bytes());
    buf
}

// ---- Aux data channel (hl2b5up_aux image, docs/rawfront/PROTOCOL.md) ------------------------------------------
/// Aux packets both ways: PC -> radio to this port, radio -> PC from this port back to the socket
/// that last sent to it.
pub const PORT_AUX: u16 = 1027;
/// Register 0x32: bit 0 aux on, bit 1 echo, bit 2 radio counter stream, bits 31:16 counter
/// stream rate in bytes per millisecond.
pub const REG_ADDR_AUX: u8 = 0x32;
pub const REG_AUX_ON: u32 = 1 << 0;
pub const REG_AUX_ECHO: u32 = 1 << 1;
pub const REG_AUX_COUNTER: u32 = 1 << 2;

pub const AUX_PC_MAGIC: u8 = 0x5B;
pub const AUX_RADIO_MAGIC: u8 = 0xB5;
pub const AUX_VERSION: u8 = 0x01;
/// PC -> radio aux header length.
pub const AUX_PC_HEADER_LEN: usize = 16;
/// Radio -> PC aux header length.
pub const AUX_RADIO_HEADER_LEN: usize = 44;
/// PC -> radio flags bit 0: address announcement only (no payload, not counted by the radio).
pub const AUX_FLAG_HELLO: u8 = 1 << 0;
/// Largest radio -> PC aux UDP payload (header included).
pub const AUX_RADIO_MAX_PAYLOAD: usize = 1400;
/// Depth of the radio's echo FIFO in bytes.
pub const AUX_ECHO_FIFO_DEPTH: usize = 4096;

/// Register 0x32 value. `counter_bytes_per_ms` is clamped to 16 bits.
pub fn reg_aux_value(on: bool, echo: bool, counter: bool, counter_bytes_per_ms: u32) -> u32 {
    let mut v = 0u32;
    if on {
        v |= REG_AUX_ON;
    }
    if echo {
        v |= REG_AUX_ECHO;
    }
    if counter {
        v |= REG_AUX_COUNTER;
    }
    v | (counter_bytes_per_ms.min(0xffff) << 16)
}

/// PC -> radio aux header: magic, version, flags, 0, 32-bit sequence number, 32-bit offset of
/// the first payload byte in the PC's aux byte stream, 16-bit payload length, 0, 0.
pub fn build_aux_pc_header(seq: u32, offset: u32, len: u16, flags: u8) -> [u8; AUX_PC_HEADER_LEN] {
    let mut b = [0u8; AUX_PC_HEADER_LEN];
    b[0] = AUX_PC_MAGIC;
    b[1] = AUX_VERSION;
    b[2] = flags;
    b[4..8].copy_from_slice(&seq.to_be_bytes());
    b[8..12].copy_from_slice(&offset.to_be_bytes());
    b[12..14].copy_from_slice(&len.to_be_bytes());
    b
}

/// Aux byte pattern, both directions: the byte at stream offset `o` is byte (o mod 4) of the
/// big-endian 32-bit word o / 4. Any 8 consecutive bytes reveal their own offset.
#[inline]
pub fn aux_pattern_byte(o: u32) -> u8 {
    (o >> 2).to_be_bytes()[(o & 3) as usize]
}

pub fn fill_aux_pattern(out: &mut [u8], offset: u32) {
    for (k, b) in out.iter_mut().enumerate() {
        *b = aux_pattern_byte(offset.wrapping_add(k as u32));
    }
}

/// If `b` (at least 8 bytes) is a run of the aux pattern, the stream offset of `b[0]`.
pub fn aux_pattern_locate(b: &[u8]) -> Option<u32> {
    if b.len() < 8 {
        return None;
    }
    for a in 0..4usize {
        let w = u32::from_be_bytes([b[a], b[a + 1], b[a + 2], b[a + 3]]);
        if w >= 1 << 30 {
            continue;
        }
        let o = (w << 2).wrapping_sub(a as u32);
        if (0..8).all(|k| b[k] == aux_pattern_byte(o.wrapping_add(k as u32))) {
            return Some(o);
        }
    }
    None
}

/// Radio -> PC aux header (docs/rawfront/PROTOCOL.md).
#[derive(Debug, Clone, Copy, Default, PartialEq)]
pub struct RadioAuxHeader {
    /// Bit 0 aux on, bit 1 echo on, bit 2 counter stream on, bit 3 raw stream running.
    pub flags: u8,
    pub seq: u32,
    /// Echo byte offset: echo bytes the radio sent before this packet.
    pub echo_offset: u32,
    pub echo_len: u16,
    /// Counter stream offset of the first counter byte in this packet.
    pub counter_offset: u32,
    pub counter_len: u16,
    /// Radio's PC -> radio checker: aux packets received, lost (sequence gaps), bad payload
    /// bytes, payload bytes received, echo FIFO overflow events.
    pub rx_packets: u32,
    pub rx_lost: u32,
    pub rx_bad: u32,
    pub rx_bytes: u32,
    pub rx_overflows: u16,
    /// Echo FIFO fill in bytes when the packet was planned.
    pub fifo_fill: u16,
    /// How long bytes of this packet waited for a send slot, microseconds (saturates).
    pub wait_us: u16,
    /// Packets whose bytes waited 10 ms or more.
    pub starved: u16,
}

impl RadioAuxHeader {
    pub fn parse(b: &[u8]) -> Option<RadioAuxHeader> {
        if b.len() < AUX_RADIO_HEADER_LEN || b[0] != AUX_RADIO_MAGIC || b[1] != AUX_VERSION {
            return None;
        }
        let u32at = |i: usize| u32::from_be_bytes([b[i], b[i + 1], b[i + 2], b[i + 3]]);
        let u16at = |i: usize| u16::from_be_bytes([b[i], b[i + 1]]);
        let h = RadioAuxHeader {
            flags: b[2],
            seq: u32at(4),
            echo_offset: u32at(8),
            echo_len: u16at(12),
            counter_offset: u32at(14),
            counter_len: u16at(18),
            rx_packets: u32at(20),
            rx_lost: u32at(24),
            rx_bad: u32at(28),
            rx_bytes: u32at(32),
            rx_overflows: u16at(36),
            fifo_fill: u16at(38),
            wait_us: u16at(40),
            starved: u16at(42),
        };
        if b.len() < AUX_RADIO_HEADER_LEN + h.echo_len as usize + h.counter_len as usize {
            return None;
        }
        Some(h)
    }

    /// Build a header (tests).
    pub fn to_bytes(&self) -> [u8; AUX_RADIO_HEADER_LEN] {
        let mut b = [0u8; AUX_RADIO_HEADER_LEN];
        b[0] = AUX_RADIO_MAGIC;
        b[1] = AUX_VERSION;
        b[2] = self.flags;
        b[4..8].copy_from_slice(&self.seq.to_be_bytes());
        b[8..12].copy_from_slice(&self.echo_offset.to_be_bytes());
        b[12..14].copy_from_slice(&self.echo_len.to_be_bytes());
        b[14..18].copy_from_slice(&self.counter_offset.to_be_bytes());
        b[18..20].copy_from_slice(&self.counter_len.to_be_bytes());
        b[20..24].copy_from_slice(&self.rx_packets.to_be_bytes());
        b[24..28].copy_from_slice(&self.rx_lost.to_be_bytes());
        b[28..32].copy_from_slice(&self.rx_bad.to_be_bytes());
        b[32..36].copy_from_slice(&self.rx_bytes.to_be_bytes());
        b[36..38].copy_from_slice(&self.rx_overflows.to_be_bytes());
        b[38..40].copy_from_slice(&self.fifo_fill.to_be_bytes());
        b[40..42].copy_from_slice(&self.wait_us.to_be_bytes());
        b[42..44].copy_from_slice(&self.starved.to_be_bytes());
        b
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn v2_header_roundtrip() {
        let tx = TxStatus {
            frames: 123_456,
            lost_frames: 7,
            bad_samples: 0x0102_0304,
            fifo_fill: 8192,
            underflows: 2,
            overflows: 65535,
            flags: TX_FLAG_ACTIVE | TX_FLAG_DAC_PLAYING,
        };
        let h = build_header_v2(FLAG_TEST_PATTERN, 9, 1_000_000, 5954, &tx);
        assert_eq!(h[1], 0x02);
        let p = FrameHeader::parse(&h).unwrap();
        assert_eq!(p.header_len, 40);
        assert_eq!(p.seq, 9);
        assert_eq!(p.samples_in_frame, 5954);
        assert_eq!(p.tx, Some(tx));
        // version 1 frames keep a 20-byte header and no TX status
        let p1 = FrameHeader::parse(&build_header(0, 1, 2, 968, 0, 0)).unwrap();
        assert_eq!(p1.header_len, 20);
        assert!(p1.tx.is_none());
        // byte 3: transmit-safety status
        let mut h3 = build_header(0, 1, 2, 968, 0, 0);
        assert_eq!(FrameHeader::parse(&h3).unwrap().safety, 0);
        h3[3] = SAFETY_TX_FORCED_OFF | SAFETY_PTT_IN;
        assert_eq!(FrameHeader::parse(&h3).unwrap().safety, 0x09);
        assert_eq!(safety_text(0x09), "0x09 tx-off ptt-in");
        assert_eq!(safety_text(0x42), "0x42 PA-KEYED OVER-TEMP");
        // a version 2 frame cut short is rejected
        assert!(FrameHeader::parse(&h[..30]).is_none());
    }

    #[test]
    fn v3_header_roundtrip() {
        let tx = TxStatus { frames: 5, flags: TX_FLAG_ACTIVE | TX_FLAG_DAC_PLAYING | TX_FLAG_ECHO, ..Default::default() };
        for &off in &[-8259i64, 0, 12345, -(1i64 << 47)] {
            let e = EchoInfo { offset: off, flags: ECHO_F_VALID | ECHO_F_ECHO, trips: 0x21 };
            let h = build_header_v3(0, 3, 77, 5948, &tx, &e);
            assert_eq!(h[1], 0x03);
            let p = FrameHeader::parse(&h).unwrap();
            assert_eq!(p.header_len, 48);
            assert_eq!(p.tx, Some(tx));
            assert_eq!(p.echo, Some(e));
        }
        // bytes as the gateware writes them: offset -8259 = 0xFFFF_FFFF_DFBD
        let h = build_header_v3(0, 0, 0, 2, &tx, &EchoInfo { offset: -8259, flags: 1, trips: 0 });
        assert_eq!(&h[40..46], &[0xff, 0xff, 0xff, 0xff, 0xdf, 0xbd]);
        assert_eq!(samples_per_frame_for_ip_mtu_hdr(9000, HEADER_LEN_V3), 5948);
        assert!(FrameHeader::parse(&h[..44]).is_none());
    }

    #[test]
    fn tx_frame_layout() {
        let h = build_tx_header(0x0a0b0c0d, 0x0000_1234_5678_9abc, 5970);
        assert_eq!(&h[0..4], &[0x5a, 0x01, 0x01, 0x00]);
        let p = parse_tx_header(&h).unwrap();
        assert_eq!(p.seq, 0x0a0b0c0d);
        assert_eq!(p.first_sample_index, 0x1234_5678_9abc);
        assert_eq!(p.samples, 5970);
        // 9,000-byte IP MTU: 5,970 TX samples (16-byte header), 5,954 RX samples (40-byte header)
        assert_eq!(samples_per_frame_for_ip_mtu_hdr(9000, TX_HEADER_LEN), 5970);
        assert_eq!(samples_per_frame_for_ip_mtu_hdr(9000, HEADER_LEN_V2), 5954);
        assert_eq!(samples_per_frame_for_ip_mtu_hdr(1500, TX_HEADER_LEN), 970);
        assert_eq!(samples_per_frame_for_ip_mtu_hdr(9000, HEADER_LEN), 5968);
        assert!(TX_HEADER_LEN + packed_len(5970) <= 9000 - 28);
        assert!(TX_HEADER_LEN + packed_len(5972) > 9000 - 28);
    }

    #[test]
    fn tx_pattern_matches_unpack() {
        let mut buf = vec![0u8; 9000];
        let idx = 4090u64;
        let w = fill_tx_pattern(&mut buf, idx, 20);
        assert_eq!(w, 30);
        let mut out = Vec::new();
        unpack_samples_i16(&buf[..w], &mut out);
        for (k, s) in out.iter().enumerate() {
            assert_eq!((*s as u16) & 0x0fff, expected_pattern_value(idx, k));
        }
    }

    #[test]
    fn pack_unpack_roundtrip() {
        let pairs = [(0u16, 0u16), (0xfff, 0xfff), (0x123, 0xabc), (1, 2)];
        let mut payload = Vec::new();
        for (a, b) in pairs.iter() {
            payload.extend_from_slice(&pack_pair(*a, *b));
        }
        let mut out = Vec::new();
        unpack_samples_i16(&payload, &mut out);
        assert_eq!(out.len(), pairs.len() * 2);
        for (i, (a, b)) in pairs.iter().enumerate() {
            assert_eq!(out[i * 2] as u16 & 0x0fff, *a);
            assert_eq!(out[i * 2 + 1] as u16 & 0x0fff, *b);
        }
    }

    #[test]
    fn header_roundtrip() {
        let h = build_header(FLAG_TEST_PATTERN | FLAG_FIRST_FRAME, 42, 123456789, 5968, 3, 2000);
        let parsed = FrameHeader::parse(&h).unwrap();
        assert_eq!(parsed.seq, 42);
        assert_eq!(parsed.first_sample_index, 123456789);
        assert_eq!(parsed.samples_in_frame, 5968);
        assert_eq!(parsed.overflow_count, 3);
        assert_eq!(parsed.fifo_high_water, 2000);
        assert!(parsed.is_test_pattern());
        assert!(parsed.is_first_frame());
        assert!(!parsed.is_overflow());
    }

    #[test]
    fn clamp_matches_rawstream_md() {
        // "0 means 968"
        assert_eq!(clamp_samples_per_frame(0), (968, true));
        assert_eq!(clamp_samples_per_frame(968), (968, false));
        // odd -> rounded down to even
        assert_eq!(clamp_samples_per_frame(969), (968, true));
        // "values above 7,680 are cut to 7,680"
        assert_eq!(clamp_samples_per_frame(7_680), (7_680, false));
        assert_eq!(clamp_samples_per_frame(8_000), (7_680, true));
        assert_eq!(clamp_samples_per_frame(u16::MAX), (7_680, true));
    }

    #[test]
    fn start_stop_packets_are_64_bytes() {
        let start = cmd_start();
        let stop = cmd_stop();
        assert_eq!(start.len(), 64);
        assert_eq!(stop.len(), 64);
        assert_eq!(&start[0..4], &[0xEF, 0xFE, 0x04, 0x81]);
        assert_eq!(&stop[0..4], &[0xEF, 0xFE, 0x04, 0x00]);
        assert!(start[4..].iter().all(|&b| b == 0));
        assert!(stop[4..].iter().all(|&b| b == 0));
    }

    #[test]
    fn samples_per_frame_for_ip_mtu_does_not_wrap_on_huge_mtu() {
        // Regression: an absurd --ip-mtu used to overflow the u16 cast and silently produce a
        // tiny wrapped-around value instead of something clamp_samples_per_frame could catch.
        let n = samples_per_frame_for_ip_mtu(99_999);
        assert!(n >= MAX_SAMPLES_PER_FRAME, "{n} should saturate high, not wrap around small");
        let (clamped, was_clamped) = clamp_samples_per_frame(n);
        assert_eq!(clamped, MAX_SAMPLES_PER_FRAME);
        assert!(was_clamped);
    }

    #[test]
    fn known_table_values_from_rawstream_md() {
        assert_eq!(samples_per_frame_for_ip_mtu(1500), 968);
        assert_eq!(samples_per_frame_for_ip_mtu(4074), 2684);
        assert_eq!(samples_per_frame_for_ip_mtu(9000), 5968);
    }

    #[test]
    fn pattern_value_wraps_at_4096() {
        assert_eq!(expected_pattern_value(0, 0), 0);
        assert_eq!(expected_pattern_value(4095, 1), 0);
        assert_eq!(expected_pattern_value(1_000_000, 0), (1_000_000u64 % 4096) as u16);
    }

    #[test]
    fn aux_pattern_and_locate() {
        let mut buf = vec![0u8; 64];
        fill_aux_pattern(&mut buf, 0x0123_4566);
        // offset 0x01234566 = word 0x0048D159, byte 2
        assert_eq!(buf[0], 0xD1);
        assert_eq!(buf[1], 0x59);
        assert_eq!(buf[2], 0x00);
        for start in 0..8 {
            assert_eq!(aux_pattern_locate(&buf[start..]), Some(0x0123_4566 + start as u32));
        }
        assert_eq!(aux_pattern_byte(0), 0);
        assert_eq!(aux_pattern_byte(7), 1);
        let mut bad = buf.clone();
        bad[3] ^= 0x10;
        assert_eq!(aux_pattern_locate(&bad), None);
        assert_eq!(aux_pattern_locate(&buf[..7]), None);
    }

    #[test]
    fn aux_headers() {
        let h = build_aux_pc_header(7, 0x1000, 1024, 0);
        assert_eq!(&h[0..4], &[0x5b, 0x01, 0x00, 0x00]);
        assert_eq!(&h[8..14], &[0x00, 0x00, 0x10, 0x00, 0x04, 0x00]);
        let r = RadioAuxHeader {
            flags: 0x0f,
            seq: 1,
            echo_offset: 2,
            echo_len: 3,
            counter_offset: 4,
            counter_len: 5,
            rx_packets: 6,
            rx_lost: 7,
            rx_bad: 8,
            rx_bytes: 9,
            rx_overflows: 10,
            fifo_fill: 11,
            wait_us: 12,
            starved: 13,
        };
        let mut pkt = r.to_bytes().to_vec();
        pkt.extend_from_slice(&[0u8; 8]);
        assert_eq!(RadioAuxHeader::parse(&pkt), Some(r));
        assert!(RadioAuxHeader::parse(&pkt[..50]).is_none(), "payload shorter than the lengths");
        assert_eq!(reg_aux_value(true, true, true, 6250), 0x186a_0007);
    }
}
