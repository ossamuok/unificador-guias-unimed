# TODO — App Unificador de PDF Unimed

## Objetivo
App web local (Flask, Mac/Windows, marca Okazaki) que:
- Junta múltiplos PDFs (1.pdf..N.pdf, em ordem numérica) num único PDF por paciente.
- Nomeia o PDF final com o **Nº da Guia no Prestador** extraído via OCR do `1.pdf` (guia SP/SADT).
- Estrutura de pastas: `Guias Unimed/{ano}/{mês}/{paciente}/inputs/` e `.../output/`.
- Só unifica quando o paciente está **completo** (Endoscopia=7, Colono=6 — tipo marcado pelo operador).
- Filtro por data (ano/mês). Unificação em **lote** ou **individual** (botão Escanear & Unir).
- Lista acessível de **erros** (faltam documentos, OCR falhou, etc.).

## Decisões (confirmadas com usuário)
- Completude: operador marca tipo por paciente (Endoscopia 7 / Colonoscopia 6).
- Interface: app web local Flask + identidade Okazaki.
- Disparo: manual (botão Escanear & Unir).

## Stack (tudo validado neste Mac)
- Python 3.14 · Flask
- pypdf → merge (append preserva streams, 7 págs == referência ✓)
- PyMuPDF (fitz) → render do topo do 1.pdf p/ OCR (pip, sem dep de sistema)
- tesseract → OCR do número da guia (binário, auto-detect de path; Mac+Windows)
- OCR validado: extraiu `18009206000040352547` == nome do arquivo de referência ✓

## Tarefas
- [x] Explorar EXEMPLOS, achar campo "Nº GUIA NO PRESTADOR" (top, após label)
- [x] Validar render+OCR+extração end-to-end (match exato)
- [x] Validar merge pypdf vs arquivo de referência (7 págs)
- [x] core.py: tesseract detect, extrair guia, listar inputs, status, merge, registry de tipo, scan
- [x] app.py: Flask endpoints (scan, tipo, merge, novo paciente, upload, abrir pasta, config base)
- [x] templates/index.html + static (CSS Okazaki + JS): filtro, tabela, lote/individual, erros
- [x] requirements.txt + launchers (iniciar.command / iniciar.bat) + README
- [x] Teste E2E via HTTP: criar→upload→merge = output/18009206000040352547.pdf (7 págs) ✓
- [x] Hardening segurança: parse_key bloqueia traversal; /api/pdf e /api/abrir validam containment
- [~] Code review adversarial multi-agente (em execução) → aplicar achados confirmados

## Evidências de teste (todas passaram)
- Criar paciente → incompleto; upload 1..7 → pronto; merge → guia 18009206000040352547, 7 págs
- Colono 6 → pronto; subir 7º → excedente
- OCR falha (PDF em branco) → erro "informe número manualmente"; override 7777 → une 6 págs
- Re-merge com override → substitui PDF antigo (output só com o novo nome)
- set tipo via API muda status; scan filtra por ano/mês; periodos lista anos/meses
- Segurança: /api/pdf path traversal → 403; key "../.." em merge/upload → rejeitado
- index/style.css/app.js → HTTP 200

## Regras de status por paciente
- `pronto`     → completo (1..N todos presentes), ainda não unificado
- `unificado`  → existe PDF em output/
- `incompleto` → faltam números (listar quais)
- `sem_tipo`   → tipo não definido
- `excedente`  → mais arquivos que o esperado p/ o tipo
- `erro`       → falha de OCR/merge na última tentativa
