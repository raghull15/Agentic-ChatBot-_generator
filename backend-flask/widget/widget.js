(function () {
  'use strict';

  // Get script element and attributes
  const script = document.currentScript;
  const token = script.getAttribute('data-token');
  const theme = script.getAttribute('data-theme') || 'light';
  const position = script.getAttribute('data-position') || 'bottom-right';
  const title = script.getAttribute('data-title') || 'AI Assistant';
  const apiUrl = script.getAttribute('data-api-url') || script.src.replace('/widget.js', '');

  if (!token) {
    console.error('Agentic Widget: data-token is required');
    return;
  }

  // Styles
  const styles = `
    .agentic-widget-container {
      position: fixed;
      ${position.includes('bottom') ? 'bottom: 20px;' : 'top: 20px;'}
      ${position.includes('right') ? 'right: 20px;' : 'left: 20px;'}
      z-index: 999999;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }

    .agentic-widget-button {
      width: 60px;
      height: 60px;
      border-radius: 50%;
      background: linear-gradient(135deg, #2563eb 0%, #0ea5e9 100%);
      border: none;
      cursor: pointer;
      box-shadow: 0 4px 20px rgba(37, 99, 235, 0.4);
      display: flex;
      align-items: center;
      justify-content: center;
      transition: all 0.3s ease;
    }

    .agentic-widget-button:hover {
      transform: scale(1.1);
      box-shadow: 0 6px 30px rgba(37, 99, 235, 0.5);
    }

    .agentic-widget-button svg {
      width: 28px;
      height: 28px;
      fill: white;
    }

    .agentic-widget-chat {
      position: absolute;
      ${position.includes('bottom') ? 'bottom: 75px;' : 'top: 75px;'}
      ${position.includes('right') ? 'right: 0;' : 'left: 0;'}
      width: 380px;
      height: 520px;
      background: ${theme === 'dark' ? '#1e293b' : '#ffffff'};
      border-radius: 20px;
      box-shadow: 0 10px 40px rgba(0, 0, 0, 0.15);
      display: none;
      flex-direction: column;
      overflow: hidden;
      border: 1px solid ${theme === 'dark' ? '#334155' : '#e2e8f0'};
    }

    .agentic-widget-chat.open {
      display: flex;
      animation: slideUp 0.3s ease;
    }

    @keyframes slideUp {
      from {
        opacity: 0;
        transform: translateY(20px);
      }
      to {
        opacity: 1;
        transform: translateY(0);
      }
    }

    .agentic-widget-header {
      padding: 16px 20px;
      background: linear-gradient(135deg, #2563eb 0%, #0ea5e9 100%);
      color: white;
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .agentic-widget-avatar {
      width: 40px;
      height: 40px;
      background: rgba(255, 255, 255, 0.2);
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 20px;
    }

    .agentic-widget-title {
      flex: 1;
    }

    .agentic-widget-title h3 {
      margin: 0;
      font-size: 16px;
      font-weight: 600;
    }

    .agentic-widget-title span {
      font-size: 12px;
      opacity: 0.8;
    }

    .agentic-widget-close {
      background: rgba(255, 255, 255, 0.2);
      border: none;
      width: 32px;
      height: 32px;
      border-radius: 8px;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: background 0.2s;
    }

    .agentic-widget-close:hover {
      background: rgba(255, 255, 255, 0.3);
    }

    .agentic-widget-close svg {
      width: 18px;
      height: 18px;
      stroke: white;
    }

    .agentic-widget-messages {
      flex: 1;
      overflow-y: auto;
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 12px;
      background: ${theme === 'dark' ? '#0f172a' : '#f8fafc'};
    }

    .agentic-widget-message {
      max-width: 85%;
      padding: 12px 16px;
      border-radius: 16px;
      font-size: 14px;
      line-height: 1.5;
    }

    .agentic-widget-message.user {
      align-self: flex-end;
      background: linear-gradient(135deg, #2563eb 0%, #0ea5e9 100%);
      color: white;
      border-bottom-right-radius: 4px;
    }

    .agentic-widget-message.assistant {
      align-self: flex-start;
      background: ${theme === 'dark' ? '#1e293b' : '#ffffff'};
      color: ${theme === 'dark' ? '#f1f5f9' : '#1e293b'};
      border: 1px solid ${theme === 'dark' ? '#334155' : '#e2e8f0'};
      border-bottom-left-radius: 4px;
    }

    .agentic-widget-message.error {
      background: #fef2f2;
      color: #dc2626;
      border: 1px solid #fecaca;
    }

    .agentic-widget-typing {
      display: flex;
      gap: 4px;
      padding: 12px 16px;
      background: ${theme === 'dark' ? '#1e293b' : '#ffffff'};
      border-radius: 16px;
      border-bottom-left-radius: 4px;
      align-self: flex-start;
      border: 1px solid ${theme === 'dark' ? '#334155' : '#e2e8f0'};
    }

    .agentic-widget-typing span {
      width: 8px;
      height: 8px;
      background: #94a3b8;
      border-radius: 50%;
      animation: bounce 1.4s infinite ease-in-out;
    }

    .agentic-widget-typing span:nth-child(1) { animation-delay: 0s; }
    .agentic-widget-typing span:nth-child(2) { animation-delay: 0.2s; }
    .agentic-widget-typing span:nth-child(3) { animation-delay: 0.4s; }

    @keyframes bounce {
      0%, 80%, 100% { transform: translateY(0); }
      40% { transform: translateY(-8px); }
    }

    .agentic-widget-input-container {
      padding: 16px;
      background: ${theme === 'dark' ? '#1e293b' : '#ffffff'};
      border-top: 1px solid ${theme === 'dark' ? '#334155' : '#e2e8f0'};
      display: flex;
      gap: 10px;
    }

    .agentic-widget-input {
      flex: 1;
      padding: 12px 16px;
      border: 1px solid ${theme === 'dark' ? '#334155' : '#e2e8f0'};
      border-radius: 12px;
      font-size: 14px;
      outline: none;
      background: ${theme === 'dark' ? '#0f172a' : '#f8fafc'};
      color: ${theme === 'dark' ? '#f1f5f9' : '#1e293b'};
      transition: border-color 0.2s;
    }

    .agentic-widget-input:focus {
      border-color: #2563eb;
    }

    .agentic-widget-input::placeholder {
      color: #94a3b8;
    }

    .agentic-widget-send {
      width: 44px;
      height: 44px;
      border-radius: 12px;
      background: linear-gradient(135deg, #2563eb 0%, #0ea5e9 100%);
      border: none;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: all 0.2s;
    }

    .agentic-widget-send:hover {
      transform: scale(1.05);
    }

    .agentic-widget-send:disabled {
      opacity: 0.5;
      cursor: not-allowed;
      transform: none;
    }

    .agentic-widget-send svg {
      width: 20px;
      height: 20px;
      fill: white;
    }

    .agentic-widget-powered {
      padding: 8px;
      text-align: center;
      font-size: 11px;
      color: #94a3b8;
      background: ${theme === 'dark' ? '#1e293b' : '#ffffff'};
    }

    .agentic-widget-powered a {
      color: #2563eb;
      text-decoration: none;
    }

    .agentic-widget-welcome {
      text-align: center;
      padding: 20px;
      color: #64748b;
    }

    .agentic-widget-welcome-icon {
      font-size: 48px;
      margin-bottom: 12px;
    }

    .agentic-widget-welcome h4 {
      margin: 0 0 8px 0;
      color: ${theme === 'dark' ? '#f1f5f9' : '#1e293b'};
      font-size: 16px;
    }

    .agentic-widget-welcome p {
      margin: 0;
      font-size: 13px;
    }
  `;

  // Inject styles
  const styleSheet = document.createElement('style');
  styleSheet.textContent = styles;
  document.head.appendChild(styleSheet);

  // Create widget HTML
  const container = document.createElement('div');
  container.className = 'agentic-widget-container';
  container.innerHTML = `
    <div class="agentic-widget-chat" id="agentic-chat">
      <div class="agentic-widget-header">
        <div class="agentic-widget-avatar">🤖</div>
        <div class="agentic-widget-title">
          <h3 id="agentic-title">${title}</h3>
          <span id="agentic-domain">AI Assistant</span>
        </div>
        <button class="agentic-widget-close" id="agentic-close">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M18 6L6 18M6 6l12 12"/>
          </svg>
        </button>
      </div>
      <div class="agentic-widget-messages" id="agentic-messages">
        <div class="agentic-widget-welcome">
          <div class="agentic-widget-welcome-icon">👋</div>
          <h4>Hi there!</h4>
          <p>Ask me anything about the documents I was trained on.</p>
        </div>
      </div>
      <div class="agentic-widget-input-container">
        <input 
          type="text" 
          class="agentic-widget-input" 
          id="agentic-input" 
          placeholder="Type your message..."
        />
        <button class="agentic-widget-send" id="agentic-send">
          <svg viewBox="0 0 24 24">
            <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
          </svg>
        </button>
      </div>
      <div class="agentic-widget-powered">
        Powered by <a href="#" target="_blank">Agentic AI</a>
      </div>
    </div>
    <button class="agentic-widget-button" id="agentic-toggle">
      <svg viewBox="0 0 24 24">
        <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H6l-2 2V4h16v12z"/>
      </svg>
    </button>
  `;

  document.body.appendChild(container);

  // Widget logic
  const chat = document.getElementById('agentic-chat');
  const toggle = document.getElementById('agentic-toggle');
  const close = document.getElementById('agentic-close');
  const input = document.getElementById('agentic-input');
  const send = document.getElementById('agentic-send');
  const messages = document.getElementById('agentic-messages');
  const titleEl = document.getElementById('agentic-title');
  const domainEl = document.getElementById('agentic-domain');

  let isOpen = false;
  let isLoading = false;
  let hasWelcome = true;

  // Fetch agent info
  fetch(`${apiUrl}/embed/${token}/info`)
    .then(res => res.json())
    .then(data => {
      if (data.success) {
        titleEl.textContent = data.agent_name || title;
        domainEl.textContent = data.domain || 'AI Assistant';
      }
    })
    .catch(() => { });

  // Toggle chat
  toggle.addEventListener('click', () => {
    isOpen = !isOpen;
    chat.classList.toggle('open', isOpen);
    if (isOpen) input.focus();
  });

  close.addEventListener('click', () => {
    isOpen = false;
    chat.classList.remove('open');
  });

  // Send message
  async function sendMessage() {
    const text = input.value.trim();
    if (!text || isLoading) return;

    // Remove welcome message
    if (hasWelcome) {
      messages.innerHTML = '';
      hasWelcome = false;
    }

    // Add user message
    addMessage(text, 'user');
    input.value = '';

    // Show typing indicator
    isLoading = true;
    send.disabled = true;
    const typingEl = document.createElement('div');
    typingEl.className = 'agentic-widget-typing';
    typingEl.innerHTML = '<span></span><span></span><span></span>';
    messages.appendChild(typingEl);
    messages.scrollTop = messages.scrollHeight;

    try {
      const response = await fetch(`${apiUrl}/embed/${token}/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: text })
      });

      const data = await response.json();
      typingEl.remove();

      if (response.status === 402) {
        // Billing/credit error
        addMessage('The chatbot owner has run out of credits. Please contact them to enable the service.', 'error');
      } else if (data.success) {
        addMessage(data.answer, 'assistant');
      } else {
        addMessage(data.error || 'Sorry, something went wrong.', 'error');
      }
    } catch (error) {
      typingEl.remove();
      addMessage('Unable to connect. Please try again.', 'error');
    }

    isLoading = false;
    send.disabled = false;
  }

  function addMessage(text, type) {
    const msg = document.createElement('div');
    msg.className = `agentic-widget-message ${type}`;
    msg.textContent = text;
    messages.appendChild(msg);
    messages.scrollTop = messages.scrollHeight;
  }

  send.addEventListener('click', sendMessage);
  input.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendMessage();
  });

})();
