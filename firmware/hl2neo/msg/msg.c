/* SPDX-License-Identifier: Apache-2.0
 * Copyright 2026 Franz Schöning, https://www.schoning.com
 */
/* HL2 message layer, protocol core. See msg.h and docs/rawfront/PROTOCOL.md.
 *
 * Far side -> radio
 *   reliable request (RELIABLE, seq s): executed once when s is the next sequence number (or RESET
 *   starts a session at s); the response packet is cached. A repeat of s gets the cached response
 *   again without executing anything. Any other s: dropped, a bare ACK tells the far side where we are.
 *   unreliable request (no RELIABLE): executed at once, response not cached (for idempotent requests
 *   such as the transmit permission renewal).
 * Radio -> far side
 *   responses: no sequence number (ACK_VALID, ack = request sequence);
 *   events: RELIABLE with their own sequence, one in flight, retransmitted after 50, 100, 200, 400,
 *   800 ms (6 sends), then dropped (the state is in every telemetry packet anyway);
 *   telemetry: unreliable, periodic once a session exists.
 */

#include "msg.h"

static uint32_t boot_id;
static uint16_t rx_seq;                     /* last reliable far-side sequence executed */
static uint8_t  session;

static uint8_t  cache[HM_HDR_SIZE + HM_MAX_PAYLOAD];
static uint32_t cache_len;

static uint16_t tx_seq;
static uint8_t  ev_pkt[HM_HDR_SIZE + HM_MAX_PAYLOAD];
static uint32_t ev_len;                     /* 0: no event in flight */
static uint32_t ev_due, ev_wait;
static uint8_t  ev_sends;

static uint32_t tele_period = 100, tele_due, tele_count;

static uint8_t  out[HM_HDR_SIZE + HM_MAX_PAYLOAD];

uint16_t hm_get16(const uint8_t *p) { return (uint16_t)(p[0] | (p[1] << 8)); }
uint32_t hm_get32(const uint8_t *p) { return p[0] | (p[1] << 8) | (p[2] << 16) | ((uint32_t)p[3] << 24); }
void hm_put16(uint8_t *p, uint32_t v) { p[0] = (uint8_t)v; p[1] = (uint8_t)(v >> 8); }
void hm_put32(uint8_t *p, uint32_t v) { hm_put16(p, v); hm_put16(p + 2, v >> 16); }

static uint32_t header(uint8_t *p, uint32_t flags, uint32_t seq, uint32_t len)
{
    p[0] = 'H';
    p[1] = 'M';
    p[2] = HM_VERSION;
    p[3] = (uint8_t)(flags | HM_F_ACK_VALID);
    hm_put32(p + 4, boot_id);
    hm_put16(p + 8, seq);
    hm_put16(p + 10, rx_seq);
    hm_put16(p + 12, len);
    hm_put16(p + 14, 0);
    return HM_HDR_SIZE + len;
}

void msg_init(uint32_t id)
{
    boot_id = id;
}

void msg_set_telemetry(uint32_t period_ms) { tele_period = period_ms; tele_due = hal_ms(); }
uint32_t msg_telemetry_period(void) { return tele_period; }

/* Execute the messages of a request payload; responses into dst. Returns the response payload length. */
static uint32_t execute(const uint8_t *d, uint32_t len, uint8_t *dst)
{
    uint32_t i = 0, o = 0;
    while (i + 6 <= len) {
        uint32_t mlen = hm_get16(d + i + 4);
        if (i + 6 + mlen > len || o + 7 > HM_MAX_PAYLOAD) break;
        uint32_t r = app_request(d[i], d[i + 1], d + i + 6, mlen, dst + o + 6, HM_MAX_PAYLOAD - o - 6);
        dst[o] = d[i];
        dst[o + 1] = d[i + 1] | HM_RESPONSE;
        dst[o + 2] = d[i + 2];
        dst[o + 3] = d[i + 3];
        hm_put16(dst + o + 4, r);
        o += 6 + r;
        i += 6 + mlen;
    }
    return o;
}

void msg_input(const uint8_t *d, uint32_t n)
{
    if (n < HM_HDR_SIZE || d[0] != 'H' || d[1] != 'M' || d[2] != HM_VERSION) return;
    uint32_t flags = d[3], seq = hm_get16(d + 8), len = hm_get16(d + 12);
    if (HM_HDR_SIZE + len > n || len > HM_MAX_PAYLOAD) return;

    if ((flags & HM_F_ACK_VALID) && ev_len && hm_get16(d + 10) == tx_seq) ev_len = 0;

    if (flags & HM_F_RELIABLE) {
        if (flags & HM_F_RESET) {
            if (!session || seq != rx_seq) {
                rx_seq = (uint16_t)(seq - 1);
                session = 1;
                cache_len = 0;
                ev_len = 0;
                tele_due = hal_ms();
            }
        }
        if (session && seq == (uint16_t)(rx_seq + 1)) {
            rx_seq = (uint16_t)seq;
            cache_len = header(cache, 0, 0, execute(d + HM_HDR_SIZE, len, cache + HM_HDR_SIZE));
            hal_send(cache, cache_len);
        } else if (session && seq == rx_seq && cache_len) {
            hal_send(cache, cache_len);         /* repeat: the response again, nothing executed */
        } else {
            hal_send(out, header(out, 0, 0, 0));
        }
    } else if (len) {
        hal_send(out, header(out, 0, 0, execute(d + HM_HDR_SIZE, len, out + HM_HDR_SIZE)));
    }
}

void msg_poll(void)
{
    uint32_t now = hal_ms(), n;
    if (!session) return;

    if (ev_len) {
        if (now - ev_due < 0x80000000u) {
            if (ev_sends >= 6) {
                ev_len = 0;
            } else {
                hm_put16(ev_pkt + 10, rx_seq);
                hal_send(ev_pkt, ev_len);
                ev_sends++;
                ev_due = now + ev_wait;
                if (ev_wait < 800) ev_wait <<= 1;
            }
        }
    } else if ((n = app_event(ev_pkt + HM_HDR_SIZE + 6, HM_MAX_PAYLOAD - 6))) {
        ev_pkt[HM_HDR_SIZE] = HM_C_EVENT;
        ev_pkt[HM_HDR_SIZE + 1] = 1;
        hm_put16(ev_pkt + HM_HDR_SIZE + 2, 0);
        hm_put16(ev_pkt + HM_HDR_SIZE + 4, n);
        ev_len = header(ev_pkt, HM_F_RELIABLE, ++tx_seq, n + 6);
        ev_sends = 0;
        ev_wait = 50;
        ev_due = now;
    }

    if (tele_period && now - tele_due < 0x80000000u) {
        tele_due = now + tele_period;
        out[HM_HDR_SIZE] = HM_C_TELEMETRY;
        out[HM_HDR_SIZE + 1] = 1;
        hm_put16(out + HM_HDR_SIZE + 2, 0);
        hm_put32(out + HM_HDR_SIZE + 6, tele_count++);
        n = 4 + app_telemetry(out + HM_HDR_SIZE + 10, HM_MAX_PAYLOAD - 10);
        hm_put16(out + HM_HDR_SIZE + 4, n);
        hal_send(out, header(out, 0, 0, n + 6));
    }
}
