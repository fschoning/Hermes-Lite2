/* SPDX-License-Identifier: Apache-2.0
 * Copyright 2026 Franz Schöning, https://www.schoning.com
 */
/* Hermes-Lite 2 soft CPU boot ROM (NEORV32 rv32imc, hl2b5up_neo).
 *
 *  - console over the aux UDP port 1027: to hl2fw.py, or to gdb as 'O' packets while gdb runs
 *    the target
 *  - GDB remote serial protocol stub over UDP (gdb: target remote udp:<radio>:1027)
 *  - save the loaded RAM image to the flash sector 0x1F0000; boot it at power-up (only images saved
 *    by this ROM: the header format names the CPU, so the VexRiscv ROM's rv32i images are refused)
 *
 * Datagrams to port 1027 that are neither Etherbone (0x4E 0x6F) nor aux channel (0x5B) packets
 * reach the CPU through the receive ring. A datagram whose first byte is 0x01 is a control
 * datagram from hl2fw.py; any other datagram is gdb byte stream.
 *
 * Written for size: the ROM and RAM share the FPGA's scarce memory blocks. No initialised data:
 * everything writable is .bss in the workspace at the top of RAM.
 */

#include "hl2cpu.h"

#define SIGINT  2
#define SIGILL  4
#define SIGTRAP 5
#define SIGSEGV 11

struct frame {
    uint32_t x[32];
    uint32_t pc;
    uint32_t mcause;
    uint32_t mtval;
    uint32_t mstatus;
};

extern void rom_idle(void) __attribute__((noreturn));
extern void rom_jump(uint32_t entry) __attribute__((noreturn));
extern uint32_t irq_off(void);              /* start.S: clear MIE, return the old mstatus */
extern void irq_restore(uint32_t old);
extern void cpu_wfi(void);
extern void irq_setup(void);
extern uint32_t mie_swap(uint32_t mie);     /* start.S: write mie, return the old value */

#define MSTATUS_MPIE (1u << 7)
#define MIE_MSIE     (1u << 3)
#define MIE_MEIE     (1u << 11)

static void con_write(const char *s, uint32_t n);
static void set_irq_handler(void (*h)(uint32_t));
static uint32_t crc32(uint32_t crc, const uint8_t *p, uint32_t n);

const struct rom_api rom_api = { ROM_API_MAGIC, ROM_VERSION, con_write, set_irq_handler, crc32 };

#define GDB_PKT_MAX 384                     /* PacketSize advertised to gdb (0x180) */
#define CTRL_MAX    24
#define RING_SIZE   256

#define EV_NONE     0
#define EV_PACKET   1
#define EV_INTR     2

/* ------------------------------------------------------------------ state (.bss in the workspace) */

static void    (*app_irq)(uint32_t);
static uint32_t fw_state;
static uint8_t  con_attached;       /* hl2fw console attached */
static uint8_t  gdb_attached;       /* gdb traffic seen since the last detach */
static uint8_t  gdb_running;        /* gdb continued the target and waits for a stop reply */
static uint8_t  in_rcmd;            /* inside a monitor command: output may go to gdb */
static uint8_t  last_sig;
static uint8_t  result_seq;

static char     ring[RING_SIZE];
static uint32_t ring_wr, ring_sent;

static uint16_t tx_n;
static uint8_t  tx_ok, csum;

static uint16_t rx_rd, rx_left;
static uint8_t  dg_first, dg_ctrl, ctrl_len;
static uint8_t  ctrl_buf[CTRL_MAX];

static uint8_t  g_state, g_cs, g_rxcs, g_ack;
static uint16_t g_len;
static char     g_in[GDB_PKT_MAX + 1];

static uint32_t load_lo, load_hi;   /* RAM range written by gdb since the last save */
static uint32_t load_entry;         /* pc set by gdb after the load (its "Start address") */

/* ------------------------------------------------------------------ helpers */

static const char hexd[] = "0123456789abcdef";

static uint32_t ms(void) { return REG(SYS_MS); }
#define ram_end() (RAM_BASE + RAM_SIZE)    /* fixed: ROM and RAM are in the same bitstream */
#define app_end() ram_end()

static int hexval(char c)
{
    if (c >= '0' && c <= '9') return c - '0';
    c |= 0x20;
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    return -1;
}

static uint32_t crc32(uint32_t crc, const uint8_t *p, uint32_t n)
{
    crc = ~crc;
    while (n--) {
        crc ^= *p++;
        for (int k = 0; k < 8; k++) crc = (crc >> 1) ^ (0xEDB88320u & -(crc & 1));
    }
    return ~crc;
}

/* ------------------------------------------------------------------ packet output */

static int tx_wait(void)
{
    uint32_t t0 = ms(), s;
    while (((s = REG(PKT_TX_LEN)) & TX_BUSY) && ms() - t0 < 200) ;
    return (s & (TX_BUSY | TX_DEST)) == TX_DEST;
}

static void tx_flush(void)
{
    if (tx_n && tx_ok) REG(PKT_TX_LEN) = tx_n;
    tx_n = 0;
}

static void tx_c(uint32_t c)
{
    if (!tx_n) tx_ok = tx_wait();
    PBUF(PBUF_TX + tx_n) = c;
    if (++tx_n == PBUF_TX_SIZE) tx_flush();
}

/* gdb packets are written straight into the transmit buffer; a long reply spans datagrams */
static void rp_c(uint32_t c) { tx_c(c); csum += c; }
static void rp_h8(uint32_t b) { rp_c(hexd[(b >> 4) & 15]); rp_c(hexd[b & 15]); }
static void rp_h32(uint32_t v) { for (int i = 0; i < 4; i++, v >>= 8) rp_h8(v & 0xFF); }

static void rp_begin(void)
{
    if (g_ack) tx_c('+');
    g_ack = 0;
    tx_c('$');
    csum = 0;
}

static void rp_end(void)
{
    uint32_t c = csum;
    tx_c('#');
    tx_c(hexd[c >> 4]);
    tx_c(hexd[c & 15]);
    tx_flush();
}

static void rp_str(const char *s)
{
    rp_begin();
    while (*s) rp_c(*s++);
    rp_end();
}

/* ------------------------------------------------------------------ console */

static void con_flush(void)
{
    if (ring_wr - ring_sent > RING_SIZE) ring_sent = ring_wr - RING_SIZE;
    if (gdb_attached ? !(gdb_running | in_rcmd) : !con_attached) return;
    while (ring_sent != ring_wr) {
        uint32_t n = 0;
        if (gdb_attached) { rp_begin(); rp_c('O'); }
        else { tx_c(1); tx_c('C'); }
        while (ring_sent != ring_wr && n++ < 100) {
            uint8_t c = ring[ring_sent++ & (RING_SIZE - 1)];
            if (gdb_attached) rp_h8(c); else tx_c(c);
        }
        if (gdb_attached) rp_end(); else tx_flush();
    }
}

static void con_write(const char *s, uint32_t n)
{
    uint32_t m = irq_off();
    while (n--) ring[ring_wr++ & (RING_SIZE - 1)] = *s++;
    con_flush();
    irq_restore(m);
}

static void con_puts(const char *s)
{
    uint32_t n = 0;
    while (s[n]) n++;
    con_write(s, n);
}

static void con_kv(const char *k, uint32_t v)
{
    char b[9];
    con_puts(k);
    for (int i = 7; i >= 0; i--, v >>= 4) b[i] = hexd[v & 15];
    b[8] = '\n';
    con_write(b, 9);
}

static void set_irq_handler(void (*h)(uint32_t)) { app_irq = h; }

static void start_app(uint32_t entry) __attribute__((noreturn));
static void start_app(uint32_t entry)
{
    fw_state = FWS_APP;
    REG(SYS_FW_STATUS) = FWS_APP;
    rom_jump(entry);
}

/* ------------------------------------------------------------------ flash sector */

static uint32_t fl_cmd(uint32_t cmd)
{
    uint32_t t0 = ms(), s;
    REG(FL_CMD) = cmd;
    while (((s = REG(FL_CMD)) & FL_ST_BUSY) && ms() - t0 < 10000) ;
    if (s & FL_ST_LOCKED) return FWR_LOCKED;
    return (s & (FL_ST_BUSY | FL_ST_REJECTED | FL_ST_ILLEGAL)) ? FWR_FLASH_ERR : FWR_OK;
}

/* Read n flash bytes at FW_SECTOR + off. */
static uint32_t fl_read(uint32_t off, uint8_t *p, uint32_t n)
{
    uint32_t r;
    while (n--) {
        REG(FL_ADDR) = FW_SECTOR + off++;
        if ((r = fl_cmd(FL_CMD_READ))) return r;
        *p++ = REG(FL_DATA);
    }
    return FWR_OK;
}

static int hdr_bad(struct fw_header *h)
{
    return h->load_addr < APP_BASE || h->length > FW_SECTOR_SIZE - FW_HDR_SIZE ||
           h->load_addr + h->length > app_end() || h->entry - h->load_addr >= h->length;
}

/* Copy the saved firmware into RAM and start it. Returns only on failure. */
static uint32_t fw_boot(void)
{
    struct fw_header h;
    uint32_t r;
    if ((r = fl_read(0, (uint8_t *)&h, FW_HDR_SIZE))) return r;
    if (h.magic != FW_MAGIC) return FWR_NO_IMAGE;
    if (crc32(0, (uint8_t *)&h, 28) != h.header_crc || hdr_bad(&h)) return FWR_BAD_IMAGE;
    if (h.format != FW_FORMAT) return FWR_WRONG_CPU;   /* for example rv32i firmware saved by the VexRiscv ROM */
    if ((r = fl_read(FW_HDR_SIZE, (uint8_t *)h.load_addr, h.length))) return r;
    if (crc32(0, (uint8_t *)h.load_addr, h.length) != h.image_crc) return FWR_BAD_IMAGE;
    con_kv("boot ", h.version);
    start_app(h.entry);
}

static uint32_t fw_save(uint32_t load, uint32_t len, uint32_t entry, uint32_t version, uint32_t want_crc)
{
    struct fw_header h;
    uint8_t *hp = (uint8_t *)&h, b;
    uint32_t r, total = FW_HDR_SIZE + len;

    h.magic = FW_MAGIC;
    h.format = FW_FORMAT;
    h.load_addr = load;
    h.length = len;
    h.entry = entry;
    h.version = version;
    if (hdr_bad(&h)) return FWR_BAD_ARGS;
    h.image_crc = crc32(0, (uint8_t *)load, len);
    h.header_crc = crc32(0, hp, 28);
    if (want_crc && want_crc != h.image_crc) return FWR_CRC_MISMATCH;

    if ((r = fl_cmd(FL_CMD_ERASE))) return r;
    for (uint32_t i = 0; i < total; i++) {
        REG(FL_DATA) = i < FW_HDR_SIZE ? hp[i] : ((uint8_t *)load)[i - FW_HDR_SIZE];
        if ((r = fl_cmd(FL_CMD_SHIFT))) return r;
        if ((i & 255) == 255 || i == total - 1) {
            REG(FL_ADDR) = FW_SECTOR + (i & ~255u);
            if ((r = fl_cmd(FL_CMD_PROGRAM))) return r;
        }
    }
    for (uint32_t i = 0; i < total; i++) {
        if ((r = fl_read(i, &b, 1))) return r;
        if (b != (i < FW_HDR_SIZE ? hp[i] : ((uint8_t *)load)[i - FW_HDR_SIZE])) return FWR_VERIFY_ERR;
    }
    return FWR_OK;
}

static uint32_t result(uint32_t op, uint32_t code)
{
    uint32_t v = (op << 24) | ((uint32_t)++result_seq << 16) | code;
    REG(SYS_FW_RESULT) = v;
    con_kv("result ", v);                   /* hl2fw.py decodes it */
    return code;
}

/* ------------------------------------------------------------------ control datagrams (hl2fw) */

static uint32_t le32(const uint8_t *p) { return p[0] | (p[1] << 8) | (p[2] << 16) | ((uint32_t)p[3] << 24); }

static void banner(void)
{
    con_kv("\nHL2 RV32 boot ROM NEORV32 ", ROM_VERSION);
    con_kv("gw ", REG(STAT_VERSION));
}

static void ctrl_datagram(void)
{
    uint8_t *b = ctrl_buf;
    switch (b[1]) {
    case 'A':                               /* attach the console, replay recent output */
        ring_sent = 0;
        gdb_attached = gdb_running = 0;
        /* fall through */
    case 'K':                               /* keep-alive */
        con_attached = 1;
        break;
    case 'S':                               /* save: load, length, entry, version, crc */
    case 'E':
        REG(SYS_FW_STATUS) = FWS_ROM_BUSY;
        result(b[1], b[1] == 'E' ? fl_cmd(FL_CMD_ERASE) : ctrl_len < 22 ? FWR_BAD_ARGS :
               fw_save(le32(b + 2), le32(b + 6), le32(b + 10), le32(b + 14), le32(b + 18)));
        REG(SYS_FW_STATUS) = fw_state;
        break;
    }
    con_flush();
}

/* ------------------------------------------------------------------ gdb input */

static int gdb_byte(uint32_t c)
{
    switch (g_state) {
    case 0:
        if (c == '$') { g_state = 1; g_len = 0; g_cs = 0; }
        else if (c == 0x03) return EV_INTR;
        break;
    case 1:
        if (c == '#') { g_state = 2; break; }
        g_cs += c;
        if (g_len < GDB_PKT_MAX) g_in[g_len++] = c;
        break;
    case 2:
        g_rxcs = hexval(c) << 4;
        g_state = 3;
        break;
    case 3:
        g_state = 0;
        if ((uint8_t)(g_rxcs | hexval(c)) == g_cs) {
            g_in[g_len] = 0;
            g_ack = 1;
            return EV_PACKET;
        }
        break;                              /* bad checksum: no ack, gdb sends again */
    }
    return EV_NONE;
}

static uint32_t rx_get(void)
{
    uint32_t c = PBUF(PBUF_RX + (rx_rd & PBUF_RX_MASK)) & 0xFF;
    rx_rd = (rx_rd + 1) & 1023;
    REG(PKT_RX_RD) = rx_rd;
    return c;
}

/* Handle waiting datagrams. Returns EV_PACKET when a gdb packet is complete, EV_INTR on Ctrl-C. */
static int rx_poll(void)
{
    for (;;) {
        if (!rx_left) {
            if (rx_rd == REG(PKT_RX_WR)) return EV_NONE;
            rx_left = rx_get();
            rx_left |= rx_get() << 8;
            dg_first = 1;
            ctrl_len = 0;
            if (rx_left > 512) {            /* out of step (restart inside a datagram): resynchronise */
                rx_left = 0;
                REG(PKT_RX_RD) = rx_rd = REG(PKT_RX_WR);
            }
            continue;
        }
        uint32_t c = rx_get();
        rx_left--;
        if (dg_first) dg_ctrl = (c == 1);
        dg_first = 0;
        if (dg_ctrl) {
            if (ctrl_len < CTRL_MAX) ctrl_buf[ctrl_len++] = c;
            if (!rx_left && ctrl_len > 1) ctrl_datagram();
            continue;
        }
        if (!gdb_attached) { gdb_attached = 1; con_attached = 0; }
        int ev = gdb_byte(c);
        if (ev) return ev;
    }
}

/* ------------------------------------------------------------------ gdb commands */

static int mem_ok(uint32_t a, uint32_t n, int wr)
{
    uint32_t e = a + n;
    if (a >= (wr ? APP_BASE : RAM_BASE) && e >= a && e <= ram_end()) return 1;
    return !wr && (a >> 16) != (PKT_BASE >> 16);    /* reads: anything but the packet registers */
}

static const char *parse_hex(const char *p, uint32_t *v)
{
    int d;
    *v = 0;
    while ((d = hexval(*p)) >= 0) { *v = (*v << 4) | d; p++; }
    return p;
}


static void monitor(const char *p)
{
    char cmd[16];
    uint32_t n = 0, v;
    while (p[0] && n < sizeof(cmd) - 1) {
        cmd[n++] = hexval(p[0]) << 4 | hexval(p[1]);
        p += 2;
    }
    cmd[n] = 0;
    g_ack = 0;
    tx_c('+');
    tx_flush();
    in_rcmd = 1;
    if (cmd[0] == 's') {                    /* "save [version-hex]"; other commands only answer OK */
        parse_hex(cmd + 5, &v);
        if (result('S', load_hi ? fw_save(load_lo, load_hi - load_lo, load_entry, n > 5 ? v : 0, 0) : FWR_BAD_ARGS) == FWR_OK)
            load_hi = 0;
    }
    con_flush();
    in_rcmd = 0;
    rp_str("OK");
}

/* Single step (gdb sends 's' on bare-metal RISC-V), with the gateware's step interrupt: SYS_STEP
 * holds the machine software interrupt line active, and NEORV32 takes an interrupt only after the
 * instruction it is executing, so the target stops after exactly one instruction. During the step
 * only the step and packet interrupts are enabled, and interrupts are on even where the target had
 * them off; both are put back when the step ends. */
#define REG16(a) (*(volatile uint16_t *)(a))

static uint32_t step_mie, step_insn;
static uint8_t  stepping, step_mpie;

static void step_start(struct frame *f)
{
    /* two 16-bit reads: with compressed code pc need not be word-aligned, and NEORV32 refuses
       32-bit reads at such addresses (load address misaligned) */
    step_insn = REG16(f->pc) | (uint32_t)REG16(f->pc + 2) << 16;
    step_mpie = f->mstatus & MSTATUS_MPIE;
    f->mstatus |= MSTATUS_MPIE;
    step_mie = mie_swap(MIE_MEIE | MIE_MSIE);
    REG(SYS_STEP) = 1;
    stepping = 1;
}

static void step_end(struct frame *f)
{
    if (!stepping) return;
    stepping = 0;
    REG(SYS_STEP) = 0;
    mie_swap(step_mie);
    /* interrupts were off before the step: off again, unless the instruction was a CSR write to mstatus */
    if (!step_mpie && !((step_insn & 0xFFF0007Fu) == 0x30000073u && (step_insn & 0x3000u)))
        f->mstatus &= ~MSTATUS_MPIE;
}

/* Returns 1 when the target resumes. */
static int gdb_handle(struct frame *f)
{
    const char *p = g_in + 1;
    uint32_t a, n;

    switch (g_in[0]) {
    case '?':
        rp_begin(); rp_c('S'); rp_h8(last_sig); rp_end();
        break;
    case 'g':
        rp_begin();
        for (int i = 0; i < 32; i++) rp_h32(f->x[i]);
        rp_h32(f->pc);
        rp_end();
        break;
    case 'P':
        p = parse_hex(p, &n);
        a = 0;
        for (int i = 0; i < 8; i += 2) a |= (uint32_t)(hexval(p[i + 1]) << 4 | hexval(p[i + 2])) << (i * 4);
        if (n == 32) f->pc = load_entry = a; else if (n && n < 32) f->x[n] = a;
        rp_str("OK");
        break;
    case 'm':
        p = parse_hex(p, &a);
        parse_hex(p + 1, &n);
        if (n > GDB_PKT_MAX / 2 - 4) n = GDB_PKT_MAX / 2 - 4;
        if (!mem_ok(a, n, 0)) { rp_str("E14"); break; }
        rp_begin();
        while (n--) {
            rp_h8(REG8(a));                 /* registers: the gateware returns the whole word */
            a++;
        }
        rp_end();
        break;
    case 'X': {
        const char *e = g_in + g_len;
        p = parse_hex(p, &a);
        p = parse_hex(p + 1, &n);
        if (!mem_ok(a, n, 1)) { rp_str("E14"); break; }
        if (n) {
            if (!load_hi || a < load_lo) load_entry = load_lo = a;
            if (a + n > load_hi) load_hi = a + n;
        }
        for (p++; n && p < e; n--) {
            uint8_t c = *p++;
            if (c == '}') c = *p++ ^ 0x20;
            REG8(a++) = c;
        }
        rp_str("OK");
        break;
    }
    case 'k':                               /* kill: detach, the target keeps running */
    case 'D':
        gdb_attached = 0;
        rp_str("OK");
        return 1;
    case 's':
        step_start(f);
        /* fall through */
    case 'c':
        if (*p) parse_hex(p, &f->pc);
        g_ack = 0;
        tx_c('+');
        tx_flush();
        gdb_running = 1;
        return 1;
    case 'q':
        if (p[0] == 'S' && p[1] == 'u') { rp_str("PacketSize=180"); break; }   /* qSupported */
        if (p[0] == 'R') { monitor(p + 5); break; }                          /* qRcmd */
        /* fall through */
    default:
        rp_str("");
        break;
    }
    return 0;
}

static void stub_stop(struct frame *f, int sig, int have_packet)
{
    last_sig = sig;
    REG(SYS_FW_STATUS) = FWS_STOPPED | sig;
    if (gdb_running) {
        gdb_running = 0;
        rp_begin(); rp_c('S'); rp_h8(sig); rp_end();
    } else if (!gdb_attached) {
        con_kv("\nstop, mcause ", f->mcause);
        con_kv("pc ", f->pc);
    }
    for (;;) {
        int ev = have_packet ? EV_PACKET : rx_poll();
        have_packet = 0;
        if (ev == EV_PACKET) {
            if (gdb_handle(f)) break;
        } else if (ev == EV_NONE) {
            cpu_wfi();
        }
    }
    REG(SYS_FW_STATUS) = fw_state;
    con_flush();
}

/* ------------------------------------------------------------------ traps */

void trap_handler(struct frame *f)
{
    uint32_t cause = f->mcause;
    if ((int32_t)cause < 0) {
        if ((cause & 0xFF) == 3) {          /* step interrupt: one instruction done */
            /* a step into the boot ROM (an API call) runs on, step by step with the ROM's own interrupt
               state, until it is back in the application, as gdb has no symbols for the ROM; not when
               the step started with interrupts off (an interrupt handler: the ROM's trap exit follows) */
            if (step_mpie && f->pc - ROM_BASE < 0x10000u) return;
            step_end(f);
            stub_stop(f, SIGTRAP, 0);
        } else if ((cause & 0xFF) == 11) {
            int ev = rx_poll();
            if (ev == EV_PACKET) gdb_running = 0;   /* a new gdb session: no stop reply expected */
            if (ev) {
                step_end(f);
                stub_stop(f, SIGINT, ev == EV_PACKET);
            }
        } else if (app_irq) {
            /* the application's handler may stop at a breakpoint, which reuses the trap frame:
               keep this interrupt's frame on the ROM stack meanwhile */
            uint32_t save[36];
            for (int i = 0; i < 36; i++) save[i] = ((uint32_t *)f)[i];
            app_irq(cause);
            for (int i = 0; i < 36; i++) ((uint32_t *)f)[i] = save[i];
        } else {
            REG(SYS_IRQ_EN) = IRQ_PKT;
        }
        return;
    }
    step_end(f);
    stub_stop(f, cause == 3 ? SIGTRAP : cause == 2 ? SIGILL : SIGSEGV, 0);
}

/* ------------------------------------------------------------------ main */

void rom_main(void) __attribute__((noreturn));
void rom_main(void)
{
    uint32_t ctrl = REG(SYS_CTRL);

    fw_state = FWS_ROM_BUSY;
    REG(SYS_FW_STATUS) = FWS_ROM_BUSY;      /* tools wait for this to change before they talk */
    REG(PKT_RX_RD) = rx_rd = REG(PKT_RX_WR);    /* drop datagrams from before the restart */
    REG(SYS_IRQ_EN) = IRQ_PKT;
    irq_setup();
    banner();
    if (ctrl & CTRL_BOOT_RAM) {
        con_kv("run ", REG(SYS_BOOT_ADDR));
        start_app(REG(SYS_BOOT_ADDR));
    }
    if (ctrl & CTRL_STAY_ROM) con_puts("stay in ROM\n");
    else result('B', fw_boot());
    fw_state = FWS_ROM_IDLE;
    REG(SYS_FW_STATUS) = FWS_ROM_IDLE;
    rom_idle();
}
