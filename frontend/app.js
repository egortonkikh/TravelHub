// TravelHub frontend — single-page app, no build step, vanilla JS.

const API = {
  users: "/api/users",
  tours: "/api/tours",
  bookings: "/api/bookings",
};

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

// ---------- Toast ----------
function toast(message, type = "info") {
  const el = $("#toast");
  el.textContent = message;
  el.className = `toast ${type} show`;
  setTimeout(() => el.classList.remove("show"), 2800);
}

// ---------- API helpers ----------
async function apiGet(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`GET ${url} → ${r.status}`);
  return r.json();
}

async function apiPost(url, body) {
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await r.json();
  if (!r.ok) {
    const detail = data.detail || `HTTP ${r.status}`;
    throw new Error(detail);
  }
  return data;
}

// ---------- Renderers ----------
function renderUsers(users) {
  const list = $('[data-list="users"]');
  if (!users.length) {
    list.innerHTML = '<div class="list-empty">Пользователей пока нет</div>';
    return;
  }
  list.innerHTML = users
    .map(
      (u) => `
      <div class="list-item">
        <span class="id">#${u.id}</span>
        <div class="main">${escapeHtml(u.name)}</div>
        <span class="secondary">${escapeHtml(u.email)}</span>
      </div>`
    )
    .join("");
}

function renderTours(tours) {
  const list = $('[data-list="tours"]');
  if (!tours.length) {
    list.innerHTML = '<div class="list-empty">Туров пока нет</div>';
    return;
  }
  list.innerHTML = tours
    .map(
      (t) => `
      <div class="list-item">
        <span class="id">#${t.id}</span>
        <div class="main">
          ${escapeHtml(t.title)}
          <div class="secondary">${escapeHtml(t.description || "")}</div>
        </div>
        <span class="secondary">$${t.price} · ${t.duration}д</span>
      </div>`
    )
    .join("");
}

function renderBookings(bookings) {
  const list = $('[data-list="bookings"]');
  if (!bookings.length) {
    list.innerHTML = '<div class="list-empty">Бронирований пока нет</div>';
    return;
  }
  list.innerHTML = bookings
    .map(
      (b) => `
      <div class="list-item">
        <span class="id">#${b.id}</span>
        <div class="main">
          User #${b.user_id} → Tour #${b.tour_id}
          <div class="secondary">${escapeHtml(b.created_at)}</div>
        </div>
      </div>`
    )
    .join("");
}

function renderStats({ users, tours, bookings }) {
  $("#stat-users").textContent = users.length;
  $("#stat-tours").textContent = tours.length;
  $("#stat-bookings").textContent = bookings.length;
}

// ---------- Update dropdowns for booking form ----------
function updateSelects(users, tours) {
  const userSelect = document.querySelector(
    'form[data-form="booking"] select[name="user_id"]'
  );
  const tourSelect = document.querySelector(
    'form[data-form="booking"] select[name="tour_id"]'
  );

  userSelect.innerHTML =
    '<option value="">Выберите пользователя</option>' +
    users
      .map((u) => `<option value="${u.id}">#${u.id} ${escapeHtml(u.name)}</option>`)
      .join("");

  tourSelect.innerHTML =
    '<option value="">Выберите тур</option>' +
    tours
      .map(
        (t) =>
          `<option value="${t.id}">#${t.id} ${escapeHtml(t.title)} ($${t.price})</option>`
      )
      .join("");
}

// ---------- Loaders ----------
async function loadAll() {
  try {
    const [users, tours, bookings] = await Promise.all([
      apiGet(API.users),
      apiGet(API.tours),
      apiGet(API.bookings),
    ]);
    renderUsers(users);
    renderTours(tours);
    renderBookings(bookings);
    renderStats({ users, tours, bookings });
    updateSelects(users, tours);
  } catch (e) {
    toast("Не удалось загрузить данные: " + e.message, "error");
  }
}

async function loadOne(kind) {
  try {
    const data = await apiGet(API[kind]);
    if (kind === "users") renderUsers(data);
    if (kind === "tours") renderTours(data);
    if (kind === "bookings") renderBookings(data);
    toast(`${kind} обновлены`, "success");
  } catch (e) {
    toast("Ошибка: " + e.message, "error");
  }
}

// ---------- Form handlers ----------
function escapeHtml(s) {
  return String(s).replace(
    /[&<>"']/g,
    (c) =>
      ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      })[c]
  );
}

document.addEventListener("submit", async (e) => {
  const form = e.target;
  if (!form.dataset.form) return;
  e.preventDefault();

  const kind = form.dataset.form;
  const formData = new FormData(form);
  const body = Object.fromEntries(formData.entries());

  // coerce numeric fields
  if (body.price) body.price = parseFloat(body.price);
  if (body.duration) body.duration = parseInt(body.duration, 10);
  if (body.user_id) body.user_id = parseInt(body.user_id, 10);
  if (body.tour_id) body.tour_id = parseInt(body.tour_id, 10);

  try {
    const url = API[kind + "s"]; // user → users, tour → tours, booking → bookings
    const result = await apiPost(url, body);
    toast(result.message || "Создано", "success");
    form.reset();
    await loadAll();
  } catch (e) {
    toast("Ошибка: " + e.message, "error");
  }
});

// ---------- Refresh buttons ----------
document.addEventListener("click", async (e) => {
  const btn = e.target.closest("[data-refresh]");
  if (!btn) return;
  await loadOne(btn.dataset.refresh);
});

// ---------- Init ----------
loadAll();
