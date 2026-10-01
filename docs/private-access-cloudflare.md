# Acceso privado HOMEX con Cloudflare Zero Trust/Tunnel

## Objetivo

Permitir que PC, laptop, tablet y móvil autorizados accedan a HOMEX sin comprar un dominio, sin IP
pública y sin abrir puertos entrantes en Internet.

La release D04 usa el hostname privado:

```text
homex.internal
```

y el origen local:

```text
https://homex.internal
```

El listener de Nginx permanece ligado a `127.0.0.1:443` en el servidor. `cloudflared` corre en
el host y es el único conector entre Cloudflare One y ese origen local.

## 1. Preparar el origen

En el servidor HOMEX:

```bash
echo '127.0.0.1 homex.internal' | sudo tee -a /etc/hosts
getent hosts homex.internal
curl --cacert /etc/homex/tls/homex-root-ca.crt -fsS https://homex.internal/api/v1/health/
```

El hostname debe resolver localmente a `127.0.0.1`.

### 1.1. Generar TLS interno HOMEX

Antes de levantar la release:

```bash
HOMEX_PRIVATE_HOSTNAME=homex.internal \
sh scripts/generate_internal_tls.sh
```

Se crean en `/etc/homex/tls/`:

- `homex-root-ca.key`: **privada del servidor; nunca copiarla a dispositivos**;
- `homex-root-ca.crt`: certificado raíz que sí se instala en dispositivos autorizados;
- `homex.internal.key`: clave privada del servidor;
- `homex.internal.crt`: certificado HTTPS del servicio.

La CA local evita comprar un dominio y permite que el navegador trate
`https://homex.internal` como contexto seguro una vez que el dispositivo confía en la CA.

## 2. Instalar cloudflared fijado

Desde la raíz de `homex-deploy`:

```bash
set -a
. ./.env.production.example
set +a

sh scripts/install_cloudflared.sh
```

El instalador:

- fija `cloudflared 2026.9.2`;
- verifica SHA256 antes de instalar;
- instala `/usr/local/bin/cloudflared`;
- instala `homex-cloudflared.service`;
- usa `--token-file`, no un token embebido en Git ni en la unidad systemd.

## 3. Crear el Tunnel en Cloudflare

En Cloudflare Zero Trust:

1. ir a **Networking > Tunnels**;
2. crear un tunnel remoto para HOMEX;
3. obtener el token del conector;
4. crear el archivo del token sin dejarlo en el historial:

```bash
sudo sh -c 'umask 077; cat > /etc/homex/cloudflared/tunnel-token'
```

Pegar el token, Enter y Ctrl-D.

Luego:

```bash
sudo systemctl enable --now homex-cloudflared.service
sudo systemctl status homex-cloudflared.service
```

## 4. Crear la ruta privada

En el tunnel:

1. abrir **Routes**;
2. **Add route**;
3. elegir **Private hostname**;
4. registrar `homex.internal`.

No crear una Published Application y no asociar un dominio público.

El servidor que ejecuta `cloudflared` debe poder resolver `homex.internal`; D04 lo resuelve a
`127.0.0.1` mediante `/etc/hosts`.

## 5. Confiar la CA HOMEX en los dispositivos

Copiar **sólo** `/etc/homex/tls/homex-root-ca.crt` a cada PC/tablet/móvil autorizado e
instalarlo como autoridad raíz de confianza.

Después de instalarlo, abrir `https://homex.internal` no debe mostrar advertencias de
certificado. Esta condición es obligatoria para usar grabación de voz en navegador.

No copiar nunca:

- `homex-root-ca.key`;
- `homex.internal.key`.

## 6. Enrolar dispositivos

Instalar Cloudflare One Client en cada dispositivo autorizado y enrolarlo en la organización Zero
Trust.

El perfil del dispositivo debe enviar a Cloudflare:

- las IP iniciales que Cloudflare usa para rutas de hostname privado;
- las consultas DNS de `homex.internal`.

Para la configuración por defecto de Cloudflare:

```text
IPv4  172.64.128.0/20
IPv6  2606:4700:0cf1:4000::/64
```

En modo Split Tunnels **Include**, incluir esos rangos. En **Local Domain Fallback**, eliminar la
entrada que capture `.internal` si existe, para que Gateway resuelva el hostname privado.

## 7. Política de acceso

Configurar reglas de enrolamiento y políticas Gateway/Zero Trust para que sólo usuarios y
dispositivos autorizados puedan utilizar la ruta.

D04 no considera suficiente que el tunnel esté "Healthy": debe probarse tanto un acceso permitido
como un intento desde un dispositivo/identidad no autorizada.

## 8. Validación manual obligatoria de D04

Desde escritorio autorizado:

```text
https://homex.internal
```

Verificar candado/certificado confiable, login, navegación, API, media y una captura real de micrófono.

Repetir desde al menos un móvil o tablet autorizado.

Luego comprobar:

- PostgreSQL y Redis no tienen puertos publicados;
- API no tiene puerto publicado al host;
- sólo Nginx escucha en `127.0.0.1:443`;
- el acceso remoto deja de funcionar si se detiene `homex-cloudflared.service`;
- un dispositivo no enrolado/no autorizado no puede alcanzar HOMEX.

## 9. HTTPS

D04 usa HTTPS real en el navegador mediante una CA privada HOMEX. El túnel de Cloudflare protege
el transporte remoto y Nginx presenta el certificado de `homex.internal`.

`HOMEX_HTTPS_ENABLED=1` es obligatorio en producción D04. Los clientes deben confiar en
`homex-root-ca.crt`; aceptar manualmente una advertencia de certificado no constituye evidencia
válida de cierre.

## Fuentes de operación

- Cloudflare One: private hostname routes;
- Cloudflare One Client: Split Tunnels y Local Domain Fallback;
- Cloudflare Tunnel: token-file para tunnels administrados remotamente.

La documentación oficial debe revisarse antes de una instalación real si la interfaz de Cloudflare
cambió desde D04.
