/* SPDX-License-Identifier: Apache-2.0
 * Copyright 2026 Franz Schöning, https://www.schoning.com
 */
/* Hermes-Lite 2 raw front-end image (hl2b5up_raw): front-end I/O block and transmit interlock registers,
 * rtl/hl2io.v. The same registers are reachable through the layer-1 bridge. See
 * docs/rawfront/PROTOCOL.md.
 */
#ifndef HL2IO_H
#define HL2IO_H

#define IO_BASE         0x40040000u
#define IO_ID           (IO_BASE + 0x00)    /* 0x494F3031 "IO01" */
#define IO_TX_PERMIT    (IO_BASE + 0x04)    /* write IO_PERMIT_KEY | bits: renews the lease */
#define IO_ILK_STATUS   (IO_BASE + 0x08)
#define IO_ILK_CLEAR    (IO_BASE + 0x0C)    /* write IO_CLEAR_KEY */
#define IO_LEASE_MS     (IO_BASE + 0x10)
#define IO_MAXKEY_S     (IO_BASE + 0x14)
#define IO_TEMP_LIMIT   (IO_BASE + 0x18)
#define IO_KEYTIME      (IO_BASE + 0x1C)
#define IO_WDOG         (IO_BASE + 0x20)    /* write IO_WDOG_KEY: kick and arm */
#define IO_WDOG_MS      (IO_BASE + 0x24)
#define IO_WDOG_DISARM  (IO_BASE + 0x28)    /* bridge only */
#define IO_CMD_DATA     (IO_BASE + 0x2C)
#define IO_CMD_ADDR     (IO_BASE + 0x30)    /* write: send (address, IO_CMD_DATA) on the command bus */
#define IO_I2C_XFER     (IO_BASE + 0x34)
#define IO_I2C_STATUS   (IO_BASE + 0x38)
#define IO_I2C_RDATA    (IO_BASE + 0x3C)
#define IO_BIAS_UNLOCK  (IO_BASE + 0x40)
#define IO_LED          (IO_BASE + 0x44)
#define IO_FAN          (IO_BASE + 0x48)
#define IO_INPUTS       (IO_BASE + 0x4C)
#define IO_ADC_SEQ      (IO_BASE + 0x50)

#define IO_PERMIT_KEY   0x54580000u         /* "TX" in [31:16] */
#define IO_PERMIT_KEYED (1u << 0)
#define IO_PERMIT_PTT   (1u << 1)
#define IO_PERMIT_CW    (1u << 2)
#define IO_CLEAR_KEY    0x434C5452u         /* "CLTR" */
#define IO_WDOG_KEY     0x57444F47u         /* "WDOG" */
#define IO_BIAS_KEY     0x42494153u         /* "BIAS" */

/* IO_CMD_ADDR read */
#define IO_CMD_BUSY     (1u << 31)

/* IO_I2C_XFER write: [31:30] bus 1..3, [24] read, [23] probe, [22:16] address, [15:8] register, [7:0] value */
#define IO_I2C_READ     (1u << 24)
#define IO_I2C_PROBE    (1u << 23)

/* IO_I2C_STATUS read */
#define IO_I2C_BUSY     (1u << 0)
#define IO_I2C_NACK     (1u << 1)
#define IO_I2C_REFUSED  (1u << 2)           /* bias guard */
#define IO_I2C_DROPPED  (1u << 3)           /* engine busy */
#define IO_I2C_PENDING  (1u << 4)           /* request not yet on the command bus */

#endif
