# Protocol specification for client builders

This is everything a client needs to drive the `hl2b5up_raw` image: find the radio, stream raw ADC samples,
send transmit samples, read and write every radio function, and handle the transmit interlock. It is
written against the gateware in this branch (`gateware/rtl`) and was checked on the radio with the
reference tools (`software/`, see [TOOLS.md](TOOLS.md)).

> **Transmit safety.** Parts of this protocol can key the transmitter. Transmit on real RF has never been
> tested with this image. Read [SAFETY.md](SAFETY.md) before you write code that sets the key bit.

Contents:

1. [Ports and conventions](#1-ports-and-conventions)
2. [Discovery](#2-discovery)
3. [Register write (port 1025)](#3-register-write-port-1025)
4. [Start and stop (port 1024)](#4-start-and-stop-port-1024)
5. [Raw sample frames (radio to client)](#5-raw-sample-frames-radio-to-client)
6. [TX sample frames (client to radio), duplex pacing, real DAC and echo](#6-tx-sample-frames-client-to-radio)
7. [Aux byte channel](#7-aux-byte-channel)
8. [Register bridge (Etherbone) and the full register map](#8-register-bridge-etherbone)
9. [Transmit interlock: permission, cut-offs, trips, clearing](#9-transmit-interlock)
10. [Message layer (firmware)](#10-message-layer-firmware)
11. [Console and gdb datagrams](#11-console-and-gdb-datagrams)
12. [Command register summary](#12-command-register-summary)

---

## 1. Ports and conventions

| UDP port on the radio | Direction | Used for | Handled by |
|---|---|---|---|
| 1024 | both | discovery, start/stop, network flashing; raw sample frames come **from** this port | gateware |
| 1025 | both | discovery, command register writes (openHPSDR "EF FE 05" format) | gateware |
| 1026 | client to radio | TX sample frames | gateware |
| 1027 | both | aux channel, register bridge, console, gdb, message layer | gateware (aux, bridge), boot ROM (console, gdb), firmware (messages) |

- Multi-byte fields are **big-endian**, except the message layer and the console/gdb control datagrams,
  which are little-endian (RISC-V native).
- The radio checks **no** Ethernet CRC, IP checksum or UDP checksum on receive. A corrupted frame is used
  as it arrives. Keep the link short and point-to-point (see [SAFETY.md](SAFETY.md)).
- The radio accepts UDP datagrams of any length up to a 16-bit IP length (jumbo frames). Stock HL2
  gateware cut received datagrams at 2,047 bytes; this image does not.
- IP address: DHCP if a server answers, otherwise a 169.254.x.x link-local address after about 15 s, or a
  static address stored in the configuration EEPROM. A direct cable to a PC without DHCP works.

## 2. Discovery

Send 60 bytes `EF FE 02` + 57 zero bytes to port 1025 (or 1024), broadcast or unicast. The radio answers
with a 60-byte datagram:

| Byte | Content |
|---|---|
| 0-1 | `EF FE` |
| 2 | 2 = stopped, 3 = running (streaming) |
| 3-8 | MAC address |
| 0x09 | gateware major version (74) |
| 0x0C | **image marker: 0xD1 for this image** (0 in stock and factory images) |
| 0x13 | receiver count: **0 in this image** (stock images report 4) |
| 0x14 | [5:0] board ID (5) |
| 0x15 | gateware minor version (2) |

The gateware version is the same 74.2 as the stock image this work started from, so tell images apart by
the marker and the receiver count. A radio that answers with marker 0 and 4 receivers after a flash is
running its factory image ([RECOVERY.md](RECOVERY.md)).

## 3. Register write (port 1025)

60 bytes:

```
EF FE 05 7F  AA  D3 D2 D1 D0  + 51 x 00
```

- `AA` = register address x 2 (bit 0 is the openHPSDR MOX bit; send 0).
- `D3..D0` = 32-bit value, big-endian.
- The radio answers the sending socket with a 60-byte `EF FE` datagram (as the stock HL2).

The same writes can be made through the register bridge (CMD_DATA / CMD_ADDR, section 8.3) or the message
layer (CMD request, section 10). All three end on the same internal command bus. The registers that matter
in this image are listed in [section 12](#12-command-register-summary).

## 4. Start and stop (port 1024)

64 bytes, sent **from the socket that will receive the stream**:

| Action | Datagram |
|---|---|
| Start | `EF FE 04 81` + 60 x 00 (bit 0 run, bit 7 openHPSDR watchdog off) |
| Stop | `EF FE 04 00` + 60 x 00 |

- The stream goes to the IP address, MAC address and UDP port that sent the last port-1024 datagram while
  the radio was stopped: the start datagram's socket. Open that socket first. If the radio receives an
  ICMP "port unreachable" for the stream, it stops (stock openHPSDR behaviour).
- Set the watchdog-off bit: the client sends nothing on port 1024 while streaming.
- Samples flow only while raw mode (register 0x30 bit 0) is on **and** the radio runs.
- Discovery replies, register write replies, aux packets and bridge replies are still sent between raw
  frames. Raw frames always have priority.
- The radio only reboots or accepts a network flash while stopped. Stop before flashing.

## 5. Raw sample frames (radio to client)

### 5.1 Register 0x30: raw mode, frame size, test pattern, quiet capture

Write while stopped (a change while streaming takes effect at the next frame).

| Bits | Meaning |
|---|---|
| 0 | Raw mode on |
| 1 | Counting test pattern instead of ADC samples |
| 2 | Quiet-capture mode (5.6) |
| 31:16 | Samples per frame N. Rounded down to even. 0 means 968. **Above 5,968 is cut to 5,968** in this image |

Examples: `0x17500001` raw on, ADC, N = 5,968 (9,000-byte IP MTU). `0x10000005` raw on, ADC, quiet capture,
N = 4,096. `0x00000000` raw off.

Choose N from the IP MTU and the header length H (20 bytes, or 48 while duplex is on):
`N = floor((MTU - 28 - H) / 3) x 2`.

| IP MTU | H = 20 | H = 48 |
|---|---|---|
| 1,500 | 968 | 948 |
| 6,192 | 4,096 | 4,076 |
| 9,000 (Windows jumbo setting "9014") | 5,968 | 5,948 |

### 5.2 Frame layout

One frame per UDP datagram, source port 1024. UDP payload = H + 3N/2.

| Bytes | Field |
|---|---|
| 0 | Magic 0xA5 |
| 1 | Header version: 0x01 (20-byte header, duplex off) or 0x03 (48-byte header, duplex on) |
| 2 | Flags (5.3) |
| 3 | Transmit-safety byte (5.4) |
| 4-7 | Frame sequence number, 0 at start |
| 8-13 | Index of the first sample in this frame, 48-bit, counts every ADC clock since start |
| 14-15 | N, samples in this frame |
| 16-17 | FIFO overflow events since start (stops at 65,535) |
| 18-19 | Highest raw FIFO fill since start, samples (FIFO depth 8,192) |
| 20-39 | Version 3 only: TX sink status (6.3) |
| 40-47 | Version 3 only: echo and interlock status (6.5) |
| H... | Samples |

**Sample packing**: 12-bit two's complement. Every two samples a, b take three bytes:
`a[11:4]`, `{a[3:0], b[11:8]}`, `b[7:0]`.

**Sample index**: within an unbroken run, index(next frame) = index(this frame) + N. After a gap the index
jumps by exactly the number of samples missed, so lost samples can be counted exactly and a long run gives
the ADC clock rate against the client's clock.

### 5.3 Flags (byte 2)

| Bit | Meaning |
|---|---|
| 0 | Test pattern selected |
| 1 | A FIFO overflow happened since start (sticky) |
| 2 | A sample in the **previous** frame was at full scale (0x7FF or 0x800). Fires regularly with the test pattern |
| 3 | Quiet-capture block |
| 4 | First frame after start |
| 5 | Samples are missing between the previous frame and this one |

### 5.4 Transmit-safety byte (byte 3)

Copied from the interlock logic into every frame, so the client sees a change within one frame
(about 78 µs at N = 5,968) with no CPU involved. Also readable at bridge address 0x4000_7000.

| Bit | Meaning |
|---|---|
| 0 | Transmit off: no interlock output is on |
| 1 | A PA supply, bias or T/R relay pin is driven |
| 2 | Transmit requested (permission lease valid and keyed) |
| 3 | PTT input (key jack ring) closed, debounced |
| 4 | Key input (key jack tip) closed, debounced |
| 5 | TX inhibit input (CN8) active, debounced |
| 6 | Over-temperature cut-off present |
| 7 | An interlock trip is latched |

Idle value: 0x01. Byte 3 was 0 in the first raw-stream test images ([HISTORY.md](HISTORY.md)).

### 5.5 Test pattern

Sample k of a frame whose first index is I equals `(I + k) mod 4096`. A receiver checks every sample against
the frame's own header, across frame boundaries and gaps, without carrying state.

### 5.6 Overflow and quiet capture

- **Overflow.** The raw FIFO never drops single samples. When full, writing stops and the index keeps
  counting; complete frames still in the FIFO are sent, the rest is discarded, writing restarts. The next
  frame has flag 5 set, flag 1 stays set, the overflow count goes up by one. With N at or above about 750
  the link carries the full rate; smaller N overflows continuously.
- **Quiet capture (bit 2).** The radio sends nothing while its FIFO fills with 8,192 contiguous samples,
  then pauses writing, sends that block in frames of N samples (flag 3), and starts the next block. Samples
  of a block are taken while the Ethernet sender is idle, which is what the noise test compares against.
  Use an N that divides 8,192 (4,096 with jumbo frames, 512 at 1,500 bytes) so no sample of a block is
  discarded. The first frame of each later block also has flag 5.

### 5.7 Rates

Each frame costs its length plus about 26 bytes of line time (preamble, gap, hand-over).

| N | Frames/s | Wire rate |
|---|---|---|
| 968 | 79,339 | 980 Mbit/s |
| 4,096 | 18,750 | 936 Mbit/s |
| 5,968 | 12,869 | 931 Mbit/s |

The payload is always 115.2 MB/s (921.6 Mbit/s). A PC must receive 12,900 datagrams a second without loss;
see [TOOLCHAIN.md](TOOLCHAIN.md#8-network-card-setup) for the network card settings that made that work.

## 6. TX sample frames (client to radio)

### 6.1 Register 0x31: duplex, real DAC, echo

| Bit | Meaning |
|---|---|
| 0 | Duplex: accept TX frames on port 1026 and send version 3 (48-byte) raw frame headers |
| 1 | Real DAC: played TX samples drive the AD9866 transmit DAC, **only while the interlock has the PA stage on** |
| 2 | Echo: played TX samples replace the ADC samples in the raw stream; the DAC is never driven (bit 1 ignored) |

The TX sink runs only while duplex is on **and** raw streaming runs. Every TX counter restarts at 0 when it
becomes active. Without bit 1 or 2 the samples go to a virtual DAC (a register clocked once per sample) that
checks the counter pattern.

`0x00000001` duplex, virtual DAC. `0x00000005` echo. `0x00000003` duplex with the real DAC (can transmit).

### 6.2 TX frame (to port 1026)

| Bytes | Field |
|---|---|
| 0 | Magic 0x5A |
| 1 | Version 0x01 |
| 2 | Flags (bit 0: counter pattern; ignored by the radio) |
| 3 | 0 |
| 4-7 | Sequence number, +1 per frame |
| 8-13 | Index of the first sample, 48-bit. Used for echo: the TX index of sample k is this index + k. Send a continuous count (+N per frame) |
| 14-15 | Samples in the frame (ignored: the radio takes every complete sample in the payload) |
| 16... | Samples, packed as in raw frames |

UDP payload = 16 + 3N/2. N = 5,970 fits a 9,000-byte IP MTU; N = 970 fits 1,500. Frames with a wrong magic
or version are ignored.

Radio side: a 16,384-sample FIFO written by the network receive path. The DAC side waits until the FIFO
holds 8,192 samples, then plays exactly one sample per AD9866 clock (76.8 MSPS). A sample due while the
FIFO is empty is one **underflow**, after which it waits for 8,192 again. A sample arriving at a full FIFO
is dropped (one **overflow** event per frame that lost samples). Sequence gaps count as **lost** frames.
With the counter pattern, mismatches count as **bad** samples.

### 6.3 TX status in version 3 headers, bytes 20-39

| Bytes | Field |
|---|---|
| 20-23 | TX frames received (valid magic and version) |
| 24-27 | TX frames lost (sequence gaps) |
| 28-31 | TX bad samples (virtual DAC pattern check) |
| 32-33 | TX FIFO fill, samples (0-16,384) |
| 34-35 | TX underflow events |
| 36-37 | TX overflow events |
| 38 | [0] TX sink active [1] DAC playing [2] real DAC mode [3] echo mode |
| 39 | 0 |

Values are at most one frame period old. Counters stop at their maximum.

### 6.4 Duplex pacing

The radio's ADC clock and the client's clock differ by a few ppm, and the radio plays at its own clock. The
client must send at the radio's rate: read the TX FIFO fill (bytes 32-33) from every raw frame and trim the
send rate to hold it near a target. `rawcap` uses a PI controller around 76.8 MSPS with a target of 12,000
samples. Half the FIFO is 8,192 samples, only about 0.1 ms of play time, so the pacing must be tight. Send in an even flow: a PC card
that sends in bursts causes overflows and underflows even when the average rate is right (see
[RESULTS.md](RESULTS.md)).

### 6.5 Echo and interlock status in version 3 headers, bytes 40-47

| Bytes | Field |
|---|---|
| 40-45 | Echo offset: TX sample index minus RX sample index of the echoed samples, 48-bit two's complement |
| 46 | [0] offset valid [1] echo on [2] real DAC mode [3] DAC driven [4] trip latched [5] lease valid [6] transmit on |
| 47 | Latched trip reasons (ILK_STATUS [13:8], section 9.3) |

**Echo mode.** Sample k of a frame with first index I carries the TX sample whose TX index is I + k + offset. A TX
sample's index is the index in its TX frame header plus its position in that frame. While nothing plays (the
FIFO refilling after an underflow) the echoed samples are 0. The offset in a header is taken from the newest sample written, so a frame built just after a
change can carry the new offset for older samples: check against the previous frame's offset too. Echo is
a full-rate bandwidth and latency test of both directions that needs no RF.

## 7. Aux byte channel

A two-way byte channel in its own UDP packets on port 1027, sent by the radio only in the gaps between raw
frames and never larger than the gap. The radio's side is a test generator and checker: it checks and
optionally echoes the client's bytes and can send its own counter stream. It measures what the link
carries beside the sample stream; it is not a general data path to the CPU.

### 7.1 Register 0x32

| Bits | Meaning |
|---|---|
| 0 | Aux on |
| 1 | Echo the client's bytes |
| 2 | Radio counter stream on |
| 31:16 | Counter stream rate, bytes per millisecond (1 Mbit/s = 125) |

Counters restart when bit 0 goes from 0 to 1. The radio sends aux packets to the address and port of the
last datagram received on port 1027, so the client sends a hello packet first.

### 7.2 Client to radio (port 1027)

| Bytes | Field |
|---|---|
| 0 | Magic 0x5B |
| 1 | Version 0x01 |
| 2 | Flags: bit 0 hello (no payload, not counted) |
| 3 | 0 |
| 4-7 | Sequence number |
| 8-11 | Offset of the first payload byte in the client's aux byte stream |
| 12-13 | Payload length L |
| 14-15 | 0 |
| 16... | L payload bytes |

Byte pattern (both directions): the byte at stream offset o is byte (o mod 4) of the big-endian 32-bit word
floor(o / 4). Any 8 consecutive bytes give their own offset.

### 7.3 Radio to client (from port 1027), 44-byte header

| Bytes | Field |
|---|---|
| 0 | Magic 0xB5 |
| 1 | Version 0x01 |
| 2 | Flags: [0] aux on [1] echo [2] counter stream [3] raw stream running |
| 3 | 0 |
| 4-7 | Sequence number |
| 8-11 | Echo offset (echo bytes sent before this packet) |
| 12-13 | Echo bytes in this packet, E |
| 14-17 | Counter stream offset of the first counter byte |
| 18-19 | Counter bytes in this packet, C |
| 20-23 | Client packets received |
| 24-27 | Client packets lost |
| 28-31 | Client bad payload bytes |
| 32-35 | Client payload bytes received |
| 36-37 | Echo FIFO overflow events |
| 38-39 | Echo FIFO fill, bytes (FIFO 1,024 bytes in this image) |
| 40-41 | Wait of this packet's bytes for a send slot, µs |
| 42-43 | Starved packets (bytes waited 10 ms or more) |
| 44... | E echo bytes, then C counter bytes |

UDP payload at most 1,400 bytes. Beside a full-rate stream at N = 5,968 the radio can send about 50 Mbit/s
of aux payload.

## 8. Register bridge (Etherbone)

A register and memory bridge in logic on port 1027. It works with the CPU running, halted, held in reset or
crashed, with the radio stopped or streaming, and needs no firmware.

### 8.1 Packet format

The Etherbone subset used by LiteX/LiteEth (LiteX tools were not tried against it). Big-endian.

| Bytes | Field |
|---|---|
| 0-1 | Magic 0x4E 0x6F |
| 2 | [7:4] version 1; [0] probe request (reply sets [1]: 0x12) |
| 3 | 0x44 (32-bit addresses and data) |
| 4-7 | 0 |
| 8 | Record flags (ignored) |
| 9 | Byte enable 0x0F |
| 10 | Write count W (0-64) |
| 11 | Read count R (0-64) |
| ... | If W > 0: base write address, then W values for consecutive words |
| ... | If R > 0: base return address, then R read addresses |

- One record per packet. Writes are done before reads: one packet can write and read back.
- A reply is sent only when R > 0: packet header (byte 2 = 0x10), record header with W = R and R = 0, the
  base return address, then R values (16 + 4R bytes). Write-only packets get no reply, so write with a
  read-back in the same packet when delivery matters.
- Addresses are byte addresses; registers are on multiples of 4.
- Unmapped addresses read 0xFFFF_FFFF; writes to read-only or unmapped addresses are refused. Both count as
  bus errors. Packets with a wrong magic or version, W or R above 64, shorter than their counts, longer than
  512 bytes, or arriving while the previous request is still being handled are dropped without a reply.
- Replies go to the address and port of the last datagram received on port 1027 (shared with the aux
  channel, console, gdb and messages): use one tool at a time.
- Reads are idempotent: retry on timeout. The layer has no sequence numbers.

### 8.2 Status block, 0x4000_0000 (also read-only from the CPU)

| Address | Access | Contents |
|---|---|---|
| 0x4000_0000 | R | ID 0x484C_3242 ("HL2B") |
| 0x4000_0004 | R | Gateware major, minor, image marker, map version: 0x4A02_D101 |
| 0x4000_0008 | RW | Scratch (0x1234_5678 after power-up) |
| 0x4000_000C | R | Capabilities: [0] receivers [1] transmitter [2] raw stream [3] duplex [4] aux [5] CPU [6] front-end register block. This image: 0x7C |
| 0x4000_0010 | R | Bridge requests handled |
| 0x4000_0014 | R | Bridge requests dropped |
| 0x4000_0018 | R | Bridge bus errors |
| 0x4000_2000 | RW | RX gain: write [6:0] = command 0x0A value (0x40 + dB + 12). Read [6:0] last 0x0A value seen on the command bus, [8] one was seen, [31] bridge write pending |
| 0x4000_3000 | R | Temperature, 12-bit slow ADC code: degC = (3.26 x code / 4096 - 0.5) / 0.01 |
| 0x4000_3004 | R | Forward power code (uncalibrated) |
| 0x4000_3008 | R | Reverse power code (uncalibrated) |
| 0x4000_300C | R | PA bias current code: A = (3.26 x code / 4096) / 50 / 0.04 |
| 0x4000_4000 | R | Inputs: [0] key [1] PTT [2] TX inhibit [3] over-temperature [4] transmit on |
| 0x4000_7000 | R | Transmit-safety byte (5.4) |

The HL2's slow ADC has these four channels only: there is no supply-voltage measurement.

### 8.3 Front-end register block, 0x4004_0000

Reachable from the bridge and the CPU. Keys guard every write that changes transmit behaviour.

| Offset | Access | Name | Contents |
|---|---|---|---|
| 0x00 | R | ID | 0x494F_3031 ("IO01") |
| 0x04 | RW | TX_PERMIT | Write 0x5458_000x renews the transmit lease: [0] key [1] PTT input may key [2] key (tip) input may key. Other values ignored. Read [2:0] last bits |
| 0x08 | R | ILK_STATUS | Section 9.3 |
| 0x0C | W | ILK_CLEAR | 0x434C_5452 clears latched trips whose cause is gone |
| 0x10 | RW | LEASE_MS | Lease length, 10-1000 ms, default 100 |
| 0x14 | RW | MAXKEY_S | Longest key-down, 1-600 s, default 600 |
| 0x18 | RW | TEMP_LIMIT | Over-temperature cut-off, slow ADC code; default and maximum 0x527 (55 degC); higher writes read back 0x527 |
| 0x1C | R | KEYTIME | Current key-down time: [19:10] s, [9:0] ms |
| 0x20 | RW | WDOG | Write 0x5744_4F47 kicks and arms the CPU watchdog. Read [31] fired [30] armed [15:0] ms left |
| 0x24 | RW | WDOG_MS | Watchdog time, 10-60,000 ms, default 1,000 |
| 0x28 | W (bridge only) | WDOG_DISARM | [0] disarms and clears "fired" |
| 0x2C | RW | CMD_DATA | Value for the next command |
| 0x30 | RW | CMD_ADDR | Write [5:0]: puts (address, CMD_DATA) on the command bus (the same as a port-1025 write). Refused while busy (bridge: bus error). Read [31] busy [15:8] commands sent (mod 256) [5:0] last address |
| 0x34 | W | I2C_XFER | [31:30] bus 1-3, [24] read, [23] probe, [22:16] 7-bit address, [15:8] register byte, [7:0] value. Refused while busy or with bus 0 |
| 0x38 | R | I2C_STATUS | [0] busy [1] last NACK [2] last refused by the bias guard [3] last dropped (engine busy) [4] request not yet on the bus; [23:16] transfers done, [31:24] refused or dropped (mod 256) |
| 0x3C | R | I2C_RDATA | Bytes read, first byte in [7:0]; a probe's byte in [31:24] |
| 0x40 | RW | BIAS_UNLOCK | 0x4249_4153 unlocks writes to the bias pots / EEPROM (0x2C); any other value locks |
| 0x44 | RW | LED | [3:0] override D2..D5, [7:4] on |
| 0x48 | RW | FAN | [3:0] minimum duty in sixteenths (15 = on), added to the gateware fan control. Read [10:8] gateware fan state, [11] band volts on the fan pin |
| 0x4C | R | INPUTS | Pin levels [0] tip [1] ring [2] CN8 [3] CN9 [4] CN10 [5] DB1-2 [6] DB1-5 [8:7] hl2link rx [12:9] TP2 TP7 TP8 TP9; debounced active [16] key [17] PTT [18] TX inhibit |
| 0x50 | R | ADC_SEQ | Slow ADC read cycles |

**I2C.** Write: register byte + value byte. Read: register pointer written, then 4 bytes read. Probe: address
only, one byte read. A transfer counts as done when the master has released the bus; poll I2C_STATUS until
"transfers done" moves (or "refused or dropped" moves). A request while the engine is busy (a slow ADC poll
or a clock chip sequence) is dropped and counted: retry. Buses: 1 = VersaClock 5 clock chip (0x6A); 2 = N2ADR
filter board MCP23008 (0x20), PA bias pots + configuration EEPROM MCP4662 (0x2C), N2ADR Pico IO board (0x1D,
its ROM 0x41); 3 = MAX11613 slow ADC (0x34, probes only; the gateware reads it).

**Bias guard.** Writes to 0x2C, and one-byte increment or decrement commands, are refused unless BIAS_UNLOCK
holds its key. MCP4662 read commands (register byte with bits 3:2 = 11, for example 0x0C wiper 0, 0x1C
wiper 1) and probes pass. Port-1025 I2C commands (0x3C/0x3D) are guarded the same way. A wrong bias setting
can overheat the PA.

### 8.4 CPU memory map (bridge view)

The bridge also reaches the CPU system, with priority over the CPU. Details in [RISCV.md](RISCV.md).

| Address | Contents |
|---|---|
| 0x0000_0000 | RAM, 16 kB (0x800-0x3FFF for applications) |
| 0x0001_0000 | Boot ROM, 4 kB (read-only) |
| 0x2000_0000 | Packet buffer, one byte per 32-bit word |
| 0x4001_0000 | CPU system block (reset, halt, boot mode, timer, interrupts, firmware state) |
| 0x4002_0000 | Packet interface |
| 0x4003_0000 | Flash sector interface (0x1F0000-0x1FFFFF only) |

## 9. Transmit interlock

A block in logic (`gateware/rtl/hl2io.v`, `tx_interlock`) is the only driver of the PA supply, PA bias,
op-amp supply, both T/R relay outputs, and the AD9866 transmit data and enable. It runs on the 2.5 MHz
control clock and does not depend on the CPU, the firmware or the client staying alive.

### 9.1 What it takes to transmit

All of these at once:

1. **A valid lease.** Each TX_PERMIT write (0x5458_000x) renews it for LEASE_MS (default 100 ms). Renew
   every 50 ms or faster, through the bridge or the message layer's unreliable TX_PERMIT request.
2. **A key request** in the same write: bit 0 (the client keys), or bit 1 / bit 2 set and the PTT (ring) or
   key (tip) input closed.
3. **No cut-off** present (9.2) and **no trip latched** (9.3).
4. For samples on the air: duplex on, real DAC (register 0x31 = 3), TX frames flowing, and the TX gain set
   (register 0x09 [31:28]). For the PA: PA enable (register 0x09 bit 19). Register 0x09 is configuration
   only; the interlock does the keying.

**Sequence.** Key-down: T/R relays first, then 10 ms later PA supply, bias, op-amp supply and DAC. Key-up or
a cut-off: PA stage and DAC off in the same clock cycle, relays 10 ms later.

### 9.2 Cut-offs (any one blocks transmit)

| Bit (ILK_STATUS [21:16]) | Cut-off |
|---|---|
| 0 | No valid lease (normal when idle) |
| 1 | Over-temperature: slow ADC code at or above TEMP_LIMIT, or the stock fan logic's overheat state |
| 2 | TX inhibit input (CN8) active |
| 3 | CPU watchdog fired |
| 4 | Key-down time reached MAXKEY_S |
| 5 | Temperature reading stale: no slow ADC cycle for 1 s (also at power-up until the first reading) |

The CPU watchdog is armed by its first kick (from the CPU or the bridge). Firmware kicks it from its main
loop. It fires when the CPU stops: a crash, `hl2fw.py halt/rom`, **and a gdb breakpoint or Ctrl-C**. A new
kick clears "fired"; only the bridge can disarm it (WDOG_DISARM).

### 9.3 Trips and ILK_STATUS

A **trip** latches when a cut-off is present while transmit is requested, or when the lease runs out while
keyed. A normal key-up (key bit 0, then let the lease run out) is not a trip. A latched trip blocks
transmit until cleared.

ILK_STATUS (0x4004_0008):

| Bits | Meaning |
|---|---|
| 0 | Transmit on |
| 1 | PA stage and DAC on |
| 2 | Lease valid |
| 3 | Transmit requested |
| 4 | A trip is latched |
| 5 | A cut-off is present |
| 6 | Key bit of the last permission |
| 13:8 | Latched trip reasons, same bit order as 9.2 (bit 0 = lease expired while keyed) |
| 21:16 | Cut-offs now (9.2) |
| 24 / 25 / 26 | PA enable / T/R disable / VNA, from register 0x09 |

**Clearing.** Write 0x434C_5452 to ILK_CLEAR (or the message layer's CLEAR_TRIPS). It removes only reasons
whose cause is gone; a max key-down trip clears after key-up. Limits can be tightened by the client:
LEASE_MS, MAXKEY_S and TEMP_LIMIT (which can only be lowered below 55 degC).

**Reporting without the CPU:** raw frame byte 3 (5.4), version 3 header bytes 46-47 (6.5), ILK_STATUS.

## 10. Message layer (firmware)

The saved firmware (`firmware/hl2neo/msg`, version 0x0003_0001) adds reliable requests, I2C scans in one
request, telemetry and events on port 1027. Everything it does is also possible through the bridge.

### 10.1 Header (16 bytes, little-endian)

| Bytes | Field |
|---|---|
| 0-1 | "HM" |
| 2 | Protocol version 1 |
| 3 | Flags: [0] reliable [1] ack valid [2] reset (first packet of a client session) |
| 4-7 | Boot ID (new at every firmware start) |
| 8-9 | Sequence number |
| 10-11 | Ack |
| 12-13 | Payload length (at most 240) |
| 14-15 | 0 |

Payload: one or more messages of class (u8), opcode (u8), tag (u16), length (u16), body. A response has
opcode | 0x80, the same tag, and a body that starts with a status byte: 0 ok, 0x10 unknown, 0x11 bad length,
0x12 refused, 0x13 busy. Datagrams are at most 256 bytes.

### 10.2 Reliability

- A reliable request with the next sequence number is executed once. Its response packet (seq 0, ack =
  request seq) is cached and sent again, without executing anything, when the same request repeats. Any
  other sequence number gets a bare ACK.
- Unreliable requests are executed at once. Use them for the transmit permission renewal: a late renewal
  must not be delivered.
- Events travel reliably the other way: one in flight, re-sent after 50, 100, 200, 400 and 800 ms until a
  packet with ack = its seq arrives.
- Telemetry is unreliable, every 100 ms once a session exists (set the period with TELEMETRY).
- A new boot ID in any packet means the firmware restarted: start a new session (reset flag).

### 10.3 Messages

| Class / op | Request body | Response body after the status byte |
|---|---|---|
| 0 / 1 HELLO | - | protocol u8, 0 u16, gateware version u32, firmware version u32, capabilities u32, max payload u16, telemetry period u16, register block ID u32 |
| 0 / 2 PING | any | the body |
| 0 / 3 TELEMETRY | period ms u16 (0 = off) | - |
| 1 / 1 READ | address u32, count u8 (1-32) | count x u32 |
| 1 / 2 WRITE | address u32, values u32... | words written u8. Refused: firmware RAM, boot ROM, packet and flash registers |
| 2 / 1 I2C XFER | bus u8, address u8, flags u8 ([0] read [1] probe), register u8, value u8 | I2C status u8 (0 ok, 1 NACK, 2 refused by the bias guard, 3 dropped, 4 timeout), data u32 |
| 2 / 2 I2C SCAN | bus u8, first u8, last u8 | 16-byte bitmap of acknowledging addresses |
| 3 / 1 TX_PERMIT | flags u8 (TX_PERMIT bits) | ILK_STATUS u32 |
| 3 / 2 CLEAR_TRIPS | - | ILK_STATUS u32 |
| 3 / 3 BIAS_UNLOCK | 1 unlock / 0 lock | - |
| 3 / 4 CMD | address u8, value u32 | - (busy if the command bus stayed busy 50 ms) |
| 3 / 5 LIMITS | lease ms u16, max key-down s u16, temperature code u16 (0 = keep) | the three values read back |
| 5 / 1 telemetry (radio) | - | ms u32, temperature, forward, reverse, bias u16, INPUTS u32, ILK_STATUS u32, I2C_STATUS u32, FAN u32, KEYTIME u32, safety byte u8 + packet counters (u32: [7:0] safety byte, [23:8] ring drops, [31:24] datagrams sent) |
| 6 / 1 event (radio) | - | ILK_STATUS u32, INPUTS u32, ms u32; sent when the transmit state, a trip, a cut-off (not the lease) or a debounced input changes |

## 11. Console and gdb datagrams

Datagrams to port 1027 are sorted by their first byte:

| First byte | Goes to |
|---|---|
| 0x4E (Etherbone magic 0x4E 0x6F) | register bridge (logic) |
| 0x5B | aux channel (logic) |
| anything else | the CPU's receive ring: "H" to the message-layer firmware if it runs, 0x02 to the health console example if it runs, 0x01 to the boot ROM console, everything else to the boot ROM's gdb stub |

Console (boot ROM), little-endian arguments:

| Datagram | Meaning |
|---|---|
| to radio 0x01 'A' | attach the console and replay the last 256 bytes of output (also ends a gdb session) |
| to radio 0x01 'K' | keep-alive / attach without replay |
| to radio 0x01 'S' + load, length, entry, version, CRC-32 (5 x u32) | save that RAM range to the flash sector (ROM idle or stopped) |
| to radio 0x01 'E' | erase the saved firmware |
| from radio 0x01 'C' + text | console output |

gdb uses the GDB remote serial protocol over UDP to the same port (`target remote udp:<radio>:1027`,
[RISCV.md](RISCV.md#gdb)). The radio sends console output, gdb replies, bridge replies and messages to
the address and port that sent to port 1027 last.

## 12. Command register summary

Register writes through port 1025, the command injector (CMD_DATA/CMD_ADDR) or the message layer's CMD.

| Address | Bits | Function |
|---|---|---|
| 0x00 | [23:17] filter board relays (N2ADR, MCP23008 0x20), [13] RX antenna, [12] switching-supply sync clocks off, [11] band volts on the fan pin | front end configuration |
| 0x01 | frequency | band volts / band data |
| 0x09 | [31:28] TX gain (AD9866 register 0x0A), [23] VNA, [19] PA enable, [18] T/R relay disable | configuration only; the interlock keys |
| 0x0A | 0x40 + dB + 12 (-12 to +48 dB) | RX gain (AD9866 PGA) |
| 0x0E | | TX-time LNA gain |
| 0x30 | section 5.1 | raw mode, frame size, test pattern, quiet capture |
| 0x31 | section 6.1 | duplex, real DAC, echo |
| 0x32 | section 7.1 | aux channel |
| 0x39 | codes 8, 0x0A-0x0D | VersaClock 5 sequences (as stock) |
| 0x3A | [0] | reboot (radio stopped) |
| 0x3B | 0x06 << 24 \| address << 16 \| value | any AD9866 register (SPI, write only) |
| 0x3C / 0x3D | stock format | I2C bus 1 / bus 2 transfers (bias guard applies) |

Not supported in this image: the openHPSDR receivers, IQ and bandscope streams, the CW keyer and sidetone,
Hardrock-50 band data, the ICOM AH-4 tuner, EER, hl2link and the AK4951 companion board
([RESULTS.md](RESULTS.md#features-left-out)).
