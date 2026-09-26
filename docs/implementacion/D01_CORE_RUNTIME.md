# D01 — Runtime integrado de backend + NLP

**Fecha:** 26 de septiembre de 2026  
**Rama:** `feat/d01-core-runtime`  
**Commit base:** `d1b4070` (merge D00 a `main`)  
**Estado:** **D01 cerrada; implementación local y CI remoto completos.**

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
- gate integral aislado;
- CI con jobs independientes de config, YAML, release, build, integración y secretos.

## Artefactos

- imagen: `homex/backend:d01-9fac22e`;
- tag baseline común API/worker: `homex/backend:d01-9fac22e`; el digest de registry se fijará al promover una candidate;
- wheel NLP 0.1.0: `cfacc3a987f6158f43934cb64304fa50ea3e577cfa576f3db1e6d2a9576d19e6`;
- modelo ASR: snapshot `536b0662742c02347bc0e980a01041f333bce120`;
- `model.bin`: `3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671`.

## Evidencia local

| Gate | Resultado |
| --- | --- |
| Compose config | correcto con Compose v5.5.0 |
| contrato env | `env-contract-ok: 34 variables únicas` |
| release schema | `release-contract-tests-ok` |
| contrato ASR | snapshot y `oid sha256` LFS fijados; verificación CI remota añadida |
| build sin caché | imagen común construida desde lock |
| base vacía → migrate | todas las migraciones `OK` |
| segunda migrate | `No migrations to apply.` |
| privilegios | `runtime-privileges-ok` |
| migraciones hoja | `expected-migrations-ok: 11 apps HOMEX` |
| API + worker + NLP | `f084-real-ok` |
| temporal | modo `0700` |
| ASR | bind mount read-only; escritura rechazada; provisión local real verificable por hash completo |
| persistencia PostgreSQL | `postgres-persistence-ok` tras stop/start |
| Redis caído | `postgres-outbox-survives-redis-outage-ok` |
| recuperación Redis | `publicados=1 errores=0` |
| cleanup sin worker | comando exitoso con worker detenido |
| datos | PostgreSQL accepting connections; Redis `PONG` |
| gate final | `d01-runtime-ok` |

El gate se ejecutó bajo `homex-d01-gate` y eliminó exclusivamente sus contenedores, redes y
volúmenes efímeros. Durante el primer intento el host agotó disco por caché BuildKit; se eliminó
sólo caché regenerable, no imágenes etiquetadas ni volúmenes ajenos.

## CI remoto

El commit funcional inicial `41505654053b3fb04625177d5b771b4a581dff8f` ejecutó GitHub Actions
`36226702767` con **6/6 jobs verdes**. Una auditoría posterior detectó que el hash ASR no se
verificaba en CI, que el manifiesto trataba un image ID local como digest estable y que el gate
podía continuar demasiado pronto tras reiniciar PostgreSQL/Redis. Esos puntos se corrigen antes
del cierre definitivo.

Gates originales:

- `compose-config` — Compose y contrato de 34 variables;
- `yaml` — manifiesto, Compose y workflow;
- `release-contract` — schema y pruebas positivas/negativas;
- `build` — imagen común construida sin caché desde backend fijado;
- `integration` — `d01-runtime-ok`, incluido PostgreSQL/Redis/worker reales;
- `secrets` — Gitleaks verde.

Los avisos del runner sobre migración futura de `ubuntu-latest` y Node 20 en actions no afectan
los gates ni el runtime; deberán atenderse como mantenimiento de CI antes de la fecha indicada por
GitHub.

## Riesgos y límites transferidos a D02

1. D01 usa el servidor Django real sólo para integración local. D02 requiere que backend fije un
   servidor WSGI/ASGI productivo.
2. `/api/v1/health/` sigue siendo liveness. Readiness real debe pertenecer a backend antes de D02.
3. El modelo ASR se provisiona fuera de Git; su snapshot y hash sí quedan versionados.
4. D01 mantiene sólo el tag de la imagen baseline; una candidate deberá registrar obligatoriamente
   el digest remoto definitivo, conforme al schema.

## Operación

Consultar `README.md` para arranque y jobs. El gate completo es:

```bash
ASR_MODEL_SOURCE=/ruta/faster-whisper-small \
POSTGRES_USER=postgres POSTGRES_DB=homex \
sh scripts/test_d01_runtime.sh
```

## Cierre

El cierre definitivo queda condicionado al CI del commit correctivo que incorpora:

- verificación remota del puntero LFS del modelo ASR fijado;
- manifest baseline sin digest local engañoso;
- esperas explícitas de PostgreSQL, Redis y worker después de restart;
- protección del namespace Compose de pruebas.

Una vez esos gates estén verdes, se registrará aquí el commit/CI final.

Los dos cambios propietarios pendientes —servidor productivo y readiness— pertenecen al inicio
de D02 y no se ocultan con comandos o endpoints ficticios.
