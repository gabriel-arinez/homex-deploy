# D03 — Media persistente local de producción

**Fecha:** 30 de septiembre de 2026  
**Rama:** `feat/d03-media-local`  
**Base:** `37e03f93d7093e53e0db30f7182f361944da30aa` (D02)  
**Backend candidato F09.1:** `595d2ae22adff68f613b2c58f5c6768207c88236`

## Objetivo

Materializar la decisión de storage productivo proporcional a HOMEX: filesystem persistente del
host, mismo origen `/media/`, sin dominio público ni object storage obligatorio.

## Topología

- `HOMEX_MEDIA_HOST_PATH`: directorio durable del host;
- API: bind RW en `/var/lib/homex/media`;
- Nginx: el mismo bind RO;
- worker: sin mount de media comercial;
- PostgreSQL: sólo keys/metadatos;
- audio: volumen separado y efímero.

La instalación productiva prepara el directorio del host con propiedad del UID/GID del backend
(10001:10001) y permisos de lectura/traversal suficientes para Nginx.

## Contrato productivo

```text
HOMEX_MEDIA_STORAGE=filesystem
HOMEX_MEDIA_HOST_PATH=/srv/homex/media
HOMEX_MEDIA_ROOT=/var/lib/homex/media
HOMEX_MEDIA_URL=/media/
HOMEX_HTTPS_ENABLED=0
```

Las variables R2 permanecen documentadas como alternativa futura, pero no se inyectan al runtime
mientras el modo productivo sea `filesystem`.

## Gates

`scripts/test_d03_contract.py` verifica:

- settings de producción;
- bind RW exclusivo de API;
- bind RO de Nginx;
- ausencia de mount comercial en worker;
- ausencia de credenciales R2 inyectadas;
- mismo origen `/media/`.

`scripts/test_d03_media.sh` ejecuta:

1. PostgreSQL y Redis reales;
2. migraciones y privilegios runtime;
3. API y Nginx con settings de producción;
4. carga de imagen de producto;
5. WebP 320/640/1280;
6. adjunto de proforma;
7. verificación de keys lógicas;
8. verificación física en el host;
9. lectura por Nginx;
10. recreación de API/proxy;
11. lectura posterior a recreación;
12. eliminación autorizada;
13. ausencia de objetos huérfanos.

El gate usa un directorio temporal de prueba; no utiliza `/srv/homex/media`.

## Base de datos

D03 no crea ni modifica migraciones. Las keys continúan bajo `productos/` y `proformas/`.
Nunca se persisten paths absolutos del host.

## CI

El workflow incorpora `media-local-integration` y conserva regresiones D01/D02. La evidencia
remota final se registrará después de obtener el run completamente verde.

## Cierre

D03 se declara cerrada sólo cuando:

- backend F09.1 está cerrado;
- contrato Compose verde;
- gate integral verde;
- recreación conserva media;
- borrado no deja huérfanos;
- CI remoto de la rama está verde.
