/* SPDX-License-Identifier: Apache-2.0
 * Copyright 2026 Franz Schöning, https://www.schoning.com
 */
/* Boot ROM entry, trap entry and exit (NEORV32 rv32imc).
 *
 * The boot ROM workspace is the first 2 kB of RAM (0x000-0x7FF). The trap frame sits at address 0,
 * so the entry code keeps sp in mscratch, sets sp to 0 and saves all registers with 2-byte
 * compressed "sw xN, off(sp)" instructions. mscratch is therefore not available to applications.
 * The linker turns every access to a ROM variable into a single x0-relative instruction.
 *
 * Frame layout: x0..x31 at 0..124, pc 128, mcause 132, mtval 136, mstatus 140 (struct frame in rom.c).
 */

#define FRAME       0
#define F_PC        (FRAME + 128)
#define F_CAUSE     (FRAME + 132)
#define F_TVAL      (FRAME + 136)
#define F_MSTATUS   (FRAME + 140)

    .section .text.start, "ax"
    .globl _start
_start:
    .option push
    .option norvc               /* 4-byte jump: the header words below stay at +4, +8, +12 */
    j       reset
    .option pop
    .word   0x4D4F5248          /* +0x04: "HROM" */
    .word   rom_api             /* +0x08: pointer to the ROM API table */
    .word   ROM_VERSION         /* +0x0C */

reset:
    csrwi   mstatus, 0
    csrwi   mie, 0
    la      t0, trap_entry
    csrw    mtvec, t0
    li      sp, 0x800           /* stack top = end of the workspace */
    la      a0, __bss_start
    la      a1, __bss_end
1:  bgeu    a0, a1, 2f
    sw      zero, 0(a0)
    addi    a0, a0, 4
    j       1b
2:  call    rom_main
    j       reset

    .globl rom_idle
rom_idle:                       /* idle loop with interrupts on */
    csrsi   mstatus, 8
3:  call    cpu_wfi
    j       3b

    .globl rom_jump
rom_jump:                       /* a0 = entry; start an application with interrupts on */
    csrsi   mstatus, 8
    jr      a0

    .align  2
    .globl trap_entry
trap_entry:                     /* sp = 0 makes every save a 2-byte c.swsp (offsets below 256) */
    csrw    mscratch, sp
    li      sp, FRAME
    sw      x1, 4(sp)
    sw      x3, 12(sp)
    sw      x4, 16(sp)
    sw      x5, 20(sp)
    sw      x6, 24(sp)
    sw      x7, 28(sp)
    sw      x8, 32(sp)
    sw      x9, 36(sp)
    sw      x10, 40(sp)
    sw      x11, 44(sp)
    sw      x12, 48(sp)
    sw      x13, 52(sp)
    sw      x14, 56(sp)
    sw      x15, 60(sp)
    sw      x16, 64(sp)
    sw      x17, 68(sp)
    sw      x18, 72(sp)
    sw      x19, 76(sp)
    sw      x20, 80(sp)
    sw      x21, 84(sp)
    sw      x22, 88(sp)
    sw      x23, 92(sp)
    sw      x24, 96(sp)
    sw      x25, 100(sp)
    sw      x26, 104(sp)
    sw      x27, 108(sp)
    sw      x28, 112(sp)
    sw      x29, 116(sp)
    sw      x30, 120(sp)
    sw      x31, 124(sp)
    csrr    t0, mscratch
    sw      t0, 8(sp)
    csrr    t0, mepc
    sw      t0, F_PC(sp)
    csrr    t0, mcause
    sw      t0, F_CAUSE(sp)
    csrr    t0, mtval
    sw      t0, F_TVAL(sp)
    csrr    t0, mstatus
    sw      t0, F_MSTATUS(sp)
    li      sp, 0x800
    li      a0, 0x800
    lw      t0, 8(zero)
    bgeu    t0, a0, 4f          /* interrupted an application: ROM stack */
    mv      sp, t0              /* interrupted the ROM itself: stay on its stack */
4:  li      a0, FRAME           /* a0 = frame pointer */
    call    trap_handler
    li      sp, FRAME
    lw      t0, F_MSTATUS(sp)
    csrw    mstatus, t0
    lw      t0, F_PC(sp)
    csrw    mepc, t0
    lw      x1, 4(sp)
    lw      x3, 12(sp)
    lw      x4, 16(sp)
    lw      x5, 20(sp)
    lw      x6, 24(sp)
    lw      x7, 28(sp)
    lw      x8, 32(sp)
    lw      x9, 36(sp)
    lw      x10, 40(sp)
    lw      x11, 44(sp)
    lw      x12, 48(sp)
    lw      x13, 52(sp)
    lw      x14, 56(sp)
    lw      x15, 60(sp)
    lw      x16, 64(sp)
    lw      x17, 68(sp)
    lw      x18, 72(sp)
    lw      x19, 76(sp)
    lw      x20, 80(sp)
    lw      x21, 84(sp)
    lw      x22, 88(sp)
    lw      x23, 92(sp)
    lw      x24, 96(sp)
    lw      x25, 100(sp)
    lw      x26, 104(sp)
    lw      x27, 108(sp)
    lw      x28, 112(sp)
    lw      x29, 116(sp)
    lw      x30, 120(sp)
    lw      x31, 124(sp)
    lw      x2, 8(sp)
    mret

    .globl irq_off
irq_off:
    csrrci  a0, mstatus, 8
    ret

    .globl irq_restore
irq_restore:
    andi    a0, a0, 8
    csrs    mstatus, a0
    ret

    .globl cpu_wfi
cpu_wfi:                        /* sleep until an enabled interrupt is pending (also with MIE off) */
    wfi
    ret

    .globl mie_swap
mie_swap:
    csrrw   a0, mie, a0
    ret

    .globl irq_setup
irq_setup:
    li      t0, 0x800
    csrw    mie, t0             /* MEIE */
    ret
