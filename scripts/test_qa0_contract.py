#!/usr/bin/env python3
"""Protege las conclusiones verificables del cierre QA0."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = (ROOT / "releases/manifest.yaml").read_text(encoding="utf-8")
EVIDENCE = json.loads(
    (ROOT / "docs/evidencias/qa0-cierre-20261011.json").read_text(encoding="utf-8")
)
REPORT = (ROOT / "docs/implementacion/QA0_CIERRE_ESTABILIZACION_20261011.md").read_text(
    encoding="utf-8"
)

assert "status: candidate" in MANIFEST
assert f'version: "{EVIDENCE["release"]["version"]}"' in MANIFEST
for component in ("backend", "frontend", "nlp"):
    assert f'revision: {EVIDENCE["release"][component]}' in MANIFEST

assert EVIDENCE["production_touched"] is False
assert EVIDENCE["production"]["mutations_performed"] == 0
assert EVIDENCE["recovery"]["migration_failure_after_ddl"] == "PASS"
assert EVIDENCE["recovery"]["media"] == {
    "referenced": 8,
    "present": 8,
    "missing": 0,
    "unreferenced": 0,
}
assert all(value == "PASS" for value in EVIDENCE["resilience"].values() if isinstance(value, str))
for marker in ("homex-restore-ok", "runtime-privileges-ok", "db-media-integrity-ok"):
    assert marker in REPORT
assert "APARTADO 0 CERRADO" in REPORT
assert "D08" in REPORT and "F11" in REPORT

print("qa0-closeout-contract-ok")
