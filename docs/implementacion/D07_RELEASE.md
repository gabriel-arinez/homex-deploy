# D07 — Release productiva y cierre de F10

## Estado

**IMPLEMENTACIÓN COMPLETA; PROMOCIÓN PRODUCTIVA PENDIENTE DE EJECUCIÓN EN EL HOST OBJETIVO.**

- rama: `feat/d07-release-productiva`;
- base deploy: `fb9c321324cfc621ac07cc42fdeb1e3257a968ab`;
- release candidata: `0.7.0-d07-rc1`;
- backend: `bc375894036d30cefbc8cdf7c512315aaf1ab971`;
- frontend: `479a092462b36a90006eb1c52f9570ea63084bab`;
- NLP: `79efeaf6a8ca738eb3abce414850f973b1962fd8`;
- paquete NLP consumido: `homex-nlp==0.1.0`, wheel SHA-256 `cfacc3a987f6158f43934cb64304fa50ea3e577cfa576f3db1e6d2a9576d19e6`;
- ASR: `Systran/faster-whisper-small@536b0662742c02347bc0e980a01041f333bce120`, LFS SHA-256 `3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671`.

No se modificó `homex-prod`. Los ensayos destructivos usan exclusivamente namespaces y rutas bajo
`/tmp`. Este documento separa el resultado automatizado del acto de promoción en el servidor.

## Release inmutable

`releases/manifest.yaml` fija fuentes, wheel, modelo, bases PostgreSQL/Redis, migraciones y tags
`d07-<sha7>`. Las imágenes incorporan labels OCI con la revisión fuente. Antes de migrar,
`scripts/deploy.sh` ejecuta `verify_release_images.py`: rechaza una imagen ausente, un label que no
coincida o una release marcada `released` sin el `RepoDigest` exacto.

El manifiesto permanece en `candidate`. El JSON Schema permite tags derivados de SHA durante
construcción, pero exige `tag@sha256:<digest>` en API, worker y frontend para `released`. La
promoción sólo procede después de publicar las imágenes finales en el registry, sustituir las tres
referencias por sus digests y repetir todos los gates sobre esos artefactos. Un ID local de Docker
no se presenta como digest distribuible.

API y worker comparten la misma imagen. Frontend se reconstruye desde el lock FE09. Las imágenes
base ya están fijadas por digest. PostgreSQL y Redis no exponen puertos en producción; Nginx TLS es
el único listener y el worker permanece en una red Docker `internal` sin ruta de descarga del
modelo.

## Integración y ASR

El gate privado heredado de D04 ahora consume exactamente Backend F10 y FE09. Verifica navegador
Vue, HTTPS, API, PostgreSQL, Redis, Celery, modelo local, ASR, NLP `RULES_ONLY`, propuesta, HITL,
persistencia comercial, documentos, media y eliminación del audio temporal. HITL sigue siendo la
autoridad humana y no aprueba proformas automáticamente.

El worker fija `--concurrency=1`. `profile_asr_runtime.py` mide, en el contenedor final y con el
modelo local:

- RSS antes y después de cargar el modelo, y RSS máximo;
- CPU del proceso;
- carga del modelo;
- primera transcripción y transcripción caliente;
- dos solicitudes secuenciales bajo la concurrencia efectiva;
- cero archivos de audio al finalizar.

La evidencia JSON no contiene texto, transcripción, rutas ni bytes de audio. Las cifras de CI no
representan el hardware productivo; el mismo comando debe ejecutarse en el PC definitivo y su JSON
debe anexarse al acta operacional antes de promover.

## Persistencia, recuperación y copia externa

PostgreSQL y media comercial forman una unidad indivisible. Audio, Redis, modelo, secretos y claves
TLS siguen excluidos. D05 destruye y restaura un entorno aislado, verifica checksums e inventario
antes de `dropdb`, aplica migraciones/permisos y ejecuta auditoría DB ↔ media. Ese ensayo constituye
la prueba de rollback: checkout/manifiesto anterior más restore completo de DB y media, nunca una
mezcla de estados.

D07 añade `backup_offsite.sh`. Usa una FIFO para no crear un tar intermedio en claro, comprueba por separado la serialización y el cifrado, y valida primero `SHA256SUMS`, crea un tar cifrado para una clave pública
GPG, publica archivo y checksum mediante rename y no copia datos en claro. El origen sólo necesita
la clave pública; la clave privada debe permanecer en custodia separada. `test_d07_offsite.sh`
genera una clave efímera, cifra, verifica checksum, descifra en `/tmp`, lista la unidad y demuestra
que no contiene audio. `backup_and_offsite.sh` encadena backup local y copia externa. Las unidades
systemd versionadas ejecutan el flujo a las 03:00, con `Persistent=true`; su destino debe ser un
mount/proveedor físicamente independiente, no otra carpeta del mismo disco.

### Integración operativa Restic + Cloudflare R2 (10-11 octubre 2026)

La copia externa **operacional** se realiza mediante `scripts/backup_restic.sh` directamente
sobre Restic/S3 en R2, sin montar el bucket. El operador ya inicializó el repositorio
cifrado `b1911bc781` en el bucket `homex-backups-prod` y confirmó subida,
restauración y SHA-256 de un archivo sintético (snapshot `1b2dbe40`).
La recuperación de PostgreSQL y media reales fue demostrada posteriormente, según el acta operacional.

`scripts/backup_and_offsite.sh` carga la configuración privada desde
`~/.config/homex/restic-r2.env`, verifica acceso remoto antes de crear una unidad D05,
ejecuta `backup.sh` y publica la unidad validada mediante Restic. La copia remota
queda etiquetada con `homex-d07-offsite` y el identificador de unidad `homex-...Z`.
El flujo comprueba el listado remoto del snapshot; la restauración e integridad se
prueban en CI con un repositorio local efímero, sin credenciales reales.

`scripts/backup_offsite.sh` y `scripts/test_d07_offsite.sh` se conservan
temporalmente para el contrato GPG histórico, pero **no se invocan desde el
servicio Restic**. No se debe configurar ni utilizar la ruta de montaje GPG
como respaldo productivo paralelo. Planificar su retiro con una fase controlada
para no romper evidencias de CI previas.

La unidad versionada `systemd/homex-backup.service` quedó instalada en el host el
11-10-2026 y el timer diario está activo. Ver acta operacional siguiente; no
confundir instalación del servicio de backup con promoción de las imágenes D07.

Los secretos S3 y contraseña de recuperación no se versionan. La retención
remota aún no se automatiza; no usar `restic forget --prune` hasta validar
la política y la restauración completa. La verificación de snapshots no
equivale por sí sola a `restic check --read-data` ni a recuperación probada.

## Acta operacional D05/R2 — 11 de octubre de 2026 (host objetivo)

Esta acta registra únicamente hechos observados y comprobados en el equipo HOMEX.
No equivale a promoción de la release D07: el runtime observado seguía usando imágenes
D04 (backend `homex/backend:d04-9ce7230`, frontend
`homex/frontend-proxy:d04-deba1de`).

| Gate real | Evidencia y resultado |
| --- | --- |
| R2 | Bucket `homex-backups-prod`; repositorio Restic cifrado `b1911bc781`; secretos privados fuera de Git, ficheros modo `0600` |
| Unidad D05 externa | `homex-20261009T051913Z` recuperada desde R2; seis archivos comparados con originales; cinco SHA-256 válidos; media tar legible |
| Recuperación PostgreSQL | Dump CUSTOM v1.16 (PostgreSQL 17.6) restaurado en contenedor efímero aislado (`--network none`), sin modificar producción |
| Objetos recuperados | 34 tablas, 52 funciones, 48 triggers y 52 migraciones; 5 clientes, 0 productos y 0 pedidos en la unidad usada |
| Media recuperada | Extracción segura y `media_inventory.py verify`: `media-checksums-ok` |
| CI de D07 | Commit `814d154`; push `38110687107` y PR `38110689479`, ambos `success` |
| Preflight systemd | RESTIC/R2, Docker 29.1.3, directorios, variables y restricciones de sandbox: éxito |
| Primer backup supervisado | `homex-20261011T041518Z`, snapshot Restic `395aaedb2a93`, salida `homex-backup-and-offsite-ok`, unidad `Result=success` |
| Backup automático sin intervención | Disparo excepcional 00:25 (-04) mediante `homex-d07-prueba-0025.timer`; unidad `homex-20261011T042511Z`, snapshot `f2a5e6e0843d` y `Result=success` |
| Verificación remota | `restic snapshots --tag homex-20261011T042511Z` y `restic ls f2a5e6e0843d` correctos |
| Estado posterior | API, worker, PostgreSQL, Redis, frontend-proxy y monitor activos/healthy donde existe healthcheck; timer diario habilitado y activo a las 03:00 (-04) |
| Rollback de systemd | Unidad previa resguardada fuera del repositorio en `~/Descargas/homex-backup-service-previo-d07-20261011-000522.service` |

Servicio actualmente instalado: `systemd/homex-backup.service` (Restic R2);
el `homex-backup.timer` del host está habilitado. Los backups cifrados
se crean sin cambiar el almacenamiento comercial `filesystem`; R2 se usa
**sólo como destino de backups**, no como backend activo de imágenes.

### Pendientes antes de promover D07

- [x] Offsite cifrado real, recuperación PostgreSQL y media en destino aislado.
- [x] Primera ejecución productiva supervisada y otra disparada por systemd sin intervención.
- [x] CI push/PR del commit de referencia en verde.
- [ ] Publicar imágenes D07 en registry y fijar `RepoDigest` de API/worker/proxy en manifiesto y Compose.
- [ ] Ejecutar build/migración/smoke de **release D07** en el host objetivo con ventana y rollback documentados; las imágenes D04 siguen desplegadas.
- [ ] Perfilar ASR/modelo en el host objetivo real y conservar el JSON técnico, incluyendo memoria/latencias y verificación de cero audio.
- [ ] Repetir smoke comercial y voz → NLP → HITL sobre release D07 en host real; validar media y documentos contra PostgreSQL.
- [ ] Revalidar PC/móvil/tablet autorizados, rechazo de dispositivo no autorizado y HTTPS/Cloudflare en la release D07.
- [ ] Ensayar rollback integral de la release D07 en namespace aislado; comprobar compatibilidad del manifiesto y las migraciones.
- [ ] Acordar política de retención **remota** y comprobar recuperación periódica; `restic forget --prune` aún no autorizado ni automatizado.
- [ ] Verificar comportamiento ante caída R2, alarma de fallo del timer y recuperación tras fallo del host; no se afirma cobertura completa de estas situaciones.

**Criterio de cierre:** no convertir `candidate` en `released`, ni crear tag final,
ni iniciar D08 hasta completar los gates restantes y revisar la evidencia física.
El PR #8 continúa abierto sin merge.

## Seguridad y operación

Se mantienen acceso privado Cloudflare, CA interna, cabeceras, límites de upload, logs sin bodies o
Authorization, correlación, rotación, límites CPU/RAM/PIDs, health/readiness y monitor D06. Los
secretos permanecen fuera de Git y del bundle Vue. El perfil ASR y la evidencia OCI sólo publican
metadatos técnicos. Los errores NLP no se vuelcan con traceback a logs de acceso.

Los runbooks de instalación, operación y recuperación describen migración, smoke, backup, copia
externa y rollback. D07 no cambia reglas comerciales, OpenAPI, tablas ni permisos.

## Gates automatizados

Antes de publicar la rama se ejecutan:

- JSON Schema y pruebas de promoción por digest;
- contrato D07 y contratos D02–D06;
- Compose productivo completo;
- build limpio de imágenes con labels OCI y evidencia de IDs locales;
- integración privada real y perfil ASR;
- backup/restore destructivo aislado;
- copia cifrada y descifrado aislado;
- resiliencia D06 y concurrencia idempotente;
- validación Python/Shell/YAML, `git diff --check` y gitleaks.

### Evidencia local aislada

| Gate | Resultado |
| --- | --- |
| contratos D00–D07 y Compose | verde |
| imágenes OCI | backend `sha256:6ad3546…`; frontend `sha256:f09ffec…`; labels fuente correctos |
| integración privada | 2/2 Playwright: recorrido comercial y voz/ASR/NLP/HITL |
| persistencia comercial | pedido/captura en PostgreSQL; audio temporal eliminado |
| superficies públicas | 4 documentos, media producto/proforma |
| modelo | snapshot/hash exactos; carga local |
| perfil ASR del host de desarrollo | carga 1,449 s; primera 2,980 s; caliente 3,767 s; CPU 15,087 s |
| memoria ASR del host de desarrollo | 72,398 MiB inicial; 651,875 MiB cargado; pico 856,133 MiB |
| concurrencia/privacidad ASR | `1`; dos transcripciones; 0 audios restantes |
| backup/restore/rollback aislado | verde; media 8/8; unidad corrupta rechazada antes de PostgreSQL |
| copia cifrada | cifrado, checksum, descifrado y contenido sin audio: verde |
| resiliencia D06 | todos los fallos controlados y recuperación: verde |

Estas cifras caracterizan este host de desarrollo; no sustituyen las métricas del PC definitivo.
La evidencia remota de CI y sus cantidades se registrarán después de publicar la rama.

## Checklist de promoción en el servidor

No ejecutar contra `homex-prod` sin ventana y autorización operacional:

1. publicar las imágenes y obtener sus `RepoDigest`;
2. actualizar el manifiesto a esas referencias, mantener `candidate` y verificar firma/checksum;
3. comprobar modelo local completo con `verify_asr_model.py` y ausencia de tráfico de descarga;
4. crear backup local y copia externa cifrada; restaurarlos en un namespace aislado;
5. ejecutar perfil ASR en el hardware objetivo y revisar RAM/CPU/latencias;
6. ejecutar migración controlada, smoke, readiness, monitor y reconciliación de outbox;
7. probar PC, tablet y móvil autorizados y el rechazo de un dispositivo no autorizado;
8. validar media real, documentos, flujo voz → HITL y cero audio temporal;
9. verificar Tunnel/HTTPS/cabeceras y que PostgreSQL, Redis y API no estén expuestos;
10. ejecutar el rollback ensayado en un namespace aislado con la unidad previa;
11. cambiar a `released` sólo con digests y toda la evidencia anterior verde.

## Condición de cierre

La implementación D07 queda lista para PR y puede demostrar la release en CI aislado. La
**promoción productiva de la release D07 no está ejecutada**: ya existe copia externa
real y backup programado, pero faltan digests de registry, perfil del hardware definitivo
y la ventana autorizada para desplegar la release D07,
acceso de dispositivos y smoke del host. Mientras falte cualquiera, el manifiesto permanece
`candidate`; Backend F10, NLP F10 y FE09 reciben evidencia técnica pero conservan su condición
productiva. No se adelanta D08 ni el piloto.

## Evidencia remota de implementación

- commit de implementación: `b3c857772f046c340d55be7794a853315715c33c`;
- workflow push `38010446638`: **13/13 jobs verdes**;
- workflow PR `38010466856`: **13/13 jobs verdes**;
- build limpio y labels OCI: verde;
- integración, staging, media, release privada, recuperación y resiliencia: verdes;
- contrato D07/copia cifrada, ASR, manifiesto, YAML, Compose y gitleaks: verdes;
- perfil ASR agregado publicado como artefacto temporal del workflow.

PR: https://github.com/gabriel-arinez/homex-deploy/pull/8
