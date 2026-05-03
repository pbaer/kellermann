// Shared utilities for the kriegstagebuch and audio proofreading tools.
// Exposed on window.ProofreadShared.
(() => {

function escHtml(s) {
  return String(s).replace(/[&<>]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
}

// Wrap each (case-insensitive) occurrence of `query` in `text` with <mark>.
// Used to render an overlay matching textarea contents char-for-char.
function highlightHTML(text, query) {
  const q = (query || "").trim();
  if (!q) return escHtml(text);
  const parts = [];
  const lower = text.toLowerCase();
  const qlower = q.toLowerCase();
  let i = 0;
  while (i < text.length) {
    const j = lower.indexOf(qlower, i);
    if (j === -1) {
      parts.push(escHtml(text.slice(i)));
      break;
    }
    if (j > i) parts.push(escHtml(text.slice(i, j)));
    parts.push(`<mark>${escHtml(text.slice(j, j + q.length))}</mark>`);
    i = j + q.length;
  }
  return parts.join("");
}

function lcs(a, b, eq) {
  const n = a.length, m = b.length;
  const dp = Array.from({ length: n + 1 }, () => new Int32Array(m + 1));
  for (let i = 0; i < n; i++) {
    for (let j = 0; j < m; j++) {
      dp[i + 1][j + 1] = eq(a[i], b[j]) ? dp[i][j] + 1 : Math.max(dp[i][j + 1], dp[i + 1][j]);
    }
  }
  const ops = [];
  let i = n, j = m;
  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && eq(a[i - 1], b[j - 1])) { ops.push(["eq", a[i - 1], b[j - 1]]); i--; j--; }
    else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) { ops.push(["add", null, b[j - 1]]); j--; }
    else { ops.push(["del", a[i - 1], null]); i--; }
  }
  ops.reverse();
  return ops;
}

function tokenize(line) {
  // Words, whitespace runs, and single punctuation chars.
  return line.match(/\s+|[A-Za-zÄÖÜäöüß]+|\d+|[^\s]/g) || [];
}

function renderLineWithInline(tokens, keepKinds, chgClass) {
  const html = [];
  for (const [kind, aVal, bVal] of tokens) {
    if (!keepKinds.has(kind)) continue;
    const text = kind === "add" ? bVal : aVal;
    if (kind === "eq") html.push(escHtml(text));
    else html.push(`<span class="${chgClass}">${escHtml(text)}</span>`);
  }
  return html.join("");
}

function inlineDelAdd(delLine, addLine) {
  const aToks = tokenize(delLine);
  const bToks = tokenize(addLine);
  const ops = lcs(aToks, bToks, (a, b) => a === b);
  const delHtml = renderLineWithInline(ops, new Set(["eq", "del"]), "chg");
  const addHtml = renderLineWithInline(ops, new Set(["eq", "add"]), "chg");
  return [delHtml, addHtml];
}

function renderUnifiedDiff(a, b) {
  const ops = lcs(a, b, (x, y) => x === y);
  const CTX = 2;
  const hunks = [];
  let k = 0;
  while (k < ops.length) {
    while (k < ops.length && ops[k][0] === "eq") k++;
    if (k >= ops.length) break;
    const hunkStart = Math.max(0, k - CTX);
    let end = k;
    while (end < ops.length) {
      if (ops[end][0] !== "eq") { end++; continue; }
      let run = 0;
      while (end + run < ops.length && ops[end + run][0] === "eq") run++;
      if (run > CTX * 2) { end += CTX; break; }
      end += run;
    }
    hunks.push([hunkStart, Math.min(ops.length, end)]);
    k = end;
  }

  if (!hunks.length) return "";
  const parts = [];
  hunks.forEach(([s, e], hIdx) => {
    if (hIdx > 0) parts.push(`<div class="hdr">…</div>`);
    let i = s;
    while (i < e) {
      const op = ops[i];
      if (op[0] === "eq") {
        parts.push(`<div class="line ctx">  ${escHtml(op[1])}</div>`);
        i++;
      } else {
        const dels = [];
        while (i < e && ops[i][0] === "del") { dels.push(ops[i][1]); i++; }
        const adds = [];
        while (i < e && ops[i][0] === "add") { adds.push(ops[i][2]); i++; }
        const pairs = Math.min(dels.length, adds.length);
        for (let p = 0; p < pairs; p++) {
          const [dH, aH] = inlineDelAdd(dels[p], adds[p]);
          parts.push(`<div class="line del">- ${dH}</div>`);
          parts.push(`<div class="line add">+ ${aH}</div>`);
        }
        for (let p = pairs; p < dels.length; p++) {
          parts.push(`<div class="line del">- ${escHtml(dels[p])}</div>`);
        }
        for (let p = pairs; p < adds.length; p++) {
          parts.push(`<div class="line add">+ ${escHtml(adds[p])}</div>`);
        }
      }
    }
  });
  return parts.join("");
}

// ----------------------------------------------------------------------------
// Search UI shared by both proofreaders.
//
// Contract:
//   createSearch({
//     navRoot,        // DOM element containing the <li data-sid="..."> entries
//     getIndex,       // () => [{id, text}, ...] — full searchable corpus
//     getCurrentId,   // () => current-selected id (string) or null
//     onSelect,       // (id) => void — host should select that entry
//   }) => {
//     element,             // DOM node to insert above the scrollable nav
//     applyHighlights(),   // re-mark <li data-sid> after a nav re-render
//     refresh(),           // recompute hits (call after corpus changed)
//     isActive(),          // bool — search query is non-empty
//   }
//
// Visual contract:
//   - When search is active, body.searching is set, so host CSS can dim
//     non-matching entries.
//   - Matching <li> get class "search-match".
//   - The N/M readout reflects the position of the currently-selected entry
//     among hits (0/M if it isn't a hit).
// ----------------------------------------------------------------------------

const SEARCH_CSS = `
.search-box {
  padding: 8px 10px;
  background: #efe7d4;
  border-bottom: 1px solid #d9cfb8;
  display: flex;
  align-items: center;
  gap: 6px;
}
.search-input-wrap {
  position: relative;
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
}
.search-input {
  flex: 1;
  padding: 5px 26px 5px 10px;
  font: inherit;
  font-size: 0.82rem;
  border: 1px solid #c9a86a;
  border-radius: 2px;
  background: #fffaf0;
  color: #2a2520;
  outline: none;
  min-width: 0;
}
.search-input:focus {
  border-color: #8a6a3a;
  box-shadow: 0 0 0 2px rgba(201, 168, 106, 0.28);
}
.search-clear {
  position: absolute;
  right: 6px;
  top: 50%;
  transform: translateY(-50%);
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #c9a86a;
  color: #2a2520;
  font-size: 0.8rem;
  line-height: 18px;
  text-align: center;
  cursor: pointer;
  user-select: none;
  font-weight: bold;
}
.search-clear:hover { background: #d8b878; }
.search-box button.search-step {
  padding: 3px 7px;
  font: inherit;
  font-size: 0.78rem;
  cursor: pointer;
  background: transparent;
  border: 1px solid #c9a86a;
  border-radius: 2px;
  color: #4a3f32;
  flex-shrink: 0;
}
.search-box button.search-step:hover:not(:disabled) {
  background: rgba(201, 168, 106, 0.18);
  color: #2a2520;
}
.search-box button.search-step:disabled { opacity: 0.35; cursor: not-allowed; border-color: #c9bfa3; }
.search-count {
  font-variant-numeric: tabular-nums;
  font-size: 0.74rem;
  letter-spacing: 0.06em;
  color: #6a5a3a;
  flex-shrink: 0;
  min-width: 3.4em;
  text-align: right;
}
.search-count.empty { color: #a89678; }

body.searching #nav li:not(.search-match) { opacity: 0.32; }
#nav li.search-match {
  box-shadow: inset 2px 0 0 #8a6a3a;
}
#nav li.search-match.active {
  box-shadow: inset 3px 0 0 #c9a86a;
}
`;

function injectSearchCss() {
  if (document.getElementById("__proofread_search_css")) return;
  const style = document.createElement("style");
  style.id = "__proofread_search_css";
  style.textContent = SEARCH_CSS;
  document.head.appendChild(style);
}

function createSearch({ navRoot, getIndex, getCurrentId, onSelect, onQueryChanged }) {
  injectSearchCss();

  const root = document.createElement("div");
  root.className = "search-box";
  root.innerHTML = `
    <div class="search-input-wrap">
      <input type="search" class="search-input" placeholder="Search all text…" spellcheck="false">
      <span class="search-clear" hidden title="Clear search (Esc)">×</span>
    </div>
    <button class="search-step search-prev" type="button" hidden title="Previous match (Shift+Enter)">↑</button>
    <button class="search-step search-next" type="button" hidden title="Next match (Enter)">↓</button>
    <span class="search-count" hidden>0 / 0</span>
  `;

  const inp = root.querySelector(".search-input");
  const clearBtn = root.querySelector(".search-clear");
  const countEl = root.querySelector(".search-count");
  const prevBtn = root.querySelector(".search-prev");
  const nextBtn = root.querySelector(".search-next");

  let query = "";
  let hits = []; // ordered list of ids that match, in corpus order

  function recompute() {
    const q = query.trim().toLowerCase();
    if (!q) {
      hits = [];
    } else {
      const idx = getIndex() || [];
      hits = [];
      for (const rec of idx) {
        if (rec.text && rec.text.toLowerCase().includes(q)) hits.push(rec.id);
      }
    }
    update();
  }

  function update() {
    const active = !!query.trim();
    document.body.classList.toggle("searching", active);
    clearBtn.hidden = !active;
    prevBtn.hidden = !active;
    nextBtn.hidden = !active;
    countEl.hidden = !active;
    if (active) {
      const curId = getCurrentId && getCurrentId();
      const pos = curId ? hits.indexOf(curId) : -1;
      const n = pos >= 0 ? pos + 1 : 0;
      countEl.textContent = `${n} / ${hits.length}`;
      countEl.classList.toggle("empty", hits.length === 0);
      prevBtn.disabled = hits.length === 0;
      nextBtn.disabled = hits.length === 0;
    }
    applyHighlights();
    if (onQueryChanged) onQueryChanged(query.trim());
  }

  function applyHighlights() {
    if (!navRoot) return;
    const set = new Set(hits);
    navRoot.querySelectorAll("li[data-sid]").forEach(li => {
      li.classList.toggle("search-match", set.has(li.getAttribute("data-sid")));
    });
  }

  function step(dir) {
    if (hits.length === 0) return;
    const curId = getCurrentId && getCurrentId();
    let pos = curId ? hits.indexOf(curId) : -1;
    if (pos === -1) {
      // Not currently on a hit — start from the appropriate end.
      pos = dir > 0 ? -1 : hits.length;
    }
    const next = (pos + dir + hits.length) % hits.length;
    onSelect(hits[next]);
  }

  inp.addEventListener("input", () => {
    query = inp.value;
    recompute();
  });
  inp.addEventListener("keydown", e => {
    if (e.key === "Enter") {
      e.preventDefault();
      step(e.shiftKey ? -1 : 1);
    } else if (e.key === "Escape") {
      e.preventDefault();
      clearBtn.click();
    }
  });
  clearBtn.addEventListener("click", () => {
    inp.value = "";
    query = "";
    recompute();
    inp.focus();
  });
  prevBtn.addEventListener("click", () => step(-1));
  nextBtn.addEventListener("click", () => step(1));

  return {
    element: root,
    applyHighlights,
    refresh: () => { recompute(); },
    update,
    isActive: () => !!query.trim(),
    getQuery: () => query.trim(),
  };
}

window.ProofreadShared = { escHtml, lcs, tokenize, renderUnifiedDiff, highlightHTML, createSearch };
})();
