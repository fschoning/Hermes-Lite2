/* SPDX-License-Identifier: Apache-2.0
 * Copyright 2026 Franz Schöning, https://www.schoning.com
 */
/* Hermes-Lite 2 soft CPU, NEORV32 rv32imc (hl2b5up_neo): memory map, registers and the boot ROM API.
 * Shared by the boot ROM and applications. See docs/rawfront/RISCV.md.
 * Same memory map as the VexRiscv image (hl2b5up_cpu), except: SYS_INFO map version 2, WFI instead of
 * SYS_SLEEP, saved-firmware header format 2 (images for the other core are refused).
 */
#ifndef HL2CPU_H
#define HL2CPU_H

#include <stdint.h>

#define REG(a) (*(volatile uint32_t *)(a))
#define REG8(a) (*(volatile uint8_t *)(a))

/* Memory */
#define RAM_BASE        0x00000000u     /* the boot ROM workspace is the first 2 kB of RAM */
#define WS_SIZE         0x800u
#define RAM_SIZE        0x4000u         /* 16 kB (SYS_INFO [15:8]) */
#define APP_BASE        0x00000800u     /* applications load here */
#define ROM_BASE        0x00010000u     /* reset vector */

/* Packet buffer shared with the network side: one byte per 32-bit word, byte n at 0x20000000 + 4n */
#define PBUF(n)         REG(0x20000000u + ((n) << 2))
#define PBUF_TX         0x100u          /* 256-byte transmit buffer */
#define PBUF_TX_SIZE    256u
#define PBUF_RX         0x200u          /* 512-byte receive ring: datagrams as 2-byte length + bytes */
#define PBUF_RX_MASK    511u

/* Read-only mirror of the layer-1 bridge status registers (writes ignored) */
#define STAT_ID         0x40000000u
#define STAT_VERSION    0x40000004u
#define STAT_CAPS       0x4000000Cu
#define STAT_TEMP       0x40003000u     /* 12-bit slow ADC code */
#define STAT_FWD        0x40003004u
#define STAT_REV        0x40003008u
#define STAT_BIAS       0x4000300Cu
#define STAT_INPUTS     0x40004000u
#define STAT_TXSTAT     0x40007000u

/* System block */
#define SYS_BASE        0x40010000u
#define SYS_ID          (SYS_BASE + 0x00)   /* 0x52563332 "RV32" */
#define SYS_INFO        (SYS_BASE + 0x04)   /* [31:24] map version (1 VexRiscv, 2 NEORV32), [23:16] ROM kB, [15:8] RAM kB */
#define MAP_VERSION     2u
#define SYS_CTRL        (SYS_BASE + 0x08)   /* written by the bridge only, see CTRL_* */
#define SYS_BOOT_ADDR   (SYS_BASE + 0x0C)   /* written by the bridge only */
#define SYS_FW_STATUS   (SYS_BASE + 0x10)   /* firmware writes, bridge reads, FWS_* */
#define SYS_FW_RESULT   (SYS_BASE + 0x14)   /* result of the last save/erase/boot, FWR_* */
#define SYS_MS          (SYS_BASE + 0x18)   /* milliseconds since power-up */
#define SYS_TIMER_CMP   (SYS_BASE + 0x1C)   /* timer IRQ pending while SYS_MS >= this value */
#define SYS_IRQ_EN      (SYS_BASE + 0x20)   /* IRQ_* */
#define SYS_IRQ_PEND    (SYS_BASE + 0x24)   /* IRQ_* levels (move SYS_TIMER_CMP to clear the timer) */
#define SYS_LED         (SYS_BASE + 0x28)   /* bit 0 LED D5 on, bit 1 CPU drives LED D5 */
#define SYS_STATUS      (SYS_BASE + 0x2C)   /* [15:0] CPU resets since power-up */
#define SYS_SCRATCH     (SYS_BASE + 0x30)
#define SYS_SLEEP       (SYS_BASE + 0x34)   /* VexRiscv image only; NEORV32 ignores it: use the wfi instruction */
#define SYS_STEP        (SYS_BASE + 0x38)   /* bit 0 holds the machine software interrupt (mcause 0x80000003)
                                               active: the boot ROM's single step for gdb */

#define CTRL_RESET      (1u << 0)   /* CPU held in reset */
#define CTRL_HALT       (1u << 1)   /* CPU bus frozen: the CPU stops, its state is kept */
#define CTRL_STAY_ROM   (1u << 2)   /* boot ROM: do not start the saved firmware */
#define CTRL_BOOT_RAM   (1u << 3)   /* boot ROM: jump to SYS_BOOT_ADDR after reset */

#define IRQ_TIMER       (1u << 0)
#define IRQ_PKT         (1u << 1)   /* a datagram is waiting in the receive ring */

/* Packet interface on the aux UDP port 1027 */
#define PKT_BASE        0x40020000u
#define PKT_RX_WR       (PKT_BASE + 0x00)   /* receive ring write pointer (network side), 0..1023 */
#define PKT_RX_RD       (PKT_BASE + 0x04)   /* receive ring read pointer (CPU) */
#define PKT_TX_LEN      (PKT_BASE + 0x08)   /* write N: send PBUF_TX[0..N-1] as one datagram; read: TX_* */
#define PKT_COUNT       (PKT_BASE + 0x0C)   /* [15:0] datagrams dropped (ring full), [31:16] sent */
#define TX_BUSY         (1u << 31)          /* the previous datagram is not sent yet */
#define TX_DEST         (1u << 30)          /* a PC has sent to port 1027: destination known */

/* Flash sector 0x1F0000-0x1FFFFF of the EPCS16 (address check in the gateware) */
#define FL_BASE         0x40030000u
#define FL_ADDR         (FL_BASE + 0x00)
#define FL_DATA         (FL_BASE + 0x04)    /* write: byte for FL_CMD_SHIFT; read: last byte read */
#define FL_CMD          (FL_BASE + 0x08)    /* write: command; read: FL_ST_* */
#define FL_CMD_ERASE    1u                  /* erase the sector 0x1F0000 (address fixed in the gateware) */
#define FL_CMD_SHIFT    2u                  /* add FL_DATA to the 256-byte page buffer */
#define FL_CMD_PROGRAM  3u                  /* program the page buffer at FL_ADDR */
#define FL_CMD_READ     4u                  /* read one byte at FL_ADDR into FL_DATA */
#define FL_ST_BUSY      (1u << 0)
#define FL_ST_REJECTED  (1u << 1)           /* last command refused: address outside the sector */
#define FL_ST_LOCKED    (1u << 2)           /* network flashing started: CPU access locked until reboot */
#define FL_ST_ILLEGAL   (1u << 3)           /* the ASMI block reported an illegal write or erase */

#define FW_SECTOR       0x1F0000u
#define FW_SECTOR_SIZE  0x10000u

/* Saved firmware header at FW_SECTOR (little-endian) */
#define FW_MAGIC        0x46324C48u         /* "HL2F" */
#define FW_FORMAT       0x00020002u         /* [15:0] header version 2, [31:16] target 2: NEORV32 rv32imc,
                                               memory map 2 (the VexRiscv ROM wrote 0x00000001) */
#define FW_HDR_SIZE     32u
struct fw_header {
    uint32_t magic;
    uint32_t format;        /* FW_FORMAT */
    uint32_t load_addr;
    uint32_t length;
    uint32_t entry;
    uint32_t version;
    uint32_t image_crc;     /* CRC-32 (IEEE, as zlib.crc32) of the image */
    uint32_t header_crc;    /* CRC-32 of the first 28 header bytes */
};

/* SYS_FW_STATUS written by the boot ROM ([31:24] state, [7:0] detail) */
#define FWS_ROM_BUSY    0x01000000u
#define FWS_ROM_IDLE    0x02000000u
#define FWS_APP         0x03000000u
#define FWS_STOPPED     0x04000000u         /* trap or debugger stop; detail = signal number */

/* SYS_FW_RESULT: [31:24] operation ('S' save, 'E' erase, 'B' boot), [23:16] sequence, [7:0] code */
#define FWR_OK          0u
#define FWR_BAD_ARGS    1u
#define FWR_CRC_MISMATCH 2u
#define FWR_FLASH_ERR   3u
#define FWR_VERIFY_ERR  4u
#define FWR_LOCKED      5u
#define FWR_NO_IMAGE    6u
#define FWR_BAD_IMAGE   7u
#define FWR_WRONG_CPU   8u                  /* saved firmware has another header format: built for another CPU */

/* Boot ROM API: the ROM stores a pointer to this table at ROM_BASE + 8 */
#define ROM_API_MAGIC   0x41524C48u         /* "HLRA" */
struct rom_api {
    uint32_t magic;
    uint32_t version;
    void     (*con_write)(const char *s, uint32_t n);        /* console output (hl2fw.py or gdb) */
    void     (*set_irq_handler)(void (*h)(uint32_t mcause)); /* timer IRQ and exceptions not for gdb */
    uint32_t (*crc32)(uint32_t crc, const uint8_t *p, uint32_t n);
};
#define ROM_API ((const struct rom_api *)REG(ROM_BASE + 8))

#endif
