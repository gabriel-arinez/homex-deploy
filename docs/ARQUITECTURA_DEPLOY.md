# Arquitectura de despliegue HOMEX

## Objetivo operativo

HOMEX se despliega inicialmente para un grupo pequeño de usuarios internos. La prioridad es
simplicidad, respuesta rápida, costo externo recurrente cero y una ruta de crecimiento sin
reescribir el dominio.

## Topología productiva

```text
PC / laptop / tablet / móvil autorizado
        |
  Cloudflare One Client
        |
 Zero Trust privado
        |
 Cloudflare Tunnel
        |
        v
https://homex.internal
  CA privada HOMEX
        |
        v
    Nginx TLS
 +------+-------+---------+
 |              |         |
Vue           /api/     /media/
                |          |
             Django    media host
                |
          +-----+------+
          |            |
     PostgreSQL      Redis
                       |
                  Worker + Beat
                   ASR + NLP
```

El túnel es saliente desde el servidor. La primera instalación no requiere IP pública,
port-forwarding ni dominio público.

HTTPS sí es obligatorio en D04: el navegador necesita un contexto seguro para micrófono,
`crypto.randomUUID()` y otras APIs sensibles. HOMEX lo resuelve con una CA privada instalada sólo
en los dispositivos autorizados.

## Fuentes de la release candidate D04

| Componente | Revisión/versión |
| --- | --- |
| backend | `9ce723048d98a3925be45d9c359a25e6be7b19f3` |
| frontend | `deba1de244395dbdcb266f03026630b403768d71` |
| NLP source | `8d1750b2d1d26f6d90da10603216b7926bdaf820` |
| NLP runtime | `0.1.0` |
| ASR | `Systran/faster-whisper-small@536b0662742c02347bc0e980a01041f333bce120` |
| release | `0.4.0-d04-rc1` |

D00–D03 permanecen como baseline cerrado. D04 ensambla la primera topología productiva privada.

## Persistencia

- PostgreSQL: volumen persistente y autoridad comercial.
- Redis: efímero/reconstruible.
- Media comercial: directorio del host `HOMEX_MEDIA_HOST_PATH`.
- API monta media RW en `/var/lib/homex/media`.
- Nginx monta la misma media RO y sirve `/media/`.
- Audio ASR: directorio/volumen separado, privado, temporal y excluido de backup.
- Modelo ASR: read-only y fijado.

Nunca se almacena media comercial en el writable layer efímero del contenedor.

## Contrato de media

Backend conserva keys relativas bajo:

```text
productos/
proformas/
```

La instalación inicial usa Django `FileSystemStorage`. El frontend sólo consume las URLs devueltas
por API. Un cambio futuro a S3/R2 no modifica tablas, endpoints ni componentes Vue.

## HTTPS interno

Nginx es el único listener de aplicación publicado al host y queda ligado a
`127.0.0.1:443`. Dentro del contenedor escucha en `8443`.

`scripts/generate_internal_tls.sh` administra:

- `homex-root-ca.key`: clave de CA que permanece exclusivamente en el servidor;
- `homex-root-ca.crt`: raíz que se instala como confiable en los dispositivos autorizados;
- `homex.internal.key` y `homex.internal.crt`: identidad TLS del servidor.

Django usa `HOMEX_HTTPS_ENABLED=1`; Nginx envía `X-Forwarded-Proto=https`.

## Red y acceso privado

La red Compose mantiene PostgreSQL/Redis aislados y no publica la API. Cloudflare Tunnel conecta de
salida desde el servidor y enruta el hostname privado `homex.internal` hacia el listener local.

Los dispositivos deben cumplir ambas condiciones:

1. estar autorizados/enrolados en Cloudflare Zero Trust;
2. confiar en `homex-root-ca.crt`.

No se compra un dominio sólo para habilitar el despliegue privado.

## Recuperación

La unidad mínima de backup es:

1. dump PostgreSQL;
2. directorio de media;
3. manifest/configuración no secreta de release.

Redis y audio no se restauran. Las claves privadas TLS son secretos operativos y se respaldarán
según la política definida en D05, separadas de los datos de aplicación.

D05 implementa `scripts/backup.sh`, `restore.sh`, `deploy.sh` y `smoke.sh`; cada unidad lleva
dump custom PostgreSQL, archivo e inventario SHA-256 de media y manifiesto de release. El restore
rechaza checksums o releases incompatibles y audita referencias DB ↔ archivos. Redis, audio ASR,
secretos y claves TLS privadas quedan fuera. El runbook es `docs/RECOVERY_RUNBOOK.md`.

La prueba de D05 destruye y reconstruye tanto DB como media antes de aceptar el backup.

## Rendimiento

Para la carga esperada se priorizan:

- mismo origen Vue/API/media;
- variantes WebP 320/640/1280;
- Nginx sirviendo binarios sin pasar cada GET por Django;
- PostgreSQL local al backend;
- polling operativo ligero en lugar de infraestructura push prematura;
- límites iniciales de CPU/RAM proporcionales;
- SSD y espacio de disco monitorizado.

## Escalabilidad

Si HOMEX crece, el orden de evolución es aumentar recursos, ampliar usuarios privados, mover media a
S3/R2 si se justifica y separar servicios/DB sólo cuando métricas reales lo indiquen. Ninguno de
esos pasos cambia las reglas comerciales.


## Observabilidad D06

Nginx genera un `request_id`, lo devuelve al cliente y lo propaga a Gunicorn. Ambos escriben JSON
sin headers de autorización ni cuerpos. Celery conserva su `task_id`; captura, intento y outbox
permiten seguir el salto asíncrono en PostgreSQL. Docker rota logs por tamaño y cantidad.

El monitor productivo consulta PostgreSQL, Redis y el health API, mide media/audio temporal y
escribe métricas Prometheus mediante archivo atómico. No publica endpoints ni accede al socket
Docker. El perfil productivo limita CPU, RAM y PIDs, y el gate D06 prueba fallos únicamente en un
namespace descartable.
