#!/bin/sh
set -eu

: "${HOMEX_DB_MIGRATOR_USER:?HOMEX_DB_MIGRATOR_USER is required}"
: "${HOMEX_DB_MIGRATOR_PASSWORD:?HOMEX_DB_MIGRATOR_PASSWORD is required}"
: "${HOMEX_DB_RUNTIME_USER:?HOMEX_DB_RUNTIME_USER is required}"
: "${HOMEX_DB_RUNTIME_PASSWORD:?HOMEX_DB_RUNTIME_PASSWORD is required}"

psql --set=ON_ERROR_STOP=1 \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  --set=migrator_user="$HOMEX_DB_MIGRATOR_USER" \
  --set=migrator_password="$HOMEX_DB_MIGRATOR_PASSWORD" \
  --set=runtime_user="$HOMEX_DB_RUNTIME_USER" \
  --set=runtime_password="$HOMEX_DB_RUNTIME_PASSWORD" <<'SQL'
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'migrator_user', :'migrator_password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'migrator_user') \gexec

SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'runtime_user', :'runtime_password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'runtime_user') \gexec

SELECT format('ALTER DATABASE %I OWNER TO %I', current_database(), :'migrator_user') \gexec
SELECT format('ALTER SCHEMA public OWNER TO %I', :'migrator_user') \gexec
SQL
