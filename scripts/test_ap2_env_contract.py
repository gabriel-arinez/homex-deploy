#!/usr/bin/env python3
"""AP2: pruebas ejecutables y aisladas del contrato de entorno (sin credenciales)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from validate_env_contract import validate


class EnvContractTests(unittest.TestCase):
    def check_content(self, contents: str, expected: set[str]) -> None:
        with tempfile.TemporaryDirectory(prefix="homex-ap2-env-") as directory:
            file = Path(directory) / ".env.example"
            file.write_text(contents, encoding="utf-8")
            validate(str(file), expected)

    def test_valid_example_with_comments_and_empty_values(self) -> None:
        self.check_content("# Comentario\nA=valor=con-igual\nB=\n", {"A", "B"})

    def test_rejects_missing_and_unknown_keys(self) -> None:
        with self.assertRaises(SystemExit):
            self.check_content("A=1\nC=2\n", {"A", "B"})

    def test_rejects_duplicate_keys(self) -> None:
        with self.assertRaises(SystemExit):
            self.check_content("A=1\nA=2\nB=3\n", {"A", "B"})

    def test_rejects_naked_key_instead_of_silently_accepting_it(self) -> None:
        with self.assertRaises(SystemExit):
            self.check_content("A=1\nB\n", {"A", "B"})

    def test_rejects_invalid_or_exported_variable_name(self) -> None:
        for invalid in ("export B=2", " B=2", "B-C=2", "B =2"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(SystemExit):
                    self.check_content(f"A=1\n{invalid}\n", {"A", "B"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
