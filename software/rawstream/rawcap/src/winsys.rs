// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Franz Schöning, https://www.schoning.com
//
//! Minimal Windows FFI, hand-declared so the crate does not need a `windows`/`winapi`
//! dependency. Only the handful of kernel32 entry points rawcap needs.

use std::sync::atomic::{AtomicBool, Ordering};

#[allow(non_camel_case_types)]
type BOOL = i32;
#[allow(non_camel_case_types)]
type DWORD = u32;
#[allow(non_camel_case_types)]
type HANDLE = *mut core::ffi::c_void;

const THREAD_PRIORITY_TIME_CRITICAL: i32 = 15;
const THREAD_PRIORITY_HIGHEST: i32 = 2;
const PROCESS_HIGH_PRIORITY_CLASS: DWORD = 0x0000_0080;
const CTRL_C_EVENT: DWORD = 0;
const CTRL_BREAK_EVENT: DWORD = 1;
const CTRL_CLOSE_EVENT: DWORD = 2;

#[link(name = "kernel32")]
extern "system" {
    fn GetCurrentThread() -> HANDLE;
    fn GetCurrentProcess() -> HANDLE;
    fn SetThreadPriority(hthread: HANDLE, npriority: i32) -> BOOL;
    fn SetPriorityClass(hprocess: HANDLE, dwpriorityclass: DWORD) -> BOOL;
    fn SetConsoleCtrlHandler(
        handler: Option<unsafe extern "system" fn(DWORD) -> BOOL>,
        add: BOOL,
    ) -> BOOL;
}

static CTRL_C_FLAG: AtomicBool = AtomicBool::new(false);

unsafe extern "system" fn ctrl_handler(ctrl_type: DWORD) -> BOOL {
    match ctrl_type {
        CTRL_C_EVENT | CTRL_BREAK_EVENT | CTRL_CLOSE_EVENT => {
            CTRL_C_FLAG.store(true, Ordering::SeqCst);
            1 // handled
        }
        _ => 0,
    }
}

/// Install a Ctrl-C / Ctrl-Break / console-close handler. Call once at startup.
pub fn install_ctrlc_handler() {
    unsafe {
        SetConsoleCtrlHandler(Some(ctrl_handler), 1);
    }
}

/// True once Ctrl-C (or Ctrl-Break, or the console closing) has been seen.
pub fn ctrlc_pressed() -> bool {
    CTRL_C_FLAG.load(Ordering::SeqCst)
}

/// Raise the current thread to time-critical priority. Best-effort: failure is not fatal
/// (e.g. running without sufficient privilege), so this only prints a warning.
pub fn raise_current_thread_priority() {
    unsafe {
        let h = GetCurrentThread();
        if SetThreadPriority(h, THREAD_PRIORITY_TIME_CRITICAL) == 0 {
            // Fall back to "highest" if time-critical was refused.
            SetThreadPriority(h, THREAD_PRIORITY_HIGHEST);
        }
    }
}

/// Raise the whole process to the "High" priority class (not realtime — that needs admin and
/// can starve the rest of the system). Best-effort.
pub fn raise_process_priority() {
    unsafe {
        let h = GetCurrentProcess();
        SetPriorityClass(h, PROCESS_HIGH_PRIORITY_CLASS);
    }
}

const FIONREAD: i32 = 0x4004_667f;

#[link(name = "ws2_32")]
extern "system" {
    fn ioctlsocket(s: usize, cmd: i32, argp: *mut u32) -> i32;
}

/// Bytes currently queued (unread) in the socket's receive buffer. Used as an approximation
/// of "socket buffer high-water" — the checker/recv thread tracks the running max of this.
pub fn fionread(sock: &std::net::UdpSocket) -> u32 {
    use std::os::windows::io::AsRawSocket;
    let raw = sock.as_raw_socket() as usize;
    let mut val: u32 = 0;
    unsafe {
        ioctlsocket(raw, FIONREAD, &mut val as *mut u32);
    }
    val
}

const IPPROTO_UDP: i32 = 17;
const UDP_NOCHECKSUM: i32 = 1;

#[link(name = "ws2_32")]
extern "system" {
    fn setsockopt(s: usize, level: i32, optname: i32, optval: *const u8, optlen: i32) -> i32;
    fn WSAGetLastError() -> i32;
}

/// Send IPv4 UDP datagrams on this socket with a zero checksum (Winsock UDP_NOCHECKSUM).
pub fn set_udp_nochecksum(sock: &socket2::Socket) -> std::io::Result<()> {
    use std::os::windows::io::AsRawSocket;
    let one: u32 = 1;
    let r = unsafe {
        setsockopt(sock.as_raw_socket() as usize, IPPROTO_UDP, UDP_NOCHECKSUM, &one as *const u32 as *const u8, 4)
    };
    if r != 0 {
        return Err(std::io::Error::from_raw_os_error(unsafe { WSAGetLastError() }));
    }
    Ok(())
}
