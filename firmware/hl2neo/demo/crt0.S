/* SPDX-License-Identifier: Apache-2.0
 * Copyright 2026 Franz Schöning, https://www.schoning.com
 */
/* Demo application start-up: loaded at APP_BASE (0x800) by gdb, hl2fw.py or the boot ROM. */
    .section .text.start, "ax"
    .globl _start
_start:
    la      sp, __stack_top
    la      a0, __bss_start
    la      a1, __bss_end
1:  bgeu    a0, a1, 2f
    sw      zero, 0(a0)
    addi    a0, a0, 4
    j       1b
2:  call    main
    ebreak                      /* main returned: stop (gdb or console shows it) */
    j       2b

    .align  2                   /* word-aligned: tb_neo overwrites this word through the bridge */
    .globl cpu_wfi
cpu_wfi:                        /* sleep until an enabled interrupt is pending */
    wfi
    ret

    .globl timer_irq_on
timer_irq_on:
    li      t0, 0x80
    csrs    mie, t0             /* MTIE */
    ret

    .globl irq_off
irq_off:
    csrci   mstatus, 8
    ret

    .globl irq_on
irq_on:
    csrsi   mstatus, 8
    ret
