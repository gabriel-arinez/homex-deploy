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

### Guardia de migración controlada (11-10-2026)

La revisión del script en el host demostró que `backup.sh` **reanuda**
API/worker/beat al terminar su captura consistente. El `deploy.sh` anterior
ejecutaba inmediatamente `migrate` con esos escritores D04 funcionando;
esto no es seguro frente a migraciones no compatibles.

Ahora `deploy.sh`, después del backup, identifica los escritores activos
(`api`, `worker`, `beat`, `publisher`, `reconciler`, `cleanup`),
los detiene antes de `migrate` y sólo inicia la release D07 después de
migraciones y concesión de privilegios. Un error **previo** al inicio de
migraciones intenta reponer los escritores detenidos; si una migración empezó
y posteriormente falla, **no** se reactivan procesos D04 automáticamente
contra un esquema potencialmente modificado: intervención mediante el
runbook de recuperación y unidad respaldada.

Esto es una mejora preventiva del procedimiento, **no evidencia de que un
despliegue D07 productivo ya haya ocurrido**. Queda ensayar en namespace
aislado la recuperación de una migración fallida y verificar que el servicio
diario de backup no coincida con la ventana de promoción.

### Evidencia de ensayo D07 aislado en host (11-10-2026)

Se ejecutó el namespace `homex-d07-ensayo`, independiente de
`homex-prod`, con PostgreSQL 17.6, Redis 8.2.1, TLS temporal y volúmenes
propios bajo `/tmp/homex-d07-ensayo`. Evidencias observadas:

- Migraciones iniciales aplicadas sin fallos; nueva ejecución sin cambios:
  **52 migraciones** registradas, **34 tablas** de sistema.
- `runtime-privileges-ok` y rechazo de conexión inválida del migrador sin
  cambios en el historial de migraciones.
- Backup D07 `homex-20261011T051035Z`, con checksum correcto para los cinco
  archivos exigidos y tabla de ensayo incluida en el dump.
- Restauración destructiva **solamente en el namespace de prueba**, autorizada
  para ese entorno: `homex-restore-ok`, registro original recuperado,
  **52 migraciones y 35 tablas** (incluida la tabla de ensayo),
  `db-media-integrity-ok`.
- Validación posrestauración: `manage.py check` sin incidencias;
  `migrate --check` correcto; `django-database-ok`; cinco checksums
  correctos; `homex-d07-verificacion-final-ok`.
- Los siete contenedores productivos D04 se observaron operativos durante
  las verificaciones, sin intervención del ensayo.

Alcance: prueba de instalación D07 limpia, fallo de conexión previa y
restauración de backup **D07 a D07**. No valida todavía transición de datos
D04 → D07, rollback de código/imágenes entre versiones ni fallo a mitad de
una migración. El entorno de ensayo queda conservado hasta autorizar limpieza
aislada; la promoción productiva sigue pendiente.

### Evidencia adicional de transición D04 → D07 → D04 (11-10-2026)

Se compararon 34 archivos de migración de las aplicaciones entre las imágenes
`homex/backend:d04-9ce7230` y `homex/backend:d07-bc37589` por SHA-256:
**0 añadidos, 0 eliminados y 0 modificados**. Los archivos de modelos de
clientes, catálogo y pedidos también coincidieron por SHA-256.

En el namespace descartable `homex-d07-upgrade` se inicializó PostgreSQL
con D04 y se creó mediante su ORM un escenario comercial sintético:
cliente ID 2, silla ID 2, carga inicial 10 unidades, proforma 970000001
por Bs 700, aprobación que generó automáticamente pedido ID 2 y venta
de 2 unidades, quedando stock 8. Un primer intento sin stock fue rechazado
correctamente por el trigger y su transacción se revirtió.

Sin reconstruir PostgreSQL, se ejecutó `migrate` con la imagen D07:
**No migrations to apply**; `runtime-privileges-ok` y verificaciones ORM
de relaciones, importes, estados, movimientos y 52 migraciones exitosas
(`homex-d07-upgrade-d04-a-d07-ok`). A continuación se revalidaron los
mismos datos mediante imagen D04: `manage.py check` sin errores,
`migrate --check` correcto, `homex-d07-rollback-d04-lectura-ok`.

Se completó adicionalmente el **rollback operativo de la API** sobre el mismo
namespace con `docker compose up -d --no-deps --force-recreate api`:
la API D04 arrancó `healthy` con respuesta 200 en `/api/v1/health/`
(`homex-d07-api-d04-healthy-ok`), fue reemplazada exclusivamente por
API D07 `healthy`, también con 200 en health, conservando IDs de
PostgreSQL/Redis y datos comerciales (`homex-d07-api-d07-healthy-ok`).
Finalmente se recreó exclusivamente la API D04: `healthy`, HTTP 200,
mismos IDs de PostgreSQL/Redis, datos/stock/importes intactos, `manage.py check`
y `migrate --check` correctos (`homex-d07-rollback-api-d04-completo-ok`).
Las comprobaciones de montaje permitieron solo media temporal aislada,
volúmenes con prefijo de proyecto y los dos archivos de configuración del
repositorio montados en modo lectura. Ninguna API del ensayo publicó puertos.

También se ensayó el proxy HTTPS del frontend con la CA autofirmada
**exclusiva** de `/tmp/homex-d07-upgrade/tls` y publicación en
`127.0.0.1:19444`. El proxy D04 inició `healthy` y retornó HTTP 200
con validación TLS (`homex-d07-frontend-d04-https-ok`). Se recreó **solo**
el frontend con imagen D07: `healthy`, frontend y
`/api/v1/health/` HTTP 200 mediante HTTPS, sin recrear API/PostgreSQL/Redis
(`homex-d07-frontend-d07-https-ok`). Finalmente el proxy volvió a la
imagen D04: `healthy`, HTTP 200 en ambos endpoints, sin recreaciones de
API/PostgreSQL/Redis (`homex-d07-frontend-rollback-d04-ok`). Los
certificados eran temporales del ensayo y no se usaron certificados
productivos. La advertencia de Nginx al intentar modificar una
configuración de solo lectura no impidió el arranque ni el healthcheck.

Se completó también el retorno del proceso **Celery worker**. La imagen D04
arrancó `healthy`, con Redis aislado conectado, cuatro tareas registradas,
concurrencia 1 y consumo de ~97 MiB
(`homex-d07-worker-d04-healthy-ok`). Al recrear exclusivamente worker con D07
se obtuvo `healthy`, Redis conectado y ~98 MiB, sin recrear API, frontend,
PostgreSQL ni Redis (`homex-d07-worker-d07-healthy-ok`). El retorno a worker
D04 recuperó `healthy`, registro de tareas y conexión a Redis, manteniendo
API accesible con HTTPS 200 y el resto de contenedores intactos
(`homex-d07-worker-rollback-d04-ok`). Beat del ensayo permaneció detenido.
**No** se enviaron tareas de transcripción; el directorio ASR de ensayo
contiene sólo un `model.bin` vacío y el resultado **no** demuestra capacidad
de procesar audio.

La programación efectiva de Celery Beat se inspeccionó en ambas imágenes:
tres tareas idénticas (`capturas.publicar_outbox` cada 5 s,
`capturas.reconciliar_outbox` cada 60 s y
`capturas.limpiar_audio_temporal` cada 900 s), zona
`America/La_Paz` y `PersistentScheduler`. Para evitar publicaciones
durante la prueba, Beat se ejecutó mediante un proceso temporal con
programación vaciada **después de cargar** la configuración de Celery.
Tanto D04 (`homex-d07-beat-d04-controlado-ok`) como D07
(`homex-d07-beat-d07-controlado-ok`) mostraron inicio real
(`celery beat v5.5.3`, `beat: Starting...`) y finalizaron a los
15 segundos por `timeout` (código 124). El servicio permanente
`beat` no se inició y producción permaneció sin cambios.
**No se comprobó publicación ni ejecución efectiva de tareas periódicas.**

En el namespace `homex-d07-upgrade` se validó la integración
**Beat → Redis → worker** con programación temporal limitada a
`capturas.limpiar_audio_temporal` cada 3 segundos, directorio de audio
vacío y cola inicialmente vacía. En D04 Beat + worker D04 se publicaron,
recibieron y completaron tres tareas (resultado 0; cola final vacía):
`homex-d07-beat-redis-worker-d04-ok`. El primer intento registró una
advertencia del archivo scheduler por abrir dos instancias, aunque
las tres tareas finalizaron. Se corrigió usando un scheduler único.
En la siguiente prueba, **Beat D07 → worker D04**, las tres tareas
se recibieron y finalizaron correctamente, sin advertencia de archivo
de scheduler (`homex-d07-beat-d07-redis-worker-d04-ok`).
Beat permanente permaneció detenido y producción intacta. Estas
pruebas **no** validan outbox, reconciliación ni transcripción ASR.

La integración **Beat D07 → Redis aislado → worker D07** también pasó:
se configuró una sola tarea temporal `capturas.limpiar_audio_temporal`
cada tres segundos, se enviaron/recibieron/ejecutaron correctamente tres
tareas con resultado 0, quedaron vacías las colas `celery` y `unacked`,
el worker D07 permaneció `healthy` y Beat permanente detenido
(`homex-d07-beat-worker-d07-integracion-ok`). Los componentes de
producción siguieron intactos. Queda pendiente el retorno del worker
a D04 y revalidar la integración; las tareas reales de outbox y ASR
continúan fuera de este ensayo.

Tras la integración Beat D07 + worker D07, se realizó nuevamente el
rollback **worker D07 → D04** en el namespace aislado: imagen D04,
estado `healthy`, Redis conectado, cuatro tareas registradas y colas
`celery`/`unacked` vacías. PostgreSQL, Redis, API y frontend conservaron
sus IDs; HTTPS `/api/v1/health/` respondió 200 y producción permaneció
intacta (`homex-d07-worker-rollback-post-integracion-ok`). Queda pendiente
la comprobación funcional Beat D04 → worker D04 después del retorno.

Se completó la prueba funcional **posterior al rollback** con Beat D04,
Redis aislado y worker D04. Beat publicó tres tareas temporales de
`capturas.limpiar_audio_temporal` a intervalos de tres segundos;
el worker D04 recibió y ejecutó satisfactoriamente las tres
(resultado 0), las colas quedaron vacías, el worker permaneció
`healthy`, HTTPS `/api/v1/health/` respondió 200 y el servicio Beat
permanente siguió detenido. Los siete contenedores productivos no
se alteraron: `homex-d07-rollback-celery-funcional-completo-ok`.
**Cierre satisfactorio únicamente de la batería controlada de
compatibilidad y rollback de Celery para esta tarea**; ASR real,
outbox y recuperación integral desde respaldo no están cubiertos.

La **lógica transaccional de Outbox** se comprobó en D04 y D07 con
nueve verificaciones por versión: trigger de creación de trabajo por
intento, publicación con emisor simulado, no duplicación, registro de
fallo, reintento, reconciliación de trabajo antiguo, reconciliación
idempotente, límite de publicaciones y rollback de la transacción.
Ambas imágenes pasaron y quedaron cero capturas, intentos y trabajos
persistidos; Redis `celery`/`unacked` quedó vacío:
`homex-d07-outbox-d04-validacion-completa-ok` y
`homex-d07-outbox-d07-validacion-completa-ok`.
La primera versión del ensayo intentaba insertar un trabajo duplicado;
se corrigió para consumir el trabajo creado automáticamente por
`trg_crear_outbox_intento`. **Pendiente:** publicación real en Redis,
entrega/consumo seguro y pruebas de fallos de broker, sin activar ASR.

La publicación **real** de Outbox D07 hacia Redis aislado pasó
(`homex-d07-outbox-redis-publicacion-d07-ok` y
`homex-d07-outbox-redis-d07-validacion-ok`): la función
`publicar_pendientes` envió `capturas.procesar_intento` a una cola
temporal exclusiva no consumida por el worker; se validaron nombre,
identificador y argumentos del mensaje, se retiró el mensaje de prueba
y la transacción PostgreSQL revirtió captura, intento y outbox
sintéticos. Las colas operativas `celery`/`unacked` terminaron vacías.
Los siete servicios productivos permanecieron activos. Este ensayo
**no** ejecutó ASR ni validó consumo de la tarea; queda pendiente
paridad de publicación real D04 y escenarios de fallo de broker.

La paridad de **publicación real a Redis** se completó también para
Outbox D04: `publicar_pendientes` envió una tarea
`capturas.procesar_intento` a una cola sintética exclusiva, se verificaron
nombre, ID y argumentos, se retiró el mensaje, se revirtieron los
registros PostgreSQL y `celery`/`unacked` permanecieron vacías
(`homex-d07-outbox-redis-publicacion-d04-ok`,
`homex-d07-outbox-redis-d04-validacion-ok`). D04 y D07 pasaron
la misma prueba; no hubo consumo por el worker ni ejecución de ASR.
Pendiente ensayar fallo de envío al broker y recuperación de Outbox.

En D07 se ensayó fallo y recuperación de publicación Outbox usando
un puerto Redis inaccesible sin detener el broker aislado real:
`publicar_pendientes` registró un `ConnectionError`, conservó el
trabajo pendiente y su clave única; el reintento publicó en una
cola sintética exclusiva del Redis aislado y preservó el mismo ID.
Se retiró el mensaje, se revirtieron los registros sintéticos y
`celery`/`unacked` permanecieron vacías
(`homex-d07-outbox-fallo-recuperacion-ok`,
`homex-d07-outbox-recuperacion-validada-ok`). Producción no cambió.
**No** representa una caída del servicio Redis ni ejercicio de ASR.
Queda pendiente la paridad D04 para este escenario y la
reconciliación integrada de eventos.

La paridad D04/D07 de **fallo de conexión y recuperación de Outbox**
también se confirmó para D04: fallo TCP simulado a puerto Redis
inaccesible, conservación de trabajo y clave única, reintento real
publicado en cola exclusiva de Redis aislado, mensaje de prueba retirado,
transacción PostgreSQL revertida y colas operativas intactas
(`homex-d07-outbox-fallo-recuperacion-d04-ok`,
`homex-d07-outbox-recuperacion-d04-validada-ok`). D04 y D07 superaron
el mismo escenario, sin detener Redis ni ejecutar ASR. Siguiente control:
reconciliación de publicaciones antiguas y reenvío seguro.

**Reconciliación y republicación Outbox D04/D07:** ambas imágenes superaron nueve comprobaciones del ensayo controlado con un intento sintético antiguo en estado `PROCESANDO`: recuperación a `PENDIENTE`, segunda reconciliación sin nuevas acciones, republicación de un solo mensaje en una cola Redis aislada conservando la clave de tarea y ausencia de publicación duplicada. Los mensajes de prueba se retiraron, los datos PostgreSQL se revirtieron y las colas operativas permanecieron vacías. Evidencias: `homex-d07-outbox-reconciliacion-d07-ok`, `homex-d07-outbox-republicacion-d07-validada-ok`, `homex-d07-outbox-reconciliacion-d04-ok` y `homex-d07-outbox-republicacion-d04-validada-ok`. No se ejecutaron tareas ASR ni hubo consumo de esta cola por el worker. El ensayo no prueba idempotencia tras consumo por el worker ni caída integral de Redis.

**Alcance limitado:** la transición D04 → D07 → D04 valida lectura
comercial y retorno operativo **de la API**, no rollback integral de
beat ni de tareas ASR, ni restauración desde una unidad anterior a la
actualización, ni ensayos de fallo a mitad de migración. No se modificó
`homex-prod`. El namespace de ensayo queda pendiente de limpieza al
concluir los gates.

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


## Actualización de candidata RC2 — Backend con fencing token

La candidata `0.7.0-d07-rc2` sustituye a RC1 para las siguientes
validaciones. Las evidencias históricas RC1 se conservan.

### Identificación

- Backend: `3e05362ac49c170963a8dc1d32b4d612e491112f`.
- Imagen API/worker: `homex/backend:d07-3e05362`.
- Migración nueva: `capturas.0008_propiedad_ejecucion`.
- Frontend: `479a092462b36a90006eb1c52f9570ea63084bab`.
- NLP: `79efeaf6a8ca738eb3abce414850f973b1962fd8`.
- Estado del manifiesto: `candidate`.
- Producción `homex-prod`: continúa ejecutando D04.

### Evidencias funcionales RC2

Se realizaron pruebas en el namespace aislado `homex-d07-upgrade`,
con API y worker RC2 temporales y cola Celery exclusiva.

Resultados verificados:

- Creación de proforma y capturas sintéticas mediante servicios reales.
- Idempotencia de recepción y rechazo de reutilización conflictiva de claves.
- Publicación Outbox mediante Celery y procesamiento NLP.
- Reentrega duplicada sin reprocesamiento.
- Reconciliación y republicación de trabajos pendientes.
- Exclusión de ejecuciones concurrentes y fencing mediante token UUID.
- Cierre de los cuatro trabajos Outbox del ensayo.
- Cuatro capturas completadas, cuatro intentos finalizados y tres ItemIA.

Las pruebas funcionales no sustituyen ASR real, pruebas de carga,
caídas de procesos ni la validación de dispositivos finales.

### Recuperación y compatibilidad

Se verificó el respaldo PostgreSQL pre-0008 mediante SHA-256 y
se restauró en `homex-d07-rc2-restore-pg`.

- Recuperación correcta de siete migraciones de Capturas.
- Compatibilidad ORM real con el backend D04.
- Migración 0007 a 0008 en otro PostgreSQL independiente,
  `homex-d07-rc2-migration-pg`.
- Ocho migraciones tras la actualización, columna UUID correcta
  y ausencia de operaciones de migración pendientes.
- Conservación de registros comerciales anteriores a RC2.

Se respaldó también el estado RC2 actual y se restauró en
`homex-d07-rc2-current-restore-pg`.

- Recuperación de dos proformas, cuatro capturas,
  cuatro intentos, cuatro trabajos Outbox y tres ItemIA.
- Coincidencia de conteos y huellas de las cinco tablas comparadas.
- Coincidencia del historial completo de migraciones.
- Reconstrucción de `homex_migrator` y `homex_runtime`.
- Coincidencia de 246 registros de auditoría de privilegios
  efectivos, propietarios y permisos predeterminados auditados.
- Lectura ORM real desde Django RC2 mediante `homex_runtime`.
- Gunicorn RC2 conectado a la restauración:
  `/api/v1/health/` y `/api/v1/ready/` respondieron HTTP 200;
  PostgreSQL y almacenamiento multimedia reportaron `ok`.

Los PostgreSQL de restauración utilizaron volúmenes exclusivos,
red Docker `none` y ningún puerto publicado.

### Evidencia multimedia

El directorio multimedia del ensayo RC2 estaba vacío.
Se validó su archivado y recuperación y, por separado,
se respaldaron y restauraron dos archivos sintéticos,
comprobando SHA-256 y estructura de directorios.

No se ha demostrado todavía recuperación integrada de medios
persistentes asociados a registros comerciales bajo escrituras
concurrentes. La prueba HTTP utilizó almacenamiento temporal
escribible, no el volumen multimedia restaurado.

### Restricciones y pendientes de RC2

- Reconstruir y validar imagen frontend-proxy con metadatos OCI RC2.
- Publicar imágenes definitivas y fijar sus `RepoDigest`.
- Perfilar ASR real en el hardware objetivo.
- Ejecutar smoke integral de voz, NLP, HITL y medios persistentes.
- Validar acceso PC, móvil y tablet mediante Zero Trust.
- Ensayar recuperación y rollback operacional integral de servicios.
- Comprobar retención, alertas y recuperación ante fallos del
  almacenamiento externo R2 según la política autorizada.
- Obtener autorización explícita para la ventana productiva.

La candidata permanece `candidate`. No se autoriza merge,
tag final, promoción D07 ni inicio D08 con estas pruebas.
