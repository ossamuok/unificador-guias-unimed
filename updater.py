"""Auto-atualização do executável Windows via GitHub Releases.

Fluxo:
  1. check_update() consulta a API pública de releases do GitHub e compara a versão.
  2. apply_update(url) baixa o novo .exe e agenda a troca: um .bat espera este
     processo encerrar, substitui o .exe antigo, relança e se apaga.

Só faz sentido no executável empacotado (sys.frozen). No app Python (Mac) a checagem
funciona, mas apply_update é bloqueado de propósito.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import ssl
import subprocess
import sys
import urllib.request
from pathlib import Path

from version import VERSION, GITHUB_REPO

API_LATEST = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
DETACHED_PROCESS = 0x00000008


def _ssl_ctx() -> ssl.SSLContext:
    """Contexto SSL com CA bundle do certifi (funciona no .exe e no Mac)."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:  # noqa: BLE001
        return ssl.create_default_context()


def _parse(v: str) -> tuple[int, ...]:
    """'v1.2.3' / '1.2.3' -> (1, 2, 3). Faltando partes viram 0."""
    nums = [int(x) for x in re.findall(r"\d+", v or "")][:3]
    nums += [0] * (3 - len(nums))
    return tuple(nums)


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def check_update(timeout: float = 6.0) -> dict:
    """Retorna {disponivel, versao, versao_atual, url, notas} ou {disponivel:False, erro}."""
    try:
        req = urllib.request.Request(
            API_LATEST,
            headers={"Accept": "application/vnd.github+json",
                     "User-Agent": "UnificadorGuias"},
        )
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx()) as resp:
            data = json.load(resp)
    except Exception as e:  # noqa: BLE001 (rede pode falhar — não é erro fatal)
        return {"disponivel": False, "versao_atual": VERSION, "erro": str(e)}

    tag = data.get("tag_name", "")
    asset = next((a for a in data.get("assets", [])
                  if a.get("name", "").lower().endswith(".exe")), None)
    if asset and _parse(tag) > _parse(VERSION):
        return {
            "disponivel": True,
            "versao": tag.lstrip("vV"),
            "versao_atual": VERSION,
            "url": asset["browser_download_url"],
            "notas": (data.get("body") or "").strip()[:1000],
        }
    return {"disponivel": False, "versao": tag.lstrip("vV") or VERSION,
            "versao_atual": VERSION}


def apply_update(url: str) -> None:
    """Baixa o novo .exe e dispara o .bat de troca+relaunch. NÃO encerra o processo
    (quem chama deve sair logo após, para liberar o arquivo)."""
    if not is_frozen():
        raise RuntimeError("Atualização automática só está disponível no executável Windows.")
    if not url:
        raise ValueError("URL de download ausente.")

    exe = Path(sys.executable)
    novo = exe.with_name("UnificadorGuias.new.exe")
    req = urllib.request.Request(url, headers={"User-Agent": "UnificadorGuias"})
    with urllib.request.urlopen(req, timeout=120, context=_ssl_ctx()) as resp, \
            open(novo, "wb") as fh:
        shutil.copyfileobj(resp, fh)

    pid = os.getpid()
    bat = exe.with_name("_update.bat")
    bat.write_text(
        "@echo off\r\n"
        "timeout /t 2 /nobreak >nul\r\n"
        ":loop\r\n"
        f'tasklist /fi "PID eq {pid}" | find "{pid}" >nul && (timeout /t 1 /nobreak >nul & goto loop)\r\n'
        f'move /y "{novo}" "{exe}" >nul\r\n'
        f'start "" "{exe}"\r\n'
        'del "%~f0"\r\n',
        encoding="utf-8",
    )
    subprocess.Popen(["cmd", "/c", str(bat)],
                     creationflags=DETACHED_PROCESS, close_fds=True)
