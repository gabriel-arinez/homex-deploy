# Plan maestro de implementación, despliegue y operación — HOMEX Deploy

**Fecha de revisión:** 30 de septiembre de 2026  
**Versión del plan:** 1.1 — despliegue privado proporcional + media local persistente  
**Repositorio:** gabriel-arinez/homex-deploy  
**Rama rectora:** main  
**Repositorio recién inicializado:** commit 343f6eb390f4794a49f1bad1a242c1af2817ef0b  
**Repositorios coordinados:** homex-backend, homex-frontend, homex-nlp y homex-deploy  
**Objetivo operativo:** convertir los tres componentes de HOMEX en una release reproducible, observable, recuperable y desplegable sin mover reglas de negocio a infraestructura.

---

# 0. Propósito

Este documento es el contrato de ejecución de homex-deploy.

El repositorio de despliegue no es un cuarto lugar para implementar lógica comercial. Su responsabilidad es ensamblar, versionar, desplegar, proteger, observar, respaldar y recuperar los componentes que ya son autoridad en sus repositorios de origen.

Cada fase de este plan define:

1. precondiciones inter-repositorio;
2. alcance permitido;
3. trabajo obligatorio;
4. trabajo prohibido;
5. pruebas y gates;
6. evidencia de cierre;
7. condición para iniciar la siguiente fase.

Una fase no se considera terminada porque Docker Compose arranque o porque una URL responda. Deben pasar todos los gates de la fase y la evidencia debe quedar versionada.

---

# 1. Estado coordinado al 30 de septiembre de 2026

## 1.1. homex-nlp

- F00–F06 cerradas;
- artefacto NLP 0.1.0 fijable y contrato externo estable;
- F09 de integración del sistema fusionada en `main` (`55236655956c2f488af645aafa657db39af66b60`);
- F10/F11 pendientes y dependientes principalmente de este repositorio.

## 1.2. homex-backend

- F07.0–F07.7 cerradas;
- F08.0–F08.4 cerradas;
- F09 de integración con frontend cerrada en `main` (`0659dc553af15b2125fad9b4ac0579669916e77b`);
- F09.1 redefine exclusivamente el proveedor productivo de media: filesystem inicial, S3 opcional;
- no cambia el esquema comercial ni el contrato de negocio.

## 1.3. homex-frontend

- FE00–FE08 cerradas;
- FE08 fusionada en `main` (`57c32d3aa2c2e46fbcc7136f6a90995b67c664ea`);
- FE09 release/despliegue/piloto permanece pendiente y se coordina con D04–D08.

## 1.4. homex-deploy

- D00 cerrada;
- D01 cerrada;
- D02 cerrada y fusionada en `main` (`37e03f93d7093e53e0db30f7182f361944da30aa`);
- la antigua rama `feat/d03-r2-media` **no fue fusionada** y queda supersedida por esta decisión;
- D03 cerrada: persistencia productiva local de media validada y con CI verde;
- el acceso productivo será privado mediante Cloudflare Zero Trust/Tunnel, sin exigir dominio público.

Conclusión: el trabajo anterior D00–D02 sigue siendo válido. El siguiente bloque coordinado es
backend F09.1 y D03 cerrados; D04 es la siguiente fase.

---

# 2. Jerarquía de autoridad

Cuando dos documentos parezcan contradecirse, usar este orden:

1. contratos y decisiones ya cerradas del backend para negocio, API, PostgreSQL, R2 y permisos;
2. contrato v1 y documentación de integración de homex-nlp para NLP/ASR;
3. OpenAPI versionado del backend para frontend/API;
4. plan maestro vigente de homex-backend;
5. plan maestro vigente de homex-frontend;
6. plan maestro vigente de homex-nlp;
7. este plan para infraestructura;
8. configuraciones históricas o experimentales.

Infraestructura nunca corrige una contradicción comercial inventando comportamiento.

Si una fase de deploy descubre que falta una capacidad en una aplicación, debe registrar el bloqueo en el repositorio propietario y esperar el cambio allí.

---

# 3. Fronteras de responsabilidad

## 3.1. homex-backend es dueño de

- autenticación y autorización;
- API y OpenAPI;
- reglas comerciales;
- migraciones Django;
- PostgreSQL como autoridad comercial;
- Celery/tasks y contrato de worker;
- outbox, publicación y reconciliación;
- archivos temporales privados de audio según su contrato;
- integración con homex-nlp;
- object keys y metadatos de media;
- endpoints de health/readiness que dependan del estado real de la aplicación.

## 3.2. homex-nlp es dueño de

- paquete homex-nlp;
- contrato v1;
- reglas/NER;
- ASR desacoplado;
- configuración y artefactos/versiones del modelo;
- lógica pura de comparación HITL.

No es dueño de PostgreSQL, Redis, HTTP, permisos ni persistencia comercial.

## 3.3. homex-frontend es dueño de

- aplicación Vue;
- build de producción;
- contrato OpenAPI consumido;
- navegación y UI;
- seguridad del código cliente;
- no incluir secretos en el bundle.

No debe duplicar Nginx, TLS, Compose o infraestructura productiva.

## 3.4. homex-deploy es dueño de

- Dockerfiles y ensamblaje de release cuando sean exclusivamente infraestructura;
- Docker Compose de desarrollo integrado/staging/producción;
- reverse proxy;
- TLS/HTTPS;
- headers de seguridad;
- configuración de red;
- secretos de despliegue;
- manifiesto de versiones;
- migración controlada de release;
- health orchestration;
- backup/restore;
- R2 productivo y dominio público de media;
- persistencia y volúmenes operativos;
- limpieza independiente de audio temporal;
- logging/monitorización;
- smoke tests;
- runbooks;
- rollback compatible;
- evidencia de recuperación.

Este repositorio no contiene modelos ORM, reglas de permisos, cálculos comerciales, lógica NLP ni componentes Vue de dominio.

---

# 4. Arquitectura objetivo

La instalación inicial se dimensiona para un equipo pequeño, de uso interno, con crecimiento
moderado sin rehacer reglas de negocio.

~~~text
PC / laptop / tablet / móvil autorizado
                 |
          Cloudflare One Client
                 |
          Zero Trust privado
                 |
       Cloudflare Tunnel
        (salida desde servidor)
                 |
                 v
              Nginx
        +--------+---------+
        |        |         |
        v        v         v
      Vue      /api/     /media/
               |          |
               v          v
             Django   filesystem persistente
               |
        +------+------+
        |             |
   PostgreSQL       Redis
                      |
                    Worker
                 ASR + homex-nlp
~~~

Reglas:

- PostgreSQL es la autoridad comercial;
- Redis es reconstruible y no es fuente de verdad;
- la media comercial vive inicialmente en filesystem persistente del host, no en la capa efímera
  del contenedor;
- PostgreSQL conserva keys/metadatos, nunca binarios;
- Nginx sirve `/media/` sólo a través del perímetro privado;
- el audio NLP es temporal, privado, separado y excluido de backups;
- API y worker usan la misma release backend;
- frontend es un build estático reproducible;
- el túnel se establece de salida; no se exige IP pública ni port-forwarding;
- no se exige dominio público para la primera instalación;
- S3/R2 queda como ruta de escalado opcional, no como dependencia de la release inicial.

### 4.1. Principio de escalabilidad

Escalar no significa rediseñar el sistema. El orden previsto es:

1. aumentar recursos del servidor si la carga lo exige;
2. admitir más dispositivos/usuarios dentro de la red privada;
3. mover media a S3/R2 si capacidad, disponibilidad o backup lo justifican;
4. mover PostgreSQL/worker a infraestructura dedicada sólo si las métricas lo requieren.

La API, las keys de media y los modelos comerciales no cambian entre los pasos 1–3.

---

# 5. Estrategia de releases

Toda release integrada debe declarar exactamente qué ejecuta.

Se creará:

~~~text
releases/
└── manifest.yaml
~~~

El manifiesto debe incluir como mínimo:

- versión/release HOMEX;
- SHA o tag exacto de homex-backend;
- SHA o tag exacto de homex-frontend;
- versión y artefacto exacto de homex-nlp;
- hash del wheel/artefacto NLP;
- versión del modelo ASR;
- hash o identificador del modelo ASR;
- imagen/tag/digest de API;
- imagen/tag/digest de worker;
- imagen/tag/digest de frontend/proxy;
- versión de PostgreSQL;
- versión de Redis;
- versión de esquema/migración esperada;
- fecha de creación de release.

Está prohibido definir producción con main, latest u otra referencia flotante como única identificación.

---

# 6. Variables, secretos y configuración

## 6.1. Regla principal

`.env.example` documenta nombres y semántica, nunca secretos reales. Producción inyecta secretos
desde el entorno operativo y no los versiona.

## 6.2. Familias mínimas

- Django;
- PostgreSQL;
- Redis/Celery;
- `HOMEX_MEDIA_STORAGE`;
- `HOMEX_MEDIA_ROOT` / `HOMEX_MEDIA_HOST_PATH` para filesystem;
- variables S3/R2 únicamente si se activa ese backend;
- CORS/CSRF/hosts;
- rutas/modelos ASR;
- directorio temporal NLP;
- reverse proxy;
- Cloudflare Tunnel/Zero Trust cuando D04 lo habilite;
- logging.

## 6.3. Prohibiciones

- secretos en Git o bundle Vue;
- credenciales de storage en navegador;
- token de Tunnel versionado;
- contraseña PostgreSQL real en compose;
- path físico del host expuesto por API;
- exigir variables S3/R2 cuando `HOMEX_MEDIA_STORAGE=filesystem`.

---

# 7. Persistencia y volúmenes

Persistencia productiva:

- PostgreSQL: volumen persistente y respaldado;
- media comercial: directorio del host definido por `HOMEX_MEDIA_HOST_PATH`, montado en API como
  lectura/escritura y en Nginx como sólo lectura;
- modelo ASR: artefacto fijado y montado read-only.

Persistencia no autoritativa:

- Redis;
- audio/temporales NLP;
- cachés de build;
- frontend estático dentro de la imagen.

La media debe sobrevivir a `docker compose down`, recreación de API/Nginx y actualización de
release. No se admite depender del writable layer de un contenedor.

S3/R2 es una alternativa futura y no participa en el backup de la instalación filesystem.

---

# 8. Migraciones y arranque

La release no permite que múltiples réplicas ejecuten migraciones sin coordinación.

Patrón objetivo:

1. validar variables y servicios;
2. backup previo cuando corresponda;
3. ejecutar un job/servicio one-shot de migración;
4. verificar que la migración terminó correctamente;
5. iniciar/actualizar API y worker;
6. ejecutar smoke;
7. promover la release;
8. conservar procedimiento de rollback/restore.

No usar migrate como efecto lateral no coordinado de cada arranque de API.

Si una migración no es compatible con rollback de aplicación, la documentación debe declararlo antes de desplegar.

---

# 9. Health, readiness y smoke

Checks mínimos:

- reverse proxy responde;
- Vue entrega index/assets y fallback SPA;
- `/api/` llega al backend;
- `/media/` sirve una variante real;
- API liveness/readiness;
- PostgreSQL healthy;
- Redis healthy;
- worker disponible;
- migraciones en versión esperada;
- flujo autenticado mínimo;
- directorio de media existe, es escribible por API y legible por Nginx;
- ausencia de secretos en respuestas.

Desde D04 se añade:

- un dispositivo autorizado alcanza HOMEX mediante Zero Trust;
- un dispositivo/no identidad no autorizada no obtiene acceso;
- la aplicación no necesita puerto público entrante en el servidor.

Los healthchecks no ejecutan operaciones comerciales irreversibles.

---

# 10. Backups y recuperación

## 10.1. PostgreSQL

Debe existir backup verificable, política de retención, restore a instancia limpia y smoke posterior.

## 10.2. Media persistente

El backup de la release inicial incluye el contenido de `HOMEX_MEDIA_HOST_PATH`.

Debe conservar:

- `productos/`;
- `proformas/`;
- estructura de keys;
- permisos suficientes para restaurar;
- checksum/manifiesto de los archivos respaldados.

Después del restore se valida coherencia entre referencias PostgreSQL y archivos. Deben detectarse
referencias huérfanas y archivos no referenciados.

## 10.3. Audio NLP

Nunca entra en backup, snapshots persistentes ni recuperación histórica.

## 10.4. Unidad de recuperación

Una copia productiva se considera válida sólo si permite reconstruir conjuntamente:

1. PostgreSQL;
2. media persistente;
3. manifiesto/configuración no secreta de release.

---

# 11. Reverse proxy y acceso privado

Nginx cubre:

- Vue;
- proxy `/api/`;
- serving `/media/`;
- fallback SPA;
- compresión;
- cache largo de assets con hash;
- política prudente de cache para media;
- límites de body compatibles con uploads;
- timeouts compatibles con audio.

Cloudflare Zero Trust/Tunnel cubre el acceso remoto privado de PC, tablet y móvil autorizados.
No se compra ni exige dominio para cumplir esta topología.

HTTPS/HSTS sólo se exigen si la topología final presenta al navegador un hostname HTTPS real. No se
simula HTTPS mediante headers sobre una ruta privada que no lo usa. La confidencialidad del enlace
remoto debe estar demostrada por la red privada/túnel.

---

# 12. Estrategia de ramas y protocolo de ejecución

Cada fase de deploy se implementa en una rama propia.

Patrón:

~~~text
main
  ├── feat/d00-baseline
  ├── feat/d01-core-runtime
  ├── feat/d02-staging-proxy
  ├── feat/d03-media-local
  ├── feat/d04-release-candidate
  ├── feat/d05-backup-restore
  ├── feat/d06-observabilidad
  ├── feat/d07-release
  └── feat/d08-piloto-cierre
~~~

Reglas:

- una fase parte de main después de fusionar la anterior, salvo paralelismo explícitamente autorizado por este plan;
- una PR corresponde a una fase;
- no mezclar cambios de aplicación que pertenecen a backend/frontend/NLP;
- no cerrar una fase con CI rojo;
- no ocultar fallos con sleeps arbitrarios;
- no usar latest;
- no fijar secretos de ejemplo reales;
- no eliminar healthchecks para hacer pasar Compose.

Cada fase crea:

~~~text
docs/implementacion/<FASE>.md
~~~

El informe incluye:

- commit base;
- precondiciones inter-repositorio verificadas;
- archivos modificados;
- imágenes/versiones;
- variables añadidas;
- pruebas;
- resultado de gates;
- evidencia CI;
- riesgos;
- bloqueos;
- comandos de operación;
- commit final.

---

# 13. CI mínimo de homex-deploy

D00 debe crear CI con jobs independientes.

Mínimo progresivo:

## 13.1. config

- docker compose config;
- validación de archivos YAML;
- comprobación de variables requeridas sin secretos;
- validación del manifiesto de release.

## 13.2. build

- construir imágenes sin cache obligatorio;
- no depender de archivos no versionados;
- comprobar que el frontend usa npm ci;
- comprobar que Python usa locks/artefactos fijados.

## 13.3. proxy

- nginx -t o equivalente real dentro de la imagen;
- fallback SPA;
- proxy /api;
- headers esperados.

## 13.4. integration

Con servicios efímeros:

- PostgreSQL;
- Redis;
- migraciones desde vacío;
- API;
- worker;
- smoke mínimo.

## 13.5. recovery

A partir de D05:

- backup;
- destrucción de la base de prueba;
- restore;
- smoke posterior.

CI nunca utiliza credenciales productivas.

---

# 14. Fases de ejecución

# D00 — Baseline de infraestructura y contrato de despliegue

**Objetivo:** convertir el repositorio inicial vacío en una base verificable sin desplegar todavía producción.

**Puede comenzar ahora.**

## Precondiciones obligatorias de otros repositorios

- homex-nlp: F06 cerrada y fusionada a main;
- homex-backend: F08.4 cerrada y fusionada a main;
- homex-frontend: FE02 cerrada y fusionada a main.

Estado al crear este plan: **las tres precondiciones están satisfechas**.

FE03 no es precondición de D00.

## Trabajo obligatorio

- auditar .env.example de los tres repositorios;
- inventariar comandos reales de API, worker, publicador/reconciliador y limpieza;
- inventariar health/readiness existentes;
- inventariar puertos reales;
- inventariar dependencias externas;
- definir estructura definitiva del repositorio;
- crear compose base válido;
- crear CI inicial;
- crear esquema de releases/manifest.yaml;
- completar docs/ARQUITECTURA_DEPLOY.md;
- documentar qué componentes faltantes requieren cambios en su repo propietario;
- retirar del .env.example de deploy variables inventadas que no correspondan al contrato real.

## Prohibido

- crear endpoints ficticios de health;
- inventar comandos Celery;
- copiar lógica Python;
- introducir R2 con credenciales reales;
- crear todavía producción definitiva.

## Gates

- docker compose config;
- YAML válido;
- CI verde;
- ninguna variable contractual duplicada con otro nombre;
- arquitectura y comandos trazables a repositorios fuente.

## Cierre

docs/implementacion/D00_BASELINE.md.

---

# D01 — Runtime integrado de backend + NLP

**Objetivo:** ejecutar localmente de forma reproducible la parte server-side real de HOMEX.

## Precondiciones obligatorias

- D00 cerrada;
- homex-backend F08.4 cerrada;
- homex-nlp F06 cerrada.

Frontend no es precondición.

## Trabajo obligatorio

Construir/orquestar:

- PostgreSQL versionado;
- Redis versionado;
- imagen backend común para API y worker;
- API Django;
- worker Celery;
- publicador/reconciliador según comandos reales del backend;
- servicio/job independiente de limpieza de audio;
- modelo/artefacto ASR fijado por versión/hash;
- wheel/artefacto homex-nlp exacto;
- volumen temporal NLP privado y no respaldado;
- job de migración one-shot;
- healthchecks internos;
- redes separadas cuando aporten aislamiento real.

## Tests obligatorios

- base vacía → migrate;
- segunda migración → no-op;
- API inicia;
- Redis inicia;
- worker responde;
- pipeline F08 feliz con worker real;
- caída/reinicio de Redis no convierte Redis en fuente de verdad;
- temporales de audio no quedan expuestos públicamente;
- cleanup puede ejecutarse aunque el worker NLP esté detenido;
- reinicio de contenedores no pierde PostgreSQL.

## Cierre

docs/implementacion/D01_CORE_RUNTIME.md.

---

# D02 — Staging integrado y reverse proxy

**Objetivo:** disponer de un entorno integrado estable que frontend pueda utilizar durante FE03–FE08.

## Precondiciones obligatorias

- D01 cerrada;
- homex-frontend FE02 cerrada;
- contrato auth/OpenAPI consumido por FE02 vigente.

FE03 puede estar todavía en desarrollo.

## Trabajo obligatorio

- build reproducible del frontend;
- imagen/etapa estática de frontend;
- reverse proxy;
- proxy /api;
- fallback SPA;
- API base correcta;
- cache de assets con hash;
- index sin cache inadecuado;
- compresión;
- límites de upload compatibles;
- headers base;
- entorno staging reproducible;
- smoke navegador/API.

## Regla de coordinación

Durante FE03–FE08 este entorno puede actualizar el SHA de frontend/backend para integración, pero una release candidata no puede usar referencias flotantes.

## Tests obligatorios

- refresh directo de una ruta Vue no produce 404;
- assets se sirven correctamente;
- /api llega al backend;
- 401/403 se conservan y no son transformados por Nginx;
- uploads permitidos atraviesan el proxy;
- frontend no contiene secretos;
- no hay CORS/CSRF relajado universalmente para “hacer funcionar” staging.

## Cierre

docs/implementacion/D02_STAGING_PROXY.md.

---

# D03 — Media persistente local de producción — CERRADA

**Objetivo:** convertir la media local de staging en persistencia productiva durable, respaldable y
servida por el mismo origen, sin depender de servicios cloud de objetos.

## Precondiciones obligatorias

- D02 cerrada;
- homex-backend F09.1 cerrado o commit candidato fijado;
- FE08 cerrada.

## Trabajo obligatorio

- definir `HOMEX_MEDIA_HOST_PATH`;
- montar el directorio en API como RW y Nginx como RO;
- mantener `/var/lib/homex/media` como target interno contractual;
- servir `/media/` desde Nginx;
- conservar `productos/` y `proformas/`;
- aplicar permisos correctos al UID/GID runtime;
- comprobar que recrear contenedores no elimina media;
- retirar del perfil productivo la obligación de variables R2;
- mantener configuración S3 opcional sin activarla;
- documentar capacidad, espacio libre y procedimiento de migración futura.

## Tests obligatorios

- carga de imagen de producto;
- variantes WebP accesibles;
- adjunto de proforma accesible;
- borrado autorizado elimina archivos esperados;
- prefijos correctos;
- PostgreSQL conserva key/ruta, no path físico absoluto;
- recreación de API/Nginx conserva los archivos;
- media no depende del writable layer del contenedor;
- audio sigue fuera de este storage.

## Cierre

`docs/implementacion/D03_MEDIA_LOCAL.md`.

---

# D04 — Release candidate integrada y acceso privado

**Objetivo:** congelar una combinación backend/frontend/NLP y hacerla accesible únicamente a
usuarios/dispositivos autorizados mediante Cloudflare Zero Trust/Tunnel.

## Precondiciones obligatorias

- D00–D03 cerradas;
- homex-backend F09.1 cerrado;
- homex-frontend FE08 cerrada;
- homex-nlp F09 cerrada.

## Trabajo obligatorio

- fijar SHAs/tags backend/frontend y artefacto/hash NLP/ASR;
- generar `manifest.yaml`;
- build limpio de imágenes;
- Compose productivo;
- crear/configurar Cloudflare Tunnel;
- publicar una ruta privada hacia el servicio HOMEX;
- configurar enrolamiento/política Zero Trust para usuarios autorizados;
- validar acceso desde escritorio y al menos un dispositivo móvil/tablet representativo;
- mantener PostgreSQL y Redis sin exposición pública;
- validar hosts/CORS/CSRF según origen real;
- source maps según política;
- límites iniciales de CPU/RAM;
- smoke E2E crítico.

No se requiere dominio público. El conector debe funcionar mediante conexión saliente.

## E2E mínimo

login → clientes → catálogo/media → proforma → aprobación → pedido/VENTA/OT → recibo →
LISTO_ENTREGA → nota → captura NLP → worker → HITL.

## Cierre

`docs/implementacion/D04_RELEASE_CANDIDATE.md`.

---

# D05 — Backup, restore, migración y rollback

**Objetivo:** demostrar recuperación real antes de producción.

## Precondiciones

- D04 cerrada;
- backend F09.1 cerrado;
- FE08 cerrada.

## Trabajo obligatorio

Crear/terminar `scripts/backup.sh`, `restore.sh`, `deploy.sh`, `smoke.sh`, procedimiento de
migración y rollback.

El backup debe incluir PostgreSQL + media persistente + manifiesto de release, y excluir audio.

## Ensayo obligatorio

1. desplegar release candidata;
2. cargar datos e imágenes representativos;
3. respaldar PostgreSQL y media;
4. destruir/recrear la base y directorio de prueba;
5. restaurar ambos;
6. ejecutar migraciones;
7. levantar API/worker/proxy;
8. ejecutar smoke;
9. verificar DB ↔ media;
10. verificar ausencia de audio en backup.

**No se cierra D05 con un backup nunca restaurado.**

## Cierre

`docs/implementacion/D05_RECOVERY.md`.

---

# D06 — Observabilidad, seguridad operacional y resiliencia

**Objetivo:** comprobar fallos controlados en la topología real.

## Trabajo obligatorio

- logs operacionales sin datos sensibles;
- correlación proxy/API/worker;
- métricas básicas;
- monitor de espacio en PostgreSQL, media y temporales;
- health/readiness;
- rotación de logs;
- límites CPU/RAM;
- runbook.

## Fallos a ensayar

- PostgreSQL no disponible;
- Redis no disponible;
- worker/API/proxy reiniciado;
- directorio de media ausente o read-only;
- disco de media/temporales lleno;
- cleanup fallido;
- Tunnel detenido;
- dispositivo no autorizado;
- configuración incompleta;
- dos procesamientos concurrentes.

## Cierre

`docs/implementacion/D06_OBSERVABILIDAD_RESILIENCIA.md`.

---

# D07 — Release productiva y cierre de F10

**Precondiciones:** D00–D06 cerradas, CI verde y restore ensayado.

## Trabajo obligatorio

- tag/version;
- manifiesto inmutable;
- builds finales;
- migración controlada;
- despliegue en PC/servidor objetivo;
- smoke;
- validación de acceso privado;
- validación de media local persistente;
- validación worker real;
- validación de backup;
- documentación installation/operations/recovery;
- checklist rollback;
- evidencia de versiones.

D07 aporta evidencia para backend F10, NLP F10 y FE09 Release.

## Cierre

`docs/implementacion/D07_RELEASE.md`.

---

# D08 — Piloto, operación y cierre integrado

**Objetivo:** operar la versión con usuarios reales y cerrar el sistema.

## Precondiciones

- D07 cerrada;
- backend/NLP F10 enlazados;
- FE09 release desplegada.

## Trabajo obligatorio

- fijar versión de piloto;
- validar PC, tablet y móvil autorizados;
- monitorear salud, errores y tiempos percibidos;
- ejecutar backups;
- probar runbook;
- documentar incidencias/cambios;
- clasificar feedback;
- no conservar audio;
- preparar handoff operacional.

D08 alimenta backend F11, NLP F11 y cierre final FE09.

## Cierre

`docs/implementacion/D08_PILOTO_CIERRE.md`.

---

# 15. Matriz de dependencias inter-repositorio

| Deploy | Backend | Frontend | NLP | Estado 30-09-2026 |
|---|---|---|---|---|
| D00 | F08.4 | FE02 | F06 | CERRADA |
| D01 | F08.4 | — | F06 | CERRADA |
| D02 | F08.4/F09 | FE08 compatible | F06/F09 | CERRADA |
| D03 | **F09.1** | FE08 | F09 | CERRADA |
| D04 | F09.1 | FE08 | F09 | SIGUIENTE |
| D05 | F09.1 | FE08 | F09 | tras D04 |
| D06 | F09.1 | FE08 | F09 | tras D05 |
| D07 | F09.1 | FE08/FE09 release | F09 | tras D06 |
| D08 | F10 | FE09 | F10 | tras D07 |

---

# 16. Secuencia recomendada desde el estado actual

~~~text
Backend F09 ---------------------------- CERRADA
Frontend FE08 -------------------------- CERRADA
NLP F09 ------------------------------- CERRADA
Deploy D00–D03 ------------------------ CERRADAS
Backend F09.1 ------------------------- CERRADA
D03 media local persistente ------------ CERRADA
        |
        v
D04 release candidate + Zero Trust/Tunnel
        |
        v
D05 backup + restore + rollback
        |
        v
D06 observabilidad + resiliencia
        |
        v
D07 release productiva
        |
        +--> Backend F10
        +--> NLP F10
        +--> FE09 Release
        |
        v
D08 piloto/cierre
        |
        +--> Backend F11
        +--> NLP F11
        +--> FE09 final
~~~

---

# 17. Estructura objetivo del repositorio

La estructura puede evolucionar durante D00, pero la intención contractual es:

~~~text
homex-deploy/
├── compose.yaml
├── compose.production.yaml
├── .env.example
├── README.md
├── docker/
│   ├── backend/
│   └── frontend/
├── nginx/
│   ├── nginx.conf
│   └── homex.conf
├── redis/
│   └── redis.conf
├── releases/
│   └── manifest.yaml
├── scripts/
│   ├── deploy.sh
│   ├── backup.sh
│   ├── restore.sh
│   ├── smoke.sh
│   └── cleanup-audio.sh
├── monitoring/
│   └── README.md
└── docs/
    ├── PLAN_MAESTRO.md
    ├── ARQUITECTURA_DEPLOY.md
    ├── installation.md
    ├── operations.md
    ├── recovery.md
    └── implementacion/
        ├── D00_BASELINE.md
        ├── D01_CORE_RUNTIME.md
        ├── D02_STAGING_PROXY.md
        ├── D03_MEDIA_LOCAL.md
        ├── D04_RELEASE_CANDIDATE.md
        ├── D05_RECOVERY.md
        ├── D06_OBSERVABILIDAD_RESILIENCIA.md
        ├── D07_RELEASE.md
        └── D08_PILOTO_CIERRE.md
~~~

El nombre compose.yaml reemplazará docker-compose.yml durante D00 únicamente si se hace como migración explícita y documentada; no mantener dos archivos equivalentes sin una razón.

---

# 18. Prohibiciones de diseño

No introducir:

- lógica comercial en Bash;
- SQL que compita con migraciones Django;
- SQLite como sustituto de PostgreSQL;
- Redis como fuente de verdad;
- audio histórico o en backups;
- media en writable layer efímero del contenedor;
- binarios de media en PostgreSQL;
- rutas físicas del host persistidas en DB/API;
- dominio público como requisito artificial;
- exposición pública de PostgreSQL/Redis/API;
- subida Vue directa a filesystem/S3;
- secretos o tokens Tunnel en Git;
- latest o ramas flotantes en release;
- migración automática desde todas las réplicas;
- permisos relajados para simplificar Compose;
- mocks como única evidencia de D04–D08.

S3/R2 no está prohibido: es una opción futura que sólo se activa si existe una necesidad operativa
medida.

---

# 19. Definición de terminado de una fase deploy

Una fase está terminada únicamente cuando:

- [ ] precondiciones inter-repositorio verificadas;
- [ ] alcance coincide con el plan;
- [ ] no mueve lógica a infraestructura;
- [ ] configuración validada;
- [ ] imágenes reproducibles cuando aplica;
- [ ] versiones no flotantes cuando aplica;
- [ ] healthchecks verdes;
- [ ] smoke verde;
- [ ] integración real verde cuando aplica;
- [ ] secretos ausentes de Git/logs/bundle;
- [ ] CI remoto verde;
- [ ] documentación de fase creada;
- [ ] riesgos/bloqueos documentados;
- [ ] no existen skips críticos;
- [ ] commit/PR contiene sólo la fase.

---

# 20. Definición de listo para producción

- [ ] D00–D07 cerradas;
- [ ] backend F09.1 cerrado;
- [ ] frontend FE08 cerrada y FE09 release coordinada;
- [ ] NLP F09 fijada por artefacto/version;
- [ ] PostgreSQL restaurado desde backup de ensayo;
- [ ] media restaurada y coherente con PostgreSQL;
- [ ] migraciones controladas;
- [ ] API/worker/NLP/modelo ASR fijados;
- [ ] Redis sin estado irrecuperable;
- [ ] audio excluido de backup;
- [ ] filesystem de media persistente fuera de contenedores;
- [ ] `productos/` y `proformas/` operativos;
- [ ] acceso mediante Zero Trust/Tunnel validado desde dispositivos autorizados;
- [ ] no existen puertos de datos expuestos públicamente;
- [ ] headers/CSP coherentes con el endpoint real;
- [ ] secretos externos;
- [ ] health/readiness y logs/metrics;
- [ ] smoke E2E crítico;
- [ ] manifiesto archivado;
- [ ] rollback/restore ensayado.

**Principio final:** homex-deploy no adelanta el negocio. Su trabajo comienza temprano para dar a frontend/backend un entorno real de integración, pero una release sólo se promueve cuando las fases de aplicación que consume están formalmente cerradas y sus versiones quedan inmovilizadas en un manifiesto reproducible.
