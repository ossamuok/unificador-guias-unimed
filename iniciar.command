#!/bin/bash
# Unificador de Guias Unimed — inicialização no macOS (duplo clique)
cd "$(dirname "$0")" || exit 1

PY=python3
echo "==> Verificando dependências..."
$PY -m pip install --quiet -r requirements.txt 2>/dev/null

if ! command -v tesseract >/dev/null 2>&1 && [ ! -x /opt/homebrew/bin/tesseract ]; then
  echo ""
  echo "[!] Tesseract (OCR) não encontrado."
  echo "    Instale com: brew install tesseract"
  echo "    Sem ele, a leitura automática do Nº da Guia não funciona."
  echo ""
fi

echo "==> Iniciando o app... o navegador abrirá em http://127.0.0.1:5000"
echo "    (Para encerrar, feche esta janela ou pressione Ctrl+C)"
$PY app.py
