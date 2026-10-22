// Front do Song Tonality Helper: envia o link, acompanha o job e desenha o relatório.
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

function renderReport(r) {
  reportBox.replaceChildren();

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

  reportBox.append(main, keyCard, result, times, ranking, warning);
  reportBox.hidden = false;
}

async function poll(id) {
  const response = await fetch(`/api/analyses/${id}`);
  if (!response.ok) throw new Error("Análise não encontrada.");
  const job = await response.json();
  if (job.status === "done") {
    statusBox.hidden = true;
    renderReport(job.report);
    return;
  }
  if (job.status === "error") {
    showError(job.error);
    return;
  }
  statusBox.textContent = STATUS_TEXT[job.status];
  await new Promise((resolve) => setTimeout(resolve, POLL_MS));
  await poll(id);
}

async function analyze(event) {
  event.preventDefault();
  errorBox.hidden = true;
  reportBox.hidden = true;
  submit.disabled = true;
  statusBox.textContent = "Enviando...";
  statusBox.hidden = false;
  try {
    const response = await fetch("/api/analyses", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: urlInput.value, ceiling_midi: Number(ceilingSelect.value) }),
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(typeof body.detail === "string" ? body.detail : "Pedido inválido.");
    }
    const { id } = await response.json();
    await poll(id);
  } catch (error) {
    showError(error.message);
  } finally {
    submit.disabled = false;
  }
}

ceilingSelect.addEventListener("change", () => saveCeiling(ceilingSelect.value));
form.addEventListener("submit", analyze);
loadCeilings().catch(() => showError("Não consegui carregar a lista de tetos."));
