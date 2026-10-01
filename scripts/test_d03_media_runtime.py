#!/usr/bin/env python3
"""Crea evidencia de media D03 sobre el FileSystemStorage productivo."""

from __future__ import annotations

import json
import os
import sys
from io import BytesIO
from pathlib import Path

sys.path.insert(0, "/app")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

import django

django.setup()

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework.test import APIClient

from apps.catalogo.models import Producto, ValorCatalogo
from apps.clientes.models import Cliente
from apps.documentos.models import ArchivoAdjunto
from apps.proformas.services import agregar_detalle, crear_proforma


def valor(concepto: str, codigo: str) -> ValorCatalogo:
    return ValorCatalogo.objects.get(concepto__codigo=concepto, codigo=codigo)


def imagen() -> SimpleUploadedFile:
    salida = BytesIO()
    Image.new("RGB", (1600, 900), "#356f99").save(salida, format="PNG")
    return SimpleUploadedFile(
        "d03-origen.png",
        salida.getvalue(),
        content_type="image/png",
    )


def comprobar_key(key: str) -> str:
    assert key
    assert not key.startswith(("/", "http://", "https://"))
    path = Path(default_storage.path(key)).resolve()
    root = Path(settings.MEDIA_ROOT).resolve()
    assert path.is_relative_to(root)
    assert path.is_file()
    return str(path)


def ejecutar() -> None:
    user = get_user_model().objects.create_superuser(
        username="d03-media-admin",
        password="d03-media-only",
    )
    producto = Producto.objects.create(
        categoria=valor("CATEGORIA_PRODUCTO", "OTRO"),
        sku="D03-MEDIA-LOCAL",
        nombre="Producto prueba media local D03",
        precio_lista="100.00",
        stock=0,
        unidad_stock=valor("UNIDAD_MEDIDA", "PIEZA"),
        activo=True,
        created_by=user,
        updated_by=user,
    )
    cliente = Cliente.objects.create(
        tipo_cliente=valor("TIPO_CLIENTE", "PERSONA"),
        nombres="Cliente",
        apellidos="D03 local",
        celular="70000003",
        activo=True,
        created_by=user,
        updated_by=user,
    )
    proforma = crear_proforma(
        actor=user,
        cliente=cliente,
        titulo="Media local D03",
    )
    detalle = agregar_detalle(
        proforma_id=proforma.id,
        actor=user,
        tipo_item=valor("TIPO_ITEM", "OTRO"),
        producto_id=producto.id,
        nombre=producto.nombre,
        cantidad=1,
        unidad=valor("UNIDAD_MEDIDA", "PIEZA"),
        precio_unitario="100.00",
    )

    api = APIClient()
    api.force_authenticate(user)

    response = api.post(
        f"/api/v1/catalogo/productos/{producto.id}/imagen-principal/",
        {"archivo": imagen()},
        format="multipart",
    )
    assert response.status_code == 201, response.data
    producto.refresh_from_db()

    product_keys = [
        producto.imagen_principal.name,
        *producto.imagen_principal_variantes.values(),
    ]
    assert product_keys[0].startswith("productos/")
    assert set(producto.imagen_principal_variantes) == {"320", "640", "1280"}
    product_paths = [comprobar_key(key) for key in product_keys]

    media = response.data["imagen_principal"]
    product_urls = [media["original"], *media["variantes"].values()]
    assert all("/media/productos/" in url for url in product_urls)

    response = api.post(
        f"/api/v1/proformas/{proforma.id}/detalles/{detalle.id}/archivos/",
        {"archivo": imagen()},
        format="multipart",
    )
    assert response.status_code == 201, response.data

    adjunto = ArchivoAdjunto.objects.get(pk=response.data["id"])
    assert adjunto.ruta_storage.startswith("proformas/")
    base = adjunto.ruta_storage.rsplit("/", 1)[0]
    attachment_keys = [
        adjunto.ruta_storage,
        *(f"{base}/{width}.webp" for width in (320, 640, 1280)),
    ]
    attachment_paths = [comprobar_key(key) for key in attachment_keys]
    attachment_url = response.data["url"]
    assert "/media/proformas/" in attachment_url

    print(
        json.dumps(
            {
                "resultado": "d03-media-local-created",
                "product_id": producto.id,
                "proforma_id": proforma.id,
                "detail_id": detalle.id,
                "attachment_id": adjunto.id,
                "product_keys": product_keys,
                "attachment_keys": attachment_keys,
                "product_paths": product_paths,
                "attachment_paths": attachment_paths,
                "product_urls": product_urls,
                "attachment_url": attachment_url,
                "db_solo_keys": True,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    ejecutar()
