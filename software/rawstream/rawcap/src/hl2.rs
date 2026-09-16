// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Franz Schöning, https://www.schoning.com
//
//! openHPSDR discovery and control (start/stop, raw-mode register) for the HL2.
//! Wire bytes come only from `protocol.rs`.

use crate::protocol;
use std::net::{IpAddr, SocketAddr, UdpSocket};
use std::time::Duration;

pub struct Discovered {
    pub ip: IpAddr,
    pub mac: [u8; 6],
    pub gateware: (u8, u8),
    pub board_id: u8,
    pub receivers: u8,
}

pub fn mac_string(mac: &[u8; 6]) -> String {
    format!(
        "{:02x}:{:02x}:{:02x}:{:02x}:{:02x}:{:02x}",
        mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]
    )
}

/// Broadcast openHPSDR discovery on the given local interface IP and collect responses for
/// up to `timeout`. Tries port 1025 first, then falls back to 1024 (matches
/// `software/hermeslite/hermeslite.py`).
pub fn discover(local_ip: IpAddr, timeout: Duration) -> std::io::Result<Vec<Discovered>> {
    for port in [protocol::PORT_CMD, protocol::PORT_START_STOP] {
        let found = discover_on_port(local_ip, port, timeout)?;
        if !found.is_empty() {
            return Ok(found);
        }
        println!("rawcap: no discovery response on port {port}, trying next port");
    }
    Ok(Vec::new())
}

fn discover_on_port(local_ip: IpAddr, port: u16, timeout: Duration) -> std::io::Result<Vec<Discovered>> {
    let sock = UdpSocket::bind(SocketAddr::new(local_ip, 0))?;
    sock.set_broadcast(true)?;
    sock.set_read_timeout(Some(Duration::from_millis(300)))?;
    let req = protocol::build_discovery_request();
    sock.send_to(&req, ("255.255.255.255", port))?;

    let mut out = Vec::new();
    let mut buf = [0u8; 128];
    let deadline = std::time::Instant::now() + timeout;
    while std::time::Instant::now() < deadline {
        match sock.recv_from(&mut buf) {
            Ok((n, from)) => {
                if let Some(r) = protocol::parse_discovery_response(&buf[..n]) {
                    out.push(Discovered {
                        ip: from.ip(),
                        mac: r.mac,
                        gateware: (r.gateware_major, r.gateware_minor),
                        board_id: r.board_id,
                        receivers: r.receivers,
                    });
                }
            }
            Err(e) if e.kind() == std::io::ErrorKind::WouldBlock || e.kind() == std::io::ErrorKind::TimedOut => {
                continue;
            }
            Err(e) => return Err(e),
        }
    }
    Ok(out)
}

/// A control connection to one HL2: used to write the raw-mode register and to send
/// start/stop. Start/stop and the stream itself go to `stream_socket` (see main.rs — the
/// receive socket must be open and used to send start, per the plan's port-unreachable rule),
/// register writes go out on their own short-lived socket to port 1025.
pub struct Hl2Control {
    pub ip: IpAddr,
}

impl Hl2Control {
    pub fn new(ip: IpAddr) -> Self {
        Hl2Control { ip }
    }

    /// Write the raw-mode/frame-size register (address 0x30) and wait briefly for the ack.
    pub fn set_raw_mode(&self, enable: bool, test_pattern: bool, quiet_capture: bool, samples_per_frame: u16) -> std::io::Result<()> {
        let value = protocol::reg_raw_value(enable, test_pattern, quiet_capture, samples_per_frame);
        self.write_raw_register(value)
    }

    /// Turn raw mode fully off (register 0x30 = 0x00000000, docs/rawfront/PROTOCOL.md). Call this on
    /// stop/exit: raw mode stays on until explicitly cleared (or the HL2 is power-cycled), and
    /// if it's left on, Quisk or other normal SDR software gets raw frames instead of IQ data
    /// the next time someone starts the radio.
    pub fn clear_raw_mode(&self) -> std::io::Result<()> {
        self.write_raw_register(protocol::reg_raw_off())
    }

    /// Duplex register 0x31 (hl2b5up_duplex image, docs/rawfront/PROTOCOL.md). Other images ignore it.
    pub fn set_duplex(&self, enable: bool) -> std::io::Result<()> {
        let v = if enable { protocol::REG_DUPLEX_ENABLE } else { 0 };
        self.write_register(protocol::REG_ADDR_DUPLEX, v)
    }

    /// Register 0x31 with the hl2b5up_raw mode bits (real DAC, echo).
    pub fn set_duplex_value(&self, value: u32) -> std::io::Result<()> {
        self.write_register(protocol::REG_ADDR_DUPLEX, value)
    }

    pub fn clear_duplex(&self) -> std::io::Result<()> {
        self.set_duplex(false)
    }

    /// Aux register 0x32 (hl2b5up_aux image, docs/rawfront/PROTOCOL.md). Other images ignore it.
    pub fn set_aux(&self, value: u32) -> std::io::Result<()> {
        self.write_register(protocol::REG_ADDR_AUX, value)
    }

    pub fn clear_aux(&self) -> std::io::Result<()> {
        self.set_aux(0)
    }

    fn write_raw_register(&self, value: u32) -> std::io::Result<()> {
        self.write_register(protocol::REG_ADDR_RAWMODE, value)
    }

    fn write_register(&self, addr: u8, value: u32) -> std::io::Result<()> {
        let pkt = protocol::build_command_packet(addr, value);
        let sock = UdpSocket::bind("0.0.0.0:0")?;
        sock.set_read_timeout(Some(Duration::from_millis(500)))?;
        sock.send_to(&pkt, (self.ip, protocol::PORT_CMD))?;
        let mut buf = [0u8; 128];
        // Best-effort ack read; not fatal if none arrives.
        let _ = sock.recv_from(&mut buf);
        Ok(())
    }
}

/// Send the openHPSDR start command on the given (already-bound/open) socket. Per docs/rawfront/PROTOCOL.md,
/// the receiving socket must be open BEFORE this is sent, or an ICMP port-unreachable will make
/// the HL2 stop the stream immediately.
pub fn send_start(sock: &UdpSocket, hl2_ip: IpAddr) -> std::io::Result<()> {
    sock.send_to(&protocol::cmd_start(), (hl2_ip, protocol::PORT_START_STOP))?;
    Ok(())
}

pub fn send_stop(sock: &UdpSocket, hl2_ip: IpAddr) -> std::io::Result<()> {
    sock.send_to(&protocol::cmd_stop(), (hl2_ip, protocol::PORT_START_STOP))?;
    Ok(())
}
