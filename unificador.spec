# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec — gera UnificadorGuias.exe (rodar NO Windows).
#   pyinstaller --noconfirm unificador.spec
# Resultado: dist\UnificadorGuias.exe  (arquivo único)
import os

# Recursos empacotados dentro do .exe
datas = [
    ('templates', 'templates'),
    ('static', 'static'),
]

# OCR opcional: se existir uma pasta 'tesseract' ao lado deste .spec, ela é
# embutida e o app a usa sozinho (totalmente standalone, sem instalar Tesseract).
# A pasta deve conter tesseract.exe + DLLs + subpasta tessdata (eng.traineddata).
if os.path.isdir('tesseract'):
    datas.append(('tesseract', 'tesseract'))

icon = 'static/icon.ico' if os.path.exists('static/icon.ico') else None

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=['fitz', 'pypdf', 'PIL', 'flask', 'jinja2', 'certifi'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='UnificadorGuias',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,          # sem janela de terminal; a UI é o navegador
    disable_windowed_traceback=False,
    icon=icon,
)
