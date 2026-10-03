"""
scripts/validate_byte_budget.py
Simulador de GitHub Linguist y Validador de Presupuesto de Bytes.
Para Prosigliere Analytics Engineer:
  Objetivo: Python: ~50%, SQL: ~32%, HCL: ~18%
"""

import sys
import argparse
from pathlib import Path

EXTENSION_LANGUAGE_MAP = {
    ".py": "Python",
    ".sql": "SQL",
    ".tf": "HCL",
    ".sh": "Shell",
    ".bat": "Batchfile",
    ".md": "Markdown",
    ".yml": "YAML",
    ".yaml": "YAML",
    ".toml": "TOML",
    ".ini": "INI",
    ".json": "JSON"
}

LINGUIST_PRIMARY_LANGUAGES = {"Python", "SQL", "HCL"}
EXCLUDED_DIRS = {".git", ".pytest_cache", "__pycache__", "venv", ".venv", "data", "dist", "build", ".terraform"}
EXCLUDED_EXTENSIONS = {".parquet", ".pyc", ".db", ".sqlite", ".ico", ".png", ".jpg"}


def calculate_byte_budget():
    root = Path(".").resolve()
    distribution = {}
    total_source_bytes = 0

    for file_path in root.rglob("*"):
        if file_path.is_dir():
            continue
        if any(part in EXCLUDED_DIRS for part in file_path.parts):
            continue
        if file_path.suffix.lower() in EXCLUDED_EXTENSIONS:
            continue

        ext = file_path.suffix.lower()
        lang = EXTENSION_LANGUAGE_MAP.get(ext, "Other")
        size = file_path.stat().st_size

        distribution[lang] = distribution.get(lang, 0) + size
        total_source_bytes += size

    if total_source_bytes == 0:
        print("[Byte Budget ERROR] Repositorio vacio.")
        sys.exit(1)

    print("=" * 60)
    print("  SIMULADOR GITHUB LINGUIST - DISTRIBUCION DE BYTES")
    print("=" * 60)
    for lang, bytes_count in sorted(distribution.items(), key=lambda x: x[1], reverse=True):
        pct = (bytes_count / total_source_bytes) * 100.0
        print(f"  {lang:<15}: {bytes_count:>8,} bytes ({pct:>5.1f}%)")
    print("-" * 60)
    print(f"  Total Masa        : {total_source_bytes:>8,} bytes (100.0%)")
    print("=" * 60)

    # Validacion informativa de lenguajes primarios
    sql_pct = (distribution.get("SQL", 0) / total_source_bytes) * 100.0
    hcl_pct = (distribution.get("HCL", 0) / total_source_bytes) * 100.0
    py_pct = (distribution.get("Python", 0) / total_source_bytes) * 100.0

    print(f"[Byte Budget Info] Python: {py_pct:.1f}% | SQL: {sql_pct:.1f}% | HCL: {hcl_pct:.1f}%")
    print("[Byte Budget PASS] Distribucion analizada satisfactoriamente.")
    sys.exit(0)


if __name__ == "__main__":
    calculate_byte_budget()
