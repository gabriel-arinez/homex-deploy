#!/usr/bin/env python3
"""Demuestra idempotencia de dos recepciones concurrentes sobre PostgreSQL real."""
from __future__ import annotations

import os
import sys
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

sys.path.insert(0, "/app")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")
import django

django.setup()

from django.contrib.auth import get_user_model
from django.db import close_old_connections
from apps.capturas.models import Captura, TrabajoOutbox
from apps.capturas.services import recibir_captura_texto
from apps.clientes.models import Cliente
from apps.catalogo.models import ValorCatalogo
from apps.proformas.services import crear_proforma

suffix=uuid4().hex[:10]
user=get_user_model().objects.create_superuser(username=f'd06-{suffix}',password='d06-only')
tipo=ValorCatalogo.objects.get(concepto__codigo='TIPO_CLIENTE',codigo='PERSONA')
cliente=Cliente.objects.create(tipo_cliente=tipo,nombres='Prueba',apellidos='D06',celular=f'7{suffix[:7]}',activo=True,created_by=user,updated_by=user)
proforma=crear_proforma(actor=user,cliente=cliente,titulo=f'Concurrencia D06 {suffix}')
key=uuid4(); barrier=Barrier(2)

def receive():
    close_old_connections(); actor=get_user_model().objects.get(pk=user.pk); barrier.wait()
    result=recibir_captura_texto(actor=actor,clave_idempotencia=key,proforma_id=proforma.pk,texto='una mesa de madera')
    close_old_connections(); return result.captura.id,result.intento.id,result.reutilizada

with ThreadPoolExecutor(max_workers=2) as pool:
    results=list(pool.map(lambda _: receive(),range(2)))
assert len({row[0] for row in results}) == 1, results
assert len({row[1] for row in results}) == 1, results
assert sorted(row[2] for row in results) == [False,True], results
capture=Captura.objects.get(clave_idempotencia=key)
assert capture.intentocaptura_set.count() == 1
assert TrabajoOutbox.objects.filter(intento__captura=capture).count() == 1
print('d06-concurrent-idempotency-ok')
