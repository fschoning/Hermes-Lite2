// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Franz Schöning, https://www.schoning.com
//
//! Single-producer/single-consumer ring of preallocated fixed-size buffers.
//! The receive thread does nothing but `recv_from` into the next slot; the checker thread
//! drains slots and does all the analysis. No allocation happens on the hot path once the
//! ring is built.

use std::cell::UnsafeCell;
use std::sync::atomic::{AtomicU64, AtomicUsize, Ordering};

/// Max bytes held per slot. Comfortably above the largest UDP payload rawcap will see
/// (9,000-byte jumbo payload plus the 20-byte header, plus slack).
pub const MAX_FRAME: usize = 9200;

struct Slot {
    buf: UnsafeCell<[u8; MAX_FRAME]>,
    len: AtomicUsize, // 0 = empty; a filled slot always has len >= protocol::HEADER_LEN
    ts: AtomicU64,    // receive time, ns since the receiver's epoch
}

// Safety: exactly one thread ever writes a given slot's buf before publishing `len` with
// Release, and exactly one thread ever reads it after observing that `len` with Acquire.
unsafe impl Sync for Slot {}

pub struct Ring {
    slots: Vec<Slot>,
    size: usize,
    head: AtomicUsize, // next slot index the producer will write (monotonic, wraps via % size)
    tail: AtomicUsize, // next slot index the consumer will read
    pub drops: AtomicUsize, // frames dropped because the ring was full
}

impl Ring {
    pub fn new(size: usize) -> Self {
        let mut slots = Vec::with_capacity(size);
        for _ in 0..size {
            slots.push(Slot {
                buf: UnsafeCell::new([0u8; MAX_FRAME]),
                len: AtomicUsize::new(0),
                ts: AtomicU64::new(0),
            });
        }
        Ring {
            slots,
            size,
            head: AtomicUsize::new(0),
            tail: AtomicUsize::new(0),
            drops: AtomicUsize::new(0),
        }
    }

    /// Producer side: get a mutable scratch buffer to `recv_from` into, up to MAX_FRAME bytes.
    /// Returns None if the ring is full (caller should drop the packet and count it lost).
    pub fn try_reserve(&self) -> Option<(usize, &mut [u8; MAX_FRAME])> {
        let head = self.head.load(Ordering::Relaxed);
        let tail = self.tail.load(Ordering::Acquire);
        if head - tail >= self.size {
            return None;
        }
        let idx = head % self.size;
        // Safety: single producer, and this slot's previous consumer read (if any) happened
        // before `tail` advanced past it, which we just observed with Acquire.
        let buf = unsafe { &mut *self.slots[idx].buf.get() };
        Some((idx, buf))
    }

    /// Publish a reserved slot with the number of valid bytes written.
    pub fn publish(&self, idx: usize, len: usize, ts_ns: u64) {
        self.slots[idx].ts.store(ts_ns, Ordering::Release);
        self.slots[idx].len.store(len, Ordering::Release);
        self.head.fetch_add(1, Ordering::Release);
    }

    /// Consumer side: borrow the next ready slot's data, if any.
    pub fn try_pop(&self) -> Option<(usize, &[u8])> {
        let tail = self.tail.load(Ordering::Relaxed);
        let head = self.head.load(Ordering::Acquire);
        if tail == head {
            return None;
        }
        let idx = tail % self.size;
        let len = self.slots[idx].len.load(Ordering::Acquire);
        // Safety: single consumer, data was published with Release before head advanced.
        let buf = unsafe { &*self.slots[idx].buf.get() };
        Some((idx, &buf[..len]))
    }

    /// Consumer side: receive time of a popped slot (ns since the receiver's epoch).
    pub fn ts(&self, idx: usize) -> u64 {
        self.slots[idx].ts.load(Ordering::Acquire)
    }

    /// Consumer side: release a slot after processing it.
    pub fn release(&self, _idx: usize) {
        self.tail.fetch_add(1, Ordering::Release);
    }
}
