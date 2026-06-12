"""
core.py — Lógica do Unificador de Guias Unimed (sem dependência de Flask).

Responsável por:
  - localizar o binário do tesseract (Mac/Windows)
  - extrair o "Nº da Guia no Prestador" do 1.pdf via OCR
  - listar/ordenar os arquivos de entrada (1.pdf..N.pdf)
  - calcular o status de cada paciente (pronto/incompleto/...)
  - unir os PDFs na ordem correta e salvar em output/{nº da guia}.pdf
  - registry: tipo de exame por paciente + resultado da última unificação
  - varrer a árvore Guias Unimed/{ano}/{mês}/{paciente}/

Toda a lógica pesada fica aqui para poder ser testada sem subir o servidor web.
"""
from __future__ import annotations

import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, asdict, field
from pathlib import Path

import fitz  # PyMuPDF
from PIL import Image
from pypdf import PdfReader, PdfWriter

# --------------------------------------------------------------------------- #
# Configuração de tipos de exame
# --------------------------------------------------------------------------- #
TIPOS = {
    "endoscopia": {"label": "Endoscopia", "esperado": 7},
    "colonoscopia": {"label": "Colonoscopia", "esperado": 6},
}

MESES_PT = [
    "", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]

REGISTRY_DIRNAME = ".unificador"
REGISTRY_FILENAME = "registry.json"


# --------------------------------------------------------------------------- #
# Tesseract
# --------------------------------------------------------------------------- #
def find_tesseract() -> str | None:
    """Retorna o caminho do binário tesseract ou None se não encontrado.

    Prioriza um tesseract empacotado junto ao app (subpasta 'tesseract/' ao lado
    do .exe), depois procura no PATH e nos locais padrão de instalação."""
    for d in (Path(getattr(sys, "_MEIPASS", "")) / "tesseract",
              Path(sys.executable).resolve().parent / "tesseract"):
        for nome in ("tesseract.exe", "tesseract"):
            p = d / nome
            if p.is_file():
                return str(p)
    found = shutil.which("tesseract")
    if found:
        return found
    candidates = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        "/opt/homebrew/bin/tesseract",
        "/usr/local/bin/tesseract",
        "/usr/bin/tesseract",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


# --------------------------------------------------------------------------- #
# OCR — extração do número da guia
# --------------------------------------------------------------------------- #
def _render_top_band(pdf_path: str | Path, top_frac: float = 0.22,
                     target_w: int = 2600) -> Image.Image:
    """Renderiza apenas a faixa superior da 1ª página com largura-alvo controlada.

    Evita estourar memória em páginas de scan com MediaBox grande, renderizando
    só o clip do topo (onde fica o campo 'Nº GUIA NO PRESTADOR').
    """
    doc = fitz.open(str(pdf_path))
    try:
        page = doc[0]
        rect = page.rect
        zoom = max(target_w / rect.width, 1.0)
        mat = fitz.Matrix(zoom, zoom)
        clip = fitz.Rect(0, 0, rect.width, rect.height * top_frac)
        pix = page.get_pixmap(matrix=mat, clip=clip)
        return Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    finally:
        doc.close()


def _tesseract_text(img: Image.Image, tesseract: str, psm: str = "6") -> str:
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp.close()
    try:
        img.save(tmp.name)
        proc = subprocess.run(
            [tesseract, tmp.name, "stdout", "--psm", psm],
            capture_output=True, text=True,
        )
        return proc.stdout or ""
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


def extract_guia_number(pdf_path: str | Path, tesseract: str | None = None) -> str | None:
    """Extrai o Nº da Guia no Prestador da 1ª página do PDF (guia SP/SADT).

    Estratégia:
      1. OCR da faixa superior.
      2. Na linha que contém 'PRESTADOR', pega a maior sequência de dígitos.
      3. Fallback: maior sequência de >=14 dígitos em toda a faixa.
    Retorna a string de dígitos ou None se não conseguir ler com confiança.
    """
    tesseract = tesseract or find_tesseract()
    if not tesseract:
        raise RuntimeError("Tesseract não encontrado. Instale o OCR (ver README).")

    img = _render_top_band(pdf_path)
    text = _tesseract_text(img, tesseract)

    # 1) linha com o rótulo "PRESTADOR"
    for line in text.splitlines():
        if re.search(r"PRESTADOR", line, re.I):
            digits = re.findall(r"\d{10,}", re.sub(r"\s+", "", line))
            if digits:
                return max(digits, key=len)

    # 2) fallback: maior sequência longa de dígitos na faixa
    alld = re.findall(r"\d{14,}", re.sub(r"\s+", "", text))
    if alld:
        return max(alld, key=len)
    return None


# --------------------------------------------------------------------------- #
# Arquivos de entrada
# --------------------------------------------------------------------------- #
def _leading_int(name: str) -> int | None:
    """Extrai o inteiro inicial do nome do arquivo ('1.pdf','01 - x.pdf' -> 1)."""
    m = re.match(r"^\s*0*(\d+)", Path(name).stem)
    return int(m.group(1)) if m else None


@dataclass
class InputDoc:
    numero: int
    nome: str
    caminho: str


def list_input_files(inputs_dir: str | Path) -> tuple[list[InputDoc], list[str]]:
    """Lista PDFs de entrada ordenados pelo número inicial do nome.

    Retorna (docs_ordenados, avisos). Avisos cobrem arquivos sem número e
    números duplicados.
    """
    inputs_dir = Path(inputs_dir)
    docs: dict[int, InputDoc] = {}
    avisos: list[str] = []
    if not inputs_dir.is_dir():
        return [], avisos
    for f in sorted(inputs_dir.iterdir()):
        if not f.is_file() or f.suffix.lower() != ".pdf":
            continue
        n = _leading_int(f.name)
        if n is None:
            avisos.append(f"Arquivo sem número ignorado: {f.name}")
            continue
        if n in docs:
            avisos.append(f"Número {n} duplicado: '{docs[n].nome}' e '{f.name}'")
            continue
        docs[n] = InputDoc(numero=n, nome=f.name, caminho=str(f))
    ordenados = [docs[k] for k in sorted(docs)]
    return ordenados, avisos


# --------------------------------------------------------------------------- #
# Registry (tipo por paciente + último resultado)
# --------------------------------------------------------------------------- #
def _registry_path(base: str | Path) -> Path:
    return Path(base) / REGISTRY_DIRNAME / REGISTRY_FILENAME


def load_registry(base: str | Path) -> dict:
    p = _registry_path(base)
    if p.is_file():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_registry(base: str | Path, data: dict) -> None:
    p = _registry_path(base)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _patient_key(ano: str, mes: str, paciente: str) -> str:
    return f"{ano}/{mes}/{paciente}"


# --------------------------------------------------------------------------- #
# Status do paciente
# --------------------------------------------------------------------------- #
@dataclass
class PatientStatus:
    ano: str
    mes: str
    mes_label: str
    paciente: str
    key: str
    tipo: str | None            # 'endoscopia' | 'colonoscopia' | None
    esperado: int | None
    presentes: list[int]
    faltando: list[int]
    excedentes: list[int]
    status: str                 # pronto|incompleto|sem_tipo|excedente|unificado|erro
    guia: str | None
    output_pdf: str | None
    avisos: list[str] = field(default_factory=list)
    erro: str | None = None
    inputs_dir: str = ""
    output_dir: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _output_pdf(output_dir: Path) -> str | None:
    if not output_dir.is_dir():
        return None
    pdfs = [f for f in output_dir.iterdir() if f.suffix.lower() == ".pdf"]
    return str(pdfs[0]) if pdfs else None


def compute_status(base: str | Path, ano: str, mes: str, paciente: str,
                   registry: dict | None = None) -> PatientStatus:
    base = Path(base)
    registry = registry if registry is not None else load_registry(base)
    key = _patient_key(ano, mes, paciente)
    reg = registry.get(key, {})

    pdir = base / ano / mes / paciente
    inputs_dir = pdir / "inputs"
    output_dir = pdir / "output"

    docs, avisos = list_input_files(inputs_dir)
    presentes = [d.numero for d in docs]

    tipo = reg.get("tipo")
    esperado = TIPOS[tipo]["esperado"] if tipo in TIPOS else None

    out_pdf = _output_pdf(output_dir)
    guia = reg.get("guia")
    erro = reg.get("erro")

    faltando: list[int] = []
    excedentes: list[int] = []
    if esperado is not None:
        alvo = set(range(1, esperado + 1))
        pres = set(presentes)
        faltando = sorted(alvo - pres)
        excedentes = sorted(n for n in pres if n > esperado)

    # Determinação do status (ordem de prioridade).
    # Estados derivados do disco (sem_tipo/excedente/incompleto) têm prioridade
    # sobre 'erro' persistido — assim um erro antigo de OCR não esconde o fato
    # de que o conjunto ainda está incompleto, e um erro stale some quando o
    # conjunto deixa de estar pronto.
    if out_pdf:
        status = "unificado"
    elif tipo not in TIPOS:
        status = "sem_tipo"
    elif excedentes:
        status = "excedente"
    elif faltando:
        status = "incompleto"
    elif erro:
        status = "erro"   # conjunto completo e tipado, mas última união falhou
    else:
        status = "pronto"

    mes_idx = _leading_int(mes) or 0
    mes_label = MESES_PT[mes_idx] if 0 < mes_idx < len(MESES_PT) else mes

    return PatientStatus(
        ano=ano, mes=mes, mes_label=mes_label, paciente=paciente, key=key,
        tipo=tipo, esperado=esperado, presentes=presentes,
        faltando=faltando, excedentes=excedentes, status=status,
        guia=guia if out_pdf else None,
        output_pdf=out_pdf, avisos=avisos, erro=erro,
        inputs_dir=str(inputs_dir), output_dir=str(output_dir),
    )


# --------------------------------------------------------------------------- #
# Varredura da árvore
# --------------------------------------------------------------------------- #
def _list_subdirs(p: Path) -> list[str]:
    if not p.is_dir():
        return []
    return sorted(
        d.name for d in p.iterdir()
        if d.is_dir() and d.name != REGISTRY_DIRNAME
    )


def list_anos(base: str | Path) -> list[str]:
    return [d for d in _list_subdirs(Path(base)) if re.match(r"^\d{4}$", d)]


def list_meses(base: str | Path, ano: str) -> list[str]:
    return _list_subdirs(Path(base) / ano)


def scan(base: str | Path, ano: str | None = None,
         mes: str | None = None) -> list[PatientStatus]:
    """Varre a árvore e retorna o status de cada paciente, filtrando por ano/mês."""
    base = Path(base)
    registry = load_registry(base)
    out: list[PatientStatus] = []
    anos = [ano] if ano else list_anos(base)
    for a in anos:
        if not (base / a).is_dir():
            continue
        meses = [mes] if mes else list_meses(base, a)
        for m in meses:
            if not (base / a / m).is_dir():
                continue
            for paciente in _list_subdirs(base / a / m):
                out.append(compute_status(base, a, m, paciente, registry))
    return out


# --------------------------------------------------------------------------- #
# Criação de paciente / estrutura
# --------------------------------------------------------------------------- #
_SAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize_name(name: str) -> str:
    name = _SAFE.sub("", name).strip().strip(".")
    return re.sub(r"\s+", " ", name)


def create_patient(base: str | Path, ano: str, mes: str, paciente: str,
                   tipo: str | None = None) -> PatientStatus:
    ano = sanitize_name(ano)
    mes = sanitize_name(mes)
    paciente = sanitize_name(paciente)
    if not (ano and mes and paciente):
        raise ValueError("Ano, mês e nome do paciente são obrigatórios.")
    base = Path(base)
    (base / ano / mes / paciente / "inputs").mkdir(parents=True, exist_ok=True)
    if tipo in TIPOS:
        set_tipo(base, ano, mes, paciente, tipo)
    return compute_status(base, ano, mes, paciente)


def set_tipo(base: str | Path, ano: str, mes: str, paciente: str,
             tipo: str) -> None:
    if tipo not in TIPOS:
        raise ValueError(f"Tipo inválido: {tipo}")
    reg = load_registry(base)
    key = _patient_key(ano, mes, paciente)
    entry = reg.get(key, {})
    entry["tipo"] = tipo
    reg[key] = entry
    save_registry(base, reg)


def delete_patient(base: str | Path, ano: str, mes: str,
                   paciente: str) -> None:
    """Apaga a pasta do paciente (inputs+output) e remove do registry.

    Valida que o diretório está DENTRO da base (defesa contra traversal) antes
    de apagar. Remove pastas de mês/ano que ficarem vazias. Irreversível.
    """
    base = Path(base)
    pdir = base / ano / mes / paciente
    # containment: levanta ValueError se cair fora da base
    pdir.resolve().relative_to(base.resolve())
    if not pdir.is_dir():
        raise FileNotFoundError("Paciente não encontrado.")
    shutil.rmtree(pdir)

    reg = load_registry(base)
    if reg.pop(_patient_key(ano, mes, paciente), None) is not None:
        save_registry(base, reg)

    # poda pastas mês/ano que ficaram vazias (nunca a base)
    for parent in (base / ano / mes, base / ano):
        try:
            if parent.is_dir() and not any(parent.iterdir()):
                parent.rmdir()
        except OSError:
            pass


def _set_result(base: str | Path, key: str, *, guia: str | None,
                erro: str | None) -> None:
    reg = load_registry(base)
    entry = reg.get(key, {})
    entry["guia"] = guia
    entry["erro"] = erro
    reg[key] = entry
    save_registry(base, reg)


# --------------------------------------------------------------------------- #
# Merge
# --------------------------------------------------------------------------- #
@dataclass
class MergeResult:
    key: str
    paciente: str
    ok: bool
    guia: str | None = None
    output_pdf: str | None = None
    paginas: int | None = None
    erro: str | None = None


def merge_patient(base: str | Path, ano: str, mes: str, paciente: str,
                  tesseract: str | None = None,
                  guia_override: str | None = None) -> MergeResult:
    """Une os PDFs de um paciente completo e salva em output/{guia}.pdf.

    Só executa se o paciente estiver com status 'pronto' (ou já unificado, caso
    em que sobrescreve). Erros são registrados no registry e retornados.
    """
    base = Path(base)
    key = _patient_key(ano, mes, paciente)
    st = compute_status(base, ano, mes, paciente)

    # Pré-checagens sobre os FATOS atuais do disco (não sobre st.status), pois
    # 'unificado' tem prioridade no status e poderia mascarar um conjunto que
    # voltou a ficar incompleto antes de um "Refazer". NÃO persistem no registry
    # (são transitórias — somem quando o operador corrige as pastas).
    if st.tipo not in TIPOS:
        return MergeResult(key=key, paciente=paciente, ok=False,
                           erro="Tipo de exame não definido.")
    if st.excedentes:
        extra = ", ".join(map(str, st.excedentes))
        return MergeResult(key=key, paciente=paciente, ok=False,
                           erro=f"Arquivos a mais para {TIPOS[st.tipo]['label']}: {extra}.")
    if st.faltando:
        faltam = ", ".join(map(str, st.faltando))
        return MergeResult(key=key, paciente=paciente, ok=False,
                           erro=f"Documentos faltando (esperado {st.esperado}): {faltam}.")

    docs, _ = list_input_files(st.inputs_dir)
    if not docs:
        return _fail(base, key, paciente, "Nenhum PDF de entrada encontrado.")

    # Número da guia: override manual ou OCR do primeiro documento
    guia = (guia_override or "").strip() or None
    if not guia:
        try:
            guia = extract_guia_number(docs[0].caminho, tesseract)
        except Exception as e:  # noqa: BLE001
            return _fail(base, key, paciente, f"Falha no OCR: {e}")
        if not guia:
            return _fail(
                base, key, paciente,
                "Não foi possível ler o Nº da Guia no 1.pdf. "
                "Informe o número manualmente.",
            )

    guia = re.sub(r"\D", "", guia)  # só dígitos no nome do arquivo
    if not guia:
        return _fail(base, key, paciente, "Nº da Guia inválido (sem dígitos).")

    # Merge na ordem numérica
    writer = PdfWriter()
    try:
        for d in docs:
            writer.append(d.caminho)
        output_dir = Path(st.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        # limpa PDFs antigos do output para não acumular nomes
        for old in output_dir.glob("*.pdf"):
            try:
                old.unlink()
            except OSError:
                pass
        out_path = output_dir / f"{guia}.pdf"
        with open(out_path, "wb") as fh:
            writer.write(fh)
    except Exception as e:  # noqa: BLE001
        return _fail(base, key, paciente, f"Falha ao unir/salvar: {e}")
    finally:
        writer.close()

    paginas = len(PdfReader(str(out_path)).pages)
    _set_result(base, key, guia=guia, erro=None)
    return MergeResult(key=key, paciente=paciente, ok=True, guia=guia,
                       output_pdf=str(out_path), paginas=paginas)


def _fail(base, key, paciente, msg) -> MergeResult:
    _set_result(base, key, guia=None, erro=msg)
    return MergeResult(key=key, paciente=paciente, ok=False, erro=msg)


def merge_batch(base: str | Path, keys: list[str],
                tesseract: str | None = None) -> list[MergeResult]:
    tesseract = tesseract or find_tesseract()
    results: list[MergeResult] = []
    for key in keys:
        parts = key.split("/")
        if len(parts) != 3:
            results.append(MergeResult(key=key, paciente=key, ok=False,
                                       erro="Chave de paciente inválida."))
            continue
        ano, mes, paciente = parts
        results.append(merge_patient(base, ano, mes, paciente, tesseract))
    return results
