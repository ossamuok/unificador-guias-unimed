# Gerar o `.exe` para Windows

> **Importante:** um executável de Windows **só pode ser gerado em um PC Windows**
> (o PyInstaller não faz cross-compile a partir do Mac). Os arquivos abaixo já
> estão prontos — copie a pasta do projeto para um Windows e rode 1 script.

## Caminho rápido (1 arquivo .exe)

No PC Windows, dentro da pasta do projeto:

1. Instale o **Python 3.10+** de https://python.org → marque **“Add Python to PATH”**.
2. Dê **duplo clique** em **`build_windows.bat`**.
3. Aguarde. O executável sai em **`dist\UnificadorGuias.exe`**.
4. Dê duplo clique no `.exe` → abre o navegador em `http://127.0.0.1:5000`.

A pasta `Guias Unimed` (com os dados) é criada **ao lado do `.exe`**.

## OCR (ler o Nº da Guia) — escolha 1 opção

O app precisa do **Tesseract** para ler o número da guia. Duas formas:

**Opção A — instalar o Tesseract no PC (mais simples)**
- Baixe o instalador: https://github.com/UB-Mannheim/tesseract/wiki
- Instale (caminho padrão `C:\Program Files\Tesseract-OCR`). O app acha sozinho.

**Opção B — embutir o OCR no próprio `.exe` (standalone, nada a instalar)**
1. No PC Windows com Tesseract instalado, copie a pasta de instalação dele para
   dentro do projeto, renomeada para **`tesseract`**. Estrutura mínima:
   ```
   tesseract\
     tesseract.exe
     *.dll                (libleptonica, etc. — todas as DLLs da pasta)
     tessdata\eng.traineddata
   ```
2. Rode o `build_windows.bat`. A pasta `tesseract` é embutida no `.exe`
   automaticamente (o app a detecta primeiro).

## Instalador profissional (opcional)

Para um instalador com atalhos no Menu Iniciar / Área de Trabalho:

1. Rode o `build_windows.bat` (gera o `.exe`).
2. Instale o **Inno Setup**: https://jrsoftware.org/isdl.php
3. Abra **`installer.iss`** no Inno Setup → **Compile**.
4. Saída: **`Output\UnificadorGuias-Instalador.exe`** — esse é o instalador que
   você distribui.

## Observações

- 1º start pode demorar alguns segundos (descompacta na primeira execução).
- Se o Windows SmartScreen avisar (“app não reconhecido”), clique em
  **Mais informações → Executar assim mesmo** (é por o `.exe` não ser assinado).
- A porta usada é a **5000**. Se estiver ocupada, feche o outro app que a usa.
