/* ==========================================================================
 * GENERATED FILE - DO NOT EDIT.
 * Source: abi/unet_abi.toml in unet_libs_core. Regenerate with
 * tools/gen_bindings.py gen --target solidc.
 * ========================================================================== */

/*
 * UNET - universal network DLL contract (libman 1.3 / L1)
 * Shared ABI for UNETESP.DLL (ESP8266 / ESP-AT) and the future
 * UNETRTL.DLL (RTL8019A). One interface, swappable backend.
 *
 * Consumers (asm / C / Pascal) load a backend DLL through libman 1.3
 * (l_load / l_call / l_free) and drive the network through the numbered
 * functions below. This file is the single source of truth for the
 * function numbers, register ABI, error codes, capability bits, GETINFO
 * fields and options. It is FROZEN: new capabilities extend the reserved
 * slots and the caps bitmask, never renumber existing functions.
 *
 * -----------------------------------------------------------------------
 * Calling convention (libman l_call):
 *   Consumer: HL = handle, B = function number, then CALL l_call.
 *   Arguments are passed ONLY in A, DE, IX, IY (HL and BC are consumed by
 *   the libman dispatcher). Results come back in A, DE, IX, IY.
 *   Every UNET function returns its status in A (0 = NERR_OK, else a
 *   NERR_* code). The libman dispatcher does NOT propagate a user
 *   function's carry flag, so consumers MUST test A, not CF.
 *
 * Memory / window discipline (enforced and documented):
 *   - Load the DLL into window 1 (0x4000) or window 2 (0x8000) only.
 *     NEVER window 3 (0xC000): the ESP backend maps the ISA UART there
 *     during every call and would swap its own code out. UNETESP refuses
 *     to initialise if it detects it was loaded into window 3.
 *   - All caller buffers (host/port strings, send/recv payload, GETINFO
 *     destinations) must live BELOW 0xC000 and OUTSIDE the 16 KB window
 *     the DLL was loaded into - the WHOLE buffer, not just its first byte;
 *     both ends of the range are validated. Violations return NERR_PARAM.
 *     WIN0 pointers are accepted: mapping a caller-owned page over DSS/system
 *     memory there, and restoring it safely, is entirely the caller's duty.
 *   - Host strings are limited to 128 bytes, port strings to 15 bytes
 *     (longer arguments return NERR_PARAM).
 *   - Keep at least ~256 bytes of free stack across a call.
 *   - The library is NOT reentrant; one call at a time.
 */

#ifndef _UNET_H_
#define _UNET_H_

/* ABI version reported by GETCAPS in IX (major<<8 | minor) */
#define UNET_ABI_VERSION 0x0100 /* ABI version reported by GETCAPS in IX (major<<8 | minor). Consumers should verify the major byte before relying on the numbered functions. */

/* Function numbers (index passed in B to l_call) */
#define UNET_FN_INIT 0 /* libman load hook. Checks window, XOR A. Do not call directly. */
#define UNET_FN_FINI 1 /* libman free hook. Closes any open link, A=0. Do not call directly. */
#define UNET_FN_GETCAPS 2 /* -> A=0, DE=caps bitmask, IX=UNET_ABI_VERSION. Callable before NETINIT. */
#define UNET_FN_NETINIT 3 /* -> A (0 / NERR_NONET / NERR_HW / NERR_BUSY). Bring the link layer up. */
#define UNET_FN_NETDONE 4 /* Close the active channel, leave the network up. A=0. Idempotent. */
/*
 * A=channel, DE=host ASCIIZ, IX=port ASCIIZ -> A
 *   channel 0..1 when GETCAPS reports CAP_MULTICHAN,
 *   otherwise channel 0 only (else NERR_PARAM)
 *   retries internally while the backend reports "busy"
 */
#define UNET_FN_CONNECT 5
/*
 * A=channel, DE=buffer, IX=length -> A, DE=bytes sent
 *   TCP: chunked internally at 2048 (ESP-AT CIPSEND cap).
 *   UDP: one datagram per call, length > 1472 -> NERR_PARAM.
 *   Peer data arriving DURING a send may be dropped by the ESP
 *   backend - drain RECV before sending (see docs/UNETAPI.md).
 *   With UNET_OPT_SENDSLICE > 0 may return NERR_AGAIN:
 *   repeat the same call to continue the transaction.
 */
#define UNET_FN_SEND 6
/*
 * A=channel, DE=buffer, IX=max, IY=timeout_ms -> A, DE=received, IX=flags
 *   A=NERR_OK, DE=0            : nothing for this channel yet
 *                                (timeout, or the backend buffered
 *                                data for the OTHER channel - see
 *                                UNET_RXF_XCHAN)
 *   A=NERR_CLOSED             : peer closed (any DE bytes are valid first)
 *   IX flags: see UNET_RXF_* below
 */
#define UNET_FN_RECV 7
#define UNET_FN_CLOSE 8 /* A=channel -> A. Idempotent. Closes ONE channel; use NETDONE to close every channel at once. */
/*
 * A=channel -> A=0, DE=state (see UNET_ST_* below)
 *   A=0xFF     -> network status WITHOUT touching hardware:
 *                 A=0/NERR_NONET, DE bit0 env configured, bit1 NETINIT done
 */
#define UNET_FN_STATUS 9
/*
 * A=channel, DE=host, IX=rport ASCIIZ, IY=lport ASCIIZ|0 -> A
 *   retries internally while the backend reports "busy"
 */
#define UNET_FN_UDPOPEN 10
#define UNET_FN_RESOLVE 11 /* DE=host ASCIIZ, IX=dest(>=16 bytes) -> A, dest="a.b.c.d",0 */
#define UNET_FN_PING 12 /* DE=host ASCIIZ, IY=timeout_ms -> A, DE=round-trip ms */
/*
 * drop RTS so a slow consumer can catch up -> A
 *   NERR_STATE before NETINIT (UART base not known yet)
 */
#define UNET_FN_RXPAUSE 13
#define UNET_FN_RXRESUME 14 /* raise RTS to resume receive -> A (NERR_STATE before NETINIT) */
/*
 * A=field id, DE=dest, IX=max(incl NUL) -> A; empty string if
 *   unset. IX=0 -> NERR_PARAM.
 */
#define UNET_FN_GETINFO 15
/*
 * DE=dest, IX=max -> A=0; copies the TAIL of the last AT/driver
 *   response (the final ERROR/CLOSED line survives truncation)
 */
#define UNET_FN_LASTERR 16
#define UNET_FN_SETOPT 17 /* A=option id, DE=value -> A */
#define UNET_FN_RESERVED18 18 /* reserved -> NERR_NOTSUP */
#define UNET_FN_RESERVED19 19
#define UNET_FN_RESERVED20 20
#define UNET_FN_RESERVED21 21
#define UNET_FN_RESERVED22 22
#define UNET_FN_RESERVED23 23
#define UNET_FN_COUNT 24 /* total slots in the jump table */

/* Error codes (returned in A). Superset of the ftpclient NERR_* set. */
#define NERR_OK 0 /* success */
#define NERR_HW 1 /* network hardware not found / not responding */
#define NERR_NONET 2 /* network not brought up (env not published) */
#define NERR_DNS 3 /* host name could not be resolved */
#define NERR_CONNECT 4 /* TCP/UDP connect failed */
#define NERR_SEND 5 /* send failed */
#define NERR_RECV_TIMEOUT 6 /* receive timed out (reserved; RECV returns OK/DE=0 for idle) */
#define NERR_CLOSED 7 /* connection closed by peer */
#define NERR_CANCEL 8 /* user cancelled (Esc / Ctrl+Z) - only when SETOPT CANCELKEYS=1 */
#define NERR_PARAM 9 /* invalid argument (bad channel, buffer out of range, ...) */
#define NERR_NOTSUP 10 /* operation not supported by this backend/firmware */
#define NERR_STATE 11 /* wrong state (e.g. CONNECT before NETINIT, or already open) */
#define NERR_TIMEOUT 12 /* generic operation timeout (ping / resolve) */
#define NERR_BUSY 13 /* backend busy (ESP IP stack still warming up) */
#define NERR_PROTO 14 /* unexpected/protocol error in backend response */
/*
 * SEND suspended: the link was silent for one
 *   UNET_OPT_SENDSLICE quantum. Repeat the SAME call
 *   (same channel/buffer/length) to continue the
 *   transaction; DE = bytes confirmed so far. Only
 *   backends with UNET_CAP_ASYNCSEND return this.
 */
#define NERR_AGAIN 15

/* Capability bits (returned in DE by GETCAPS) */
#define UNET_CAP_TCP 1 /* TCP client connect/send/recv/close */
#define UNET_CAP_UDP 2 /* connected UDP */
#define UNET_CAP_RESOLVE 4 /* RESOLVE returns a dotted-quad (may still NERR_NOTSUP at runtime) */
#define UNET_CAP_PING 8 /* ICMP-style ping */
#define UNET_CAP_MULTICHAN 16 /* channels 0 and 1 can be open at the same time (UNETESP >= 0.3; UNETRTL: 0) */
#define UNET_CAP_LISTEN 32 /* inbound/listen sockets (neither backend: 0) */
#define UNET_CAP_RAWETH 64 /* raw Ethernet frames (RTL only) */
#define UNET_CAP_TRANSPARENT 128 /* ESP transparent byte-pipe mode (reserved extension) */
#define UNET_CAP_RXFLOW 256 /* consumer must honour RXPAUSE/RXRESUME for lossless receive */
#define UNET_CAP_ASYNCSEND 512 /* SEND can suspend with NERR_AGAIN instead of blocking (see UNET_OPT_SENDSLICE); UNETRTL: 0 */
/*
 * UNETESP v1 advertises: TCP | UDP | RESOLVE | PING | RXFLOW = 0x010F
 * UNETESP v0.3 adds MULTICHAN = 0x011F
 * UNETESP v0.4 adds ASYNCSEND = 0x031F
 */

/* STATUS(channel) state bits (returned in DE) */
#define UNET_ST_CONN 2 /* channel is connected (last known state) */
/*
 * received data is buffered for this channel and
 *   not delivered yet. OPTIONAL: only backends that
 *   buffer per channel set it (UNETESP >= 0.3 with
 *   CAP_MULTICHAN); UNETRTL never does, so consumers
 *   must treat "not set" as "unknown", not as "empty"
 */
#define UNET_ST_RXPEND 4

/* RECV flag bits (returned in IX) */
/*
 * oversized datagram was truncated. UNETESP never
 *   truncates - its tail arrives on the next call
 *   with UNET_RXF_MORE set.
 */
#define UNET_RXF_TRUNC 1
#define UNET_RXF_MORE 2 /* more data is already buffered for this channel */
/*
 * UART overrun (LSR OE) or a dropped buffered frame
 *   since the last call; per channel from v0.3
 */
#define UNET_RXF_LOST 4
/*
 * data is pending on the OTHER channel (v0.3,
 *   optional). A read that returns DE=0 with this bit
 *   set means "switch channels", not "link idle"
 */
#define UNET_RXF_XCHAN 8

/* GETINFO field ids (A on entry) */
#define UNET_IF_BACKEND 0 /* short backend tag, e.g. "ESP" / "RTL" */
#define UNET_IF_IP 1 /* station IPv4, dotted quad */
#define UNET_IF_MASK 2 /* netmask */
#define UNET_IF_GW 3 /* gateway */
#define UNET_IF_MAC 4 /* station MAC */
#define UNET_IF_DNS1 5 /* primary DNS */
#define UNET_IF_DNS2 6 /* secondary DNS */
#define UNET_IF_IPSRC 7 /* "STATIC" / "DHCP" */
#define UNET_IF_SSID 8 /* Wi-Fi SSID (ESP only; empty on RTL) */
#define UNET_IF_BAUD 9 /* UART baud (ESP only; empty on RTL) */
#define UNET_IF_NTP 10 /* configured NTP server */
#define UNET_IF_TZ 11 /* timezone */
#define UNET_IF_HW 12 /* hardware descriptor ("<slot>/#<base>") */

/* SETOPT option ids (A) and values (DE) */
#define UNET_OPT_CANCELKEYS 1 /* DE=1 poll Esc/Ctrl+Z during blocking UART loops (default 0) */
/*
 * DE=1/4/8/14 - RX FIFO auto-RTS trigger level (ESP; default 4).
 *   NERR_STATE before NETINIT (UART base not known yet).
 *   TR4 is the stable compromise: TR1 throttles ESP to ~1 KB/s,
 *   while TR8 leaves too little headroom and causes overruns. Use
 *   other values only for field diagnostics on specific hardware.
 */
#define UNET_OPT_RXTRIG 2
/*
 * DE=ms of link SILENCE after which SEND suspends with
 *   NERR_AGAIN instead of blocking (0 = blocking, the default;
 *   minimum 50 is enforced). Requires UNET_CAP_ASYNCSEND.
 *   While a send is suspended, RECV serves only already
 *   buffered data and returns immediately, and other
 *   transmitting calls return NERR_BUSY without touching
 *   the UART (see docs/UNETAPI.md).
 */
#define UNET_OPT_SENDSLICE 3

/* UNETLD loader error codes, stored in UNETLD.ERROR and returned in A on CF=1 (asm) / false (Pascal/C). */
#define UNETLD_E_NOENV 1 /* NET is not set or empty */
#define UNETLD_E_BADVALUE 2 /* NET is not 3-4 chars of [A-Z0-9] (raw value in ENV_VALUE) */
#define UNETLD_E_LOAD 3 /* l_load failed (see LIBMAN.l_reason/l_dss_error/...) */
#define UNETLD_E_INFO 4 /* l_info failed */
#define UNETLD_E_NAME 5 /* the loaded DLL's L1 name does not match NET */
#define UNETLD_E_CALL 6 /* libman dispatcher (CF) failure, or GETCAPS returned a non-OK status during LOAD */
#define UNETLD_E_ABI 7 /* GETCAPS major ABI byte != HIGH(UNET_ABI_VERSION) */
#define UNETLD_E_STATUS 8 /* STATUS(0FFh) returned neither NERR_OK nor NERR_NONET */
#define UNETLD_E_NETINIT 9 /* NETINIT returned a non-OK status (see LAST_STATUS) */

/* UNETLD loader state flags, stored in UNETLD.FLAGS. */
#define UNETLD_F_LOADED 1 /* bit0 of FLAGS: DLL handle is open */
#define UNETLD_F_NETINIT 2 /* bit1 of FLAGS: NETINIT succeeded */

#endif /* _UNET_H_ */
