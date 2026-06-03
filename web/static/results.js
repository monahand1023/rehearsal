function annotateTranscript(report) {
  const words = report.transcript.words;
  const hits = report.fillers.hits || [];
  const lexStarts = new Set(
    hits.filter((h) => h.source !== "acoustic").map((h) => h.start)
  );
  const acoustic = hits.filter((h) => h.source === "acoustic");

  function chipsInGap(lo, hi) {
    return acoustic
      .filter((h) => h.start >= lo - 0.001 && h.start < hi)
      .map((h) => `<span class="filler acoustic">${h.text}</span>`);
  }

  const parts = [];
  const firstStart = words.length ? words[0].start : Infinity;
  parts.push(...chipsInGap(-1, firstStart));

  words.forEach((w, i) => {
    if (lexStarts.has(w.start)) {
      parts.push(`<span class="filler">${w.text}</span>`);
    } else {
      parts.push(w.text);
    }
    const nextStart = i + 1 < words.length ? words[i + 1].start : Infinity;
    parts.push(...chipsInGap(w.end, nextStart));
    if (i + 1 < words.length) {
      const gap = words[i + 1].start - w.end;
      if (gap >= 0.5) {
        parts.push(`<span class="pause"> …(${gap.toFixed(1)}s)… </span>`);
      }
    }
  });
  return parts.join(" ");
}

window.renderResults = function (report) {
  const d = report.delivery;
  const f = report.fillers;
  const p = report.prosody;
  const c = report.content;

  let html = "";

  html += `<div class="card"><h2>Delivery</h2>
    <span class="metric"><b>${d.words_per_minute}</b> wpm</span>
    <span class="metric"><b>${f.count}</b> fillers (${f.per_minute}/min)</span>
    <span class="metric"><b>${d.long_pause_count}</b> long pauses</span>
    <span class="metric">monotone: <b>${p.monotone ? "yes" : "no"}</b> (pitch σ ${p.pitch_std_hz}Hz)</span>
    <span class="metric">first word at <b>${d.time_to_first_word}s</b></span>
  </div>`;

  html += `<div class="card"><h2>Transcript</h2>
    <p>${annotateTranscript(report)}</p>
    <small>Highlighted = filler word · italic = pause</small></div>`;

  if (c) {
    const star = Object.entries(c.star_present)
      .map(([k, v]) => `${v ? "✅" : "⬜️"} ${k}`)
      .join("  ");
    html += `<div class="card"><h2>Content</h2>
      <p><b>Answered the question:</b> ${c.answered_question ? "yes" : "no"} — ${c.answered_explanation}</p>
      <p><b>STAR:</b> ${star}</p>
      ${c.issues.length ? `<p><b>Watch out:</b> ${c.issues.join("; ")}</p>` : ""}
      <p><b>Tighter version:</b> ${c.tighter_rewrite}</p>
      <p><b>Next time, try:</b></p>
      <ul>${c.coaching_notes.map((n) => `<li>${n}</li>`).join("")}</ul>
    </div>`;
  }

  if (report.spoken_summary) {
    const voiceUi = window.ttsEnabled
      ? '<button id="hearBtn">🔊 Hear feedback</button> ' +
        '<span id="hearStatus"></span>' +
        '<audio id="coachAudio" class="hidden"></audio>'
      : "";
    html += `<div class="card"><h2>Coach</h2>
      <p id="coachText">${report.spoken_summary}</p>
      ${voiceUi}</div>`;
  }

  document.getElementById("results").innerHTML = html;

  if (report.spoken_summary && window.ttsEnabled) {
    const hearBtn = document.getElementById("hearBtn");
    const status = document.getElementById("hearStatus");
    hearBtn.addEventListener("click", async () => {
      hearBtn.disabled = true;
      status.textContent = "Generating voice…";
      try {
        const form = new FormData();
        form.append("text", report.spoken_summary);
        form.append("language", window.trackLanguage || "en");
        const resp = await fetch("/api/speak", { method: "POST", body: form });
        if (!resp.ok) throw new Error("speak failed");
        const blob = await resp.blob();
        const audio = document.getElementById("coachAudio");
        audio.src = URL.createObjectURL(blob);
        audio.classList.remove("hidden");
        audio.play();
        status.textContent = "";
      } catch (e) {
        status.textContent = "Voice unavailable.";
      } finally {
        hearBtn.disabled = false;
      }
    });
  }
};
