# D01 — Runtime integrado de backend + NLP

**Fecha:** 26 de septiembre de 2026  
**Rama:** `feat/d01-core-runtime`  
**Commit base:** `d1b4070` (merge D00 a `main`)  
**Estado:** implementación y gates locales completos; CI remoto pendiente del commit/push.

## Precondiciones

- D00 cerrada y fusionada, CI 4/4 verde.
- backend `9fac22ecc4f471237e6611b5a226532ab2a037ab`, F08.4 cerrada.
- NLP `b5fe2921320c9031f6d44dc5c91a18411daa393e`, F06 cerrada.

## Entregables

- imagen común API/worker construida desde lock y wheel local;
- PostgreSQL 17.6 y Redis 8.2.1 fijados;
- roles admin/migrador/runtime separados;
- jobs one-shot `migrate` y `grant-runtime`;
- API y worker con healthchecks;
- publisher, reconciler y cleanup como jobs independientes;
- temporal privado compartido y modelo ASR read-only;
- verificación del mapa real de migraciones;
- gate integral aislado y CI progresivo con jobs `build` e `integration`.

## Artefactos

- imagen: `homex/backend:d01-9fac22e`;
- digest local: `sha256:ea2fd64aca79858a3a8185c2629fcb63f7f158cb63a6d4a582177a95836d3b4f`;
- wheel NLP 0.1.0: `cfacc3a987f6158f43934cb64304fa50ea3e577cfa576f3db1e6d2a9576d19e6`;
- modelo ASR: snapshot `536b0662742c02347bc0e980a01041f333bce120`;
- `model.bin`: `3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671`.

## Evidencia local

| Gate | Resultado |
| --- | --- |
| Compose config | correcto con Compose v5.5.0 |
| contrato env | `env-contract-ok: 34 variables únicas` |
| release schema | `release-contract-tests-ok` |
| modelo ASR | `asr-model-ok` con hash exacto |
| build sin caché | imagen común construida desde lock |
| base vacía → migrate | todas las migraciones `OK` |
| segunda migrate | `No migrations to apply.` |
| privilegios | `runtime-privileges-ok` |
| migraciones hoja | `expected-migrations-ok: 11 apps HOMEX` |
| API + worker + NLP | `f084-real-ok` |
| temporal | modo `0700` |
| ASR | bind mount read-only; escritura rechazada por filesystem |
| persistencia PostgreSQL | `postgres-persistence-ok` tras stop/start |
| Redis caído | `postgres-outbox-survives-redis-outage-ok` |
| recuperación Redis | `publicados=1 errores=0` |
| cleanup sin worker | `eliminados=0`, comando exitoso con worker detenido |
| datos | PostgreSQL accepting connections; Redis `PONG` |
| gate final | `d01-runtime-ok` |

El gate se ejecutó bajo `homex-d01-gate` y eliminó exclusivamente sus contenedores, redes y
volúmenes efímeros. Durante el primer intento el host agotó disco por caché BuildKit; se eliminó
sólo caché regenerable, no imágenes etiquetadas ni volúmenes ajenos.

## Riesgos y límites

1. D01 usa el servidor Django real sólo para integración local. D02 requiere que backend fije un
   servidor WSGI/ASGI productivo.
2. `/api/v1/health/` sigue siendo liveness. Readiness real debe pertenecer a backend antes de D02.
3. El modelo ASR se provisiona fuera de Git; su snapshot y hash sí quedan versionados.
4. El digest anotado corresponde al build local verificado; una publicación a registry deberá
   registrar el digest remoto definitivo.

## Operación

Consultar `README.md` para arranque y jobs. El gate completo es:

```bash
ASR_MODEL_SOURCE=/ruta/faster-whisper-small \
POSTGRES_USER=postgres POSTGRES_DB=homex \
sh scripts/test_d01_runtime.sh
```

## Cierre

Pendiente de registrar commit final y CI remoto verde.
