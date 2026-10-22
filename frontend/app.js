// Front do Song Tonality Helper: envia o link, acompanha a análise, lista o histórico e desenha o relatório.
// Todo dado vindo da API entra na página por textContent, nunca por innerHTML.

const CEILING_KEY = "ceilingMidi";
const POLL_MS = 2000;
const STATUS_TEXT = {
  downloading: "Baixando o áudio do vídeo...",
  analyzing: "Analisando a melodia e o tom...",
};

const form = document.getElementById("form");
const urlInput = document.getElementById("url");
const ceilingSelect = document.getElementById("ceiling");
const submit = document.getElementById("submit");
const statusBox = document.getElementById("status");
const errorBox = document.getElementById("error");
const reportBox = document.getElementById("report");
const noticeBox = document.getElementById("notice");
const historyList = document.getElementById("history-list");

let currentVideoId = null;

function readSavedCeiling() {
  try {
    return localStorage.getItem(CEILING_KEY);
  } catch {
    return null;
  }
}

function saveCeiling(midi) {
  try {
    localStorage.setItem(CEILING_KEY, midi);
  } catch {
    // Sem armazenamento: a escolha só vale nesta visita.
  }
}

function el(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function noteText(note) {
  return `${note.user} (padrão: ${note.standard})`;
}

function clock(seconds) {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

function signed(n) {
  return n > 0 ? `+${n}` : String(n);
}

async function loadCeilings() {
  const response = await fetch("/api/ceilings");
  const data = await response.json();
  const saved = Number(readSavedCeiling());
  const wanted = data.options.some((o) => o.midi === saved) ? saved : data.default_midi;
  for (const option of data.options) {
    const node = el("option", `${option.user} (padrão: ${option.standard})`);
    node.value = option.midi;
    node.selected = option.midi === wanted;
    ceilingSelect.append(node);
  }
}

function showError(message) {
  errorBox.textContent = message;
  errorBox.hidden = false;
  statusBox.hidden = true;
}

function card(...children) {
  const node = el("div", undefined, "card");
  node.append(...children);
  return node;
}

function renderReport(r, title) {
  reportBox.replaceChildren();
  const heading = el("h2", title);

  const main = card(
    el("div", `Nota mais aguda: ${noteText(r.top_note)}`, "big"),
    el("p", `Grau dessa nota no tom detectado: ${r.scale_degree}.`),
    el("p", `Seu teto: ${noteText(r.ceiling)}`, "muted"),
  );

  const best = r.keys[0];
  const others = r.keys.slice(1).map((k) => `${k.tonic} ${k.mode}`).join(" ou ");
  const keyCard = card(
    el("div", `Tom detectado: ${best.tonic} ${best.mode}`, "big"),
    el("p", `Outros candidatos: ${others}.`, "muted"),
  );

  const result = card(
    el("div", `Novo tom: ${r.new_key}`, "big"),
    el("p", `Deslocamento: ${signed(r.shift)} semitons (alternativa: ${signed(r.alternative_shift)}).`),
    el("p", `A nota mais aguda passa a ser ${noteText(r.new_top_note)}.`),
  );

  const times = card(
    el("h2", "Onde a nota mais aguda aparece"),
    el("p", r.top_times.length ? r.top_times.map(clock).join(" · ") : "Sem trechos marcados."),
  );

  const table = el("table");
  const head = el("tr");
  head.append(el("th", "Nota"), el("th", "Quadros"));
  table.append(head);
  for (const row of r.ranking) {
    const tr = el("tr");
    tr.append(el("td", noteText(row.note)), el("td", String(row.frames)));
    table.append(tr);
  }
  const ranking = card(el("h2", "Ranking das notas mais agudas"), table);

  const warning = el(
    "p",
    "Aviso: o método não separa a voz dos instrumentos. Acordeão e segundas vozes podem aparecer como notas altas, então confira o ranking. O tom detectado é estatístico e pode errar em músicas com modulação.",
    "muted",
  );

  reportBox.append(heading, main, keyCard, result, times, ranking, warning);
  reportBox.hidden = false;
}

function dateText(iso) {
  return new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

// Busca o relatório do vídeo para o teto atual; espera enquanto a análise roda.
async function loadReport(videoId) {
  const ceiling = Number(ceilingSelect.value);
  const response = await fetch(`/api/analyses/${videoId}?ceiling_midi=${ceiling}`);
  if (!response.ok) throw new Error("Análise não encontrada.");
  const analysis = await response.json();
  if (analysis.status === "done") {
    statusBox.hidden = true;
    currentVideoId = videoId;
    renderReport(analysis.report, analysis.title);
    return;
  }
  if (analysis.status === "error") {
    showError(analysis.error);
    return;
  }
  statusBox.textContent = STATUS_TEXT[analysis.status];
  statusBox.hidden = false;
  await new Promise((resolve) => setTimeout(resolve, POLL_MS));
  await loadReport(videoId);
}

async function loadHistory() {
  const response = await fetch("/api/analyses");
  const items = await response.json();
  historyList.replaceChildren();
  if (items.length === 0) {
    historyList.append(el("li", "Nenhuma música analisada ainda.", "muted"));
    return;
  }
  for (const item of items) {
    const button = el("button");
    button.type = "button";
    button.append(
      el("div", item.title, "title"),
      el("div", `${clock(item.duration_seconds)} · nota mais aguda ${noteText(item.top_note)} · ${dateText(item.created_at)}`, "muted"),
    );
    button.addEventListener("click", () => openFromHistory(item.video_id));
    const li = el("li");
    li.append(button);
    historyList.append(li);
  }
}

async function openFromHistory(videoId) {
  errorBox.hidden = true;
  noticeBox.hidden = true;
  try {
    await loadReport(videoId);
  } catch (error) {
    showError(error.message);
  }
}

async function analyze(event) {
  event.preventDefault();
  errorBox.hidden = true;
  noticeBox.hidden = true;
  reportBox.hidden = true;
  submit.disabled = true;
  statusBox.textContent = "Enviando...";
  statusBox.hidden = false;
  try {
    const response = await fetch("/api/analyses", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: urlInput.value }),
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(typeof body.detail === "string" ? body.detail : "Pedido inválido.");
    }
    const created = await response.json();
    if (created.already_analyzed) {
      noticeBox.textContent = `Você já analisou esta música em ${dateText(created.analyzed_at)}.`;
      noticeBox.hidden = false;
    }
    await loadReport(created.video_id);
    await loadHistory();
  } catch (error) {
    showError(error.message);
  } finally {
    submit.disabled = false;
  }
}

function onCeilingChange() {
  saveCeiling(ceilingSelect.value);
  if (currentVideoId && !reportBox.hidden) {
    loadReport(currentVideoId).catch((error) => showError(error.message));
  }
}

ceilingSelect.addEventListener("change", onCeilingChange);
form.addEventListener("submit", analyze);
loadCeilings().catch(() => showError("Não consegui carregar a lista de tetos."));
loadHistory().catch(() => showError("Não consegui carregar a lista de músicas."));
