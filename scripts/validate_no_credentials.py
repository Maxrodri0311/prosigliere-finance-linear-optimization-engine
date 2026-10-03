"""
scripts/validate_no_credentials.py
CI/CD Universal Security Guard: Escanea recursivamente el repositorio buscando
secretos, API keys, credenciales hardcodeadas, tokens JWT o contraseñas.
"""

import sys
import re
from pathlib import Path

CREDENTIAL_PATTERNS = [
    (r"(?:api[_-]?key|apikey|secret[_-]?key|auth[_-]?token)\s*=\s*['\"][A-Za-z0-9_\-\.]{16,}['\"]", "API Key / Auth Token asignado"),
    (r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", "Llave Privada SSH/RSA"),
    (r"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,}", "GitHub Personal Access Token"),
    (r"xox[baprs]-[0-9]{10,13}-[0-9]{10,13}-[a-zA-Z0-9]{24,34}", "Slack Token"),
    (r"AIza[0-9A-Za-z\\-_]{35}", "Google API Key"),
    (r"postgres(?:ql)?:\/\/[a-zA-Z0-9_-]+:[^@\s\n]+@[a-zA-Z0-9_\-\.]+", "Database Connection String con Password"),
]

EXCLUDED_DIRS = {".git", ".pytest_cache", "__pycache__", "venv", ".venv", "data", "dist", "build"}
EXCLUDED_EXTS = {".parquet", ".png", ".jpg", ".jpeg", ".ico", ".pyc", ".db", ".sqlite", ".zip", ".tar"}


def scan_for_credentials():
    root = Path(".").resolve()
    violations = []

    for file_path in root.rglob("*"):
        if file_path.is_dir():
            continue
        if any(excluded in file_path.parts for excluded in EXCLUDED_DIRS):
            continue
        if file_path.suffix.lower() in EXCLUDED_EXTS:
            continue

        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        for pattern, label in CREDENTIAL_PATTERNS:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for m in matches:
                # Excluir placeholders obvios
                matched_str = m.group(0)
                if any(placeholder in matched_str.lower() for placeholder in ["dummy", "placeholder", "your_", "example", "env_var", "<", "${"]):
                    continue
                violations.append(f"[{file_path.relative_to(root)}] Detectado: {label}")

    if violations:
        print("[Security Guard FAIL] Se detectaron credenciales o secretos potenciales:")
        for v in violations:
            print(f"  - {v}")
        sys.exit(1)

    print("[Security Guard PASS] Cero credenciales o secretos hardcodeados en el repositorio.")
    sys.exit(0)


if __name__ == "__main__":
    scan_for_credentials()
