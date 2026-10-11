#!/usr/bin/env python3
"""Pruebas de comportamiento de deploy.sh: sin Docker, datos ni red productiva."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMPOSE_MOCK = """#!/bin/sh
printf '%s\\n' "$*" >> "$D07_EVENTS"
case " $* " in
  *" config --quiet "*) exit 0 ;;
  *" exec -T postgres "*) exit 0 ;;
  *" ps --status running --services "*) printf 'api\\nworker\\nbeat\\n'; exit 0 ;;
  *" stop api worker beat "*) [ "${D07_FAIL:-}" = stop ] && exit 14; exit 0 ;;
  *" run --rm migrate "*) [ "${D07_FAIL:-}" = migrate ] && exit 15; exit 0 ;;
  *" run --rm grant-runtime "*) [ "${D07_FAIL:-}" = grant ] && exit 16; exit 0 ;;
  *" up -d api worker beat frontend-proxy monitor "*) [ "${D07_FAIL:-}" = startup ] && exit 17; exit 0 ;;
  *" ps -q monitor "*) echo mock-monitor; exit 0 ;;
esac
exit 0
"""
PYTHON_MOCK = """#!/bin/sh
printf 'python %s\\n' "$*" >> "$D07_EVENTS"
[ "${D07_FAIL:-}" = verify ] && exit 11
exit 0
"""
DOCKER_MOCK = """#!/bin/sh
printf 'docker %s\\n' "$*" >> "$D07_EVENTS"
echo healthy
"""
BACKUP_MOCK = """#!/bin/sh
echo backup >> "$D07_EVENTS"
[ "${D07_FAIL:-}" = backup ] && exit 12
exit 0
"""
SMOKE_MOCK = """#!/bin/sh
echo smoke >> "$D07_EVENTS"
[ "${D07_FAIL:-}" = smoke ] && exit 18
exit 0
"""


class DeployBehavior(unittest.TestCase):
    def run_case(self, failure: str | None):
        with tempfile.TemporaryDirectory(prefix="homex-d07-deploy-test-") as temp:
            root = Path(temp)
            (root / "scripts").mkdir()
            (root / "bin").mkdir()
            shutil.copyfile(ROOT / "scripts/deploy.sh", root / "scripts/deploy.sh")
            for path, content in {
                "bin/mock-compose": COMPOSE_MOCK,
                "bin/python3": PYTHON_MOCK,
                "bin/docker": DOCKER_MOCK,
                "scripts/backup.sh": BACKUP_MOCK,
                "scripts/smoke.sh": SMOKE_MOCK,
            }.items():
                target = root / path
                target.write_text(content, encoding="utf-8")
                target.chmod(0o700)
            events = root / "events.txt"
            events.touch()
            env = dict(os.environ)
            env.update(
                D07_EVENTS=str(events),
                COMPOSE_BIN=str(root / "bin/mock-compose"),
                HOMEX_COMPOSE_FILES="-f demo.yml",
                HOMEX_ENV_FILE=".env.synthetic",
                COMPOSE_PROJECT_NAME="homex-d07-mock",
                PATH=f"{root / 'bin'}:{os.environ['PATH']}",
            )
            env.pop("D07_FAIL", None)
            if failure:
                env["D07_FAIL"] = failure
            outcome = subprocess.run(
                ["/bin/sh", "scripts/deploy.sh"],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                timeout=15,
            )
            return outcome, events.read_text(encoding="utf-8").splitlines()

    @staticmethod
    def find(events: list[str], needle: str):
        for index, event in enumerate(events):
            if needle in event:
                return index
        raise AssertionError(f"No aparece {needle!r} en {events!r}")

    def test_success_order(self):
        result, events = self.run_case(None)
        self.assertEqual(result.returncode, 0, result.stderr)
        sequence = ("python scripts/verify_release_images.py", "backup",
                    " stop api worker beat", " run --rm migrate", " run --rm grant-runtime",
                    " up -d api worker beat frontend-proxy monitor", "smoke")
        positions = [self.find(events, item) for item in sequence]
        self.assertEqual(positions, sorted(positions))
        self.assertNotIn(" start api worker beat", " ".join(events))
        self.assertIn("homex-deploy-ok", result.stdout)

    def test_failure_before_migration_recovers_writers(self):
        result, events = self.run_case("stop")
        self.assertNotEqual(result.returncode, 0)
        self.assertLess(self.find(events, " stop api worker beat"),
                        self.find(events, " start api worker beat"))
        self.assertFalse(any(" run --rm migrate" in event for event in events))

    def test_migration_failure_does_not_restart_old_writers(self):
        result, events = self.run_case("migrate")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any(" start api worker beat" in event for event in events))
        self.assertFalse(any(" up -d api worker beat frontend-proxy monitor" in event for event in events))
        self.assertIn("NO reiniciar escritores D04", result.stderr)

    def test_grants_failure_does_not_restart_old_writers(self):
        result, events = self.run_case("grant")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any(" start api worker beat" in event for event in events))
        self.assertIn("NO reiniciar escritores D04", result.stderr)

    def test_backup_failure_blocks_migration(self):
        result, events = self.run_case("backup")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any(" stop api worker beat" in event for event in events))
        self.assertFalse(any(" run --rm migrate" in event for event in events))

    def test_image_verification_failure_blocks_all_changes(self):
        result, events = self.run_case("verify")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any(" up -d postgres redis" in event for event in events))
        self.assertNotIn("backup", events)

    def test_smoke_failure_does_not_restart_old_writers(self):
        result, events = self.run_case("smoke")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any(" start api worker beat" in event for event in events))
        self.assertIn("NO reiniciar escritores D04", result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
