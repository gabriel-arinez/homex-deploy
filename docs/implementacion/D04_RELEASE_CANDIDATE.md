# D04 — Release candidate integrada y acceso privado

## Estado

**EN CURSO.**

La parte reproducible del repositorio está implementada. D04 no se cerrará hasta validar un tunnel
real de Cloudflare Zero Trust y acceso desde escritorio + móvil/tablet autorizados.

## Base

- deploy: `b323f1f1fbf88fdc9d6ba658b8e138675bcb604b` (D03 fusionada);
- backend: `9ce723048d98a3925be45d9c359a25e6be7b19f3`;
- frontend: `deba1de244395dbdcb266f03026630b403768d71`;
- NLP source: `8d1750b2d1d26f6d90da10603216b7926bdaf820`;
- NLP package: `homex-nlp 0.1.0`;
- ASR: `Systran/faster-whisper-small@536b0662742c02347bc0e980a01041f333bce120`.

## Release candidate

`releases/manifest.yaml` define `0.4.0-d04-rc1` y fija fuentes, artefacto NLP, modelo ASR e IDs
de las imágenes construidas por CI.

La topología productiva utiliza:

```text
homex.internal
      |
Cloudflare One Client
      |
Cloudflare Zero Trust
      |
Cloudflare Tunnel
      |
cloudflared host
      |
127.0.0.1:8080
      |
Nginx
 ├── Vue
 ├── /api/  → Django
 └── /media/→ filesystem persistente
```

No se requiere dominio público.

## Endurecimiento productivo

`compose.production.yml`:

- elimina publicaciones de puertos de PostgreSQL, Redis y API;
- publica únicamente Nginx en `127.0.0.1:8080`;
- conserva media bind RW en API y RO en Nginx;
- fija settings Django de producción;
- añade límites iniciales CPU/RAM;
- incorpora `Celery beat` para scheduling operativo.

El frontend se construye para `http://homex.internal:8080` y el Dockerfile rechaza source maps.

## Cloudflare Tunnel

Se fija `cloudflared 2026.9.2` y se verifican SHA256 para Linux amd64/arm64 antes de instalar.

El servicio `homex-cloudflared.service` usa:

```text
--token-file /etc/homex/cloudflared/tunnel-token
```

El token no se versiona, no se incluye en `.env.production.example` y no queda embebido en la
unidad systemd.

Runbook: `docs/private-access-cloudflare.md`.

## Gates automatizados

- contratos staging D02 y media D03 continúan como regresión;
- `scripts/test_d04_contract.py` valida puertos, origen privado, límites, settings, manifest,
  cloudflared y ausencia de secretos;
- build productivo reconstruye API/worker + frontend/proxy sin cache y compara IDs con manifest;
- `scripts/test_d04_candidate.sh` ejecuta la release productiva con PostgreSQL/Redis reales,
  worker, Celery beat, ASR/NLP, Nginx y Playwright;
- el E2E reutiliza el recorrido FE08 real: flujo comercial + captura de voz + HITL;
- `manage.py check` y `makemigrations --check --dry-run` corren dentro de la release;
- se verifica ausencia de source maps y secretos en el bundle.

## Validación externa pendiente

Para cerrar D04 faltan evidencias no simulables por CI sin credenciales/dispositivos reales:

1. crear tunnel remoto en la organización Cloudflare Zero Trust;
2. crear ruta **Private hostname** para `homex.internal`;
3. enrolar al menos un escritorio y un móvil/tablet con Cloudflare One Client;
4. validar usuario/dispositivo autorizado;
5. validar rechazo de un dispositivo o identidad no autorizada;
6. registrar evidencia de tunnel saludable y acceso funcional;
7. confirmar que detener `homex-cloudflared.service` corta el acceso remoto.

No se almacenarán tokens, capturas con secretos ni credenciales en Git.

## Cierre

D04 sólo cambia a **CERRADA** después de CI verde y de las pruebas externas anteriores.
