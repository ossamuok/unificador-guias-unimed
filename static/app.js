"use strict";

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];

const STATUS_LABEL = {
  pronto: "Pronto p/ unir", unificado: "Unificado", incompleto: "Incompleto",
  sem_tipo: "Definir tipo", excedente: "Arquivos a mais", erro: "Erro",
};
const TIPO_LABEL = { endoscopia: "Endoscopia", colonoscopia: "Colonoscopia" };

let CONFIG = { tipos: {} };
let PACIENTES = [];
let ERROS = [];
let NOME_Q = "";   // termo de busca por nome (normalizado)
let UPDATE_URL = null;   // URL do .exe novo quando há atualização

// normaliza p/ busca: remove acentos e caixa ("João" -> "joao")
const norm = s => (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();

// ------------------------------------------------------------------ utils
async function api(url, opts) {
  const r = await fetch(url, opts);
  let data = {};
  try { data = await r.json(); } catch (_) {}
  if (!r.ok) throw new Error(data.erro || `Erro ${r.status}`);
  return data;
}
function toast(msg, kind = "") {
  const t = $("#toast");
  t.textContent = msg; t.className = "toast " + kind;
  setTimeout(() => t.classList.add("hidden"), 3600);
}
function esc(s) {
  return String(s).replace(/[&<>"]/g, c =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

// ------------------------------------------------------------------ boot
async function boot() {
  CONFIG = await api("/api/config");
  renderOcrBadge();
  await loadPeriodos();
  await scan();
  wireEvents();
  if (CONFIG.frozen) checkUpdate(false);   // auto-checa só no .exe
}

function renderOcrBadge() {
  const b = $("#ocrBadge");
  if (CONFIG.tesseract) {
    b.className = "pill pill-ok"; b.textContent = "OCR pronto";
    b.title = CONFIG.tesseract;
  } else {
    b.className = "pill pill-bad"; b.textContent = "OCR ausente";
    b.title = "Instale o Tesseract (ver README)";
  }
}

// ------------------------------------------------------------------ atualização
async function checkUpdate(manual) {
  let info;
  try { info = await api("/api/update/check"); }
  catch (e) { if (manual) toast("Não foi possível verificar: " + e.message, "err"); return; }
  if (info.disponivel) {
    UPDATE_URL = info.url;
    $("#ubVersao").textContent = info.versao;
    $("#updateBanner").classList.remove("hidden");
    if (manual) toast("Nova versão " + info.versao + " disponível.", "ok");
  } else {
    $("#updateBanner").classList.add("hidden");
    if (manual) toast(info.erro ? ("Falha: " + info.erro)
                                : "Você já está na versão mais recente.", info.erro ? "err" : "");
  }
}

async function applyUpdate() {
  if (!confirm("Atualizar agora? O app vai fechar e reabrir sozinho na nova versão.")) return;
  try {
    await api("/api/update/apply", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: UPDATE_URL }),
    });
    document.body.innerHTML =
      '<div style="font-family:DM Sans,sans-serif;display:grid;place-items:center;height:100vh;text-align:center;color:#0A2540">'
      + '<div><div class="spin" style="border-color:#A9D7D8;border-top-color:#148A8E;width:34px;height:34px;margin:0 auto 16px"></div>'
      + '<h2>Atualizando…</h2><p style="color:#56696D">O app vai reiniciar sozinho. Aguarde alguns segundos e recarregue a página se não abrir.</p></div></div>';
  } catch (e) { toast(e.message, "err"); }
}

async function loadPeriodos() {
  const p = await api("/api/periodos");
  const ano = $("#filtroAno"), mes = $("#filtroMes");
  const curAno = ano.value, curMes = mes.value;
  ano.innerHTML = '<option value="">Todos os anos</option>' +
    p.anos.map(a => `<option ${a === curAno ? "selected" : ""}>${a}</option>`).join("");
  // meses do ano selecionado (ou todos)
  const selAno = ano.value;
  let meses = selAno ? (p.meses[selAno] || []) : [...new Set(Object.values(p.meses).flat())].sort();
  mes.innerHTML = '<option value="">Todos os meses</option>' +
    meses.map(m => `<option value="${m}" ${m === curMes ? "selected" : ""}>${mesLabel(m, p.meses_pt)}</option>`).join("");
  // popular meses do modal novo paciente
  const npMes = $("#npMes");
  npMes.innerHTML = p.meses_pt.slice(1).map((nm, i) =>
    `<option value="${String(i + 1).padStart(2, "0")}">${String(i + 1).padStart(2, "0")} — ${nm}</option>`).join("");
}
function mesLabel(m, pt) {
  const n = parseInt(m, 10);
  return (pt && pt[n]) ? `${m} — ${pt[n]}` : m;
}

// ------------------------------------------------------------------ scan
async function scan() {
  const ano = $("#filtroAno").value, mes = $("#filtroMes").value;
  const qs = new URLSearchParams();
  if (ano) qs.set("ano", ano);
  if (mes) qs.set("mes", mes);
  const data = await api("/api/scan?" + qs.toString());
  PACIENTES = data.pacientes; ERROS = data.erros;
  renderTable(); renderErros(); updateSelBar();
}

function renderTable() {
  const tb = $("#tbody"); tb.innerHTML = "";
  const lista = NOME_Q ? PACIENTES.filter(p => norm(p.paciente).includes(NOME_Q)) : PACIENTES;
  $("#tabCountPac").textContent = lista.length;
  const vazio = $("#vazio");
  vazio.classList.toggle("hidden", lista.length > 0);
  vazio.innerHTML = (PACIENTES.length && NOME_Q)
    ? `Nenhum paciente com “<b>${esc($("#filtroNome").value.trim())}</b>” neste período.`
    : "Nenhum paciente neste período. Crie um paciente em <b>+ Novo paciente</b>.";
  for (const p of lista) tb.appendChild(rowFor(p));
  $("#checkAll").checked = false;
  updateSelBar();
}

function rowFor(p) {
  const tr = document.createElement("tr");
  tr.dataset.key = p.key;
  const fracTotal = p.esperado ?? "?";
  const fracN = p.presentes.length;
  const selectable = p.status === "pronto";

  const tipoSel = `<select class="tipo-select" data-key="${esc(p.key)}">
      <option value="">— tipo —</option>
      <option value="endoscopia" ${p.tipo === "endoscopia" ? "selected" : ""}>Endoscopia (7)</option>
      <option value="colonoscopia" ${p.tipo === "colonoscopia" ? "selected" : ""}>Colonoscopia (6)</option>
    </select>`;

  const guiaCell = p.guia
    ? `<span class="guia-num"><a href="/api/pdf?path=${encodeURIComponent(p.output_pdf)}" target="_blank">${esc(p.guia)}</a></span>`
    : '<span class="muted" style="margin:0">—</span>';

  const acoes = [];
  acoes.push(`<button class="btn btn-secondary btn-sm" data-act="upload" data-key="${esc(p.key)}">Enviar PDFs</button>`);
  if (p.status === "pronto" || p.status === "erro" || p.status === "unificado") {
    const txt = p.status === "unificado" ? "Refazer" : "Unir";
    acoes.push(`<button class="btn btn-primary btn-sm" data-act="unir" data-key="${esc(p.key)}">${txt}</button>`);
  }
  if (p.status === "unificado") {
    acoes.push(`<button class="btn btn-ghost btn-sm" data-act="abrir" data-path="${esc(p.output_dir)}">Pasta</button>`);
  }
  acoes.push(`<button class="btn btn-danger-ghost btn-sm" data-act="apagar" data-key="${esc(p.key)}">Apagar</button>`);

  tr.innerHTML = `
    <td class="col-check"><input type="checkbox" class="rowchk" data-key="${esc(p.key)}" ${selectable ? "" : "disabled"} /></td>
    <td><div class="pname">${esc(p.paciente)}</div></td>
    <td class="periodo">${esc(p.mes_label || p.mes)}/${esc(p.ano)}</td>
    <td>${tipoSel}</td>
    <td><span class="docs-frac">${fracN}/${fracTotal}</span>${p.faltando.length ? `<span class="muted" style="margin:0 0 0 6px;font-size:12px">falta ${p.faltando.join(", ")}</span>` : ""}</td>
    <td><span class="badge b-${p.status}">${STATUS_LABEL[p.status] || p.status}</span></td>
    <td>${guiaCell}</td>
    <td class="col-acoes"><div class="acoes">${acoes.join("")}</div></td>`;
  return tr;
}

function renderErros() {
  const ul = $("#listaErros"); ul.innerHTML = "";
  const items = [];
  for (const p of ERROS) {
    const per = `${p.mes_label || p.mes}/${p.ano}`;
    if (p.status === "incompleto")
      items.push(["warn", p.paciente, `${per} · ${TIPO_LABEL[p.tipo] || ""} — faltam documentos: ${p.faltando.join(", ")} (tem ${p.presentes.length} de ${p.esperado}).`]);
    else if (p.status === "sem_tipo")
      items.push(["info", p.paciente, `${per} — defina o tipo de exame (Endoscopia 7 / Colonoscopia 6).`]);
    else if (p.status === "excedente")
      items.push(["warn", p.paciente, `${per} — arquivos a mais para ${TIPO_LABEL[p.tipo] || ""}: ${p.excedentes.join(", ")}. Confira o tipo/arquivos.`]);
    else if (p.status === "erro")
      items.push(["err", p.paciente, `${per} — ${p.erro || "erro ao unificar."}`]);
    for (const a of (p.avisos || []))
      items.push(["warn", p.paciente, `${per} — ${a}`]);
  }
  $("#tabCountErr").textContent = items.length;
  $("#semErros").classList.toggle("hidden", items.length > 0);
  for (const [kind, nome, det] of items) {
    const li = document.createElement("li");
    const ico = kind === "err" ? "ico-err" : kind === "warn" ? "ico-warn" : "ico-info";
    const sym = kind === "err" ? "!" : kind === "warn" ? "▲" : "i";
    li.innerHTML = `<span class="ico ${ico}">${sym}</span>
      <div class="corpo"><b>${esc(nome)}</b><div class="det">${esc(det)}</div></div>`;
    ul.appendChild(li);
  }
}

// ------------------------------------------------------------------ seleção / lote
function selectedKeys() {
  return $$(".rowchk:checked").map(c => c.dataset.key);
}
function updateSelBar() {
  const n = selectedKeys().length;
  $("#selCount").textContent = n;
  $("#btnUnirLote").disabled = n === 0;
}

// ------------------------------------------------------------------ ações
async function setTipo(key, tipo) {
  if (!tipo) return;
  await api("/api/tipo", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ key, tipo }),
  });
  await scan();
}

async function unir(keys, guiaOverride) {
  const body = keys.length === 1 && guiaOverride
    ? { key: keys[0], guia: guiaOverride }
    : { keys };
  let data;
  try {
    data = await api("/api/merge", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (e) {
    toast(e.message, "err");
    await scan();   // re-renderiza a tabela e limpa qualquer spinner travado
    return;
  }
  const res = data.resultados || [];
  const ok = res.filter(r => r.ok);
  const fail = res.filter(r => !r.ok);

  // OCR não leu o número (união individual) → pedir manual
  const ocrFail = fail.find(r => r.erro && /Nº da Guia/i.test(r.erro) && keys.length === 1);
  if (ocrFail && !guiaOverride) {
    openGuiaModal(keys[0], ocrFail.paciente);
    await scan();
    return;
  }
  if (ok.length) toast(`${ok.length} unificado(s) com sucesso.`, "ok");
  if (fail.length) toast(`${fail.length} com problema. Veja a aba Erros.`, ok.length ? "" : "err");
  if (!ok.length && !fail.length) toast("Nada para unir.");
  await scan();
}

// ------------------------------------------------------------------ modais
function openModal(id) { $("#" + id).classList.remove("hidden"); }
function closeModal(id) { $("#" + id).classList.add("hidden"); }

let uploadKey = null;
function openUploadModal(key) {
  uploadKey = key;
  $("#upPaciente").textContent = key.replaceAll("/", " · ");
  $("#upFiles").value = "";
  openModal("modalUpload");
}

let guiaKey = null;
function openGuiaModal(key, paciente) {
  guiaKey = key;
  $("#gmPaciente").textContent = paciente + "  (" + key.replaceAll("/", " · ") + ")";
  $("#gmNumero").value = "";
  openModal("modalGuia");
}

let apagarKey = null;
function openApagarModal(key) {
  apagarKey = key;
  const p = PACIENTES.find(x => x.key === key);
  const [ano, mes, nome] = key.split("/");
  const docs = p ? p.presentes.length : 0;
  const temPdf = p && p.output_pdf;
  $("#apResumo").innerHTML =
    `<div class="pnome">${esc(p ? p.paciente : nome)}</div>
     <div class="det">${esc((p && p.mes_label) || mes)}/${esc(ano)} · ${docs} documento(s)`
    + (temPdf ? " · PDF unificado existe" : "") + "</div>";
  openModal("modalApagar");
}

// ------------------------------------------------------------------ eventos
function wireEvents() {
  $("#btnEscanear").onclick = () => scan().then(() => toast("Pastas escaneadas."));
  $("#filtroAno").onchange = async () => { await loadPeriodos(); scan(); };
  $("#filtroMes").onchange = scan;

  // busca por nome (client-side, instantânea, ignora acento/maiúscula)
  $("#filtroNome").oninput = () => {
    NOME_Q = norm($("#filtroNome").value);
    $("#btnLimparBusca").classList.toggle("hidden", !$("#filtroNome").value);
    renderTable();
  };
  $("#btnLimparBusca").onclick = () => {
    $("#filtroNome").value = ""; NOME_Q = "";
    $("#btnLimparBusca").classList.add("hidden");
    renderTable(); $("#filtroNome").focus();
  };

  // delegação na tabela
  $("#tbody").addEventListener("change", e => {
    const sel = e.target.closest(".tipo-select");
    if (sel) return void setTipo(sel.dataset.key, sel.value);
    if (e.target.classList.contains("rowchk")) updateSelBar();
  });
  $("#tbody").addEventListener("click", e => {
    const btn = e.target.closest("button[data-act]");
    if (!btn) return;
    const { act, key, path } = btn.dataset;
    if (act === "unir") {
      btn.innerHTML = '<span class="spin"></span>';
      unir([key]).finally(() => {});
    } else if (act === "upload") openUploadModal(key);
    else if (act === "apagar") openApagarModal(key);
    else if (act === "abrir") api("/api/abrir", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path }),
    }).catch(err => toast(err.message, "err"));
  });

  $("#checkAll").onchange = e => {
    $$(".rowchk:not(:disabled)").forEach(c => c.checked = e.target.checked);
    updateSelBar();
  };
  $("#btnUnirLote").onclick = () => {
    const keys = selectedKeys();
    if (!keys.length) return;
    $("#btnUnirLote").disabled = true;
    $("#btnUnirLote").innerHTML = '<span class="spin"></span>Unindo…';
    unir(keys).finally(() => {
      $("#btnUnirLote").innerHTML = 'Unir selecionados <span id="selCount" class="count">0</span>';
    });
  };

  // tabs
  $$(".tab").forEach(t => t.onclick = () => {
    $$(".tab").forEach(x => x.classList.remove("is-active"));
    t.classList.add("is-active");
    $("#tabPacientes").classList.toggle("is-active", t.dataset.tab === "pacientes");
    $("#tabErros").classList.toggle("is-active", t.dataset.tab === "erros");
  });

  // modal close
  $$("[data-close]").forEach(b => b.onclick = () => b.closest(".modal").classList.add("hidden"));
  $$(".modal").forEach(m => m.addEventListener("click", e => { if (e.target === m) m.classList.add("hidden"); }));

  // novo paciente
  $("#btnNovo").onclick = () => {
    $("#npAno").value = new Date().getFullYear();
    $("#npNome").value = ""; $("#npTipo").value = ""; $("#npFiles").value = "";
    $("#npStatus").className = "np-status hidden"; $("#npStatus").textContent = "";
    openModal("modalNovo");
  };
  $("#npSalvar").onclick = novoPaciente;
  $("#npFiles").onchange = lerGuiaAuto;   // lê o doc 1 e pré-preenche

  // upload
  $("#upEnviar").onclick = enviarUpload;

  // apagar paciente (confirmação)
  $("#apConfirmar").onclick = async () => {
    if (!apagarKey) return;
    try {
      await api("/api/paciente/apagar", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ key: apagarKey }),
      });
      closeModal("modalApagar");
      await loadPeriodos(); await scan();
      toast("Paciente apagado.", "ok");
    } catch (e) { toast(e.message, "err"); }
  };

  // guia manual
  $("#gmUnir").onclick = () => {
    const num = $("#gmNumero").value.replace(/\D/g, "");
    if (!num) return toast("Digite o número da guia.", "err");
    closeModal("modalGuia");
    unir([guiaKey], num);
  };

  // atualização
  $("#ubAtualizar").onclick = applyUpdate;
  $("#ubDepois").onclick = () => $("#updateBanner").classList.add("hidden");
  $("#cfgBuscarUpd").onclick = () => checkUpdate(true);

  // config
  $("#btnConfig").onclick = () => {
    $("#cfgBase").value = CONFIG.base || "";
    $("#cfgTess").value = CONFIG.tesseract || "Não encontrado";
    $("#cfgVersao").value = "v" + (CONFIG.version || "?") + (CONFIG.frozen ? "" : "  (modo dev — sem auto-update)");
    openModal("modalConfig");
  };
  $("#cfgSalvar").onclick = async () => {
    try {
      await api("/api/config", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ base: $("#cfgBase").value }),
      });
      CONFIG = await api("/api/config");
      closeModal("modalConfig");
      await loadPeriodos(); await scan();
      toast("Pasta base atualizada.", "ok");
    } catch (e) { toast(e.message, "err"); }
  };
}

function docLeadingInt(name) {
  const m = (name || "").match(/^\s*0*(\d+)/);
  return m ? parseInt(m[1], 10) : null;
}

// Lê o documento 1 selecionado e pré-preenche nome, data(→ano/mês) e tipo.
async function lerGuiaAuto() {
  const files = [...$("#npFiles").files];
  if (!files.length) return;
  const doc1 = files.find(f => docLeadingInt(f.name) === 1)
    || files.slice().sort((a, b) => (docLeadingInt(a.name) ?? 99) - (docLeadingInt(b.name) ?? 99))[0];
  const st = $("#npStatus");
  st.className = "np-status lendo"; st.textContent = "Lendo dados do documento 1…";
  try {
    const fd = new FormData(); fd.append("file", doc1);
    const r = await api("/api/extrair", { method: "POST", body: fd });
    const c = r.campos || {};
    if (c.nome) $("#npNome").value = c.nome;
    if (c.ano) $("#npAno").value = c.ano;
    if (c.mes && [...$("#npMes").options].some(o => o.value === c.mes)) $("#npMes").value = c.mes;
    if (c.tipo) $("#npTipo").value = c.tipo;
    const ok = [];
    if (c.nome) ok.push(c.nome);
    if (c.data) ok.push(c.data);
    if (c.tipo) ok.push(TIPO_LABEL[c.tipo] || c.tipo);
    const completo = c.nome && c.data && c.tipo;
    if (ok.length) {
      st.className = "np-status";
      st.textContent = "✓ Lido da guia: " + ok.join(" · ") + (completo ? "" : "  — confira os campos em branco.");
    } else {
      st.className = "np-status falha";
      st.textContent = "Não consegui ler os dados — preencha manualmente.";
    }
  } catch (e) {
    st.className = "np-status falha";
    st.textContent = "Falha ao ler a guia: " + e.message + " — preencha manualmente.";
  }
}

async function novoPaciente() {
  const ano = $("#npAno").value.trim();
  const mes = $("#npMes").value;
  const paciente = $("#npNome").value.trim();
  const tipo = $("#npTipo").value;
  if (!ano || !mes || !paciente) return toast("Preencha ano, mês e nome.", "err");
  try {
    const r = await api("/api/paciente", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ano, mes, paciente, tipo }),
    });
    const files = $("#npFiles").files;
    if (files.length) await uploadFiles(r.paciente.key, files);
    closeModal("modalNovo");
    await loadPeriodos(); await scan();
    toast("Paciente criado.", "ok");
  } catch (e) { toast(e.message, "err"); }
}

async function uploadFiles(key, files) {
  const fd = new FormData();
  fd.append("key", key);
  for (const f of files) fd.append("files", f);
  return api("/api/upload", { method: "POST", body: fd });
}

async function enviarUpload() {
  const files = $("#upFiles").files;
  if (!files.length) return toast("Selecione ao menos um PDF.", "err");
  try {
    await uploadFiles(uploadKey, files);
    closeModal("modalUpload");
    await scan();
    toast("Documentos enviados.", "ok");
  } catch (e) { toast(e.message, "err"); }
}

boot().catch(e => toast("Falha ao iniciar: " + e.message, "err"));
