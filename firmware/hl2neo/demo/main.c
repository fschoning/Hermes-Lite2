/* SPDX-License-Identifier: Apache-2.0
 * Copyright 2026 Franz Schöning, https://www.schoning.com
 */
/* Demo application: banner, then once a second the board temperature on the console and a toggle
 * of LED D5 (a receive-side indicator, not transmit-related). Sleeps between timer ticks.
 * Load with gdb ("load", "continue") or hl2fw.py ("run demo.elf"); save with "monitor save" or
 * "hl2fw.py save demo.elf".
 */

#include "hl2cpu.h"

#define DEMO_VERSION 0x00010000u

extern void cpu_wfi(void);
extern void timer_irq_on(void);
extern void irq_off(void);
extern void irq_on(void);

static volatile uint32_t ticks;

static void out(const char *s)
{
    uint32_t n = 0;
    while (s[n]) n++;
    ROM_API->con_write(s, n);
}

static void out_dec(int32_t v)
{
    char b[12];
    int i = sizeof(b);
    uint32_t u = v < 0 ? -(uint32_t)v : (uint32_t)v;
    b[--i] = 0;
    do { b[--i] = '0' + u % 10; u /= 10; } while (u);
    if (v < 0) b[--i] = '-';
    out(b + i);
}

static void on_irq(uint32_t mcause)
{
    if ((mcause & 0xFF) == 7) {             /* machine timer: next tick in 1 s */
        REG(SYS_TIMER_CMP) += 1000;
        ticks++;
    }
}

int main(void)
{
    uint32_t seen = 0, n = 0;

    out("\ndemo: HL2 RV32 demo application, temperature once a second\n");
    ROM_API->set_irq_handler(on_irq);
    REG(SYS_LED) = 2;                       /* CPU drives LED D5, off */
    REG(SYS_TIMER_CMP) = REG(SYS_MS) + 1000;
    REG(SYS_IRQ_EN) |= IRQ_TIMER;
    timer_irq_on();

    for (;;) {
        irq_off();                          /* check and sleep with interrupts off: no lost wake-up */
        if (ticks == seen) cpu_wfi();
        irq_on();                           /* a pending timer interrupt is taken here */
        if (ticks == seen) continue;
        seen = ticks;

        uint32_t code = REG(STAT_TEMP) & 0xFFF;
        /* degC = (3.26 V * code / 4096 - 0.5 V) / 0.01 V/degC; in tenths: 3260 * code / 4096 - 500 */
        int32_t t10 = (int32_t)((code * 3260u) >> 12) - 500;
        out("t ");
        out_dec(t10 / 10);
        out(".");
        out_dec((t10 < 0 ? -t10 : t10) % 10);
        out(" C  code ");
        out_dec(code);
        out("  n ");
        out_dec(n++);
        out("\n");
        REG(SYS_LED) ^= 1;
    }
}
