// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Franz Schöning, https://www.schoning.com
//
//! rawcap: Windows PC receiver (and test emulator) for the Hermes-Lite 2 raw ADC Ethernet
//! stream. See README.md in this folder for the full walkthrough. Wire-format details live
//! only in `protocol.rs`.

mod auxchan;
mod duplex;
mod emulate;
mod hl2;
mod protocol;
mod receive;
mod ring;
mod stats;
mod winsys;

use std::net::IpAddr;
use std::sync::atomic::AtomicBool;
use std::sync::{Arc, Mutex};
use std::time::Duration;

/// The radio's IP, once known, for the panic hook below: if rawcap crashes mid-stream, this
/// lets the hook make a best-effort attempt to turn raw mode back off so Quisk or other normal
/// SDR software isn't left receiving raw frames after an abnormal exit. Set right after the
/// radio IP is resolved, before any raw-mode-enabling command is sent.
static HL2_IP_FOR_CLEANUP: Mutex<Option<IpAddr>> = Mutex::new(None);

/// Best-effort: clear raw mode and send stop to `ip`, ignoring errors (there is no good way to
/// report an error from inside a panic hook). Used both by the panic hook and by
/// `--clear-raw-mode`.
fn best_effort_clear_raw_mode(ip: IpAddr) {
    if let Ok(sock) = std::net::UdpSocket::bind("0.0.0.0:0") {
        let _ = sock.send_to(&protocol::cmd_stop(), (ip, protocol::PORT_START_STOP));
    }
    let ctrl = hl2::Hl2Control::new(ip);
    let _ = ctrl.clear_aux();
    let _ = ctrl.clear_duplex();
    let _ = ctrl.clear_raw_mode();
}

fn install_panic_cleanup_hook() {
    let default_hook = std::panic::take_hook();
    std::panic::set_hook(Box::new(move |info| {
        default_hook(info);
        match HL2_IP_FOR_CLEANUP.lock().ok().and_then(|g| *g) {
            Some(ip) => {
                eprintln!(
                    "rawcap: abnormal exit -- attempting to send stop and clear raw mode on {ip} so \
                     Quisk/other software isn't left receiving raw frames..."
                );
                best_effort_clear_raw_mode(ip);
                eprintln!(
                    "rawcap: sent stop + raw-mode-off to {ip}. If that didn't reach the radio, clear \
                     it manually: rawcap --ip {ip} --clear-raw-mode"
                );
            }
            None => {
                eprintln!(
                    "rawcap: abnormal exit before a radio IP was known -- nothing to clean up on the \
                     radio side."
                );
            }
        }
    }));
}

fn main() {
    winsys::install_ctrlc_handler();
    winsys::raise_process_priority();
    install_panic_cleanup_hook();

    let args: Vec<String> = std::env::args().skip(1).collect();
    if args.iter().any(|a| a == "--help" || a == "-h") || args.is_empty() {
        print_help();
        return;
    }

    let opts = match Args::parse(&args) {
        Ok(o) => o,
        Err(e) => {
            eprintln!("rawcap: {e}");
            std::process::exit(2);
        }
    };

    let result = if opts.clear_raw_mode_only {
        cmd_clear_raw_mode(&opts)
    } else if opts.discover_only {
        cmd_discover(&opts)
    } else if opts.emulate {
        cmd_emulate(&opts)
    } else {
        cmd_receive(&opts)
    };

    if let Err(e) = result {
        eprintln!("rawcap: error: {e}");
        std::process::exit(1);
    }
}

fn print_help() {
    println!(
        r#"rawcap - Windows receiver/emulator for the HL2 raw ADC Ethernet stream

USAGE:
  rawcap --discover [--local-ip <ip>]
  rawcap --ip <hl2-ip> [--local-ip <ip>] [--ip-mtu 1500|9000|...] [--mode pattern|adc]
         [--quiet-capture] [--seconds <n>] [--save <file> --save-seconds <n>]
         [--soak] [--rcvbuf <bytes>] [--ring-slots <n>] [--jumbo-ok]
         [--duplex [--sndbuf <bytes>] [--tx-target <samples>] [--lock-in <s>]] [--echo]
         [--aux-rate <Mbit/s> [--aux-radio-rate <Mbit/s>] [--aux-size <bytes>] [--aux-no-echo]]
  rawcap --ip <hl2-ip> --aux-only --aux-rate <Mbit/s> [--seconds <n>] [aux options]
  rawcap --ip <hl2-ip> --clear-raw-mode
  rawcap --emulate [--local-ip <ip>] [--seconds <n>] [--tone-hz <hz>] [--tone-amp <0..1>]
         [--gap-every <n>] [--rate-fraction <0..1>] [--dac-ppm <ppm>]

MODES:
  --discover           Broadcast openHPSDR discovery and print any HL2s found, then exit.
  --emulate            Act like a raw-stream HL2: answer discovery/register/start/stop and
                        stream correctly formatted frames, for testing rawcap with no radio.
  --duplex             Needs hl2b5up_raw (or the earlier duplex test image). While receiving, also send TX frames
                        (counter pattern, UDP port 1026) at the radio's ADC rate, paced closed
                        loop on the radio-reported TX FIFO fill. Prints radio TX counters each
                        second and a separate TX PASS/FAIL. See docs/rawfront/PROTOCOL.md.
  --echo               Needs the hl2b5up_raw image. Duplex (as --duplex) with the radio in echo mode
                        (register 0x31 = 5): the radio puts the TX samples it plays into the RX
                        stream instead of the ADC samples, and never drives the DAC. Checks every
                        echoed sample against the TX index the header's offset gives, and reports
                        Mbit/s and loss each way and the round-trip latency. See docs/rawfront/PROTOCOL.md.
  --aux-only           Needs hl2b5up_raw (or the earlier aux test image). Aux channel test with no sample stream: the
                        radio is not started. See AUX OPTIONS.
  --clear-raw-mode     Recovery: write register 0x30 = 0 (raw mode off) and send stop to --ip,
                        then exit. Use this if rawcap exited abnormally and the radio might be
                        stuck in raw mode (Quisk would then receive raw frames, not IQ data).
  (default)            Connect to --ip, configure raw mode, start, receive and check the
                        stream until --seconds elapses or Ctrl-C, then send stop and clear raw
                        mode again.

COMMON OPTIONS:
  --local-ip <ip>      Local interface IP to bind to. Required on multi-NIC machines.
  --ip <ip>            HL2 (or emulator) IP address. Skips discovery.
  --ip-mtu <bytes>     IP MTU to size frames for: 1500 (default, no jumbo), 4074, or 9000
                        (jumbo 9014 in Windows' NIC settings). See nic_setup.ps1. Values are
                        clamped to what the gateware accepts (max 7,680 samples/frame), and to
                        5,968 samples/frame (IP MTU 9000) unless --jumbo-ok is given, since a
                        standard 9014-byte NIC jumbo setting can't carry more than that.
  --jumbo-ok           Allow requesting more than 5,968 samples/frame -- only if the NIC is
                        actually configured for a jumbo frame bigger than the standard 9014.
  --mode pattern|adc   Counter test pattern (default) or real ADC samples.
  --quiet-capture      Set the quiet-capture header flag (see README.md's quiet-capture note).
  --seconds <n>        Run for n seconds then send stop and exit. Default: run until Ctrl-C.
  --soak                Long-run mode: no --save allowed, periodic stats only, final summary.
  --save <file>         Save packed payload bytes to <file> (plus a <file>.json sidecar).
  --save-seconds <n>    How many seconds to save for (required with --save).
  --rcvbuf <bytes>      Requested SO_RCVBUF. Default 268435456 (256 MB).
  --ring-slots <n>      Ring buffer depth in frames. Default 8192.

DUPLEX OPTIONS:
  --sndbuf <bytes>      Requested SO_SNDBUF for the TX socket. Default 67108864 (64 MB).
  --tx-target <n>       Radio TX FIFO fill to hold, in samples (FIFO depth 16,384). Default 12000.
  --lock-in <s>         Radio TX errors in the first s seconds of sending do not fail the run.
                         Default 2.
  --tx-no-udp-checksum  Send TX datagrams with a zero UDP checksum (the HL2 does not check it).

AUX OPTIONS (hl2b5up_raw, docs/rawfront/PROTOCOL.md section 7; with the RX stream, --duplex, or --aux-only):
  --aux-rate <Mbit/s>   PC -> radio aux payload rate (UDP port 1027, byte pattern). The radio
                         echoes the bytes back and reports its own checker counters. 0 = no PC
                         data. Prints aux counters each second and separate aux PASS/FAIL lines.
  --aux-radio-rate <m>  Radio-generated counter stream, Mbit/s. Default: same as --aux-rate.
  --aux-size <bytes>    PC aux payload bytes per packet. Default 1024.
  --aux-no-echo         Radio does not echo the PC's bytes (it still checks them).

EMULATE-ONLY OPTIONS:
  --tone-hz <hz>        Synthetic tone frequency when a receiver requests ADC (non-pattern)
                         mode. Default 10000000 (10 MHz).
  --tone-amp <0..1>     Tone amplitude as a fraction of full scale. Default 0.1.
  --gap-every <n>       Deliberately drop one frame every n frames, to test gap detection.
  --rate-fraction <f>   Scale the 76.8 MSPS pacing clock (e.g. 0.5 = half rate). Default 1.0.
                         With --duplex on the receiver, pass the same value to both.
  --dac-ppm <ppm>       Emulated TX DAC clock error, to exercise --duplex pacing. Default 0.
"#
    );
}

struct Args {
    discover_only: bool,
    emulate: bool,
    clear_raw_mode_only: bool,
    local_ip: IpAddr,
    hl2_ip: Option<IpAddr>,
    ip_mtu: usize,
    adc_mode: bool, // false = test pattern (default), true = real ADC
    quiet_capture: bool,
    seconds: Option<f64>,
    #[allow(dead_code)] // only used for validation in Args::parse (kept with --save/--soak check)
    soak: bool,
    save: Option<String>,
    save_seconds: Option<f64>,
    rcvbuf: usize,
    ring_slots: usize,
    tone_hz: f64,
    tone_amp: f64,
    gap_every: Option<u64>,
    rate_fraction: f64,
    jumbo_ok: bool,
    duplex: bool,
    sndbuf: usize,
    tx_target: f64,
    lock_in: f64,
    dac_ppm: f64,
    tx_nocsum: bool,
    aux_rate: Option<f64>,
    aux_radio_rate: Option<f64>,
    aux_size: usize,
    aux_no_echo: bool,
    aux_only: bool,
    echo: bool,
}

impl Args {
    fn parse(args: &[String]) -> Result<Args, String> {
        let mut discover_only = false;
        let mut emulate = false;
        let mut clear_raw_mode_only = false;
        let mut local_ip: IpAddr = "0.0.0.0".parse().unwrap();
        let mut hl2_ip = None;
        let mut ip_mtu = 1500usize;
        let mut adc_mode = false;
        let mut quiet_capture = false;
        let mut seconds = None;
        let mut soak = false;
        let mut save = None;
        let mut save_seconds = None;
        let mut rcvbuf = 256usize * 1024 * 1024;
        let mut ring_slots = 8192usize;
        let mut tone_hz = 10_000_000.0;
        let mut tone_amp = 0.1;
        let mut gap_every = None;
        let mut rate_fraction = 1.0;
        let mut jumbo_ok = false;
        let mut duplex = false;
        let mut sndbuf = 64usize * 1024 * 1024;
        // 12,000 of 16,384: 156 us of sender stall before the radio FIFO runs dry, 57 us of
        // headroom above for ripple (one frame adds at most ~470 samples net).
        let mut tx_target = 12_000.0;
        let mut lock_in = 2.0;
        let mut dac_ppm = 0.0;
        let mut tx_nocsum = false;
        let mut aux_rate = None;
        let mut aux_radio_rate = None;
        let mut aux_size = 1024usize;
        let mut aux_no_echo = false;
        let mut aux_only = false;
        let mut echo = false;

        let mut i = 0;
        while i < args.len() {
            let a = args[i].as_str();
            let mut next = || -> Result<&str, String> {
                i += 1;
                args.get(i).map(|s| s.as_str()).ok_or_else(|| format!("{a} needs a value"))
            };
            match a {
                "--discover" => discover_only = true,
                "--emulate" => emulate = true,
                "--clear-raw-mode" => clear_raw_mode_only = true,
                "--jumbo-ok" => jumbo_ok = true,
                "--duplex" => duplex = true,
                "--echo" => {
                    echo = true;
                    duplex = true;
                }
                "--tx-no-udp-checksum" => tx_nocsum = true,
                "--aux-only" => aux_only = true,
                "--aux-no-echo" => aux_no_echo = true,
                "--aux-rate" => aux_rate = Some(next()?.parse().map_err(|_| "bad --aux-rate".to_string())?),
                "--aux-radio-rate" => aux_radio_rate = Some(next()?.parse().map_err(|_| "bad --aux-radio-rate".to_string())?),
                "--aux-size" => aux_size = next()?.parse().map_err(|_| "bad --aux-size".to_string())?,
                "--sndbuf" => sndbuf = next()?.parse().map_err(|_| "bad --sndbuf".to_string())?,
                "--tx-target" => tx_target = next()?.parse().map_err(|_| "bad --tx-target".to_string())?,
                "--lock-in" => lock_in = next()?.parse().map_err(|_| "bad --lock-in".to_string())?,
                "--dac-ppm" => dac_ppm = next()?.parse().map_err(|_| "bad --dac-ppm".to_string())?,
                "--local-ip" => local_ip = next()?.parse().map_err(|_| "bad --local-ip".to_string())?,
                "--ip" => hl2_ip = Some(next()?.parse().map_err(|_| "bad --ip".to_string())?),
                "--ip-mtu" => ip_mtu = next()?.parse().map_err(|_| "bad --ip-mtu".to_string())?,
                "--mode" => {
                    let v = next()?;
                    adc_mode = match v {
                        "pattern" => false,
                        "adc" => true,
                        _ => return Err("--mode must be pattern or adc".into()),
                    };
                }
                "--quiet-capture" => quiet_capture = true,
                "--seconds" => seconds = Some(next()?.parse().map_err(|_| "bad --seconds".to_string())?),
                "--soak" => soak = true,
                "--save" => save = Some(next()?.to_string()),
                "--save-seconds" => save_seconds = Some(next()?.parse().map_err(|_| "bad --save-seconds".to_string())?),
                "--rcvbuf" => rcvbuf = next()?.parse().map_err(|_| "bad --rcvbuf".to_string())?,
                "--ring-slots" => ring_slots = next()?.parse().map_err(|_| "bad --ring-slots".to_string())?,
                "--tone-hz" => tone_hz = next()?.parse().map_err(|_| "bad --tone-hz".to_string())?,
                "--tone-amp" => tone_amp = next()?.parse().map_err(|_| "bad --tone-amp".to_string())?,
                "--gap-every" => gap_every = Some(next()?.parse().map_err(|_| "bad --gap-every".to_string())?),
                "--rate-fraction" => rate_fraction = next()?.parse().map_err(|_| "bad --rate-fraction".to_string())?,
                other => return Err(format!("unknown option {other}")),
            }
            i += 1;
        }

        if save.is_some() != save_seconds.is_some() {
            return Err("--save and --save-seconds must be given together".into());
        }
        if soak && save.is_some() {
            return Err("--soak and --save cannot be combined (soak checks in memory only)".into());
        }
        if aux_only && aux_rate.is_none() && aux_radio_rate.is_none() {
            return Err("--aux-only needs --aux-rate and/or --aux-radio-rate".into());
        }
        if aux_only && (duplex || save.is_some()) {
            return Err("--aux-only runs no sample stream; it cannot be combined with --duplex or --save".into());
        }
        if !(1..=8900).contains(&aux_size) {
            return Err("--aux-size must be 1..8900".into());
        }
        if clear_raw_mode_only && hl2_ip.is_none() {
            return Err("--clear-raw-mode needs --ip".into());
        }

        Ok(Args {
            discover_only,
            emulate,
            clear_raw_mode_only,
            local_ip,
            hl2_ip,
            ip_mtu,
            adc_mode,
            quiet_capture,
            seconds,
            soak,
            save,
            save_seconds,
            rcvbuf,
            ring_slots,
            tone_hz,
            tone_amp,
            gap_every,
            rate_fraction,
            jumbo_ok,
            duplex,
            sndbuf,
            tx_target,
            lock_in,
            dac_ppm,
            tx_nocsum,
            aux_rate,
            aux_radio_rate,
            aux_size,
            aux_no_echo,
            aux_only,
            echo,
        })
    }
}

fn cmd_discover(opts: &Args) -> std::io::Result<()> {
    println!("rawcap: broadcasting discovery on {}", opts.local_ip);
    let found = hl2::discover(opts.local_ip, Duration::from_secs(2))?;
    if found.is_empty() {
        println!("rawcap: no radios found");
    }
    for d in found {
        println!(
            "  IP={} MAC={} gateware={}.{} board_id={} receivers={}",
            d.ip,
            hl2::mac_string(&d.mac),
            d.gateware.0,
            d.gateware.1,
            d.board_id,
            d.receivers
        );
    }
    Ok(())
}

fn cmd_clear_raw_mode(opts: &Args) -> std::io::Result<()> {
    let hl2_ip = opts.hl2_ip.expect("checked in Args::parse");
    println!("rawcap: clearing raw mode (register 0x30 = 0) and sending stop to {hl2_ip}...");
    let ctrl = hl2::Hl2Control::new(hl2_ip);
    ctrl.clear_aux()?;
    ctrl.clear_duplex()?;
    ctrl.clear_raw_mode()?;
    let sock = std::net::UdpSocket::bind((opts.local_ip, 0))?;
    hl2::send_stop(&sock, hl2_ip)?;
    println!("rawcap: done. The radio should now behave as a normal HL2 (IQ data, not raw frames).");
    Ok(())
}

fn cmd_emulate(opts: &Args) -> std::io::Result<()> {
    let stop_flag = Arc::new(AtomicBool::new(false));
    emulate::run(
        emulate::EmulateOptions {
            bind_ip: opts.local_ip,
            tone_hz: opts.tone_hz,
            tone_amp_fraction: opts.tone_amp,
            gap_every: opts.gap_every,
            rate_fraction: opts.rate_fraction,
            dac_ppm: opts.dac_ppm,
            seconds: opts.seconds,
        },
        stop_flag,
    )
}

fn cmd_receive(opts: &Args) -> std::io::Result<()> {
    let hl2_ip = match opts.hl2_ip {
        Some(ip) => ip,
        None => {
            println!("rawcap: no --ip given, running discovery on {}", opts.local_ip);
            let found = hl2::discover(opts.local_ip, Duration::from_secs(2))?;
            match found.first() {
                Some(d) => {
                    println!(
                        "rawcap: using discovered radio IP={} MAC={} gateware={}.{}",
                        d.ip,
                        hl2::mac_string(&d.mac),
                        d.gateware.0,
                        d.gateware.1
                    );
                    d.ip
                }
                None => {
                    return Err(std::io::Error::new(
                        std::io::ErrorKind::NotFound,
                        "no radio found by discovery; pass --ip explicitly",
                    ));
                }
            }
        }
    };

    // From here on, a radio might be told to start raw-streaming, so record its IP for the
    // panic-hook cleanup before sending anything that could put it in that state.
    *HL2_IP_FOR_CLEANUP.lock().unwrap() = Some(hl2_ip);

    let aux_opts = if opts.aux_rate.is_some() || opts.aux_radio_rate.is_some() {
        let pc = opts.aux_rate.unwrap_or(0.0);
        Some(auxchan::AuxOptions {
            local_ip: opts.local_ip,
            hl2_ip,
            pc_rate_mbit: pc,
            radio_rate_mbit: opts.aux_radio_rate.unwrap_or(pc),
            echo: !opts.aux_no_echo,
            packet_size: opts.aux_size,
        })
    } else {
        None
    };
    if opts.aux_only {
        let ctrl = hl2::Hl2Control::new(hl2_ip);
        let _ = ctrl.clear_duplex();
        let _ = ctrl.clear_raw_mode();
        let r = auxchan::run_standalone(aux_opts.expect("checked in Args::parse"), opts.seconds);
        let _ = ctrl.clear_aux();
        *HL2_IP_FOR_CLEANUP.lock().unwrap() = None;
        return r.map(|_| ());
    }

    // Duplex frames carry a 40-byte header (48 on hl2b5up_raw), so the same IP MTU holds fewer samples.
    // Sized for 48 bytes: correct for both images.
    let header_len = if opts.duplex { protocol::HEADER_LEN_V3 } else { protocol::HEADER_LEN };
    let requested = protocol::samples_per_frame_for_ip_mtu_hdr(opts.ip_mtu, header_len);
    if requested < 2 {
        return Err(std::io::Error::new(std::io::ErrorKind::InvalidInput, "ip-mtu too small"));
    }
    // Clamp to what the gateware will actually use (docs/rawfront/PROTOCOL.md: 0 -> 968, cut above 7,680),
    // and separately, unless --jumbo-ok was given, to what a standard 9014-byte NIC jumbo
    // setting can carry (5,968 samples at IP MTU 9000) -- asking for more than that without a
    // bigger jumbo setting configured would just get silently dropped/fragmented by Windows.
    let (mut samples_per_frame, hw_clamped) = protocol::clamp_samples_per_frame(requested);
    if hw_clamped {
        println!(
            "rawcap: warning: {requested} samples/frame is not what the gateware will use; it clamps \
             to {samples_per_frame} (docs/rawfront/PROTOCOL.md: 0 means 968, values above {} are cut to {}).",
            protocol::MAX_SAMPLES_PER_FRAME,
            protocol::MAX_SAMPLES_PER_FRAME
        );
    }
    if samples_per_frame > protocol::MAX_SAMPLES_PER_FRAME_STANDARD_JUMBO && !opts.jumbo_ok {
        println!(
            "rawcap: warning: {samples_per_frame} samples/frame needs an Ethernet frame bigger than a \
             standard 9014-byte NIC jumbo setting can carry. Clamping to {} (IP MTU {}). Pass \
             --jumbo-ok if the NIC is actually configured for something bigger.",
            protocol::MAX_SAMPLES_PER_FRAME_STANDARD_JUMBO,
            opts.ip_mtu
        );
        samples_per_frame = protocol::MAX_SAMPLES_PER_FRAME_STANDARD_JUMBO;
    }
    println!(
        "rawcap: ip-mtu={} -> samples/frame={} (expected ~{:.0} frames/s at 76.8 MSPS)",
        opts.ip_mtu,
        samples_per_frame,
        protocol::expected_frames_per_sec(samples_per_frame)
    );

    // 1. Configure raw mode + frame size on the HL2 (register 0x30, port 1025). Order relative
    //    to opening the stream socket does not matter: this goes to a different port than the
    //    one the ICMP port-unreachable rule cares about (see protocol.rs).
    let ctrl = hl2::Hl2Control::new(hl2_ip);
    ctrl.set_raw_mode(true, !opts.adc_mode, opts.quiet_capture, samples_per_frame)?;
    let tx_samples_per_frame = protocol::samples_per_frame_for_ip_mtu_hdr(opts.ip_mtu, protocol::TX_HEADER_LEN);
    if opts.duplex {
        let reg = protocol::REG_DUPLEX_ENABLE | if opts.echo { protocol::REG_DUPLEX_ECHO } else { 0 };
        ctrl.set_duplex_value(reg)?;
        println!(
            "rawcap: duplex on (register 0x31 = {reg}{}): TX frames of {} samples to port {}, {:.0} frames/s, target radio FIFO fill {:.0}",
            if opts.echo { ", echo" } else { "" },
            tx_samples_per_frame,
            protocol::PORT_TX,
            protocol::expected_frames_per_sec(tx_samples_per_frame) * opts.rate_fraction,
            opts.tx_target
        );
    } else {
        // A duplex image left in duplex mode by an earlier run would send version 2 frames.
        let _ = ctrl.clear_duplex();
    }

    // 2. Open and size the stream socket BEFORE sending start (docs/rawfront/PROTOCOL.md: an ICMP port-
    //    unreachable on a closed port makes the HL2 stop the stream).
    let sock = receive::open_socket(opts.local_ip, opts.rcvbuf)?;

    // 3. Send start.
    hl2::send_start(&sock, hl2_ip)?;
    println!("rawcap: sent start to {hl2_ip}, receiving...");

    let recv_opts = receive::ReceiveOptions {
        seconds: opts.seconds, // None = run until Ctrl-C; --soak just forbids --save (above)
        save_path: opts.save.clone(),
        save_seconds: opts.save_seconds,
        pattern_mode: !opts.adc_mode,
        ring_slots: opts.ring_slots,
        duplex: if opts.duplex {
            Some(receive::DuplexRun {
                sender: duplex::SenderOptions {
                    local_ip: opts.local_ip,
                    hl2_ip,
                    samples_per_frame: tx_samples_per_frame,
                    sndbuf: opts.sndbuf,
                    target_fill: opts.tx_target,
                    rate_fraction: opts.rate_fraction,
                    no_udp_checksum: opts.tx_nocsum,
                    send_times: None,
                },
                lock_in_secs: opts.lock_in,
            })
        } else {
            None
        },
        aux: aux_opts,
        echo: opts.echo,
    };
    let stop_flag = Arc::new(AtomicBool::new(false));
    let run_result = receive::run(sock, recv_opts, stop_flag);

    // 4. Always try to send stop AND clear raw mode, even if the run loop errored. Raw mode
    //    stays on until explicitly cleared or the radio is power-cycled (docs/rawfront/PROTOCOL.md) -- if
    //    left on, Quisk or other normal SDR software gets raw frames instead of IQ data the
    //    next time someone starts the radio.
    if let Ok(stop_sock) = std::net::UdpSocket::bind((opts.local_ip, 0)) {
        let _ = hl2::send_stop(&stop_sock, hl2_ip);
    }
    println!("rawcap: sent stop to {hl2_ip}");
    if opts.duplex {
        let _ = ctrl.clear_duplex();
    }
    let _ = ctrl.clear_aux();
    if let Err(e) = ctrl.clear_raw_mode() {
        println!(
            "rawcap: warning: could not clear raw mode on {hl2_ip} ({e}). The radio may still be in \
             raw mode -- run: rawcap --ip {hl2_ip} --clear-raw-mode"
        );
    } else {
        println!("rawcap: cleared raw mode on {hl2_ip} (register 0x30 = 0)");
    }
    // Cleanup succeeded via the normal path; the panic hook no longer needs to do anything for
    // this IP even if something goes wrong later during shutdown.
    *HL2_IP_FOR_CLEANUP.lock().unwrap() = None;

    run_result.map(|_| ())
}
