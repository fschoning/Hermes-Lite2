/* SPDX-License-Identifier: Apache-2.0
 * Copyright 2026 Franz Schöning, https://www.schoning.com
 */
/* Boot ROM: code and constants in the ROM, writable data in the workspace (first 2 kB of RAM). */
OUTPUT_ARCH(riscv)
ENTRY(_start)
MEMORY
{
    ROM (rx)  : ORIGIN = 0x00010000, LENGTH = 16384
    WS  (rw)  : ORIGIN = 0x00000090, LENGTH = 0x770
}
SECTIONS
{
    .text : {
        KEEP(*(.text.start))
        *(.text .text.*)
        *(.rodata .rodata.* .srodata .srodata.*)
        . = ALIGN(4);
    } > ROM
    .data : { *(.data .data.* .sdata .sdata.*) } > WS
    ASSERT(SIZEOF(.data) == 0, "boot ROM must not have initialised data")
    .bss (NOLOAD) : {
        __bss_start = .;
        *(.bss .bss.* .sbss .sbss.* COMMON)
        . = ALIGN(4);
        __bss_end = .;
    } > WS
    ASSERT(0x800 - __bss_end >= 0x280, "boot ROM workspace: less than 640 bytes of stack")
    /DISCARD/ : { *(.comment) *(.riscv.attributes) *(.note*) *(.eh_frame*) }
}
