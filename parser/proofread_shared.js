// Shared utilities for the kriegstagebuch and audio proofreading tools.
// Exposed on window.ProofreadShared.
(() => {

function escHtml(s) {
  return String(s).replace(/[&<>]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
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

window.ProofreadShared = { escHtml, lcs, tokenize, renderUnifiedDiff };
})();
