# MEMORY — App Unificador de Guias Unimed

> Memória viva do projeto. Fonte da verdade pra retomar o trabalho em qualquer sessão.
> Atualizar a cada mudança relevante de escopo, decisão ou arquitetura.

**Versão atual:** v1.0.1 · **Repo:** https://github.com/ossamuok/unificador-guias-unimed (público)
**Cliente:** Centro Clínico Okazaki (Recife) · **Plataforma alvo:** Windows (.exe) + Mac (dev)

---

## 1. O que o app faz

App web local (Flask, roda no navegador, 100% offline) que junta os PDFs escaneados
de uma guia Unimed (1.pdf … N.pdf) num **único PDF**, nomeado com o **Nº da Guia no
Prestador**. Organiza por `Guias Unimed/{ano}/{mês}/{paciente}/inputs|output`.

Privacidade: nenhum dado de paciente sai da máquina. EXEMPLOS e `Guias Unimed/` ficam
fora do git (`.gitignore`).

---

## 2. Regras de negócio (críticas)

- **Ordem do merge:** estrita por número no nome do arquivo (1→N). Tolera `01.pdf`, `1 - x.pdf`.
- **Nome do PDF final:** Nº da Guia no Prestador (campo 2 da SP/SADT), só dígitos.
- **Completude por tipo:** Endoscopia = **7** documentos · Colonoscopia = **6**.
  Operador marca o tipo (ou é auto-lido do doc 1). Só une quando completo.
- **Estrutura de pastas:** `Guias Unimed/{ano}/{mês MM}/{NOME PACIENTE}/inputs/` e `/output/`.
  `output/{guia}.pdf` é recriado a cada merge (limpa PDFs antigos).
- **Filtro:** por ano/mês (dropdowns) + busca por nome (client-side, ignora acento/caixa).
- **Erros (aba dedicada):** faltam docs (lista quais), sem tipo, excedente, falha OCR.

---

## 3. Extração por OCR (doc 1 = guia SP/SADT)

Os PDFs são **escaneados (imagem)** — sem camada de texto. OCR via **tesseract**.
Render via **PyMuPDF** (clip da faixa só quando precisa; página inteira p/ campos amplos).

Campos lidos do **documento 1** (`core.extract_guide_fields`):
| Campo | Origem no formulário | Âncora de extração |
|---|---|---|
| Nº da guia | Campo 2 "Nº GUIA NO PRESTADOR" | linha com "PRESTADOR" → maior dígito |
| Nome paciente | Campo 10 "Nome" (beneficiário) | nº carteira (16-18 díg) seguido de nome maiúsculo |
| Data do exame | Campo 36 "Data" (Execução) | data seguida de **hora** `dd/mm/aaaa HH:MM` (fallback: Data Autorização) |
| Ano/Mês | derivados da data do exame | — |
| Tipo | descrição do procedimento | contém "colono" → colono; "endoscop" → endoscopia |

- Código de barras do topo = `238510247_11975` (lote interno) — **NÃO** é o nº da guia.
- OCR é **assistivo**: pré-preenche o cadastro; operador confere campos em branco.
- Se o OCR do nº da guia falhar no merge → app pede o número manual (nunca gera nome errado).

---

## 4. Arquitetura / mapa de arquivos

```
app.py            Flask: endpoints (scan, tipo, merge, paciente CRUD, upload,
                  extrair, update/check|apply, pdf, abrir, config). frozen-aware.
core.py           Lógica pura testável: OCR/extração, listar inputs, status,
                  merge, registry de tipo, scan, delete_patient, extract_guide_fields.
updater.py        Auto-update do .exe via GitHub Releases (check/download/swap+relaunch).
version.py        VERSION + GITHUB_REPO.
templates/index.html  UI (tabela, filtros, modais, banner de update).
static/style.css      Design System Okazaki (teal/navy, DM Sans/Mono, botões pill).
static/app.js         Frontend SPA (fetch). Busca por nome, leitura auto do doc 1, update.
unificador.spec   PyInstaller (gera UnificadorGuias.exe; embute tesseract/ se existir).
build_windows.bat Build do .exe (rodar NO Windows).
installer.iss     Inno Setup (instalador opcional com atalhos).
.github/workflows/build-release.yml  CI: builda .exe no Windows + publica Release na tag v*.
requirements.txt  Flask, pypdf, PyMuPDF, Pillow, certifi.
iniciar.command / iniciar.bat  Launchers Mac/Windows (modo Python).
tasks/todo.md, tasks/lessons.md, COMO_ATUALIZAR.md, BUILD_WINDOWS.md, README.md
```

Dados (fora do git): `Guias Unimed/.unificador/registry.json` = tipo por paciente +
resultado da última união. `config.json` = pasta base (configurável na UI).

---

## 5. Decisões do usuário (confirmadas)

- Completude: **operador marca tipo** (com auto-detecção do doc 1 como apoio).
- Interface: **app web local Flask** + identidade Okazaki, Windows/Mac.
- Disparo do merge: **manual** (botão Escanear & Unir; lote ou individual).
- Upload **respeita o número do nome** (não a ordem de chegada do navegador).
- Auto-update: **só o .exe Windows**, via **GitHub público** (sem token).

---

## 6. Auto-update e publicação de versões

Fluxo (detalhe em `COMO_ATUALIZAR.md`):
1. Mexe no código. 2. Sobe `VERSION` em `version.py`. 3. `git push`.
4. `git tag vX.Y.Z && git push origin vX.Y.Z` → CI builda o .exe e publica o Release.
5. Clínica abre o app → banner "Atualização disponível" → baixa, troca, reabre sozinho.

- O .exe é **standalone** (CI embute o Tesseract via choco). ~101 MB.
- `updater.check_update()` compara versão (numérica); `apply_update()` baixa e agenda
  `_update.bat` (espera o processo sair, troca o .exe, relança).
- SSL via `certifi` (funciona no .exe e no Mac).
- Download direto (latest): `…/releases/latest/download/UnificadorGuias.exe`.

---

## 7. Lições / bugs corrigidos (ver tasks/lessons.md)

- **Ordem invertida no upload (CRÍTICO):** o upload numerava pela ordem de chegada do
  navegador → páginas trocadas. Fix: respeitar o número do nome do arquivo. Verificado
  por hash de imagem página-a-página vs PDF de referência.
- **Refazer com inputs incompletos:** `merge_patient` checava `st.status` (e "unificado"
  mascarava "incompleto"). Fix: checar os fatos (`tipo`/`faltando`/`excedentes`).
- **Erros transitórios não persistem** no registry (só falhas reais de OCR/merge).
- **Segurança:** `parse_key` bloqueia path traversal; `/api/pdf` e `/api/abrir` validam
  containment na base; `delete_patient` idem.
- **Op:** `pkill -f app.py` às vezes não derruba; usar `lsof -ti tcp:5000 | xargs kill -9`.

---

## 8. Comandos úteis

```bash
# rodar local (Mac)
python3 app.py                       # abre http://127.0.0.1:5000
lsof -ti tcp:5000 | xargs kill -9    # matar servidor preso

# publicar nova versão
# 1) editar version.py  2) git push  3):
git tag v1.0.2 && git push origin v1.0.2
gh run watch <id> --exit-status      # acompanhar build
gh release view v1.0.2               # conferir asset .exe
```

---

## 9. Próximos passos / ideias em aberto

- Instalador `.exe` (Inno Setup) também no pipeline do CI (hoje é manual).
- Ícone próprio do app (`static/icon.ico`) — o spec já usa se existir.
- Detecção de tipo poderia validar contra a contagem de arquivos (cross-check).
- Auto-update no Mac (hoje só .exe — decisão do usuário).
```
