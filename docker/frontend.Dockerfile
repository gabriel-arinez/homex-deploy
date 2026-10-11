# syntax=docker/dockerfile:1.7
FROM node:24.15.0-bookworm-slim@sha256:4e6b70dd6cbfc88c8157ba19aa3d9f9cce6ba4703576d55459e45efcbc9c5f5d AS build

ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
WORKDIR /src

COPY --from=frontend package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci --ignore-scripts

COPY --from=frontend index.html env.d.ts vite.config.ts ./
COPY --from=frontend tsconfig.json tsconfig.app.json tsconfig.node.json tsconfig.vitest.json ./
COPY --from=frontend vitest.config.ts ./
COPY --from=frontend public/ ./public/
COPY --from=frontend src/ ./src/
RUN test -n "$VITE_API_BASE_URL" \
    && npm run build \
    && find dist/assets -maxdepth 1 -type f \
        \( -name '*-????????.js' -o -name '*-????????.css' -o -name '*-????????.woff2' \) \
        | grep -q . \
    && test -z "$(find dist/assets -maxdepth 1 -type f ! -name '*-????????.*' -print -quit)" \
    && test -z "$(find dist -type f -name '*.map' -print -quit)"

FROM nginxinc/nginx-unprivileged:1.29.3-alpine3.22@sha256:5aea7cc516b419e3526f47dd1531be31a56a046cfe44754d94f9383e13e2ee99

ARG HOMEX_FRONTEND_REVISION
LABEL org.opencontainers.image.source="https://github.com/gabriel-arinez/homex-frontend" \
      org.opencontainers.image.revision="$HOMEX_FRONTEND_REVISION" \
      org.opencontainers.image.version="0.7.0-d07-rc1"

COPY nginx/default.conf /etc/nginx/conf.d/default.conf
COPY --from=build /src/dist/ /usr/share/nginx/html/

USER 101:101
EXPOSE 8080
