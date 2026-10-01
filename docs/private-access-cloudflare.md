# Acceso privado HOMEX con Cloudflare Zero Trust/Tunnel

## Objetivo

Permitir que PC, laptop, tablet y móvil autorizados accedan a HOMEX sin comprar un dominio, sin IP
pública y sin abrir puertos entrantes en Internet.

La release D04 usa:

```text
https://homex.internal
```

Nginx escucha sólo en `127.0.0.1:443` del servidor. Cloudflare Tunnel conecta de salida y los
clientes autorizados llegan mediante Cloudflare One Client.

## 1. Preparar el servidor HOMEX

Crear la resolución local del hostname:

```bash
grep -qE '(^|[[:space:]])homex\.internal([[:space:]]|$)' /etc/hosts ||
  echo '127.0.0.1 homex.internal' | sudo tee -a /etc/hosts

getent hosts homex.internal
```

Preparar media persistente:

```bash
sudo install -d -o 10001 -g 10001 -m 0755 /srv/homex/media
```

Crear el entorno productivo local:

```bash
cp .env.production.example .env.production
```

Editar `.env.production` y sustituir únicamente los marcadores de secretos/rutas reales. El archivo
está excluido de Git.

## 2. Generar TLS interno HOMEX

```bash
set -a
. ./.env.production
set +a

HOMEX_PRIVATE_HOSTNAME=homex.internal \
sh scripts/generate_internal_tls.sh
```

Se crean en `/etc/homex/tls/`:

- `homex-root-ca.key`: clave privada de la CA; **nunca sale del servidor**;
- `homex-root-ca.crt`: certificado raíz que sí se instala en dispositivos autorizados;
- `homex.internal.key`: clave privada del servidor;
- `homex.internal.crt`: certificado HTTPS del servicio.

Verificación local:

```bash
openssl verify \
  -CAfile /etc/homex/tls/homex-root-ca.crt \
  /etc/homex/tls/homex.internal.crt
```

## 3. Levantar la release candidate

Con backend/frontend disponibles en las rutas declaradas por `.env.production`:

```bash
docker compose \
  -f docker-compose.yml \
  -f compose.production.yml \
  --env-file .env.production \
  --profile operations \
  build --no-cache backend frontend-proxy

docker compose \
  -f docker-compose.yml \
  -f compose.production.yml \
  --env-file .env.production \
  --profile operations \
  up -d postgres redis

docker compose \
  -f docker-compose.yml \
  -f compose.production.yml \
  --env-file .env.production \
  --profile operations \
  run --rm migrate

docker compose \
  -f docker-compose.yml \
  -f compose.production.yml \
  --env-file .env.production \
  --profile operations \
  run --rm grant-runtime

docker compose \
  -f docker-compose.yml \
  -f compose.production.yml \
  --env-file .env.production \
  --profile operations \
  up -d api worker beat frontend-proxy
```

Comprobar el origen directamente en el servidor:

```bash
curl --cacert /etc/homex/tls/homex-root-ca.crt \
  -fsS https://homex.internal/api/v1/health/
```

PostgreSQL, Redis y API no deben publicar puertos al host. Sólo Nginx debe escuchar en
`127.0.0.1:443`.

## 4. Habilitar Gateway para tráfico privado

En Cloudflare Zero Trust:

1. **Traffic policies > Traffic settings**;
2. abrir **Proxy and inspection**;
3. activar **Allow Secure Web Gateway to proxy traffic**;
4. activar **TCP**;
5. activar **UDP**;
6. ICMP es opcional y útil para diagnóstico.

El routing por hostname privado requiere que el tráfico del cliente pase por Gateway.

## 5. Crear Cloudflare Tunnel

En **Networking > Tunnels**:

1. crear un tunnel `cloudflared`, por ejemplo `homex`;
2. esperar a obtener el token del conector;
3. guardar sólo el token en el servidor, sin pegarlo en Git ni en scripts:

```bash
sudo install -d -m 0700 /etc/homex/cloudflared
sudo sh -c 'umask 077; cat > /etc/homex/cloudflared/tunnel-token'
```

Pegar el token, Enter y Ctrl-D.

Instalar el binario fijado por D04:

```bash
set -a
. ./.env.production
set +a

sh scripts/install_cloudflared.sh
```

El instalador verifica SHA256 e instala `cloudflared 2026.9.2` y la unidad systemd.

Validar:

```bash
sudo systemctl enable --now homex-cloudflared.service
sudo systemctl --no-pager --full status homex-cloudflared.service
```

## 6. Crear la ruta de hostname

En **Networking > Tunnels**:

1. abrir el tunnel `homex`;
2. ir a la pestaña **Routes**;
3. seleccionar **Add route**;
4. elegir **Private hostname**;
5. Hostname: `homex.internal`;
6. guardar la ruta.

No usar **Published application** y no asociar un dominio público.

## 7. Configurar el perfil de dispositivos

En **Zero Trust > Team & Resources > Devices > Device profiles > General profiles**, abrir el
perfil usado por HOMEX.

Para **Split Tunnels**, mantener los rangos iniciales resueltos por defecto. Las versiones actuales
del Cloudflare One Client administran automáticamente el rango IPv4
`172.64.128.0/20` y el bloque IPv6 de Cloudflare requerido por hostname routing; no hace falta
añadirlos manualmente en una configuración normal.

Si la cuenta usa un rango IPv4 inicial personalizado, ese rango sí debe enviarse por Cloudflare One
Client. Añadir manualmente los rangos por defecto sólo se usa como medida de diagnóstico.

En **Local Domain Fallback**, eliminar la entrada que capture el TLD `internal` si existe. La
consulta de `homex.internal` debe llegar a Cloudflare Gateway para que el hostname route funcione.

## 8. Crear la política de Access

En **Zero Trust > Access controls > Applications**:

1. **Create new application**;
2. **Self-hosted and private**;
3. **Add private hostname**;
4. Hostname: `homex.internal`;
5. Port: `443`;
6. crear una política **Allow** sólo para las identidades autorizadas de HOMEX;
7. habilitar **Authenticate with Cloudflare One Client** si corresponde al perfil elegido;
8. guardar.

Una aplicación HTTPS privada en 443 necesita SNI válido; el certificado D04 tiene SAN
`homex.internal`.

## 9. Preparar cada PC, tablet o móvil

En cada dispositivo autorizado:

1. instalar Cloudflare One Client;
2. enrolarlo en la organización Zero Trust;
3. copiar **sólo** `homex-root-ca.crt`;
4. instalarlo como autoridad raíz de confianza;
5. reconectar Cloudflare One Client para aplicar el perfil actualizado.

Nunca copiar:

- `homex-root-ca.key`;
- `homex.internal.key`;
- el token del tunnel.

En iOS/iPadOS, además de instalar el perfil de la CA, debe activarse la confianza completa para esa
raíz. En Android, la CA se instala como certificado CA del usuario para navegación interna.

## 10. Validación manual obligatoria de D04

En un escritorio autorizado y, como mínimo, en un móvil o tablet autorizado:

```text
https://homex.internal
```

Comprobar:

- no aparece advertencia de certificado;
- login funciona;
- clientes/productos/proformas cargan;
- imágenes/media cargan con normalidad;
- una captura real de micrófono puede grabarse, enviarse y completar ASR/NLP/HITL.

Comprobar aislamiento:

- PostgreSQL y Redis no tienen puertos publicados;
- API no tiene puerto publicado al host;
- sólo Nginx escucha en `127.0.0.1:443`;
- un dispositivo/identidad no autorizado queda bloqueado;
- al detener `homex-cloudflared.service`, el acceso remoto deja de funcionar;
- al volver a iniciarlo, el acceso se recupera.

## 11. Cierre

D04 sólo se cierra cuando existen:

- CI verde de la release candidate;
- tunnel real saludable;
- escritorio autorizado validado;
- móvil/tablet autorizado validado;
- micrófono real validado;
- prueba de denegación;
- prueba de caída/recuperación del tunnel.

No se versionan secretos, claves privadas, tokens ni certificados cliente.
