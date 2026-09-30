#!/usr/bin/env python3
"""Valida las fronteras estáticas de R2 y media productiva D03."""
from __future__ import annotations
import json, os, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def require(text, fragment, source):
    if fragment not in text: raise SystemExit(f'Falta {fragment!r} en {source}')

def reject(text, fragment, source):
    if fragment in text: raise SystemExit(f'Valor prohibido {fragment!r} en {source}')

def main():
    production=(ROOT/'compose.production.yml').read_text()
    terraform=(ROOT/'infra/r2/main.tf').read_text()
    backend=(Path(os.environ.get('BACKEND_CONTEXT',ROOT.parent/'homex-backend')))
    settings=(backend/'config/settings/production.py').read_text()
    openapi=(backend/'docs/openapi.yaml').read_text()
    frontend=Path(os.environ.get('FRONTEND_CONTEXT',ROOT.parent/'homex-frontend'))
    for name in ('R2_ACCESS_KEY_ID','R2_SECRET_ACCESS_KEY','R2_ENDPOINT_URL','R2_BUCKET_NAME','HOMEX_MEDIA_PUBLIC_DOMAIN'):
        require(production,f'${{{name}:?', 'compose.production.yml')
        require(settings,f'required("{name}")', 'backend production settings')
        reject(openapi,name,'backend OpenAPI')
    require(settings,'querystring_auth": False','backend production settings')
    require(settings,'file_overwrite": False','backend production settings')
    reject(settings,'default_acl','backend production settings')
    for fragment in ('"homex-public-media"','cloudflare_r2_bucket','cloudflare_r2_custom_domain','enabled     = true','cloudflare_ruleset','/productos/','/proformas/','min_tls     = "1.2"'):
        require(terraform,fragment,'infra/r2/main.tf')
    reject(terraform,'r2.dev','infra/r2/main.tf')
    for path in frontend.rglob('*'):
        if path.is_file() and path.suffix in {'.ts','.vue','.js','.yaml','.yml'}:
            content=path.read_text(errors='ignore')
            for name in ('R2_ACCESS_KEY_ID','R2_SECRET_ACCESS_KEY','R2_ENDPOINT_URL'):
                reject(content,name,str(path))
    env=os.environ.copy(); env.update({'R2_ACCESS_KEY_ID':'contract-access','R2_SECRET_ACCESS_KEY':'contract-secret','R2_ENDPOINT_URL':'https://contract.invalid','R2_BUCKET_NAME':'homex-public-media','HOMEX_MEDIA_PUBLIC_DOMAIN':'media.contract.invalid'})
    compose=os.environ.get('COMPOSE_BIN','docker compose').split()
    output=subprocess.check_output([*compose,'-f','docker-compose.yml','-f','compose.production.yml','--env-file','.env.example','config','--format','json'],cwd=ROOT,env=env,text=True)
    config=json.loads(output)
    for service in ('api','worker','frontend-proxy'):
        volumes=config['services'][service].get('volumes',[])
        if any(volume.get('target')=='/var/lib/homex/media' for volume in volumes):
            raise SystemExit(f'{service} conserva volumen productivo de media')
    frontend_env=config['services']['frontend-proxy'].get('environment',{})
    if any(name.startswith('R2_') for name in frontend_env):
        raise SystemExit('frontend-proxy recibió credenciales R2')
    print('d03-contract-tests-ok')
if __name__=='__main__': main()
