// Front do Tonalidade: envia o link, acompanha a análise, lista o histórico e desenha o relatório.
// Todo dado vindo da API entra na página por textContent, nunca por innerHTML.

const POLL_MS = 2000;
const HISTORY_POLL_MS = 10000;
const HISTORY_MAX_FAILURES = 3;
const CONFIRM_MS = 4000;
const FETCH_ATTEMPTS = 3;
const SLOW_MS = 5 * 60 * 1000;
const EXTRACT_KEY = "extractNow";
const BACKGROUND_TEXT = "Pedido recebido: a música está sendo processada em segundo plano. Quando ficar pronta, ela aparece na lista de músicas analisadas.";
const SLOW_TEXT = "Está demorando: o worker pode estar desligado.";
const EXTRACT_LABEL = {
  true: "Extrair agora (até 60 s; se não der, vai para o worker)",
  false: "Enviar para o worker (processa em segundo plano)",
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
const jobsBox = document.getElementById("jobs");
const jobsList = document.getElementById("jobs-list");
const historyRefresh = document.getElementById("history-refresh");
const appBox = document.getElementById("app");
const authBox = document.getElementById("auth");
const authForm = document.getElementById("auth-form");
const authTabs = document.getElementById("auth-tabs");
const authTitle = document.getElementById("auth-title");
const authName = document.getElementById("auth-name");
const authEmail = document.getElementById("auth-email");
const authPassword = document.getElementById("auth-password");
const authConfirm = document.getElementById("auth-confirm");
const authMessage = document.getElementById("auth-message");
const authSubmit = document.getElementById("auth-submit");
const authLink = document.getElementById("auth-link");
const userName = document.getElementById("user-name");
const togglePassword = document.getElementById("toggle-password");
const logoutButton = document.getElementById("logout");

let currentVideoId = null;
let activeRun = 0; // cada ação do usuário abre uma execução nova; as anteriores desistem de atualizar a tela

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

// Telas da conta: cada modo mostra só os campos que usa (data-modes) e o texto do botão.
const AUTH_MODES = {
  login: { title: "Entre com a sua conta.", submit: "Entrar", link: "Esqueci a senha", other: "forgot" },
  register: { title: "Crie uma conta para guardar as suas músicas e o seu tom teto.", submit: "Criar conta", link: "", other: "" },
  forgot: { title: "Informe o e-mail da conta e enviaremos um link para criar uma nova senha.", submit: "Enviar link", link: "Voltar", other: "login" },
  reset: { title: "Escolha a nova senha.", submit: "Salvar senha", link: "", other: "" },
  verify: { title: "Confirmando o e-mail...", submit: "Entrar", link: "", other: "" },
};
let authMode = "login";
let authToken = ""; // token de ?verificar= ou ?redefinir=, só em memória

// Mensagem de erro da API: `detail` vem como texto, ou como lista nos 422.
function errorText(body, fallback) {
  if (typeof body.detail === "string") return body.detail;
  if (Array.isArray(body.detail) && body.detail.length > 0) return "Confira os dados informados.";
  return fallback;
}

function showAuthMessage(text, ok = false) {
  authMessage.textContent = text;
  authMessage.className = ok ? "banner notice" : "banner error";
  authMessage.hidden = text === "";
}

function setAuthMode(mode) {
  authMode = mode;
  const config = AUTH_MODES[mode];
  authTitle.textContent = config.title;
  authSubmit.textContent = config.submit;
  authSubmit.hidden = mode === "verify";
  authLink.textContent = config.link;
  authLink.hidden = config.link === "";
  for (const label of authForm.querySelectorAll("[data-modes]")) {
    label.hidden = !label.dataset.modes.split(" ").includes(mode);
  }
  authTabs.hidden = mode === "forgot" || mode === "reset" || mode === "verify";
  for (const tab of authTabs.querySelectorAll("button")) {
    tab.setAttribute("aria-selected", String(tab.dataset.mode === mode));
  }
  authPassword.autocomplete = mode === "login" ? "current-password" : "new-password";
  showAuthMessage("");
}

// Esconde o app (hidden + inert: fora do foco e dos leitores de tela) e mostra a tela de entrada.
function showAuth(mode = "login") {
  appBox.hidden = true;
  appBox.inert = true;
  authBox.hidden = false;
  document.body.classList.add("locked");
  userName.textContent = "";
  authPassword.value = "";
  authConfirm.value = "";
  setAuthMode(mode);
}

// Sessão válida: revela o app e some com a tela de entrada.
function showApp(user) {
  userName.textContent = user.name;
  if (!appBox.hidden) return;
  authBox.hidden = true;
  appBox.hidden = false;
  appBox.inert = false;
  document.body.classList.remove("locked");
}

// Limpa o que a sessão anterior deixou na tela (outra pessoa pode entrar em seguida).
function resetScreen() {
  activeRun++;
  currentVideoId = null;
  historyKey = null;
  jobsKey = null;
  historyFailures = 0;
  reportBox.hidden = true;
  noticeBox.hidden = true;
  statusBox.hidden = true;
  errorBox.hidden = true;
  jobsBox.hidden = true;
  historyList.replaceChildren();
  jobsList.replaceChildren();
  ceilingSelect.replaceChildren();
  urlInput.value = "";
}

// fetch da API: um 401 (sessão ausente ou vencida) devolve a pessoa para a tela de entrada.
async function api(url, options = {}) {
  const response = await fetch(url, options);
  if (response.status === 401 && !appBox.hidden) {
    resetScreen();
    showAuth("login");
    showAuthMessage("Sua sessão acabou. Entre de novo.");
  }
  return response;
}

async function authRequest(path, payload) {
  return fetch(`/api/auth/${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

async function submitAuth(event) {
  event.preventDefault();
  const email = authEmail.value.trim();
  const needsConfirm = authMode === "register" || authMode === "reset";
  if (needsConfirm && authPassword.value !== authConfirm.value) {
    showAuthMessage("As senhas não são iguais.");
    return;
  }
  authSubmit.disabled = true;
  try {
    let response;
    if (authMode === "login") {
      response = await authRequest("login", { email, password: authPassword.value });
    } else if (authMode === "register") {
      response = await authRequest("register", { name: authName.value.trim(), email, password: authPassword.value });
    } else if (authMode === "forgot") {
      response = await authRequest("forgot-password", { email });
    } else {
      response = await authRequest("reset-password", { token: authToken, password: authPassword.value });
    }
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      showAuthMessage(errorText(body, "Não foi possível concluir. Tente de novo."));
      return;
    }
    if (authMode === "register") {
      // o cadastro não abre sessão: entra em seguida com os mesmos dados
      response = await authRequest("login", { email, password: authPassword.value });
      if (!response.ok) {
        setAuthMode("login");
        showAuthMessage("Conta criada. Entre com o e-mail e a senha.", true);
        return;
      }
    }
    if (authMode === "forgot") {
      showAuthMessage("Se o e-mail tiver conta, o link já está a caminho.", true);
    } else if (authMode === "reset") {
      authToken = "";
      setAuthMode("login");
      showAuthMessage("Senha trocada. Entre com a nova senha.", true);
    } else {
      // login (ou cadastro seguido de login): o cookie de sessão já foi gravado, então busca o usuário e abre o app
      await start();
    }
  } catch {
    showAuthMessage("Sem conexão com o servidor.");
  } finally {
    authSubmit.disabled = false;
  }
}

async function logout() {
  await fetch("/api/auth/logout", { method: "POST" }).catch(() => {});
  resetScreen();
  showAuth("login");
}

// Monta o seletor de teto e marca o que está salvo no servidor.
async function loadCeilings() {
  const [options, settings] = await Promise.all([api("/api/ceilings"), api("/api/me/settings")]);
  if (!options.ok || !settings.ok) throw new Error("ceilings");
  const data = await options.json();
  const saved = (await settings.json()).ceiling_midi;
  ceilingSelect.replaceChildren();
  for (const option of data.options) {
    const node = el("option", option.name);
    node.value = option.midi;
    node.selected = option.midi === saved;
    ceilingSelect.append(node);
  }
}

// Abre o app se já há sessão; senão mostra a tela de entrada.
async function start() {
  let response;
  try {
    response = await fetch("/api/auth/me");
  } catch {
    showAuth("login");
    showAuthMessage("Sem conexão com o servidor.");
    return;
  }
  if (!response.ok) {
    showAuth("login");
    return;
  }
  resetScreen();
  showApp(await response.json());
  loadCeilings().catch(() => showError("Não consegui carregar a lista de tetos."));
  refreshHistory({ manual: true });
}

// Links do e-mail: ?verificar=<token> confirma o endereço, ?redefinir=<token> abre a nova senha.
async function openEmailLink() {
  const params = new URLSearchParams(location.search);
  const verify = params.get("verificar");
  const reset = params.get("redefinir");
  if (!verify && !reset) return false;
  history.replaceState(null, "", location.pathname); // o token não fica na barra de endereço
  if (reset) {
    authToken = reset;
    showAuth("reset");
    return true;
  }
  showAuth("verify");
  try {
    const response = await authRequest("verify-email", { token: verify });
    if (response.ok) showAuthMessage("E-mail confirmado. Agora é só entrar.", true);
    else showAuthMessage("Link inválido ou vencido.");
  } catch {
    showAuthMessage("Sem conexão com o servidor.");
  }
  authTitle.textContent = "";
  authSubmit.hidden = false;
  authLink.hidden = false;
  authLink.textContent = "Ir para a entrada";
  return true;
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
  const modulates = r.sections.length > 1;
  shift.append(el("span", `${signed(r.shift)} semitons`, "shift-value"));
  const first = r.sections[0];
  const keys = el("div", undefined, "pair");
  keys.append(
    noteBox(modulates ? "Tom no início" : "Tom detectado", { name: `${first.tonic} ${first.mode}` }),
    el("span", "→", "arrow"),
    noteBox(modulates ? "Novo tom (no início)" : "Novo tom", { name: r.new_key }, "to"),
  );
  const pair = el("div", undefined, "pair");
  pair.append(noteBox("Nota mais aguda hoje", r.top_note), el("span", "→", "arrow"), noteBox("Depois de transpor", r.new_top_note, "to"));
  const result = card(
    el("div", "Resultado", "eyebrow"),
    el("h2", title, "song"),
    shift,
    keys,
    pair,
    el("p", `Alternativa: ${signed(r.alternative_shift)} semitons. Seu teto: ${noteText(r.ceiling)}.`, "muted"),
  );
  result.classList.add("result");

  const chips = el("div", undefined, "chips");
  r.top_times.forEach((t, i) => {
    const chord = r.top_chords[i];
    chips.append(el("span", chord ? `${clock(t)} · ${chord.original} → ${chord.new}` : clock(t), "chip"));
  });
  const peak = card(
    fact(r.scale_degree, "Grau da nota mais aguda"),
    el("h2", "Onde a nota mais aguda aparece"),
    r.top_times.length ? chips : el("p", "Sem trechos marcados.", "muted"),
  );
  peak.classList.add("result"); // mesmo espaçamento em grade do cartão de resultado
  if (r.top_chords.some((c) => c)) {
    peak.append(el("p", "Acorde provável, estimado do áudio (tom original → novo tom): só maiores e menores, e pode confundir relativos ou acordes com sétima.", "muted"));
  }
  if (first.relative) {
    peak.append(el("p", `Também pode ser ${first.relative}: o relativo usa as mesmas notas e o áudio não separa os dois com certeza.`, "muted"));
  }
  if (modulates) {
    const sectionChips = el("div", undefined, "chips");
    for (const k of r.sections) {
      sectionChips.append(el("span", `${clock(k.start)} · ${k.tonic} ${k.mode}${k.relative ? ` (ou ${k.relative})` : ""} → ${k.new_key}`, "chip"));
    }
    peak.append(
      el("p", "A música muda de tom. O grau vale para o tom do início.", "muted"),
      sectionChips,
    );
  }

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

  reportBox.append(result, peak, ranking, warning);
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

let jobsKey = null;

// Pedidos na fila, em curso ou com erro; o erro tem botão para dispensar.
function renderJobs(items) {
  const key = JSON.stringify(items);
  if (key === jobsKey) return;
  jobsKey = key;
  jobsBox.hidden = items.length === 0;
  jobsList.replaceChildren();
  for (const job of items) {
    const li = el("li", undefined, job.status === "error" ? "job error" : "job");
    const text = el("div");
    text.append(
      el("div", `youtu.be/${job.video_id}`, "title"),
      el("div", job.status === "error" ? job.error : STATUS_TEXT[job.status], "meta"),
    );
    li.append(text);
    if (job.status === "error") {
      const dismiss = el("button", "Dispensar", "small");
      dismiss.type = "button";
      dismiss.addEventListener("click", async () => {
        await api(`/api/jobs/${job.video_id}`, { method: "DELETE" });
        await refreshHistory({ manual: true });
      });
      li.append(dismiss);
    }
    jobsList.append(li);
  }
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
    const jobsResponse = await api("/api/jobs");
    if (!jobsResponse.ok) throw new Error(String(jobsResponse.status));
    renderJobs(await jobsResponse.json());
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
  statusBox.textContent = extractNow.checked ? "Extraindo a música (até 60 s)..." : "Enviando...";
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
    if (!created.already_analyzed && !extractNow.checked) {
      // Enviado ao worker (202): não espera; a lista se atualiza quando ficar pronto.
      statusBox.hidden = true;
      noticeBox.textContent = BACKGROUND_TEXT;
      noticeBox.hidden = false;
      urlInput.value = "";
    } else {
      await loadReport(created.video_id);
    }
    await refreshHistory();
  } catch (error) {
    showError(error.message);
  } finally {
    submit.disabled = false;
  }
}

// Salva o teto no servidor e refaz o relatório aberto com as features que ele já tem.
async function onCeilingChange() {
  const midi = Number(ceilingSelect.value);
  try {
    const response = await api("/api/me/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ceiling_midi: midi }),
    });
    if (!response.ok) throw new Error("settings");
  } catch {
    showError("Não consegui salvar o teto; ele vale só nesta tela.");
  }
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
authForm.addEventListener("submit", submitAuth);
authTabs.addEventListener("click", (event) => {
  const tab = event.target.closest("button[data-mode]");
  if (tab) setAuthMode(tab.dataset.mode);
});
authLink.addEventListener("click", () => {
  if (authMode === "verify") start(); // abre o app se já há sessão, senão a tela de entrada
  else setAuthMode(AUTH_MODES[authMode].other || "login");
});
logoutButton.addEventListener("click", logout);
togglePassword.addEventListener("click", () => {
  const show = authPassword.type === "password";
  authPassword.type = show ? "text" : "password";
  togglePassword.textContent = show ? "Ocultar" : "Mostrar";
  togglePassword.setAttribute("aria-label", show ? "Ocultar senha" : "Mostrar senha");
});
openEmailLink().then((handled) => {
  if (!handled) start();
});
historyRefresh.addEventListener("click", () => refreshHistory({ manual: true }));
setInterval(pollHistory, HISTORY_POLL_MS);
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible" && !appBox.hidden) refreshHistory({ manual: true });
});
