#!/usr/bin/env python3
"""Utility script to run YapYap backend and frontend together."""

import argparse
import os
import signal
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
BACKEND_MODULE = "backend.app:app"
FRONTEND_DIR = PROJECT_ROOT / "frontend"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run YapYap backend and frontend together")
    parser.add_argument(
        "--backend-host",
        default="0.0.0.0",
        help="Host interface for the backend FastAPI server (default: %(default)s)",
    )
    parser.add_argument(
        "--backend-port",
        type=int,
        default=int(os.environ.get("PORT", "5001")),
        help="Port for the backend FastAPI server (default: env PORT or 5001)",
    )
    parser.add_argument(
        "--frontend-port",
        type=int,
        default=4173,
        help="Port for the static frontend dev server (default: %(default)s)",
    )
    parser.add_argument(
        "--skip-frontend",
        action="store_true",
        help="Skip launching the static frontend server",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Run uvicorn with --reload for backend hot-reload",
    )
    return parser.parse_args()


def start_process(cmd, cwd=None, env=None, label="process"):
    print(f"[run_all] starting {label}: {' '.join(cmd)}")
    return subprocess.Popen(cmd, cwd=cwd, env=env)


def main() -> int:
    args = parse_args()

    child_env = os.environ.copy()
    child_env["PORT"] = str(args.backend_port)

    processes = []

    backend_cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        BACKEND_MODULE,
        "--host",
        args.backend_host,
        "--port",
        str(args.backend_port),
    ]
    if args.reload:
        backend_cmd.append("--reload")

    try:
        backend_proc = start_process(backend_cmd, cwd=PROJECT_ROOT, env=child_env, label="backend")
        processes.append(backend_proc)

        if not args.skip_frontend:
            if not FRONTEND_DIR.exists():
                raise FileNotFoundError(f"Frontend directory not found at {FRONTEND_DIR}")
            frontend_cmd = [
                sys.executable,
                "-m",
                "http.server",
                str(args.frontend_port),
            ]
            frontend_proc = start_process(frontend_cmd, cwd=FRONTEND_DIR, label="frontend")
            processes.append(frontend_proc)
            print(
                f"[run_all] Frontend available at http://localhost:{args.frontend_port} (proxying API to backend)."
            )

        print(
            f"[run_all] Backend running at http://{args.backend_host}:{args.backend_port}. Press Ctrl+C to stop both servers."
        )

        # Wait for backend to exit; ctrl+c handled below
        backend_proc.wait()
        return backend_proc.returncode or 0
    except KeyboardInterrupt:
        print("\n[run_all] Keyboard interrupt received. Shutting down...")
        return 0
    finally:
        for proc in processes:
            if proc.poll() is None:
                proc.send_signal(signal.SIGINT)
        for proc in processes:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                if proc.poll() is None:
                    proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
