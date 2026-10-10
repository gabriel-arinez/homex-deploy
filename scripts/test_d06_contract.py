#!/usr/bin/env python3
"""Contrato estático D06: observabilidad segura y resiliencia operativa."""
from __future__ import annotations
import json, os, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def need(text,fragment,source):
    if fragment not in text: raise SystemExit(f'Falta {fragment!r} en {source}')

def forbid(text,fragment,source):
    if fragment in text: raise SystemExit(f'Prohibido {fragment!r} en {source}')

def main():
    overlay=(ROOT/'compose.production.yml').read_text(); nginx=(ROOT/'nginx/production.conf').read_text(); env=(ROOT/'.env.production.example').read_text(); runbook=(ROOT/'docs/OPERATIONS_RUNBOOK.md').read_text(); workflow=(ROOT/'.github/workflows/ci.yml').read_text()
    for fragment in ('max-size: ${HOMEX_LOG_MAX_SIZE:-10m}','max-file: ${HOMEX_LOG_MAX_FILES:-5}','pids_limit:','  monitor:','HOMEX_STORAGE_WARN_PERCENT','collect_runtime_metrics.py','HOMEX_AUDIO_TEMP_ROOT: /var/lib/homex/audio-temporal','--access-logformat=','request_id'):
        need(overlay,fragment,'compose.production.yml')
    for fragment in ('log_format homex_json escape=json','"request_id":"$request_id"','proxy_set_header X-Request-ID $request_id','add_header X-Request-ID $request_id','access_log /dev/stdout homex_json','error_log /dev/stderr warn'):
        need(nginx,fragment,'nginx/production.conf')
    for fragment in ('HOMEX_LOG_MAX_SIZE=10m','HOMEX_LOG_MAX_FILES=5','HOMEX_STORAGE_WARN_PERCENT=80','HOMEX_STORAGE_CRITICAL_PERCENT=90','HOMEX_MONITOR_MEMORY=128m'):
        need(env,fragment,'.env.production.example')
    for fragment in ('PostgreSQL','Redis','API','worker','Nginx','Tunnel','disco','cleanup','dispositivo no autorizado','correlación'):
        need(runbook.lower(),fragment.lower(),'docs/OPERATIONS_RUNBOOK.md')
    for forbidden in ('Authorization','request_body','$http_authorization','$request_body'):
        forbid(nginx,forbidden,'nginx/production.conf')
    need(workflow,'resilience-observability:','.github/workflows/ci.yml')
    deploy=(ROOT/'scripts/deploy.sh').read_text()
    resilience=(ROOT/'scripts/test_d06_resilience.sh').read_text()
    metrics=(ROOT/'scripts/collect_runtime_metrics.py').read_text()
    for fragment in ('--profile operations --profile observability', 'up -d api worker beat frontend-proxy monitor', 'monitor_status', 'Monitor no disponible'):
        need(deploy,fragment,'scripts/deploy.sh')
    for fragment in ('[ "$root" != "/tmp/$project" ]', '[ -e "$root" ]', '[ -L "$root" ]', '.d06-owner'):
        need(resilience,fragment,'scripts/test_d06_resilience.sh')
    need(metrics,'homex_monitor_collection_healthy','scripts/collect_runtime_metrics.py')
    compose=os.environ.get('COMPOSE_BIN','docker compose').split(); output=subprocess.check_output([*compose,'-f','docker-compose.yml','-f','compose.production.yml','--env-file','.env.production.example','--profile','operations','--profile','observability','config','--format','json'],cwd=ROOT,text=True)
    cfg=json.loads(output)
    for name in ('postgres','redis','api','worker','beat','frontend-proxy','monitor'):
        service=cfg['services'][name]
        assert service.get('logging',{}).get('driver') == 'json-file', name
        assert service['logging']['options']['max-size'] and service['logging']['options']['max-file'], name
        assert service.get('pids_limit'), name
        assert service.get('mem_limit') or service.get('deploy',{}).get('resources',{}).get('limits',{}).get('memory'), name
        assert service.get('cpus') or service.get('deploy',{}).get('resources',{}).get('limits',{}).get('cpus'), name
    for name in ('postgres','redis','api'):
        assert not cfg['services'][name].get('ports'), name
    assert cfg['services']['monitor']['profiles'] == ['observability']
    print('d06-observability-contract-ok')
if __name__=='__main__': main()
