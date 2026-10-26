#!/usr/bin/env python3
"""Check that ft-textinput reports focus changes and refreshes its state."""
import os
import socket
import struct
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
path = os.path.join(HERE, "..", "ft-textinput")
namespace = {"__name__": "ft_textinput_test"}
with open(path, encoding="utf-8") as f:
    exec(compile(f.read(), path, "exec"), namespace)

relay_name = f"ft_textinput_test_{os.getpid()}"
namespace["RELAY"] = "\0" + relay_name
relay = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
relay.bind("\0" + relay_name)
relay.settimeout(2)
client, server = socket.socketpair()
wayland_fd = os.dup(client.fileno())
client.close()
os.environ["WAYLAND_SOCKET"] = str(wayland_fd)
errors = []


def run():
    try:
        namespace["main"]()
    except BaseException as error:
        errors.append(error)


worker = threading.Thread(target=run, daemon=True)
worker.start()


def event(opcode, context):
    server.sendall(struct.pack("=II", 3, (12 << 16) | opcode) + struct.pack("=I", context))


def receive(expected, timeout=2):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        relay.settimeout(max(0.01, deadline - time.monotonic()))
        message = relay.recv(128).decode()
        if message == expected:
            return
    raise AssertionError(f"did not receive {expected!r}")


try:
    event(0, 42)
    receive("textfield 1")
    receive("textfield sync 1", 1.5)
    event(1, 42)
    receive("textfield 0")
    receive("textfield sync 0", 1.5)
finally:
    server.settimeout(1)
    drained = 0
    while drained < 20:
        data = server.recv(1024)
        if not data:
            break
        drained += len(data)
    server.shutdown(socket.SHUT_WR)
    server.close()
    worker.join(timeout=2)
    relay.close()

if worker.is_alive():
    raise AssertionError("ft-textinput did not exit after KWin disconnected")
if errors:
    raise errors[0]
print("focus transitions and 1-second heartbeats: ok")
