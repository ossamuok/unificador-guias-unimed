# Como publicar uma atualização (auto-update do .exe)

O `.exe` instalado na clínica se atualiza sozinho. Para lançar uma melhoria:

1. **Faça as melhorias** no código.
2. **Suba a versão** em [`version.py`](version.py): `VERSION = "1.0.1"` (depois `1.0.2`, etc.).
3. **Commit + push:**
   ```bash
   git add -A && git commit -m "melhoria X" && git push
   ```
4. **Crie a tag da versão e envie** (isso dispara o build):
   ```bash
   git tag v1.0.1
   git push origin v1.0.1
   ```
5. O **GitHub Actions** builda o `.exe` no Windows e publica o **Release** sozinho
   (acompanhe em `gh run watch` ou na aba *Actions* do GitHub).
6. Na próxima vez que a clínica **abrir o app**, aparece o banner
   **“Atualização disponível”** → clicam em **Atualizar agora** → o app baixa a nova
   versão, troca e reabre sozinho.

## Regras
- A **tag** (`v1.0.1`) e o **VERSION** (`1.0.1`) devem bater.
- Versão é comparada numericamente: `1.0.10 > 1.0.9`. Sempre suba o número.
- O `.exe` é **standalone** (Tesseract embutido pelo CI) — a clínica não instala nada.
- Repositório: https://github.com/ossamuok/unificador-guias-unimed

## Onde fica o quê
- **Auto-update (cliente):** [`updater.py`](updater.py) — checa o release, baixa,
  agenda troca via `_update.bat`, relança.
- **Build/publish (CI):** [`.github/workflows/build-release.yml`](.github/workflows/build-release.yml)
- **Empacotamento:** [`unificador.spec`](unificador.spec)
