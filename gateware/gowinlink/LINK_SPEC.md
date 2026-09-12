# HL2 <-> Tang Mega 138K link ("gowinlink") — logical layer specification

Status: design specification; the RTL implements it (see section 13 for the file map).
Pin locations are provisional: `gateware/variants/hl2b5up_gowinlink/gowinlink_pins.tcl`
(HL2) and `gowin/proj/gowinlink.cst` (Gowin) are the only files that hold them.

## 0. Physical geometry (fixed by the hardware decisions)

Two DVI cables between fab-made adapter boards (LVDS drivers/receivers), one direction each,
each with its own forwarded clock. Levels at the FPGA pins are single-ended CMOS.

| Direction | Clock | Data | Slow / other |
|---|---|---|---|
| Cable 1, HL2 -> Gowin ("forward") | 76.8 MHz forwarded (HL2 `PIN_98`, Gowin `U20`) | `GL_LANES` = 6 lanes, DDR, 153.6 Mbit/s each (HL2 `PIN_72,76,77,80,83,85`) | status UART HL2 -> Gowin (`PIN_86`), aux output reserved (`PIN_87`) |
| Cable 2, Gowin -> HL2 ("reverse") | 153.6 MHz forwarded, 90 degrees late (Gowin PLL; HL2 `PIN_88`, a dedicated clock input) | 3 lanes DDR, 307.2 Mbit/s each, `gl_rev[2:0]` (HL2 `PIN_99,100,101`) | fast serial 76.8 Mbit/s Gowin -> HL2 (`PIN_89`) carrying the command packets |

Fallback forward geometry, kept working and simulated: `GL_LANES = 3` lanes DDR at 153.6 MHz
(clock on `PIN_76`, lanes `PIN_77,83,85`).

| Forward parameter | default | fallback |
|---|---|---|
| `GL_LANES` | 6 | 3 |
| lane clock | 76.8 MHz = `clk_ad9866` | 153.6 MHz = `clk_ad9866_2x` |
| bits per lane per sample `B = 12/GL_LANES` | 2 | 4 |
| lane bit rate / unit interval | 153.6 Mbit/s / 6.51 ns | 307.2 Mbit/s / 3.255 ns |

Both directions carry 12 bits x 76.8 MSPS = 921.6 Mbit/s of payload with no framing bits;
the reverse lanes carry test patterns now and TX samples later.

* HL2 forward outputs: Cyclone IV `altddio_out` on every lane **including the clock lane**
  (fed 1/0), so clock and data edges come from identical I/O register structures
  (edge-aligned forwarded clock, no PLL phase shift). "H" bit while the clock is high.
* Gowin forward inputs: `IBUF -> IODELAY (dynamic, 256 x 12.5 ps) -> IDDR`, IDDR clocked by
  the forwarded clock directly (GCLK pin `U20`). No PLL in the forward capture: the eye is
  centred per lane by a delay sweep (section 6.2). The Gowin PLL (section 6.6) is only used
  for the reverse transmitter.
* Gowin reverse outputs: `ODDR` on the lanes clocked by the PLL 153.6 MHz output, and the
  clock lane from an `ODDR` (fed 1/0) clocked by the 90-degree shifted PLL output, so the
  clock edge lands mid-bit at the HL2.
* HL2 reverse inputs: `PIN_88 -> altpll` (normal mode, compensates the clock network so the
  I/O registers see the pin phase) `-> altddio_in` on the 3 lanes and on the fast serial
  line. No sweep; a word-alignment search absorbs skew and the H/L half-swap (section 6.5).
* The plain command UART exists as a build option (`GL_CMD_UART = 1`, HL2 `PIN_89`, Gowin
  `N15`; 115200 8N1, or open drain against the HL2 weak pull-up at 19200) for bring-up.

## 1. Lane bit mapping

Sample `s[11:0]` (two's complement from `ad9866.v`), `B = 12/LANES` bits per lane per sample.
Lane `j` carries `s[B*j+B-1 : B*j]`, **most significant first**, "H" bit (clock high) before
"L" bit (clock low) within each lane-clock cycle.

| geometry | per lane `j` | cycle 1 (H, L) | cycle 2 (H, L) |
|---|---|---|---|
| forward, 6 lanes (B = 2) | `s[2j+1 : 2j]` | `s[2j+1]`, `s[2j]` | — |
| forward fallback, 3 lanes (B = 4) | `s[4j+3 : 4j]` | `s[4j+3]`, `s[4j+2]` | `s[4j+1]`, `s[4j]` |
| reverse, 3 lanes (B = 4) | `s[4j+3 : 4j]` | `s[4j+3]`, `s[4j+2]` | `s[4j+1]`, `s[4j]` |

The **serial bit order** on a lane is `s_n[Bj+B-1], ..., s_n[Bj], s_{n+1}[Bj+B-1], ...`. All
per-lane patterns (PRBS, alignment) are defined on this serial stream, which makes them
independent of where the receiver splits it into words.

Word transfer 76.8 -> 153.6 MHz (`gowinlink_tx_lanes`): the word domain toggles `wtog` once
per sample; the lane domain registers word and `wtog` and sends the first half in the cycle
where the registered `wtog` changed, the second half in the next cycle. Correct for any phase
between the two clocks because they are related PLL outputs analysed as a 6.5 ns path.

## 2. Transmit modes (both directions; HL2 forward selected by the MODE command, Gowin reverse by the Gowin control plane)

| Mode | Code | Word stream | Scrambler |
|---|---|---|---|
| LIVE | 0 | forward: `rx_data` from `ad9866.v` (power-up default). reverse: zeros now (TX samples later) | yes, if enabled (forward only) |
| PRBS | 1 | per-lane PRBS-23 serial stream (section 3) | no |
| TOGGLE | 2 | H = 1, L = 0 on every lane (a copy of the clock lane; oscilloscope skew check) | no |
| COUNTER | 3 | 12-bit counter, +1 per sample | yes, if enabled (forward only) |
| ALIGN | 4 | per-lane 16-bit de Bruijn sequence (section 4), identical on all lanes, sample synchronous | no |

RESET (link-local command) reloads the PRBS seeds, zeroes the counter and restarts the
alignment sequence.

## 3. PRBS-23

**One independent PRBS-23 stream per lane, on the lane's serial bit stream, different seed per
lane.** Not one PRBS across the 12-bit word and not one per bit position. Reason: the checker
is self-synchronising on the serial stream, so it is indifferent to which sampled bit is "H",
to the gearbox phase and to inter-lane skew — every tap setting of the delay sweep gives a
meaningful error count for every lane at once, with no alignment needed first. A word-wide
PRBS would need alignment before any lane could be checked. Different seeds keep neighbouring
lanes uncorrelated so crosstalk is exercised.

Polynomial x^23 + x^18 + 1 (ITU-T O.150, non-inverted): `x[n] = x[n-23] ^ x[n-18]`.
Generator, two bits per cycle, history `h[22:0]` (`h[0]` newest): `b0 = h[22]^h[17]` (H),
`b1 = h[21]^h[16]` (L), `h <= {h[20:0], b0, b1}`.
Seeds lane 0..5: `0x6B8B45, 0x327B23, 0x643C98, 0x66334A, 0x74B0DC, 0x19495C`.

Checker (per lane, self-synchronising): the same history built from received bits,
`err0 = rx0 ^ (h[22]^h[17])`, `err1 = rx1 ^ (h[21]^h[16])`. One channel bit error gives **3**
mismatches (itself, then at taps 18 and 23): BER = mismatches / 3 / bits. Consoles and status
frames report raw mismatch counts.

## 4. Alignment sequence (mode ALIGN)

Every lane sends the 16-bit de Bruijn sequence B(2,4), first-to-last:
`D = 0000 1001 1010 1111` (`d0` first; as a Verilog constant with `d_k` at bit k: `16'hF590`).
All 16 rotations are distinct and every 4-bit window is unique. Bit `d0` is the first bit of a
sample, so sample boundaries are at indices that are multiples of B.

## 5. Scrambler (forward LIVE and COUNTER only, default off, switched on both sides together)

Self-synchronising x^43 + 1 on the 12-bit word stream. Serial index of bit `i` of word `n` is
`12n + i`; `y[k] = x[k] ^ y[k-43]`. As 43 = 3 x 12 + 7, bit `i` of the feedback is bit `i-7` of
output word `n-3` for `i >= 7`, else bit `i+5` of word `n-4` (4 words of history). Descrambler
identical with the received words as history; synchronises after 4 words; one channel error
becomes two output errors. Purpose: spread the spectrum of near-static ADC data next to an HF
receiver, not DC balance.

## 6. Receivers, training and lock

### 6.1 Data plane (`gl_rx_datapath`, used on both boards)

Per lane: the IDDR pair `{Q0 (rising), Q1 (preceding falling = older)}` enters a 16-bit history
`hist[15:0]` (`hist[0]` newest): `hist <= {hist[13:0], Q1, Q0}`. `pair_swap` exchanges the two
if the silicon delivers them the other way round. A free-running word tick (every B/2 cycles)
extracts, per lane, `hist[off_j + B-1 : off_j]` (oldest first = MSB) into `s[Bj+B-1 : Bj]`.
`off_j` (0..12) absorbs the gearbox phase, the H/L half-swap and inter-lane skew of up to
+/- one sample. Then descrambler -> `sample[11:0]`, `sample_valid`. The PRBS checkers work on
the raw pairs and need no alignment.

### 6.2 Forward delay sweep (Gowin, mode PRBS on the HL2)

```
for tap in 0..255:
    all lanes' IODELAY = tap; wait 40 cycles; clear counters; count 2^SWEEP_LEN_LOG2 words (4096)
    per lane: error-free = (mismatches == 0); track the current and the longest error-free run
per lane: longest run < MIN_EYE (16 taps = 0.2 ns) -> FAIL 1; else tap = run start + run length / 2
```
Only start/length of the longest run are stored. IODELAY range 250 ps + 12.5 ps x 255 = 3.4 ns
typical is about half a UI for the 6-lane geometry (at least one eye edge is inside the range,
or the whole range is error free and the middle is >= 1.7 ns from any edge) and one UI for the
3-lane fallback. If no lane shows an eye, `pair_swap` is toggled once and the sweep repeated.
Time: 256 x (40 + 4096) cycles = 13.8 ms at 76.8 MHz.

### 6.3 Word alignment (both boards, mode ALIGN on the transmitter)

At each tick `t` the candidate phase `c_t = t (B+1) mod 16` is compared with every lane's
16-bit history (exact match); a matching lane records `p_j = t mod 16`. After all lanes matched
(timeout 128 ticks -> FAIL 1): `off_0 = (p_0 + 1) mod B`, `d_j = (p_j - p_0) mod 16` as a signed
value in [-8, 8), `off_j = off_0 + d_j`; if any `off_j < 0` add B to all; any `off_j > 16 - B`
-> FAIL 2 (skew too large). Then a verification pass: after the first 4 bits identify the
phase, every lane's group must equal the expected bits of D for 2^VERIFY_LEN_LOG2 words, else
FAIL 4.

### 6.4 Forward training sequence and states (Gowin `gl_train`)

MODE=PRBS -> sweep -> taps set -> MODE=ALIGN -> alignment -> verification -> MODE=PRBS,
LOCKED, PRBS accumulators cleared and enabled. Automatic at power-up (250 ms) once the
command channel is up (section 6.5), and on 't'. States: 0 NOCLK (no forward clock activity
for 1 ms), 1 IDLE, 2 SWEEP, 3 ALIGN, 4 LOCKED, 5 FAIL (reason 1 no eye, 2 no alignment phase
(also 1 from the search), 3 offsets out of range, 4 verification errors).

### 6.5 Reverse link bootstrap (HL2 `gowinlink_rev_train`, Gowin `gl_train`)

The command channel rides on the reverse cable, so the reverse link locks without commands:

* Gowin: the reverse transmitter sends ALIGN until the status frame reports the HL2 reverse
  receiver locked (`rev_state = 2`); then it switches to the wanted mode (PRBS by default)
  and sends REV_MODE so the HL2 enables the matching accumulator.
* HL2: once the reverse PLL is locked, run alignment (retry once with `pair_swap`
  toggled), then verification; success -> `rev_state = 2`; failure -> `rev_state = 3`,
  retry every 10 ms. REV_TRAIN step 1 restarts it.
* The fast serial line is sampled by the same DDR front end; its bit (one per word,
  transitions at word boundaries) is taken B/2 positions after lane 0's word start, i.e.
  mid-bit, once lane 0's offset is known. Before alignment offset 0 is used, which works
  for small skews; the HL2 only needs it after alignment anyway.

### 6.6 Clocks and the Gowin PLL

Gowin PLL (`gl_pll`): input the forward clock (76.8 MHz; 153.6 MHz in the fallback),
VCO 1228.8 MHz (IDIV 1, FBDIV 1, MDIV 16 / 8), CLKOUT0 = 76.8 MHz (reverse word clock),
CLKOUT1 = 153.6 MHz (lane clock), CLKOUT2 = 153.6 MHz shifted +90 degrees
(`CLKOUT2_PE_COARSE = 2`: two VCO periods = 1.628 ns; **to be confirmed on hardware with a
scope**). HL2 PLL (`gowinlink_rxpll`): 153.6 MHz x1, normal mode, static phase parameter
`PHASE_PS` (default 0) as a trim knob. Forward capture uses the raw forwarded clock.

## 7. Command channel (Gowin -> HL2)

Default: one fast-serial packet (section 9) of type `0x01` per command, payload
`ADDR, D[31:24], D[23:16], D[15:8], D[7:0]` (several commands may share one packet, 5 bytes each).
Bring-up option (`CMD_UART = 1`): 7-byte UART frames `0xA5, ADDR, D[31:24..7:0], CRC-8`
(poly 0x07, init 0, over ADDR..D[7:0]); CRC failure or a gap of 4 byte-times discards the frame.

### 7.1 openHPSDR commands, `ADDR[7:6] = 00`

`ADDR[5:0]` = C&C address (Ethernet C0 bits 6:1), `D` = C1..C4 (C1 most significant) — the
same words the Ethernet path produces. Issued on the internal bus with `cmd_resprqst = 0`,
`cmd_is_alt = 0`. Arbitration: section 8.

### 7.2 Link-local commands, `ADDR[7:6] = 11` (consumed by the HL2 link module)

| ADDR | Name | Data |
|---|---|---|
| 0xC0 | MODE | `D[3:0]` forward mode 0..4 (section 2) |
| 0xC1 | SCRAMBLER | `D[0]` |
| 0xC2 | STATUS_PERIOD | `D[7:0]` x 10 ms, 0 = off, default 10 |
| 0xC3 | RESET | pattern generators reset |
| 0xC4 | PTT | `D[0]` -> `link_ptt` output (reserved, not connected to the radio) |
| 0xC5 | REV_MODE | `D[2:0]` mode the Gowin's reverse transmitter is in: selects the HL2 accumulator (PRBS mismatches or counter word errors) and clears it |
| 0xC6 | REV_TRAIN | `D[3:0]` = 1 restart reverse alignment; `D[15:8]` nonce echoed in the status frame |
| 0xCF | ECHO | `D[7:0]` echoed in the status frame |

Other addresses are accepted and ignored.

## 8. Command bus arbitration on the HL2 (`gowinlink_cmd_mux`, in `clk_ad9866`)

The internal bus (`cmd_addr[5:0]`, `cmd_data[31:0]`, `cmd_cnt` toggle, `cmd_resprqst`,
`cmd_is_alt`) is produced by `hl2link_app` (HL2LINK = 1) or wired from `dsopenhpsdr1`;
consumers derive their request pulse from `cmd_cnt` with `sync_pulse` and sample the data a
few cycles later. `hermeslite_core.v` now names that producer `eth_cmd_*` and, with
`GOWINLINK = 1`, inserts the arbiter in front of the consumers:

* Ethernet-originated commands are re-issued on the next cycle, unconditionally: never
  delayed, queued, dropped or reordered.
* Link-originated commands enter a 16-entry FIFO and one is issued only when there is no
  Ethernet toggle in that cycle and at least `CMD_GAP_CYCLES` = 512 cycles (6.7 us) have
  passed since the last issue of either source. 6.7 us exceeds the 4.1 us spacing of the two
  C&C frames of one openHPSDR UDP packet at 1 Gb/s, so a link command never lands between them.
* Residual hazard: an Ethernet C&C toggle arriving within about one `clk_ctrl` period (400 ns)
  after a link issue could merge with it in the 2.5 MHz consumers' 2-flop `sync_pulse`.
  Probability per link command while streaming at 1 Gb/s ~ 400 ns / 2.6 ms = 1.5e-4, and
  openHPSDR re-sends every register in later frames, so the effect is a delayed update.
  Removing it would mean delaying Ethernet commands, which is excluded.
* FIFO full: the link frame is dropped and counted (`cmd_drop`).

## 9. Fast serial channel (`gl_fastserial_tx/rx`, one bit per word tick = 76.8 Mbit/s)

Line idle 1. Packet: start bit 0, sync `0x5C`, `len[7:0]`, `len[15:8]`, `len` payload bytes,
CRC-16 (CCITT, poly 0x1021, init 0xFFFF, bit-serial over the len and payload bits in
transmission order, sent MSB first), stop bit 1, >= 4 idle bits. Bytes LSB first. Max length
511 bytes. Byte FIFO on each end: the TX takes bytes with a "last" flag and sends a packet
when complete (up to 15 queued); the RX writes tentatively and commits only after a good
CRC and stop bit (a corrupted packet is rolled back and counted, possibly more than once as
the receiver re-hunts). Packet types (payload byte 0): `0x01` commands, `0x02` test packet
(the Gowin sends one 16-byte test packet every 10 ms so the channel is counted; the HL2 reports
`fs_ok` / `fs_err`). The HL2 -> Gowin direction has no fast serial line (aux `PIN_87` is
reserved; the modules are reusable if it is added).

## 10. Status channel (HL2 -> Gowin UART, `PIN_86`, 115200 8N1)

Every STATUS_PERIOD (100 ms): `0x5A`, 32 payload bytes, CRC-8(payload). Before latching the
payload the frame builder takes a snapshot of the reverse-link accumulators (toggle
handshake into the reverse clock domain) so multi-byte values are consistent.

| Byte | Content |
|---|---|
| 1 | `{run, tx_on, cw_on, ptt, key, scrambler_on, link_ptt, rev_pll_locked}` |
| 2 | `{0, rev_mode[2:0], 0, fwd_mode[2:0]}` |
| 3-4 | clip count since the last frame (samples at +2047 / -2048, saturating) |
| 5-6, 7-8, 9-10, 11-12 | temperature, forward power, reverse power, bias (12-bit from `control.v`; double registered and accepted only when two samples 32 cycles apart agree) |
| 13, 14 | `cmd_ok` (accepted command bodies), `cmd_err` (UART CRC/timeouts, or fast serial packet errors) |
| 15, 16 | echo, frame sequence |
| 17 | `{rev_state[3:0], rev_fail[3:0]}` (0 no PLL lock, 1 aligning, 2 locked, 3 failed/retrying; fail 1 no phase, 2 offsets, 4 verification) |
| 18 | REV_TRAIN nonce |
| 19 | `{rev_pair_swap, 000, rev_step[3:0]}` |
| 20, 21 | reverse offsets `{off1, off0}`, `{0, off2}` |
| 22-27 | reverse PRBS mismatches lanes 0, 1, 2 (32-bit accumulators saturated to 16 bits) |
| 28-29 | reverse counter-mode word errors (saturated) |
| 30, 31, 32 | fast serial packets ok, packets bad, command FIFO drops (low bytes) |
| 34 | CRC-8 over bytes 1..32 |

## 11. Debug console (Gowin, BL616 USB-UART, 115200 8N1)

Help line at power-up and on 'h'; one status line per second, hexadecimal fields
(`gowin/tools/gen_console_fmt.py` defines the layout):

```
GL st=4 fail=0 mode=1 scr=0 clk=1 pll=1 swap=0 rev=1 st=1 tap=.. eye=.. off=.. err=.. words=.. werr=.. sf=.. se=.. tx=.. hl2: fl=.. md=.. clip=.. t=.. f=.. r=.. b=.. ok=.. er=.. ec=.. sq=.. rst=.. rn=.. rsw=.. roff=.. re=..,..,.. rw=.. fs=..,..,..
```
`st` link state, `fail` reason, `mode` HL2 forward mode, `scr` scrambler, `clk` forward clock
present, `pll` Gowin PLL lock, `swap` pair swap, `rev` HL2 reports reverse locked, second `st`
= status frames arriving; `tap`/`eye` (taps)/`off` per forward lane; `err` PRBS mismatches per
forward lane, `words` since reset, `werr` counter-mode word errors, `sf`/`se` status frames
good/bad, `tx` fast serial packets sent; then the HL2 status frame fields (section 10).

Commands: `t` train, `p` PRBS, `l` live, `c` counter, `o` toggle, `s` scrambler on/off,
`r` reset counters (both boards), `x` send test command (address 0x01, data 0x00ABCDEF),
`h` help. Mode commands act on both directions. Key 0 on the dock also triggers 't'.
LEDs (PMOD LED module): heartbeat, forward locked, reverse locked, forward clock present.

## 12. Simulation (Icarus, `gowin/sim/run_sim.sh`)

* `tb_uart`: UART pair, CRC-8 framer/parser (good, corrupt, resync), fast serial link
  (good packets, corrupted packet rejected with FIFO rolled back, recovery).
* `tb_rev`: reverse chain (PLL model, serialiser, ODDR, skewed cable, altddio_in model,
  data plane): alignment, verification, PRBS, counter mode.
* `tb_link` (LANES 6 and 3): both boards with cable models (per-lane skew up to +/-1.5 ns,
  bit-error injection), driven through the debug console: reverse bootstrap, automatic forward
  training, PRBS both ways (zero errors; injected errors counted on the right lane only; reset),
  test command through the arbiter, Ethernet command scoreboard (in order, none lost), live
  ADC samples bit-exact with and without scrambling, counter mode both ways, fast serial and
  status frames error free. Prints PASS/FAIL.
* Vendor primitives: Gowin `simlib/gw5a/prim_sim.v` (IBUF/OBUF/IODELAY/IDDR/ODDR/GSR);
  Altera `altddio_out`, `altddio_in`, `altpll` and the Gowin `PLL` replaced by behavioural
  models under `ifdef SIM` inside their wrappers.

## 13. File map

| Where | What |
|---|---|
| `gateware/rtl/gowinlink/` | shared RTL: UART rx/tx, CRC-8, PRBS-23, scrambler, lane serialiser, DDR in/out wrappers, `gl_rx_datapath` (data plane), `gl_fastserial_tx/rx`, `gl_cdc`; HL2-only: `gowinlink_hl2` (top), `gowinlink_cmd_mux`, `gowinlink_cmd_rx`, `gowinlink_fs_cmd`, `gowinlink_status_tx`, `gowinlink_rev_train`, `gowinlink_rxpll` |
| `gateware/variants/hl2b5up_gowinlink/` | Quartus variant: `hermeslite.v`, `hermeslite.qsf`, `gowinlink_pins.tcl` (pins), `gowinlink_files.tcl`, `timing_gowinlink.sdc` |
| `gateware/rtl/hermeslite_core.v` | parameters `GOWINLINK`, `GL_LANES`, `GL_CMD_UART`; arbiter insertion; link instance |
| `gowin/rtl/` | Gowin-only RTL: `gl_top` (+ `gl_top_l3`), `gl_lane_rx`, `gl_pll`, `gl_train`, `gl_console` (+ generated `.vh`), `gl_cmd_fs`, `gl_cmd_tx`, `gl_status_rx` |
| `gowin/proj/` | `build.tcl` (gw_sh), `gowinlink.cst` / `.sdc` and the `_l3` fallback pair |
| `gowin/sim/` | testbenches and `run_sim.sh` |
