const API = "";

const $ = (id) => document.getElementById(id);

let lastVisibleSources = [];
let bookingState = {
  sessionId: null,
  placeId: null,
  placeName: null,
  state: "idle",
};

const BOOKING_STEPS = [
  "collecting_name",
  "collecting_phone",
  "collecting_date",
  "collecting_people",
  "confirming",
];

function esc(value) {
  if (value == null) return "";
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function normalize(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function scrollChat() {
  const box = $("chat-messages");
  if (box) box.scrollTop = box.scrollHeight;
}

async function get(path) {
  const response = await fetch(`${API}${path}`);
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

async function post(path, body) {
  const response = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: `HTTP ${response.status}` }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

async function checkHealth() {
  try {
    const data = await get("/api/health");
    $("status-dot").className = `status-dot ${data.status === "ok" ? "ok" : "degraded"}`;
    $("status-txt").textContent = data.status === "ok" ? "All systems online" : "System degraded";
  } catch {
    $("status-dot").className = "status-dot degraded";
    $("status-txt").textContent = "Backend offline";
  }
}

function showWelcome() {
  addAssistantMessage(
    "Salam, I am WanderRAG.\n\nAsk me about Pakistan's historical landmarks, mountain routes, entry fees, opening hours, best travel seasons, and tour packages.",
    []
  );
}

async function sendMessage(overrideQuery) {
  const input = $("chat-input");
  const query = String(overrideQuery || input.value || "").trim();
  if (!query) return;

  if (!overrideQuery) input.value = "";
  addUserMessage(query);

  const sendButton = $("send-btn");
  sendButton.disabled = true;
  const typing = addTypingMessage();

  try {
    const data = await post("/api/chat", { query, top_k: 5 });
    typing.remove();

    const sources = chooseVisibleSources(query, data.sources || []);
    lastVisibleSources = sources.length ? sources : lastVisibleSources;

    addAssistantMessage(data.answer || "I could not generate an answer.", sources);
    updateSidebar(sources.length ? sources : data.sources || []);
  } catch (error) {
    typing.remove();
    addErrorMessage(error.message);
  } finally {
    sendButton.disabled = false;
    input.focus();
  }
}

function chooseVisibleSources(query, sources) {
  if (!Array.isArray(sources) || sources.length === 0) {
    if (isImageIntent(query) && lastVisibleSources.length) return lastVisibleSources.slice(0, 1);
    return [];
  }

  const q = normalize(query);
  const exact = sources
    .filter((source) => normalize(source.name) && q.includes(normalize(source.name)))
    .sort((a, b) => Number(b.score || 0) - Number(a.score || 0));

  if (exact.length) return [exact[0]];
  if (isImageIntent(query) && lastVisibleSources.length) return lastVisibleSources.slice(0, 1);

  return sources
    .filter((source) => Number(source.score || 0) >= 0.15)
    .slice(0, 3);
}

function isImageIntent(query) {
  const q = normalize(query);
  return ["image", "images", "picture", "pictures", "photo", "photos"].some((word) => q.includes(word));
}

function addUserMessage(text) {
  const row = document.createElement("div");
  row.className = "message-row user";
  row.innerHTML = `
    <div class="avatar">You</div>
    <div class="message-body">
      <div class="bubble user">${esc(text)}</div>
    </div>
  `;
  $("chat-messages").appendChild(row);
  scrollChat();
}

function addAssistantMessage(text, sources) {
  const row = document.createElement("div");
  row.className = "message-row assistant";
  row.innerHTML = `
    <div class="avatar">AI</div>
    <div class="message-body">
      <div class="bubble assistant">${formatAnswer(text)}</div>
      ${renderSourceStrip(sources)}
    </div>
  `;
  $("chat-messages").appendChild(row);
  scrollChat();
}

function addTypingMessage() {
  const row = document.createElement("div");
  row.className = "message-row assistant";
  row.innerHTML = `
    <div class="avatar">AI</div>
    <div class="message-body">
      <div class="bubble assistant">
        <span class="typing-dots"><span></span><span></span><span></span></span>
      </div>
    </div>
  `;
  $("chat-messages").appendChild(row);
  scrollChat();
  return row;
}

function addErrorMessage(message) {
  const row = document.createElement("div");
  row.className = "message-row assistant";
  row.innerHTML = `
    <div class="avatar">AI</div>
    <div class="message-body">
      <div class="bubble error">
        Connection error: ${esc(message)}
        <br><small>Make sure the backend is running and tourism data has been synced.</small>
      </div>
    </div>
  `;
  $("chat-messages").appendChild(row);
  scrollChat();
}

function formatAnswer(text) {
  return esc(text)
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\n/g, "<br>");
}

function renderSourceStrip(sources) {
  if (!Array.isArray(sources) || sources.length === 0) return "";
  const singleClass = sources.length === 1 ? " single" : "";
  return `
    <div class="source-strip${singleClass}">
      ${sources.map(renderSourceCard).join("")}
    </div>
  `;
}

function renderSourceCard(source) {
  const mapUrl = resolveMapUrl(source);
  return `
    <article class="source-card">
      <div class="source-media">
        ${renderMedia(source)}
        <span class="tag">${esc(source.category || "place")}</span>
      </div>
      <div class="source-body">
        <h3>${esc(source.name)}</h3>
        <p class="meta">${esc(source.city)}, ${esc(source.province)}</p>
        <span class="fee">${esc(source.entry_fee || "Free")}</span>
        <div class="source-actions">
          <a href="${esc(mapUrl)}" target="_blank" rel="noopener">Map</a>
          <button type="button" data-detail="${esc(source.name)}">Details</button>
          <button type="button" class="book-btn" data-book="${esc(source.id || "")}" data-place="${esc(source.name)}">Book</button>
        </div>
      </div>
    </article>
  `;
}

function renderMedia(source) {
  const url = String(source.image_url || "").trim();
  if (!isValidImageUrl(url)) {
    return fallbackMedia(source);
  }

  return `
    <a class="image-link" href="${esc(url)}" target="_blank" rel="noopener" title="Open image">
      <img
        src="${esc(url)}"
        alt="${esc(source.name)}"
        loading="lazy"
        data-fallback-name="${esc(source.name)}"
        data-fallback-category="${esc(source.category || "place")}"
      />
    </a>
  `;
}

function fallbackMedia(source) {
  return `<div class="fallback-media">${esc(source.name || "Tourism place")}</div>`;
}

function isValidImageUrl(url) {
  if (!url) return false;
  return url.startsWith("/") || /^https?:\/\//i.test(url);
}

function resolveMapUrl(source) {
  const direct = String(source.map_url || "").trim();
  if (direct) return direct;
  const query = encodeURIComponent(`${source.name || ""} ${source.city || ""} Pakistan`);
  return `https://maps.google.com/?q=${query}`;
}

function updateSidebar(sources) {
  const panel = $("sidebar-places");
  panel.innerHTML = "";

  if (!Array.isArray(sources) || sources.length === 0) {
    panel.innerHTML = `
      <div class="empty-state">
        <strong>No matches</strong>
        <p>Try asking about a city, landmark, entry fee, or tour package.</p>
      </div>
    `;
    return;
  }

  sources.slice(0, 4).forEach((source) => {
    const item = document.createElement("button");
    item.type = "button";
    item.className = "rail-place";
    item.dataset.detail = source.name || "";
    item.innerHTML = `
      <span class="rail-thumb">${renderRailThumb(source)}</span>
      <span class="rail-info">
        <strong>${esc(source.name)}</strong>
        <span>${esc(source.city)}, ${esc(source.province)}</span>
        <span class="rail-tag">${esc(source.category || "place")}</span>
      </span>
    `;
    panel.appendChild(item);
  });
}

function renderRailThumb(source) {
  const url = String(source.image_url || "").trim();
  if (!isValidImageUrl(url)) {
    return `<span class="rail-fallback">${esc(source.name || "Place")}</span>`;
  }

  return `
    <img
      src="${esc(url)}"
      alt="${esc(source.name)}"
      loading="lazy"
      data-fallback-name="${esc(source.name)}"
      data-fallback-category="${esc(source.category || "place")}"
    />
  `;
}

function openBooking(placeId, placeName) {
  const sessionId = `booking-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  bookingState = {
    sessionId,
    placeId,
    placeName,
    state: "collecting_name",
  };

  $("booking-place").textContent = placeName;
  $("booking-messages").innerHTML = "";
  $("booking-input").value = "";
  $("booking-input").disabled = false;
  $("booking-send").disabled = false;
  $("booking-overlay").classList.add("open");
  $("booking-overlay").setAttribute("aria-hidden", "false");
  updateBookingSteps("collecting_name");
  callBookingAgent(`I want to book ${placeName}`, placeId, placeName);
}

function closeBooking() {
  $("booking-overlay").classList.remove("open");
  $("booking-overlay").setAttribute("aria-hidden", "true");
}

async function sendBookingMessage() {
  const input = $("booking-input");
  const message = input.value.trim();
  if (!message) return;

  input.value = "";
  appendBookingMessage("user", message);
  await callBookingAgent(message);
}

async function callBookingAgent(message, placeId, placeName) {
  const button = $("booking-send");
  button.disabled = true;
  const typing = appendBookingMessage("bot", "Typing...");

  try {
    const body = {
      session_id: bookingState.sessionId,
      message,
    };

    if (placeId !== undefined) {
      body.place_id = placeId || null;
      body.place_name = placeName || null;
    }

    const data = await post("/api/booking-agent/message", body);
    typing.remove();

    bookingState.state = data.state || "idle";
    updateBookingSteps(bookingState.state);
    appendBookingMessage("bot", buildBookingReply(data));

    if (data.state === "completed") {
      $("booking-input").disabled = true;
      button.disabled = true;
    } else {
      button.disabled = false;
    }
  } catch (error) {
    typing.remove();
    appendBookingMessage("bot", `Something went wrong: ${error.message}`);
    button.disabled = false;
  }
}

function buildBookingReply(data) {
  let text = data.reply || "Please continue.";
  if (data.booking_id) {
    text += `\n\nBooking reference: ${data.booking_id}`;
  }
  if (data.summary) {
    text += "\n\nSummary:";
    Object.entries(data.summary).forEach(([key, value]) => {
      text += `\n${key.replace(/_/g, " ")}: ${value}`;
    });
  }
  return text;
}

function appendBookingMessage(role, text) {
  const row = document.createElement("div");
  row.className = `booking-msg ${role}`;
  row.innerHTML = formatAnswer(text);
  $("booking-messages").appendChild(row);
  $("booking-messages").scrollTop = $("booking-messages").scrollHeight;
  return row;
}

function updateBookingSteps(state) {
  const current = BOOKING_STEPS.indexOf(state);
  document.querySelectorAll("#booking-steps span").forEach((step, index) => {
    step.classList.remove("active", "done");
    if (state === "completed" || index < current) step.classList.add("done");
    if (index === current) step.classList.add("active");
  });
}

document.addEventListener("error", (event) => {
  const image = event.target;
  if (!(image instanceof HTMLImageElement) || !image.dataset.fallbackName) return;

  const media = image.closest(".source-media");
  if (media) {
    media.innerHTML = `${fallbackMedia({ name: image.dataset.fallbackName })}<span class="tag">${esc(image.dataset.fallbackCategory || "place")}</span>`;
    return;
  }

  const thumb = image.closest(".rail-thumb");
  if (thumb) {
    thumb.innerHTML = `<span class="rail-fallback">${esc(image.dataset.fallbackName)}</span>`;
  }
}, true);

document.addEventListener("DOMContentLoaded", () => {
  checkHealth();
  showWelcome();

  $("chat-form").addEventListener("submit", (event) => {
    event.preventDefault();
    sendMessage();
  });

  $("booking-form").addEventListener("submit", (event) => {
    event.preventDefault();
    sendBookingMessage();
  });

  $("booking-close").addEventListener("click", closeBooking);
  $("booking-overlay").addEventListener("click", (event) => {
    if (event.target === $("booking-overlay")) closeBooking();
  });

  document.addEventListener("click", (event) => {
    const bookButton = event.target.closest("[data-book]");
    if (bookButton) {
      event.preventDefault();
      openBooking(bookButton.dataset.book, bookButton.dataset.place);
      return;
    }

    const detailButton = event.target.closest("[data-detail]");
    if (detailButton) {
      event.preventDefault();
      sendMessage(`Tell me more about ${detailButton.dataset.detail}. Include history, opening hours, entry fee, best time to visit, and nearby tour options.`);
      return;
    }

    const promptButton = event.target.closest("[data-q]");
    if (promptButton) {
      event.preventDefault();
      sendMessage(promptButton.dataset.q);
    }
  });
});
