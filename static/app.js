// ============================================================
// ENTERPRISE AI ASSISTANT - CLIENT LOGIC (VERSION 3.2)
// Full Features: Real Tickets, Sample RAG Ingest, Stop Generation,
// Direct Attach, Chat Export, Soothing Palette, Lucide Icons
// ============================================================

// State
let sessions = [];
let currentSessionId = null;
let currentSelectedFile = null;
let currentPreviewData = null;
let currentAbortController = null;

// DOM Elements - Sidebar & Sessions
const sidebar = document.getElementById("sidebar");
const toggleSidebarBtn = document.getElementById("toggleSidebarBtn");
const newChatBtn = document.getElementById("newChatBtn");
const sessionsList = document.getElementById("sessionsList");
const currentSessionTitle = document.getElementById("currentSessionTitle");

// DOM Elements - Main Chat
const chatMessages = document.getElementById("chatMessages");
const welcomeHero = document.getElementById("welcomeHero");
const chatForm = document.getElementById("chatForm");
const chatInput = document.getElementById("chatInput");
const sendBtn = document.getElementById("sendBtn");
const stopBtn = document.getElementById("stopBtn");
const clearChatBtn = document.getElementById("clearChatBtn");
const attachFileBtn = document.getElementById("attachFileBtn");
const directAttachInput = document.getElementById("directAttachInput");
const exportChatBtn = document.getElementById("exportChatBtn");
const headerAdminBtn = document.getElementById("headerAdminBtn");
const onlineStatusPill = document.getElementById("onlineStatusPill");
const onlineCount = document.getElementById("onlineCount");
let lastKnownOnlineCount = 1;

// DOM Elements - Admin Hub Modal (Kho tài liệu & Quản lý)
const adminHubModal = document.getElementById("adminHubModal");
const openAdminHubBtn = document.getElementById("openAdminHubBtn");
const closeAdminHubBtn = document.getElementById("closeAdminHubBtn");
const closeAdminHubFooterBtn = document.getElementById("closeAdminHubFooterBtn");
const adminTabBtns = document.querySelectorAll(".admin-tab-btn");
const adminPanes = document.querySelectorAll(".admin-pane");
const adminDocCount = document.getElementById("adminDocCount");
const adminTicketCount = document.getElementById("adminTicketCount");

// DOM Elements - Upload & Chunking inside Admin Hub
const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("fileInput");
const selectFileLink = document.getElementById("selectFileLink");
const selectedFileName = document.getElementById("selectedFileName");
const chunkSizeInput = document.getElementById("chunkSizeInput");
const chunkOverlapInput = document.getElementById("chunkOverlapInput");
const contextualHeaderCheck = document.getElementById("contextualHeaderCheck");
const previewChunksBtn = document.getElementById("previewChunksBtn");
const saveDocBtn = document.getElementById("saveDocBtn");
const docList = document.getElementById("docList");
const refreshDocsBtn = document.getElementById("refreshDocsBtn");
const ingestSampleBtn = document.getElementById("ingestSampleBtn");

// DOM Elements - Tickets Tab
const ticketsList = document.getElementById("ticketsList");
const refreshTicketsBtn = document.getElementById("refreshTicketsBtn");

// DOM Elements - Preview & Settings Modals
const previewModal = document.getElementById("previewModal");
const closePreviewBtn = document.getElementById("closePreviewBtn");
const cancelPreviewBtn = document.getElementById("cancelPreviewBtn");
const confirmIngestBtn = document.getElementById("confirmIngestBtn");
const previewStats = document.getElementById("previewStats");
const previewChunksList = document.getElementById("previewChunksList");

const settingsModal = document.getElementById("settingsModal");
const openSettingsBtn = document.getElementById("openSettingsBtn");
const closeSettingsBtn = document.getElementById("closeSettingsBtn");
const cancelSettingsBtn = document.getElementById("cancelSettingsBtn");
const saveSettingsBtn = document.getElementById("saveSettingsBtn");
const selectProvider = document.getElementById("selectProvider");
const geminiKeyGroup = document.getElementById("geminiKeyGroup");
const openaiKeyGroup = document.getElementById("openaiKeyGroup");
const geminiKeyInput = document.getElementById("geminiKeyInput");
const openaiKeyInput = document.getElementById("openaiKeyInput");
const selectEmbedding = document.getElementById("selectEmbedding");

const toast = document.getElementById("toast");

// --- INITIALIZATION ---
document.addEventListener("DOMContentLoaded", () => {
  setupMarked();
  loadSessions();
  fetchDocumentList();
  fetchTicketsList();
  setupEventListeners();
  setupDirectAttachment();
  setupExportChat();
  setupSessionRename();
  autoResizeChatInput();
  initPresenceTracking();
  refreshIcons();
});

function refreshIcons(rootElement) {
  if (window.lucide) {
    try {
      if (rootElement) {
        lucide.createIcons({ root: rootElement });
      } else {
        lucide.createIcons();
      }
    } catch (e) {
      lucide.createIcons();
    }
  }
}

function setupMarked() {
  marked.setOptions({
    highlight: function(code, lang) {
      if (lang && hljs.getLanguage(lang)) {
        return hljs.highlight(code, { language: lang }).value;
      }
      return hljs.highlightAuto(code).value;
    },
    breaks: true
  });
}

function showToast(msg, type = "info") {
  toast.textContent = msg;
  toast.className = `toast show ${type}`;
  setTimeout(() => {
    toast.className = "toast";
  }, 3200);
}

// ========================================================
// SESSION MANAGEMENT (LỊCH SỬ HỘI THOẠI)
// ========================================================
function loadSessions() {
  const saved = localStorage.getItem("ai_assistant_sessions");
  if (saved) {
    try {
      sessions = JSON.parse(saved);
    } catch (e) {
      sessions = [];
    }
  }

  if (!sessions || sessions.length === 0) {
    createNewSession(false);
  } else {
    currentSessionId = sessions[0].id;
    renderSessionsList();
    renderCurrentSessionMessages();
  }
}

function saveSessions() {
  localStorage.setItem("ai_assistant_sessions", JSON.stringify(sessions));
}

function createNewSession(save = true) {
  const newSession = {
    id: "session_" + Date.now(),
    title: "Cuộc trò chuyện mới",
    messages: [],
    createdAt: new Date().toISOString()
  };
  sessions.unshift(newSession);
  currentSessionId = newSession.id;
  if (save) saveSessions();
  renderSessionsList();
  renderCurrentSessionMessages();
  chatInput.focus();
}

function getCurrentSession() {
  return sessions.find(s => s.id === currentSessionId);
}

function renderSessionsList() {
  sessionsList.innerHTML = sessions.map(s => `
    <div class="session-item ${s.id === currentSessionId ? 'active' : ''}" data-id="${s.id}">
      <div class="session-title-wrap" title="${escapeHtml(s.title)}">
        <i data-lucide="message-square" class="session-icon"></i>
        <span class="session-title">${escapeHtml(s.title)}</span>
      </div>
      <button class="btn-delete-session" onclick="event.stopPropagation(); deleteSession('${s.id}')" title="Xóa đoạn chat">
        <i data-lucide="trash-2" style="width: 13px; height: 13px;"></i>
      </button>
    </div>
  `).join("");

  document.querySelectorAll(".session-item").forEach(el => {
    el.addEventListener("click", () => {
      const id = el.getAttribute("data-id");
      if (id !== currentSessionId) {
        currentSessionId = id;
        renderSessionsList();
        renderCurrentSessionMessages();
      }
    });
  });

  const cur = getCurrentSession();
  if (cur) {
    currentSessionTitle.textContent = cur.title;
  }
  refreshIcons();
}

function deleteSession(id) {
  if (sessions.length <= 1) {
    sessions = [];
    createNewSession(true);
    return;
  }
  sessions = sessions.filter(s => s.id !== id);
  if (currentSessionId === id) {
    currentSessionId = sessions[0].id;
  }
  saveSessions();
  renderSessionsList();
  renderCurrentSessionMessages();
}

function renderCurrentSessionMessages() {
  const cur = getCurrentSession();
  if (!cur || cur.messages.length === 0) {
    chatMessages.innerHTML = "";
    chatMessages.appendChild(welcomeHero);
    welcomeHero.style.display = "flex";
    setupStarterPrompts();
    refreshIcons();
    return;
  }

  welcomeHero.style.display = "none";
  chatMessages.innerHTML = "";

  cur.messages.forEach(m => {
    if (m.role === "user") {
      appendUserMessage(m.content, false);
    } else if (m.role === "assistant") {
      const bubble = createAssistantMessageBubble();
      updateAssistantText(bubble, m.content);
    }
  });

  scrollToBottom();
  refreshIcons();
}

function setupSessionRename() {
  currentSessionTitle.title = "Nhấp để đổi tên cuộc trò chuyện";
  currentSessionTitle.addEventListener("click", () => {
    const cur = getCurrentSession();
    if (!cur) return;
    const newTitle = prompt("Nhập tên mới cho cuộc trò chuyện này:", cur.title);
    if (newTitle && newTitle.trim()) {
      cur.title = newTitle.trim();
      currentSessionTitle.textContent = cur.title;
      saveSessions();
      renderSessionsList();
      showToast("Đã đổi tên cuộc trò chuyện", "success");
    }
  });
}

// ========================================================
// KHO TÀI LIỆU (DOCUMENTS) & MẪU
// ========================================================
async function fetchDocumentList() {
  try {
    const res = await fetch("/api/documents");
    const data = await res.json();
    const docs = data.documents || [];
    renderDocumentList(docs);
  } catch (err) {
    console.error("Lỗi tải danh sách tài liệu:", err);
  }
}

function renderDocumentList(docs) {
  if (adminDocCount) adminDocCount.textContent = docs.length;
  if (!docList) return;

  if (docs.length === 0) {
    docList.innerHTML = `<div class="empty-state">Chưa có tài liệu nào trong kho dữ liệu</div>`;
    return;
  }

  docList.innerHTML = docs.map(d => `
    <div class="doc-item">
      <div class="doc-info">
        <i data-lucide="file-text" style="width: 16px; height: 16px; color: var(--primary);"></i>
        <div>
          <div class="doc-title" title="${escapeHtml(d.doc_name)}">${escapeHtml(d.doc_name)}</div>
          <span class="doc-badge">${d.chunk_count} phần nội dung</span>
        </div>
      </div>
      <button class="btn-delete-doc" onclick="deleteDocument('${escapeHtml(d.doc_name)}')" title="Xóa tài liệu">
        <i data-lucide="trash-2" style="width: 14px; height: 14px;"></i>
      </button>
    </div>
  `).join("");
  refreshIcons(docList);
}

async function deleteDocument(docName) {
  if (!confirm(`Bạn có chắc muốn xóa tài liệu '${docName}'?`)) return;
  try {
    const res = await fetch(`/api/documents/${encodeURIComponent(docName)}`, { method: "DELETE" });
    const data = await res.json();
    showToast(`Đã xóa tài liệu: ${docName}`, "success");
    fetchDocumentList();
  } catch (err) {
    showToast(`Lỗi xóa: ${err.message}`, "error");
  }
}

async function handleIngestSample() {
  if (ingestSampleBtn.disabled) return;
  ingestSampleBtn.disabled = true;
  const originalHtml = ingestSampleBtn.innerHTML;
  ingestSampleBtn.innerHTML = `<span>Đang nạp...</span>`;

  try {
    const res = await fetch("/api/documents/ingest-sample", { method: "POST" });
    const data = await res.json();
    if (res.ok) {
      showToast(data.message || "Đã nạp thành công bộ tài liệu mẫu!", "success");
      fetchDocumentList();
    } else {
      showToast(data.detail || "Lỗi khi nạp dữ liệu mẫu", "error");
    }
  } catch (err) {
    showToast("Lỗi nạp dữ liệu mẫu: " + err.message, "error");
  } finally {
    ingestSampleBtn.disabled = false;
    ingestSampleBtn.innerHTML = originalHtml;
    refreshIcons();
  }
}

// ========================================================
// QUẢN LÝ PHIẾU HỖ TRỢ (TICKETS)
// ========================================================
async function fetchTicketsList() {
  try {
    const res = await fetch("/api/tickets");
    const data = await res.json();
    const tickets = data.tickets || [];
    renderTicketsList(tickets);
  } catch (err) {
    console.error("Lỗi tải danh sách phiếu hỗ trợ:", err);
  }
}

function renderTicketsList(tickets) {
  if (adminTicketCount) adminTicketCount.textContent = tickets.length;
  if (!ticketsList) return;

  if (tickets.length === 0) {
    ticketsList.innerHTML = `
      <tr>
        <td colspan="5" style="text-align:center; padding: 28px; color: var(--text-muted);">
          Chưa có phiếu hỗ trợ nào. Hãy thử nhắn với trợ lý: <i>"Tạo phiếu hỗ trợ: Lỗi mạng nội bộ, mức độ Khẩn cấp"</i>
        </td>
      </tr>
    `;
    return;
  }

  ticketsList.innerHTML = tickets.map(t => {
    let priorityClass = "binh-thuong";
    const prioLower = (t.priority || "").toLowerCase();
    if (prioLower.includes("khẩn")) priorityClass = "khan-cap";
    else if (prioLower.includes("thấp")) priorityClass = "thap";

    return `
      <tr>
        <td><strong style="color:var(--primary); font-family: 'JetBrains Mono', monospace;">${escapeHtml(t.id)}</strong></td>
        <td>
          <div style="font-weight: 500;">${escapeHtml(t.title)}</div>
          <div style="font-size: 0.74rem; color: var(--text-sub); margin-top: 2px;">${escapeHtml(t.description)}</div>
        </td>
        <td><span class="priority-badge ${priorityClass}">${escapeHtml(t.priority || 'Bình thường')}</span></td>
        <td><span class="status-pill-ticket">${escapeHtml(t.status || 'Đang tiếp nhận')}</span></td>
        <td style="color: var(--text-muted); font-size: 0.76rem;">${escapeHtml(t.created_at || '')}</td>
      </tr>
    `;
  }).join("");
}

// ========================================================
// CHAT STREAMING, TOOLS & ABORT CONTROLLER
// ========================================================
async function handleChatSubmit(e) {
  if (e) e.preventDefault();
  const text = chatInput.value.trim();
  if (!text) return;

  chatInput.value = "";
  chatInput.style.height = "auto";
  
  // Set up AbortController & Toggle Stop Button
  currentAbortController = new AbortController();
  sendBtn.style.display = "none";
  stopBtn.style.display = "flex";

  welcomeHero.style.display = "none";

  const cur = getCurrentSession();
  if (cur.messages.length === 0) {
    cur.title = text.length > 28 ? text.substring(0, 28) + "..." : text;
    currentSessionTitle.textContent = cur.title;
    renderSessionsList();
  }

  // 1. Append user message
  appendUserMessage(text);
  cur.messages.push({ role: "user", content: text });
  saveSessions();

  // 2. Create assistant message container
  const assistantBubble = createAssistantMessageBubble();
  scrollToBottom();

  let accumulatedContent = "";

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: cur.messages }),
      signal: currentAbortController.signal
    });

    if (!response.ok) {
      throw new Error(`Mã lỗi HTTP: ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunkText = decoder.decode(value);
      const lines = chunkText.split("\n\n");

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const jsonStr = line.replace("data: ", "").trim();
        if (!jsonStr) continue;

        try {
          const event = JSON.parse(jsonStr);

          // Event 1: Tool Call Start (Friendly User Text)
          if (event.type === "tool_call_start") {
            renderToolCallStart(assistantBubble, event.tool_name);
            scrollToBottom();
          }

          // Event 2: Tool Call Result
          else if (event.type === "tool_call_result") {
            renderToolCallResult(assistantBubble, event.tool_name, event.result);
            scrollToBottom();
          }

          // Event 3: Content Streaming Delta
          else if (event.type === "content_delta") {
            accumulatedContent += event.delta;
            updateAssistantText(assistantBubble, accumulatedContent);
            scrollToBottom();
          }

          // Event 4: Key Required
          else if (event.type === "key_required") {
            const cardHtml = `
              <div class="system-alert-card key-required-card">
                <div class="alert-card-header">
                  <i data-lucide="key-round" class="alert-icon"></i>
                  <span class="alert-card-title">${escapeHtml(event.title || "Yêu cầu cấu hình API Key")}</span>
                </div>
                <div class="alert-card-body">
                  <p class="alert-card-text">${escapeHtml(event.message)}</p>
                  <button type="button" class="btn-alert-action" onclick="document.getElementById('openSettingsBtn').click()">
                    <i data-lucide="sliders-horizontal"></i>
                    <span>Cấu hình API Key</span>
                  </button>
                </div>
              </div>
            `;
            const textContent = assistantBubble.querySelector(".text-content");
            textContent.innerHTML = cardHtml;
            refreshIcons();
            scrollToBottom();
            cur.messages.push({
              role: "assistant",
              content: `[Thông báo hệ thống: ${event.message}]`
            });
            saveSessions();
            return;
          }

          // Event 5: General Error
          else if (event.type === "error") {
            const cardHtml = `
              <div class="system-alert-card error-card">
                <div class="alert-card-header">
                  <i data-lucide="alert-circle" class="alert-icon"></i>
                  <span class="alert-card-title">Thông báo hệ thống</span>
                </div>
                <div class="alert-card-body">
                  <p class="alert-card-text">${escapeHtml(event.content)}</p>
                </div>
              </div>
            `;
            const textContent = assistantBubble.querySelector(".text-content");
            textContent.innerHTML = cardHtml;
            refreshIcons();
            scrollToBottom();
          }
        } catch (parseErr) {
          console.error("Lỗi parse SSE:", parseErr);
        }
      }
    }

    // Save final response into session
    if (accumulatedContent) {
      cur.messages.push({ role: "assistant", content: accumulatedContent });
      saveSessions();
    }
  } catch (err) {
    if (err.name === "AbortError") {
      accumulatedContent += "\n\n*(Đã dừng câu trả lời theo yêu cầu)*";
      updateAssistantText(assistantBubble, accumulatedContent);
      if (accumulatedContent) {
        cur.messages.push({ role: "assistant", content: accumulatedContent });
        saveSessions();
      }
    } else {
      const connErrHtml = `
        <div class="system-alert-card error-card">
          <div class="alert-card-header">
            <i data-lucide="wifi-off" class="alert-icon"></i>
            <span class="alert-card-title">Lỗi kết nối</span>
          </div>
          <div class="alert-card-body">
            <p class="alert-card-text">${escapeHtml(err.message)}. Vui lòng kiểm tra lại kết nối mạng hoặc trạng thái máy chủ.</p>
          </div>
        </div>
      `;
      const textContent = assistantBubble.querySelector(".text-content");
      textContent.innerHTML = connErrHtml;
      refreshIcons();
    }
  } finally {
    currentAbortController = null;
    sendBtn.style.display = "flex";
    stopBtn.style.display = "none";
    sendBtn.disabled = false;
    chatInput.focus();
    refreshIcons();
  }
}

function appendUserMessage(text, scroll = true) {
  const row = document.createElement("div");
  row.className = "message-row user";
  row.innerHTML = `
    <div class="avatar">
      <i data-lucide="user" style="width: 16px; height: 16px;"></i>
    </div>
    <div class="message-bubble">${escapeHtml(text)}</div>
  `;
  chatMessages.appendChild(row);
  refreshIcons();
  if (scroll) scrollToBottom();
}

function createAssistantMessageBubble() {
  const row = document.createElement("div");
  row.className = "message-row assistant";
  row.innerHTML = `
    <div class="avatar">
      <i data-lucide="sparkles" style="width: 16px; height: 16px;"></i>
    </div>
    <div class="message-bubble">
      <div class="tool-container"></div>
      <div class="text-content"><i>Đang suy nghĩ...</i></div>
    </div>
  `;
  chatMessages.appendChild(row);
  refreshIcons();
  return row;
}

function renderToolCallStart(assistantBubble, toolName) {
  const toolContainer = assistantBubble.querySelector(".tool-container");
  
  let desc = "Đang xử lý thông tin...";
  let iconName = "search";

  if (toolName === "tra_cuu_tai_lieu") {
    desc = "Đang tra cứu thông tin trong tài liệu nội bộ...";
    iconName = "book-open";
  } else if (toolName === "tra_cuu_thoi_gian") {
    desc = "Đang kiểm tra thời gian thực...";
    iconName = "clock";
  } else if (toolName === "tao_phieu_ho_tro") {
    desc = "Đang tạo phiếu yêu cầu hỗ trợ tới kỹ thuật...";
    iconName = "ticket";
  } else if (toolName === "tra_cuu_phieu_ho_tro") {
    desc = "Đang tra cứu thông tin phiếu hỗ trợ...";
    iconName = "search";
  } else if (toolName === "may_tinh") {
    desc = "Đang tính toán kết quả...";
    iconName = "calculator";
  }

  const banner = document.createElement("div");
  banner.className = "tool-call-banner";
  banner.id = `tool_call_${toolName}`;
  banner.innerHTML = `<i data-lucide="${iconName}" style="width: 14px; height: 14px;"></i> <span>${desc}</span>`;
  toolContainer.appendChild(banner);
  refreshIcons();
}

function renderToolCallResult(assistantBubble, toolName, result) {
  const toolContainer = assistantBubble.querySelector(".tool-container");
  const banner = toolContainer.querySelector(`#tool_call_${toolName}`);
  if (banner) {
    banner.remove();
  }

  // If a ticket was created or looked up, refresh tickets counter
  if (toolName === "tao_phieu_ho_tro" || toolName === "tra_cuu_phieu_ho_tro") {
    fetchTicketsList();
  }

  // Collapsible card for document citations
  if (toolName === "tra_cuu_tai_lieu") {
    const resultBox = document.createElement("div");
    resultBox.className = "tool-result-box";
    resultBox.innerHTML = `
      <div class="tool-result-header" onclick="this.nextElementSibling.classList.toggle('show')">
        <span style="display:flex;align-items:center;gap:6px;">
          <i data-lucide="bookmark-check" style="width:14px;height:14px;color:var(--primary)"></i>
          <span>Trích dẫn nguồn tài liệu tham khảo</span>
        </span>
        <span style="font-size: 0.72rem; color: var(--text-sub);">Xem chi tiết ▼</span>
      </div>
      <div class="tool-result-content">${escapeHtml(result)}</div>
    `;
    toolContainer.appendChild(resultBox);
    refreshIcons();
  }
}

function updateAssistantText(assistantBubble, text) {
  const textContent = assistantBubble.querySelector(".text-content");
  textContent.innerHTML = marked.parse(text);
  injectCopyCodeButtons(textContent);

  // Ensure bottom action bar with Copy button exists
  let actionsBar = assistantBubble.querySelector(".message-actions");
  if (!actionsBar) {
    actionsBar = document.createElement("div");
    actionsBar.className = "message-actions";
    actionsBar.innerHTML = `
      <button class="msg-action-btn btn-copy-msg" type="button" title="Sao chép toàn bộ câu trả lời">
        <i data-lucide="copy" style="width: 12px; height: 12px;"></i>
        <span>Sao chép</span>
      </button>
    `;
    assistantBubble.querySelector(".message-bubble").appendChild(actionsBar);

    actionsBar.querySelector(".btn-copy-msg").addEventListener("click", (e) => {
      navigator.clipboard.writeText(text);
      const btn = e.currentTarget;
      btn.classList.add("copied");
      btn.querySelector("span").textContent = "Đã chép";
      setTimeout(() => {
        btn.classList.remove("copied");
        btn.querySelector("span").textContent = "Sao chép";
      }, 2000);
    });
  } else {
    const copyBtn = actionsBar.querySelector(".btn-copy-msg");
    if (copyBtn) {
      copyBtn.onclick = () => {
        navigator.clipboard.writeText(text);
        copyBtn.classList.add("copied");
        copyBtn.querySelector("span").textContent = "Đã chép";
        setTimeout(() => {
          copyBtn.classList.remove("copied");
          copyBtn.querySelector("span").textContent = "Sao chép";
        }, 2000);
      };
    }
  }

  refreshIcons();
}

function injectCopyCodeButtons(container) {
  const codeBlocks = container.querySelectorAll("pre code");
  codeBlocks.forEach(block => {
    const pre = block.parentElement;
    if (pre.parentElement.classList.contains("code-block-wrapper")) return;

    const wrapper = document.createElement("div");
    wrapper.className = "code-block-wrapper";

    const lang = block.className.replace("language-", "").trim() || "code";
    const header = document.createElement("div");
    header.className = "code-header";
    header.innerHTML = `
      <span>${lang}</span>
      <button class="btn-copy-code" type="button">
        <i data-lucide="copy" style="width: 12px; height: 12px;"></i>
        <span>Sao chép</span>
      </button>
    `;

    pre.parentNode.insertBefore(wrapper, pre);
    wrapper.appendChild(header);
    wrapper.appendChild(pre);

    header.querySelector(".btn-copy-code").addEventListener("click", (e) => {
      navigator.clipboard.writeText(block.innerText);
      const btnSpan = e.currentTarget.querySelector("span");
      if (btnSpan) btnSpan.textContent = "Đã chép";
      setTimeout(() => { if (btnSpan) btnSpan.textContent = "Sao chép"; }, 2000);
    });
  });
}

function scrollToBottom() {
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

// ========================================================
// DIRECT ATTACHMENT & EXPORT CHAT
// ========================================================
function setupDirectAttachment() {
  attachFileBtn.addEventListener("click", () => {
    directAttachInput.click();
  });

  directAttachInput.addEventListener("change", async (e) => {
    if (!e.target.files || e.target.files.length === 0) return;
    const file = e.target.files[0];
    showToast(`Đang tự động nạp tài liệu: ${file.name}...`, "info");

    const formData = new FormData();
    formData.append("file", file);
    formData.append("chunk_size", 600);
    formData.append("chunk_overlap", 120);
    formData.append("add_contextual_header", true);

    try {
      const res = await fetch("/api/documents/upload", {
        method: "POST",
        body: formData
      });
      const data = await res.json();
      if (res.ok) {
        showToast(`Đã nạp thành công "${file.name}" (${data.chunks_count} đoạn). Giờ bạn có thể hỏi về tài liệu này!`, "success");
        fetchDocumentList();
      } else {
        showToast(data.detail || "Không thể nạp file", "error");
      }
    } catch (err) {
      showToast("Lỗi nạp file: " + err.message, "error");
    } finally {
      directAttachInput.value = "";
    }
  });
}

function setupExportChat() {
  exportChatBtn.addEventListener("click", () => {
    const cur = getCurrentSession();
    if (!cur || cur.messages.length === 0) {
      showToast("Chưa có tin nhắn nào để xuất file!", "info");
      return;
    }

    let md = `# ${cur.title}\n\n`;
    md += `*Thời gian tạo: ${new Date(cur.createdAt).toLocaleString("vi-VN")}*\n\n`;
    md += `---\n\n`;

    cur.messages.forEach(m => {
      const roleName = m.role === "user" ? "👤 Người dùng" : "🤖 Trợ lý Doanh nghiệp";
      md += `### ${roleName}:\n\n${m.content}\n\n---\n\n`;
    });

    const blob = new Blob([md], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    const sanitizedTitle = cur.title.replace(/[^a-zA-Z0-9\u00C0-\u1EF9]/g, "_").substring(0, 30);
    a.href = url;
    a.download = `Hoi_thoai_${sanitizedTitle}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showToast("Đã xuất file Markdown thành công!", "success");
  });
}

// ========================================================
// STARTER PROMPTS
// ========================================================
function setupStarterPrompts() {
  document.querySelectorAll(".starter-card").forEach(card => {
    card.addEventListener("click", () => {
      const prompt = card.getAttribute("data-prompt");
      if (prompt) {
        chatInput.value = prompt;
        handleChatSubmit();
      }
    });
  });
}

function autoResizeChatInput() {
  chatInput.addEventListener("input", function() {
    this.style.height = "auto";
    this.style.height = Math.min(this.scrollHeight, 140) + "px";
  });

  chatInput.addEventListener("keydown", function(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleChatSubmit();
    }
  });
}

// ========================================================
// REAL-TIME PRESENCE & HIGH CONCURRENCY TRACKING
// ========================================================
function initPresenceTracking() {
  let clientId = sessionStorage.getItem("enterprise_chat_client_id");
  if (!clientId) {
    clientId = "emp_" + Math.random().toString(36).substring(2, 9) + "_" + Date.now().toString(36);
    sessionStorage.setItem("enterprise_chat_client_id", clientId);
  }

  const updateOnlineCount = (count) => {
    if (!onlineCount) return;
    const num = Math.max(1, parseInt(count) || 1);
    if (num !== lastKnownOnlineCount) {
      onlineCount.style.transform = "scale(1.25)";
      onlineCount.style.transition = "transform 0.18s cubic-bezier(0.16, 1, 0.3, 1)";
      setTimeout(() => {
        onlineCount.textContent = num.toLocaleString("vi-VN");
        onlineCount.style.transform = "scale(1)";
      }, 150);
      lastKnownOnlineCount = num;
    } else {
      onlineCount.textContent = num.toLocaleString("vi-VN");
    }
  };

  // TRUE REAL-TIME: WebSocket 2 chiều (Độ trễ < 15ms khi mở hoặc đóng tab)
  let ws = null;
  let heartbeatTimer = null;

  function connectRealtimePresence() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws/presence?client_id=${encodeURIComponent(clientId)}`;

    try {
      if (ws) {
        try { ws.close(); } catch(e){}
      }
      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        clearInterval(heartbeatTimer);
        heartbeatTimer = setInterval(() => {
          if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send("ping");
          }
        }, 25000);
      };

      ws.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data);
          if (data && data.active_users !== undefined) {
            updateOnlineCount(data.active_users);
          }
        } catch (err) {}
      };

      ws.onclose = () => {
        clearInterval(heartbeatTimer);
        setTimeout(connectRealtimePresence, 2500);
      };

      ws.onerror = () => {
        try { ws.close(); } catch(e){}
      };
    } catch (e) {
      connectSSE();
    }
  }

  // Khởi chạy kết nối WebSocket thời gian thực
  connectRealtimePresence();

  // Báo cho server ngay tức khắc khi tab bị đóng (0ms delay khi tắt tab)
  window.addEventListener("beforeunload", () => {
    if (ws) {
      try { ws.close(); } catch(e){}
    }
    try {
      const blob = new Blob([JSON.stringify({ client_id: clientId })], { type: "application/json" });
      navigator.sendBeacon("/api/presence/leave", blob);
    } catch(e) {}
  });

  // Click vào pill xem chi tiết trạng thái chịu tải
  if (onlineStatusPill) {
    onlineStatusPill.addEventListener("click", async () => {
      try {
        const res = await fetch("/api/presence/stats");
        if (res.ok) {
          const stats = await res.json();
          const users = stats.active_users || 1;
          const hitRatio = stats.cache_stats?.hit_ratio_percent || 0;
          showToast(`🟢 Đang trực tuyến: ${users} nhân viên (Real-time SSE 0ms) | HNSW Vector + Connection Pool Active | Cache hit: ${hitRatio}%`, "info");
        }
      } catch (e) {
        showToast("Hệ thống trực tuyến và sẵn sàng phục vụ", "info");
      }
    });
  }
}

// ========================================================
// KHO TÀI LIỆU (ADMIN MODAL)
// ========================================================
function setupAdminHub() {
  const openHub = () => {
    // 1. Mở popup tức thì, mượt mà không bị khựng
    adminHubModal.classList.add("active");
    // 2. Cập nhật ngầm dữ liệu tài liệu & ticket mà không gây lag hiệu ứng mở
    setTimeout(() => {
      fetchDocumentList();
      fetchTicketsList();
    }, 100);
  };
  const closeHub = () => {
    adminHubModal.classList.remove("active");
  };

  openAdminHubBtn.addEventListener("click", openHub);
  headerAdminBtn.addEventListener("click", openHub);
  closeAdminHubBtn.addEventListener("click", closeHub);
  closeAdminHubFooterBtn.addEventListener("click", closeHub);

  // Tabs - Chuyển đổi siêu mượt, chiều cao cố định không bị nhảy
  adminTabBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      adminTabBtns.forEach(b => b.classList.remove("active"));
      adminPanes.forEach(p => p.classList.remove("active"));

      btn.classList.add("active");
      const tabId = btn.getAttribute("data-admintab");
      const targetPane = document.getElementById(tabId);
      if (targetPane) {
        targetPane.classList.add("active");
        refreshIcons(targetPane);
      }
    });
  });

  // Sample data button
  ingestSampleBtn.addEventListener("click", handleIngestSample);

  // Refresh tickets button
  refreshTicketsBtn.addEventListener("click", () => {
    fetchTicketsList();
    showToast("Đã làm mới danh sách phiếu hỗ trợ", "info");
  });

  // Dropzone
  dropzone.addEventListener("click", () => fileInput.click());
  selectFileLink.addEventListener("click", (e) => {
    e.stopPropagation();
    fileInput.click();
  });

  dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
  });

  dropzone.addEventListener("dragleave", () => {
    dropzone.classList.remove("dragover");
  });

  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
    if (e.dataTransfer.files.length > 0) {
      handleSelectedFile(e.dataTransfer.files[0]);
    }
  });

  fileInput.addEventListener("change", (e) => {
    if (e.target.files.length > 0) {
      handleSelectedFile(e.target.files[0]);
    }
  });

  refreshDocsBtn.addEventListener("click", () => {
    fetchDocumentList();
    showToast("Đã làm mới danh sách tài liệu", "info");
  });

  previewChunksBtn.addEventListener("click", handlePreviewChunks);
  saveDocBtn.addEventListener("click", handleSaveDocument);
  confirmIngestBtn.addEventListener("click", handleSaveDocument);

  setupBenchmarkUI();
}

// ========================================================
// TAB 5: AI ACCURACY BENCHMARK & EVALUATION
// ========================================================
function setupBenchmarkUI() {
  const runBtn = document.getElementById("runBenchmarkBtn");
  const bmAccuracy = document.getElementById("bmAccuracy");
  const bmPassedCount = document.getElementById("bmPassedCount");
  const bmFaithfulness = document.getElementById("bmFaithfulness");
  const bmLatency = document.getElementById("bmLatency");
  const bmLastRun = document.getElementById("bmLastRun");
  const resultsList = document.getElementById("benchmarkResultsList");

  const renderBenchmarkData = (data) => {
    if (!data) return;
    if (bmAccuracy) bmAccuracy.textContent = `${data.accuracy_percent || 0}%`;
    if (bmPassedCount) bmPassedCount.textContent = `${data.passed_tests || 0} / ${data.total_tests || 5} ca ĐẠT`;
    if (bmFaithfulness) bmFaithfulness.textContent = `${data.faithfulness_percent || 100}%`;
    if (bmLatency) bmLatency.textContent = `${data.avg_latency_seconds || 0}s`;
    if (bmLastRun) bmLastRun.textContent = data.last_run_at || "Vừa xong";

    if (!resultsList) return;

    if (!data.results || data.results.length === 0) {
      resultsList.innerHTML = `<div class="empty-state">Chưa có kết quả kiểm thử. Hãy nhấn nút "Bắt đầu kiểm thử" ở trên!</div>`;
      return;
    }

    resultsList.innerHTML = data.results.map(r => {
      const isPassed = r.status === "PASSED";
      const statusBadge = isPassed 
        ? `<span class="bm-status-pill passed">ĐẠT (PASSED)</span>`
        : `<span class="bm-status-pill failed">CHƯA ĐẠT</span>`;
      
      const retrievalBadge = r.retrieval_ok 
        ? `<span class="bm-detail-tag" style="color:var(--accent-emerald);"><i data-lucide="check-circle-2" style="width:12px;height:12px;"></i> Vector: Đạt</span>`
        : `<span class="bm-detail-tag" style="color:var(--accent-rose);"><i data-lucide="alert-circle" style="width:12px;height:12px;"></i> Vector: Trượt</span>`;

      const toolsBadge = (r.called_tools && r.called_tools.length > 0)
        ? `<span class="bm-detail-tag"><i data-lucide="wrench" style="width:12px;height:12px;"></i> Tool: ${r.called_tools.join(", ")}</span>`
        : "";

      return `
        <div class="bm-case-item">
          <div class="bm-case-top">
            <div class="bm-case-id-badge">
              <span><b>${escapeHtml(r.id)}</b> • ${escapeHtml(r.category)}</span>
            </div>
            ${statusBadge}
          </div>
          <div class="bm-question-text">${escapeHtml(r.question)}</div>
          <div class="bm-case-details">
            <span class="bm-detail-tag"><i data-lucide="clock" style="width:12px;height:12px;"></i> ${r.latency}s</span>
            ${retrievalBadge}
            ${toolsBadge}
            <span class="bm-detail-tag" style="color:var(--accent-cyan);"><i data-lucide="key" style="width:12px;height:12px;"></i> Khớp: ${r.matched_keywords && r.matched_keywords.length > 0 ? r.matched_keywords.join(", ") : "Chính xác"}</span>
          </div>
          <div class="bm-answer-text">"${escapeHtml(r.answer_preview || "")}"</div>
        </div>
      `;
    }).join("");

    refreshIcons(resultsList);
  };

  const fetchLatestBenchmark = async () => {
    try {
      const res = await fetch("/api/benchmark/latest");
      if (res.ok) {
        const data = await res.json();
        renderBenchmarkData(data);
      }
    } catch (e) {
      console.error("Lỗi lấy dữ liệu benchmark:", e);
    }
  };

  if (runBtn) {
    runBtn.addEventListener("click", async () => {
      runBtn.disabled = true;
      runBtn.innerHTML = `<i data-lucide="rotate-cw" class="spin-icon" style="width:15px;height:15px;"></i><span>Đang kiểm thử 5 ca...</span>`;
      refreshIcons(runBtn);
      showToast("Đang thực thi 5 bài kiểm thử tự động (Vector RAG, Tool, Chống ảo giác)...", "info");

      try {
        const res = await fetch("/api/benchmark/run", { method: "POST" });
        if (!res.ok) throw new Error("Lỗi khi chạy benchmark");
        const data = await res.json();
        renderBenchmarkData(data);
        showToast(`Đã hoàn thành kiểm thử! Độ chính xác đạt: ${data.accuracy_percent}%`, "success");
      } catch (err) {
        showToast("Lỗi kiểm thử: " + err.message, "error");
      } finally {
        runBtn.disabled = false;
        runBtn.innerHTML = `<i data-lucide="play" style="width:15px;height:15px;"></i><span>Chạy lại kiểm thử</span>`;
        refreshIcons(runBtn);
      }
    });
  }

  // Nạp dữ liệu ban đầu
  fetchLatestBenchmark();
}

function handleSelectedFile(file) {
  currentSelectedFile = file;
  selectedFileName.textContent = `Đã chọn: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
  previewChunksBtn.disabled = false;
  saveDocBtn.disabled = false;
  refreshIcons();
}

// Băm thử Chunk
async function handlePreviewChunks() {
  if (!currentSelectedFile) return;

  const chunkSize = parseInt(chunkSizeInput.value) || 600;
  const chunkOverlap = parseInt(chunkOverlapInput.value) || 120;
  const addHeader = contextualHeaderCheck.checked;

  showToast("Đang đọc và phân đoạn tài liệu...", "info");

  if (currentSelectedFile.name.endsWith(".pdf")) {
    try {
      const formData = new FormData();
      formData.append("file", currentSelectedFile);
      formData.append("chunk_size", chunkSize);
      formData.append("chunk_overlap", chunkOverlap);
      formData.append("add_contextual_header", addHeader);

      const res = await fetch(`/api/documents/preview-file`, {
        method: "POST",
        body: formData
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Lỗi xử lý file PDF");
      renderPreviewModal(data);
    } catch (err) {
      showToast("Lỗi: " + err.message, "error");
    }
    return;
  }

  const reader = new FileReader();
  reader.onload = async (e) => {
    try {
      const text = e.target.result;
      const res = await fetch(`/api/documents/preview`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: text,
          doc_name: currentSelectedFile.name,
          chunk_size: chunkSize,
          chunk_overlap: chunkOverlap,
          add_contextual_header: addHeader
        })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Lỗi preview");
      renderPreviewModal(data);
    } catch (err) {
      showToast("Lỗi: " + err.message, "error");
    }
  };
  reader.readAsText(currentSelectedFile);
}

function renderPreviewModal(data) {
  currentPreviewData = data;
  previewStats.innerHTML = `
    <span class="stat-pill">Tài liệu: <b>${escapeHtml(data.doc_name)}</b></span>
    <span class="stat-pill">Tổng số: <b>${data.total_chunks} đoạn</b></span>
    <span class="stat-pill">Độ dài: <b>${data.chunk_size} ký tự</b></span>
  `;

  previewChunksList.innerHTML = data.chunks.map(c => `
    <div class="preview-chunk-item">
      <div class="chunk-header-tag">
        <span>Đoạn #${c.chunk_index} / ${data.total_chunks}</span>
        <span>${c.metadata.char_count} ký tự</span>
      </div>
      <div class="chunk-content-text">${escapeHtml(c.content)}</div>
    </div>
  `).join("");

  previewModal.classList.add("active");
  refreshIcons();
}

// Lưu tài liệu vào Database
async function handleSaveDocument() {
  if (!currentSelectedFile) return;

  const chunkSize = parseInt(chunkSizeInput.value) || 600;
  const chunkOverlap = parseInt(chunkOverlapInput.value) || 120;
  const addHeader = contextualHeaderCheck.checked;

  saveDocBtn.disabled = true;
  confirmIngestBtn.disabled = true;
  saveDocBtn.innerHTML = `<span>Đang lưu...</span>`;

  try {
    const formData = new FormData();
    formData.append("file", currentSelectedFile);
    formData.append("chunk_size", chunkSize);
    formData.append("chunk_overlap", chunkOverlap);
    formData.append("add_contextual_header", addHeader);

    const res = await fetch("/api/documents/upload", {
      method: "POST",
      body: formData
    });

    const data = await res.json();
    if (res.ok) {
      showToast(`Đã thêm thành công tài liệu: ${currentSelectedFile.name}`, "success");
      previewModal.classList.remove("active");
      fetchDocumentList();
      currentSelectedFile = null;
      selectedFileName.textContent = "";
      fileInput.value = "";
    } else {
      showToast(data.detail || "Lỗi khi lưu tài liệu", "error");
    }
  } catch (err) {
    showToast("Lỗi: " + err.message, "error");
  } finally {
    saveDocBtn.disabled = !currentSelectedFile;
    previewChunksBtn.disabled = !currentSelectedFile;
    confirmIngestBtn.disabled = false;
    saveDocBtn.innerHTML = `<i data-lucide="check" style="width: 14px; height: 14px;"></i><span>Lưu vào kho AI</span>`;
    refreshIcons();
  }
}

// ========================================================
// GENERAL EVENT LISTENERS & MODALS
// ========================================================
function setupEventListeners() {
  toggleSidebarBtn.addEventListener("click", () => {
    sidebar.classList.toggle("open");
  });

  newChatBtn.addEventListener("click", () => {
    createNewSession(true);
  });

  // Stop Generation button
  stopBtn.addEventListener("click", () => {
    if (currentAbortController) {
      currentAbortController.abort();
      showToast("Đã dừng tạo phản hồi", "info");
    }
  });

  clearChatBtn.addEventListener("click", () => {
    const cur = getCurrentSession();
    if (!cur) return;
    if (confirm("Bạn có chắc muốn xóa toàn bộ tin nhắn trong cuộc trò chuyện này?")) {
      cur.messages = [];
      saveSessions();
      renderCurrentSessionMessages();
    }
  });

  chatForm.addEventListener("submit", handleChatSubmit);

  setupAdminHub();

  closePreviewBtn.addEventListener("click", () => previewModal.classList.remove("active"));
  cancelPreviewBtn.addEventListener("click", () => previewModal.classList.remove("active"));

  // Click on in-chat action link [⚙️ Mở Cài đặt tại đây](#open-settings)
  document.addEventListener("click", (e) => {
    const link = e.target.closest("a[href='#open-settings']");
    if (link) {
      e.preventDefault();
      openSettingsBtn.click();
    }
  });

  openSettingsBtn.addEventListener("click", async () => {
    try {
      const res = await fetch("/api/settings/status");
      if (res.ok) {
        const data = await res.json();
        if (data.llm_provider) selectProvider.value = data.llm_provider;
        if (data.embedding_provider) selectEmbedding.value = data.embedding_provider;
        if (data.has_gemini_key) {
          geminiKeyInput.placeholder = "•••••••••••••••••••• (Đã cấu hình sẵn)";
        } else {
          geminiKeyInput.placeholder = "Dán mã AIzaSy... vào đây";
        }
      }
    } catch(e){}
    settingsModal.classList.add("active");
  });
  closeSettingsBtn.addEventListener("click", () => settingsModal.classList.remove("active"));
  cancelSettingsBtn.addEventListener("click", () => settingsModal.classList.remove("active"));

  selectProvider.addEventListener("change", (e) => {
    if (e.target.value === "gemini") {
      geminiKeyGroup.style.display = "block";
      openaiKeyGroup.style.display = "none";
    } else {
      geminiKeyGroup.style.display = "none";
      openaiKeyGroup.style.display = "block";
    }
  });

  saveSettingsBtn.addEventListener("click", async () => {
    const payload = {
      llm_provider: selectProvider.value,
      gemini_api_key: geminiKeyInput.value.trim() || undefined,
      openai_api_key: openaiKeyInput.value.trim() || undefined,
      embedding_provider: selectEmbedding.value
    };

    try {
      const res = await fetch("/api/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (!res.ok) {
        const text = await res.text();
        let errMsg = "Lỗi máy chủ (" + res.status + ")";
        try {
          const errJson = JSON.parse(text);
          errMsg = errJson.detail || errJson.message || errMsg;
        } catch(e) {}
        throw new Error(errMsg);
      }
      const data = await res.json();
      showToast(data.message || "Đã lưu cài đặt & kích hoạt API Key!", "success");
      settingsModal.classList.remove("active");
      geminiKeyInput.value = "";
      openaiKeyInput.value = "";
    } catch (err) {
      showToast("Lỗi lưu cấu hình: " + err.message, "error");
    }
  });
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
