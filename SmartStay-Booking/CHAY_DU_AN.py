#!/usr/bin/env python3
"""Run the existing SmartStay stack locally after cloning (Python 3.10+).

Place beside smartstay-backend/ and quickstay-frontend/. No third-party Python
packages are needed. The existing backend helper owns secret generation.
"""

import argparse
import importlib.util
import json
import re
import shutil
import socket
import subprocess
import sys
import urllib.request
from pathlib import Path


GITIGNORE_BLOCK = """# SmartStay: per-machine configuration and generated files
.env
.env.*
.env-*
!.env.example
!.env.*.example
node_modules/
dist/
__pycache__/
*.py[cod]
.venv/
.pytest_cache/
dev-certs/
booking-backups/
repair-backups/
"""


def check_layout(root):
    required = (
        "smartstay-backend/.env.example",
        "smartstay-backend/docker-compose.yml",
        "smartstay-backend/scripts/configure_phase2.py",
        "quickstay-frontend/.env.example",
        "quickstay-frontend/package.json",
        "quickstay-frontend/package-lock.json",
    )
    missing = [name for name in required if not (root / name).is_file()]
    if missing:
        raise ValueError(
            "Dat CHAY_DU_AN.py cung cap voi hai thu muc smartstay-backend va "
            "quickstay-frontend. Dang thieu: " + ", ".join(missing)
        )
    for name in (
        ".gitignore",
        "smartstay-backend/.env",
        "quickstay-frontend/.env.local",
    ):
        if (root / name).is_symlink():
            raise ValueError("Hay kiem tra file lien ket truoc khi cau hinh: " + name)


def prepare_configuration(root):
    check_layout(root)
    backend = root / "smartstay-backend"
    helper_path = backend / "scripts" / "configure_phase2.py"
    spec = importlib.util.spec_from_file_location("smartstay_setup_helper", helper_path)
    if spec is None or spec.loader is None:
        raise ValueError("Khong doc duoc scripts/configure_phase2.py")
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)

    # This existing helper validates before writing, generates only missing or
    # placeholder secrets, preserves strong keys/passwords, and uses env_only.
    # The React client uses bearer tokens; local HTTP does not need the optional
    # HTTPS gateway. Any HTTPS/S3 overlay already configured is retained.
    helper.configure(backend, https=False)

    frontend = root / "quickstay-frontend"
    frontend_env = frontend / ".env.local"
    if not frontend_env.exists():
        template = (frontend / ".env.example").read_text(encoding="utf-8-sig")
        with frontend_env.open("x", encoding="utf-8", newline="\n") as target:
            target.write(template)

    ignore = root / ".gitignore"
    existing = ignore.read_text(encoding="utf-8-sig") if ignore.exists() else ""
    if GITIGNORE_BLOCK not in existing:
        separator = "" if not existing else "\n" if existing.endswith("\n") else "\n\n"
        with ignore.open("a", encoding="utf-8", newline="\n") as target:
            target.write(separator + GITIGNORE_BLOCK)


def executable(name):
    path = shutil.which(name)
    if not path:
        raise ValueError(
            "Chua tim thay " + name + ". Cai cong cu nay, roi mo lai Terminal."
        )
    return path


def run(command, cwd, quiet=False, timeout=None):
    if not quiet:
        print("\n> " + " ".join(command), flush=True)
    return subprocess.run(
        command,
        cwd=cwd,
        check=True,
        text=True,
        capture_output=quiet,
        timeout=timeout,
    )


def check_tools(root):
    docker, node, npm = (executable(name) for name in ("docker", "node", "npm"))
    try:
        run([docker, "compose", "version"], root, quiet=True, timeout=20)
        run(
            [docker, "info", "--format", "{{.ServerVersion}}"],
            root,
            quiet=True,
            timeout=20,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        raise ValueError(
            "Mo Docker Desktop, cho Docker Engine chay va kiem tra Docker Compose v2."
        ) from None

    version = run([node, "--version"], root, quiet=True, timeout=10).stdout.strip()
    match = re.fullmatch(r"v(\d+)\.(\d+)\.(\d+)", version)
    if not match or tuple(map(int, match.groups())) < (22, 12, 0):
        raise ValueError("Du an yeu cau Node.js >= 22.12.0; dang dung " + version)

    try:
        with socket.create_connection(("127.0.0.1", 4173), timeout=1):
            occupied = True
    except OSError:
        occupied = False
    if occupied:
        raise ValueError(
            "Cong 4173 dang duoc dung. Dung frontend cu bang Ctrl+C, roi chay lai."
        )
    return docker, npm


def verify_backend():
    # Keep localhost checks independent of system HTTP proxy configuration.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open("http://127.0.0.1:8001/health/ready", timeout=10) as response:
            data = json.load(response)
            if response.status != 200 or not isinstance(data, dict):
                raise ValueError("Unexpected readiness response")
    except (OSError, ValueError) as exc:
        raise ValueError(
            "Chua kiem tra duoc backend tai localhost:8001/health/ready. "
            "Tai smartstay-backend, chay: docker compose logs --tail=80 backend"
        ) from exc


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--setup-only",
        action="store_true",
        help="Chi tao/kiem tra cau hinh, khong chay Docker hay npm.",
    )
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parent
    backend = root / "smartstay-backend"
    frontend = root / "quickstay-frontend"

    try:
        if sys.version_info < (3, 10):
            raise ValueError("Can Python 3.10 tro len.")
        check_layout(root)
        docker = npm = None
        if not args.setup_only:
            docker, npm = check_tools(root)
        prepare_configuration(root)
        print(
            "Da chuan bi .env backend, .env.local frontend va quy tac .gitignore.",
            flush=True,
        )
        print(
            "Tai khoan admin: xem SUPERADMIN_USERNAME / SUPERADMIN_PASSWORD trong smartstay-backend/.env."
        )
        print(
            "Cac khoa va mat khau hop le da co duoc giu nguyen; khong in bi mat ra Terminal."
        )
        if args.setup_only:
            print("De khoi dong ca du an: python CHAY_DU_AN.py")
            return 0

        run([npm, "ci"], frontend)
        run(
            [
                docker,
                "compose",
                "up",
                "-d",
                "--build",
                "--wait",
                "--wait-timeout",
                "180",
            ],
            backend,
        )
        verify_backend()
        print("\nBackend da tra loi kiem tra san sang.")
        print("Sau khi Vite hien Ready, mo http://localhost:4173/#/rooms")
        print("Dashboard: http://localhost:4173/#/admin")
        print("Tai lieu API: http://localhost:8001/docs")
        print("Neu trinh duyet nho Design preview: chon Live SmartStay API va /api.")
        print(
            "Giu Terminal mo. Ctrl+C dung frontend; Docker tiep tuc chay nen.",
            flush=True,
        )
        run([npm, "run", "dev"], frontend)
        return 0
    except KeyboardInterrupt:
        print(
            "\nDa dung frontend. De dung backend: cd smartstay-backend, sau do docker compose stop."
        )
        return 0
    except subprocess.CalledProcessError as exc:
        print(
            "\nLenh khong thanh cong. Xem loi phia tren; neu la Docker, chay docker compose ps -a tai smartstay-backend.",
            file=sys.stderr,
        )
        return exc.returncode if exc.returncode > 0 else 1
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print("\nLOI: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
