; ============================================================
;  Inno Setup — cria um INSTALADOR .exe de verdade para Windows.
;  (Opcional — só se quiser um instalador com atalhos no Menu Iniciar
;   e na Área de Trabalho, em vez do .exe solto.)
;
;  Pré-requisitos:
;   1) Já ter rodado build_windows.bat (gera dist\UnificadorGuias.exe)
;   2) Instalar o Inno Setup: https://jrsoftware.org/isdl.php
;   3) Abrir este arquivo no Inno Setup e clicar em "Compile"
;
;  Saída: Output\UnificadorGuias-Instalador.exe
; ============================================================

[Setup]
AppName=Unificador de Guias Unimed
AppVersion=1.0
AppPublisher=Centro Clinico Okazaki
DefaultDirName={autopf}\UnificadorGuias
DefaultGroupName=Unificador de Guias Unimed
DisableProgramGroupPage=yes
OutputBaseFilename=UnificadorGuias-Instalador
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na Área de Trabalho"; GroupDescription: "Atalhos:"

[Files]
Source: "dist\UnificadorGuias.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion isreadme
; Se embutiu o OCR numa pasta 'tesseract', descomente a linha abaixo:
; Source: "tesseract\*"; DestDir: "{app}\tesseract"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Unificador de Guias Unimed"; Filename: "{app}\UnificadorGuias.exe"
Name: "{group}\Desinstalar"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Unificador de Guias Unimed"; Filename: "{app}\UnificadorGuias.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\UnificadorGuias.exe"; Description: "Abrir o Unificador agora"; Flags: nowait postinstall skipifsilent
