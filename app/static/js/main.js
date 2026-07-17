// CHIMERA — Persona Creation Engine

(function () {
  "use strict";

  /* ── Interview Chat ── */
  const chatMessages = document.getElementById("chat-messages");
  const chatInputArea = document.getElementById("chat-input-area");
  const chatStart = document.getElementById("chat-start");
  const chatQuestion = document.getElementById("chat-question");
  const chatForm = document.getElementById("chat-form");
  const chatInput = document.getElementById("chat-input");
  const chatSend = document.getElementById("chat-send");
  const reasoningEl = document.getElementById("chat-reasoning");
  const reasoningText = document.getElementById("reasoning-text");
  const startBtn = document.getElementById("start-btn");

  const sdName = document.getElementById("sd-name");
  const sdValues = document.getElementById("sd-values");
  const sdMotivations = document.getElementById("sd-motivations");
  const sdStrengths = document.getElementById("sd-strengths");
  const sdWeaknesses = document.getElementById("sd-weaknesses");
  const sdCompleteness = document.getElementById("sd-completeness");
  const sdFill = document.getElementById("sd-fill");
  const previewBtn = document.getElementById("preview-btn");

  let currentSessionId = null;
  let currentQuestion = null;
  let currentReasoning = null;
  let interviewComplete = false;

  function addMessage(avatar, text, cls = "msg-system") {
    const div = document.createElement("div");
    div.className = `msg ${cls}`;
    div.innerHTML = `<div class="msg-avatar">${avatar}</div><div class="msg-content"><p>${text}</p></div>`;
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function updateSidebar(data) {
    const val = (v) => (v && v.length ? v : "—");
    const list = (arr) => (arr && arr.length ? arr.join(", ") : "—");
    sdName.textContent = data.name || "—";
    sdValues.textContent = list(data.core_values);
    sdMotivations.textContent = list(data.motivations);
    sdStrengths.textContent = list(data.strengths);
    sdWeaknesses.textContent = list(data.weaknesses);
    const pct = Math.round((data.completeness || 0) * 100);
    sdCompleteness.textContent = pct + "%";
    sdFill.style.width = pct + "%";
  }

  function setQuestion(q, reasoning) {
    currentQuestion = q;
    currentReasoning = reasoning;
    if (q) {
      chatQuestion.textContent = q;
      chatInputArea.style.display = "block";
      chatInput.value = "";
      chatInput.focus();
      if (reasoning) {
        reasoningText.textContent = reasoning;
        reasoningEl.style.display = "block";
      } else {
        reasoningEl.style.display = "none";
      }
    } else {
      chatInputArea.style.display = "none";
      reasoningEl.style.display = "none";
    }
  }

  function completeInterview() {
    interviewComplete = true;
    chatInputArea.style.display = "none";
    reasoningEl.style.display = "none";
    addMessage("C", "I think I understand now. Let me show you what I've learned.", "msg-system");
    if (previewBtn) {
      previewBtn.style.display = "inline-block";
      previewBtn.href = `/preview/${currentSessionId}`;
    }
  }

  if (startBtn) {
    startBtn.addEventListener("click", async function () {
      startBtn.disabled = true;
      startBtn.textContent = "Starting...";
      try {
        const resp = await fetch("/api/interview", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
        const data = await resp.json();
        currentSessionId = data.session_id;
        addMessage("C", data.question, "msg-system");
        if (data.reasoning) {
          reasoningText.textContent = data.reasoning;
          reasoningEl.style.display = "block";
        }
        setQuestion(data.question, data.reasoning);
        chatStart.style.display = "none";
        updateSidebar({});
        history.replaceState(null, "", `/interview/${currentSessionId}`);
      } catch (e) {
        addMessage("C", "Something went wrong. Please try again.");
        startBtn.disabled = false;
        startBtn.textContent = "Start Interview";
      }
    });
  }

  if (chatForm) {
    chatForm.addEventListener("submit", async function (e) {
      e.preventDefault();
      if (!currentQuestion || interviewComplete) return;
      const answer = chatInput.value.trim();
      if (!answer) return;
      addMessage("You", answer, "msg-user");
      chatInput.value = "";
      chatSend.disabled = true;
      chatSend.textContent = "...";

      try {
        const resp = await fetch(`/api/interview/${currentSessionId}/answer`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ answer }),
        });
        const data = await resp.json();
        addMessage("C", data.next_question || "I think I understand now.", "msg-system");
        if (data.complete) {
          completeInterview();
          updateSidebar({ completeness: 1, ...data });
        } else {
          setQuestion(data.next_question, data.next_reasoning);
          updateSidebar({ completeness: data.completeness, ...data });
        }
      } catch (e) {
        addMessage("C", "Something went wrong. Let's try that again.");
        setQuestion(currentQuestion, currentReasoning);
      }
      chatSend.disabled = false;
      chatSend.textContent = "Send";
    });
  }

  /* ── Persona Preview ── */
  const previewBody = document.getElementById("preview-body");
  const previewLoading = document.getElementById("preview-loading");

  async function loadPreview(sid) {
    if (!previewBody || !sid) return;
    try {
      const resp = await fetch(`/api/interview/${sid}/preview`);
      if (!resp.ok) throw new Error("Not found");
      const data = await resp.json();
      const setText = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.textContent = val || "—";
      };
      setText("pv-name", data.name);
      setText("pv-summary", data.summary);
      setText("pv-style", data.communication_style);
      setText("pv-values", data.core_values?.join(", "));
      setText("pv-motivations", data.motivations?.join(", "));
      setText("pv-strengths", data.strengths?.join(", "));
      setText("pv-weaknesses", data.weaknesses?.join(", "));
      setText("pv-goals", data.goals?.join(", "));
      setText("pv-boundaries", data.boundaries?.join(", "));
      setText("pv-unknowns", data.unknowns?.join(", "));
      const pct = data.completeness || 0;
      setText("pv-pct", pct + "%");
      const fill = document.getElementById("pv-fill");
      if (fill) fill.style.width = pct + "%";

      const forgeBtn = document.getElementById("pv-forge");
      const continueBtn = document.getElementById("pv-continue");
      if (forgeBtn) {
        forgeBtn.disabled = data.unknowns?.length > 0;
        if (!forgeBtn.disabled) {
          forgeBtn.addEventListener("click", async function () {
            forgeBtn.disabled = true;
            forgeBtn.textContent = "Forging...";
            try {
              const resp = await fetch(`/api/interview/${sid}/cartridge`, { method: "POST" });
              const result = await resp.json();
              if (resp.ok) {
                forgeBtn.textContent = "Forged!";
                forgeBtn.style.background = "#22c55e";
                forgeBtn.style.borderColor = "#22c55e";
                forgeBtn.style.color = "#0a0f1e";
              }
            } catch (e) {
              forgeBtn.disabled = false;
              forgeBtn.textContent = "Forge Persona Cartridge";
            }
          });
        }
      }
      if (continueBtn) continueBtn.href = `/interview/${sid}`;
      if (previewLoading) previewLoading.style.display = "none";
    } catch (e) {
      if (previewLoading) previewLoading.innerHTML = "<p>Could not load persona. <a href='/interview'>Start a new interview.</a></p>";
    }
  }

  const sid = typeof sessionId !== "undefined" ? sessionId : null;
  if (sid) loadPreview(sid);
})();
