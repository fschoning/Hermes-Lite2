/* SPDX-License-Identifier: Apache-2.0
 * Copyright 2026 Franz Schöning, https://www.schoning.com
 *
 * Radio health console: an example application for the NEORV32 CPU in the hl2b5up_raw image.
 *
 *  - I2C scan of the three HL2 I2C buses, naming the chips the HL2 and its usual add-ons carry
 *  - temperature, PA bias current and the forward/reverse power codes once a second
 *  - a callsign in Morse code on LED D5 (default N0CALL, set with "call" or build.py --callsign)
 *  - text commands over the network console (software/hl2console/hl2console.py)
 *
 * Every command is read-only or harmless: nothing here can request transmit, change the PA configuration,
 * the bias pots, the clock chip or the transmit interlock limits. LED D3 (the transmit indicator) is never
 * overridden. The firmware kicks the CPU watchdog from its main loop, as firmware that shares the radio
 * with a transmitting client must: if it hangs (or gdb stops it), the watchdog cuts transmit.
 *
 * Datagrams: the application reads the receive ring itself, with interrupts off. A datagram whose first byte
 * is 0x02 is a command line for this console. Console attach (0x01 'A') and keep-alive (0x01 'K') are handled
 * here the way the boot ROM handles them. Anything else (gdb, save and erase requests) is handed to the boot
 * ROM, as the message-layer firmware does (msg/main.c): interrupts on, the ROM reads the ring in its packet
 * interrupt, then the application takes the ring back. Output goes through the boot ROM console (0x01 'C'
 * datagrams to the PC that sent to port 1027 last), so hl2fw.py console, hl2console.py and gdb all see it.
 *
 * Build: python firmware/hl2neo/build.py [--callsign CALL]  ->  firmware/hl2neo/build/health.elf
 * Run:   hl2fw.py --ip RADIO run firmware/hl2neo/build/health.elf, then hl2console.py --ip RADIO
 * Docs:  docs/rawfront/RISCV.md, section "Example: radio health console".
 */

#include "hl2cpu.h"
#include "hl2io.h"
#include "rom_syms.h"

#define HEALTH_VERSION  0x00010000u
#ifndef CALLSIGN
#define CALLSIGN        "N0CALL"
#endif

extern void irq_off(void);
extern void irq_on(void);

static uint32_t ms(void) { return REG(SYS_MS); }
static void kick(void) { REG(IO_WDOG) = IO_WDOG_KEY; }

/* ------------------------------------------------------------------ output */

/* The boot ROM keeps console output in a 256-byte ring and sends it on each write: write in pieces. */
static void outn(const char *s, uint32_t n)
{
    while (n) {
        uint32_t k = n > 128 ? 128 : n;
        ROM_API->con_write(s, k);
        s += k;
        n -= k;
    }
}

static void out(const char *s)
{
    uint32_t n = 0;
    while (s[n]) n++;
    outn(s, n);
}

static void out_udec(uint32_t u)
{
    char b[11];
    int i = sizeof(b);
    do { b[--i] = '0' + u % 10; u /= 10; } while (u);
    outn(b + i, sizeof(b) - i);
}

static void out_hex(uint32_t v, int digits)
{
    static const char h[] = "0123456789ABCDEF";
    char b[8];
    for (int i = digits - 1; i >= 0; i--, v >>= 4) b[i] = h[v & 15];
    out("0x");
    outn(b, digits);
}

static void out_tenths(int32_t t10)
{
    if (t10 < 0) { out("-"); t10 = -t10; }
    out_udec(t10 / 10);
    out(".");
    out_udec(t10 % 10);
}

/* ------------------------------------------------------------------ measurements */

/* degC = (3.26 V * code / 4096 - 0.5 V) / 0.01 V/degC, in tenths (as software/hermeslite/hermeslite.py) */
static int32_t temp_tenths(void) { return (int32_t)(((REG(STAT_TEMP) & 0xFFF) * 3260u) >> 12) - 500; }

/* PA bias current A = (3.26 V * code / 4096) / 50 / 0.04 ohm (hermeslite.py), in mA */
static uint32_t bias_ma(void) { return ((REG(STAT_BIAS) & 0xFFF) * 1630u) >> 12; }

static void show_measurements(void)
{
    out("t ");
    out_tenths(temp_tenths());
    out(" C  bias ");
    out_udec(bias_ma());
    out(" mA  fwd ");
    out_udec(REG(STAT_FWD) & 0xFFF);
    out("  rev ");
    out_udec(REG(STAT_REV) & 0xFFF);
    out("  fan ");
    out_udec((REG(IO_FAN) >> 8) & 7);
    out("\n");
}

/* ------------------------------------------------------------------ I2C */

static int wait_cmd_idle(void)
{
    uint32_t t0 = ms();
    while (REG(IO_CMD_ADDR) & IO_CMD_BUSY)
        if (ms() - t0 > 50) return 0;
    return 1;
}

/* One transfer through the register block: 0 ok, 1 NACK, 2 refused (bias guard), 3 dropped, 4 timeout. */
static uint32_t i2c_xfer(uint32_t word, uint32_t *data)
{
    uint32_t st = REG(IO_I2C_STATUS), done = (st >> 16) & 0xFF, ref = st >> 24, t0;
    if (!wait_cmd_idle()) return 4;
    REG(IO_I2C_XFER) = word;
    for (t0 = ms(); ms() - t0 < 250;) {
        st = REG(IO_I2C_STATUS);
        if (((st >> 16) & 0xFF) != done) {
            *data = REG(IO_I2C_RDATA);
            return (st & IO_I2C_NACK) ? 1 : 0;
        }
        if ((st >> 24) != ref) return (st & IO_I2C_REFUSED) ? 2 : 3;
    }
    return 4;
}

static uint32_t i2c_probe(uint32_t bus, uint32_t addr)
{
    uint32_t d, r;
    for (int tries = 0; tries < 4; tries++) {       /* dropped: the engine was busy (slow ADC poll); retry */
        r = i2c_xfer(bus << 30 | IO_I2C_READ | IO_I2C_PROBE | addr << 16, &d);
        if (r != 3) return r;
    }
    return r;
}

struct chip { uint8_t bus, addr; const char *name; };

/* From the HL2 schematic and bill of materials (hardware/hl), gateware/rtl/i2c.v and hermeslite.py */
static const struct chip chips[] = {
    { 1, 0x6A, "VersaClock 5 5P49V5923 clock generator (HL2 U6)" },
    { 1, 0x12, "AK4951 audio codec (AK4951 companion board)" },
    { 2, 0x2C, "MCP4662 PA bias pots + configuration EEPROM (HL2 U15)" },
    { 2, 0x20, "MCP23008 I/O expander (N2ADR filter board)" },
    { 2, 0x1D, "Pico microcontroller (N2ADR HL2 IO board)" },
    { 2, 0x41, "IO board ROM (N2ADR HL2 IO board)" },
    { 3, 0x34, "MAX11613 slow ADC: temperature, power, bias (HL2)" },
};

static void scan(uint32_t bus)
{
    uint32_t n = 0, a;
    uint8_t found[16] = { 0 };
    out("bus ");
    out_udec(bus);
    out(bus == 1 ? " (clock chip):\n" : bus == 2 ? " (bias pots, filter and IO boards):\n" : " (slow ADC; probes only):\n");
    for (a = 0x08; a <= 0x77; a++) {
        kick();
        uint32_t r = i2c_probe(bus, a);
        if (r > 1) { out("  "); out_hex(a, 2); out(r == 2 ? " refused\n" : r == 3 ? " busy\n" : " timeout\n"); continue; }
        if (r) continue;
        n++;
        found[a >> 3] |= 1 << (a & 7);
        out("  ");
        out_hex(a, 2);
        out("  ");
        const char *name = "unknown device";
        for (uint32_t i = 0; i < sizeof(chips) / sizeof(chips[0]); i++)
            if (chips[i].bus == bus && chips[i].addr == a) name = chips[i].name;
        out(name);
        out("\n");
    }
    for (uint32_t i = 0; i < sizeof(chips) / sizeof(chips[0]); i++) {
        a = chips[i].addr;
        if (chips[i].bus != bus || a == 0x12 || a == 0x41 || (found[a >> 3] >> (a & 7) & 1)) continue;
        out("  not found: ");
        out(chips[i].name);
        out("\n");
    }
    out("  ");
    out_udec(n);
    out(" device(s)\n");
}

/* MCP4662 wipers: read commands 0x0C (wiper 0) and 0x1C (wiper 1) are let through by the bias guard */
static void pots(void)
{
    for (uint32_t w = 0; w < 2; w++) {
        uint32_t d = 0, r = i2c_xfer(2u << 30 | IO_I2C_READ | 0x2Cu << 16 | (w ? 0x1C : 0x0C) << 8, &d);
        out("bias pot wiper ");
        out_udec(w);
        if (r) { out(": I2C error "); out_udec(r); out("\n"); continue; }
        out(" = ");
        out_hex((((d & 0xFF) << 8) | ((d >> 8) & 0xFF)) & 0x1FF, 3);
        out("\n");
    }
}

/* ------------------------------------------------------------------ status */

static const char *const reasons[] = { "lease", "over-temperature", "TX inhibit", "CPU watchdog", "max key-down", "temperature stale" };

static void list_reasons(uint32_t bits)
{
    int any = 0;
    for (int i = 0; i < 6; i++)
        if (bits >> i & 1) { out(any ? ", " : ""); out(reasons[i]); any = 1; }
    if (!any) out("none");
}

static void status(void)
{
    uint32_t ilk = REG(IO_ILK_STATUS), in = REG(IO_INPUTS), wd = REG(IO_WDOG), i2c = REG(IO_I2C_STATUS);
    out("uptime ");
    out_udec(ms() / 1000);
    out(" s, gateware ");
    out_hex(REG(STAT_VERSION), 8);
    out(", health console ");
    out_hex(HEALTH_VERSION, 8);
    out("\n");
    show_measurements();
    out("transmit ");
    out(ilk & 1 ? "ON" : "off");
    out(", trips latched: ");
    list_reasons(ilk >> 8 & 0x3F);
    out(", cut-offs now: ");
    list_reasons(ilk >> 16 & 0x3E);                 /* bit 0 "no lease" is the normal idle state */
    out("\ninputs (debounced): key ");
    out(in >> 16 & 1 ? "closed" : "open");
    out(", PTT ");
    out(in >> 17 & 1 ? "closed" : "open");
    out(", TX inhibit ");
    out(in >> 18 & 1 ? "active" : "inactive");
    out("\nwatchdog ");
    out(wd >> 30 & 1 ? "armed" : "not armed");
    out(wd >> 31 ? ", FIRED" : "");
    out(", I2C transfers ");
    out_udec(i2c >> 16 & 0xFF);
    out(" (mod 256), refused/dropped ");
    out_udec(i2c >> 24);
    out("\n");
}

/* ------------------------------------------------------------------ Morse on LED D5 */

#define LED_D5_OVR  (1u << 3)
#define LED_D5_ON   (1u << 7)

/* A-Z then 0-9: element count in the top 3 bits, elements in the low bits, first element in bit 0, 1 = dash */
static const uint8_t morse_az[26] = {
    0x42, 0x81, 0x85, 0x61, 0x20, 0x84, 0x63, 0x80, 0x40, 0x8E, 0x65, 0x82, 0x43,
    0x41, 0x67, 0x86, 0x8B, 0x62, 0x60, 0x21, 0x64, 0x88, 0x66, 0x89, 0x8D, 0x83 };
static const uint8_t morse_09[10] = { 0xBF, 0xBE, 0xBC, 0xB8, 0xB0, 0xA0, 0xA1, 0xA3, 0xA7, 0xAF };

static char     call[16] = CALLSIGN;
static char     tx_text[64];
static uint32_t tx_pos, tx_len;
static uint8_t  el_bits, el_left, beacon = 1, monitor = 1;
static uint32_t wpm = 15, next_ms, beacon_ms;
static int      led_state = -1;                 /* -1: Morse not driving the LED */

static void led_d5(int on)
{
    uint32_t v = REG(IO_LED) & 0xFF;
    if (on < 0) v &= ~(LED_D5_OVR | LED_D5_ON);
    else v = (v | LED_D5_OVR | (on ? LED_D5_ON : 0)) & ~(on ? 0 : LED_D5_ON);
    REG(IO_LED) = v;
    led_state = on;
}

static uint8_t morse_code(char c)
{
    if (c >= 'a' && c <= 'z') c -= 32;
    if (c >= 'A' && c <= 'Z') return morse_az[c - 'A'];
    if (c >= '0' && c <= '9') return morse_09[c - '0'];
    if (c == '/') return 0xA9;                  /* -..-. */
    return 0;                                   /* space and anything else: word gap */
}

static void morse_start(const char *s)
{
    uint32_t n = 0;
    while (s[n] && n < sizeof(tx_text) - 1) { tx_text[n] = s[n]; n++; }
    tx_text[n] = 0;
    tx_len = n;
    tx_pos = 0;
    el_left = 0;
    next_ms = ms();
}

/* one step of the Morse state machine: dot = 1200 / wpm ms, dash 3, element gap 1, letter gap 3, word gap 7 */
static void morse_poll(void)
{
    uint32_t dot = 1200 / wpm, now = ms();
    if (tx_pos > tx_len || now < next_ms) {
        if (tx_pos > tx_len && beacon && call[0] && now - beacon_ms >= 10000) {
            beacon_ms = now;
            morse_start(call);
        }
        return;
    }
    if (led_state == 1) {                       /* element done: gap */
        led_d5(0);
        next_ms = now + (el_left ? dot : 3 * dot);
        return;
    }
    if (!el_left) {
        if (tx_pos == tx_len) {                 /* text done: release the LED */
            led_d5(-1);
            tx_pos++;
            beacon_ms = now;
            return;
        }
        uint8_t c = morse_code(tx_text[tx_pos++]);
        if (!c) { led_d5(0); next_ms = now + 4 * dot; return; }    /* + the 3-dot letter gap = 7 */
        el_left = c >> 5;
        el_bits = c;
    }
    led_d5(1);
    next_ms = now + ((el_bits & 1) ? 3 * dot : dot);
    el_bits >>= 1;
    el_left--;
}

/* ------------------------------------------------------------------ commands */

static int word_is(const char **p, const char *w)
{
    const char *s = *p;
    while (*w && *s == *w) { s++; w++; }
    if (*w || (*s && *s != ' ')) return 0;
    while (*s == ' ') s++;
    *p = s;
    return 1;
}

static uint32_t parse_u(const char *p, int *ok)
{
    uint32_t v = 0;
    *ok = (*p >= '0' && *p <= '9');
    while (*p >= '0' && *p <= '9') v = v * 10 + (*p++ - '0');
    if (*p && *p != ' ') *ok = 0;
    return v;
}

static const char help_text[] =
    "commands (read-only or harmless; nothing here can transmit):\n"
    "  help                 this list\n"
    "  status               uptime, measurements, transmit interlock state, inputs, watchdog\n"
    "  temp                 temperature, bias current, power codes, fan state\n"
    "  monitor on|off       print the measurements once a second\n"
    "  scan [1|2|3]         I2C address probes, known chips named\n"
    "  pots                 read the PA bias pot wipers (read-only)\n"
    "  call [TEXT]          show or set the callsign sent on LED D5 every 10 s\n"
    "  beacon on|off        callsign repeat on/off\n"
    "  morse TEXT           send TEXT once on LED D5\n"
    "  wpm N                Morse speed, 5-40 words per minute\n"
    "  led d2|d4|d5 on|off|auto   LED override (D3 shows transmit and is not overridden)\n"
    "  fan N                minimum fan duty 0-15 sixteenths, added to the gateware fan control\n";

static void command(char *line)
{
    const char *p = line;
    int ok;
    while (*p == ' ') p++;
    out("> ");
    out(p);
    out("\n");

    if (!*p) return;
    if (word_is(&p, "help")) { out(help_text); return; }
    if (word_is(&p, "status")) { status(); return; }
    if (word_is(&p, "temp")) { show_measurements(); return; }
    if (word_is(&p, "pots")) { pots(); return; }
    if (word_is(&p, "monitor")) {
        if (word_is(&p, "on")) monitor = 1;
        else if (word_is(&p, "off")) monitor = 0;
        out(monitor ? "monitor on\n" : "monitor off\n");
        return;
    }
    if (word_is(&p, "scan")) {
        uint32_t b = parse_u(p, &ok);
        if (!*p) { scan(1); scan(2); scan(3); }
        else if (ok && b >= 1 && b <= 3) scan(b);
        else out("scan: bus 1, 2 or 3\n");
        return;
    }
    if (word_is(&p, "call")) {
        uint32_t n = 0;
        if (*p) {
            while (p[n] && n < sizeof(call) - 1) { call[n] = p[n]; n++; }
            call[n] = 0;
            beacon_ms = ms() - 10000;
        }
        out("callsign ");
        out(call);
        out(beacon ? ", beacon on\n" : ", beacon off\n");
        return;
    }
    if (word_is(&p, "beacon")) {
        if (word_is(&p, "on")) { beacon = 1; beacon_ms = ms() - 10000; }
        else if (word_is(&p, "off")) beacon = 0;
        out(beacon ? "beacon on\n" : "beacon off\n");
        return;
    }
    if (word_is(&p, "morse")) {
        if (!*p) { out("morse: text missing\n"); return; }
        morse_start(p);
        out("sending on LED D5\n");
        return;
    }
    if (word_is(&p, "wpm")) {
        uint32_t v = parse_u(p, &ok);
        if (ok && v >= 5 && v <= 40) wpm = v;
        out("wpm ");
        out_udec(wpm);
        out("\n");
        return;
    }
    if (word_is(&p, "led")) {
        uint32_t bit;
        if (word_is(&p, "d2")) bit = 0;
        else if (word_is(&p, "d4")) bit = 2;
        else if (word_is(&p, "d5")) bit = 3;
        else { out("led: d2, d4 or d5 (D3 shows transmit and is not overridden)\n"); return; }
        uint32_t v = REG(IO_LED) & 0xFF;
        if (word_is(&p, "on")) v |= (1u << bit) | (0x10u << bit);
        else if (word_is(&p, "off")) v = (v | (1u << bit)) & ~(0x10u << bit);
        else if (word_is(&p, "auto")) v &= ~((1u << bit) | (0x10u << bit));
        else { out("led: on, off or auto\n"); return; }
        if (bit == 3) { tx_pos = tx_len + 1; beacon = 0; led_state = -1; }   /* manual D5 stops Morse */
        REG(IO_LED) = v;
        out("LED register ");
        out_hex(REG(IO_LED) & 0xFF, 2);
        out("\n");
        return;
    }
    if (word_is(&p, "fan")) {
        uint32_t v = parse_u(p, &ok);
        if (!ok || v > 15) { out("fan: 0-15\n"); return; }
        REG(IO_FAN) = v;
        out("fan minimum ");
        out_udec(REG(IO_FAN) & 15);
        out("/16\n");
        return;
    }
    out("unknown command, try help\n");
}

/* ------------------------------------------------------------------ packets */

#define PB(i) ((uint8_t)PBUF(PBUF_RX + ((i) & PBUF_RX_MASK)))

static uint16_t rx_rd;
static uint8_t  handed;                     /* receive ring handed to the boot ROM */
static char     line[96];

static void rx_poll(void)
{
    if (handed) {
        if (REG(PKT_RX_RD) != REG(PKT_RX_WR)) return;
        irq_off();                          /* the ROM has read everything: take the ring back */
        rx_rd = REG(PKT_RX_RD);
        handed = 0;
    }
    while (rx_rd != REG(PKT_RX_WR)) {
        uint32_t n = PB(rx_rd) | (PB(rx_rd + 1) << 8), i;
        if (n > 510) {                      /* out of step: skip everything waiting */
            REG(PKT_RX_RD) = rx_rd = REG(PKT_RX_WR);
            return;
        }
        if (n == 2 && PB(rx_rd + 2) == 0x01 && (PB(rx_rd + 3) == 'A' || PB(rx_rd + 3) == 'K')) {
            /* console attach ('A', with replay of the kept output) or keep-alive ('K'): done here as the
               boot ROM does it, so command datagrams queued behind it are not read by the ROM (it would
               take them for gdb traffic) */
            if (PB(rx_rd + 3) == 'A') {
                ROM_RING_SENT = 0;
                ROM_GDB_ATTACHED = ROM_GDB_RUNNING = 0;
            }
            ROM_CON_ATTACHED = 1;
            rx_rd = (rx_rd + 4) & 1023;
            REG(PKT_RX_RD) = rx_rd;
            ROM_API->con_write("", 0);      /* sends the replay */
            continue;
        }
        if (n == 0 || PB(rx_rd + 2) != 0x02) {
            ROM_RX_RD = rx_rd;              /* gdb or a save/erase request: the boot ROM reads from here */
            ROM_RX_LEFT = 0;
            handed = 1;
            irq_on();                       /* the pending packet interrupt enters the boot ROM now */
            return;
        }
        for (i = 0; i + 1 < n && i < sizeof(line) - 1; i++) {
            char c = PB(rx_rd + 3 + i);
            line[i] = (c == '\r' || c == '\n' || c == '\t') ? ' ' : c;
        }
        line[i] = 0;
        rx_rd = (rx_rd + 2 + n) & 1023;
        REG(PKT_RX_RD) = rx_rd;
        command(line);
    }
}

/* ------------------------------------------------------------------ main */

int main(void)
{
    uint32_t last = 0;

    /* The application reads the receive ring itself with interrupts off (mstatus.MIE = 0). The packet
       interrupt stays enabled in the gateware (SYS_IRQ_EN) and in mie: the boot ROM's gdb stub sleeps in
       wfi while the target is stopped, and wfi only wakes on an enabled interrupt. */
    irq_off();
    REG(SYS_IRQ_EN) = IRQ_PKT;
    rx_rd = REG(PKT_RX_RD);
    kick();
    out("\nHL2 radio health console ");
    out_hex(HEALTH_VERSION, 8);
    out(", callsign ");
    out(call);
    out(" on LED D5. Type help.\n");
    beacon_ms = ms() - 8000;                /* first callsign after 2 s */
    tx_pos = tx_len + 1;

    for (;;) {
        kick();
        rx_poll();
        morse_poll();
        if (ms() - last >= 1000) {
            last = ms();
            if (monitor) show_measurements();
        }
    }
}
