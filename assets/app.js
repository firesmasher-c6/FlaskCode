document.addEventListener("DOMContentLoaded", () => {
  const chatLog = document.getElementById("chatLog");
  const chatInput = document.getElementById("chatInput");
  const sendButton = document.getElementById("sendButton");
  const usernameInput = document.getElementById("usernameInput");
  const modelSelect = document.getElementById("modelSelect");

  function appendMessage(role, text) {
    const message = document.createElement("div");
    message.className = `message ${role}`;
    message.textContent = text;
    chatLog.appendChild(message);
    chatLog.scrollTop = chatLog.scrollHeight;
  }

  function appendMeta(text) {
    const meta = document.createElement("div");
    meta.className = "message-meta";
    meta.textContent = text;
    chatLog.appendChild(meta);
    chatLog.scrollTop = chatLog.scrollHeight;
  }

  async function sendMessage() {
    const message = chatInput.value.trim();
    if (!message) return;

    const username = usernameInput.value.trim();
    const model = modelSelect.value;

    appendMessage("user", `You: ${message}`);
    chatInput.value = "";

    const body = { message };
    if (username) body.username = username;
    if (model) body.model = model;

    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    const result = await response.json();
    if (response.ok) {
      appendMessage("bot", `Flask: ${result.answer}`);
      if (result.provider) {
        appendMeta(`provider: ${result.provider}`);
      }
      if (result.debug) {
        appendMeta(`debug: ${JSON.stringify(result.debug)}`);
      }
    } else {
      appendMessage("bot", `Error: ${result.error || "Request failed"}`);
    }
  }

  sendButton.addEventListener("click", sendMessage);
  chatInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
    }
  });
});