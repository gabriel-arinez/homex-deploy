# Apartado 0 — Cierre de estabilización técnica

**Fecha:** 2026-10-11, zona `America/La_Paz`.

**Resultado:** **APARTADO 0 CERRADO**.

**Alcance:** QA, recuperación, DevSecOps y resiliencia en namespaces aislados. No es promoción productiva de D07.

## Identidad y límites conservados

La candidata permanece `0.7.0-d07-rc2`, estado `candidate`, con Backend
`3e05362ac49c170963a8dc1d32b4d612e491112f`, Frontend
`479a092462b36a90006eb1c52f9570ea63084bab` y NLP
`79efeaf6a8ca738eb3abce414850f973b1962fd8`. Los digests OCI y el SHA-256 del
wheel no cambiaron. D08, Backend F11, NLP F11 y la promoción de D07 continúan
congelados.

`homex-prod` no recibió comandos Compose, migraciones, reinicios, escrituras ni
cambios de Cloudflare. Al final del ensayo sus siete servicios seguían activos
sobre D04; PostgreSQL, Redis, API, worker, proxy y monitor estaban saludables,
beat estaba activo y `homex-cloudflared.service` seguía `active`.

## Entornos y fuente de verdad

| Recurso | Uso | Aislamiento |
| --- | --- | --- |
| `homex-qa0-20261011` | restauración D04, actualización RC2 y resiliencia | proyecto, redes, volúmenes, media y puertos propios |
| `homex-qa0-failure-20261011` | fallo real durante migración y rollback | segundo proyecto, redes, volúmenes, media y puertos propios |
| `/srv/homex/backups/homex-20261009T051913Z` | unidad D04 original, solo lectura lógica | checksums verificados antes y después |
| `~/Descargas/homex-qa0-20261011` | runtime del primer ensayo | datos sintéticos sin información comercial real |
| `~/Descargas/homex-qa0-failure-20261011` | runtime del segundo ensayo | fallo inducido exclusivo del namespace |
| `~/Descargas/qa0-diagnostico-20261011` | logs sanitizados del host | fuera de Git por decisión del handoff |

La evidencia resumida y sanitizada está versionada en
`docs/evidencias/qa0-cierre-20261011.json`. Los logs locales conservan la salida
completa de los comandos sin secretos.

## Recuperación integral D04 → RC2 → D04

1. La unidad D04 original pasó `sha256sum -c SHA256SUMS` antes y después.
2. La restauración inicial produjo `homex-restore-ok`,
   `runtime-privileges-ok` y `db-media-integrity-ok`.
3. Se creó un fixture sintético mediante ORM y almacenamiento real: dos
   productos, dos proformas, un adjunto, tres Outbox y ocho WebP. PostgreSQL
   referenciaba 8 archivos y el filesystem contenía exactamente esos 8.
4. Se generó una unidad D04 nueva. Verificó dump, inventario, archivos, release
   y exclusión del sentinel de audio temporal.
5. Con escritores D04 detenidos se aplicó RC2. La migración
   `capturas.0008_propiedad_ejecucion` terminó, los conteos pasaron de 52/7 a
   53/8 migraciones totales/de Capturas, y API, HTTPS, proxy, Redis, worker,
   beat y monitor regresaron operativos. Los ocho medios permanecieron íntegros.
6. En el segundo namespace se montó una migración exclusiva del ensayo. Primero
   aplicó `0008`; después creó `qa0_partial_migration` y lanzó una excepción.
   `deploy.sh` terminó distinto de cero, imprimió su advertencia de recuperación,
   no registró la migración fallida y mantuvo API, worker y beat D04 detenidos.
7. El restore de la unidad D04 eliminó la tabla parcial y `0008`, recuperó 52/7
   migraciones, todos los datos sintéticos y 8/8 archivos. HTTP de frontend y
   health respondieron, Redis devolvió `PONG`, el worker devolvió `pong` y beat
   publicó tareas periódicas nuevamente.

## Outbox, Redis, worker, idempotencia y fencing

Sobre RC2 se detuvieron Redis y worker realmente. Dos recepciones con la misma
clave produjeron una captura, un intento y un Outbox. La publicación fallida
conservó el trabajo y registró el error. Tras recuperar Redis, el primer intento
publicó uno y el segundo cero. La inspección de la cola confirmó exactamente un
mensaje `capturas.procesar_intento`; las demás entradas eran tareas periódicas
de beat. El worker consumió la captura una vez, dejó un `ItemIA`, finalizó el
intento y vació la cola.

La prueba concurrente de recepción produjo `[False, True]` para creación/replay.
Dos ejecuciones simultáneas del mismo intento produjeron `PROCESANDO` y
`FINALIZADO`, un único `ItemIA` y un token UUID de ejecución. La limpieza
eliminó un audio terminal vencido. Ningún audio apareció en las unidades D04,
Restic ni la evidencia versionada.

## Restic/R2 y operación

La inspección no destructiva encontró tres snapshots etiquetados
`homex-d07-offsite`. `restic check` comprobó índices, packs, snapshots, árboles
y blobs sin errores. El snapshot `f2a5e6e0843d` se restauró en
`~/Descargas/qa0-restic-restore-20261011`; sus cinco checksums pasaron y el tar
de media no contenía audio. Las credenciales y contraseña tienen modo `0600`.
Un repositorio REST inaccesible aislado devolvió código 1, confirmando que el
fallo se propaga. El servicio instalado conserva `Result=success`; el timer está
activo para las 03:00 y todavía no registra una ejecución disparada por timer.

Propuesta pendiente de aprobación operacional:

- RPO objetivo: 24 horas mientras exista un backup diario; reducir a 4 horas
  antes del piloto si el volumen de ventas lo exige.
- RTO objetivo medible: 60 minutos para host + PostgreSQL + media + servicios;
  repetir trimestralmente y registrar duración real.
- Retención local: conservar los 14 días ya configurados.
- Retención remota propuesta: 14 diarios, 8 semanales y 12 mensuales. No
  automatizar `forget --prune` hasta aprobar capacidad, coste y doble custodia.
- Responsable operativo: administrador de infraestructura HOMEX; responsable
  de negocio para autorizar pérdida máxima y ventana; custodio separado para
  contraseña/credenciales de recuperación.
- Alertas pendientes de canal autorizado: fallo del servicio, snapshot con más
  de 26 horas, `restic check` fallido, espacio local crítico y restore trimestral
  no conforme. Systemd/journal ya exponen los fallos, pero aún no existe destino
  de notificación aprobado.

## Matriz de cierre

| Gate | Estado | Evidencia |
| --- | --- | --- |
| cuatro `main` y CI vigentes | PASS | runs `38192027974`, `38188201596`, `38188210073`, `38192289486` |
| corrección CI frontend | PASS | frontend `70883b0`, 12/12 jobs |
| inventario host y aislamiento | PASS | proyectos y montajes identificados; dos namespaces nuevos |
| restore D04 inicial | PASS | tres marcadores finales; 52/7 migraciones |
| media PostgreSQL ↔ filesystem | PASS | 8 referenciados, 8 presentes, 0 faltantes, 0 huérfanos |
| migración D04 → RC2 | PASS | `0008`, 53/8 migraciones, stack RC2 operativo |
| fallo después de iniciar migración | PASS | DDL parcial presente, código 1, escritores detenidos |
| rollback RC2 → D04 | PASS | DDL parcial ausente, 52/7, stack completo operativo |
| Redis/worker/Outbox | PASS | caída real, conservación, reintento y consumo único |
| idempotencia/concurrencia/fencing | PASS | replay único, dos hilos, token UUID, un `ItemIA` |
| audio efímero | PASS | cleanup real y ausencia en backups/evidencias |
| Restic/R2 | PASS | 3 snapshots, `check`, restore y checksums |
| detección de fallo offsite | PASS | conectividad aislada fallida con código 1 |
| retención remota automática | BLOCKED | requiere política/coste/responsables aprobados; no bloquea este cierre técnico |
| alertas externas | BLOCKED | falta canal y responsable autorizados; journal/systemd sí registra fallos |
| branch protection/rulesets | BLOCKED | GitHub informa `protected: false`; modificación remota no autorizada |
| promoción productiva D07 | NOT RUN | expresamente fuera de Apartado 0 |
| pruebas físicas definitivas | NOT RUN | diferidas por criterio aprobado |

Los tres `BLOCKED` son decisiones operativas futuras delimitadas y no ocultan
un fallo de recuperación. Ninguna prueba crítica del Apartado 0 quedó sin
ejecutar.

## Reproducción

Los comandos siguientes usan siempre un proyecto de prueba; nunca sustituirlo
por `homex-prod`:

```bash
# Estado remoto y CI
git fetch --prune origin
gh run list -R gabriel-arinez/homex-deploy --branch main --limit 3

# Unidad original
(cd /srv/homex/backups/homex-20261009T051913Z && sha256sum -c SHA256SUMS)

# Restore aislado; ENV apunta a rutas, secretos y puertos exclusivos del ensayo
COMPOSE_PROJECT_NAME=homex-qa0-AAAA HOMEX_ENV_FILE=/ruta/qa0.env \
HOMEX_COMPOSE_FILES='-f docker-compose.yml -f compose.production.yml' \
HOMEX_MEDIA_HOST_PATH=/ruta/media HOMEX_MEDIA_UID="$(id -u)" \
HOMEX_MEDIA_GID="$(id -g)" \
sh scripts/restore.sh /ruta/backup-d04 --confirm

# Gates de contrato/locales
python3 scripts/test_qa0_contract.py
python3 scripts/test_d07_contract.py
python3 scripts/test_d07_deploy_behavior.py
sh scripts/test_d07_offsite.sh
sh scripts/test_d07_restic.sh

# Restic remoto de solo lectura
set -a; . "$HOME/.config/homex/restic-r2.env"; set +a
export RESTIC_PASSWORD_FILE="$HOME/.config/homex/restic-password"
restic snapshots --tag homex-d07-offsite
restic check
restic restore <snapshot> --target "$HOME/Descargas/qa0-restic-restore"
```

La migración fallida se reprodujo con un override Compose que montaba una
migración `atomic = False` sólo en el servicio `migrate` del segundo namespace.
El archivo creó una tabla parcial y lanzó `RuntimeError`; no forma parte de la
imagen, del repositorio ni de producción.
