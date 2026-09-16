/* SPDX-License-Identifier: Apache-2.0
 * Copyright 2026 Franz Schöning, https://www.schoning.com
 */
/* HL2 message layer (layer 2 on the aux UDP port 1027): reliable requests, cached responses, reliable
 * events, unreliable telemetry. Portable C99: no hardware access, explicit little-endian packing, no
 * malloc. The application supplies the hooks at the end. Protocol: docs/rawfront/PROTOCOL.md.
 */
#ifndef HL2_MSG_H
#define HL2_MSG_H

#include <stdint.h>

#define HM_VERSION      1u
#define HM_HDR_SIZE     16u
#define HM_MAX_PAYLOAD  240u                /* datagram <= 256 bytes (the HL2 CPU transmit buffer) */

#define HM_F_RELIABLE   0x01u               /* consumes a sequence number, must be acknowledged */
#define HM_F_ACK_VALID  0x02u               /* the ack field acknowledges the peer's reliable packets */
#define HM_F_RESET      0x04u               /* far side: first reliable packet of a new session */

/* message classes */
#define HM_C_SYS        0u
#define HM_C_REG        1u
#define HM_C_I2C        2u
#define HM_C_RF         3u
#define HM_C_TELEMETRY  5u
#define HM_C_EVENT      6u
#define HM_RESPONSE     0x80u               /* opcode bit of a response */

/* response status (first body byte) */
#define HM_OK           0u
#define HM_E_UNKNOWN    0x10u               /* unknown class or opcode */
#define HM_E_LENGTH     0x11u               /* body too short or too long */
#define HM_E_REFUSED    0x12u               /* address or value not allowed */
#define HM_E_BUSY       0x13u               /* the gateware did not accept the request in time */

void msg_init(uint32_t boot_id);
void msg_input(const uint8_t *d, uint32_t n);       /* one received datagram */
void msg_poll(void);                                /* call often: retransmissions, telemetry, events */
void msg_set_telemetry(uint32_t period_ms);
uint32_t msg_telemetry_period(void);

uint16_t hm_get16(const uint8_t *p);
uint32_t hm_get32(const uint8_t *p);
void hm_put16(uint8_t *p, uint32_t v);
void hm_put32(uint8_t *p, uint32_t v);

/* hooks provided by the application */
uint32_t hal_ms(void);
void     hal_send(const uint8_t *d, uint32_t n);
/* handle one request message; write the response body (status first) to out, return its length */
uint32_t app_request(uint8_t cls, uint8_t op, const uint8_t *body, uint32_t len, uint8_t *out, uint32_t max);
/* telemetry body; event body or 0 when nothing changed */
uint32_t app_telemetry(uint8_t *out, uint32_t max);
uint32_t app_event(uint8_t *out, uint32_t max);

#endif
