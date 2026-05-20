"""Flush the password cache from the running agent."""

import socket
import sys

from . import utils

try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(3)
    s.connect((utils.AGENT_HOST, utils.AGENT_PORT))
    s.sendall(b"FLUSH\r\n")
    resp = b""
    while b"\r\n" not in resp:
        chunk = s.recv(4096)
        if not chunk:
            break
        resp += chunk
    s.close()
    if resp.strip() == b"OK":
        print("Password cache cleared.")
    else:
        print(f"Unexpected response: {resp.decode().strip()}")
except ConnectionRefusedError:
    print("qssh-agent is not running.")
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
