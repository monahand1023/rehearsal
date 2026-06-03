let mediaRecorder = null;
let chunks = [];
let lastBlob = null;
let questions = [];
let trackLanguage = "en";
let allTracks = [];
let trackMode = "interview";
window.ttsEnabled = false;
window.trackLanguage = "en";
const MODE_LABELS = { interview: "Interview Coach", japanese: "Japanese Practice" };

const modeSelect = document.getElementById("modeSelect");
const trackSelect = document.getElementById("trackSelect");
const qSelect = document.getElementById("questionSelect");
const qText = document.getElementById("question");
const recordBtn = document.getElementById("recordBtn");
const stopBtn = document.getElementById("stopBtn");
const analyzeBtn = document.getElementById("analyzeBtn");
const playback = document.getElementById("playback");
const statusEl = document.getElementById("status");

async function loadTracks() {
  try {
    const cfg = await (await fetch("/api/config")).json();
    window.ttsEnabled = !!cfg.tts_enabled;
  } catch (e) {
    window.ttsEnabled = false;
  }
  const data = await (await fetch("/api/tracks")).json();
  allTracks = data.tracks;
  const modes = [...new Set(allTracks.map((t) => t.mode))];
  modeSelect.innerHTML = "";
  modes.forEach((m) => {
    const opt = document.createElement("option");
    opt.value = m;
    opt.textContent = MODE_LABELS[m] || m;
    modeSelect.appendChild(opt);
  });
  populateTracksForMode(modeSelect.value);
}

function populateTracksForMode(mode) {
  const forMode = allTracks.filter((t) => t.mode === mode);
  trackSelect.innerHTML = "";
  forMode.forEach((t) => {
    const opt = document.createElement("option");
    opt.value = t.track;
    opt.textContent = `${t.track} (${t.language})`;
    trackSelect.appendChild(opt);
  });
  loadQuestions(trackSelect.value);
}

modeSelect.addEventListener("change", () => populateTracksForMode(modeSelect.value));

trackSelect.addEventListener("change", () => loadQuestions(trackSelect.value));

async function loadQuestions(track) {
  const resp = await fetch("/api/questions?track=" + encodeURIComponent(track));
  const data = await resp.json();
  questions = data.questions;
  trackLanguage = data.language || "en";
  const t = allTracks.find((x) => x.track === track);
  trackMode = t ? t.mode : "interview";
  window.trackLanguage = trackLanguage;
  qSelect.innerHTML = "";
  questions.forEach((q, i) => {
    const opt = document.createElement("option");
    opt.value = String(i);
    opt.textContent = `[${q.category}] ${q.prompt.slice(0, 60)}…`;
    qSelect.appendChild(opt);
  });
  showQuestion();
}

function currentQuestion() {
  return questions[Number(qSelect.value)];
}

function showQuestion() {
  qText.textContent = currentQuestion().prompt;
}

qSelect.addEventListener("change", showQuestion);

recordBtn.addEventListener("click", async () => {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  mediaRecorder = new MediaRecorder(stream);
  chunks = [];
  mediaRecorder.ondataavailable = (e) => chunks.push(e.data);
  mediaRecorder.onstop = () => {
    lastBlob = new Blob(chunks, { type: "audio/webm" });
    playback.src = URL.createObjectURL(lastBlob);
    playback.classList.remove("hidden");
    analyzeBtn.disabled = false;
    stream.getTracks().forEach((t) => t.stop());
  };
  mediaRecorder.start();
  recordBtn.disabled = true;
  stopBtn.disabled = false;
  analyzeBtn.disabled = true;
  statusEl.textContent = "Recording…";
  statusEl.className = "rec-on";
});

stopBtn.addEventListener("click", () => {
  mediaRecorder.stop();
  recordBtn.disabled = false;
  stopBtn.disabled = true;
  statusEl.textContent = "";
  statusEl.className = "";
});

analyzeBtn.addEventListener("click", async () => {
  if (!lastBlob) return;
  analyzeBtn.disabled = true;
  statusEl.textContent = "Analyzing… (this can take a few seconds)";
  const form = new FormData();
  form.append("question", currentQuestion().prompt);
  form.append("audio", lastBlob, "answer.webm");
  form.append("language", trackLanguage);
  form.append("mode", trackMode);
  try {
    const resp = await fetch("/api/analyze", { method: "POST", body: form });
    const report = await resp.json();
    window.renderResults(report);
  } finally {
    statusEl.textContent = "";
    analyzeBtn.disabled = false;
  }
});

loadTracks();
