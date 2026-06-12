# Unificador de Guias Unimed · Centro Clínico Okazaki

App web local que junta os PDFs de uma guia (escaneados como `1.pdf`, `2.pdf`, …)
num único PDF, nomeado automaticamente com o **Nº da Guia no Prestador** lido da
guia SP/SADT. Roda 100% no seu computador — nenhum dado sai da máquina.

## O que ele faz
- Junta os PDFs **na ordem numérica** (1 → 2 → 3 …).
- Lê o **Nº da Guia no Prestador** do `1.pdf` (OCR) e usa como nome do arquivo final.
- Organiza tudo em `Guias Unimed/{ano}/{mês}/{paciente}/inputs` e salva o resultado
  em `.../output/{nº da guia}.pdf`.
- Só unifica quando o paciente está **completo**: Endoscopia = 7 folhas, Colonoscopia = 6.
- **Filtro por data** (ano/mês), unificação em **lote** ou **individual**.
- **Lista de erros/pendências**: documentos faltando, tipo não definido, falha de OCR, etc.

## Requisitos
- **Python 3.10+**
- **Tesseract OCR** (lê o número da guia):
  - macOS: `brew install tesseract`
  - Windows: instalador em https://github.com/UB-Mannheim/tesseract/wiki
- As demais dependências (Flask, pypdf, PyMuPDF, Pillow) são instaladas
  automaticamente pelos inicializadores.

## Como iniciar
- **macOS:** duplo clique em **`iniciar.command`**
- **Windows:** duplo clique em **`iniciar.bat`**
- Manual: `pip install -r requirements.txt` e depois `python app.py`

O navegador abre em **http://127.0.0.1:5000**.

## Fluxo de uso
1. **+ Novo paciente** → informe ano, mês, nome e o tipo de exame
   (Endoscopia/Colonoscopia). A estrutura de pastas é criada.
2. Coloque os PDFs em `inputs/` (nomeados `1.pdf … N.pdf`) — pelo Finder/Explorer
   **ou** pelo botão **Enviar PDFs** na linha do paciente.
3. Clique em **Escanear** para atualizar a lista.
4. Pacientes completos ficam com status **Pronto p/ unir**.
   - Individual: botão **Unir** na linha.
   - Lote: marque os checkboxes e clique **Unir selecionados**.
5. O PDF final aparece em `output/`, com o nome do Nº da Guia. Clique no número
   para abrir, ou em **Pasta** para abrir no Finder/Explorer.

## Estrutura criada
```
Guias Unimed/
  2026/
    05/
      FERNANDA DOS SANTOS VAZ/
        inputs/   1.pdf 2.pdf 3.pdf 4.pdf 5.pdf 6.pdf 7.pdf
        output/   18009206000040352547.pdf
  .unificador/registry.json   (tipo de exame por paciente + resultados)
```

## Observações
- O **número da guia** é lido por OCR do `1.pdf`. Se a leitura falhar, o app pede
  o número manualmente antes de unir (nunca gera arquivo com nome errado).
- Nome do paciente, ano e mês vêm dos **nomes das pastas** (você controla) — não
  dependem de OCR, evitando erro de arquivamento.
- A pasta base pode ser trocada em **Configurações** (ex.: apontar para uma pasta
  no Google Drive/OneDrive sincronizada).
