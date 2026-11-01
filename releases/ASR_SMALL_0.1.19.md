# Congelamiento ASR Small / NLP 0.1.19

Investigación de optimización ASR cerrada para esta versión. Los resultados experimentales históricos se conservan; no se declara precisión acústica certificada.

| Componente | Identidad definitiva |
| --- | --- |
| NLP `main` | `61e086a59330f394ab311264bd2fad566c74a26a` |
| Backend `main` | `f146ef92548a583616553fa5384ae9407530adfd` |
| Frontend `main` | `6d358ecba3e529e6e5ccc118f59c27a3cba2abb8` |
| Wheel NLP | `homex_nlp-0.1.19-py3-none-any.whl`, SHA-256 `9c299ff0072a68e3a352db491900d3031c6e512dde3918def896ae4ee1f73aee` |
| Procesamiento | `prf04-rules-money-2`, contrato `1.0`, `RULES_ONLY` |
| Modelo | `Systran/faster-whisper-small@536b0662742c02347bc0e980a01041f333bce120` |
| Pesos locales `model.bin` | SHA-256 / LFS OID `3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671` |
| Parámetros | CPU, `int8`, `transcribe(path, language="es")`, caché por worker |

La instancia local de demostración usa `scripts/run_asr_local.sh` con los checkouts `*-asr-main` y las credenciales existentes de `.env.manual-demo` en el checkout original. No se modifica el manifiesto D07 ni producción.
