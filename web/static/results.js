// Annotated transcript: lexicon fillers highlight the word; acoustic fillers show
// as inline gap chips; long pauses are marked between words.
function annotateTranscript(report, ja) {
  const words = report.transcript.words;
  const hits = report.fillers.hits || [];
  // A lexicon filler can span several word tokens (Japanese is tokenized per character),
  // so highlight any token that falls within a lexicon hit's [start, end] span.
  const lexRanges = hits.filter((h) => h.source !== "acoustic").map((h) => [h.start, h.end]);
  const isLexFiller = (w) =>
    lexRanges.some(([s, e]) => w.start >= s - 0.001 && w.end <= e + 0.001);
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
    parts.push(isLexFiller(w) ? `<span class="filler">${w.text}</span>` : w.text);
    const nextStart = i + 1 < words.length ? words[i + 1].start : Infinity;
    parts.push(...chipsInGap(w.end, nextStart));
    if (i + 1 < words.length) {
      const gap = words[i + 1].start - w.end;
      if (gap >= 0.5) parts.push(`<span class="pause"> …(${gap.toFixed(1)}s)… </span>`);
    }
  });
  // Japanese has no inter-word spaces and Whisper tokenizes per character, so join with
  // "" (the filler/pause chips carry their own spacing); English keeps word spaces.
  return parts.join(ja ? "" : " ");
}

function meter(on, total = 5) {
  let s = '<span class="meter">';
  for (let i = 0; i < total; i++) s += `<i class="${i < on ? "on" : ""}"></i>`;
  return s + "</span>";
}

// --- Progress history (client-side only; localStorage, keyed per track) ---
function progressKey() {
  return "rehearsal_progress_" + (window.trackLanguage || "ja");
}
function loadProgress() {
  try { return JSON.parse(localStorage.getItem(progressKey()) || "[]"); } catch (e) { return []; }
}
function saveProgress(arr) {
  try { localStorage.setItem(progressKey(), JSON.stringify(arr.slice(-60))); } catch (e) {}
}
function todayStr() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
// Consecutive calendar days (ending at the most recent recorded day) with at least one attempt.
function practiceStreak(history) {
  const days = [...new Set(history.map((h) => h.date))].sort();
  let streak = days.length ? 1 : 0;
  for (let i = days.length - 1; i > 0; i--) {
    const diff = Math.round((new Date(days[i]) - new Date(days[i - 1])) / 86400000);
    if (diff === 1) streak++; else break;
  }
  return streak;
}

// pace -> {num, unit, caption, dots}. Japanese is measured in characters per minute
// (words_per_minute is meaningless there — Whisper tokenizes JP per character); English
// uses words per minute against a target band.
function paceTile(d, lang) {
  if (lang === "ja") {
    const cpm = Math.round(d.chars_per_minute || 0);
    // Gentle bands for a young learner — slow is fine (taking your time), only very fast is flagged.
    let cap = "a nice, natural pace", dots = 5;
    if (cpm < 180) { cap = "you took your time — that's okay"; dots = 4; }
    else if (cpm > 560) { cap = "pretty fast — you can slow down"; dots = 3; }
    return { num: cpm, unit: "cpm", cap, dots };
  }
  const wpm = d.words_per_minute;
  if (wpm < 100) return { num: Math.round(wpm), unit: "wpm", cap: "relaxed — room to speak up", dots: 2 };
  if (wpm <= 160) return { num: Math.round(wpm), unit: "wpm", cap: "a natural, easy pace", dots: 5 };
  if (wpm <= 185) return { num: Math.round(wpm), unit: "wpm", cap: "a touch quick", dots: 3 };
  return { num: Math.round(wpm), unit: "wpm", cap: "quite fast — try a breath", dots: 2 };
}

function clarityTile(conf) {
  const pct = Math.round(conf * 100);
  let cap = "crisp and clear", dots = 5;
  if (pct < 75) { cap = "a little muffled in places"; dots = 2; }
  else if (pct < 90) { cap = "clear"; dots = 4; }
  return { pct, cap, dots };
}

function fillerTile(count, ja) {
  // A learner reaching for words hesitates more — be lenient for the kid's Japanese track.
  if (ja) {
    let cap = "smooth — no ums!", dots = 5;
    if (count > 5) { cap = "lots of ums — take your time"; dots = 3; }
    else if (count >= 3) { cap = "a couple of ums — natural when thinking"; dots = 4; }
    return { count, cap, dots };
  }
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
  const pace = paceTile(d, window.trackLanguage);
  const fil = fillerTile(f.count, ja);
  // Clarity needs real per-word confidence; the cloud transcriber supplies none, so the
  // report omits it (cl === null) rather than show a fake 100%. Hide the tile then.
  const clarityTileHtml = cl ? (() => {
    const clar = clarityTile(cl.mean_confidence);
    return `<div class="tile"><div class="label">Clarity</div>
        <div class="num">${clar.pct}<span class="unit">%</span></div>
        <div class="cap">${clar.cap}</div>${meter(clar.dots)}</div>`;
  })() : "";
  // Prosody (Expression) is only present in native mode; cloud "lite" mode omits it.
  const expressionTile = p ? `<div class="tile"><div class="label">Expression</div>
        <div class="num" style="font-size:1.2rem">${!p.monotone ? "Expressive" : "A bit flat"}</div>
        <div class="cap">${!p.monotone ? "good pitch variety" : "try more ups and downs"}</div></div>` : "";
  cards.push(`<div class="card"><h2>How you did</h2>
    <div class="tiles">
      <div class="tile"><div class="label">Pace</div>
        <div class="num">${pace.num}<span class="unit">${pace.unit}</span></div>
        <div class="cap">${pace.cap}</div>${meter(pace.dots)}</div>
      ${clarityTileHtml}
      <div class="tile"><div class="label">Fillers</div>
        <div class="num">${fil.count}</div>
        <div class="cap">${fil.cap}</div>${meter(fil.dots)}</div>
      ${expressionTile}
    </div></div>`);

  // --- Transcript ---
  cards.push(`<div class="card"><h2>What you said</h2>
    <div class="transcript${ja ? " lang-ja" : ""}">${annotateTranscript(report, ja)}</div>
    <div class="legend"><span class="l-filler">filler word</span>
      <span class="l-ac">heard pause</span>
      <span class="pause">…(s)… long pause</span></div></div>`);

  // --- Proficiency (kid-facing: progress + one tip; the ACTFL detail lives in a toggle) ---
  if (c && c.kind === "proficiency") {
    const lvl = c.stamp_level;
    // Progress vs. last time + practice streak (client-side history; compare BEFORE recording).
    const history = loadProgress();
    const prev = history.length ? history[history.length - 1] : null;
    let progressLine = "";
    if (prev && lvl) {
      const arrow = lvl > prev.stamp_level ? " ⬆" : (lvl < prev.stamp_level ? " ⬇" : " →");
      const cls = lvl > prev.stamp_level ? "up" : (lvl < prev.stamp_level ? "down" : "");
      progressLine = `<div class="progress-line ${cls}">Last time: Level ${prev.stamp_level} → <b>today: Level ${lvl}${arrow}</b></div>`;
    }
    if (lvl) {
      history.push({ date: todayStr(), stamp_level: lvl, fillers: f.count, cpm: Math.round(d.chars_per_minute || 0) });
      saveProgress(history);
    }
    const streak = practiceStreak(history);
    const streakLine = streak >= 2 ? `<div class="streak">🔥 ${streak} days in a row — keep it up!</div>` : "";
    const levelBlock = lvl
      ? `<div class="level-progress"><span class="level-badge">Level ${lvl} of 8</span>
           ${meter(lvl, 8)}<div class="level-name">${c.level || ""}</div></div>`
      : `<span class="level-badge">${c.level || "—"}</span>`;
    const kidSteps = (c.next_steps || []).slice(0, 2);   // one or two, not a wall of five
    const grownup = `<details class="grownup"><summary>For grown-ups: full breakdown</summary>
        <div class="row"><small>STAMP-style practice estimate, not an official score.</small></div>
        ${c.level_explanation ? `<div class="row">${c.level_explanation}</div>` : ""}
        <div class="row"><b>Functions</b> <small>(task)</small>: ${c.functions || ""}</div>
        <div class="row"><b>Accuracy</b> <small>(understandability)</small>: ${c.accuracy || ""}</div>
        <div class="row"><b>Context &amp; content</b>: ${c.context_content || ""}</div>
        <div class="row"><b>Text type</b> <small>(discourse)</small>: ${c.text_type || ""}</div></details>`;
    cards.push(`<div class="card"><h2>How your Japanese is growing</h2>
      ${levelBlock}
      ${progressLine}
      ${streakLine}
      ${c.strengths && c.strengths.length ? `<div class="row"><b>Great job:</b> ${c.strengths.join("; ")}</div>` : ""}
      ${c.english_words && c.english_words.length ? `<div class="row"><b>Try these in Japanese next time:</b>
        <ul class="notes">${c.english_words.map((s) => `<li>${s}</li>`).join("")}</ul></div>` : ""}
      ${kidSteps.length ? `<div class="row"><b>One thing to try:</b></div>
        <ul class="notes">${kidSteps.map((s) => `<li>${s}</li>`).join("")}</ul>` : ""}
      ${grownup}</div>`);
  } else if (c) {
    const order = ["situation", "task", "action", "result"];
    const starCount = order.filter((k) => c.star_present && c.star_present[k]).length;
    // Progress vs. last time (STAR completeness) + practice streak — compare BEFORE recording.
    const history = loadProgress();
    const prev = history.length ? history[history.length - 1] : null;
    let progressLine = "";
    if (prev && typeof prev.star === "number") {
      const arrow = starCount > prev.star ? " ⬆" : (starCount < prev.star ? " ⬇" : " →");
      const cls = starCount > prev.star ? "up" : (starCount < prev.star ? "down" : "");
      progressLine = `<div class="progress-line ${cls}">Last time: ${prev.star}/4 STAR → <b>today: ${starCount}/4${arrow}</b></div>`;
    }
    history.push({ date: todayStr(), star: starCount, answered: !!c.answered_question, fillers: f.count });
    saveProgress(history);
    const streak = practiceStreak(history);
    const streakLine = streak >= 2 ? `<div class="streak">🔥 ${streak} days in a row — keep it up!</div>` : "";
    const star = order.map((k) => {
      const on = c.star_present && c.star_present[k];
      return `<span class="pill ${on ? "on" : ""}"><span class="tick">${on ? "✓" : "○"}</span>${k}</span>`;
    }).join("");
    cards.push(`<div class="card"><h2>Your answer</h2>
      ${progressLine}
      ${streakLine}
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
      ? '<button id="hearBtn" class="hear">🔊 Play coach feedback</button><span id="hearStatus" class="hear-status"></span><audio id="coachAudio" playsinline class="hidden"></audio>'
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
        hearBtn.textContent = "🔊 Play again";
      } catch (e) {
        // Autoplay is blocked on iOS (and after the processing gap) — the button is the fallback.
        status.textContent = auto ? "👆 Tap the button to hear your coach" : "Voice unavailable.";
      } finally {
        hearBtn.disabled = false;
      }
    }
    hearBtn.addEventListener("click", () => playCoach(false));
    playCoach(true); // start playing as soon as the feedback is ready
  }
};
