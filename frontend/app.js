const API_URL = "http://localhost:8001/api";
const token = localStorage.getItem("token");
const username = localStorage.getItem("username");

if (!token) window.location.href = "./login.html";

document.getElementById("userBadge").textContent = username;
document.getElementById("logoutBtn").onclick = () => {
  localStorage.clear();
  window.location.href = "./login.html";
};

const taskList = document.getElementById("taskList");
const taskForm = document.getElementById("taskForm");
const searchBox = document.getElementById("search");

function renderTasks(tasks) {
  if (!tasks.length) {
    taskList.innerHTML = "<p>No tasks found.</p>";
    return;
  }

  taskList.innerHTML = tasks
    .map((t) => {
      const due = t.dueDate
        ? `Due: ${new Date(t.dueDate).toLocaleDateString()}`
        : "";
      const done = t.status === "done" ? "completed" : "";
      return `
        <div class="task-item ${done}">
          <div>
            <h4>${t.title}</h4>
            <p>${t.description || ""}</p>
            <small>${due}</small>
          </div>
          <div class="task-actions">
            <button class="btn btn-secondary" onclick="completeTask(${
              t.id
            })">Complete</button>
            <button class="btn btn-danger" onclick="deleteTask(${
              t.id
            })">Delete</button>
          </div>
        </div>
      `;
    })
    .join("");
}

async function loadTasks() {
  const search = searchBox.value.trim();
  const res = await fetch(`${API_URL}/tasks?search=${search}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const tasks = await res.json();
  renderTasks(tasks);
}

taskForm.onsubmit = async (e) => {
  e.preventDefault();
  const newTask = {
    title: title.value,
    description: description.value,
    dueDate: dueDate.value,
  };
  await fetch(`${API_URL}/tasks`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(newTask),
  });
  taskForm.reset();
  loadTasks();
};

async function deleteTask(id) {
  await fetch(`${API_URL}/tasks/${id}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
  loadTasks();
}

async function completeTask(id) {
  await fetch(`${API_URL}/tasks/${id}/complete`, {
    method: "PATCH",
    headers: { Authorization: `Bearer ${token}` },
  });
  loadTasks();
}

searchBox.oninput = loadTasks;
loadTasks();

const socket = io("http://localhost:8001");
const chatBox = document.getElementById("chatBox");
const chatInput = document.getElementById("chatText");
const createBtn = document.getElementById("createBtn");
const joinBtn = document.getElementById("joinBtn");
const leaveBtn = document.getElementById("leaveBtn");
const roomInput = document.getElementById("room");
const roomStatus = document.getElementById("roomStatus");

let currentRoom = null;

function setRoomUI(inRoom, name = "") {
  createBtn.disabled = inRoom;
  joinBtn.disabled = inRoom;
  leaveBtn.disabled = !inRoom;

  if (inRoom) {
    roomStatus.textContent = name.startsWith("created:")
      ? `Room "${name.slice(8)}" created. Share this name with others.`
      : `Joined room: "${name}"`;
    roomStatus.classList.add("active");
  } else {
    roomStatus.textContent = "";
    roomStatus.classList.remove("active");
  }
}

function joinRoom(name, created = false) {
  if (!name) return alert("Enter room name first");
  socket.emit("join", name);
  currentRoom = name;
  setRoomUI(true, created ? `created:${name}` : name);
}

createBtn.onclick = () => joinRoom(roomInput.value.trim(), true);
joinBtn.onclick = () => joinRoom(roomInput.value.trim());

leaveBtn.onclick = () => {
  if (!currentRoom) return;
  socket.emit("leave", currentRoom);
  chatBox.innerHTML = "";
  currentRoom = null;
  setRoomUI(false);
};

document.getElementById("chatForm").onsubmit = (e) => {
  e.preventDefault();
  if (!currentRoom) return alert("Join a room first!");
  const message = chatInput.value.trim();
  if (!message) return;
  socket.emit("message", { room: currentRoom, user: username, text: message });
  chatInput.value = "";
};

socket.on("message", (msg) => {
  if (
    msg.user === "System" ||
    msg.text.includes("joined room") ||
    msg.text.includes("left room")
  )
    return;

  chatBox.innerHTML += `<div class="chat-message"><b>${msg.user}:</b> ${msg.text}</div>`;
  chatBox.scrollTop = chatBox.scrollHeight;
});
