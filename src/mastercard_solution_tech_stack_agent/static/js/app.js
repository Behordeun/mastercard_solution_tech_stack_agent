const API_URL = "http://127.0.0.1:8000/api/v1/chat/chat-ai";
const CHAT_HISTORY = "http://127.0.0.1:8000/api/v1/chat/chat-history";
const USER_SESSIONS_URL = "http://127.0.0.1:8000/api/v1/chat/user_sessions"; // Add this line
const CREATE_SESSION_URL = "http://127.0.0.1:8000/api/v1/chat/sessions"; // Add this line

document.addEventListener("DOMContentLoaded", function() {
  loadChatHistory();
  loadUserSessions(); // Add this line
});

async function loadUserSessions() {
  // const userId = localStorage.getItem("user_id"); // Assuming you store user_id in localStorage
  const token = localStorage.getItem("token");

  // if (!userId) {
  //   console.error("❌ No user ID found in localStorage.");
  //   return;
  // }

  if (!token) {
    console.error("❌ No token found in localStorage. Please log in.");
    window.location.href = "/login"; // Redirect to login page
    return;
  }

  try {
    const response = await fetch(`${USER_SESSIONS_URL}`, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${token}`
      }
    });

    if (!response.ok) {
      throw new Error(`Failed to load user sessions. Status: ${response.status}`);
    }

    const userSessions = await response.json();
    displayUserSessions(userSessions);

  } catch (error) {
    console.error("❌ Error loading user sessions:", error);
  }
}

function displayUserSessions(sessions) {
  const sidebar = document.querySelector(".sidebar ul"); // Assuming your sidebar has a <ul> element
  if (!sidebar) {
    console.error("❌ Sidebar element not found.");
    return;
  }

  // Clear existing sessions
  sidebar.innerHTML = "";

  sessions.forEach(session => {
    const listItem = document.createElement("li");
    const link = document.createElement("a");
    link.href = `?${session.session_id}`; // You can set the link to do something, e.g., load the chat history for that session
    link.textContent = `Session: ${session.session_id.substring(0, 8)}... Created: ${new Date(session.created_at).toLocaleDateString()}`; // Customize the display as needed
    listItem.appendChild(link);
    sidebar.appendChild(listItem);
  });
}

async function loadChatHistory() {
  let roomId = new URLSearchParams(window.location.search).get('tsa145_room');

  if (!roomId){
    roomId = localStorage.getItem("tsa145_room")
  }

  if (!roomId){
    roomId = await createNewSession();
    
    if (roomId) {
      localStorage.setItem("tsa145_room", roomId);
    }else{
      console.log("Unable to create room")
    }
  }

  // const roomId = localStorage.getItem("tsa145_room") || crypto.randomUUID();
  // localStorage.setItem("tsa145_room", roomId);
  const token = localStorage.getItem("token");
  if (!token) {
    console.error("❌ No token found in localStorage. Please log in.");
    window.location.href = "/login"; // Redirect to login page
    return;
  }

  try {
    const response = await fetch(CHAT_HISTORY + "?session_id=" + roomId, {
      method: "GET",
      headers: {"Content-Type": "application/json" , 
                "Authorization": "Bearer " + localStorage.getItem("token") },
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
async function resetChat() {
  // Clear the chat box content
  const chatBox = document.getElementById("chat-box");
  chatBox.innerHTML = ""; // Clears the messages

  // Reset the pillar banner (if needed)
  const banner = document.getElementById("pillar-banner");
  banner.textContent = ""; // Clear the pillar banner text
  
  // Clear the room ID from localStorage
  localStorage.removeItem("tsa145_room");

  // Create a new session
  const newSessionId = await createNewSession();
  if (newSessionId) {
    localStorage.setItem("tsa145_room", newSessionId);
  }

  // Optionally, focus on the input field
  const inputField = document.getElementById("user-input");
  inputField.value = ""; // Clear the input field
  inputField.focus(); // Focus on the input field for the next message

  loadChatHistory();
}

async function createNewSession() {
  const token = localStorage.getItem("token");
  if (!token) {
    console.error("❌ No token found in localStorage. Please log in.");
    window.location.href = "/login"; // Redirect to login page
    return null;
  }

  try {
    const response = await fetch(`${CREATE_SESSION_URL}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${token}`
      }
    });

    if (!response.ok) {
      throw new Error(`Failed to create new session. Status: ${response.status}`);
    }

    const sessionData = await response.json();
    return sessionData.session_id; // Assuming the response contains the new session ID

  } catch (error) {
    console.error("❌ Error creating new session:", error);
    return null;
  }
}

async function sendMessage() {
  const inputField = document.getElementById("user-input");
  const userMessage = inputField.value.trim();

  if (!userMessage) return;

  const token = localStorage.getItem("token");
  if (!token) {
    console.error("❌ No token found in localStorage. Please log in.");
    window.location.href = "/login"; // Redirect to login page
    return;
  }

  displayMessage(userMessage, "user-message");
  inputField.value = "";
  inputField.focus();

  const roomId = localStorage.getItem("tsa145_room") || crypto.randomUUID();
  localStorage.setItem("tsa145_room", roomId);

  try {
    const response = await fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json",
                "Authorization": "Bearer " + localStorage.getItem("token")
      },
      body: JSON.stringify({session_id: roomId, message: userMessage, id: Date.now() }),
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