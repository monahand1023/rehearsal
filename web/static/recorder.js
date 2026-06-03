// ---- state ----
let mediaRecorder = null;
let chunks = [];
let lastBlob = null;
let recording = false;
let timerId = null;
let seconds = 0;

let allTracks = [];
let questions = [];
let qIndex = 0;
let currentTrack = null;
let trackMode = "interview";
let trackLanguage = "en";
window.ttsEnabled = false;
window.trackLanguage = "en";

const MODE_LABELS = { interview: "Interview Coach", japanese: "Japanese Practice" };
const ENCOURAGE = {
  idle: "Take your time — you've got this.",
  recording: "Speak naturally. I'm listening…",
  done: "Nice. Play it back, then get your feedback.",
};

// ---- elements ----
const modeToggle = document.getElementById("modeToggle");
const qCategory = document.getElementById("qCategory");
const qCounter = document.getElementById("qCounter");
const qPrev = document.getElementById("qPrev");
const qNext = document.getElementById("qNext");
const qText = document.getElementById("question");
const recordBtn = document.getElementById("recordBtn");
const recordLabel = document.getElementById("recordLabel");
const timerEl = document.getElementById("timer");
const encourage = document.getElementById("encourage");
const playback = document.getElementById("playback");
const analyzeBtn = document.getElementById("analyzeBtn");
const statusEl = document.getElementById("status");
const hearPromptBtn = document.getElementById("hearPromptBtn");
const promptAudio = document.getElementById("promptAudio");

const MAX_SECONDS = 180; // 3-minute response cap, like the real STAMP test

// ---- bootstrap ----
async function init() {
  try {
    const cfg = await (await fetch("/api/config")).json();
    window.ttsEnabled = !!cfg.tts_enabled;
  } catch (e) {
    window.ttsEnabled = false;
  }
  if (window.ttsEnabled) hearPromptBtn.classList.remove("hidden");
  const data = await (await fetch("/api/tracks")).json();
  allTracks = data.tracks;

  const modes = [...new Set(allTracks.map((t) => t.mode))];
  modeToggle.innerHTML = "";
  modes.forEach((m, i) => {
    const b = document.createElement("button");
    b.className = "mode-btn" + (i === 0 ? " active" : "");
    b.dataset.mode = m;
    b.textContent = MODE_LABELS[m] || m;
    b.addEventListener("click", () => selectMode(m));
    modeToggle.appendChild(b);
  });
  selectMode(modes[0]);
}

function selectMode(mode) {
  trackMode = mode;
  document.body.dataset.mode = mode;
  document.querySelectorAll(".mode-btn").forEach((b) =>
    b.classList.toggle("active", b.dataset.mode === mode));
  const track = allTracks.find((t) => t.mode === mode);
  currentTrack = track ? track.track : null;
  resetRecording();
  document.getElementById("results").innerHTML = "";
  if (currentTrack) loadQuestions(currentTrack);
}

async function loadQuestions(track) {
  const data = await (await fetch("/api/questions?track=" + encodeURIComponent(track))).json();
  questions = data.questions || [];
  trackLanguage = data.language || "en";
  window.trackLanguage = trackLanguage;
  qIndex = 0;
  showQuestion();
}

function showQuestion() {
  if (!questions.length) return;
  const q = questions[qIndex];
  qCategory.textContent = q.category || "Question";
  qCounter.textContent = `${qIndex + 1} / ${questions.length}`;
  qText.textContent = q.prompt;
  qText.classList.toggle("lang-ja", trackLanguage === "ja");
  qPrev.disabled = qIndex === 0;
  qNext.disabled = qIndex === questions.length - 1;
}

function currentQuestion() {
  return questions[qIndex];
}

qPrev.addEventListener("click", () => { if (qIndex > 0) { qIndex--; showQuestion(); resetRecording(); } });
qNext.addEventListener("click", () => { if (qIndex < questions.length - 1) { qIndex++; showQuestion(); resetRecording(); } });

// Hear the prompt read aloud (the real STAMP test plays each prompt in the target language).
hearPromptBtn.addEventListener("click", async () => {
  const q = currentQuestion();
  if (!q) return;
  hearPromptBtn.disabled = true;
  try {
    const form = new FormData();
    form.append("text", q.prompt);
    form.append("language", trackLanguage);
    const resp = await fetch("/api/speak", { method: "POST", body: form });
    if (!resp.ok) throw new Error("speak failed");
    promptAudio.src = URL.createObjectURL(await resp.blob());
    promptAudio.play();
  } catch (e) {
    /* ignore — the on-screen prompt is still there */
  } finally {
    hearPromptBtn.disabled = false;
  }
});

// ---- recording ----
function fmt(s) {
  const m = Math.floor(s / 60), r = s % 60;
  return `${m}:${String(r).padStart(2, "0")}`;
}

recordBtn.addEventListener("click", () => (recording ? stopRecording() : startRecording()));

async function startRecording() {
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch (e) {
    statusEl.textContent = "Microphone access is needed to record.";
    return;
  }
  mediaRecorder = new MediaRecorder(stream);
  chunks = [];
  mediaRecorder.ondataavailable = (e) => chunks.push(e.data);
  mediaRecorder.onstop = () => {
    lastBlob = new Blob(chunks, { type: "audio/webm" });
    playback.src = URL.createObjectURL(lastBlob);
    playback.classList.remove("hidden");
    analyzeBtn.classList.remove("hidden");
    encourage.textContent = ENCOURAGE.done;
    stream.getTracks().forEach((t) => t.stop());
  };
  mediaRecorder.start();
  recording = true;
  seconds = 0;
  document.body.classList.add("is-recording");
  recordLabel.textContent = "Stop";
  timerEl.textContent = "0:00 / 3:00";
  timerEl.classList.remove("hidden");
  encourage.textContent = ENCOURAGE.recording;
  playback.classList.add("hidden");
  analyzeBtn.classList.add("hidden");
  statusEl.textContent = "";
  document.getElementById("results").innerHTML = "";
  timerId = setInterval(() => {
    seconds++;
    timerEl.textContent = `${fmt(seconds)} / 3:00`;
    if (seconds >= MAX_SECONDS) {
      stopRecording();
      statusEl.textContent = "That's the 3-minute limit — same as the real test.";
    }
  }, 1000);
}

function stopRecording() {
  if (mediaRecorder && recording) mediaRecorder.stop();
  recording = false;
  clearInterval(timerId);
  document.body.classList.remove("is-recording");
  recordLabel.textContent = "Record again";
  timerEl.classList.add("hidden");
}

function resetRecording() {
  if (recording) stopRecording();
  lastBlob = null;
  recordLabel.textContent = "Start recording";
  timerEl.classList.add("hidden");
  encourage.textContent = ENCOURAGE.idle;
  playback.classList.add("hidden");
  analyzeBtn.classList.add("hidden");
  statusEl.textContent = "";
  document.getElementById("results").innerHTML = ""; // clear stale feedback when changing question/mode
}

// ---- analyze ----
analyzeBtn.addEventListener("click", async () => {
  if (!lastBlob) return;
  analyzeBtn.disabled = true;
  statusEl.innerHTML = '<span class="spin"></span>Listening back and writing your feedback…';
  const form = new FormData();
  form.append("question", currentQuestion().prompt);
  form.append("audio", lastBlob, "answer.webm");
  form.append("language", trackLanguage);
  form.append("mode", trackMode);
  try {
    const resp = await fetch("/api/analyze", { method: "POST", body: form });
    if (!resp.ok) throw new Error("analyze failed");
    const report = await resp.json();
    window.renderResults(report);
  } catch (e) {
    statusEl.textContent = "Something went wrong analyzing that — try again.";
  } finally {
    if (statusEl.querySelector(".spin")) statusEl.textContent = "";
    analyzeBtn.disabled = false;
  }
});

init();
