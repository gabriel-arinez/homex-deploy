#!/usr/bin/env python3
"""Verifica referencias y labels OCI antes de migrar una release."""
from __future__ import annotations
import json
import os
from pathlib import Path
import re
import subprocess
import sys

MANIFEST = Path("releases/manifest.yaml")

def value(section: str, key: str) -> str:
    current = ""
    for raw in MANIFEST.read_text(encoding="utf-8").splitlines():
        if raw and not raw.startswith(" ") and raw.endswith(":"):
            current = raw[:-1]
        match = re.fullmatch(rf"\s+{re.escape(key)}:\s+(.+)", raw)
        if current == section and match:
            return match.group(1).strip('"')
    raise SystemExit(f"Falta {section}.{key} en manifest")

def source_revision(component: str) -> str:
    lines = MANIFEST.read_text(encoding="utf-8").splitlines()
    inside_sources = False; inside_component = False
    for raw in lines:
        if raw == "sources:": inside_sources = True; continue
        if inside_sources and raw and not raw.startswith(" "): break
        if inside_sources and raw == f"  {component}:": inside_component = True; continue
        if inside_component and re.fullmatch(r"  [a-z].*:", raw): break
        if inside_component and (match := re.fullmatch(r"    revision:\s+([0-9a-f]{40})", raw)):
            return match.group(1)
    raise SystemExit(f"Falta revisión {component}")

def image_ref(key: str) -> str:
    lines=MANIFEST.read_text(encoding="utf-8").splitlines(); in_images=False
    for raw in lines:
        if raw == "  images:": in_images=True; continue
        if in_images and not raw.startswith("    "): break
        if in_images and (match := re.fullmatch(rf"    {key}:\s+(.+)", raw)):
            return match.group(1).strip('"')
    raise SystemExit(f"Falta imagen {key}")

def inspect(reference: str) -> dict:
    local_ref=reference.split("@sha256:",1)[0]
    try:
        payload=subprocess.check_output(["docker","image","inspect",local_ref], text=True)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"Imagen local ausente: {local_ref}") from exc
    data=json.loads(payload)[0]
    if "@sha256:" in reference and reference not in data.get("RepoDigests",[]):
        raise SystemExit(f"Digest OCI no coincide con imagen local: {reference}")
    return data

def verify_compose(refs: dict[str, str]) -> None:
    if len(sys.argv) == 1:
        return
    if len(sys.argv) != 3 or sys.argv[1] != "--compose-json":
        raise SystemExit("Uso: verify_release_images.py [--compose-json archivo]")
    services = json.loads(Path(sys.argv[2]).read_text())["services"]
    for name, expected in (
        ("api", refs["api"]),
        ("worker", refs["worker"]),
        ("frontend-proxy", refs["frontend"]),
    ):
        actual = services[name]["image"]
        if actual != expected:
            raise SystemExit(f"Compose {name} utiliza {actual}, manifiesto exige {expected}")


def main() -> None:
    status=value("release","status")
    refs={"api":image_ref("api"),"worker":image_ref("worker"),"frontend":image_ref("frontend_proxy")}
    verify_compose(refs)
    if refs["api"] != refs["worker"]:
        raise SystemExit("API y worker deben compartir la imagen backend")
    backend=inspect(refs["api"]); frontend=inspect(refs["frontend"])
    expected={"backend":source_revision("backend"),"frontend":source_revision("frontend")}
    for name,data,revision in (("backend",backend,expected["backend"]),("frontend",frontend,expected["frontend"])):
        actual=data.get("Config",{}).get("Labels",{}).get("org.opencontainers.image.revision")
        if actual != revision:
            raise SystemExit(f"Label OCI {name} inválido: expected={revision} actual={actual}")
    if status == "released" and any("@sha256:" not in ref for ref in refs.values()):
        raise SystemExit("Una release released exige digests OCI")
    evidence={"schema_version":"1.0","release_status":status,"images":{
        "backend":{"reference":refs["api"],"image_id":backend["Id"],"revision":expected["backend"]},
        "frontend":{"reference":refs["frontend"],"image_id":frontend["Id"],"revision":expected["frontend"]}}}
    output=os.environ.get("HOMEX_RELEASE_IMAGE_EVIDENCE")
    if output:
        path=Path(output); path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(evidence,indent=2,sort_keys=True)+"\n")
    print("d07-release-images-ok")
if __name__ == "__main__": main()
