// Front do Song Tonality Helper: envia o link, acompanha a análise, lista o histórico e desenha o relatório.
// Todo dado vindo da API entra na página por textContent, nunca por innerHTML.

const CEILING_KEY = "ceilingMidi";
const PASSPHRASE_KEY = "passphrase";
const PASSPHRASE_HEADER = "X-App-Passphrase";
const POLL_MS = 2000;
const HISTORY_POLL_MS = 10000;
const HISTORY_MAX_FAILURES = 3;
const CONFIRM_MS = 4000;
const FETCH_ATTEMPTS = 3;
const SLOW_MS = 5 * 60 * 1000;
const EXTRACT_KEY = "extractNow";
const SLOW_TEXT = "Está demorando: o worker pode estar desligado.";
const EXTRACT_LABEL = {
  true: "Extrair agora (até 60 s; se não der, vai para o worker)",
  false: "Enviar para o worker",
};
const STATUS_TEXT = {
  pending: "Na fila, aguardando o worker...",
  downloading: "Baixando o áudio do vídeo...",
  analyzing: "Analisando a melodia e o tom...",
};

const form = document.getElementById("form");
const urlInput = document.getElementById("url");
const ceilingSelect = document.getElementById("ceiling");
const extractNow = document.getElementById("extract-now");
const extractNowText = document.getElementById("extract-now-text");
const submit = document.getElementById("submit");
const statusBox = document.getElementById("status");
const errorBox = document.getElementById("error");
const reportBox = document.getElementById("report");
const noticeBox = document.getElementById("notice");
const historyList = document.getElementById("history-list");
const historyRefresh = document.getElementById("history-refresh");
const appBox = document.getElementById("app");
const gate = document.getElementById("gate");
const gateForm = document.getElementById("gate-form");
const gateInput = document.getElementById("gate-input");
const gateMessage = document.getElementById("gate-message");

let currentVideoId = null;
let activeRun = 0; // cada ação do usuário abre uma execução nova; as anteriores desistem de atualizar a tela

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

function readSavedExtractNow() {
  try {
    return localStorage.getItem(EXTRACT_KEY) === "true";
  } catch {
    return false;
  }
}

function saveExtractNow(value) {
  try {
    localStorage.setItem(EXTRACT_KEY, String(value));
  } catch {
    // Sem armazenamento: a escolha só vale nesta visita.
  }
}

// O texto do switch acompanha o estado marcado.
function showExtractLabel() {
  extractNowText.textContent = EXTRACT_LABEL[extractNow.checked];
}

function readSavedPassphrase() {
  try {
    return localStorage.getItem(PASSPHRASE_KEY) ?? "";
  } catch {
    return "";
  }
}

function savePassphrase(value) {
  try {
    if (value) localStorage.setItem(PASSPHRASE_KEY, value);
    else localStorage.removeItem(PASSPHRASE_KEY);
  } catch {
    // Sem armazenamento: a palavra só vale até fechar a página.
  }
}

let passphrase = readSavedPassphrase();
let passphraseAsk = null; // pedido de palavra em andamento, compartilhado pelas chamadas simultâneas

// Mostra a tela só com o campo da palavra secreta e devolve o que a pessoa digitar.
function askPassphrase(message) {
  if (passphraseAsk) return passphraseAsk;
  passphraseAsk = new Promise((resolve) => {
    lock();
    gateMessage.textContent = message;
    gateInput.value = "";
    gateInput.focus();
    gateForm.addEventListener(
      "submit",
      (event) => {
        event.preventDefault();
        passphraseAsk = null;
        resolve(gateInput.value);
      },
      { once: true },
    );
  });
  return passphraseAsk;
}

// Esconde o app (hidden + inert: fora do foco e dos leitores de tela) e mostra só a palavra secreta.
function lock() {
  appBox.hidden = true;
  appBox.inert = true;
  gate.hidden = false;
  document.body.classList.add("locked");
}

// Primeira chamada aceita: revela o app e some com a tela da palavra.
function unlock() {
  if (!appBox.hidden) return;
  gate.hidden = true;
  appBox.hidden = false;
  appBox.inert = false;
  document.body.classList.remove("locked");
}

// fetch da API: manda a palavra secreta guardada e, se a API recusar (401), pede de novo e reenvia.
async function api(url, options = {}) {
  for (;;) {
    const sent = passphrase;
    const headers = { ...options.headers };
    if (passphrase) headers[PASSPHRASE_HEADER] = passphrase;
    let response;
    try {
      response = await fetch(url, { ...options, headers });
    } catch (error) {
      unlock(); // sem rede: mostra o app com o erro, nunca uma tela vazia
      throw error;
    }
    if (response.status !== 401) {
      unlock(); // qualquer resposta que não seja 401 mostra o app (erros aparecem nos avisos)
      return response;
    }
    if (passphrase !== sent) continue; // outra chamada já trocou a palavra: só reenvia
    const message = passphrase ? "Palavra secreta recusada. Digite de novo:" : "Digite a palavra secreta:";
    passphrase = "";
    savePassphrase("");
    passphrase = await askPassphrase(message);
    savePassphrase(passphrase);
  }
}

function el(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function noteText(note) {
  return note.name;
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
  const response = await api("/api/ceilings");
  if (!response.ok) throw new Error("ceilings");
  const data = await response.json();
  const saved = Number(readSavedCeiling());
  const wanted = data.options.some((o) => o.midi === saved) ? saved : data.default_midi;
  for (const option of data.options) {
    const node = el("option", option.name);
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

function noteBox(label, note, className) {
  const box = el("div", undefined, className ? `note ${className}` : "note");
  box.append(el("span", label), el("b", note.name));
  return box;
}

function fact(value, label) {
  const box = el("div", undefined, "fact");
  box.append(el("b", value), el("span", label));
  return box;
}

function renderReport(r, title) {
  reportBox.replaceChildren();

  const shift = el("div", undefined, "shift");
  shift.append(el("span", `${signed(r.shift)} semitons`, "shift-value"), el("span", `Novo tom: ${r.new_key}`, "new-key"));
  const pair = el("div", undefined, "pair");
  pair.append(noteBox("Nota mais aguda hoje", r.top_note), el("span", "→", "arrow"), noteBox("Depois de transpor", r.new_top_note, "to"));
  const result = card(
    el("div", "Resultado", "eyebrow"),
    el("h2", title, "song"),
    shift,
    pair,
    el("p", `Alternativa: ${signed(r.alternative_shift)} semitons. Seu teto: ${noteText(r.ceiling)}.`, "muted"),
  );
  result.classList.add("result");

  const best = r.keys[0];
  const others = r.keys.slice(1).map((k) => `${k.tonic} ${k.mode}`).join(" ou ");
  const facts = el("div", undefined, "facts");
  facts.append(
    fact(`${best.tonic} ${best.mode}`, "Tom detectado"),
    fact(r.scale_degree, "Grau da nota mais aguda"),
  );
  const keyCard = card(facts, el("p", `Outros candidatos: ${others}.`, "muted"));

  const chips = el("div", undefined, "chips");
  for (const t of r.top_times) chips.append(el("span", clock(t), "chip"));
  const times = card(
    el("h2", "Onde a nota mais aguda aparece"),
    r.top_times.length ? chips : el("p", "Sem trechos marcados.", "muted"),
  );

  const bars = el("div", undefined, "bars");
  const max = Math.max(...r.ranking.map((row) => row.frames), 1);
  r.ranking.forEach((row, index) => {
    const fill = el("div", undefined, "bar-fill");
    fill.style.width = `${(row.frames / max) * 100}%`;
    const track = el("div", undefined, "bar-track");
    track.append(fill);
    const line = el("div", undefined, index === 0 ? "bar-row peak" : "bar-row");
    line.append(el("span", noteText(row.note)), track, el("span", String(row.frames), "count"));
    bars.append(line);
  });
  const ranking = card(el("h2", "Ranking das notas mais agudas"), bars);

  const warning = el(
    "p",
    "O método não separa a voz dos instrumentos. Acordeão e segundas vozes podem aparecer como notas altas, então confira o ranking. O tom detectado é estatístico e pode errar em músicas com modulação.",
    "warning",
  );

  reportBox.append(result, keyCard, times, ranking, warning);
  reportBox.hidden = false;
}

function dateText(iso) {
  return new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// Falha de rede passageira não derruba o acompanhamento: tenta de novo algumas vezes.
async function fetchWithRetry(url) {
  for (let attempt = 1; ; attempt++) {
    try {
      return await api(url);
    } catch (error) {
      if (attempt === FETCH_ATTEMPTS) throw error;
      await wait(POLL_MS);
    }
  }
}

// Busca o relatório do vídeo para o teto atual; espera enquanto a análise roda.
// Devolve null se outra ação do usuário assumiu a tela no meio do caminho.
async function loadReport(videoId, run = ++activeRun, started = Date.now()) {
  const ceiling = Number(ceilingSelect.value);
  const response = await fetchWithRetry(`/api/analyses/${videoId}?ceiling_midi=${ceiling}`);
  if (run !== activeRun) return null;
  if (!response.ok) throw new Error("Análise não encontrada.");
  const analysis = await response.json();
  if (run !== activeRun) return null;
  if (analysis.status === "done") {
    statusBox.hidden = true;
    currentVideoId = videoId;
    renderReport(analysis.report, analysis.title);
    markSelected();
    refreshHistory(); // o worker pode ter acabado de gravar esta música: a lista pega na hora
    return;
  }
  if (analysis.status === "error") {
    showError(analysis.error);
    return;
  }
  const slow = Date.now() - started > SLOW_MS;
  statusBox.textContent = slow ? `${STATUS_TEXT[analysis.status]} ${SLOW_TEXT}` : STATUS_TEXT[analysis.status];
  statusBox.hidden = false;
  await wait(POLL_MS);
  return loadReport(videoId, run, started);
}

let historyKey = null; // ids e títulos da lista desenhada; só redesenha quando muda
let historyBusy = false;
let historyFailures = 0;

// Destaca na lista a música aberta no relatório.
function markSelected() {
  for (const button of historyList.querySelectorAll("li > button:first-child")) {
    button.classList.toggle("selected", button.dataset.videoId === currentVideoId);
  }
}

function renderHistory(items) {
  const key = JSON.stringify(items.map((item) => [item.video_id, item.title]));
  if (key === historyKey) return;
  historyKey = key;
  const scroll = historyList.scrollTop;
  historyList.replaceChildren();
  if (items.length === 0) {
    historyList.append(el("li", "Nenhuma música analisada ainda.", "muted"));
    return;
  }
  for (const item of items) {
    const button = el("button");
    button.type = "button";
    button.dataset.videoId = item.video_id;
    button.append(
      el("div", item.title, "title"),
      el("div", `${clock(item.duration_seconds)} · nota mais aguda ${noteText(item.top_note)} · ${dateText(item.created_at)}`, "meta"),
    );
    button.addEventListener("click", () => openFromHistory(item.video_id));
    const li = el("li");
    li.append(button, deleteButton(item));
    historyList.append(li);
  }
  markSelected();
  historyList.scrollTop = scroll;
}

// Busca a lista sem sobrepor chamadas. Erro 429/401 repetido (ou de rede) suspende o polling automático.
async function refreshHistory({ manual = false } = {}) {
  if (manual) historyFailures = 0;
  if (historyBusy) return;
  historyBusy = true;
  try {
    const response = await api("/api/analyses");
    if (!response.ok) throw new Error(String(response.status));
    renderHistory(await response.json());
    historyFailures = 0;
  } catch (error) {
    historyFailures++;
    if (manual) showError("Não consegui carregar a lista de músicas.");
  } finally {
    historyBusy = false;
  }
}

function pollHistory() {
  if (document.visibilityState !== "visible" || appBox.hidden) return;
  if (historyFailures >= HISTORY_MAX_FAILURES) return;
  refreshHistory();
}

// Dois cliques para apagar: o primeiro pede confirmação e desiste sozinho depois de alguns segundos.
function deleteButton(item) {
  const button = el("button", "Apagar", "delete");
  button.type = "button";
  button.setAttribute("aria-label", `Apagar ${item.title}`);
  let timer = null;
  button.addEventListener("click", async () => {
    if (timer === null) {
      button.textContent = "Confirmar?";
      timer = setTimeout(() => {
        button.textContent = "Apagar";
        timer = null;
      }, CONFIRM_MS);
      return;
    }
    clearTimeout(timer);
    await deleteAnalysis(item.video_id);
  });
  return button;
}

async function deleteAnalysis(videoId) {
  errorBox.hidden = true;
  try {
    const response = await api(`/api/analyses/${videoId}`, { method: "DELETE" });
    if (!response.ok && response.status !== 404) {
      const body = await response.json().catch(() => ({}));
      throw new Error(typeof body.detail === "string" ? body.detail : "Não consegui apagar.");
    }
    if (videoId === currentVideoId) {
      activeRun++;
      currentVideoId = null;
      reportBox.hidden = true;
      noticeBox.hidden = true;
    }
    await refreshHistory();
  } catch (error) {
    showError(error.message);
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
  activeRun++; // interrompe o acompanhamento de qualquer música anterior
  errorBox.hidden = true;
  noticeBox.hidden = true;
  reportBox.hidden = true;
  submit.disabled = true;
  statusBox.textContent = "Enviando...";
  statusBox.hidden = false;
  try {
    const response = await api("/api/analyses", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: urlInput.value, extract_now: extractNow.checked }),
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
    await refreshHistory();
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

extractNow.checked = readSavedExtractNow();
showExtractLabel();
extractNow.addEventListener("change", () => {
  saveExtractNow(extractNow.checked);
  showExtractLabel();
});
ceilingSelect.addEventListener("change", onCeilingChange);
form.addEventListener("submit", analyze);
loadCeilings().catch(() => showError("Não consegui carregar a lista de tetos."));
refreshHistory({ manual: true });
historyRefresh.addEventListener("click", () => refreshHistory({ manual: true }));
setInterval(pollHistory, HISTORY_POLL_MS);
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible" && !appBox.hidden) refreshHistory({ manual: true });
});
