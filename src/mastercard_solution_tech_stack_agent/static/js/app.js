const API_URL = "http://127.0.0.1:8000/api/v1/chat-ai";
const CHAT_HISTORY = "http://127.0.0.1:8000/api/v1/chat-history";

document.addEventListener("DOMContentLoaded", function() {
  loadChatHistory();
});

async function loadChatHistory() {
  const roomId = localStorage.getItem("tsa145_room") || crypto.randomUUID();
  localStorage.setItem("tsa145_room", roomId);

  try {
    const response = await fetch(CHAT_HISTORY + "?room_id=" + roomId, {
      method: "GET",
      headers: { "Content-Type": "application/json" },
    });

    // Check if the response is successful
    if (!response.ok) {
      throw new Error(`Failed to load chat history. Status: ${response.status}`);
    }

    const chatHistory = await response.json();

    // Handle case where chatHistory is empty or null
    if (chatHistory && chatHistory.length > 0) {
      console.log(chatHistory);

      const chatBox = document.getElementById("chat-box");
      chatBox.innerHTML = ""; // Clear any existing content

      chatHistory.forEach(message => {
        if (message.role == "ai"){
          displayMessage(message.content, "bot-message")
        } else if (message.role == "user"){
          displayMessage(message.content, "user-message")
        } else {
          const messageDiv = document.createElement("div");
          messageDiv.classList.add("chat-message");
          messageDiv.innerText = message.content || "No text available"; // Handling missing 'text' field
          chatBox.appendChild(messageDiv);
        }
      });
    } 
    // else {
    //   // Handle empty chat history case
    //   const chatBox = document.getElementById("chat-box");
    //   chatBox.innerHTML = "<p>No chat history available.</p>";
    // }
  } catch (error) {
    console.error("❌ Error loading chat history:", error);
    const chatBox = document.getElementById("chat-box");
    chatBox.innerHTML = "<p>⚠️ Could not load chat history. Please try again later.</p>";
  }
}

// Reset the chat
function resetChat() {
  // Clear the chat box content
  const chatBox = document.getElementById("chat-box");
  chatBox.innerHTML = ""; // Clears the messages

  // Reset the pillar banner (if needed)
  const banner = document.getElementById("pillar-banner");
  banner.textContent = ""; // Clear the pillar banner text
  
  // Clear the room ID from localStorage, so a new room will be created next time
  localStorage.removeItem("tsa145_room");

  // Optionally, focus on the input field
  const inputField = document.getElementById("user-input");
  inputField.value = ""; // Clear the input field
  inputField.focus(); // Focus on the input field for the next message

  loadChatHistory();
}

async function sendMessage() {
  const inputField = document.getElementById("user-input");
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