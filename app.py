"""
app.py — Servidor web local (Flask) do Unificador de Guias Unimed.

Roda 100% local. Abra http://127.0.0.1:5000 no navegador.
Toda a lógica pesada está em core.py.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import webbrowser
from pathlib import Path
from threading import Timer

from flask import (
    Flask, jsonify, render_template, request, send_file, abort,
)

import core
import updater
from version import VERSION

# Compatível com execução normal e empacotada (PyInstaller .exe):
#  - APP_DIR: onde ficam os DADOS do usuário (config.json, pasta "Guias Unimed").
#    Quando .exe, é a pasta do executável (não a pasta temporária _MEIPASS).
#  - RES_DIR: onde ficam os RECURSOS empacotados (templates/static). _MEIPASS quando .exe.
FROZEN = getattr(sys, "frozen", False)
APP_DIR = (Path(sys.executable).resolve().parent if FROZEN
           else Path(__file__).resolve().parent)
RES_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
CONFIG_PATH = APP_DIR / "config.json"
DEFAULT_BASE = APP_DIR / "Guias Unimed"

app = Flask(__name__,
            template_folder=str(RES_DIR / "templates"),
            static_folder=str(RES_DIR / "static"))


# --------------------------------------------------------------------------- #
# Config (pasta base)
# --------------------------------------------------------------------------- #
def load_config() -> dict:
    if CONFIG_PATH.is_file():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_config(cfg: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2),
                           encoding="utf-8")


def get_base() -> Path:
    cfg = load_config()
    base = Path(cfg.get("base", str(DEFAULT_BASE)))
    base.mkdir(parents=True, exist_ok=True)
    return base


def parse_key(key: str) -> tuple[str, str, str]:
    """Valida e divide 'ano/mes/paciente'. Bloqueia traversal de caminho."""
    parts = (key or "").split("/")
    if len(parts) != 3 or not all(parts):
        raise ValueError("Identificador de paciente inválido.")
    for part in parts:
        if part in (".", "..") or "\\" in part or "\x00" in part:
            raise ValueError("Identificador de paciente inválido.")
    return parts[0], parts[1], parts[2]


# --------------------------------------------------------------------------- #
# Páginas
# --------------------------------------------------------------------------- #
@app.route("/")
def index():
    return render_template("index.html")


# --------------------------------------------------------------------------- #
# API
# --------------------------------------------------------------------------- #
@app.get("/api/config")
def api_config():
    base = get_base()
    return jsonify({
        "base": str(base),
        "tesseract": core.find_tesseract(),
        "tipos": core.TIPOS,
        "version": VERSION,
        "frozen": updater.is_frozen(),
    })


@app.get("/api/update/check")
def api_update_check():
    """Verifica se há versão nova publicada no GitHub."""
    return jsonify(updater.check_update())


@app.post("/api/update/apply")
def api_update_apply():
    """Baixa e aplica a atualização; o app encerra e o .bat troca + relança."""
    data = request.get_json(force=True) or {}
    url = (data.get("url") or "").strip()
    if not url:
        info = updater.check_update()
        url = info.get("url", "")
    try:
        updater.apply_update(url)
    except (RuntimeError, ValueError, OSError) as e:
        return jsonify({"ok": False, "erro": str(e)}), 400
    # responde antes de sair, dando tempo do .bat assumir
    Timer(0.8, lambda: os._exit(0)).start()
    return jsonify({"ok": True})


@app.post("/api/config")
def api_set_config():
    data = request.get_json(force=True) or {}
    base = (data.get("base") or "").strip()
    if not base:
        return jsonify({"ok": False, "erro": "Caminho vazio."}), 400
    cfg = load_config()
    cfg["base"] = base
    save_config(cfg)
    Path(base).mkdir(parents=True, exist_ok=True)
    return jsonify({"ok": True, "base": base})


@app.get("/api/periodos")
def api_periodos():
    """Anos e meses disponíveis para o filtro de data."""
    base = get_base()
    anos = core.list_anos(base)
    meses = {a: core.list_meses(base, a) for a in anos}
    return jsonify({"anos": anos, "meses": meses, "meses_pt": core.MESES_PT})


@app.get("/api/scan")
def api_scan():
    base = get_base()
    ano = request.args.get("ano") or None
    mes = request.args.get("mes") or None
    pacientes = [p.to_dict() for p in core.scan(base, ano, mes)]
    erros = [p for p in pacientes
             if p["status"] in ("incompleto", "sem_tipo", "excedente", "erro")
             or p["avisos"]]
    return jsonify({"pacientes": pacientes, "erros": erros})


@app.post("/api/tipo")
def api_tipo():
    base = get_base()
    data = request.get_json(force=True) or {}
    try:
        ano, mes, paciente = parse_key(data.get("key", ""))
        core.set_tipo(base, ano, mes, paciente, data["tipo"])
    except (KeyError, ValueError) as e:
        return jsonify({"ok": False, "erro": str(e)}), 400
    st = core.compute_status(base, ano, mes, paciente)
    return jsonify({"ok": True, "paciente": st.to_dict()})


@app.post("/api/paciente")
def api_novo_paciente():
    base = get_base()
    data = request.get_json(force=True) or {}
    try:
        st = core.create_patient(
            base,
            data.get("ano", ""), data.get("mes", ""),
            data.get("paciente", ""), data.get("tipo") or None,
        )
    except ValueError as e:
        return jsonify({"ok": False, "erro": str(e)}), 400
    return jsonify({"ok": True, "paciente": st.to_dict()})


@app.post("/api/paciente/apagar")
def api_apagar_paciente():
    """Apaga a pasta do paciente. Ação irreversível — confirmada no frontend."""
    base = get_base()
    data = request.get_json(force=True) or {}
    try:
        ano, mes, paciente = parse_key(data.get("key", ""))
        core.delete_patient(base, ano, mes, paciente)
    except (ValueError, FileNotFoundError) as e:
        return jsonify({"ok": False, "erro": str(e)}), 400
    return jsonify({"ok": True})


@app.post("/api/upload")
def api_upload():
    """Recebe PDFs e grava em inputs/ do paciente.

    A ORDEM é definida pelo NÚMERO no nome original do arquivo (1.pdf, 02.pdf,
    '3 - guia.pdf' …), NUNCA pela ordem em que o navegador entrega os arquivos —
    isso evita que a sequência fique trocada/invertida. Arquivos sem número no
    nome vão para os próximos espaços livres (ordenados pelo nome)."""
    base = get_base()
    try:
        ano, mes, paciente = parse_key(request.form.get("key", ""))
    except ValueError:
        return jsonify({"ok": False, "erro": "Paciente inválido."}), 400
    inputs_dir = base / ano / mes / paciente / "inputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)

    files = [f for f in request.files.getlist("files")
             if f.filename and f.filename.lower().endswith(".pdf")]
    if not files:
        return jsonify({"ok": False, "erro": "Nenhum PDF enviado."}), 400

    numerados, sem_numero = [], []
    for f in files:
        n = core._leading_int(f.filename)
        (numerados if n is not None else sem_numero).append((n, f))

    ocupados = {d.numero for d in core.list_input_files(inputs_dir)[0]}
    salvos, avisos = [], []

    # 1) arquivos com número no nome → respeitam o número (substituem o existente)
    for n, f in sorted(numerados, key=lambda x: x[0]):
        dest = inputs_dir / f"{n}.pdf"
        f.save(str(dest))
        ocupados.add(n)
        salvos.append((n, dest.name))

    # 2) arquivos sem número → próximos espaços livres, em ordem alfabética
    prox = 1
    for _, f in sorted(sem_numero, key=lambda x: (x[1].filename or "").lower()):
        while prox in ocupados:
            prox += 1
        dest = inputs_dir / f"{prox}.pdf"
        f.save(str(dest))
        ocupados.add(prox)
        salvos.append((prox, dest.name))
        avisos.append(f"'{f.filename}' não tinha número no nome → salvo como {prox}.pdf")

    salvos.sort(key=lambda x: x[0])
    st = core.compute_status(base, ano, mes, paciente)
    return jsonify({"ok": True, "salvos": [s[1] for s in salvos],
                    "avisos": avisos, "paciente": st.to_dict()})


@app.post("/api/merge")
def api_merge():
    base = get_base()
    data = request.get_json(force=True) or {}
    keys = data.get("keys") or ([data["key"]] if data.get("key") else [])
    if not keys:
        return jsonify({"ok": False, "erro": "Nenhum paciente selecionado."}), 400
    try:
        for k in keys:
            parse_key(k)
    except ValueError as e:
        return jsonify({"ok": False, "erro": str(e)}), 400
    guia_override = data.get("guia")  # só válido p/ união individual
    tess = core.find_tesseract()
    if len(keys) == 1 and guia_override:
        ano, mes, paciente = parse_key(keys[0])
        r = core.merge_patient(base, ano, mes, paciente, tess, guia_override)
        results = [r]
    else:
        results = core.merge_batch(base, keys, tess)
    return jsonify({
        "ok": True,
        "resultados": [r.__dict__ for r in results],
    })


@app.get("/api/pdf")
def api_pdf():
    """Serve um PDF de output para visualização no navegador."""
    base = get_base()
    path = Path(request.args.get("path", ""))
    try:
        path.resolve().relative_to(base.resolve())
    except ValueError:
        abort(403)
    if not path.is_file() or path.suffix.lower() != ".pdf":
        abort(404)
    return send_file(str(path), mimetype="application/pdf")


@app.post("/api/abrir")
def api_abrir():
    """Abre a pasta no Finder/Explorer."""
    base = get_base()
    path = Path((request.get_json(force=True) or {}).get("path", ""))
    try:
        path.resolve().relative_to(base.resolve())
    except ValueError:
        return jsonify({"ok": False, "erro": "Caminho fora da base."}), 403
    if not path.exists():
        return jsonify({"ok": False, "erro": "Caminho não existe."}), 404
    try:
        if sys.platform == "darwin":
            subprocess.run(["open", str(path)])
        elif os.name == "nt":
            os.startfile(str(path))  # type: ignore[attr-defined]
        else:
            subprocess.run(["xdg-open", str(path)])
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "erro": str(e)}), 500
    return jsonify({"ok": True})


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def _open_browser():
    webbrowser.open("http://127.0.0.1:5000")


if __name__ == "__main__":
    get_base()
    if core.find_tesseract() is None:
        print("\n[AVISO] Tesseract (OCR) não encontrado. A leitura do número da "
              "guia não vai funcionar até instalar. Veja o README.\n")
    if "--no-browser" not in sys.argv:
        Timer(1.0, _open_browser).start()
    app.run(host="127.0.0.1", port=5000, debug=False)
