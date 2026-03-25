"""
build_site.py — Generates index.html from all_set_cards.json
Run: python build_site.py
"""
import json, sys

# ── Load card data ────────────────────────────────────────────────────────────
with open("all_set_cards.json", encoding="utf-8") as f:
    cards = json.load(f)

# Build compact JS array: [api_id, label, number, total, set, setId, rarity, variant, isReverse]
rows = [json.dumps([c["id"], c["label"], c["number"], c["total"], c["set"],
                    c["setId"], c["rarity"], c["variant"], 1 if c["isReverse"] else 0],
                   ensure_ascii=False, separators=(",", ":")) for c in cards]
card_data_js = "const R=[\n" + ",\n".join(rows) + "\n];"

# Set entry counts for sidebar stats
set_counts = {}
for c in cards:
    set_counts[c["set"]] = set_counts.get(c["set"], 0) + 1

total = len(cards)

# ── HTML template ─────────────────────────────────────────────────────────────
CSS = """
    :root {
      --bg:        #0d0d0f;
      --surface:   #16161a;
      --surface2:  #1e1e24;
      --surface3:  #252530;
      --border:    #2a2a35;
      --border2:   #363645;
      --accent:    #7c6aff;
      --glow:      rgba(124,106,255,0.2);
      --text:      #e8e8f0;
      --muted:     #6b6b80;
      --muted2:    #8888a0;
      --green:     #4ade80;
      --gold:      #fbbf24;
      --cyan:      #22d3ee;
      --blue:      #60a5fa;
      --purple:    #c084fc;
      --red:       #f87171;
    }
    *{box-sizing:border-box;margin:0;padding:0}
    body{background:var(--bg);color:var(--text);font-family:'Segoe UI',system-ui,sans-serif;display:flex;height:100vh;overflow:hidden}

    /* Sidebar */
    #sidebar{width:196px;min-width:196px;background:var(--surface);border-right:1px solid var(--border);display:flex;flex-direction:column;overflow:hidden}
    #sb-header{padding:18px 16px 14px;border-bottom:1px solid var(--border)}
    #sb-header h1{font-size:13px;font-weight:800;letter-spacing:.1em;text-transform:uppercase;color:var(--accent)}
    #sb-header .sb-sub{font-size:10px;color:var(--muted);margin-top:3px}
    #sb-sets{padding:8px 0;flex:1;overflow-y:auto}
    #sb-sets::-webkit-scrollbar{width:3px}
    #sb-sets::-webkit-scrollbar-thumb{background:var(--border);border-radius:2px}
    .sb-set{display:flex;align-items:center;justify-content:space-between;padding:10px 14px;cursor:pointer;border-left:3px solid transparent;transition:background .12s,border-color .12s}
    .sb-set:hover{background:var(--surface2)}
    .sb-set.active{border-left-color:var(--accent);background:var(--surface2)}
    .sb-set-name{font-size:12px;font-weight:600;line-height:1.3}
    .sb-set-count{font-size:10px;color:var(--muted);background:var(--border);border-radius:8px;padding:2px 7px;white-space:nowrap}
    #sb-stats{padding:12px 14px;border-top:1px solid var(--border);font-size:10px;color:var(--muted)}
    #sb-stats .sr{display:flex;justify-content:space-between;padding:3px 0}
    #sb-stats .sv{color:var(--muted2)}

    /* Main */
    #main{flex:1;display:flex;flex-direction:column;overflow:hidden;min-width:0}

    /* Top bar */
    #top-bar{padding:16px 28px 12px;border-bottom:1px solid var(--border);display:flex;flex-direction:column;gap:11px;background:var(--surface);flex-shrink:0}
    #top-row{display:flex;align-items:baseline;gap:14px;flex-wrap:wrap}
    #set-title{font-size:20px;font-weight:800}
    #set-subtitle{font-size:11px;color:var(--muted)}
    #filter-row{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
    #search-wrap{position:relative;flex:1;max-width:320px}
    #search-wrap::before{content:"\\2315";position:absolute;left:10px;top:50%;transform:translateY(-50%);color:var(--muted);font-size:15px;pointer-events:none}
    #search{width:100%;background:var(--surface2);border:1px solid var(--border2);color:var(--text);border-radius:7px;padding:7px 10px 7px 30px;font-size:12.5px;outline:none;transition:border-color .15s}
    #search:focus{border-color:var(--accent)}
    #search::placeholder{color:var(--muted)}
    .filter-tabs{display:flex;gap:4px}
    .ftab{background:var(--surface2);border:1px solid var(--border2);color:var(--muted2);border-radius:6px;padding:5px 12px;cursor:pointer;font-size:11.5px;font-weight:600;transition:background .12s,border-color .12s,color .12s}
    .ftab:hover{background:var(--surface3);color:var(--text)}
    .ftab.active{background:var(--accent);border-color:var(--accent);color:#fff}

    /* Table */
    #table-wrap{flex:1;overflow-y:auto;padding:0}
    #table-wrap::-webkit-scrollbar{width:6px}
    #table-wrap::-webkit-scrollbar-thumb{background:var(--border2);border-radius:3px}
    #card-table{width:100%;border-collapse:collapse;font-size:13px}
    #card-table thead{position:sticky;top:0;z-index:10;background:var(--bg)}
    #card-table th{padding:12px 10px 10px;text-align:left;font-size:10px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);border-bottom:1px solid var(--border2)}
    #card-table th.r{text-align:right}
    #card-table th.c{text-align:center}
    .card-row{cursor:pointer;transition:background .1s}
    .card-row:hover td{background:var(--surface)}
    .card-row.selected td{background:var(--surface2)}
    .card-row td{padding:9px 10px;border-bottom:1px solid var(--border);vertical-align:middle}
    .td-num{font-size:11.5px;font-variant-numeric:tabular-nums;color:var(--muted2);width:60px;font-weight:600}
    .td-name{font-size:13px;font-weight:600}
    .td-var{width:115px;text-align:center}
    .td-rar{font-size:11px;color:var(--muted2);width:130px}
    .td-price{text-align:right;font-size:13px;font-weight:700;font-variant-numeric:tabular-nums;width:90px;color:var(--green)}
    .price-loading{color:var(--muted);font-size:11px;font-weight:400}

    /* Variant badges */
    .vbadge{display:inline-block;font-size:9.5px;font-weight:700;padding:2px 7px;border-radius:8px;letter-spacing:.04em;text-transform:uppercase;white-space:nowrap}
    .v-holo  {background:#1f1a35;color:var(--purple);border:1px solid #3d2d6b}
    .v-rev   {background:#1a2820;color:var(--green);border:1px solid #14532d}
    .v-ex    {background:#2a2210;color:var(--gold);border:1px solid #78350f}
    .v-star  {background:#0e2830;color:var(--cyan);border:1px solid #0e4058}
    .v-rare  {background:#1a2035;color:var(--blue);border:1px solid #1e3a5f}
    .v-unc   {background:#1a1a25;color:#94a3b8;border:1px solid #2d2d45}
    .v-com   {background:#141418;color:#64748b;border:1px solid #22222e}
    .v-secret{background:#2a1018;color:var(--red);border:1px solid #7f1d1d}

    /* Detail panel */
    .detail-row td{padding:0!important;border-bottom:2px solid var(--accent)!important;background:var(--surface)!important}
    .detail-inner{display:flex;gap:28px;padding:22px 28px;border-top:2px solid var(--accent);background:linear-gradient(to bottom,rgba(124,106,255,.07),transparent 60%);flex-wrap:wrap}
    .dp-img-wrap{flex-shrink:0;display:flex;flex-direction:column;align-items:center;gap:10px}
    .dp-img-wrap img{width:160px;border-radius:8px;box-shadow:0 0 28px var(--glow),0 6px 20px rgba(0,0,0,.5);transition:transform .3s}
    .dp-img-wrap img:hover{transform:scale(1.05)}
    .dp-img-ph{width:160px;height:222px;border-radius:8px;background:var(--surface2);border:1px solid var(--border2);display:flex;align-items:center;justify-content:center;font-size:32px;color:var(--muted)}
    .tcg-btn{font-size:11px;color:var(--accent);text-decoration:none;border:1px solid var(--accent);padding:4px 14px;border-radius:14px;transition:background .15s;text-align:center}
    .tcg-btn:hover{background:var(--glow)}
    .dp-info{flex:1;min-width:260px}
    .dp-info h3{font-size:18px;font-weight:800;margin-bottom:8px}
    .dp-tags{display:flex;gap:7px;flex-wrap:wrap;margin-bottom:18px}
    .tag{font-size:9.5px;font-weight:700;padding:3px 9px;border-radius:9px;letter-spacing:.05em;text-transform:uppercase}
    .tag-set{background:#1a1a2e;color:#818cf8;border:1px solid #312e81}
    .tag-num{background:#1a2035;color:var(--blue);border:1px solid #1e3a5f}
    .dp-sec{font-size:10px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);margin:16px 0 9px}
    .dp-sec:first-of-type{margin-top:0}
    .price-tbl{width:100%;border-collapse:collapse;font-size:12.5px}
    .price-tbl th{text-align:left;font-size:9.5px;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);padding:0 8px 6px;border-bottom:1px solid var(--border2)}
    .price-tbl th:last-child{text-align:right}
    .price-tbl td{padding:7px 8px;border-bottom:1px solid var(--border)}
    .price-tbl tr:last-child td{border-bottom:none}
    .price-tbl tr:hover td{background:var(--surface3)}
    .price-tbl td:last-child{text-align:right;font-weight:700;font-variant-numeric:tabular-nums}
    .cond-dot{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:7px;vertical-align:middle}
    .est-note{font-size:9px;color:var(--muted);font-weight:400}
    .mkt-row{display:flex;gap:10px;flex-wrap:wrap}
    .mkt-stat{background:var(--surface2);border:1px solid var(--border2);border-radius:8px;padding:8px 14px;min-width:85px}
    .mkt-lbl{font-size:9.5px;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);margin-bottom:3px}
    .mkt-val{font-size:16px;font-weight:700;font-variant-numeric:tabular-nums}
    .dp-upd{font-size:9.5px;color:var(--muted);margin-top:12px}
    .dp-err{font-size:12px;color:var(--muted);padding:12px 0}
    .dp-spin{width:22px;height:22px;border:2px solid var(--border2);border-top-color:var(--accent);border-radius:50%;animation:spin .8s linear infinite;margin:24px auto}
    @keyframes spin{to{transform:rotate(360deg)}}

    /* Pagination */
    #pagination{display:flex;align-items:center;justify-content:space-between;padding:11px 28px;border-top:1px solid var(--border);background:var(--surface);flex-shrink:0}
    .pag-info{font-size:11px;color:var(--muted)}
    .pag-btns{display:flex;gap:6px;align-items:center}
    .pag-btn{background:var(--surface2);border:1px solid var(--border2);color:var(--text);border-radius:6px;padding:5px 14px;cursor:pointer;font-size:12px;transition:background .12s,border-color .12s}
    .pag-btn:hover:not(:disabled){background:var(--surface3);border-color:var(--accent)}
    .pag-btn:disabled{opacity:.3;cursor:default}
    .pag-label{font-size:11.5px;color:var(--muted2);min-width:70px;text-align:center}

    /* Empty / no-results */
    #empty{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:10px;color:var(--muted)}
    #empty .em-ico{font-size:40px;opacity:.4}
    #empty .em-txt{font-size:13px}
    #no-results{text-align:center;padding:60px 20px;color:var(--muted);font-size:13px;display:none}

    @media(max-width:700px){.td-rar,.th-rar{display:none}}
"""

JS = r"""
// Columns: [api_id, label, number, total, set, setId, rarity, variant, isReverse]
const CARDS = R.map(r => ({id:r[0],label:r[1],num:r[2],tot:r[3],set:r[4],sid:r[5],rar:r[6],var:r[7],rev:r[8]}));

const SETS = [
  {name:"Holon Phantoms",    id:"ex13"},
  {name:"Crystal Guardians", id:"ex14"},
  {name:"Delta Species",     id:"ex11"},
  {name:"Dragon Frontiers",  id:"ex15"},
];
const PER_PAGE  = 25;
const API_BASE  = "https://api.pokemontcg.io/v2/cards/";
const COND = [
  {label:"NM \u2014 Near Mint",         mult:1.00, color:"#4ade80"},
  {label:"LP \u2014 Lightly Played",    mult:0.80, color:"#a3e635"},
  {label:"MP \u2014 Moderately Played", mult:0.57, color:"#facc15"},
  {label:"HP \u2014 Heavily Played",    mult:0.40, color:"#f87171"},
];

let currentSet    = null;
let currentPage   = 1;
let currentFilter = "all";
let searchQuery   = "";
let expandedKey   = null;
const priceCache  = {};
const fetching    = new Set();

function varBadge(v) {
  const map = {
    "Holo Rare":    ["v-holo",  "Holo"],
    "Reverse Holo": ["v-rev",   "Rev Holo"],
    "pok\u00e9mon-ex": ["v-ex", "Pok\u00e9mon-ex"],
    "Gold Star":    ["v-star",  "\u2605 Gold Star"],
    "Rare":         ["v-rare",  "Rare"],
    "Rare Secret":  ["v-secret","Secret Rare"],
    "Uncommon":     ["v-unc",   "Uncommon"],
    "Common":       ["v-com",   "Common"],
  };
  const [cls, lbl] = map[v] || ["v-com", v];
  return `<span class="vbadge ${cls}">${lbl}</span>`;
}

function fmt(val) { return val != null ? `$${parseFloat(val).toFixed(2)}` : "N/A"; }
function ekey(c)  { return `${c.id}|${c.rev}`; }

// ── Sidebar ────────────────────────────────────────────────────────────────
function buildSidebar() {
  const nav = document.getElementById("sb-sets");
  SETS.forEach(s => {
    const count = CARDS.filter(c => c.sid === s.id).length;
    const el = document.createElement("div");
    el.className = "sb-set";
    el.dataset.sid = s.id;
    el.innerHTML = `<span class="sb-set-name">${s.name}</span><span class="sb-set-count">${count}</span>`;
    el.addEventListener("click", () => showSet(s.id));
    nav.appendChild(el);
  });
}

// ── Filtered list ─────────────────────────────────────────────────────────
function getVisible() {
  return CARDS.filter(c => {
    if (c.sid !== currentSet) return false;
    if (currentFilter === "regular" && c.rev) return false;
    if (currentFilter === "reverse" && !c.rev) return false;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      if (!c.label.toLowerCase().includes(q) && !c.num.includes(q)) return false;
    }
    return true;
  });
}

// ── Show set ──────────────────────────────────────────────────────────────
function showSet(sid) {
  currentSet    = sid;
  currentPage   = 1;
  expandedKey   = null;
  searchQuery   = "";
  currentFilter = "all";
  document.getElementById("search").value = "";
  document.querySelectorAll(".ftab").forEach(b => b.classList.toggle("active", b.dataset.filter === "all"));
  document.querySelectorAll(".sb-set").forEach(el => el.classList.toggle("active", el.dataset.sid === sid));
  const s   = SETS.find(x => x.id === sid);
  const all = CARDS.filter(c => c.sid === sid);
  const reg = all.filter(c => !c.rev).length;
  const rev = all.filter(c => c.rev).length;
  document.getElementById("set-title").textContent    = s.name;
  document.getElementById("set-subtitle").textContent = `${reg} cards \u00b7 ${rev} with reverse holo \u00b7 ${all.length} total entries`;
  document.getElementById("top-bar").style.display    = "";
  document.getElementById("empty").style.display      = "none";
  document.getElementById("table-area").style.display = "flex";
  renderTable();
}

// ── Render table ──────────────────────────────────────────────────────────
function renderTable() {
  const vis   = getVisible();
  const total = Math.max(1, Math.ceil(vis.length / PER_PAGE));
  if (currentPage > total) currentPage = total;
  const page  = vis.slice((currentPage-1)*PER_PAGE, currentPage*PER_PAGE);

  document.getElementById("no-results").style.display = vis.length ? "none" : "block";
  document.getElementById("pag-info").textContent =
    `${vis.length} entr${vis.length !== 1 ? "ies" : "y"} \u00b7 showing ${
      (currentPage-1)*PER_PAGE+1}\u2013${Math.min(currentPage*PER_PAGE, vis.length)}`;
  document.getElementById("pag-label").textContent  = `${currentPage} / ${total}`;
  document.getElementById("btn-prev").disabled      = currentPage <= 1;
  document.getElementById("btn-next").disabled      = currentPage >= total;

  const tbody = document.getElementById("tbody");
  tbody.innerHTML = "";

  page.forEach(c => {
    const key    = ekey(c);
    const cached = priceCache[c.id];
    let priceHtml;
    if (!cached || cached === "loading") {
      priceHtml = `<span class="price-loading">${cached === "loading" ? "\u2026" : "\u2014"}</span>`;
    } else if (cached === "error") {
      priceHtml = `<span class="price-loading">N/A</span>`;
    } else {
      const p = getPrice(cached, c.rev);
      priceHtml = p && p.market != null ? fmt(p.market) : `<span class="price-loading">N/A</span>`;
    }

    const tr = document.createElement("tr");
    tr.className   = "card-row" + (expandedKey === key ? " selected" : "");
    tr.dataset.key = key;
    tr.innerHTML   = `
      <td class="td-num">${c.num}/${c.tot}</td>
      <td class="td-name">${c.label}</td>
      <td class="td-var">${varBadge(c.var)}</td>
      <td class="td-rar th-rar">${c.rar}</td>
      <td class="td-price">${priceHtml}</td>`;
    tr.addEventListener("click", () => toggleDetail(c, tr, tbody));
    tbody.appendChild(tr);

    if (expandedKey === key) {
      tbody.appendChild(buildDetailRow(c));
    }
  });

  // Background-load prices for unique card IDs on this page
  const uids = [...new Set(page.map(c => c.id))];
  uids.forEach(id => schedFetch(id, tbody));
}

function schedFetch(id, tbody) {
  if (priceCache[id] && priceCache[id] !== "loading") return;
  if (fetching.has(id)) return;
  fetching.add(id);
  fetchPrice(id).then(() => {
    fetching.delete(id);
    if (!tbody.isConnected) return;
    // Patch price cells for this ID
    tbody.querySelectorAll("tr.card-row").forEach(row => {
      const k = row.dataset.key;
      if (!k || !k.startsWith(id + "|")) return;
      const rev  = k.endsWith("|1");
      const data = priceCache[id];
      const p    = data && data !== "error" ? getPrice(data, rev) : null;
      const cell = row.querySelector(".td-price");
      if (cell) cell.innerHTML = p && p.market != null ? fmt(p.market) : `<span class="price-loading">N/A</span>`;
    });
    // Refresh open detail panel if it belongs to this card
    if (expandedKey && expandedKey.startsWith(id + "|")) {
      const inner = tbody.querySelector(".detail-row .detail-inner");
      const card  = CARDS.find(c => ekey(c) === expandedKey);
      if (inner && card) renderDetailInner(inner, card);
    }
  });
}

// ── Price helpers ─────────────────────────────────────────────────────────
function getPrice(apiCard, isReverse) {
  const p = apiCard?.tcgplayer?.prices ?? {};
  if (isReverse && p.reverseHolofoil) return p.reverseHolofoil;
  if (p.holofoil)  return p.holofoil;
  if (p.normal)    return p.normal;
  const k = Object.keys(p)[0];
  return k ? p[k] : null;
}
function getPriceType(apiCard, isReverse) {
  const p = apiCard?.tcgplayer?.prices ?? {};
  if (isReverse && p.reverseHolofoil) return "Reverse Holofoil";
  if (p.holofoil)  return "Holofoil";
  if (p.normal)    return "Normal";
  const k = Object.keys(p)[0];
  return k || "\u2014";
}

async function fetchPrice(id) {
  if (priceCache[id] && priceCache[id] !== "loading") return;
  priceCache[id] = "loading";
  try {
    const res = await fetch(`${API_BASE}${id}?select=name,number,set,tcgplayer,images`);
    const d   = await res.json();
    priceCache[id] = d.data ?? "error";
  } catch(e) {
    priceCache[id] = "error";
  }
}

// ── Detail panel ──────────────────────────────────────────────────────────
async function toggleDetail(card, tr, tbody) {
  const key = ekey(card);
  const existing = tbody.querySelector(".detail-row");
  if (existing) {
    existing.remove();
    if (expandedKey === key) {
      expandedKey = null;
      tr.classList.remove("selected");
      return;
    }
  }
  tbody.querySelectorAll(".card-row").forEach(r => r.classList.remove("selected"));
  expandedKey = key;
  tr.classList.add("selected");

  const detailTr = buildDetailRow(card);
  tr.insertAdjacentElement("afterend", detailTr);
  detailTr.scrollIntoView({behavior:"smooth", block:"nearest"});

  if (!priceCache[card.id] || priceCache[card.id] === "loading") {
    await fetchPrice(card.id);
    const inner = detailTr.querySelector(".detail-inner");
    if (inner) renderDetailInner(inner, card);
  }
}

function buildDetailRow(card) {
  const tr = document.createElement("tr");
  tr.className = "detail-row";
  const td = document.createElement("td");
  td.colSpan = 5;
  const inner = document.createElement("div");
  inner.className = "detail-inner";
  renderDetailInner(inner, card);
  td.appendChild(inner);
  tr.appendChild(td);
  return tr;
}

function renderDetailInner(el, card) {
  const api = priceCache[card.id];
  if (!api || api === "loading") { el.innerHTML = `<div class="dp-spin"></div>`; return; }
  if (api === "error")            { el.innerHTML = `<div class="dp-err">Failed to load price data.</div>`; return; }

  const prices   = getPrice(api, card.rev);
  const pType    = getPriceType(api, card.rev);
  const tcgUrl   = api.tcgplayer?.url ?? "";
  const updated  = api.tcgplayer?.updatedAt ?? "";
  const imgLg    = api.images?.large ?? api.images?.small ?? "";

  const condRows = COND.map(c => {
    const est = prices?.market != null ? fmt(prices.market * c.mult) : "N/A";
    return `<tr><td><span class="cond-dot" style="background:${c.color}"></span>${c.label}</td><td><span class="est-note">est.</span> ${est}</td></tr>`;
  }).join("");

  el.innerHTML = `
    <div class="dp-img-wrap">
      ${imgLg ? `<img src="${imgLg}" alt="${card.label}" loading="lazy"/>` : `<div class="dp-img-ph">\ud83c\udccf</div>`}
      ${tcgUrl ? `<a class="tcg-btn" href="${tcgUrl}" target="_blank">TCGPlayer \u2197</a>` : ""}
    </div>
    <div class="dp-info">
      <h3>${card.label}</h3>
      <div class="dp-tags">
        <span class="tag tag-set">${card.set}</span>
        <span class="tag tag-num">#${card.num}/${card.tot}</span>
        ${varBadge(card.var)}
      </div>
      <div class="dp-sec">Condition Estimates</div>
      <table class="price-tbl">
        <thead><tr><th>Condition</th><th>Estimate</th></tr></thead>
        <tbody>${condRows}</tbody>
      </table>
      <div class="dp-sec" style="margin-top:16px">TCGPlayer Market
        <span style="color:var(--muted2);font-weight:400;text-transform:none;letter-spacing:0;font-size:10px"> \u2014 ${pType}</span>
      </div>
      <div class="mkt-row">
        <div class="mkt-stat"><div class="mkt-lbl">Market</div><div class="mkt-val" style="color:var(--green)">${fmt(prices?.market)}</div></div>
        <div class="mkt-stat"><div class="mkt-lbl">Low</div><div class="mkt-val">${fmt(prices?.low)}</div></div>
        <div class="mkt-stat"><div class="mkt-lbl">Mid</div><div class="mkt-val">${fmt(prices?.mid)}</div></div>
        <div class="mkt-stat"><div class="mkt-lbl">High</div><div class="mkt-val">${fmt(prices?.high)}</div></div>
      </div>
      ${updated ? `<div class="dp-upd">TCGPlayer data: ${updated}</div>` : ""}
    </div>`;
}

// ── Search & filter ───────────────────────────────────────────────────────
document.getElementById("search").addEventListener("input", e => {
  searchQuery = e.target.value.trim();
  currentPage = 1;
  expandedKey = null;
  renderTable();
});
document.querySelectorAll(".ftab").forEach(btn => {
  btn.addEventListener("click", () => {
    currentFilter = btn.dataset.filter;
    currentPage   = 1;
    expandedKey   = null;
    document.querySelectorAll(".ftab").forEach(b => b.classList.toggle("active", b === btn));
    renderTable();
  });
});

// ── Pagination ────────────────────────────────────────────────────────────
function changePage(delta) {
  const total = Math.ceil(getVisible().length / PER_PAGE);
  const next  = currentPage + delta;
  if (next < 1 || next > total) return;
  currentPage = next;
  expandedKey = null;
  document.getElementById("table-wrap").scrollTop = 0;
  renderTable();
}

buildSidebar();
"""

# ── Stat rows for sidebar ─────────────────────────────────────────────────────
stat_rows = "\n".join(
    f'    <div class="sr"><span>{s["name"]}</span><span class="sv">{set_counts.get(s["name"], 0)}</span></div>'
    for s in [
        {"name": "Holon Phantoms"},
        {"name": "Crystal Guardians"},
        {"name": "Delta Species"},
        {"name": "Dragon Frontiers"},
    ]
)

HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Delta Era \u2014 Pokemon Card Tracker</title>
  <style>{CSS}</style>
</head>
<body>

<aside id="sidebar">
  <div id="sb-header">
    <h1>Delta Era</h1>
    <div class="sb-sub">4 sets \u00b7 {total} entries</div>
  </div>
  <div id="sb-sets"></div>
  <div id="sb-stats">
{stat_rows}
  </div>
</aside>

<div id="main">
  <div id="top-bar" style="display:none">
    <div id="top-row">
      <span id="set-title"></span>
      <span id="set-subtitle"></span>
    </div>
    <div id="filter-row">
      <div id="search-wrap"><input id="search" type="text" placeholder="Search name or \u2116\u2026" autocomplete="off" /></div>
      <div class="filter-tabs">
        <button class="ftab active" data-filter="all">All</button>
        <button class="ftab" data-filter="regular">Regular</button>
        <button class="ftab" data-filter="reverse">Reverse Holo</button>
      </div>
    </div>
  </div>

  <div id="empty">
    <div class="em-ico">\U0001f0cf</div>
    <div class="em-txt">Select a set from the sidebar</div>
  </div>

  <div id="table-area" style="display:none;flex:1;flex-direction:column;overflow:hidden;min-height:0">
    <div id="table-wrap">
      <table id="card-table">
        <thead>
          <tr>
            <th style="width:60px">#</th>
            <th>Name</th>
            <th style="width:115px" class="c">Variant</th>
            <th style="width:130px" class="th-rar">Rarity</th>
            <th style="width:90px" class="r">Market</th>
          </tr>
        </thead>
        <tbody id="tbody"></tbody>
      </table>
      <div id="no-results">No cards match your search.</div>
    </div>
    <div id="pagination">
      <span class="pag-info" id="pag-info"></span>
      <div class="pag-btns">
        <button class="pag-btn" id="btn-prev" onclick="changePage(-1)">\u2190 Prev</button>
        <span class="pag-label" id="pag-label"></span>
        <button class="pag-btn" id="btn-next" onclick="changePage(1)">Next \u2192</button>
      </div>
    </div>
  </div>
</div>

<script>
{card_data_js}
{JS}
</script>
</body>
</html>"""

with open("index.html", "w", encoding="utf-8") as f:
    f.write(HTML)

print(f"Written index.html  ({len(HTML)//1024} KB,  {total} card entries embedded)")
