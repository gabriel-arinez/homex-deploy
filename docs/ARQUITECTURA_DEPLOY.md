# Arquitectura de despliegue HOMEX

## Objetivo operativo

HOMEX se despliega inicialmente para un grupo pequeño de usuarios internos. La prioridad es
simplicidad, respuesta rápida, costo externo recurrente cero y una ruta de crecimiento sin
reescribir el dominio.

## Topología productiva

```text
PC / laptop / tablet / móvil
        |
  Cloudflare One Client
        |
 Zero Trust privado
        |
 Cloudflare Tunnel
        |
        v
      Nginx
   +----+-----+---------+
   |          |         |
  Vue       /api/     /media/
              |          |
           Django    media host
              |
        +-----+------+
        |            |
   PostgreSQL      Redis
                     |
                   Worker
                ASR + homex-nlp
```

El túnel es saliente desde el servidor. La primera instalación no requiere IP pública,
port-forwarding ni dominio público.

## Fuentes fijadas antes de D03

| Componente | Revisión/versión |
| --- | --- |
| backend | `0659dc553af15b2125fad9b4ac0579669916e77b` + F09.1 para storage |
| frontend | `57c32d3aa2c2e46fbcc7136f6a90995b67c664ea` |
| NLP | integración `55236655956c2f488af645aafa657db39af66b60` |
| NLP runtime | `0.1.0` |
| ASR | snapshot fijado por manifest |

D00–D02 permanecen como baseline de construcción, runtime y staging.

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

## Red

La red de datos Compose mantiene PostgreSQL/Redis aislados. Nginx es el único punto de entrada de la
aplicación. D04 añade Cloudflare Tunnel y políticas Zero Trust para los dispositivos autorizados.

No se compra un dominio sólo para habilitar el despliegue privado.

## Recuperación

La unidad mínima de backup es:

1. dump PostgreSQL;
2. directorio de media;
3. manifest/configuración no secreta de release.

Redis y audio no se restauran.

La prueba de D05 destruye y reconstruye tanto DB como media antes de aceptar el backup.

## Rendimiento

Para la carga esperada se priorizan:

- mismo origen Vue/API/media;
- variantes WebP 320/640/1280;
- Nginx sirviendo binarios sin pasar cada GET por Django;
- PostgreSQL local al backend;
- polling operativo ligero en lugar de infraestructura push prematura;
- SSD y espacio de disco monitorizado.

## Escalabilidad

Si HOMEX crece, el orden de evolución es aumentar recursos, ampliar usuarios privados, mover media a
S3/R2 si se justifica y separar servicios/DB sólo cuando métricas reales lo indiquen. Ninguno de
esos pasos cambia las reglas comerciales.
