# Lessons — App Unificador de PDF Unimed

Log de correções e regras aprendidas. Atualizar após qualquer bug/feedback/retrabalho.

## Descobertas iniciais (build)
- Os PDFs das guias são **escaneados (imagem)** — não têm camada de texto. `pypdf.extract_text()` retorna vazio. Por isso OCR é obrigatório p/ ler o número da guia.
- O **código de barras** do topo decodifica para `238510247_11975` (lote interno), **NÃO** é o Nº da Guia no Prestador. Não usar barcode p/ nomear o arquivo.
- O número da guia (`Nº GUIA NO PRESTADOR`) é texto impresso limpo no topo → OCR tesseract (psm 6) lê com precisão. Validado: `18009206000040352547`.
- A página do scan tem MediaBox grande (≈40in). Renderizar a página inteira em alta DPI estoura memória. Solução: renderizar só o clip do topo (22%) com zoom alvo p/ ~2600px de largura.
- Nome do paciente, ano e mês vêm dos **nomes das pastas** (operador organiza) — não usar OCR p/ isso (evita erro de arquivamento de doc médico).

## Correções (review próprio — review multi-agente caiu por limite de sessão)
- **Bug de corretude:** `merge_patient` checava `st.status`, mas `unificado` tem
  prioridade sobre `incompleto`. Refazer um paciente já unificado cujos inputs
  voltaram a ficar incompletos uniria documentos faltando e sobrescreveria o PDF.
  - Causa: decidir bloqueio pela *string de status* em vez dos *fatos* (`tipo`/`faltando`/`excedentes`).
  - Regra: pré-checagens de merge devem olhar os dados crus do disco, não um
    status derivado que pode ser mascarado por outro estado de maior prioridade.
  - Teste de regressão: refazer com 1 doc removido → bloqueia e preserva o output de 7 págs.
- **Robustez frontend:** `unir()` não tratava erro de rede → spinner travado sem
  feedback. Agora faz try/catch → toast + re-scan (limpa a UI).
- **Segurança:** `parse_key` rejeita `..`, `\`, NUL e formato fora de `ano/mes/paciente`
  em /api/tipo, /api/upload, /api/merge. /api/pdf e /api/abrir validam containment via
  `resolve().relative_to(base)`.
- **Teste via shell:** montar args de `curl` em variável (`F="$F -F files=@$n"`) e usar
  sem aspas pode expandir vazio → upload sem arquivos. Passar os `-F` literais.

## Bug de ORDEM no upload (encontrado pelo usuário em teste real) — CRÍTICO
- Sintoma: PDF unido saiu com páginas em ordem trocada (na verdade INVERTIDA).
- Causa raiz: `/api/upload` renomeava todo arquivo para `{prox}.pdf` pela ordem de
  CHEGADA do navegador, ignorando o número no nome original. O navegador entregou
  os arquivos em ordem inversa → input 1 recebeu o conteúdo do doc 7, etc.
- Diagnóstico: hash MD5 de cada input vs EXEMPLOS provou o mapeamento invertido.
- Fix: upload passou a RESPEITAR o número do nome original (`core._leading_int`):
  `3.pdf` sempre vira input 3, não importa a ordem de chegada. Sem número no nome →
  próximos espaços livres em ordem alfabética (+ aviso).
- Verificação: enviar 7→1 invertido e confirmar `input n == EXEMPLO n`; depois comparar
  hash da IMAGEM embutida de cada página do merge vs PDF de referência (todas batem).
- Regra: nunca confiar na ordem de entrega de arquivos do navegador/FS. A ordem é dado
  do usuário (número no nome) — preservá-la explicitamente.
- Cuidado operacional: `pkill -f app.py` às vezes não derruba; usar
  `lsof -ti tcp:5000 | xargs kill -9` p/ garantir que o código novo suba na porta.

## Feature: busca por nome de paciente
- Filtro client-side sobre os pacientes já carregados (instantâneo, sem novo scan).
- `norm()` = NFD + remove diacríticos + lowercase → busca ignora acento e caixa.
