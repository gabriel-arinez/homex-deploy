# D03 — Cloudflare R2 y media pública

**Fecha:** 30 de septiembre de 2026  
**Rama:** `feat/d03-r2-media`  
**Commit base:** `37e03f93d7093e53e0db30f7182f361944da30aa`  
**Estado:** implementación completa y CI remoto verde; pendiente únicamente aceptación operacional contra Cloudflare real, registro de esa evidencia y fusión a `main`.

## Alcance cerrado

D03 reemplaza el filesystem persistente del perfil productivo por el único bucket
`homex-public-media`. Django conserva la autoridad sobre las cargas y borrados; Vue nunca recibe
credenciales R2 ni sube directamente al bucket. PostgreSQL guarda sólo object keys bajo
`productos/` y `proformas/`, mientras el backend construye URLs públicas estables mediante el
dominio configurado en `HOMEX_MEDIA_PUBLIC_DOMAIN`.

El overlay `compose.production.yml` activa `config.settings.production`, exige las cinco variables
R2 en todos los procesos Django y elimina `/var/lib/homex/media` de API, worker y proxy. El volumen
`audio_temporal` permanece privado porque no es media persistente. La ausencia de cualquier
variable R2 hace fallar la resolución de Compose antes del arranque, y el backend vuelve a
validarlas al cargar settings.

## Infraestructura Cloudflare

`infra/r2/` contiene Terraform fijado a Terraform 1.16.4 y Cloudflare provider 5.24.0, con lock de
proveedor versionado. Declara:

- bucket R2 Standard `homex-public-media`, protegido con `prevent_destroy`;
- dominio propio público con TLS mínimo 1.2;
- regla CDN limitada al hostname y a `/productos/` o `/proformas/`;
- TTL edge de un año para respuestas 2xx y TTL de navegador de un día;
- ausencia de caché para 3xx/4xx/5xx y exclusión de query strings de la cache key.

No se habilita `r2.dev`, Cloudflare Images, URLs firmadas, segundo bucket ni MinIO productivo. El
acceso de escritura se realiza exclusivamente con un token R2 de backend. Las lecturas llegan por
el dominio propio. No se necesita CORS de escritura porque el navegador publica a Django.

Aplicación controlada:

```bash
cd infra/r2
cp terraform.tfvars.example terraform.tfvars
# Completar account_id, zone_id y media_domain; autenticar Terraform con un token Cloudflare externo.
terraform init
terraform plan -out=d03.tfplan
terraform apply d03.tfplan
terraform output
```

Después del apply debe comprobarse que el custom domain esté activo y que `r2.dev` siga
deshabilitado. Las credenciales runtime se crean con alcance Object Read & Write únicamente sobre
`homex-public-media`; el token administrativo de Terraform es distinto y no se inyecta a Django.

## Gates

`scripts/test_d03_contract.py` comprueba las fronteras entre Terraform, Compose, backend, OpenAPI y
frontend. `scripts/test_d03_required_env.sh` demuestra el fallo explícito al retirar cada variable.
`scripts/test_d03_r2.sh` crea PostgreSQL vacío y un endpoint S3 compatible descartable sólo para CI;
este emulador valida la semántica utilizada por `django-storages`, pero no forma parte del runtime.

El gate ejecuta los endpoints reales y verifica:

1. imagen PNG de producto normalizada y almacenada bajo `productos/`;
2. original WebP y variantes 320/640/1280 legibles sin autenticación;
3. adjunto de proforma y variantes bajo `proformas/`;
4. respuestas del API con URLs HTTPS del dominio público, sin firma, endpoint ni bucket;
5. PostgreSQL con keys relativas y nunca URLs completas;
6. borrado autorizado de original y variantes;
7. bucket vacío al terminar, sin objetos huérfanos;
8. ausencia de secretos R2 en frontend y OpenAPI;
9. perfil productivo sin volumen Docker de media.

Para la aceptación final contra Cloudflare se usa una base PostgreSQL descartable ya migrada y el
mismo test, sin emulador:

```bash
D03_REAL_R2_CONFIRM=YES-DISPOSABLE-DATABASE \
D03_COMPOSE_PROJECT=homex-d03-real \
sh scripts/test_d03_r2_real.sh
```

El marcador es deliberado: el gate crea filas comerciales de prueba aunque elimina todos los
objetos R2 creados. No debe apuntarse a la base productiva. Las keys contienen UUID y no se
reutilizan; el borrado quita los objetos de origen, aunque una copia ya almacenada en un edge puede
permanecer hasta expirar o purgarse administrativamente.

## Evidencia local

| Validación | Resultado |
| --- | --- |
| Terraform `fmt`, `init -backend=false`, `validate` | verde |
| contrato estático backend/frontend/OpenAPI/Compose | `d03-contract-tests-ok` |
| cinco variables obligatorias ausentes una por una | `d03-required-env-ok` |
| PostgreSQL vacío y migraciones backend | verde |
| imagen producto + WebP 320/640/1280 | verde |
| lectura pública sin autenticación | verde |
| adjunto de proforma | verde |
| borrado y ausencia de huérfanos | `d03-r2-no-orphans-ok` |
| gate integral | `d03-r2-gate-ok` |
| regresión D02 HTTP/API/multipart | `d02-http-api-smoke-ok` |

La cuenta disponible durante la implementación contenía marcadores, por lo que no se ejecutó `terraform apply` ni
el gate sobre Cloudflare real. Esto evita inventar dominio, account ID o secretos. El workflow CI
valida Terraform y el ciclo completo mediante el servicio descartable; la aceptación real queda
como paso operativo obligatorio del entorno que posea esas credenciales.

## Evidencia remota

El commit funcional `d39662bc574a5b56a531483b0c57cf1f2d1293b5` fue publicado en
`feat/d03-r2-media` y ejecutó GitHub Actions CI run `36729729834` con resultado **success**.
Los diez jobs terminaron verdes: `asr-contract`, `yaml`, `build`, `terraform-r2`,
`release-contract`, `compose-config`, `secrets`, `integration`, `r2-integration` y
`staging-integration`. Esto deja verificados remotamente el contrato D03, Terraform, el ciclo R2
reproducible, secretos y las regresiones D01/D02.

Esta evidencia no sustituye la aceptación contra Cloudflare real: el emulador S3 del CI no puede
demostrar que el bucket, custom domain, DNS/TLS y reglas CDN hayan quedado materializados en la
cuenta productiva.

## Rotación de credenciales

1. Crear un segundo token R2 con Object Read & Write limitado a `homex-public-media`.
2. Actualizar `R2_ACCESS_KEY_ID` y `R2_SECRET_ACCESS_KEY` en el gestor de secretos, nunca en Git.
3. Recrear API, worker y jobs Django con ambas variables como unidad atómica.
4. Ejecutar una carga, lectura pública y borrado con una base descartable mediante el gate real.
5. Revocar el token anterior sólo después del smoke verde.
6. Si falla, restaurar el par anterior todavía vigente y recrear los procesos.

`R2_ENDPOINT_URL`, bucket y dominio no cambian durante una rotación normal. Los valores secretos no
se imprimen ni se pasan como argumentos de URL. Gitleaks y el test contractual protegen el
repositorio; los logs de aplicación deben conservar únicamente object keys y errores saneados.

## CI

El workflow añade `terraform-r2` y `r2-integration`. El primero valida código y lock Terraform. El
segundo fija los mismos SHA backend/frontend de D02, construye el backend y ejecuta todo el ciclo de
media sobre PostgreSQL y el endpoint descartable. No utiliza secretos Cloudflare ni simula que el
emulador sea evidencia del dominio real. La evidencia remota del commit funcional quedó registrada
en la sección anterior.

## Pendiente para cierre definitivo

El repositorio ya no tiene trabajo técnico pendiente que pueda completarse sin acceso a la cuenta
Cloudflare real. Para declarar D03 cerrada falta únicamente:

1. completar `infra/r2/terraform.tfvars` con `cloudflare_account_id`, `cloudflare_zone_id` y
   `media_domain` reales;
2. autenticar Terraform con un token administrativo externo apropiado y ejecutar `terraform plan`
   seguido de `terraform apply`;
3. confirmar en Cloudflare que `homex-public-media` existe, el custom domain está activo, `r2.dev`
   permanece deshabilitado y la regla CDN está aplicada;
4. crear credenciales runtime R2 Object Read & Write restringidas exclusivamente al bucket;
5. cargar las cinco variables R2 reales en `.env` local/no versionado junto con una base PostgreSQL
   descartable correctamente migrada;
6. ejecutar `scripts/test_d03_r2_real.sh` y obtener `d03-r2-real-ok`;
7. registrar esa evidencia final y fusionar `feat/d03-r2-media` en `main`.

No se debe iniciar D04 antes de completar estos siete puntos.
