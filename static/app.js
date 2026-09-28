const $ = (id) => document.getElementById(id);
let currentUser = null;

// One helper for every call to the backend
async function api(path, options = {}) {
  const res = await fetch("/api" + path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Something went wrong");
  }
  return res.status === 204 ? null : res.json();
}

function showError(e) { $("error").textContent = e ? e.message : ""; }

async function loadUsers(selectId) {
  const users = await api("/users");
  const select = $("user-select");
  select.innerHTML = users.map((u) => `<option value="${u.id}">${u.name}</option>`).join("");
  if (!users.length) { $("tasks-section").hidden = true; currentUser = null; return; }
  if (selectId) select.value = selectId;
  currentUser = Number(select.value);
  await loadTasks();
}

async function loadTasks() {
  $("tasks-section").hidden = false;
  const tasks = await api(`/tasks?user_id=${currentUser}`);
  $("empty").hidden = tasks.length > 0;
  const list = $("task-list");
  list.innerHTML = "";
  for (const t of tasks) {
    const li = document.createElement("li");
    li.className = t.status;

    const title = document.createElement("span");
    title.className = "title";
    title.textContent = t.title; // textContent avoids HTML injection

    const status = document.createElement("select");
    for (const [value, label] of [["todo", "To do"], ["in_progress", "In progress"], ["done", "Done"]]) {
      status.add(new Option(label, value, false, value === t.status));
    }
    status.onchange = () => run(async () => {
      await api(`/tasks/${t.id}`, { method: "PATCH", body: JSON.stringify({ status: status.value }) });
      await loadTasks();
    });

    const del = document.createElement("button");
    del.className = "delete";
    del.textContent = "Delete";
    del.onclick = () => run(async () => {
      await api(`/tasks/${t.id}`, { method: "DELETE" });
      await loadTasks();
    });

    li.append(title, status, del);
    list.append(li);
  }
}

async function run(fn) {
  try { showError(null); await fn(); } catch (e) { showError(e); }
}

$("add-user").onclick = () => run(async () => {
  const user = await api("/users", { method: "POST", body: JSON.stringify({ name: $("new-user").value }) });
  $("new-user").value = "";
  await loadUsers(user.id);
});

$("user-select").onchange = () => run(async () => {
  currentUser = Number($("user-select").value);
  await loadTasks();
});

$("add-task").onclick = () => run(async () => {
  await api("/tasks", { method: "POST", body: JSON.stringify({ title: $("new-task").value, user_id: currentUser }) });
  $("new-task").value = "";
  await loadTasks();
});

run(() => loadUsers());
