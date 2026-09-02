const projectId = new URLSearchParams(window.location.search).get("id");
const projectTopic = document.querySelector("#project-topic");
const sourceForm = document.querySelector("#source-form");
const sourcesContainer = document.querySelector("#sources");
const message = document.querySelector("#form-message");
const researchMessage = document.querySelector("#research-message");
const researchButton = document.querySelector("#generate-research");
const researchBrief = document.querySelector("#research-brief");

function showMessage(text, isError = false) {
  message.textContent = text;
  message.classList.toggle("error", isError);
}

function escapeHtml(value) {
  const element = document.createElement("div");
  element.textContent = value;
  return element.innerHTML;
}

async function loadProject() {
  if (!projectId) throw new Error("Missing project ID");
  const response = await fetch(`/api/projects/${projectId}`);
  if (!response.ok) throw new Error("Project not found");
  const project = await response.json();
  projectTopic.textContent = project.topic;
}

async function loadSources() {
  const response = await fetch(`/api/projects/${projectId}/sources`);
  if (!response.ok) throw new Error("Sources could not be loaded");
  const sources = await response.json();
  if (sources.length === 0) {
    sourcesContainer.innerHTML = '<p class="empty">No sources yet. Add official reports, reputable reporting, or original material.</p>';
    return;
  }
  sourcesContainer.innerHTML = sources.map((source) => `
    <article class="project source-card">
      <a href="${escapeHtml(source.url)}" target="_blank" rel="noreferrer">${escapeHtml(source.title)}</a>
      <p>${escapeHtml(source.notes || "No notes added.")}</p>
      <button class="secondary extract-button" data-source-id="${source.id}" type="button">Extract source text</button>
      <button class="secondary delete-button" data-delete-source-id="${source.id}" type="button">Remove source</button>
      <p class="extract-status">${source.extracted_at ? "Text extracted and ready for AI research." : "Source text not extracted yet."}</p>
    </article>`).join("");
}

async function loadResearch() {
  const response = await fetch(`/api/projects/${projectId}/research`);
  if (response.status === 404) return;
  if (!response.ok) throw new Error("Research brief could not be loaded");
  const brief = await response.json();
  researchBrief.textContent = brief.content;
  researchBrief.hidden = false;
  document.querySelector("#output-language").value = brief.language;
  researchMessage.textContent = `Saved research brief · ${brief.model}`;
}

sourceForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  showMessage("Saving source…");
  const body = {
    title: document.querySelector("#source-title").value,
    url: document.querySelector("#source-url").value,
    notes: document.querySelector("#source-notes").value,
  };
  try {
    const response = await fetch(`/api/projects/${projectId}/sources`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!response.ok) throw new Error("Source could not be saved");
    sourceForm.reset();
    showMessage("Source saved.");
    await loadSources();
  } catch (error) {
    showMessage("Source could not be saved. Check the link and try again.", true);
  }
});

Promise.all([loadProject(), loadSources(), loadResearch()]).catch(() => {
  projectTopic.textContent = "Project could not be loaded";
  sourcesContainer.innerHTML = '<p class="empty">Return to the project list and try again.</p>';
});

sourcesContainer.addEventListener("click", async (event) => {
  const deleteButton = event.target.closest("[data-delete-source-id]");
  if (deleteButton) {
    if (!window.confirm("Remove this source from the project?")) return;
    deleteButton.disabled = true;
    try {
      const response = await fetch(
        `/api/projects/${projectId}/sources/${deleteButton.dataset.deleteSourceId}`,
        { method: "DELETE" },
      );
      if (!response.ok) throw new Error("Source could not be removed");
      showMessage("Source removed.");
      await loadSources();
    } catch (error) {
      showMessage("Source could not be removed.", true);
      deleteButton.disabled = false;
    }
    return;
  }
  const button = event.target.closest("[data-source-id]");
  if (!button) return;
  button.disabled = true;
  button.textContent = "Extracting…";
  try {
    const response = await fetch(
      `/api/projects/${projectId}/sources/${button.dataset.sourceId}/extract`,
      { method: "POST" },
    );
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "Extraction failed");
    showMessage("Source text extracted and saved.");
    await loadSources();
  } catch (error) {
    showMessage(error.message || "The source could not be extracted.", true);
    button.disabled = false;
    button.textContent = "Extract source text";
  }
});

researchButton.addEventListener("click", async () => {
  researchButton.disabled = true;
  researchButton.textContent = "Generating…";
  researchMessage.classList.remove("error");
  researchMessage.textContent = "Creating a concise, source-bound brief. On a CPU-only PC this can take a few minutes.";
  try {
    const response = await fetch(`/api/projects/${projectId}/research/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ language: document.querySelector("#output-language").value }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "Research generation failed");
    researchBrief.textContent = result.content;
    researchBrief.hidden = false;
    researchMessage.textContent = `Research brief generated with ${result.model}.`;
  } catch (error) {
    researchMessage.textContent = error.message || "Research generation failed.";
    researchMessage.classList.add("error");
  } finally {
    researchButton.disabled = false;
    researchButton.textContent = "Generate evidence-based timeline";
  }
});
