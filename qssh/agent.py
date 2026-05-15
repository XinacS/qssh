import base64
import socket
import threading
import time
import sys
import os
import signal

from . import utils


class PasswordAgent:
    """Background TCP server that holds SSH passwords in memory."""

    def __init__(self):
        self.passwords: dict[str, str] = {}
        self.last_activity = time.time()
        self.running = False
        self.server_socket: socket.socket | None = None
        self.server_thread: threading.Thread | None = None
        self.lock = threading.Lock()

    def _reset_idle_timer(self):
        self.last_activity = time.time()

    def _is_idle_expired(self) -> bool:
        return (time.time() - self.last_activity) > utils.IDLE_TIMEOUT

    def _write_pid(self):
        pid_file = os.path.join(os.getcwd(), utils.PID_FILE)
        with open(pid_file, "w") as f:
            f.write(str(os.getpid()))

    def _remove_pid(self):
        pid_file = os.path.join(os.getcwd(), utils.PID_FILE)
        try:
            os.remove(pid_file)
        except OSError:
            pass

    def _handle_client(self, conn: socket.socket, addr):
        try:
            self._reset_idle_timer()
            buffer = b""
            while self.running:
                data = conn.recv(4096)
                if not data:
                    break
                buffer += data
                while b"\r\n" in buffer:
                    line_bytes, buffer = buffer.split(b"\r\n", 1)
                    line = line_bytes.decode("utf-8", errors="replace").strip()
                    if not line:
                        continue
                    response = self._process_command(line)
                    conn.sendall((response + "\r\n").encode("utf-8"))
        except (ConnectionResetError, BrokenPipeError, OSError):
            pass
        finally:
            try:
                conn.close()
            except OSError:
                pass

    def _process_command(self, line: str) -> str:
        parts = line.split(" ", 1)
        cmd = parts[0].upper()

        if cmd == "PING":
            self._reset_idle_timer()
            return "PONG"

        if cmd == "GET":
            if len(parts) < 2:
                return "ERROR: missing key"
            key = parts[1].strip()
            with self.lock:
                pwd = self.passwords.get(key)
            if pwd is not None:
                b64pwd = base64.b64encode(pwd.encode("utf-8")).decode("ascii")
                return f"OK:{b64pwd}"
            return "MISS"

        if cmd == "SET":
            if len(parts) < 2:
                return "ERROR: missing data"
            remainder = parts[1]
            space_idx = remainder.find(" ")
            if space_idx == -1:
                return "ERROR: missing password"
            key = remainder[:space_idx].strip()
            b64value = remainder[space_idx + 1 :]
            try:
                value = base64.b64decode(b64value).decode("utf-8")
            except Exception:
                return "ERROR: invalid base64 password"
            with self.lock:
                self.passwords[key] = value
            return "OK"

        return f"ERROR: unknown command {cmd}"

    def _idle_checker(self):
        while self.running:
            if self._is_idle_expired():
                self.stop()
                return
            time.sleep(60)

    def start(self):
        self.running = True
        self._reset_idle_timer()
        self._write_pid()

        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.server_socket.bind((utils.AGENT_HOST, utils.AGENT_PORT))
        except OSError as e:
            self._remove_pid()
            print(
                f"Agent failed to bind on {utils.AGENT_HOST}:{utils.AGENT_PORT}: {e}",
                file=sys.stderr,
            )
            sys.exit(1)

        self.server_socket.listen(5)
        self.server_socket.settimeout(5)

        idle_thread = threading.Thread(target=self._idle_checker, daemon=True)
        idle_thread.start()

        while self.running:
            try:
                conn, addr = self.server_socket.accept()
                self._reset_idle_timer()
                t = threading.Thread(
                    target=self._handle_client, args=(conn, addr), daemon=True
                )
                t.start()
            except socket.timeout:
                continue
            except OSError:
                if self.running:
                    raise

    def stop(self):
        self.running = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except OSError:
                pass
        self._remove_pid()

    def run(self):
        def shutdown_handler(signum, frame):
            self.stop()
            sys.exit(0)

        signal.signal(signal.SIGINT, shutdown_handler)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, shutdown_handler)
        self.start()


def run_agent():
    agent = PasswordAgent()
    agent.run()
