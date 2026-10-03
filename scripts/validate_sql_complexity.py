"""
scripts/validate_sql_complexity.py
CI/CD Universal SQL Guard: Valida que los scripts SQL no sean consultas triviales
(e.g., SELECT * FROM t WHERE id=1), sino modelos analiticos profesionales con
Common Table Expressions (CTEs), Window Functions, particionamiento o agregaciones complejas.
"""

import sys
import re
from pathlib import Path

COMPLEX_SQL_PATTERNS = [
    (r"\bWITH\s+[a-zA-Z0-9_]+\s+AS\s*\(", "Common Table Expression (CTE)"),
    (r"\bOVER\s*\(\s*(?:PARTITION\s+BY|ORDER\s+BY)", "Window Function (OVER / PARTITION BY)"),
    (r"\b(?:RANK|DENSE_RANK|ROW_NUMBER|LAG|LEAD|NTILE|PERCENTILE_CONT)\s*\(", "Advanced Analytic Function"),
    (r"\b(?:GROUP\s+BY\s+CUBE|GROUP\s+BY\s+ROLLUP|GROUPING\s+SETS)", "Multi-dimensional Grouping"),
    (r"\bCREATE\s+(?:OR\s+REPLACE\s+)?TABLE\b.*?\bPARTITION\s+BY\b", "Partitioned Table DDL"),
    (r"\bCREATE\s+INDEX\b.*?\bUSING\s+BRIN\b", "BRIN Range Index"),
    (r"\bCREATE\s+OR\s+REPLACE\s+FUNCTION\b", "Stored Procedure / Function DDL"),
]


def audit_sql_complexity():
    root = Path(".").resolve()
    sql_files = list(root.glob("analytics/**/*.sql"))

    if not sql_files:
        print("[SQL Complexity Guard PASS] No hay archivos SQL en analytics/ para auditar.")
        sys.exit(0)

    failed_files = []
    audited_count = 0

    for sf in sql_files:
        if not sf.is_file():
            continue
        audited_count += 1
        content = sf.read_text(encoding="utf-8", errors="ignore")

        # Verificar si cumple al menos un patron complejo
        matched_patterns = []
        for pat, label in COMPLEX_SQL_PATTERNS:
            if re.search(pat, content, re.IGNORECASE | re.DOTALL):
                matched_patterns.append(label)

        if not matched_patterns:
            failed_files.append(f"{sf.relative_to(root)}: Sin CTEs, Window Functions ni DDL avanzado.")

    if failed_files:
        print(f"[SQL Complexity Guard FAIL] {len(failed_files)}/{audited_count} archivos SQL no cumplen con el estandar analitico:")
        for ff in failed_files:
            print(f"  - {ff}")
        sys.exit(1)

    print(f"[SQL Complexity Guard PASS] Complejidad analitica avanzada verificada en {audited_count}/{audited_count} archivos SQL (CTEs/Window Functions detectadas).")
    sys.exit(0)


if __name__ == "__main__":
    audit_sql_complexity()
