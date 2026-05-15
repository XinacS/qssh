import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        prog="qssh",
        description="Quick SSH with password caching via a background agent.",
    )
    parser.add_argument(
        "target",
        nargs="?",
        default=None,
        help="SSH target in user@host format",
    )
    parser.add_argument(
        "ssh_args",
        nargs="*",
        help="Additional arguments passed to ssh",
    )
    parser.add_argument(
        "--agent",
        action="store_true",
        help="Run the qssh-agent server (internal use)",
    )

    args = parser.parse_args()

    if args.agent:
        from .agent import run_agent

        run_agent()
    elif args.target:
        from .client import run

        run(args.target, args.ssh_args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
