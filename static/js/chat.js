(function () {
  var OPEN = false;
  var messages = [];

  var container = document.getElementById("chatbot-container");
  var toggleBtn = document.getElementById("chatbot-toggle");
  var body = document.getElementById("chatbot-body");
  var input = document.getElementById("chatbot-input");
  var sendBtn = document.getElementById("chatbot-send");
  var messagesEl = document.getElementById("chatbot-messages");

  function scrollBottom() {
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function addMessage(role, text) {
    var div = document.createElement("div");
    div.className = "chat-msg chat-msg--" + role;
    div.textContent = text;
    messagesEl.appendChild(div);
    scrollBottom();
  }

  function showTyping() {
    var div = document.createElement("div");
    div.className = "chat-msg chat-msg--assistant chat-msg--typing";
    div.id = "chatbot-typing";
    div.innerHTML = '<span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span>';
    messagesEl.appendChild(div);
    scrollBottom();
  }

  function hideTyping() {
    var el = document.getElementById("chatbot-typing");
    if (el) el.remove();
  }

  function toggle() {
    OPEN = !OPEN;
    container.classList.toggle("chatbot--open", OPEN);
    if (OPEN) {
      input.focus();
      if (messagesEl.children.length === 0) {
        addMessage("assistant", "Hello! I'm the AI Security Assistant. Ask me anything about the MCC Digital ID System — stats, employees, visits, centres, or how things work.");
      }
    }
  }

  function send() {
    var text = input.value.trim();
    if (!text) return;
    input.value = "";
    addMessage("user", text);
    messages.push({ role: "user", content: text });
    showTyping();

    fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: messages })
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        hideTyping();
        var reply = data.reply || "Sorry, I couldn't process that.";
        addMessage("assistant", reply);
        messages.push({ role: "assistant", content: reply });
      })
      .catch(function () {
        hideTyping();
        addMessage("assistant", "Connection error. Please try again.");
      });
  }

  toggleBtn.addEventListener("click", toggle);
  sendBtn.addEventListener("click", send);
  input.addEventListener("keydown", function (e) {
    if (e.key === "Enter") send();
  });
})();
