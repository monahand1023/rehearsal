// Annotated transcript: lexicon fillers highlight the word; acoustic fillers show
// as inline gap chips; long pauses are marked between words.
function annotateTranscript(report) {
  const words = report.transcript.words;
  const hits = report.fillers.hits || [];
  const lexStarts = new Set(hits.filter((h) => h.source !== "acoustic").map((h) => h.start));
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
    parts.push(lexStarts.has(w.start) ? `<span class="filler">${w.text}</span>` : w.text);
    const nextStart = i + 1 < words.length ? words[i + 1].start : Infinity;
    parts.push(...chipsInGap(w.end, nextStart));
    if (i + 1 < words.length) {
      const gap = words[i + 1].start - w.end;
      if (gap >= 0.5) parts.push(`<span class="pause"> …(${gap.toFixed(1)}s)… </span>`);
    }
  });
  return parts.join(" ");
}

function meter(on, total = 5) {
  let s = '<span class="meter">';
  for (let i = 0; i < total; i++) s += `<i class="${i < on ? "on" : ""}"></i>`;
  return s + "</span>";
}

// pace -> {caption, dots}. English has a target band; Japanese wpm reads high
// (Whisper segments JP into short "words"), so we keep it qualitative there.
function paceTile(wpm, lang) {
  if (lang === "ja") return { num: Math.round(wpm), cap: "approx. (JP rate varies)", dots: 3 };
  if (wpm < 100) return { num: Math.round(wpm), cap: "relaxed — room to speak up", dots: 2 };
  if (wpm <= 160) return { num: Math.round(wpm), cap: "a natural, easy pace", dots: 5 };
  if (wpm <= 185) return { num: Math.round(wpm), cap: "a touch quick", dots: 3 };
  return { num: Math.round(wpm), cap: "quite fast — try a breath", dots: 2 };
}

function clarityTile(conf) {
  const pct = Math.round(conf * 100);
  let cap = "crisp and clear", dots = 5;
  if (pct < 75) { cap = "a little muffled in places"; dots = 2; }
  else if (pct < 90) { cap = "clear"; dots = 4; }
  return { pct, cap, dots };
}

function fillerTile(count) {
  let cap = "smooth — no fillers", dots = 5;
  if (count >= 3) { cap = "a few ums crept in"; dots = 2; }
  else if (count >= 1) { cap = "just a couple"; dots = 4; }
  return { count, cap, dots };
}

window.renderResults = function (report) {
  const d = report.delivery, f = report.fillers, p = report.prosody;
  const cl = report.clarity, c = report.content;
  const ja = (window.trackLanguage || "en") === "ja";
  const cards = [];

  // --- How you did ---
  const pace = paceTile(d.words_per_minute, window.trackLanguage);
  const clar = clarityTile(cl ? cl.mean_confidence : 0);
  const fil = fillerTile(f.count);
  // Prosody (Expression) is only present in native mode; cloud "lite" mode omits it.
  const expressionTile = p ? `<div class="tile"><div class="label">Expression</div>
        <div class="num" style="font-size:1.2rem">${!p.monotone ? "Expressive" : "A bit flat"}</div>
        <div class="cap">${!p.monotone ? "good pitch variety" : "try more ups and downs"}</div></div>` : "";
  cards.push(`<div class="card"><h2>How you did</h2>
    <div class="tiles">
      <div class="tile"><div class="label">Pace</div>
        <div class="num">${pace.num}<span class="unit">wpm</span></div>
        <div class="cap">${pace.cap}</div>${meter(pace.dots)}</div>
      <div class="tile"><div class="label">Clarity</div>
        <div class="num">${clar.pct}<span class="unit">%</span></div>
        <div class="cap">${clar.cap}</div>${meter(clar.dots)}</div>
      <div class="tile"><div class="label">Fillers</div>
        <div class="num">${fil.count}</div>
        <div class="cap">${fil.cap}</div>${meter(fil.dots)}</div>
      ${expressionTile}
    </div></div>`);

  // --- Transcript ---
  cards.push(`<div class="card"><h2>What you said</h2>
    <div class="transcript${ja ? " lang-ja" : ""}">${annotateTranscript(report)}</div>
    <div class="legend"><span class="l-filler">filler word</span>
      <span class="l-ac">heard pause</span>
      <span class="pause">…(s)… long pause</span></div></div>`);

  // --- Content / Proficiency (ACTFL FACT criteria) ---
  if (c && c.kind === "proficiency") {
    cards.push(`<div class="card"><h2>Proficiency <small>ACTFL-style practice estimate, not an official score</small></h2>
      <span class="level-badge">${c.level || "—"}</span>
      ${c.level_explanation ? `<div class="row">${c.level_explanation}</div>` : ""}
      <div class="row"><b>Functions</b> <small>(task)</small>: ${c.functions || ""}</div>
      <div class="row"><b>Accuracy</b> <small>(understandability)</small>: ${c.accuracy || ""}</div>
      <div class="row"><b>Context &amp; content</b>: ${c.context_content || ""}</div>
      <div class="row"><b>Text type</b> <small>(discourse)</small>: ${c.text_type || ""}</div>
      ${c.strengths && c.strengths.length ? `<div class="row"><b>Strengths:</b> ${c.strengths.join("; ")}</div>` : ""}
      <div class="row"><b>To reach the next level:</b></div>
      <ul class="notes">${(c.next_steps || []).map((s) => `<li>${s}</li>`).join("")}</ul></div>`);
  } else if (c) {
    const order = ["situation", "task", "action", "result"];
    const star = order.map((k) => {
      const on = c.star_present && c.star_present[k];
      return `<span class="pill ${on ? "on" : ""}"><span class="tick">${on ? "✓" : "○"}</span>${k}</span>`;
    }).join("");
    cards.push(`<div class="card"><h2>Your answer</h2>
      <div class="row"><b>Answered the question:</b> ${c.answered_question ? "yes" : "not quite"} — ${c.answered_explanation || ""}</div>
      <div class="row"><b>STAR structure</b></div>
      <div class="star">${star}</div>
      ${c.issues && c.issues.length ? `<div class="row"><b>Watch for:</b> ${c.issues.join("; ")}</div>` : ""}
      ${c.tighter_rewrite ? `<div class="row"><b>A tighter version:</b></div><div class="rewrite">${c.tighter_rewrite}</div>` : ""}
      <div class="row" style="margin-top:.8rem"><b>Next time, try:</b></div>
      <ul class="notes">${(c.coaching_notes || []).map((n) => `<li>${n}</li>`).join("")}</ul></div>`);
  }

  // --- Coach (spoken summary) ---
  if (report.spoken_summary) {
    const voiceUi = window.ttsEnabled
      ? '<button id="hearBtn" class="hear">🔊 Hear it</button><span id="hearStatus" class="hear-status"></span><audio id="coachAudio" class="hidden"></audio>'
      : "";
    cards.push(`<div class="card coach"><h2>Your coach says</h2>
      <p class="quote${ja ? " lang-ja" : ""}">${report.spoken_summary}</p>${voiceUi}</div>`);
  }

  const results = document.getElementById("results");
  results.innerHTML = cards.join("");
  // staggered entrance
  [...results.children].forEach((el, i) => { el.style.animationDelay = `${i * 0.07}s`; });

  if (report.spoken_summary && window.ttsEnabled) {
    const hearBtn = document.getElementById("hearBtn");
    const status = document.getElementById("hearStatus");
    const audio = document.getElementById("coachAudio");
    let cachedUrl = null;

    async function playCoach(auto) {
      hearBtn.disabled = true;
      if (!cachedUrl) status.textContent = auto ? "Preparing your coach's voice…" : "Generating voice…";
      try {
        if (!cachedUrl) {
          const form = new FormData();
          form.append("text", report.spoken_summary);
          form.append("language", window.trackLanguage || "en");
          const resp = await fetch("/api/speak", { method: "POST", body: form });
          if (!resp.ok) throw new Error("speak failed");
          cachedUrl = URL.createObjectURL(await resp.blob());
          audio.src = cachedUrl;
          audio.classList.remove("hidden");
        }
        await audio.play();
        status.textContent = "";
        hearBtn.textContent = "🔊 Hear it again";
      } catch (e) {
        // Autoplay can be blocked after the long processing gap — the button is the fallback.
        status.textContent = auto ? "Tap “Hear it” to play ▶" : "Voice unavailable.";
      } finally {
        hearBtn.disabled = false;
      }
    }
    hearBtn.addEventListener("click", () => playCoach(false));
    playCoach(true); // start playing as soon as the feedback is ready
  }
};
