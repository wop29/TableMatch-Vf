/* Tablematch prototype front end. Plain JavaScript, no build step. */
const $ = (s, el = document) => el.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const money = n => { n = Number(n || 0); return "$" + n.toLocaleString("en-US", { minimumFractionDigits: Number.isInteger(n) ? 0 : 2, maximumFractionDigits: 2 }); };
const fmtDate = d => new Date(d + "T12:00:00").toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
const plural = (n, w) => `${n} ${w}${n === 1 ? "" : "s"}`;
const store = {
  get(k, d) { try { const v = localStorage.getItem("pc_" + k); return v === null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem("pc_" + k, JSON.stringify(v)); } catch { /* storage can be blocked */ } },
};

const PREFS = { text: store.get("text", 0), still: store.get("still", false) };
function applyPrefs() {
  document.documentElement.classList.toggle("ts-1", PREFS.text === 1);
  document.documentElement.classList.toggle("ts-2", PREFS.text === 2);
  document.documentElement.classList.toggle("reduce-motion", !!PREFS.still);
}
applyPrefs();

const S = {
  meta: null,
  role: store.get("role", "sponsor"),
  sponsorId: store.get("sponsorId", null),
  clubId: store.get("clubId", null),
  tab: store.get("tab", { sponsor: "find", host: "dinners", platform: "overview" }),
  sf: { query: "", budget: "", slot_type: "" }, sfData: null, filters: {},
  hf: { event_id: null, guests: "", funding: "", notes: "" }, hfData: null, sort: "match",
  hidden: new Set(),
};

const TABS = {
  sponsor: [["find", "Find events"], ["deals", "My deals"]],
  host: [["dinners", "My events"], ["sponsors", "Find sponsors"], ["inbox", "Inbox"]],
  platform: [["overview", "Overview"], ["review", "Review queue"], ["payouts", "Payouts"], ["fees", "Fees"]],
};
const TAB_ICON = {
  find: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="M15.5 15.5L21 21"/>',
  deals: '<path d="M6 3h12v18l-3-2-3 2-3-2-3 2z"/><path d="M9 8h6M9 12h6"/>',
  dinners: '<path d="M3 10h18"/><path d="M6 10v10M18 10v10"/><circle cx="8" cy="5" r="1.5"/><circle cx="12" cy="5" r="1.5"/><circle cx="16" cy="5" r="1.5"/>',
  sponsors: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c.6-3.6 3.3-5.5 6.5-5.5s5.9 1.9 6.5 5.5"/><path d="M17 5.5a3.2 3.2 0 010 6M18.5 14.8c2 .6 3.2 2.2 3.5 5"/>',
  inbox: '<path d="M3 13l3-8h12l3 8v6H3z"/><path d="M3 13h5l1.5 2.5h5L16 13h5"/>',
  overview: '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
  review: '<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
  payouts: '<path d="M3 12h15M13 6l6 6-6 6"/>',
  fees: '<path d="M19 5L5 19"/><circle cx="7" cy="7" r="2.5"/><circle cx="17" cy="17" r="2.5"/>',
};
const icon = k => `<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${TAB_ICON[k]}</svg>`;
const matchWord = n => (n >= 80 ? "Strong match" : n >= 50 ? "Good match" : "Possible match");
const ROLE_NAME = { sponsor: "Sponsor", host: "Host", platform: "Platform" };

// ------------------------------------------------------------ helpers
async function api(path, method = "GET", body) {
  const opt = { method, headers: {} };
  if (body instanceof FormData) opt.body = body;
  else if (body !== undefined) { opt.headers["Content-Type"] = "application/json"; opt.body = JSON.stringify(body); }
  let r;
  try { r = await fetch(path, opt); } catch { throw new Error("We could not reach the server. Check that it is still running, then try again."); }
  let data = null;
  try { data = await r.json(); } catch { /* empty body */ }
  if (!r.ok) throw new Error((data && (data.detail?.[0]?.msg || data.detail)) || `Request failed (${r.status})`);
  return data;
}
function toast(msg, bad) {
  const el = document.createElement("div");
  el.className = "toast" + (bad ? " bad" : "");
  el.textContent = msg;
  $("#toasts").append(el);
  setTimeout(() => el.remove(), bad ? 6000 : 3800);
}
function dialog(html) {
  const d = $("#dlg");
  d.innerHTML = `<div class="dlg">${html}</div>`;
  if (!d.open) d.showModal();
  return d;
}
const closeDialog = () => { const d = $("#dlg"); if (d.open) d.close(); };
const sponsor = () => S.meta.sponsors.find(s => s.id === S.sponsorId) || S.meta.sponsors[0];
const club = () => S.meta.clubs.find(c => c.id === S.clubId) || S.meta.clubs[0];
const IC = {
  ok: '<svg class="ok" width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><path d="M3 8.5l3.2 3L13 4.5" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  no: '<svg class="no" width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><path d="M4 4l8 8M12 4l-8 8" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/></svg>',
};

function pill(status, label) { return `<span class="pill st-${esc(status)}">${esc(label || status.replaceAll("_", " "))}</span>`; }

function ticket(p, o = {}) {
  return `<div class="ticket" aria-label="Payout breakdown">
    ${o.stamp ? '<span class="stamp">Paid out</span>' : ""}
    <div class="t-row"><span>${esc(o.sponsorLabel || "Sponsor pays")}</span><b>${money(p.price)}</b></div>
    <div class="t-row t-fee"><span>Platform fee, ${Math.round(p.rate * 1000) / 10}% (cap ${money(p.cap)})</span><b>-${money(p.fee)}</b></div>
    <div class="t-tear"></div>
    <div class="t-row t-net"><span>${esc(o.netLabel || "Host receives")}</span><b>${money(p.net)}</b></div>
    ${p.capped ? `<p class="t-cap">Cap applied. ${Math.round(p.rate * 1000) / 10}% would have been ${money(Math.round(p.price * p.rate * 100) / 100)}.</p>` : ""}
  </div>`;
}

function tracker(o) {
  const steps = ["Paid into escrow", "Photos checked", "Verified", "Paid out"];
  const at = { awaiting_payment: -1, in_escrow: 0, under_review: 1, ready_for_payout: 2, released: 3 }[o.status];
  if (o.status === "refunded") return "";
  return `<ol class="track" aria-label="Order progress">${steps.map((s, i) => {
    const cls = i < at ? "done" : i === at ? "done now" : "";
    return `<li class="${cls}">${s}</li>`;
  }).join("")}</ol>`;
}

function proofBlock(o, withNote = true) {
  const p = o.latest_proof;
  if (!p) return "";
  const who = p.mode === "claude" ? "AI check" : "Demo check";
  const tone = p.decision === "verified" ? "" : p.decision === "rejected" ? "bad" : "warn";
  return `<div class="proof">
    <div class="photos">${p.photos.map(u => `<a href="${esc(u)}" target="_blank" rel="noopener"><img src="${esc(u)}" alt="Placement photo submitted by the host"></a>`).join("")}</div>
    <ul class="checks">${p.checks.map(c => `<li>${c.ok ? IC.ok : IC.no}<span>${esc(c.label)}</span></li>`).join("")}</ul>
    ${(p.links || []).length ? `<p class="sub">Post links: ${p.links.map(u => `<a href="${esc(u)}" target="_blank" rel="noopener noreferrer">${esc(u.replace(/^https?:\/\//, "").slice(0, 40))}</a>`).join(", ")}</p>` : ""}
    ${withNote ? `<p class="note ${tone}"><b>${who}: ${pill(p.decision, p.decision.replaceAll("_", " "))}</b> ${Math.round(p.confidence * 100)}% confidence. ${esc(p.notes)}${p.reviewer_note ? ` Reviewer: ${esc(p.reviewer_note)}` : ""}</p>` : ""}
  </div>`;
}

function tent(s, { dim = false, actions = "" } = {}) {
  return `<div class="tent ${dim ? "dim" : ""}">
    <div class="tent-top"><h4>${esc(s.title)}</h4><p>${esc(s.specs)}</p><small>Proof: ${plural(s.photos_required, "photo")}</small></div>
    <div class="tent-fold"></div>
    <div class="tent-bottom"><span class="price num">${money(s.price)}</span><span class="acts">${actions}</span></div>
  </div>`;
}

// ------------------------------------------------------------ shell
function renderShell() {
  document.body.dataset.role = S.role;
  $("#roles").innerHTML = Object.keys(TABS).map(r =>
    `<button type="button" data-act="role" data-role="${r}" aria-pressed="${r === S.role}">${ROLE_NAME[r]}</button>`).join("");
  const sel = $("#persona");
  const lab = $("#persona-label");
  if (S.role === "sponsor") {
    lab.textContent = "Acting as"; sel.hidden = false; lab.parentElement.hidden = false;
    sel.innerHTML = S.meta.sponsors.map(s => `<option value="${s.id}" ${s.id === sponsor().id ? "selected" : ""}>${esc(s.name)}</option>`).join("");
  } else if (S.role === "host") {
    lab.textContent = "Acting as"; lab.parentElement.hidden = false;
    sel.innerHTML = S.meta.clubs.map(c => `<option value="${c.id}" ${c.id === club().id ? "selected" : ""}>${esc(c.name)}</option>`).join("");
  } else {
    lab.parentElement.hidden = true;
  }
  $("#tabs").innerHTML = TABS[S.role].map(([k, label]) =>
    `<button type="button" data-act="tab" data-tab="${k}" ${S.tab[S.role] === k ? 'aria-current="page"' : ""}>${icon(k)}<span>${label}</span><span class="badge" data-badge="${k}" hidden></span></button>`).join("");
}

async function updateBadges() {
  let counts = {};
  try {
    if (S.role === "sponsor") {
      const [offers, orders] = await Promise.all([api(`/api/offers?sponsor_id=${sponsor().id}`), api(`/api/orders?sponsor_id=${sponsor().id}`)]);
      counts.deals = offers.filter(o => o.from_side === "host" && o.status === "pending").length + orders.filter(o => o.status === "awaiting_payment").length;
    } else if (S.role === "host") {
      const [offers, orders] = await Promise.all([api(`/api/offers?club_id=${club().id}`), api(`/api/orders?club_id=${club().id}`)]);
      counts.inbox = offers.filter(o => o.from_side === "sponsor" && o.status === "pending").length + orders.filter(o => o.status === "in_escrow").length;
    } else {
      const orders = await api("/api/orders");
      counts.review = orders.filter(o => o.status === "under_review").length;
      counts.payouts = orders.filter(o => o.status === "ready_for_payout").length;
    }
  } catch { /* badges are a nicety */ }
  document.querySelectorAll("[data-badge]").forEach(b => { const n = counts[b.dataset.badge] || 0; b.hidden = !n; b.textContent = n; });
}

async function render() {
  renderShell();
  const app = $("#app");
  document.body.classList.remove("in-detail");
  try {
    const view = VIEWS[S.role][S.tab[S.role]];
    app.innerHTML = await view();
  } catch (e) {
    app.innerHTML = `<p class="note bad">Something went wrong: ${esc(e.message)}. Check that the server is still running, then reload.</p>`;
  }
  updateBadges();
}

// ------------------------------------------------------------ sponsor views
async function runSponsorSearch() {
  S.sfData = await api("/api/search/events", "POST", {
    query: S.sf.query, sponsor_id: sponsor().id,
    budget: S.sf.budget === "" ? null : Number(S.sf.budget), slot_type: S.sf.slot_type || null,
    filters: S.filters,
  });
}
const nice = t => String(t || "").replace(/-/g, " ");
const catName = k => (S.meta.categories || {})[k] || k;
function breakdownHTML(b, title) {
  return `<div class="why"><h3>${esc(title || "Why this matches")}</h3><ul class="factors">${b.map(f => `<li class="${f.score === null ? "off" : ""}">
    <div class="f-top"><span>${esc(f.label)} <small>${f.weight}%</small></span><b>${f.score === null ? "Not used" : f.score + "%"}</b></div>
    <div class="bar thin"><i style="width:${f.score || 0}%"></i></div>
    ${f.note ? `<small class="f-note">${esc(f.note)}</small>` : ""}</li>`).join("")}</ul>
    <p class="tag-note">Factors you did not describe are left out, and the rest are re-weighted.</p></div>`;
}
function hiddenNote(h) {
  if (!h) return "";
  const bits = [];
  if (h.filters) bits.push(`${plural(h.filters, "event")} outside your filters`);
  if (h.budget) bits.push(`${h.budget} over budget`);
  if (h.category) bits.push(`${h.category} already ${h.category === 1 ? "has" : "have"} a brand in your category`);
  if (h.capacity) bits.push(`${h.capacity} at sponsor capacity`);
  if (h.excluded) bits.push(`${h.excluded} where the host excludes your category`);
  return bits.length ? `<p class="read hidden-note">Not shown: ${bits.join(", ")}.</p>` : "";
}
function filterBar() {
  const m = S.meta, f = S.filters;
  const sel = (key, label, opts) => `<label class="fsel ${f[key] ? "set" : ""}"><span>${label}</span><select data-act-change="filter" data-key="${key}"><option value="">Any</option>${opts.map(([v, t]) => `<option value="${esc(v)}" ${String(f[key] || "") === String(v) ? "selected" : ""}>${esc(t)}</option>`).join("")}</select></label>`;
  const n = Object.values(f).filter(Boolean).length;
  return `<div class="filters" role="group" aria-label="Filters">
    ${sel("kind", "Type", Object.entries(m.kinds))}
    ${sel("borough", "Borough", [["Brooklyn", "Brooklyn"], ["Manhattan", "Manhattan"], ["Queens", "Queens"]])}
    ${sel("audience", "Guests", m.audiences.map(a => [a, nice(a)]))}
    ${sel("interest", "Interest", m.interests.map(a => [a, a]))}
    ${sel("vibe", "Vibe", m.vibes.map(a => [a, nice(a)]))}
    ${sel("format", "Format", Object.entries(m.formats))}
    ${sel("age_group", "Age group", m.age_groups.map(a => [a, a]))}
    ${sel("max_guests", "Size", [["30", "Up to 30 guests"], ["60", "Up to 60 guests"], ["200", "Any size"]])}
    ${sel("within_days", "When", [["14", "Next 2 weeks"], ["30", "Next 30 days"], ["60", "Next 60 days"]])}
    ${n ? `<button type="button" class="link-btn" data-act="clear-filters">Clear ${plural(n, "filter")}</button>` : ""}
  </div><p class="tag-note filter-note">Filters are must-haves and remove events. Your description is a preference and ranks what is left.</p>`;
}
function parsedLine(p) {
  const bits = [];
  if (p.vibes.length) bits.push(`vibe <b>${esc(p.vibes.join(", "))}</b>`);
  if (p.audiences.length) bits.push(`guests <b>${esc(p.audiences.join(", "))}</b>`);
  if (p.places.length) bits.push(`in <b>${esc(p.places.join(", "))}</b>`);
  if (p.budget) bits.push(`up to <b>${money(p.budget)}</b>`);
  return (bits.length ? `We read your brief as: ${bits.join(", ")}.` : "No brief yet, so these are ranked by your brand profile.") + ` <button class="link-btn" data-act="match-info">How matching works</button>`;
}
const PLATE = '<svg viewBox="0 0 120 90" fill="none" stroke="#9a9a9a" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M10 52h100"/><path d="M20 52v22M100 52v22"/><circle cx="36" cy="38" r="7"/><circle cx="60" cy="38" r="7"/><circle cx="84" cy="38" r="7"/></svg>';
function cover(ev, big) {
  if (ev.cover) return `<img src="${esc(ev.cover)}" alt="${esc(ev.title)}" loading="lazy">`;
  return `<div class="ph tone-${ev.id % 4}" role="img" aria-label="No photo yet for ${esc(ev.title)}">${PLATE}<span>Photo coming soon</span></div>`;
}
const FAVS = new Set(store.get("fav", []));
const HEART = '<svg width="24" height="24" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 21s-7.5-4.6-9.6-9.4C.9 8.2 2.9 4.5 6.6 4.5c2 0 3.5 1 4.4 2.5.9-1.5 2.4-2.5 4.4-2.5 3.7 0 5.7 3.7 4.2 7.1C19.5 16.4 12 21 12 21z"/></svg>';
const kindName = k => ((S.meta && S.meta.kinds) || {})[k] || "Event";
const roughly = n => n >= 100 ? `over ${Math.floor(n / 50) * 50}` : String(n);
const listCap = t => t ? t.charAt(0).toUpperCase() + t.slice(1) : t;
function evCard(r) {
  const ev = r.event, open = ev.slots.filter(s => s.status === "open");
  const from = open.length ? Math.min(...open.map(s => s.price)) : 0;
  const saved = FAVS.has(ev.id);
  return `<article class="lcard"><button class="lcard-btn" data-act="open-event" data-ev="${ev.id}" aria-label="Open ${esc(ev.title)}, ${r.score}% match">
    <div class="lcard-art">${cover(ev)}<span class="tag">${r.score}% match</span></div>
    <p class="kind">${esc(kindName(ev.kind))}${ev.interested ? ` <span>${ev.interested.toLocaleString("en-US")} interested</span>` : ""}</p>
    <h3>${esc(ev.title)}</h3>
    <p>${esc(ev.club_name)} in ${esc(ev.neighborhood)}, ${esc(ev.borough)}</p>
    <p>${esc(listCap(ev.vibes.map(nice).join(", ")))}, for ${esc(ev.audiences.map(nice).join(", "))}</p>
    <p>${fmtDate(ev.date)}, ${ev.guests} guests</p>
    <p class="lprice"><b class="num">From ${money(from)}</b> per slot, ${plural(open.length, "slot")} open</p>
  </button>
  <button class="heart" type="button" data-act="fav" data-ev="${ev.id}" aria-pressed="${saved}" aria-label="Save ${esc(ev.title)}">${HEART}</button></article>`;
}
function pickHTML(list) {
  if (!list.length) return "";
  const r = list[0], ev = r.event, sp = sponsor();
  const q = ev.interested ? `, with ${roughly(ev.interested)} people interested` : "";
  return `<section class="pick" aria-label="Picked for ${esc(sp.name)}">
    <div class="pick-art">${cover(ev, true)}</div>
    <div class="pick-body"><span class="eyebrow-tag">Picked for ${esc(sp.name)}, ${r.score}% match</span>
      <h2>Does ${esc(sp.name)} want to sponsor ${esc(ev.title)}${esc(q)}?</h2>
      <p class="sub">${esc(kindName(ev.kind))} in ${esc(ev.neighborhood)}, ${fmtDate(ev.date)}. ${esc(r.reasons.slice(0, 2).join(". "))}.</p>
      <p style="margin-top:12px"><button class="btn primary" data-act="open-event" data-ev="${ev.id}">See the event</button></p></div></section>`;
}
function sortedResults(list) {
  const arr = [...list];
  const minp = r => Math.min(...r.event.slots.filter(s => s.status === "open").map(s => s.price));
  if (S.sort === "soon") arr.sort((a, b) => a.event.date.localeCompare(b.event.date));
  else if (S.sort === "price") arr.sort((a, b) => minp(a) - minp(b));
  else if (S.sort === "interest") arr.sort((a, b) => (b.event.interested || 0) - (a.event.interested || 0));
  return arr; // "match" keeps the server's ranking untouched
}
function sponsorResults() {
  document.body.classList.remove("in-detail");
  const d = S.sfData;
  if (!d) return "";
  if (S.openEv) {
    const r = d.results.find(x => x.event.id === S.openEv);
    if (r) return eventDetail(r);
  }
  if (!d.results.length) return `<div class="rhead"><div><p class="read">${parsedLine(d.parsed)}</p>${hiddenNote(d.hidden)}</div></div><div class="empty"><p>No dinners match just yet. Try broadening your audience or budget.</p><p style="margin-top:12px"><button class="btn primary" data-act="clear-search">Clear search and filters</button></p></div>`;
  return `<div class="rhead"><div><p class="read"><b>${plural(d.results.length, "event")}</b> found</p><p class="read">${parsedLine(d.parsed)}</p>${hiddenNote(d.hidden)}</div>
    <label class="sort"><span>Sort by</span><select data-act-change="sort" aria-label="Sort dinners"><option value="match" ${S.sort === "match" ? "selected" : ""}>Best match</option><option value="soon" ${S.sort === "soon" ? "selected" : ""}>Soonest</option><option value="price" ${S.sort === "price" ? "selected" : ""}>Lowest price</option><option value="interest" ${S.sort === "interest" ? "selected" : ""}>Most interested</option></select></label></div>
    ${pickHTML(d.results)}
    <div class="lgrid">${sortedResults(d.results).map(evCard).join("")}</div>`;
}
// A mock of the placement the sponsor is buying, drawn with the brand's name (no real logos).
function placementMock(type, sp, ev) {
  ev = Object.assign({ club_name: "", neighborhood: "" }, ev);
  const name = esc(sp.name), col = esc(sp.color || "#263f33"), title = esc(ev.title);
  const word = `<span class="mk-word" style="color:${col}">${name}</span>`;
  const M = {
    menu: `<div class="mk mk-menu"><small>${esc(ev.club_name)}</small><b>Tonight</b><i></i><i></i><i class="short"></i><div class="mk-foot">Menu supported by ${word}</div></div>`,
    drink: `<div class="mk mk-drink"><div class="mk-glass" style="--c:${col}"></div><div><small>Welcome drink</small><b>The ${name} Spritz</b><span>Poured for every guest on arrival</span></div></div>`,
    gift: `<div class="mk mk-gift"><div class="mk-bag" style="--c:${col}"><span>${name}</span></div><div><small>Take-home gift</small><b>A little something from ${name}</b><span>With a printed card in every bag</span></div></div>`,
    table: `<div class="mk mk-table"><div class="mk-tent"><small>This table is set by</small>${word}</div><div class="mk-plates"><i></i><i></i><i></i></div></div>`,
    display: `<div class="mk mk-screen" style="--c:${col}"><div class="mk-tv"><small>Welcome to ${title}</small><b>${name}</b></div><span>Shown at arrival and between courses</span></div>`,
    title: `<div class="mk mk-invite"><small>${name} presents</small><b>${title}</b><span>${fmtDate(ev.date)}, ${esc(ev.neighborhood)}</span><div class="mk-foot">Name on every invitation, plus a two-minute welcome</div></div>`,
  };
  return M[type] || M.menu;
}
function eventDetail(r) {
  const ev = r.event, open = ev.slots.filter(s => s.status === "open");
  if (!open.some(s => s.id === S.pickSlot)) S.pickSlot = (open.find(s => r.matching_slot_ids.includes(s.id)) || open[0]).id;
  const pick = open.find(s => s.id === S.pickSlot);
  document.body.classList.add("in-detail");
  return `<p class="read"><button class="link-btn" data-act="back">Back to results</button></p>
  <h1>${esc(ev.title)}</h1>
  <div class="gallery">${cover(ev, true)}</div>
  <div class="detail">
    <div>
      <h2>${esc(ev.club_name)}, ${esc(ev.neighborhood)}, ${esc(ev.borough)}</h2>
      <div class="meta"><span>${esc(kindName(ev.kind))}</span><span>${fmtDate(ev.date)}</span><span>${ev.guests} guests</span>${ev.interested ? `<span>${ev.interested.toLocaleString("en-US")} interested</span>` : ""}<span>Hosted by ${esc(ev.host_name)}</span></div>
      <p class="desc">${esc(ev.description)}</p>
      <div class="reasons">${r.reasons.map(x => `<span>${esc(x)}</span>`).join("")}</div>
      ${breakdownHTML(r.breakdown, `Why this matches: ${r.score}%`)}
      <hr class="rule">
      <h2>How payment works</h2>
      <ol class="steps"><li>You pay Tablematch when you buy a slot. The host does not get the money yet.</li>
        <li>After the dinner, the host uploads photos of your placement. Each slot below says how many it needs.</li>
        <li>Once the photos pass the check, Tablematch pays the host. Our fee comes out of the host's payout, not out of your price.</li>
        <li>If the placement is not verified, the platform can refund you.</li></ol>
      <hr class="rule">
      <h2>Slots you can sponsor</h2>
      <div class="offers" role="radiogroup" aria-label="Choose a slot">${open.map(s => `<label class="offer ${s.id === S.pickSlot ? "on" : ""} ${r.matching_slot_ids.includes(s.id) ? "" : "dim"}">
        <input type="radio" name="slot" value="${s.id}" data-act-change="pick" ${s.id === S.pickSlot ? "checked" : ""}>
        <span><b>${esc(s.title)}</b><br><span class="sub">${esc(s.specs)} Proof: ${plural(s.photos_required, "photo")}.</span></span>
        <b class="num">${money(s.price)}</b></label>`).join("")}</div>
    </div>
    <aside class="reserve" aria-label="Sponsor this event">
      <div class="mockwrap"><p class="mock-label">Preview: how ${esc(sponsor().name)} would appear</p>${placementMock(pick.type, sponsor(), ev)}</div>
      <p><b class="price num">${money(pick.price)}</b> <span class="sub">for ${esc(pick.title.toLowerCase())}</span></p>
      <button class="btn primary block" data-act="buy" data-slot="${pick.id}" data-ev="${ev.id}">Buy slot</button>
      <button class="btn block" data-act="bid" data-slot="${pick.id}" data-ev="${ev.id}">Place bid</button>
      <p class="sub center tag-note">Your payment is held until the host proves your placement.</p>
      <p class="sub center tag-note">${ev.density.sponsors} of ${ev.density.max_sponsors} sponsor spots taken. One brand per category.</p>
    </aside>
  </div>`;
}
async function sponsorFind() {
  const sp = sponsor();
  if (!S.sfData) await runSponsorSearch();
  const types = Object.entries(S.meta.slot_types);
  const chips = ["Hip, trendy Brooklyn creatives.", "Foodies in Queens, up to $800.", "Upscale couples who like live music.", "Young professionals who care about wellness."];
  return `<section class="intro"><span class="eyebrow-tag">Good brands. Great tables.</span><h1>Find events for ${esc(sp.name)}</h1>
    <p class="lede">Supper clubs, swap meets, artist talks, run clubs and listening parties whose guests are the people you want to reach.</p></section>
  <form class="pill-search" data-form="sponsor-search" role="search">
    <label class="seg-f grow"><span>Who do you want to reach?</span><input id="sf-q" type="text" placeholder="Hip, trendy Brooklyn creatives." value="${esc(S.sf.query)}"></label>
    <label class="seg-f"><span>Budget per slot</span><input id="sf-b" type="number" min="0" step="any" inputmode="numeric" placeholder="No limit" value="${esc(S.sf.budget)}"></label>
    <label class="seg-f"><span>Slot type</span><select id="sf-t"><option value="">Any</option>${types.map(([k, v]) => `<option value="${k}" ${S.sf.slot_type === k ? "selected" : ""}>${esc(v)}</option>`).join("")}</select></label>
    <button class="go" type="submit" aria-label="Find my audience"><svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true"><circle cx="7.5" cy="7.5" r="5.5" fill="none" stroke="currentColor" stroke-width="2"/><path d="M12 12l4.5 4.5" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg></button>
  </form>
  <div class="examples" role="group" aria-label="Suggested searches">
    ${chips.map(t => `<button type="button" class="chip ${S.sf.query === t ? "on" : ""}" aria-pressed="${S.sf.query === t}" data-act="example" data-text="${esc(t)}">${esc(t)}</button>`).join("")}</div>
  <div id="filterbar">${filterBar()}</div>
  <div id="results">${sponsorResults()}</div>`;
}

async function sponsorDeals() {
  const sp = sponsor();
  const [offers, orders] = await Promise.all([api(`/api/offers?sponsor_id=${sp.id}`), api(`/api/orders?sponsor_id=${sp.id}`)]);
  const incoming = offers.filter(o => o.from_side === "host" && o.status === "pending");
  const bids = offers.filter(o => o.from_side === "sponsor");
  const orderRows = orders.map(o => `<div class="row has-mock">
      <div class="deal-mock" aria-label="Preview of the placement">${placementMock(o.slot.type, Object.assign({}, sp, o.sponsor), Object.assign({ club_name: o.club.name }, o.event))}</div>
      <div><h3>${esc(o.slot.title)} at ${esc(o.event.title)}</h3>
        <p class="sub">${esc(o.club.name)}, ${fmtDate(o.event.date)}. ${esc(o.source === "buy" ? "Bought at list price" : o.source === "bid" ? "Your bid was accepted" : "Host offer you accepted")}.</p>
        ${tracker(o)}
        ${o.status === "in_escrow" && !o.latest_proof ? `<p class="note">Your ${money(o.price)} is held by Tablematch. ${esc(o.club.host_name)} will upload photos of your placement.</p>` : ""}
        ${o.status === "in_escrow" && o.latest_proof ? `<p class="note bad">The photos did not pass. The host has been asked to retake them, and your money stays held.</p>` : ""}
        ${o.status === "ready_for_payout" && !o.signoff ? `<div class="note signoff"><b>Your placement was verified.</b> Please confirm it looks right, or dispute it. If you do nothing, it confirms itself after 72 hours.
          <span class="acts" style="margin-top:8px"><button class="btn primary small" data-act="signoff" data-id="${o.id}" data-d="confirm">Confirm placement</button><button class="btn small" data-act="signoff" data-id="${o.id}" data-d="dispute">Dispute</button></span></div>` : ""}
        ${o.signoff ? `<p class="sub" style="margin-top:6px">${o.signoff === "confirmed" ? "You confirmed this placement." : "You disputed this placement. Tablematch is reviewing it."}</p>` : ""}
        ${o.latest_proof ? `<details${o.status === "ready_for_payout" && !o.signoff ? " open" : ""}><summary>Proof from the host</summary>${proofBlock(o)}</details>` : ""}
      </div>
      <div class="side"><b class="price num">${money(o.price)}</b>${pill(o.status, o.status_label)}
        ${o.status === "awaiting_payment" ? `<span class="acts"><button class="btn primary small" data-act="pay" data-id="${o.id}">Pay ${money(o.price)}</button><button class="btn small" data-act="cancel" data-id="${o.id}">Cancel</button></span>` : ""}
      </div></div>`).join("");
  return `<section class="intro"><h1>My deals</h1><p class="lede">Your money is held by Tablematch until the host proves your placement happened.</p></section>
  ${incoming.length ? `<section class="sect"><h2>Offers from hosts</h2><div class="rows">${incoming.map(o => `<div class="row">
      <div><div class="deal-mock inline">${placementMock(o.slot.type, sp, Object.assign({ club_name: o.club.name, neighborhood: "" }, o.event))}</div><h3>${esc(o.club.name)} offers you ${esc(o.slot.title)}</h3><p class="sub">${esc(o.event.title)}, ${fmtDate(o.event.date)}. List price ${money(o.slot.price)}.</p>
      ${o.message ? `<p class="note" style="margin-top:8px">${esc(o.message)}</p>` : ""}</div>
      <div class="side"><b class="price num">${money(o.amount)}</b><span class="acts"><button class="btn primary small" data-act="decide" data-id="${o.id}" data-d="accept">Accept offer</button><button class="btn small" data-act="decide" data-id="${o.id}" data-d="decline">Decline</button></span></div></div>`).join("")}</div></section>` : ""}
  <section class="sect"><h2>Orders</h2>${orders.length ? `<div class="rows">${orderRows}</div>` : `<div class="empty"><p>No orders yet. Find an event and buy a slot or place a bid.</p><p style="margin-top:12px"><button class="btn primary" data-act="goto" data-role="sponsor" data-tab="find">Find events</button></p></div>`}</section>
  ${bids.length ? `<section class="sect"><h2>Your bids</h2><div class="rows">${bids.map(o => `<div class="row"><div><h3>${esc(o.slot.title)} at ${esc(o.event.title)}</h3><p class="sub">${esc(o.club.name)}. List price ${money(o.slot.price)}.</p></div><div class="side"><b class="price num">${money(o.amount)}</b>${pill(o.status)}</div></div>`).join("")}</div></section>` : ""}`;
}

// ------------------------------------------------------------ host views
async function hostDinners() {
  const c = club();
  const events = await api(`/api/events?club_id=${c.id}`);
  return `<section class="intro"><h1>${esc(c.name)}</h1><p class="lede">Describe each dinner, set what it costs and what sponsors can buy. Tablematch works out the funding gap and keeps the evening from feeling too commercial.</p>
    <p style="margin-top:14px"><button class="btn primary" data-act="new-event">Add a dinner</button></p></section>
  ${events.length ? events.map(ev => {
    const f = ev.funding, d = ev.density;
    return `<article class="event">
      <div class="ev-head"><div class="ev-top"><div class="thumb">${cover(ev)}</div><div><h2>${esc(ev.title)}</h2><div class="meta"><span>${fmtDate(ev.date)}</span><span>${ev.guests} guests</span><span>${esc((S.meta.formats || {})[ev.format] || "")}</span>${ev.age_group ? `<span>Ages ${esc(ev.age_group)}</span>` : ""}</div>
        <p class="sub">${esc([...ev.vibes.map(nice), ...(ev.interests || [])].join(", "))}${(ev.preferred_cats || []).length ? `. Prefers ${esc(ev.preferred_cats.map(catName).join(", ").toLowerCase())}` : ""}${(ev.excluded_cats || []).length ? `. Excludes ${esc(ev.excluded_cats.map(catName).join(", ").toLowerCase())}` : ""}.</p></div></div>
        <div class="acts"><button class="btn small" data-act="edit-event" data-ev="${ev.id}">Edit dinner profile</button><label class="cover-edit">${ev.cover ? "Change cover photo" : "Add cover photo"}<input type="file" accept="image/*" data-act-change="cover" data-ev="${ev.id}"></label><button class="btn small" data-act="new-slot" data-ev="${ev.id}">Add a slot</button></div></div>
      <div class="calc">
        <div class="calc-grid" aria-label="Funding calculator">
          <div><span>Event cost</span><b class="num">${money(f.total_cost)}</b></div>
          <div><span>Ticket revenue</span><b class="num">${money(f.ticket_revenue)}</b><small>${ev.guests} × ${money(f.ticket_price)}</small></div>
          <div><span>Funding gap</span><b class="num">${money(f.gap)}</b></div>
          <div><span>Sponsors committed</span><b class="num">${money(f.gross)}</b><small>${money(f.net)} to you after ${money(f.fee)} fee</small></div>
          <div class="hl"><span>Still to raise</span><b class="num">${money(f.remaining)}</b><small>${f.pct}% of the gap covered</small></div>
        </div>
        <div class="bar" role="img" aria-label="${f.pct} percent of the funding gap covered"><i style="width:${f.pct}%"></i></div>
        <div class="calc-foot">
          <p class="density ${d.flag ? "warn" : ""}"><b>Sponsorship density: ${esc(d.level)}.</b> ${d.sponsors} of ${d.max_sponsors} sponsor spots used, ${plural(d.placements, "placement")}${d.flag ? ". This may feel too commercial for guests. Consider lowering placements." : "."}</p>
          ${f.remaining > 0 && f.recommended.length ? (f.recommended_net >= f.remaining
            ? `<p class="sub">To close the gap, sell: ${f.recommended.map(r => `${esc(r.title)} (${money(r.price)})`).join(", ")}. That brings in about ${money(f.recommended_net)} after fees.</p>`
            : `<p class="sub">Best you can do with open slots and sponsor spots: ${f.recommended.map(r => `${esc(r.title)} (${money(r.price)})`).join(", ")}, about ${money(f.recommended_net)} after fees. That still leaves ${money(f.remaining - f.recommended_net)} to raise, so consider higher prices, another slot, a higher ticket price or more sponsor spots.</p>`) : f.remaining > 0 ? `<p class="sub">${d.at_capacity ? "Sponsor capacity is reached. Raise it in the dinner profile or adjust ticket prices." : "Add slots or raise prices to close the gap."}</p>` : `<p class="sub">The funding gap is covered.</p>`}
        </div>
      </div>
      <div class="tablewrap" style="margin-top:14px"><table><thead><tr><th>Slot</th><th>What the sponsor gets</th><th class="r">Price</th><th>Status</th><th></th></tr></thead><tbody>
      ${ev.slots.filter(s => !S.hidden.has(s.id)).map(s => `<tr><td><b>${esc(s.title)}</b></td><td>${esc(s.specs)}</td>
        <td class="r">${s.status === "open" ? `<input type="number" min="1" step="any" value="${s.price}" aria-label="Price for ${esc(s.title)}" data-act-change="price" data-slot="${s.id}">` : `<span class="num">${money(s.price)}</span>`}</td>
        <td>${pill(s.order_status || s.status, s.order_status ? ({ awaiting_payment: "Awaiting payment", in_escrow: "Sold", under_review: "Sold", ready_for_payout: "Sold", released: "Paid out" })[s.order_status] : s.status === "open" ? "Open" : "Reserved")}</td>
        <td class="r">${s.status === "open" ? `<button class="btn small danger" data-act="del-slot" data-slot="${s.id}">Remove</button>` : ""}</td></tr>`).join("")}
      </tbody></table></div></article>`;
  }).join("") : `<div class="empty"><p>No dinners yet. Add one to start listing slots.</p><p style="margin-top:12px"><button class="btn primary" data-act="new-event">Add a dinner</button></p></div>`}`;
}

async function hostSponsors() {
  const c = club();
  const events = (await api(`/api/events?club_id=${c.id}`));
  if (!events.length) return `<section class="intro"><h1>Find sponsors</h1></section><div class="empty"><p>Add a dinner first, then come back to find sponsors for it.</p><p style="margin-top:12px"><button class="btn primary" data-act="goto" data-role="host" data-tab="dinners">Go to My dinners</button></p></div>`;
  if (!events.some(e => e.id === S.hf.event_id)) { const e = events[0]; S.hf = { event_id: e.id, guests: e.guests, funding: e.funding.remaining, notes: "" }; S.hfData = null; }
  return `<section class="intro"><h1>Find brands that make your next dinner possible</h1><p class="lede">Tell us the guest count and how much funding you need. We match you with brands from the demo list whose audience and budget fit your table.</p></section>
  <form class="finder host" data-form="host-search">
    <label class="field"><span>Dinner</span><select id="hf-e">${events.map(e => `<option value="${e.id}" ${e.id === S.hf.event_id ? "selected" : ""}>${esc(e.title)}, ${fmtDate(e.date)}</option>`).join("")}</select></label>
    <label class="field"><span>Guests</span><input id="hf-g" type="number" min="1" value="${esc(S.hf.guests)}" required></label>
    <label class="field"><span>Funding needed ($)</span><input id="hf-f" type="number" min="0" step="any" value="${esc(S.hf.funding)}" required></label>
    <label class="field grow"><span>What kind of brands belong at your table? <span class="hint">Optional, for example "coffee or snack brands"</span></span>
      <textarea id="hf-n" rows="2">${esc(S.hf.notes)}</textarea></label>
    <button class="btn primary" type="submit">Find brand partners</button>
  </form>
  <div id="results">${hostResults(events)}</div>`;
}
function hostResults(events) {
  const d = S.hfData;
  if (!d) return "";
  const ev = (events || []).find(e => e.id === S.hf.event_id);
  const pk = d.package;
  const pctc = pk.needed ? Math.min(100, Math.round(pk.covered / pk.needed * 100)) : 0;
  const h = d.hidden || {};
  const hid = [h.excluded ? `${plural(h.excluded, "brand")} in categories you exclude` : "", h.category ? `${h.category} in a category already taken at this dinner` : ""].filter(Boolean);
  return `<div class="pkg"><b>The best matches could cover ${money(pk.covered)} of the ${money(pk.needed)} still to raise.</b>${pk.room < 4 ? ` <span class="sub">You have room for ${plural(pk.room, "more sponsor")}.</span>` : ""}
    <div class="bar" style="max-width:420px"><i style="width:${pctc}%"></i></div>
    <p class="sub" style="margin-top:6px">${pk.items.length ? pk.items.map(i => `${esc(i.sponsor)} for ${esc(i.slot)} (${money(i.price)})`).join(", ") : "No open slots to suggest. Add slots or raise sponsor capacity first."}</p>
    ${hid.length ? `<p class="sub" style="margin-top:6px">Not shown: ${hid.join(", ")}.</p>` : ""}</div>
  <div class="rows">${d.results.map(r => {
    const sp = r.sponsor, sl = r.suggested_slot;
    return `<div class="row"><div>
      <h3>${esc(sp.name)} <span class="sub" style="font-weight:400">${esc(sp.category)}</span></h3>
      <p class="sub">${esc(sp.blurb)}</p>
      <div class="reasons">${r.reasons.map(x => `<span>${esc(x)}</span>`).join("")}</div>
      <details class="why-d"><summary>Score breakdown</summary>${breakdownHTML(r.breakdown, "How this score is built")}</details></div>
      <div class="side"><div class="match" style="text-align:left"><b>${matchWord(r.score)}, ${r.score}%</b><div class="bar" role="img" aria-label="${r.score} percent match"><i style="width:${r.score}%"></i></div></div>
      ${sl ? `<button class="btn primary small" data-act="propose" data-sp="${sp.id}" data-slot="${sl.id}">Offer ${esc(sl.title)} for ${money(sl.price)}</button>` : `<span class="sub">No open slot within their budget</span>`}</div></div>`;
  }).join("")}</div>`;
}

async function hostInbox() {
  const c = club();
  const [offers, orders] = await Promise.all([api(`/api/offers?club_id=${c.id}`), api(`/api/orders?club_id=${c.id}`)]);
  const bids = offers.filter(o => o.from_side === "sponsor" && o.status === "pending");
  const sent = offers.filter(o => o.from_side === "host");
  const orderRow = o => {
    const need = o.slot.photos_required;
    let body = "";
    if (o.status === "awaiting_payment") body = `<p class="note warn">Waiting for ${esc(o.sponsor.name)} to pay. Nothing to do yet.</p>`;
    if (o.status === "in_escrow") body = `<p class="note">${esc(o.sponsor.name)} has paid and ${money(o.price)} is held in escrow. Upload ${plural(need, "photo")} showing the ${esc(o.slot.title.toLowerCase())} at the dinner, with their branding clear.</p>
      ${o.latest_proof ? `<p class="note bad" style="margin-top:8px">Your last photos did not pass. Retake and submit again.</p>${proofBlock(o)}` : ""}
      <form class="upload proofform" data-form="proof" data-id="${o.id}">
        <label class="field"><span>Placement photos</span><input type="file" name="files" accept="image/*" multiple required></label>
        <label class="field"><span>Links to posts that tag ${esc(o.sponsor.name)} <span class="hint">Optional, one per line</span></span><textarea name="links" rows="2" placeholder="https://www.instagram.com/p/..."></textarea></label>
        <label class="field"><span>Guests who checked in <span class="hint">Optional, from your door list or check-in code</span></span><input name="checkins" type="number" min="0" step="any" placeholder="${o.event.guests}"></label>
        <button class="btn primary small" type="submit">Submit proof</button></form>
      <div class="samples"><span>No photos handy? Try a sample:</span>
        <button class="chip" data-act="sample" data-id="${o.id}" data-s="good">Clear photo</button>
        <button class="chip" data-act="sample" data-id="${o.id}" data-s="blurry">Blurry photo</button>
        <button class="chip" data-act="sample" data-id="${o.id}" data-s="wrong_brand">Wrong brand</button></div>`;
    if (o.status === "under_review") body = `<p class="note warn">The photos need a person to look at them. This is in the Tablematch review queue, and your funds stay protected.</p>${proofBlock(o, false)}`;
    if (o.status === "ready_for_payout") body = `<p class="note">Verified. Tablematch is preparing your payout.</p>${proofBlock(o, false)}<div style="margin-top:10px">${ticket(o.estimate, { sponsorLabel: "Sponsor paid", netLabel: "You receive" })}</div>`;
    if (o.status === "released") body = `<div style="margin-top:10px">${ticket({ price: o.price, fee: o.fee, net: o.net, rate: o.estimate.rate, cap: o.estimate.cap, capped: o.fee < o.price * o.estimate.rate - 0.005 }, { stamp: true, netLabel: "You received" })}</div>`;
    return `<div class="row"><div><h3>${esc(o.slot.title)} for ${esc(o.sponsor.name)}</h3><p class="sub">${esc(o.event.title)}, ${fmtDate(o.event.date)}</p>${tracker(o)}${body}</div>
      <div class="side"><b class="price num">${money(o.price)}</b>${pill(o.status, o.status_label)}</div></div>`;
  };
  return `<section class="intro"><h1>Inbox</h1><p class="lede">Answer bids, upload proof of placement, and see when you get paid.</p></section>
  <section class="sect"><h2>Bids to answer</h2>${bids.length ? `<div class="rows">${bids.map(o => `<div class="row"><div><h3>${esc(o.sponsor.name)} bids on ${esc(o.slot.title)}</h3><p class="sub">${esc(o.event.title)}, ${fmtDate(o.event.date)}. Your price is ${money(o.slot.price)}.</p>${o.message ? `<p class="note" style="margin-top:8px">${esc(o.message)}</p>` : ""}</div>
      <div class="side"><b class="price num">${money(o.amount)}</b><span class="acts"><button class="btn primary small" data-act="decide" data-id="${o.id}" data-d="accept">Accept bid</button><button class="btn small" data-act="decide" data-id="${o.id}" data-d="decline">Decline</button></span></div></div>`).join("")}</div>` : `<p class="empty">No bids waiting.</p>`}</section>
  <section class="sect"><h2>Sold slots</h2>${orders.length ? `<div class="rows">${orders.map(orderRow).join("")}</div>` : `<div class="empty"><p>Nothing sold yet. Sponsors can buy your open slots, or you can offer one in Find sponsors.</p><p style="margin-top:12px"><button class="btn primary" data-act="goto" data-role="host" data-tab="sponsors">Find sponsors</button></p></div>`}</section>
  ${sent.length ? `<section class="sect"><h2>Offers you sent</h2><div class="rows">${sent.map(o => `<div class="row"><div><h3>${esc(o.slot.title)} to ${esc(o.sponsor.name)}</h3><p class="sub">${esc(o.event.title)}</p></div><div class="side"><b class="price num">${money(o.amount)}</b>${pill(o.status)}</div></div>`).join("")}</div></section>` : ""}`;
}

// ------------------------------------------------------------ platform views
async function platOverview() {
  const [ov, orders, fb] = await Promise.all([api("/api/overview"), api("/api/orders"), api("/api/feedback")]);
  const s = S.meta.settings;
  return `<section class="intro"><h1>Platform overview</h1><p class="lede">Sponsors pay Tablematch, Tablematch holds the money, and the host is paid only after the placement is verified.</p></section>
  <dl class="stats">
    <div><dt>Held in escrow</dt><dd class="num">${money(ov.held)}</dd></div>
    <div><dt>Fees earned</dt><dd class="num">${money(ov.fees_earned)}</dd></div>
    <div><dt>Paid out to hosts</dt><dd class="num">${money(ov.paid_out)}</dd></div>
    <div><dt>Photo checks</dt><dd class="num">${money(ov.ai_cost)}</dd><small>${plural(ov.photos_checked, "photo")} checked</small></div>
  </dl>
  ${perfHTML(ov.performance)}
  <section class="sect"><h2>All deals</h2>${orders.length ? `<div class="tablewrap"><table><thead><tr><th>Dinner</th><th>Slot</th><th>Sponsor</th><th>Host</th><th class="r">Price</th><th>Status</th><th></th></tr></thead><tbody>
    ${orders.map(o => `<tr><td>${esc(o.event.title)}</td><td>${esc(o.slot.title)}</td><td>${esc(o.sponsor.name)}</td><td>${esc(o.club.name)}</td><td class="r num">${money(o.price)}</td><td>${pill(o.status, o.status_label)}</td>
      <td class="r">${["in_escrow", "under_review", "ready_for_payout"].includes(o.status) ? `<button class="btn small danger" data-act="refund" data-id="${o.id}">Refund sponsor</button>` : ""}</td></tr>`).join("")}</tbody></table></div>` : `<p class="empty">No deals yet.</p>`}</section>
  <section class="sect"><details><summary>Money movements</summary><div class="tablewrap"><table><thead><tr><th>Time</th><th>Order</th><th>What happened</th><th class="r">Amount</th></tr></thead><tbody>
    ${ov.ledger.map(l => `<tr><td>${esc(l.ts.replace("T", " "))}</td><td>#${l.order_id}</td><td>${esc(l.note)}</td><td class="r num">${money(l.amount)}</td></tr>`).join("")}</tbody></table></div></details></section>
  <section class="sect"><details><summary>Feedback from testers (${fb.length})</summary>${fb.length ? fb.map(f => `<div class="fbk"><b>${f.rating} of 5</b> <span class="sub">${esc(f.role || "visitor")} on ${esc(f.page || "unknown page")}, ${esc(f.ts.replace("T", " "))}</span>${f.message ? `<p>${esc(f.message)}</p>` : ""}</div>`).join("") : `<p class="empty">No feedback yet. Ask testers to use Give feedback in the footer.</p>`}</details></section>
  <p class="sub" style="margin-top:20px;color:var(--muted)">Verification mode: ${S.meta.verify_mode === "claude" ? "AI reads the photos with Claude." : "demo checks (set ANTHROPIC_API_KEY to let AI read the photos)."} Fee: ${Math.round(s.fee_rate * 1000) / 10}%, capped at ${money(s.fee_cap)}.</p>`;
}

function perfHTML(p) {
  const v = x => x === null || x === undefined ? "No data yet" : x + "%";
  const tiles = [
    ["Match quality", "Offers accepted", v(p.match_to_deal), `${p.offers} offers so far`],
    ["Sponsor acquisition", "Search to booking", v(p.search_to_booking), `${p.deals} deals from ${p.searches} searches`],
    ["Host monetization", "Average sponsorship per funded dinner", money(p.avg_revenue_per_event), "Gross, before fees"],
    ["Funding", "Average funding gap covered", p.avg_gap_covered + "%", `Across ${p.events} dinners`],
    ["Liquidity", "Dinners with offers or deals", v(p.liquidity), "Listings getting relevant interest"],
    ["Trust", "Verified placement rate", v(p.verification_rate), "Of paid deals with photos submitted"],
    ["Retention", "Repeat sponsor rate", v(p.repeat_rate), "Sponsors with more than one deal"],
    ["Guest experience", "Guest satisfaction", "Not collected yet", p.heavy_events.length ? `${p.heavy_events.length} dinners flagged as too commercial` : "No dinners flagged as too commercial"],
  ];
  return `<section class="sect"><h2>Marketplace performance</h2><p class="lede" style="margin-bottom:16px">A baseline from activity in this demo. No targets are set yet: the pilot should establish them.</p>
    <div class="kpis">${tiles.map(([o, k, val, n]) => `<div class="kpi"><small>${esc(o)}</small><span>${esc(k)}</span><b class="num">${esc(val)}</b><em>${esc(n)}</em></div>`).join("")}</div></section>`;
}

async function platReview() {
  const orders = (await api("/api/orders?status=under_review"));
  return `<section class="intro"><h1>Review queue</h1><p class="lede">Photos the AI could not judge with enough confidence land here. Approve them to unlock the payout, or ask the host for new photos.</p></section>
  ${orders.length ? `<div class="rows">${orders.map(o => `<div class="row"><div><h3>${esc(o.slot.title)} for ${esc(o.sponsor.name)}</h3><p class="sub">${esc(o.event.title)} hosted by ${esc(o.club.name)}. Expected: ${esc(o.slot.specs)}</p>${proofBlock(o)}
      <label class="field" style="margin-top:10px"><span>Note to the host <span class="hint">Optional</span></span><input id="rv-${o.id}" type="text" placeholder="For example: logo is hidden behind the glass"></label></div>
      <div class="side"><b class="price num">${money(o.price)}</b><span class="acts"><button class="btn primary small" data-act="review" data-id="${o.id}" data-d="approve">Approve photos</button><button class="btn small danger" data-act="review" data-id="${o.id}" data-d="reject">Ask for new photos</button></span></div></div>`).join("")}</div>` : `<p class="empty">Nothing to review. Submit a real photo as a host in demo mode to see an item here.</p>`}`;
}

async function platPayouts() {
  const orders = await api("/api/orders?status=ready_for_payout");
  return `<section class="intro"><h1>Payouts</h1><p class="lede">Verified placements waiting for a transfer. The fee is deducted at the moment of transfer.</p></section>
  ${orders.length ? `<div class="rows">${orders.map(o => `<div class="row"><div><h3>${esc(o.slot.title)}, ${esc(o.event.title)}</h3><p class="sub">${esc(o.sponsor.name)} to ${esc(o.club.name)}. ${esc(o.note || "")}</p>
      <p class="sub">Sponsor sign-off: ${o.signoff === "confirmed" ? "confirmed" : "waiting (confirms itself after 72 hours)"}</p></div>
      <div class="side"><b class="price num">${money(o.price)}</b><button class="btn primary small" data-act="payout" data-id="${o.id}">Review transfer</button></div></div>`).join("")}</div>` : `<p class="empty">No payouts waiting. Verify a placement as a host to see one here.</p>`}`;
}

async function platFees() {
  const s = (await api("/api/meta")).settings; S.meta.settings = s;
  const samples = [300, 1000, 5000, 10000, 12000];
  const prev = await Promise.all(samples.map(p => api(`/api/fee-preview?price=${p}`)));
  return `<section class="intro"><h1>Fees and checks</h1><p class="lede">These are the placeholder numbers from the planning meeting. Change them here and every preview, ticket and payout follows.</p></section>
  <form class="finder four" data-form="settings">
    <label class="field"><span>Platform fee (%)</span><input id="st-rate" type="number" min="0" max="100" step="any" value="${Math.round(s.fee_rate * 1000) / 10}"></label>
    <label class="field"><span>Fee cap per transaction ($)</span><input id="st-cap" type="number" min="0" step="any" value="${s.fee_cap}"></label>
    <label class="field"><span>Cost per photo check ($)</span><input id="st-ai" type="number" min="0" step="any" value="${s.ai_cost_per_photo}"></label>
    <label class="field"><span>AI auto-verify confidence (%)</span><input id="st-conf" type="number" min="0" max="100" step="any" value="${Math.round(s.auto_verify_confidence * 100)}"></label>
    <div class="wide"><button class="btn primary" type="submit">Save settings</button></div>
  </form>
  <section class="sect"><h2>What the fee looks like</h2>
    <div class="tablewrap"><table><thead><tr><th class="r">Slot price</th><th class="r">Fee</th><th class="r">Host receives</th><th>Note</th></tr></thead><tbody>
    ${prev.map(p => `<tr><td class="r num">${money(p.price)}</td><td class="r num">${money(p.fee)}</td><td class="r num">${money(p.net)}</td><td>${p.capped ? `Cap applied, ${Math.round(p.rate * 1000) / 10}% would be ${money(Math.round(p.price * p.rate * 100) / 100)}` : ""}</td></tr>`).join("")}</tbody></table></div></section>
  <section class="sect"><h2>Matching weights</h2><p class="lede" style="margin-bottom:12px">Starting weights to test with users. Hard rules (filters, budget ceilings, excluded categories, one brand per category, sponsor capacity) apply before any scoring.</p>
    <div class="two">${[["sponsor", "Brands ranking dinners"], ["host", "Hosts ranking brands"]].map(([k, t]) => `<div><h3 style="margin-bottom:8px">${t}</h3><table><tbody>${S.meta.weights[k].map(([, l, w]) => `<tr><td>${esc(l)}</td><td class="r num">${w}%</td></tr>`).join("")}</tbody></table></div>`).join("")}</div></section>
  <section class="sect"><h2>What a photo check costs</h2><p class="lede">Checks are priced per photo, not per deal. A ${money(300)} menu mention and a ${money(12000)} title sponsorship that each need one photo cost the same to verify: about ${money(s.ai_cost_per_photo)} at this setting.</p></section>`;
}

const VIEWS = {
  sponsor: { find: sponsorFind, deals: sponsorDeals },
  host: { dinners: hostDinners, sponsors: hostSponsors, inbox: hostInbox },
  platform: { overview: platOverview, review: platReview, payouts: platPayouts, fees: platFees },
};

// ------------------------------------------------------------ actions
async function findSlot(slotId, evId) {
  const evs = await api("/api/events");
  const ev = evs.find(e => e.id === Number(evId));
  return { ev, slot: ev.slots.find(s => s.id === Number(slotId)) };
}

const ACTIONS = {
  async role(el) { S.role = el.dataset.role; store.set("role", S.role); await render(); },
  async tab(el) { S.tab[S.role] = el.dataset.tab; store.set("tab", S.tab); await render(); },
  async "open-event"(el) { S.openEv = Number(el.dataset.ev); S.pickSlot = null; $("#results").innerHTML = sponsorResults(); window.scrollTo({ top: 0 }); },
  async fav(el) {
    const id = Number(el.dataset.ev);
    FAVS.has(id) ? FAVS.delete(id) : FAVS.add(id);
    store.set("fav", [...FAVS]);
    el.setAttribute("aria-pressed", FAVS.has(id));
    toast(FAVS.has(id) ? "Saved to this browser." : "Removed from saved.");
  },
  async "clear-filters"() { S.filters = {}; S.openEv = null; await runSponsorSearch(); await render(); },
  async "edit-event"(el) {
    const ev = (await api(`/api/events?club_id=${club().id}`)).find(e => e.id === Number(el.dataset.ev));
    const m = S.meta;
    const checks = (name, opts, chosen) => `<div class="opts">${opts.map(([v, t]) => `<label><input type="checkbox" name="${name}" value="${esc(v)}" ${(chosen || []).includes(v) ? "checked" : ""}>${esc(t)}</label>`).join("")}</div>`;
    const cats = Object.entries(m.categories);
    dialog(`<h2>Dinner profile</h2><form class="stack" data-form="edit-event" data-ev="${ev.id}">
      <label class="field"><span>Title</span><input id="ee-t" value="${esc(ev.title)}" required></label>
      <div class="two"><label class="field"><span>Date</span><input id="ee-d" type="date" value="${esc(ev.date)}" required></label>
      <label class="field"><span>Guests</span><input id="ee-g" type="number" min="1" value="${ev.guests}" required></label></div>
      <div class="two"><label class="field"><span>Format</span><select id="ee-f">${Object.entries(m.formats).map(([k, v]) => `<option value="${k}" ${ev.format === k ? "selected" : ""}>${esc(v)}</option>`).join("")}</select></label>
      <label class="field"><span>Main age group</span><select id="ee-a"><option value="">Mixed</option>${m.age_groups.map(a => `<option ${ev.age_group === a ? "selected" : ""}>${a}</option>`).join("")}</select></label></div>
      <fieldset class="field fs"><legend>Atmosphere</legend>${checks("vibes", m.vibes.map(v => [v, nice(v)]), ev.vibes)}</fieldset>
      <fieldset class="field fs"><legend>Who comes</legend>${checks("audiences", m.audiences.map(v => [v, nice(v)]), ev.audiences)}</fieldset>
      <fieldset class="field fs"><legend>Guest interests</legend>${checks("interests", m.interests.map(v => [v, v]), ev.interests)}</fieldset>
      <h3>Costs</h3>
      <div class="two"><label class="field"><span>Total event cost ($)</span><input id="ee-c" type="number" min="0" step="any" value="${ev.funding.total_cost ?? 0}" required></label>
      <label class="field"><span>Ticket price per guest ($)</span><input id="ee-p" type="number" min="0" step="any" value="${ev.ticket_price ?? 0}" required></label></div>
      <h3>Sponsors</h3>
      <label class="field"><span>Most sponsors at this dinner <span class="hint">Keeps the evening from feeling too commercial</span></span><input id="ee-m" type="number" min="1" max="10" value="${ev.density.max_sponsors}" required></label>
      <fieldset class="field fs"><legend>Categories you would welcome</legend>${checks("pref", cats, ev.preferred_cats)}</fieldset>
      <fieldset class="field fs"><legend>Categories you do not want</legend>${checks("excl", cats, ev.excluded_cats)}</fieldset>
      <div class="btns"><button type="button" class="btn" data-act="close">Cancel</button><button class="btn primary" type="submit">Save profile</button></div></form>`);
  },
  async signoff(el) {
    if (el.dataset.d === "dispute" && !el.dataset.confirmed) {
      return dialog(`<h2>Dispute this placement?</h2><form class="stack" data-form="dispute" data-id="${el.dataset.id}">
        <label class="field"><span>What is wrong?</span><textarea id="dp-note" rows="3" required placeholder="For example: our name was not on the menu"></textarea></label>
        <p class="sub">The payout to the host pauses while Tablematch reviews the proof.</p>
        <div class="btns"><button type="button" class="btn" data-act="close">Cancel</button><button class="btn primary" type="submit">Send dispute</button></div></form>`);
    }
    await api(`/api/orders/${el.dataset.id}/signoff`, "POST", { decision: "confirm" });
    toast("Thanks. Placement confirmed."); await render();
  },
  async back() { S.openEv = null; $("#results").innerHTML = sponsorResults(); },
  async example(el) { S.openEv = null; S.sf.query = el.dataset.text; $("#sf-q").value = el.dataset.text; $("#sf-b").value = ""; S.sf.budget = ""; await submitSponsorSearch(); },
  async buy(el) {
    const { ev, slot } = await findSlot(el.dataset.slot, el.dataset.ev);
    dialog(`<h2>Buy ${esc(slot.title)}</h2>
      <p>${esc(ev.club_name)}, ${esc(ev.title)}, ${fmtDate(ev.date)}</p>
      <div class="how"><p><b>What happens next</b></p><ol class="steps"><li>You pay ${money(slot.price)} to Tablematch now. This demo moves no real money.</li><li>${esc(ev.host_name)} uploads ${plural(slot.photos_required, "photo")} of your placement at the dinner.</li><li>When the photos pass, Tablematch pays the host. If they do not, the platform can refund you.</li></ol></div>
      <p class="sub">${esc(slot.specs)}</p>
      <div class="btns"><button class="btn" data-act="close">Cancel</button><button class="btn primary" data-act="confirm-buy" data-slot="${slot.id}" data-price="${slot.price}">Buy slot for ${money(slot.price)}</button></div>`);
  },
  async "confirm-buy"(el) {
    const o = await api(`/api/slots/${el.dataset.slot}/buy`, "POST", { sponsor_id: sponsor().id });
    await api(`/api/orders/${o.id}/pay`, "POST");
    closeDialog(); toast(`Paid ${money(el.dataset.price)}. Your sponsorship is secured. We'll let you know when your placement is verified.`);
    S.sfData = null; S.openEv = null; S.tab.sponsor = "deals"; await render();
  },
  async bid(el) {
    const { ev, slot } = await findSlot(el.dataset.slot, el.dataset.ev);
    dialog(`<h2>Place a bid on ${esc(slot.title)}</h2><p>${esc(ev.club_name)}, ${esc(ev.title)}. List price ${money(slot.price)}.</p>
      <form class="stack" data-form="bid" data-slot="${slot.id}">
        <label class="field"><span>Your bid ($)</span><input id="bid-amt" type="number" min="1" step="any" value="${Math.round(slot.price * 0.85)}" required></label>
        <label class="field"><span>Message to the host <span class="hint">Optional</span></span><textarea id="bid-msg" rows="3" placeholder="Why your brand fits their guests"></textarea></label>
        <div class="btns"><button type="button" class="btn" data-act="close">Cancel</button><button class="btn primary" type="submit">Place bid</button></div></form>`);
  },
  async pay(el) { await api(`/api/orders/${el.dataset.id}/pay`, "POST"); toast("Paid. The money is held in escrow."); await render(); },
  async cancel(el) {
    if (!el.dataset.confirmed) return dialog(`<h2>Cancel this order?</h2><p>You have not paid yet, so nothing is charged. The slot opens up for other sponsors.</p><div class="btns"><button class="btn" data-act="close">Keep order</button><button class="btn primary" data-act="cancel" data-id="${el.dataset.id}" data-confirmed="1">Cancel order</button></div>`);
    closeDialog(); await api(`/api/orders/${el.dataset.id}/cancel`, "POST"); toast("Order cancelled. The slot is open again."); await render();
  },
  async decide(el) {
    const accept = el.dataset.d === "accept";
    if (!accept && !el.dataset.confirmed) {
      return dialog(`<h2>Decline this ${S.role === "host" ? "bid" : "offer"}?</h2><p>The other side will see it as declined. You cannot undo this.</p>
        <div class="btns"><button class="btn" data-act="close">Keep it</button><button class="btn primary" data-act="decide" data-id="${el.dataset.id}" data-d="decline" data-confirmed="1">Decline</button></div>`);
    }
    closeDialog();
    await api(`/api/offers/${el.dataset.id}/decision`, "POST", { decision: el.dataset.d });
    toast(accept ? (S.role === "sponsor" ? "Offer accepted. Pay to put the money in escrow." : "Bid accepted. The sponsor has been asked to pay.") : "Declined.");
    await render();
  },
  async "new-event"() {
    const c = club();
    dialog(`<h2>Add a dinner</h2><form class="stack" data-form="new-event">
      <label class="field"><span>Dinner title</span><input id="ne-t" required></label>
      <div class="two"><label class="field"><span>Date</span><input id="ne-d" type="date" required></label>
      <label class="field"><span>Guests</span><input id="ne-g" type="number" min="1" value="24" required></label></div>
      <div class="two"><label class="field"><span>Total event cost ($)</span><input id="ne-c" type="number" min="0" step="any" value="4000" required></label>
      <label class="field"><span>Ticket price per guest ($)</span><input id="ne-p" type="number" min="0" step="any" value="60" required></label></div>
      <p class="sub">The funding gap is the cost minus ticket revenue. You can add audience, format and sponsor preferences after.</p>
      <label class="field"><span>What the dinner is like</span><textarea id="ne-x" rows="2" placeholder="One or two sentences for sponsors"></textarea></label>
      <p class="sub">Vibe and guest tags start from ${esc(c.name)}'s profile.</p>
      <div class="btns"><button type="button" class="btn" data-act="close">Cancel</button><button class="btn primary" type="submit">Add dinner</button></div></form>`);
  },
  async "new-slot"(el) {
    dialog(`<h2>Add a slot</h2><form class="stack" data-form="new-slot" data-ev="${el.dataset.ev}">
      <label class="field"><span>Type</span><select id="ns-t">${Object.entries(S.meta.slot_types).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join("")}</select></label>
      <label class="field"><span>Price ($)</span><input id="ns-p" type="number" min="1" step="any" value="500" required></label>
      <label class="field"><span>Photos needed as proof</span><input id="ns-n" type="number" min="1" max="5" value="1" required></label>
      <label class="field"><span>What the sponsor gets <span class="hint">Leave blank to use the standard wording</span></span><textarea id="ns-s" rows="3"></textarea></label>
      <div class="btns"><button type="button" class="btn" data-act="close">Cancel</button><button class="btn primary" type="submit">Add slot</button></div></form>`);
  },
  async "del-slot"(el) {
    const id = Number(el.dataset.slot);
    S.hidden.add(id); await render();
    let undone = false;
    const t = document.createElement("div"); t.className = "toast";
    t.innerHTML = `Slot removed.<button class="undo" type="button">Undo</button>`;
    $("#toasts").append(t);
    t.querySelector(".undo").addEventListener("click", async () => { undone = true; S.hidden.delete(id); t.remove(); await render(); });
    setTimeout(async () => {
      t.remove();
      if (undone) return;
      try { await api(`/api/slots/${id}`, "DELETE"); } catch (e) { toast(e.message, true); }
      S.hidden.delete(id); await render();
    }, 6000);
  },
  async goto(el) { S.role = el.dataset.role; S.tab[S.role] = el.dataset.tab; store.set("role", S.role); store.set("tab", S.tab); await render(); },
  async "clear-search"() { S.sf = { query: "", budget: "", slot_type: "" }; S.filters = {}; S.openEv = null; S.sfData = null; await render(); },
  async "match-info"() {
    dialog(`<h2>How matching works</h2><div class="how"><p>Each dinner and sponsor in this demo list is tagged with vibes, guest types and a neighborhood. We compare your brief with those tags.</p>
      <ul class="steps"><li>Sponsors searching dinners: vibe 40%, guests 30%, location 20%, budget 10%.</li><li>Hosts searching sponsors: vibe 30%, guests 25%, location 15%, guest count 10%, budget 20%.</li></ul>
      <p>The percentage is a rough fit score on invented data. It does not predict sales or turnout.</p></div><div class="btns"><button class="btn primary" data-act="close">Got it</button></div>`);
  },
  async display() {
    dialog(`<h2>Display</h2>
      <fieldset class="field" style="border:0;padding:0;margin:0"><legend style="font-weight:600;margin-bottom:6px">Text size</legend>
        <div class="opts">${["Normal", "Large", "Largest"].map((l, i) => `<label><input type="radio" name="ts" value="${i}" data-act-change="textsize" ${PREFS.text === i ? "checked" : ""}>${l}</label>`).join("")}</div></fieldset>
      <div class="opts"><label><input type="checkbox" data-act-change="still" ${PREFS.still ? "checked" : ""}>Reduce animation</label></div>
      <div class="btns"><button class="btn primary" data-act="close">Done</button></div>`);
  },
  async welcome() {
    dialog(`<h2>Welcome to Tablematch</h2>
      <p>Good brands. Great tables. A demo marketplace where brands sponsor independent supper club dinners. The sponsors, clubs and dinners are made up, and no real money moves. You can switch sides any time from the top.</p>
      <div class="choice">
        <button data-act="pick-role" data-role="sponsor"><b>I want to sponsor dinners</b><span>Search for dinners that fit your brand, then buy a slot or place a bid.</span></button>
        <button data-act="pick-role" data-role="host"><b>I host dinners</b><span>List what sponsors can get, set prices, and find brands that fit your guests.</span></button>
        <button data-act="pick-role" data-role="platform"><b>I run the platform</b><span>Watch the money held, review photos, and confirm payouts.</span></button>
      </div>`);
  },
  async "pick-role"(el) { store.set("welcomed", true); closeDialog(); S.role = el.dataset.role; store.set("role", S.role); await render(); },
  async feedback() {
    dialog(`<h2>Give feedback</h2><form class="stack" data-form="feedback">
      <fieldset class="field" style="border:0;padding:0;margin:0"><legend style="font-weight:600;margin-bottom:6px">How easy was this to use?</legend>
        <div class="opts">${[["1", "Hard"], ["2", "Tricky"], ["3", "Okay"], ["4", "Easy"], ["5", "Very easy"]].map(([v, l]) => `<label><input type="radio" name="rate" value="${v}" required>${l}</label>`).join("")}</div></fieldset>
      <label class="field"><span>What was confusing, or what would you change? <span class="hint">Optional</span></span><textarea id="fb-msg" rows="4"></textarea></label>
      <div class="btns"><button type="button" class="btn" data-act="close">Cancel</button><button class="btn primary" type="submit">Send feedback</button></div></form>`);
  },
  async propose(el) {
    const events = await api(`/api/events?club_id=${club().id}`);
    const ev = events.find(e => e.id === S.hf.event_id);
    const slot = ev.slots.find(s => s.id === Number(el.dataset.slot));
    const sp = S.meta.sponsors.find(s => s.id === Number(el.dataset.sp));
    dialog(`<h2>Offer ${esc(slot.title)} to ${esc(sp.name)}</h2>
      <form class="stack" data-form="propose" data-slot="${slot.id}" data-sp="${sp.id}">
        <label class="field"><span>Price ($)</span><input id="pr-amt" type="number" min="1" step="any" value="${slot.price}" required></label>
        <label class="field"><span>Message</span><textarea id="pr-msg" rows="3">We think ${esc(sp.name)} would suit our guests at ${esc(ev.title)}.</textarea></label>
        <div class="btns"><button type="button" class="btn" data-act="close">Cancel</button><button class="btn primary" type="submit">Send offer</button></div></form>`);
  },
  async sample(el) {
    const fd = new FormData(); fd.append("scenario", el.dataset.s);
    const o = await api(`/api/orders/${el.dataset.id}/proof`, "POST", fd);
    proofToast(o); await render();
  },
  async review(el) {
    const note = ($(`#rv-${el.dataset.id}`) || {}).value || "";
    await api(`/api/orders/${el.dataset.id}/review`, "POST", { decision: el.dataset.d, note });
    toast(el.dataset.d === "approve" ? "Approved. The payout is ready." : "Sent back to the host for new photos."); await render();
  },
  async payout(el) {
    const p = await api(`/api/orders/${el.dataset.id}/payout-preview`);
    dialog(`<h2>Confirm transfer to host</h2><p>The fee is deducted now, so the host receives the net amount below.</p>${ticket(p)}
      <div class="btns"><button class="btn" data-act="close">Not yet</button><button class="btn primary" data-act="release" data-id="${el.dataset.id}">Transfer ${money(p.net)} to host</button></div>`);
  },
  async release(el) {
    const o = await api(`/api/orders/${el.dataset.id}/release`, "POST", { confirm: true });
    dialog(`<h2>Transferred</h2>${ticket({ price: o.price, fee: o.fee, net: o.net, rate: o.estimate.rate, cap: o.estimate.cap, capped: o.fee < o.price * o.estimate.rate - 0.005 }, { stamp: true, netLabel: "Sent to host" })}
      <div class="btns"><button class="btn primary" data-act="close">Done</button></div>`);
    await render();
  },
  async refund(el) {
    if (!el.dataset.confirmed) return dialog(`<h2>Refund the sponsor?</h2><p>The sponsor gets the full price back and the slot opens up again. The host is not paid for this slot. You cannot undo this.</p><div class="btns"><button class="btn" data-act="close">Not now</button><button class="btn primary" data-act="refund" data-id="${el.dataset.id}" data-confirmed="1">Refund sponsor</button></div>`);
    closeDialog(); await api(`/api/orders/${el.dataset.id}/refund`, "POST"); toast("Refunded to the sponsor. The slot is open again."); await render();
  },
  async reset() { await api("/api/reset", "POST"); S.sfData = null; S.hfData = null; S.meta = await api("/api/meta"); toast("Demo data reset."); await render(); },
  close() { closeDialog(); },
};

function proofToast(o) {
  const p = o.latest_proof;
  if (p.decision === "verified") toast("Photos verified. Tablematch can now pay you out.");
  else if (p.decision === "needs_review") toast("Photos passed the quality check and are waiting for a reviewer.");
  else toast("Photos rejected: " + p.notes, true);
}

async function submitSponsorSearch() {
  S.openEv = null;
  S.sf.query = $("#sf-q").value; S.sf.budget = $("#sf-b").value; S.sf.slot_type = $("#sf-t").value;
  await runSponsorSearch();
  $("#results").innerHTML = sponsorResults();
  document.querySelectorAll(".examples .chip").forEach(c => { const on = c.dataset.text === S.sf.query; c.classList.toggle("on", on); c.setAttribute("aria-pressed", on); });
}

const FORMS = {
  "sponsor-search": submitSponsorSearch,
  async "host-search"() {
    S.hf = { event_id: Number($("#hf-e").value), guests: $("#hf-g").value, funding: $("#hf-f").value, notes: $("#hf-n").value };
    S.hfData = await api("/api/search/sponsors", "POST", { event_id: S.hf.event_id, guests: Number(S.hf.guests), funding_needed: Number(S.hf.funding), notes: S.hf.notes });
    const events = await api(`/api/events?club_id=${club().id}`);
    $("#results").innerHTML = hostResults(events);
  },
  async bid(form) {
    await api(`/api/slots/${form.dataset.slot}/bids`, "POST", { sponsor_id: sponsor().id, amount: Number($("#bid-amt").value), message: $("#bid-msg").value });
    closeDialog(); toast("Bid placed. You will see the answer in My deals."); S.sfData = null; S.openEv = null; S.tab.sponsor = "deals"; await render();
  },
  async "new-event"() {
    await api(`/api/clubs/${club().id}/events`, "POST", { title: $("#ne-t").value, date: $("#ne-d").value, guests: Number($("#ne-g").value), total_cost: Number($("#ne-c").value), ticket_price: Number($("#ne-p").value), description: $("#ne-x").value });
    closeDialog(); toast("Dinner added. Now add slots for sponsors."); await render();
  },
  async "edit-event"(form) {
    const vals = n => [...form.querySelectorAll(`input[name=${n}]:checked`)].map(i => i.value);
    await api(`/api/events/${form.dataset.ev}`, "PATCH", {
      title: $("#ee-t").value, date: $("#ee-d").value, guests: Number($("#ee-g").value), format: $("#ee-f").value,
      age_group: $("#ee-a").value, vibes: vals("vibes"), audiences: vals("audiences"), interests: vals("interests"),
      total_cost: Number($("#ee-c").value), ticket_price: Number($("#ee-p").value), max_sponsors: Number($("#ee-m").value),
      preferred_cats: vals("pref"), excluded_cats: vals("excl"),
    });
    closeDialog(); toast("Dinner profile saved. Matching and the funding gap are updated."); S.hfData = null; S.sfData = null; await render();
  },
  async dispute(form) {
    await api(`/api/orders/${form.dataset.id}/signoff`, "POST", { decision: "dispute", note: $("#dp-note").value });
    closeDialog(); toast("Dispute sent. The payout is paused while we review."); await render();
  },
  async "new-slot"(form) {
    await api(`/api/events/${form.dataset.ev}/slots`, "POST", { type: $("#ns-t").value, price: Number($("#ns-p").value), photos_required: Number($("#ns-n").value), specs: $("#ns-s").value || null });
    closeDialog(); toast("Slot added."); await render();
  },
  async propose(form) {
    await api("/api/proposals", "POST", { slot_id: Number(form.dataset.slot), sponsor_id: Number(form.dataset.sp), amount: Number($("#pr-amt").value), message: $("#pr-msg").value });
    closeDialog(); toast("Offer sent. It shows in your Inbox under Offers you sent."); updateBadges();
  },
  async proof(form) {
    const fd = new FormData();
    [...form.querySelector("input[type=file]").files].forEach(f => fd.append("files", f));
    fd.append("links", form.querySelector("[name=links]").value);
    fd.append("checkins", form.querySelector("[name=checkins]").value);
    const o = await api(`/api/orders/${form.dataset.id}/proof`, "POST", fd);
    proofToast(o); await render();
  },
  async feedback() {
    const rate = document.querySelector("input[name=rate]:checked");
    await api("/api/feedback", "POST", { rating: Number(rate.value), message: $("#fb-msg").value, role: S.role, page: S.tab[S.role] });
    closeDialog(); toast("Thanks. Your feedback was saved.");
  },
  async settings() {
    S.meta.settings = await api("/api/settings", "PUT", {
      fee_rate: Number($("#st-rate").value) / 100, fee_cap: Number($("#st-cap").value),
      ai_cost_per_photo: Number($("#st-ai").value), auto_verify_confidence: Number($("#st-conf").value) / 100,
    });
    toast("Settings saved."); await render();
  },
};

// ------------------------------------------------------------ wiring
document.addEventListener("click", async e => {
  const el = e.target.closest("[data-act]");
  if (!el) return;
  e.preventDefault();
  try { await ACTIONS[el.dataset.act](el); } catch (err) { toast(err.message, true); }
});
document.addEventListener("submit", async e => {
  const form = e.target.closest("[data-form]");
  if (!form) return;
  e.preventDefault();
  const btn = form.querySelector("button[type=submit]"); const label = btn && btn.textContent;
  if (btn) { btn.disabled = true; if (form.dataset.form === "proof") btn.textContent = "Checking photos"; }
  try { await FORMS[form.dataset.form](form); } catch (err) { toast(err.message, true); }
  finally { if (btn && btn.isConnected) { btn.disabled = false; btn.textContent = label; } }
});
document.addEventListener("change", async e => {
  const el = e.target;
  if (el.id === "persona") {
    const id = Number(el.value);
    if (S.role === "sponsor") { S.sponsorId = id; store.set("sponsorId", id); S.sfData = null; }
    else { S.clubId = id; store.set("clubId", id); S.hfData = null; S.hf.event_id = null; }
    await render();
  } else if (el.dataset.actChange === "textsize") {
    PREFS.text = Number(el.value); store.set("text", PREFS.text); applyPrefs();
  } else if (el.dataset.actChange === "still") {
    PREFS.still = el.checked; store.set("still", PREFS.still); applyPrefs();
  } else if (el.dataset.actChange === "filter") {
    S.filters[el.dataset.key] = el.value; S.openEv = null;
    try { await runSponsorSearch(); } catch (err) { toast(err.message, true); }
    const fb = $("#filterbar"); if (fb) fb.innerHTML = filterBar();
    $("#results").innerHTML = sponsorResults();
  } else if (el.dataset.actChange === "sort") {
    S.sort = el.value; $("#results").innerHTML = sponsorResults();
  } else if (el.dataset.actChange === "cover") {
    const f = el.files[0]; if (!f) return;
    const fd = new FormData(); fd.append("file", f);
    try { await api(`/api/events/${el.dataset.ev}/cover`, "POST", fd); toast("Cover photo saved."); S.sfData = null; await render(); }
    catch (err) { toast(err.message, true); }
  } else if (el.dataset.actChange === "pick") {
    S.pickSlot = Number(el.value); $("#results").innerHTML = sponsorResults();
  } else if (el.dataset.actChange === "price") {
    try { await api(`/api/slots/${el.dataset.slot}`, "PATCH", { price: Number(el.value) }); toast("Price updated."); }
    catch (err) { toast(err.message, true); }
  }
});

(async function init() {
  try {
    S.meta = await api("/api/meta");
    if (!S.meta.sponsors.some(s => s.id === S.sponsorId)) S.sponsorId = S.meta.sponsors.find(s => s.name === "Sunbrew")?.id || S.meta.sponsors[0].id;
    if (!S.meta.clubs.some(c => c.id === S.clubId)) S.clubId = S.meta.clubs[0].id;
    await render();
    if (!store.get("welcomed", false)) { store.set("welcomed", true); ACTIONS.welcome(); }
  } catch (e) {
    $("#app").innerHTML = `<p class="note bad">Could not reach the server: ${esc(e.message)}. Start it with <code>python run.py</code>.</p>`;
  }
})();
