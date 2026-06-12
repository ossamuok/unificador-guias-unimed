@echo off
REM ============================================================
REM  Gera o executavel UnificadorGuias.exe para Windows.
REM  RODE ESTE ARQUIVO EM UM PC WINDOWS (com Python 3.10+ instalado).
REM  Nao e possivel gerar .exe de Windows a partir do Mac.
REM ============================================================
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo [ERRO] Python nao encontrado. Instale o Python 3.10+ de python.org
  echo        e marque "Add Python to PATH" durante a instalacao.
  pause
  exit /b 1
)

echo ==^> Instalando dependencias de build...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller
if errorlevel 1 ( echo [ERRO] Falha ao instalar dependencias. & pause & exit /b 1 )

echo ==^> Empacotando (PyInstaller)...
python -m PyInstaller --noconfirm unificador.spec
if errorlevel 1 ( echo [ERRO] Falha no empacotamento. & pause & exit /b 1 )

echo.
echo ============================================================
echo  PRONTO!  Executavel gerado em:  dist\UnificadorGuias.exe
echo.
echo  Para o OCR (ler o numero da guia) funcionar, o PC precisa do
echo  Tesseract instalado (https://github.com/UB-Mannheim/tesseract/wiki)
echo  OU coloque uma pasta 'tesseract' aqui antes de buildar para
echo  embutir o OCR no proprio .exe (veja BUILD_WINDOWS.md).
echo ============================================================
pause
