const API_URL = "http://127.0.0.1:8000/api/v1/chat-ai";

async function sendMessage() {
  const inputField = document.getElementById("user-input");
  const chatBox = document.getElementById("chat-box");
  const userMessage = inputField.value.trim();

  if (!userMessage) return;

  displayMessage(userMessage, "user-message");
  inputField.value = "";
  inputField.focus();

  const roomId = localStorage.getItem("tsa145_room") || crypto.randomUUID();
  localStorage.setItem("tsa145_room", roomId);

  try {
    const response = await fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ roomId, message: userMessage, id: Date.now() }),
    });

    if (!response.ok) throw new Error(`Error ${response.status}: ${response.statusText}`);

    const data = await response.json();
    const reply = data.message || data.content || "⚠️ TSA145 returned no content";

    updatePillarBanner(reply);
    displayMessage(reply, "bot-message");
  } catch (err) {
    console.error("❌ API Error:", err);
    displayMessage("⚠️ Could not connect to TSA145. Please try again.", "bot-message");
  }
}

function displayMessage(text, className) {
  const chatBox = document.getElementById("chat-box");
  const msg = document.createElement("div");
  msg.className = `chat-message ${className}`;
  msg.innerHTML = text.replace(/\n/g, "<br>");
  chatBox.appendChild(msg);
  chatBox.scrollTop = chatBox.scrollHeight;
}

function updatePillarBanner(message) {
  const banner = document.getElementById("pillar-banner");
  if (message.toLowerCase().includes("now answering questions under")) {
    const pillar = message.replace(/📂/g, "").trim();
    banner.textContent = pillar;
  }
}

function handleKeyPress(event) {
  if (event.key === "Enter") sendMessage();
}