# -*- coding: utf-8 -*-
"""
Script gom toan bo source code cua du an thanh 1 file duy nhat.
Tu dong bo qua: node_modules, .git, dist, file anh, audio, zip...
"""

import os
import sys

# Dam bao terminal Windows khong bi loi font utf-8
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

OUTPUT_FILE = "TOAN_BO_CODE_DU_AN.txt"

# Cac thu muc bo qua khong gom
IGNORE_DIRS = {
    "node_modules",
    ".git",
    "dist",
    "build",
    "__pycache__",
    ".pytest_cache",
    "repair-backups",
    ".system_generated",
    ".idea",
    ".vscode",
    "venv",
    ".venv",
}

# Cac duoi file bo qua (file nhi phan, anh, nhac, font...)
IGNORE_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg",
    ".mp3", ".wav", ".ogg",
    ".zip", ".tar", ".gz", ".rar", ".7z",
    ".pdf", ".exe", ".dll", ".so",
    ".woff", ".woff2", ".ttf", ".eot",
    ".pyc", ".pyo", ".lock",
}

# Cac file dac thu bo qua
IGNORE_FILES = {
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    OUTPUT_FILE,
}

def main():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    count = 0
    total_lines = 0

    print(f"Dang tien hanh gom toan bo ma nguon tai: {root_dir}")
    print(f"File ket qua se luu tai: {OUTPUT_FILE} ...\n")

    with open(OUTPUT_FILE, "w", encoding="utf-8", errors="replace") as outfile:
        outfile.write("=" * 80 + "\n")
        outfile.write("TONG HOP TOAN BO MA NGUON DU AN SMARTSTAY BOOKING\n")
        outfile.write("=" * 80 + "\n\n")

        for current_path, dirs, files in os.walk(root_dir):
            # Loc bo thu muc khong can thiet
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith(".")]

            for file in sorted(files):
                if file in IGNORE_FILES:
                    continue

                _, ext = os.path.splitext(file)
                if ext.lower() in IGNORE_EXTS:
                    continue

                full_path = os.path.join(current_path, file)
                rel_path = os.path.relpath(full_path, root_dir).replace("\\", "/")

                try:
                    with open(full_path, "r", encoding="utf-8", errors="replace") as infile:
                        content = infile.read()
                        lines = content.count("\n") + 1
                        total_lines += lines
                        count += 1

                        outfile.write("\n" + "=" * 80 + "\n")
                        outfile.write(f"FILE: {rel_path} ({lines} dong)\n")
                        outfile.write("=" * 80 + "\n\n")
                        outfile.write(content)
                        outfile.write("\n")
                except Exception as e:
                    print(f"Khong the doc file {rel_path}: {e}")

    print("Hoan tat gom code!")
    print(f"- Tong so file da gom: {count} files")
    print(f"- Tong so dong code: {total_lines:,} dong")
    print(f"- Da luu vao file: {os.path.join(root_dir, OUTPUT_FILE)}")

if __name__ == "__main__":
    main()
