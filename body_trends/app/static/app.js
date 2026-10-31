const $ = (id) => document.getElementById(id);
const RANGES = {W: 7, M: 30, "3M": 90, Y: 365, All: 0};
const state = {user: null, range: "M", offset: 0, data: null, users: []};
const DAY = 864e5;
const j = async (url, opts) => { const r = await fetch(url, opts); if (!r.ok) throw new Error(url + " " + r.status); return r.json(); };
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));
const f1 = (x, d = 1) => (x == null ? "–" : Number(x).toFixed(d));

function window_() {
  const days = RANGES[state.range];
  if (!days) return [null, null];
  const end = new Date(Date.now() - state.offset * days * DAY);
  return [new Date(+end - days * DAY), end];
}

function lineChart(series, {unit = "", forecast = null, outliers = [], h = 220} = {}) {
  const W = 700, pad = {l: 40, r: 10, t: 10, b: 22};
  const pts = series.value.map((v, i) => [+new Date(series.ts[i]), v, series.trend[i]]);
  if (!pts.length) return '<p class="muted">No data in this range</p>';
  const fc = forecast ? forecast.t.map((d, i) => [+new Date(state.data.t0) + d * DAY, forecast.mean[i], forecast.low[i], forecast.high[i]]) : [];
  const xs = [...pts.map((p) => p[0]), ...fc.map((p) => p[0])];
  const ys = [...pts.flatMap((p) => [p[1], p[2]]), ...fc.flatMap((p) => [p[2], p[3]])];
  const [x0, x1] = [Math.min(...xs), Math.max(...xs)], [y0, y1] = [Math.min(...ys), Math.max(...ys)];
  const X = (x) => pad.l + ((x - x0) / (x1 - x0 || 1)) * (W - pad.l - pad.r);
  const Y = (y) => h - pad.b - ((y - y0) / (y1 - y0 || 1)) * (h - pad.t - pad.b);
  const path = (a) => a.map((p, i) => (i ? "L" : "M") + X(p[0]).toFixed(1) + " " + Y(p[1]).toFixed(1)).join("");
  let s = `<svg viewBox="0 0 ${W} ${h}" role="img">`;
  for (let i = 0; i <= 4; i++) { const y = y0 + ((y1 - y0) * i) / 4;
    s += `<line x1="${pad.l}" x2="${W - pad.r}" y1="${Y(y)}" y2="${Y(y)}" stroke="var(--line)"/><text x="${pad.l - 4}" y="${Y(y) + 3}" text-anchor="end">${f1(y)}</text>`; }
  for (let i = 0; i <= 4; i++) { const x = x0 + ((x1 - x0) * i) / 4;
    s += `<text x="${X(x)}" y="${h - 6}" text-anchor="middle">${new Date(x).toLocaleDateString(undefined, {month: "short", day: "numeric"})}</text>`; }
  if (fc.length) {
    s += `<path d="${path(fc.map((p) => [p[0], p[3]]))}L${[...fc].reverse().map((p) => X(p[0]).toFixed(1) + " " + Y(p[2]).toFixed(1)).join("L")}Z" fill="var(--accent)" opacity=".15"/>`;
    s += `<path d="${path(fc)}" fill="none" stroke="var(--accent)" stroke-dasharray="4 3"/>`;
  }
  pts.forEach((p) => (s += `<circle cx="${X(p[0])}" cy="${Y(p[1])}" r="2.5" fill="var(--muted)" opacity=".7"><title>${new Date(p[0]).toLocaleString()}: ${f1(p[1], 2)} ${unit}</title></circle>`));
  s += `<path d="${path(pts.map((p) => [p[0], p[2]]))}" fill="none" stroke="var(--accent)" stroke-width="2.5"/></svg>`;
  return s;
}

function barChart(rows, key = "mean", h = 160) {
  if (!rows.length) return '<p class="muted">No data</p>';
  const W = 700, vals = rows.map((r) => r[key]), lo = Math.min(...vals) - 0.5, hi = Math.max(...vals) + 0.1;
  const bw = W / rows.length;
  return `<svg viewBox="0 0 ${W} ${h}">` + rows.map((r, i) => {
    const bh = ((r[key] - lo) / (hi - lo || 1)) * (h - 30);
    return `<rect x="${i * bw + 2}" y="${h - 20 - bh}" width="${bw - 4}" height="${bh}" fill="var(--accent)" rx="3"><title>${r.period}: ${f1(r[key], 2)} (n=${r.n})</title></rect>` +
      (rows.length <= 16 ? `<text x="${i * bw + bw / 2}" y="${h - 6}" text-anchor="middle">${r.period.slice(-3)}</text>` : "");
  }).join("") + "</svg>";
}

function rateTile(label, s, unit) {
  if (!s) return `<div class="tile"><div class="muted">${label}</div><div class="big">–</div></div>`;
  const cls = s.plateau ? "muted" : s.per_week > 0 ? "pos" : "neg";
  return `<div class="tile"><div class="muted">${label}</div><div class="big ${cls}">${s.per_week > 0 ? "+" : ""}${f1(s.per_week, 2)}</div><div class="muted">${unit}/wk${s.plateau ? " · plateau" : ""}</div></div>`;
}

function render() {
  const d = state.data, u = state.users.find((x) => x.slug === state.user) || {};
  if (!d || !d.n) { $("cards").innerHTML = '<p class="muted">No measurements for this user in the selected range.</p>'; return; }
  const S = d.summary, w = d.series.weight, cards = [];
  cards.push(`<div class="card wide"><h2>Weight</h2><div class="tiles"><div class="tile"><div class="big">${f1(S.trend_weight)} kg</div><div class="muted">trend · latest ${f1(S.latest_weight)} kg</div></div>
    ${S.bmi_trend ? `<div class="tile"><div class="big">${f1(S.bmi_trend)}</div><div class="muted">BMI · ${esc(S.bmi_band)}</div></div>` : ""}
    ${S.goal_weight ? `<div class="tile"><div class="big">${S.goal_eta || "–"}</div><div class="muted">goal ${f1(S.goal_weight)} kg ETA</div></div>` : ""}</div>
    ${lineChart(w, {unit: "kg", forecast: d.forecast})}</div>`);
  cards.push(`<div class="card"><h2>Rate of change · weight</h2><div class="tiles">${[7, 30, 90].map((n) => rateTile(n + "d", d.trends.weight[n + "d"], "kg")).join("")}</div></div>`);
  if (d.series.bodyFatPercent) {
    const b = d.series.bodyFatPercent;
    cards.push(`<div class="card"><h2>Body fat</h2><div class="big">${f1(b.trend.at(-1))} %</div><div class="muted">${esc(S.body_fat_band || "set sex in profile for category")} · impedance estimates are noisy; read the trend</div>${lineChart(b, {unit: "%", h: 140})}</div>`);
    cards.push(`<div class="card"><h2>Composition</h2><table><tr><th></th><th>Value</th></tr>
      <tr><td>Fat mass</td><td>${f1(S.fat_mass)} kg</td></tr><tr><td>Lean mass</td><td>${f1(S.lean_mass)} kg</td></tr>
      <tr><td>FFMI (normalized)</td><td>${f1(S.ffmi)}</td></tr></table>
      <div class="tiles">${[30, 90].map((n) => rateTile("Body fat " + n + "d", d.trends.bodyFatPercent?.[n + "d"], "%")).join("")}</div></div>`);
  }
  cards.push(`<div class="card"><h2>Weekly mean weight</h2>${barChart(d.weekly.slice(-26))}</div>`);
  const dows = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  cards.push(`<div class="card"><h2>Weekday vs trend (kg)</h2><table>${Object.entries(d.weekday_offsets).map(([k, v]) => `<tr><td>${dows[k]}</td><td>${v > 0 ? "+" : ""}${f1(v, 2)}</td></tr>`).join("") || '<tr><td class="muted">Needs more data</td></tr>'}</table></div>`);
  cards.push(`<div class="card"><h2>Data quality</h2><table><tr><td>Readings</td><td>${S.n_readings}</td></tr><tr><td>Flagged outliers (excluded)</td><td>${S.n_outliers}</td></tr>
    <tr><td>First</td><td>${S.first.slice(0, 10)}</td></tr><tr><td>Last</td><td>${S.last.slice(0, 10)}</td></tr></table></div>`);
  cards.push(`<div class="card"><h2>Profile</h2><form class="profile" id="profile">
    <label>Height (cm)</label><input name="height_cm" type="number" step="0.1" value="${u.height_cm ?? ""}">
    <label>Birth year</label><input name="birth_year" type="number" value="${u.birth_year ?? ""}">
    <label>Sex</label><select name="sex"><option value="">–</option><option ${u.sex === "male" ? "selected" : ""}>male</option><option ${u.sex === "female" ? "selected" : ""}>female</option></select>
    <label>Goal weight (kg)</label><input name="goal_weight" type="number" step="0.1" value="${u.goal_weight ?? ""}">
    <span></span><button>Save</button></form></div>`);
  $("cards").innerHTML = cards.join("");
  $("profile").onsubmit = async (e) => {
    e.preventDefault();
    const body = {};
    new FormData(e.target).forEach((v, k) => { if (v !== "") body[k] = ["sex"].includes(k) ? v : Number(v); });
    await j("api/users/" + encodeURIComponent(state.user), {method: "PUT", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
    await load();
  };
}

async function load() {
  state.users = await j("api/users");
  const sel = $("user");
  sel.innerHTML = state.users.map((u) => `<option value="${esc(u.slug)}">${esc(u.slug)}</option>`).join("");
  if (!state.users.length) { $("cards").innerHTML = '<p class="muted">Waiting for the first weigh-in from BLE Scale Sync (or import history via POST api/import/&lt;user&gt;).</p>'; return; }
  if (!state.users.some((u) => u.slug === state.user)) state.user = state.users[0].slug;
  sel.value = state.user;
  const [a, b] = window_();
  $("label").textContent = a ? `${a.toLocaleDateString()} – ${b.toLocaleDateString()}` : "All time";
  const q = a ? `?start=${a.toISOString()}&end=${b.toISOString()}` : "";
  state.data = await j(`api/users/${encodeURIComponent(state.user)}/analysis${q}`);
  render();
}

$("ranges").innerHTML = Object.keys(RANGES).map((r) => `<button data-r="${r}" class="${r === state.range ? "on" : ""}">${r}</button>`).join("");
$("ranges").onclick = (e) => { const r = e.target.dataset.r; if (!r) return; state.range = r; state.offset = 0;
  document.querySelectorAll("#ranges button").forEach((b) => b.classList.toggle("on", b.dataset.r === r)); load(); };
$("prev").onclick = () => { state.offset++; load(); };
$("next").onclick = () => { state.offset = Math.max(0, state.offset - 1); load(); };
$("user").onchange = (e) => { state.user = e.target.value; load(); };
$("export").onclick = () => {
  const [a, b] = window_();
  const p = new URLSearchParams({user: state.user, format: $("fmt").value, anonymize: $("anon").checked});
  if (a) { p.set("start", a.toISOString()); p.set("end", b.toISOString()); }
  location.href = "api/export?" + p;
};
load().catch((e) => ($("cards").innerHTML = `<p class="pos">${esc(e.message)}</p>`));
