/* ============================================================
   admin.js — WanderRAG Admin Dashboard Logic
============================================================ */

const API      = "";
let allPlaces  = [];
let editingId  = null;
let toastTimer = null;

// ── NAVIGATION ────────────────────────────────────────────
function navTo(name) {
  document.querySelectorAll(".section").forEach(s => s.classList.remove("active"));
  document.querySelectorAll(".sb-link").forEach(l => l.classList.remove("active"));

  const sec = document.getElementById(`sec-${name}`);
  if (sec) sec.classList.add("active");

  document.querySelectorAll(".sb-link").forEach(l => {
    if ((l.dataset.section || "") === name) l.classList.add("active");
  });

 const titles = {
    dashboard: "Dashboard",
    places:    "Places Management",
    sync:      "Sync to Pinecone",
    data:      "Import / Export",
    bookings:  "Bookings",
};
  const titleEl = document.getElementById("page-title");
  if (titleEl) titleEl.textContent = titles[name] || name;

  if (name === "places")    loadPlaces();
  if (name === "dashboard") loadDashboard();
  if (name === "bookings")  loadBookings();
  if (name === "sync")      loadSyncStatus();
}

// ── HEALTH ────────────────────────────────────────────────
async function checkHealth() {
  try {
    const d   = await (await fetch(`${API}/api/health`)).json();
    const dot = document.getElementById("status-dot");
    const txt = document.getElementById("status-txt");

    dot.className = `status-dot ${d.status}`;
    txt.textContent = d.status === "ok" ? "All systems online" : "Degraded";

    const healthEl    = document.getElementById("st-health");
    const healthIcon  = document.getElementById("st-health-icon");
    const healthSub   = document.getElementById("st-health-sub");

    if (healthEl) {
      healthEl.textContent  = d.status === "ok" ? "All OK" : "Degraded";
      healthIcon.textContent = d.status === "ok" ? "✅" : "⚠️";
      healthSub.textContent =
        `DB:${d.database?"✓":"✗"}  Pinecone:${d.pinecone?"✓":"✗"}  Embed:${d.embedding_model?"✓":"✗"}`;
    }
  } catch {
    const dot = document.getElementById("status-dot");
    if (dot) dot.className = "status-dot degraded";
    const txt = document.getElementById("status-txt");
    if (txt) txt.textContent = "Backend offline";
  }
}

// ── DASHBOARD ─────────────────────────────────────────────
async function loadDashboard() {
  try {
    const [places, bookings, syncStatus] = await Promise.all([
      fetch(`${API}/api/places`).then(r => r.ok ? r.json() : []),
      fetch(`${API}/api/bookings`).then(r => r.ok ? r.json() : []),
      fetch(`${API}/api/sync/status`).then(r => r.ok ? r.json() : null).catch(() => null),
    ]);

    setInner("st-places",   places.length);
    setInner("st-packages", bookings.length);
    setInner("st-chunks",   syncStatus?.total_pinecone ?? "—");

    allPlaces = places;
    const tbody = document.getElementById("dash-tbody");
    const slice = places.slice(0, 6);

    if (!slice.length) {
      tbody.innerHTML = `<tr><td colspan="4" class="tbl-loading">
        No places yet.
        <a href="#" onclick="navTo('places');openModal()" style="color:var(--green)">Add one →</a>
      </td></tr>`;
      return;
    }

    tbody.innerHTML = slice.map(p => `
      <tr>
        <td class="td-name">${esc(p.name)}</td>
        <td class="td-muted">${esc(p.city)}</td>
        <td>${renderBadge(p.category)}</td>
        <td class="td-muted">${esc(p.entry_fee || "Free")}</td>
      </tr>`).join("");

  } catch(e) {
    console.error("Dashboard load error:", e);
    const tbody = document.getElementById("dash-tbody");
    if (tbody) {
      tbody.innerHTML = `<tr><td colspan="4" class="tbl-loading" style="color:var(--danger)">
        Failed to load dashboard: ${esc(e.message)}
      </td></tr>`;
    }
  }
}

// ── PLACES TABLE ──────────────────────────────────────────
async function loadPlaces() {
  const tbody = document.getElementById("places-tbody");
  tbody.innerHTML = `<tr><td colspan="6" class="tbl-loading">Loading...</td></tr>`;

  try {
    const res = await fetch(`${API}/api/places`);
    allPlaces  = await res.json();
    renderPlacesTable(allPlaces);
  } catch(e) {
    tbody.innerHTML = `<tr><td colspan="6" class="tbl-loading" style="color:var(--danger)">
      Failed to load places: ${esc(e.message)}</td></tr>`;
  }
}

function renderPlacesTable(places) {
  const tbody = document.getElementById("places-tbody");

  if (!places.length) {
    tbody.innerHTML = `<tr><td colspan="6" class="tbl-loading">
      No places found.
      <a href="#" onclick="openModal()" style="color:var(--green)">Add first place →</a>
    </td></tr>`;
    return;
  }

  tbody.innerHTML = places.map(p => {
    const updatedStr = p.updated_at
      ? new Date(p.updated_at).toLocaleDateString("en-GB", {
          day:"2-digit", month:"short", year:"numeric"
        })
      : "—";

    // Serialise place for edit button — safe via data attribute
    return `
      <tr>
        <td>
          <div class="td-name">${esc(p.name)}</div>
          <div class="td-id">${esc(p.id)}</div>
        </td>
        <td class="td-muted">${esc(p.city)}, ${esc(p.province)}</td>
        <td>${renderBadge(p.category)}</td>
        <td class="td-muted">${esc(p.entry_fee || "Free")}</td>
        <td class="td-muted">${updatedStr}</td>
        <td>
          <div class="td-actions">
            <button class="btn btn-ghost btn-sm"
              onclick='openModal(${JSON.stringify(p)})'>✏️ Edit</button>
            <button class="btn btn-danger btn-sm"
              onclick="confirmDelete('${esc(p.id)}','${esc(p.name.replace(/'/g,"\\'"))}')">
              🗑️
            </button>
          </div>
        </td>
      </tr>`;
  }).join("");
}

function filterPlaces() {
  const q   = (document.getElementById("place-search")?.value  || "").toLowerCase();
  const cat = (document.getElementById("cat-filter")?.value    || "").toLowerCase();

  renderPlacesTable(allPlaces.filter(p => {
    const blob = [p.name, p.city, p.province, p.description]
      .filter(Boolean).join(" ").toLowerCase();
    const catMatch = !cat || (p.category || "").toLowerCase() === cat;
    return (!q || blob.includes(q)) && catMatch;
  }));
}

// ── MODAL ─────────────────────────────────────────────────
function openModal(place = null) {
  editingId = place ? place.id : null;

  setInner("modal-ttl", place ? `Edit — ${place.name}` : "Add New Place");
  show("del-btn", !!place);

  // Clear all fields
  const fields = ["f-name","f-city","f-province","f-desc","f-hist",
                  "f-fee","f-hours","f-best","f-img","f-map","f-lat","f-lng","f-tags"];
  fields.forEach(id => { const el = document.getElementById(id); if(el) el.value = ""; });
  const catEl = document.getElementById("f-category");
  if (catEl) catEl.value = "";

  // Populate if editing
  if (place) {
    setVal("f-name",     place.name);
    setVal("f-city",     place.city);
    setVal("f-province", place.province);
    setVal("f-category", place.category);
    setVal("f-desc",     place.description);
    setVal("f-hist",     place.history);
    setVal("f-fee",      place.entry_fee);
    setVal("f-hours",    place.opening_hours);
    setVal("f-best",     place.best_time_to_visit);
    setVal("f-img",      place.image_url);
    setVal("f-map",      place.map_url);
    setVal("f-lat",      place.latitude  ?? "");
    setVal("f-lng",      place.longitude ?? "");

    // Parse tags JSON → comma-separated
    try {
      const tags = JSON.parse(place.tags || "[]");
      setVal("f-tags", Array.isArray(tags) ? tags.join(", ") : place.tags || "");
    } catch {
      setVal("f-tags", place.tags || "");
    }
  }

  document.getElementById("modal-overlay").classList.add("open");
  document.getElementById("f-name")?.focus();
}

function closeModal() {
  document.getElementById("modal-overlay").classList.remove("open");
  editingId = null;
}

// Close modal when clicking backdrop
document.addEventListener("click", e => {
  const overlay = document.getElementById("modal-overlay");
  if (e.target === overlay) closeModal();
});

// ── SAVE PLACE ────────────────────────────────────────────
async function savePlace() {
  const name     = getVal("f-name").trim();
  const city     = getVal("f-city").trim();
  const province = getVal("f-province").trim();
  const category = getVal("f-category").trim();

  if (!name || !city || !province || !category) {
    toast("Name, city, province and category are required", "error");
    return;
  }

  const tagsArr = getVal("f-tags")
    .split(",")
    .map(t => t.trim())
    .filter(Boolean);

  const payload = {
    name,
    city,
    province,
    category,
    description:        getVal("f-desc").trim(),
    history:            getVal("f-hist").trim(),
    entry_fee:          getVal("f-fee").trim()   || "Free",
    opening_hours:      getVal("f-hours").trim() || "Open daily",
    best_time_to_visit: getVal("f-best").trim(),
    image_url:          getVal("f-img").trim(),
    map_url:            getVal("f-map").trim(),
    latitude:           parseFloat(getVal("f-lat"))  || null,
    longitude:          parseFloat(getVal("f-lng")) || null,
    tags:               JSON.stringify(tagsArr),
  };

  const saveBtn = document.getElementById("save-btn");
  saveBtn.disabled  = true;
  saveBtn.innerHTML = `<span class="spinner"></span> Saving...`;

  try {
    const url    = editingId ? `${API}/api/places/${editingId}` : `${API}/api/places`;
    const method = editingId ? "PUT" : "POST";

    const res = await fetch(url, {
      method,
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify(payload),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Save failed" }));
      throw new Error(err.detail || "Save failed");
    }

    closeModal();
    loadPlaces();
    loadDashboard();
    toast(
      editingId
        ? `✅ "${name}" updated — run Sync to re-embed changed fields`
        : `✅ "${name}" added — run Sync to embed it into Pinecone`,
      "success"
    );

  } catch(e) {
    toast(`Error: ${e.message}`, "error");
  } finally {
    saveBtn.disabled  = false;
    saveBtn.innerHTML = "💾 Save Place";
  }
}

// ── DELETE ────────────────────────────────────────────────
function deleteFromModal() {
  if (!editingId) return;
  const name = getVal("f-name") || editingId;
  confirmDelete(editingId, name, true);
}

function confirmDelete(id, name, fromModal = false) {
  if (!confirm(
    `Delete "${name}"?\n\nThis removes the record from SQLite.\n` +
    `Run Sync afterwards to remove its vectors from Pinecone.`
  )) return;
  doDelete(id, name, fromModal);
}

async function doDelete(id, name, fromModal) {
  try {
    const res = await fetch(`${API}/api/places/${id}`, { method: "DELETE" });
    if (!res.ok && res.status !== 204) throw new Error("Delete failed");

    if (fromModal) closeModal();
    allPlaces = allPlaces.filter(p => p.id !== id);
    renderPlacesTable(allPlaces);
    loadDashboard();
    toast(`🗑️ "${name}" deleted — run Sync to remove from Pinecone`, "info");
  } catch(e) {
    toast(`Error: ${e.message}`, "error");
  }
}

// ── SYNC ──────────────────────────────────────────────────
async function loadSyncStatus() {
  try {
    const res = await fetch(`${API}/api/sync/status`);
    if (!res.ok) return;
    renderSyncResults(await res.json());
  } catch { /* no previous sync */ }
}

async function runSync() {
  const btn = document.getElementById("sync-run-btn");
  btn.disabled  = true;
  btn.innerHTML = `<span class="spinner"></span> Running sync...`;

  document.getElementById("sync-results")?.classList.add("hidden");

  try {
    const res = await fetch(`${API}/api/sync`, { method: "POST" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    const data = await res.json();
    renderSyncResults(data);
    toast(
      `✅ Sync done — +${data.added} added, ` +
      `${data.updated} updated, ${data.deleted} deleted, ${data.skipped} skipped`,
      "success"
    );
    loadDashboard();

  } catch(e) {
    toast(`Sync error: ${e.message}`, "error");
  } finally {
    btn.disabled  = false;
    btn.innerHTML = "🔄 Run Incremental Sync";
  }
}

function renderSyncResults(d) {
  setInner("sr-added",   d.added);
  setInner("sr-updated", d.updated);
  setInner("sr-deleted", d.deleted);
  setInner("sr-skipped", d.skipped);
  setInner("sr-total",   d.total_pinecone);
  setInner("sr-dur",     `${d.duration_seconds}s`);

  const logEl = document.getElementById("sync-log");
  if (logEl && d.details) {
    logEl.textContent = d.details.join("\n");
    logEl.scrollTop   = logEl.scrollHeight;
  }

  document.getElementById("sync-results")?.classList.remove("hidden");
}

// ── BOOKINGS ───────────────────────────────────────────────
let allBookings = [];

async function loadBookings() {
  const tbody = document.getElementById("bk-tbody");
  if (!tbody) return;

  tbody.innerHTML = `<tr><td colspan="9" class="tbl-loading">Loading...</td></tr>`;

  try {
    const res = await fetch(`${API}/api/bookings`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    allBookings = await res.json();
    renderBookings(allBookings);
    renderBookingStats(allBookings);
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="9" class="tbl-loading" style="color:var(--danger)">
      Failed to load bookings: ${esc(e.message)}
    </td></tr>`;
  }
}

function filterBookings() {
  const status = (document.getElementById("bk-status-filter")?.value || "").toLowerCase();
  const rows = status ? allBookings.filter(b => (b.status || "").toLowerCase() === status) : allBookings;
  renderBookings(rows);
}

function renderBookings(bookings) {
  const tbody = document.getElementById("bk-tbody");
  if (!tbody) return;

  if (!bookings.length) {
    tbody.innerHTML = `<tr><td colspan="9" class="tbl-loading">No bookings yet.</td></tr>`;
    return;
  }

  tbody.innerHTML = bookings.map(b => {
    const created = b.created_at
      ? new Date(b.created_at).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" })
      : "—";
    const status = (b.status || "pending").toLowerCase();
    const options = ["pending", "confirmed", "cancelled", "completed"].map(s =>
      `<option value="${s}" ${s === status ? "selected" : ""}>${s}</option>`
    ).join("");

    return `
      <tr>
        <td><span class="bk-id-cell">${esc(b.id)}</span></td>
        <td>
          <div class="td-name">${esc(b.customer_name || "—")}</div>
          <div class="td-id">${esc(b.customer_email || "")}</div>
        </td>
        <td class="td-muted">${esc(b.place_name || b.place_id || b.package_id || "—")}</td>
        <td class="td-muted">${esc(b.travel_date || "—")}</td>
        <td class="td-muted">${esc(b.number_of_people ?? "—")}</td>
        <td class="td-muted">${esc(b.customer_phone || "—")}</td>
        <td class="td-muted">${created}</td>
        <td><span class="bk-status ${esc(status)}">${esc(status)}</span></td>
        <td class="td-actions">
          <select class="bk-status-select" onchange="updateBookingStatus('${esc(b.id)}', this.value)">
            ${options}
          </select>
        </td>
      </tr>`;
  }).join("");
}

function renderBookingStats(bookings) {
  const counts = { pending: 0, confirmed: 0, completed: 0, cancelled: 0 };
  bookings.forEach(b => {
    const status = (b.status || "pending").toLowerCase();
    if (status in counts) counts[status] += 1;
  });
  setInner("bkst-pending", `${counts.pending} Pending`);
  setInner("bkst-confirmed", `${counts.confirmed} Confirmed`);
  setInner("bkst-completed", `${counts.completed} Completed`);
  setInner("bkst-cancelled", `${counts.cancelled} Cancelled`);
}

async function updateBookingStatus(id, status) {
  try {
    const res = await fetch(`${API}/api/bookings/${id}/status`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    toast(`Booking ${id} marked ${status}`, "success");
    loadBookings();
    loadDashboard();
  } catch (e) {
    toast(`Status update failed: ${e.message}`, "error");
  }
}

// ── CSV IMPORT ────────────────────────────────────────────
function onDragOver(e) {
  e.preventDefault();
  document.getElementById("upload-zone")?.classList.add("drag");
}
function onDragLeave() {
  document.getElementById("upload-zone")?.classList.remove("drag");
}
function onDrop(e) {
  e.preventDefault();
  onDragLeave();
  const file = e.dataTransfer?.files?.[0];
  if (file) processCSV(file);
}
function onFileSelect(e) {
  const file = e.target?.files?.[0];
  if (file) processCSV(file);
}

async function processCSV(file) {
  const resultDiv = document.getElementById("import-result");
  resultDiv.className   = "import-result ir-ok";
  resultDiv.textContent = "⏳ Uploading...";

  const fd = new FormData();
  fd.append("file", file);

  try {
    const res  = await fetch(`${API}/api/import-csv`, { method: "POST", body: fd });
    const data = await res.json();

    if (!res.ok) {
      resultDiv.className   = "import-result ir-err";
      resultDiv.textContent = `❌ ${data.detail || "Import failed"}`;
      return;
    }

    resultDiv.className = "import-result ir-ok";
    resultDiv.innerHTML = `
      ✅ <strong>Import complete</strong><br/>
      ➕ Inserted: <strong>${data.inserted}</strong><br/>
      🔄 Updated:  <strong>${data.updated}</strong><br/>
      ⏭️ Skipped:  <strong>${data.skipped}</strong>
      ${data.errors?.length ? `<br/>⚠️ ${data.errors.length} row error(s)` : ""}
      <br/><em>${esc(data.message)}</em>`;

    loadDashboard();
    toast(`Import done: ${data.inserted} new, ${data.updated} updated`, "success");

  } catch(e) {
    resultDiv.className   = "import-result ir-err";
    resultDiv.textContent = `❌ ${e.message}`;
  }
}

// ── CSV EXPORT ────────────────────────────────────────────
function doExport() {
  window.open(`${API}/api/export-csv`, "_blank");
  toast("📥 CSV download started", "info");
}

// ── TOAST ─────────────────────────────────────────────────
function toast(msg, type = "info") {
  const el = document.getElementById("toast");
  if (!el) return;
  el.textContent = msg;
  el.className   = `toast show ${type}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.className = "toast"; }, 4500);
}

// ── BADGE ─────────────────────────────────────────────────
function renderBadge(cat) {
  const map = {
    historical: "bg-historical",
    nature:     "bg-nature",
    religious:  "bg-religious",
    adventure:  "bg-adventure",
    food:       "bg-food",
    cultural:   "bg-cultural",
  };
  const cls = map[(cat || "").toLowerCase()] || "bg-default";
  return `<span class="badge ${cls}">${esc(cat || "—")}</span>`;
}

// ── DOM HELPERS ───────────────────────────────────────────
function esc(str) {
  if (str == null) return "";
  return String(str)
    .replace(/&/g,"&amp;").replace(/</g,"&lt;")
    .replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}

function setInner(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val ?? "—";
}

function setVal(id, val) {
  const el = document.getElementById(id);
  if (el) el.value = val ?? "";
}

function getVal(id) {
  return document.getElementById(id)?.value ?? "";
}

function show(id, visible) {
  const el = document.getElementById(id);
  if (el) el.style.display = visible ? "inline-flex" : "none";
}

// ── INIT ─────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  // Wire sidebar navigation
  document.querySelectorAll(".sb-link[data-section]").forEach(link => {
    link.addEventListener("click", () => navTo(link.dataset.section));
  });

  checkHealth();
  loadDashboard();
});
