# Persistencia y privacidad de galerías

Actualizar este repositorio junto con las ramas de galerías de `homex-backend` y `homex-frontend`. Las referencias de muebles se guardan en el área `media/.private` del volumen persistente existente. El migrador y el worker necesitan el mismo volumen para migrar fotografías históricas y limpiar borradores abandonados. El backup de media ya incluye este subdirectorio.

Nginx rechaza tanto `/media/.private/` como `/media/proformas/`. Las referencias antiguas y nuevas se consultan mediante la API autenticada; las imágenes públicas de catálogo continúan bajo `/media/productos/`.

Antes de actualizar backend/frontend, publicar esta configuración del proxy. Luego ejecutar las migraciones usando el volumen existente y el rol migrador; aplicar los permisos runtime habituales. Finalmente, actualizar el frontend y los workers. No borrar los volúmenes. Las migraciones conservan IDs y referencias de catálogo, y trasladan los archivos privados históricos antes de retirar sus claves públicas.

```bash
cd /home/gabriel/HOMEX/homex-deploy
python3 scripts/validate_env_contract.py
python3 scripts/test_ap2_env_contract.py
python3 scripts/test_d02_contract.py
python3 scripts/test_d03_contract.py
python3 scripts/test_d04_contract.py
python3 scripts/test_d05_contract.py
python3 scripts/test_d06_contract.py
python3 scripts/test_d07_contract.py
docker compose --env-file .env.production.example -f docker-compose.yml -f compose.production.yml --profile operations config --quiet
```

Filesystem sigue siendo el valor predeterminado. `HOMEX_GALLERY_MAX_IMAGES=8` permite configurar la cantidad. Celery Beat programa la eliminación diaria de galerías no vinculadas con 30 días de inactividad.

Para instalaciones S3/R2 se proporciona `compose.s3-media.yml`, aplicado después del overlay productivo. Configurar las variables R2 en un archivo de entorno adicional y usar un bucket **privado**, distinto de `homex-public-media`, sin acceso público. `R2_PRIVATE_BUCKET_NAME` es obligatorio sólo en este modo. No se configura un dominio público para este bucket. Las credenciales R2 no se inyectan en instalaciones filesystem.
