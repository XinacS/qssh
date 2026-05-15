import base64
import socket
import subprocess
import sys
import os
import getpass
import platform

from . import utils


def send_to_agent(command: str, timeout: float = 5.0) -> str | None:
    """Send a command to the agent and return the response, or None on failure."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect((utils.AGENT_HOST, utils.AGENT_PORT))
            s.sendall((command + "\r\n").encode("utf-8"))
            data = b""
            while b"\r\n" not in data:
                chunk = s.recv(4096)
                if not chunk:
                    break
                data += chunk
            return data.decode("utf-8", errors="replace").strip()
    except (socket.timeout, socket.error, ConnectionRefusedError, OSError):
        return None


def is_agent_running() -> bool:
    """Check whether the agent is alive via a PING."""
    return send_to_agent("PING") == "PONG"


def get_password(key: str) -> str | None:
    """Retrieve a password from the agent. Returns None on MISS or agent down."""
    resp = send_to_agent(f"GET {key}")
    if resp and resp.startswith("OK:"):
        b64pwd = resp[3:]
        try:
            return base64.b64decode(b64pwd).decode("utf-8")
        except Exception:
            return resp[3:]
    return None


def set_password(key: str, password: str) -> bool:
    """Store a password in the agent. Returns True on success."""
    b64pwd = base64.b64encode(password.encode("utf-8")).decode("ascii")
    resp = send_to_agent(f"SET {key} {b64pwd}")
    return resp == "OK"


def start_agent() -> bool:
    """Start the qssh-agent process in the background. Returns True on success."""
    try:
        python = sys.executable or "python"
        qssh_pkg = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cmd = [python, "-m", "qssh", "--agent"]
        creationflags = 0
        cwd = None
        if platform.system() == "Windows":
            creationflags = 0x08000000  # DETACHED_PROCESS
            cwd = qssh_pkg

        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=creationflags,
            cwd=cwd,
        )
        import time

        time.sleep(1)
        return is_agent_running()
    except Exception as e:
        print(f"Failed to start agent: {e}", file=sys.stderr)
        return False


def ensure_agent():
    """Ensure the agent is running; start it if not."""
    if not is_agent_running():
        if not start_agent():
            print(
                "Error: Could not start qssh-agent. Start it manually with: python -m qssh --agent",
                file=sys.stderr,
            )
            sys.exit(1)


def prompt_password(key: str) -> str:
    """Prompt the user for a password using getpass."""
    current_user = getpass.getuser()
    pwd = get_password(key)
    if pwd is not None:
        return pwd
    password = getpass.getpass(f"Password for {key}: ")
    if not password:
        print("Error: Empty password provided.", file=sys.stderr)
        sys.exit(1)
    if not set_password(key, password):
        print("Warning: Failed to cache password in agent.", file=sys.stderr)
    return password


def parse_target(argv: list[str]) -> tuple[str, list[str]]:
    """Extract user@host from arguments. Returns (target, remaining_args)."""
    if not argv:
        print("Usage: qssh user@host [ssh-options...]", file=sys.stderr)
        sys.exit(1)
    target = argv[0]
    remaining = argv[1:]
    if "@" not in target:
        print(f"Error: '{target}' does not match user@host format.", file=sys.stderr)
        sys.exit(1)
    return target, remaining


def run_ssh(target: str, password: str, ssh_args: list[str]):
    """Spawn ssh with expect-based password automation."""
    ssh_cmd = ["ssh", target] + ssh_args

    system = platform.system()

    if system == "Windows":
        _run_ssh_windows(ssh_cmd, password)
    else:
        _run_ssh_posix(ssh_cmd, password)


def _run_ssh_posix(ssh_cmd: list[str], password: str):
    """Run ssh on POSIX systems using pexpect."""
    try:
        import pexpect
    except ImportError:
        print(
            "Error: pexpect is required on POSIX systems. Install with: pip install pexpect",
            file=sys.stderr,
        )
        sys.exit(1)

    ssh_proc = pexpect.spawn(
        " ".join(ssh_cmd),
        encoding="utf-8",
        codec_errors="replace",
        env=os.environ.copy(),
    )

    try:
        idx = ssh_proc.expect(
            [
                r"[\[ ]?password[\]: ]",
                r"Are you sure you want to continue connecting.*",
                pexpect.EOF,
                pexpect.TIMEOUT,
            ],
            timeout=30,
        )

        if idx == 0:
            ssh_proc.sendline(password)
        elif idx == 1:
            ssh_proc.sendline("yes")
            ssh_proc.expect(
                [
                    r"[\[ ]?password[\]: ]",
                    pexpect.EOF,
                    pexpect.TIMEOUT,
                ],
                timeout=30,
            )
            ssh_proc.sendline(password)

        ssh_proc.interact()
    finally:
        ssh_proc.terminate()


def _run_ssh_windows(ssh_cmd: list[str], password: str):
    """Run ssh on Windows using SSH_ASKPASS to inject the password."""
    import tempfile

    python = sys.executable or "python"
    b64pwd = base64.b64encode(password.encode("utf-8")).decode("ascii")

    askpass_py = tempfile.NamedTemporaryFile(
        suffix=".py", prefix="qssh_askpass_", delete=False, mode="w"
    )
    askpass_py.write(
        f"import base64, sys; sys.stdout.write(base64.b64decode('{b64pwd}').decode())\n"
    )
    askpass_py.close()

    askpass_bat = tempfile.NamedTemporaryFile(
        suffix=".bat", prefix="qssh_askpass_", delete=False, mode="w"
    )
    askpass_bat.write(f'@echo off\r\n"{python}" "{askpass_py.name}"\r\n')
    askpass_bat.close()

    env = os.environ.copy()
    env["SSH_ASKPASS"] = askpass_bat.name
    env["SSH_ASKPASS_REQUIRE"] = "force"

    try:
        cmd = ["ssh", "-o", "PreferredAuthentications=password"] + ssh_cmd[1:]
        proc = subprocess.run(cmd, env=env)
        sys.exit(proc.returncode)
    finally:
        os.unlink(askpass_bat.name)
        os.unlink(askpass_py.name)


def run(target_arg: str, ssh_args: list[str]):
    """Main client flow: ensure agent, get password, run ssh."""
    ensure_agent()
    password = prompt_password(target_arg)
    run_ssh(target_arg, password, ssh_args)
