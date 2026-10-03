#!/usr/bin/env python3
"""Comprueba que los datos representativos D05 sobrevivieron al restore."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, "/app")

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

import django

django.setup()

from apps.catalogo.models import Producto
from apps.documentos.models import ArchivoAdjunto
from apps.proformas.models import Proforma
from django.contrib.auth import get_user_model
from django.core.files.storage import default_storage


def main() -> None:
    state = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    assert get_user_model().objects.filter(username="d03-media-admin").exists()
    assert Producto.objects.filter(pk=state["product_id"]).exists()
    assert Proforma.objects.filter(pk=state["proforma_id"]).exists()
    assert ArchivoAdjunto.objects.filter(pk=state["attachment_id"]).exists()
    for key in state["product_keys"] + state["attachment_keys"]:
        assert default_storage.exists(key), key
    print("d05-restored-data-ok")


if __name__ == "__main__":
    main()
