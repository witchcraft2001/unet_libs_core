#!/usr/bin/env python3
"""UDP echo server for the UDPECHO.EXE example.

Run this on a host reachable from the Sprinter, then on the Sprinter:
    UDPECHO <this host's IP> 7777

Adapted from sprinter_wifi/network/examples/UDP_ECHO.PY.
"""
import socket
import sys


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 7777
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", port))
    print(f"UDP echo on {port}", flush=True)

    while True:
        data, addr = sock.recvfrom(2048)
        print(addr, data, flush=True)
        sock.sendto(data, addr)


if __name__ == "__main__":
    main()
