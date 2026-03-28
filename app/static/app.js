const form = document.getElementById("composer-form");
const apiKeyInput = document.getElementById("api-key");
const promptInput = document.getElementById("prompt");
const statusNode = document.getElementById("status");
const codeNode = document.getElementById("code");
const errorNode = document.getElementById("error");
const downloadLink = document.getElementById("download");

let downloadUrl = null;

function resetOutput() {
  statusNode.textContent = "Generating...";
  codeNode.textContent = "";
  errorNode.textContent = "";
  downloadLink.classList.add("hidden");
  downloadLink.removeAttribute("href");
  if (downloadUrl) {
    URL.revokeObjectURL(downloadUrl);
    downloadUrl = null;
  }
}

async function submitPrompt(event) {
  event.preventDefault();

  const apiKey = apiKeyInput.value.trim();
  const prompt = promptInput.value.trim();
  if (!apiKey || !prompt) {
    return;
  }

  resetOutput();

  const response = await fetch("/api/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ api_key: apiKey, prompt }),
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

  statusNode.textContent = "Ready";
  codeNode.textContent = payload.python_code;

  downloadUrl = URL.createObjectURL(
    new Blob([payload.musicxml], { type: "application/vnd.recordare.musicxml+xml" }),
  );
  downloadLink.href = downloadUrl;
  downloadLink.download = payload.filename;
  downloadLink.classList.remove("hidden");
  downloadLink.click();
}

form.addEventListener("submit", submitPrompt);
