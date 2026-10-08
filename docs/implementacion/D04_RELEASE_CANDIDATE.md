# D04 — Release candidate integrada y acceso privado

## Estado

**CERRADA — 8 de octubre de 2026.**

La release candidate reproducible quedó implementada y validada por CI y por pruebas reales en
laptop y Android TECNO. Se verificaron HTTPS privado, tunnel Cloudflare, captura física de audio,
ASR/NLP/HITL, aislamiento de un dispositivo no autorizado y caída/recuperación del tunnel.

## Base

- deploy: `b323f1f1fbf88fdc9d6ba658b8e138675bcb604b` (D03 fusionada);
- backend: `9ce723048d98a3925be45d9c359a25e6be7b19f3`;
- frontend: `deba1de244395dbdcb266f03026630b403768d71`;
- NLP source: `8d1750b2d1d26f6d90da10603216b7926bdaf820`;
- NLP package: `homex-nlp 0.1.0`;
- ASR: `Systran/faster-whisper-small@536b0662742c02347bc0e980a01041f333bce120`.

## Release candidate

`releases/manifest.yaml` define `0.4.0-d04-rc1` y fija fuentes, artefacto NLP, modelo ASR y tags
de imágenes derivados de los SHA de fuente (`d04-<sha7>`). Los IDs locales de Docker se observan
sólo como evidencia de build porque no son estables entre builds `--no-cache`. Si en el futuro se
publican imágenes en un registry, el contrato también admite referencias por digest `@sha256:`.

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
homex0 / 10.254.254.1:443
      |
Nginx TLS
      |  certificado homex.internal
      |  firmado por HOMEX Local Root CA
 ├── Vue
 ├── /api/  → Django
 └── /media/→ filesystem persistente
```

No se requiere dominio público.

## Endurecimiento productivo

`compose.production.yml`:

- elimina publicaciones de puertos de PostgreSQL, Redis y API;
- publica únicamente Nginx TLS en `10.254.254.1:443`, sobre la interfaz virtual persistente `homex0`;
- conserva media bind RW en API y RO en Nginx;
- fija settings Django de producción;
- añade límites iniciales CPU/RAM;
- incorpora `Celery beat` para scheduling operativo.

El frontend se construye para `https://homex.internal` y el Dockerfile rechaza source maps.

### Por qué D04 exige HTTPS aunque el túnel ya cifre el transporte

La captura de voz depende de APIs de navegador que requieren un **contexto seguro**. El primer gate
D04 sobre `http://homex.internal` reprodujo correctamente el flujo comercial, pero la vista de
captura no llegó a montar porque ese hostname HTTP no es un contexto seguro para APIs como
`crypto.randomUUID()` y el micrófono.

Por ello D04 mantiene el acceso privado de Cloudflare, pero añade TLS en Nginx sin comprar dominio:

- `scripts/generate_internal_tls.sh` crea una CA local HOMEX y un certificado para
  `homex.internal`;
- la clave privada de la CA y la clave del servidor quedan sólo en el host;
- los dispositivos autorizados instalan únicamente `homex-root-ca.crt`;
- Django usa `HOMEX_HTTPS_ENABLED=1` y Nginx envía `X-Forwarded-Proto=https`.

Esto conserva coste externo recurrente cero y habilita correctamente micrófono/funciones seguras
en PC, tablet y móvil.

## Cloudflare Tunnel

Se fija `cloudflared 2026.9.2` y se verifican SHA256 para Linux amd64/arm64 antes de instalar.

El servicio `homex-cloudflared.service` usa:

```text
--protocol http2
--token-file /etc/homex/cloudflared/tunnel-token
```

`scripts/setup_private_endpoint.sh` crea de forma idempotente `homex0` con `10.254.254.1/32` y
mantiene `homex.internal` en ese endpoint estable, desacoplándolo de la IP DHCP del servidor.

El token no se versiona, no se incluye en `.env.production.example` y no queda embebido en la
unidad systemd.

Runbook: `docs/private-access-cloudflare.md`.

## Gates automatizados

- contratos staging D02 y media D03 continúan como regresión;
- `scripts/test_d04_contract.py` valida puertos, HTTPS privado, mounts TLS, límites, settings,
  manifest, cloudflared y ausencia de secretos;
- build productivo reconstruye API/worker + frontend/proxy sin cache y verifica que los tags `d04-<sha7>` coincidan con el manifest;
- `scripts/test_d04_candidate.sh` genera TLS efímero de prueba y ejecuta la release productiva con
  PostgreSQL/Redis reales, worker, Celery beat, ASR/NLP, Nginx HTTPS y Playwright;
- el E2E valida primero `window.isSecureContext` y luego reutiliza el recorrido FE08 real:
  flujo comercial + captura de voz + HITL;
- `manage.py check` y `makemigrations --check --dry-run` corren dentro de la release;
- se verifica ausencia de source maps y secretos en el bundle.

## Validación externa real

Ya se comprobó en infraestructura real:

1. tunnel remoto `homex` activo en la organización Cloudflare Zero Trust `muebleria-homex`;
2. ruta **Private hostname** para `homex.internal`;
3. CA/certificado HOMEX generados y clave privada conservada sólo en el servidor;
4. `homex-root-ca.crt` confiado en el servidor y en Android TECNO;
5. Android enrolado mediante Cloudflare One Client;
6. `https://homex.internal` y `/api/v1/health/` accesibles desde el móvil;
7. acceso remoto validado también con datos móviles, fuera de la LAN;
8. listener productivo estabilizado en `homex0 / 10.254.254.1:443`;
9. `cloudflared` funcionando con cuatro conexiones registradas por HTTP/2;
10. secretos expuestos accidentalmente durante diagnóstico rotados y servicios revalidados.

Los gates manuales finales quedaron completados:

1. laptop autorizada: login, navegación y flujo micrófono → upload → ASR → NLP → HITL correctos;
2. Android TECNO autorizado: mismo flujo real completado correctamente;
3. dispositivo no enrolado: HOMEX no fue alcanzable; se observó `504 DNS look up failed` mediante
   Fortinet/DNS y no se expuso el login de HOMEX;
4. con `homex-cloudflared.service` detenido, el TECNO perdió acceso remoto y mostró
   `DNS_PROBE_POSSIBLE`;
5. tras iniciar nuevamente el servicio, `https://homex.internal` volvió a funcionar normalmente.

No se almacenarán tokens, capturas con secretos ni credenciales en Git.

## Cierre

**D04 CERRADA — 8 de octubre de 2026.**

No quedan gates funcionales, de acceso privado ni de resiliencia del tunnel pendientes para esta fase.
La siguiente fase formal es D05 — backup, restore, migración y rollback.


## Evidencia automatizada

Commit automatizado anterior validado: `1ed902ee25658294fcb357925bcf532d80bcfd77`.

Commit técnico actual validado: `f0a971f8f18520b53ea159f5c3ae4d69fe580079`.

GitHub Actions PR run `37800151828`: **success**.

Jobs verdes:

- `compose-config`;
- `yaml`;
- `release-contract`;
- `asr-contract`;
- `build`;
- `integration`;
- `staging-integration`;
- `media-local-integration`;
- `private-release-candidate`;
- `secrets`.

El gate D04 confirmó en HTTPS:

- `window.isSecureContext=true`;
- flujo comercial completo;
- captura de audio;
- ASR `faster-whisper-small` en el snapshot/hash fijado;
- NLP + worker + Celery beat;
- revisión HITL;
- evidencia PostgreSQL;
- documentos y media;
- ausencia de migraciones nuevas;
- ausencia de source maps y secretos en el bundle.

El fallo HTTP previo queda conservado como evidencia de por qué HTTPS no es opcional para el
navegador de HOMEX.

CI, infraestructura Cloudflare, laptop, Android TECNO, captura real y resiliencia del tunnel quedaron
validados. D04 no mantiene bloqueos abiertos.
