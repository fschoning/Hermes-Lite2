/* SPDX-License-Identifier: Apache-2.0
 * Copyright 2026 Franz Schöning, https://www.schoning.com
 */
/* Applications: RAM from 0x800 (after the boot ROM workspace) to the end of the 16 kB RAM. */
OUTPUT_ARCH(riscv)
ENTRY(_start)
MEMORY
{
    RAM (rwx) : ORIGIN = 0x00000800, LENGTH = 0x3800
}
PHDRS
{
    image PT_LOAD;                      /* one segment, no ELF headers in it (hl2fw.py loads segments) */
}
SECTIONS
{
    .text : {
        KEEP(*(.text.start))
        *(.text .text.*)
        *(.rodata .rodata.* .srodata .srodata.*)
        *(.data .data.* .sdata .sdata.*)
        . = ALIGN(4);
    } > RAM :image
    .bss (NOLOAD) : {
        __bss_start = .;
        *(.bss .bss.* .sbss .sbss.* COMMON)
        . = ALIGN(4);
        __bss_end = .;
    } > RAM :image
    __stack_top = ORIGIN(RAM) + LENGTH(RAM);
    ASSERT(__stack_top - __bss_end >= 0x400, "application: less than 1 kB of stack")
    /DISCARD/ : { *(.comment) *(.riscv.attributes) *(.note*) *(.eh_frame*) }
}
