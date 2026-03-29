const form = document.getElementById("composer-form");
const apiKeyInput = document.getElementById("api-key");
const promptInput = document.getElementById("prompt");
const recordButton = document.getElementById("record");
const stopButton = document.getElementById("stop");
const hummedNotesNode = document.getElementById("hummed-notes");
const statusNode = document.getElementById("status");
const codeNode = document.getElementById("code");
const errorNode = document.getElementById("error");

function resetOutput() {
  statusNode.textContent = "Generating...";
  codeNode.textContent = "";
  errorNode.textContent = "";
}

function setRecordingState(isRecording) {
  recordButton.disabled = isRecording;
  stopButton.disabled = !isRecording;
}

async function startRecording() {
  errorNode.textContent = "";

  const response = await fetch("/api/humming/start", {
    method: "POST",
  });
  const payload = await response.json().catch(() => ({ error: "Request failed." }));
  if (!response.ok) {
    statusNode.textContent = "Failed";
    errorNode.textContent = payload.error || "Request failed.";
    return;
  }

  hummedNotesNode.textContent = "";
  statusNode.textContent = payload.status;
  setRecordingState(true);
}

async function stopRecording() {
  errorNode.textContent = "";
  statusNode.textContent = "Transcribing...";

  const response = await fetch("/api/humming/stop", {
    method: "POST",
  });
  const payload = await response.json().catch(() => ({ error: "Request failed." }));
  if (!response.ok) {
    statusNode.textContent = "Failed";
    errorNode.textContent = payload.error || "Request failed.";
    setRecordingState(false);
    return;
  }

  hummedNotesNode.textContent = payload.hummed_notes || "";
  statusNode.textContent = payload.status;
  setRecordingState(false);
}

async function submitPrompt(event) {
  event.preventDefault();

  const apiKey = apiKeyInput.value.trim();
  const prompt = promptInput.value.trim();
  const hummedNotes = hummedNotesNode.textContent.trim();
  if (!apiKey || !prompt) {
    return;
  }

  resetOutput();

  const response = await fetch("/api/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ api_key: apiKey, prompt, hummed_notes: hummedNotes }),
  });

  const payload = await response.json().catch(() => ({ error: "Request failed." }));
  if (!response.ok) {
    statusNode.textContent = "Failed";
    errorNode.textContent = payload.error || "Request failed.";
    if (payload.python_code) {
      codeNode.textContent = payload.python_code;
    }
    return;
  }

  statusNode.textContent = "Code ready";
  codeNode.textContent = payload.python_code;
}

recordButton.addEventListener("click", startRecording);
stopButton.addEventListener("click", stopRecording);
form.addEventListener("submit", submitPrompt);
