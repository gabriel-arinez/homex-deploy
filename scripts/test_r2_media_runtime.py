#!/usr/bin/env python3
"""E2E D03 contra un endpoint S3-compatible descartable o R2 real."""
from __future__ import annotations
import json, os, sys, urllib.request
from io import BytesIO
from pathlib import Path
from uuid import uuid4
sys.path.insert(0, '/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.production')
import django
django.setup()
from django.contrib.auth import get_user_model
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework.test import APIClient
from apps.catalogo.models import Producto, ValorCatalogo
from apps.clientes.models import Cliente
from apps.documentos.models import ArchivoAdjunto
from apps.proformas.services import agregar_detalle, crear_proforma

def valor(concepto, codigo):
    return ValorCatalogo.objects.get(concepto__codigo=concepto, codigo=codigo)

def imagen():
    salida=BytesIO(); Image.new('RGB',(1600,900),'#356f99').save(salida,format='PNG')
    return SimpleUploadedFile('d03-origen.png',salida.getvalue(),content_type='image/png')

def publica(key):
    url=f"{os.environ['R2_PUBLIC_TEST_BASE_URL'].rstrip('/')}/{key}"
    with urllib.request.urlopen(url,timeout=10) as response:
        assert response.status == 200
        return response.read()

def ejecutar():
    suffix=uuid4().hex[:10]
    user=get_user_model().objects.create_superuser(username=f'd03-r2-{suffix}',password='d03-test-only')
    producto=Producto.objects.create(categoria=valor('CATEGORIA_PRODUCTO','OTRO'),sku=f'D03-R2-{suffix.upper()}',nombre='Producto prueba R2 D03',precio_lista='100.00',stock=0,unidad_stock=valor('UNIDAD_MEDIDA','PIEZA'),activo=True,created_by=user,updated_by=user)
    cliente=Cliente.objects.create(tipo_cliente=valor('TIPO_CLIENTE','PERSONA'),nombres='Cliente',apellidos='D03',celular='70000003',activo=True,created_by=user,updated_by=user)
    proforma=crear_proforma(actor=user,cliente=cliente,titulo=f'Media R2 D03 {suffix}')
    detalle=agregar_detalle(proforma_id=proforma.id,actor=user,tipo_item=valor('TIPO_ITEM','OTRO'),producto_id=producto.id,nombre=producto.nombre,cantidad=1,unidad=valor('UNIDAD_MEDIDA','PIEZA'),precio_unitario='100.00')
    api=APIClient(); api.force_authenticate(user)
    respuesta=api.post(f'/api/v1/catalogo/productos/{producto.id}/imagen-principal/',{'archivo':imagen()},format='multipart',secure=True)
    assert respuesta.status_code == 201, respuesta.data
    producto.refresh_from_db()
    product_keys=[producto.imagen_principal.name,*producto.imagen_principal_variantes.values()]
    assert product_keys[0].startswith('productos/')
    assert set(producto.imagen_principal_variantes) == {'320','640','1280'}
    assert all(not key.startswith(('http://','https://')) for key in product_keys)
    assert all(default_storage.exists(key) and publica(key) for key in product_keys)
    media=respuesta.data['imagen_principal']; urls=[media['original'],*media['variantes'].values()]
    domain=os.environ['HOMEX_MEDIA_PUBLIC_DOMAIN']
    assert all(url.startswith(f'https://{domain}/productos/') for url in urls)
    assert all('?' not in url and os.environ['R2_ENDPOINT_URL'] not in url and os.environ['R2_BUCKET_NAME'] not in url for url in urls)
    respuesta=api.post(f'/api/v1/proformas/{proforma.id}/detalles/{detalle.id}/archivos/',{'archivo':imagen()},format='multipart',secure=True)
    assert respuesta.status_code == 201, respuesta.data
    adjunto=ArchivoAdjunto.objects.get(pk=respuesta.data['id'])
    base=adjunto.ruta_storage.rsplit('/',1)[0]
    attachment_keys=[adjunto.ruta_storage,*(f'{base}/{width}.webp' for width in (320,640,1280))]
    assert adjunto.ruta_storage.startswith('proformas/') and not adjunto.ruta_storage.startswith(('http://','https://'))
    assert respuesta.data['url'].startswith(f'https://{domain}/proformas/')
    assert all(default_storage.exists(key) and publica(key) for key in attachment_keys)
    respuesta=api.delete(f'/api/v1/proformas/{proforma.id}/detalles/{detalle.id}/archivos/{adjunto.id}/',secure=True)
    assert respuesta.status_code == 204
    assert all(not default_storage.exists(key) for key in attachment_keys)
    respuesta=api.delete(f'/api/v1/catalogo/productos/{producto.id}/imagen-principal/',secure=True)
    assert respuesta.status_code == 204
    producto.refresh_from_db()
    assert not producto.imagen_principal and producto.imagen_principal_variantes == {}
    assert all(not default_storage.exists(key) for key in product_keys)
    print(json.dumps({'resultado':'d03-r2-media-ok','producto_prefijo':'productos','proforma_prefijo':'proformas','variantes':3,'publico_sin_auth':True,'borrado':True,'db_solo_keys':True},sort_keys=True))

if __name__ == '__main__': ejecutar()
