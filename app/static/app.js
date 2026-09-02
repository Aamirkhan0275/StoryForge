const form = document.querySelector("#project-form");
const topicInput = document.querySelector("#topic");
const message = document.querySelector("#form-message");
const projectsContainer = document.querySelector("#projects");
const refreshButton = document.querySelector("#refresh-button");

function showMessage(text, isError = false) {
  message.textContent = text;
  message.classList.toggle("error", isError);
}

function formatDate(value) {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

async function loadProjects() {
  projectsContainer.innerHTML = '<p class="empty">Loading projects…</p>';
  try {
    const response = await fetch("/api/projects");
    if (!response.ok) throw new Error("Could not load projects");
    const projects = await response.json();
    if (projects.length === 0) {
      projectsContainer.innerHTML = '<p class="empty">No projects yet. Start with an idea above.</p>';
      return;
    }
    projectsContainer.innerHTML = projects.map((project) => `
      <article class="project">
        <h3><a href="/static/project.html?id=${encodeURIComponent(project.id)}">${escapeHtml(project.topic)}</a></h3>
        <p>${project.status} · ${formatDate(project.created_at)}</p>
      </article>`).join("");
  } catch (error) {
    projectsContainer.innerHTML = '<p class="empty">Projects could not be loaded. Check that the server is running.</p>';
  }
}

function escapeHtml(value) {
  const element = document.createElement("div");
  element.textContent = value;
  return element.innerHTML;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  showMessage("Saving project…");
  try {
    const response = await fetch("/api/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ topic: topicInput.value }),
    });
    if (!response.ok) throw new Error("Could not save project");
    topicInput.value = "";
    showMessage("Project saved. Research will be the next stage.");
    await loadProjects();
  } catch (error) {
    showMessage("Project could not be saved. Please try again.", true);
  }
});

refreshButton.addEventListener("click", loadProjects);
loadProjects();
