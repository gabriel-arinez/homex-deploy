#!/usr/bin/env python3
"""Pruebas del contrato de releases y referencias inmutables de imágenes."""

from copy import deepcopy
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


SCHEMA_PATH = Path("releases/manifest.schema.json")
HASH = "a" * 64
DIGESTED_IMAGE = f"ghcr.io/homex/service:0.1.0@sha256:{HASH}"
SOURCE_TAGGED_IMAGE = "homex/service:d04-1a2b3c4"


def base_manifest() -> dict:
    return {
        "schema_version": "1.0",
        "release": {
            "version": "0.0.0-d00",
            "created_at": "2026-09-26T00:00:00-04:00",
            "status": "baseline",
        },
        "sources": {
            "backend": {
                "repository": "gabriel-arinez/homex-backend",
                "revision": "1" * 40,
            },
            "frontend": {
                "repository": "gabriel-arinez/homex-frontend",
                "revision": "2" * 40,
            },
            "nlp": {
                "repository": "gabriel-arinez/homex-nlp",
                "revision": "3" * 40,
                "package_version": "0.1.0",
                "artifact": "homex_nlp-0.1.0-py3-none-any.whl",
                "sha256": "4" * 64,
            },
        },
        "runtime": {
            "asr_model": {"version": "pending-d01", "sha256": "pending-d01"},
            "images": {
                "api": "pending-d01",
                "worker": "pending-d01",
                "frontend_proxy": "pending-d02",
            },
            "postgresql": "17.6-alpine3.22",
            "redis": "8.2.1-alpine3.22",
            "expected_migrations": {"accounts": "0001_initial"},
        },
    }


def errors(validator: Draft202012Validator, document: dict) -> list:
    return sorted(validator.iter_errors(document), key=lambda error: list(error.path))


def candidate_with(images: dict[str, str]) -> dict:
    candidate = deepcopy(base_manifest())
    candidate["release"]["status"] = "candidate"
    candidate["runtime"]["asr_model"] = {
        "version": "faster-whisper-small-v1",
        "sha256": HASH,
    }
    candidate["runtime"]["images"] = images
    return candidate


def main() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())

    baseline = base_manifest()
    if baseline_errors := errors(validator, baseline):
        raise SystemExit(f"baseline válida rechazada: {baseline_errors}")

    for status in ("candidate", "released", "superseded"):
        invalid = deepcopy(baseline)
        invalid["release"]["status"] = status
        if not errors(validator, invalid):
            raise SystemExit(f"{status} aceptó valores pending-*")

    tagged = candidate_with(
        {
            "api": SOURCE_TAGGED_IMAGE,
            "worker": SOURCE_TAGGED_IMAGE,
            "frontend_proxy": SOURCE_TAGGED_IMAGE,
        }
    )
    if tagged_errors := errors(validator, tagged):
        raise SystemExit(f"candidate con tag derivado de SHA fue rechazada: {tagged_errors}")

    digested = candidate_with(
        {
            "api": DIGESTED_IMAGE,
            "worker": DIGESTED_IMAGE,
            "frontend_proxy": DIGESTED_IMAGE,
        }
    )
    if digested_errors := errors(validator, digested):
        raise SystemExit(f"candidate con digest de registry fue rechazada: {digested_errors}")

    for mutable in (
        "homex/service:latest",
        "homex/service:0.4.0",
        "homex/service:d04-main",
        "homex/service:d04-123456",
        "homex/service:d04-12345678",
    ):
        invalid = deepcopy(tagged)
        invalid["runtime"]["images"]["api"] = mutable
        if not errors(validator, invalid):
            raise SystemExit(f"candidate aceptó referencia mutable/no contractual: {mutable}")

    bad_migration = deepcopy(baseline)
    bad_migration["runtime"]["expected_migrations"] = {"accounts": "backend-sha"}
    if not errors(validator, bad_migration):
        raise SystemExit("se aceptó una revisión Git como migración Django")

    print("release-contract-tests-ok")


if __name__ == "__main__":
    main()
