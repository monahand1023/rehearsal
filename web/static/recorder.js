let mediaRecorder = null;
let chunks = [];
let lastBlob = null;
let questions = [];

const qSelect = document.getElementById("questionSelect");
const qText = document.getElementById("question");
const recordBtn = document.getElementById("recordBtn");
const stopBtn = document.getElementById("stopBtn");
const analyzeBtn = document.getElementById("analyzeBtn");
const playback = document.getElementById("playback");
const statusEl = document.getElementById("status");

async function loadQuestions() {
  const resp = await fetch("/api/questions?track=interview_en");
  const data = await resp.json();
  questions = data.questions;
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
  try {
    const resp = await fetch("/api/analyze", { method: "POST", body: form });
    const report = await resp.json();
    window.renderResults(report);
  } finally {
    statusEl.textContent = "";
    analyzeBtn.disabled = false;
  }
});

loadQuestions();
