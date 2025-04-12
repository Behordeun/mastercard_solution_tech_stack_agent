const API_URL = "http://127.0.0.1:8000/api/v1/chat-ai";
const CHAT_HISTORY = "http://127.0.0.1:8000/api/v1/chat-history";
const LOGIN_URL = "http://127.0.0.1:8000/api/v1/users/login";
const SIGNUP_URL = "http://127.0.0.1:8000/api/v1/users/register";
const PASSWORD_RESET_URL = "http://127.0.0.1:8000/api/v1/users/password-reset";
const PROFILE_UPDATE_URL = "http://127.0.0.1:8000/api/v1/users/profile/update";

document.addEventListener("DOMContentLoaded", function () {
  const currentPage = document.body.dataset.page; // Use a `data-page` attribute to identify the current page

  if (currentPage === "chat") {
    loadChatHistory();
  } else if (currentPage === "login") {
    setupLoginForm();
  } else if (currentPage === "signup") {
    setupSignupForm();
  } else if (currentPage === "password-reset") {
    setupPasswordResetForm();
  } else if (currentPage === "profile") {
    setupProfileUpdateForm();
  }
});

// === Chat Functionality ===
async function loadChatHistory() {
  const roomId = localStorage.getItem("tsa145_room") || crypto.randomUUID();
  localStorage.setItem("tsa145_room", roomId);

  try {
    const response = await fetch(CHAT_HISTORY + "?room_id=" + roomId, {
      method: "GET",
      headers: { "Content-Type": "application/json" },
    });

    if (!response.ok) {
      throw new Error(`Failed to load chat history. Status: ${response.status}`);
    }

    const chatHistory = await response.json();

    if (chatHistory && chatHistory.length > 0) {
      const chatBox = document.getElementById("chat-box");
      chatBox.innerHTML = "";

      chatHistory.forEach((message) => {
        if (message.role === "ai") {
          displayMessage(message.content, "bot-message");
        } else if (message.role === "user") {
          displayMessage(message.content, "user-message");
        }
      });
    } else {
      const chatBox = document.getElementById("chat-box");
      chatBox.innerHTML = "<p>No chat history available.</p>";
    }
  } catch (error) {
    console.error("❌ Error loading chat history:", error);
    const chatBox = document.getElementById("chat-box");
    chatBox.innerHTML = "<p>⚠️ Could not load chat history. Please try again later.</p>";
  }
}

// === Reset Chat ===
function resetChat() {
  const chatBox = document.getElementById("chat-box");
  chatBox.innerHTML = "";
  localStorage.removeItem("tsa145_room");
  loadChatHistory();
}

// === Send Message ===
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

// === Display Message ===
function displayMessage(text, className) {
  const chatBox = document.getElementById("chat-box");
  const msg = document.createElement("div");
  msg.className = `chat-message ${className}`;
  msg.innerHTML = text.replace(/\n/g, "<br>");
  chatBox.appendChild(msg);
  chatBox.scrollTop = chatBox.scrollHeight;
}

// === Update Pillar Banner ===
function updatePillarBanner(message) {
  const banner = document.getElementById("pillar-banner");
  if (message.toLowerCase().includes("now answering questions under")) {
    const pillar = message.replace(/📂/g, "").trim();
    banner.textContent = pillar;
  }
}

// === Handle Key Press ===
function handleKeyPress(event) {
  if (event.key === "Enter") sendMessage();
}

// === Login Functionality ===
function setupLoginForm() {
  const loginForm = document.querySelector("form");
  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const email = document.getElementById("email").value.trim();
    const password = document.getElementById("password").value.trim();

    try {
      const response = await fetch(LOGIN_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      if (!response.ok) throw new Error("Invalid login credentials");

      const data = await response.json();
      alert("Login successful!");
      localStorage.setItem("access_token", data.access_token);
      window.location.href = "/"; // Redirect to the home page
    } catch (error) {
      console.error("❌ Login Error:", error);
      alert("⚠️ Login failed. Please check your credentials.");
    }
  });
}

// === Signup Functionality ===
function setupSignupForm() {
  const signupForm = document.querySelector("form");
  signupForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const formData = new FormData(signupForm);
    const userData = Object.fromEntries(formData.entries());

    try {
      const response = await fetch(SIGNUP_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(userData),
      });

      if (!response.ok) throw new Error("Signup failed");

      alert("Signup successful! Please log in.");
      window.location.href = "/login"; // Redirect to the login page
    } catch (error) {
      console.error("❌ Signup Error:", error);
      alert("⚠️ Signup failed. Please try again.");
    }
  });
}

// === Password Reset Functionality ===
function setupPasswordResetForm() {
  const resetForm = document.querySelector("form");
  resetForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const email = document.getElementById("email").value.trim();

    try {
      const response = await fetch(PASSWORD_RESET_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });

      if (!response.ok) throw new Error("Password reset failed");

      alert("Password reset link sent to your email.");
      window.location.href = "/login"; // Redirect to the login page
    } catch (error) {
      console.error("❌ Password Reset Error:", error);
      alert("⚠️ Password reset failed. Please try again.");
    }
  });
}

// === Profile Update Functionality ===
function setupProfileUpdateForm() {
  const profileForm = document.querySelector("form");
  profileForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const formData = new FormData(profileForm);
    const profileData = Object.fromEntries(formData.entries());

    try {
      const response = await fetch(PROFILE_UPDATE_URL, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("access_token")}`,
        },
        body: JSON.stringify(profileData),
      });

      if (!response.ok) throw new Error("Profile update failed");

      alert("Profile updated successfully!");
      window.location.reload(); // Reload the profile page
    } catch (error) {
      console.error("❌ Profile Update Error:", error);
      alert("⚠️ Profile update failed. Please try again.");
    }
  });
}