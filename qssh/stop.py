"""Stop the qssh-agent background process."""

import os
import socket
import subprocess
import sys

from . import utils

pid_file = os.path.join(os.getcwd(), utils.PID_FILE)

if os.path.exists(pid_file):
    with open(pid_file) as f:
        pid = f.read().strip()
    if pid:
        subprocess.run(["taskkill", "/PID", pid, "/F"], capture_output=True)
        print(f"Stopped qssh-agent (PID {pid}).")
        os.remove(pid_file)
        sys.exit(0)
    else:
        os.remove(pid_file)

# Fallback: find the agent process by port using netstat
try:
    result = subprocess.run(
        ["netstat", "-ano"], capture_output=True, text=True, encoding="cp1252"
    )
    for line in result.stdout.split("\n"):
        if str(utils.AGENT_PORT) in line:
            parts = line.split()
            if parts:
                pid = parts[-1]
                if pid.isdigit():
                    subprocess.run(["taskkill", "/PID", pid, "/F"], capture_output=True)
                    print(
                        f"Stopped qssh-agent (PID {pid}, found via port {utils.AGENT_PORT})."
                    )
                    sys.exit(0)
except Exception:
    pass

print("qssh-agent is not running.")
