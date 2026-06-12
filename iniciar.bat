@echo off
REM Unificador de Guias Unimed - inicializacao no Windows (duplo clique)
cd /d "%~dp0"

echo ==^> Verificando dependencias...
python -m pip install --quiet -r requirements.txt

where tesseract >nul 2>nul
if errorlevel 1 (
  if not exist "C:\Program Files\Tesseract-OCR\tesseract.exe" (
    echo.
    echo [!] Tesseract OCR nao encontrado.
    echo     Baixe em: https://github.com/UB-Mannheim/tesseract/wiki
    echo     Sem ele, a leitura automatica do No da Guia nao funciona.
    echo.
  )
)

echo ==^> Iniciando o app... o navegador abrira em http://127.0.0.1:5000
echo     (Para encerrar, feche esta janela ou pressione Ctrl+C)
python app.py
pause
