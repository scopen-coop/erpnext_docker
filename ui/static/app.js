const clientsGrid = document.querySelector("#clientsGrid");
const clientCount = document.querySelector("#clientCount");
const modulesList = document.querySelector("#modulesList");
const moduleCount = document.querySelector("#moduleCount");
const createForm = document.querySelector("#createForm");
const refreshButton = document.querySelector("#refreshButton");
const clientTemplate = document.querySelector("#clientCardTemplate");
const moduleTemplate = document.querySelector("#moduleTemplate");
const jobStatus = document.querySelector("#jobStatus");
const jobCommand = document.querySelector("#jobCommand");
const jobOutput = document.querySelector("#jobOutput");
const statClients = document.querySelector("#statClients");
const statRunning = document.querySelector("#statRunning");
const statModules = document.querySelector("#statModules");

let activeJobId = null;

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.error || `HTTP ${response.status}`);
  }
  return payload;
}

function badgeTone(status) {
  return `badge-${String(status).replace(/[^a-z0-9-]/gi, "").toLowerCase()}`;
}

function showJob(job) {
  jobStatus.textContent = `Status: ${job.status}`;
  jobCommand.textContent = job.command || "";
  jobOutput.textContent = job.output || "No output.";
}

function showError(command, error) {
  showJob({
    status: "failed",
    command,
    output: error instanceof Error ? error.message : String(error),
  });
}

async function runOperation(payload) {
  const response = await request("/api/jobs", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  followJob(response.job.id);
}

async function loadDashboard() {
  const payload = await request("/api/dashboard");
  renderStats(payload.stats);
  renderModules(payload.modules);
  renderClients(payload.clients);
}

function renderStats(stats) {
  statClients.textContent = stats.clients;
  statRunning.textContent = stats.running_clients;
  statModules.textContent = stats.modules;
}

function renderModules(modules) {
  moduleCount.textContent = `${modules.length} module${modules.length > 1 ? "s" : ""}`;
  modulesList.replaceChildren();

  if (!modules.length) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "No module yet.";
    modulesList.append(empty);
    return;
  }

  for (const module of modules) {
    const fragment = moduleTemplate.content.cloneNode(true);
    fragment.querySelector(".module-name").textContent = module.name;
    fragment.querySelector(".module-meta").textContent = module.repo || module.path;
    fragment.querySelector(".module-branch").textContent = module.branch || "unknown";
    modulesList.append(fragment);
  }
}

function attachButtonActions(scope, client) {
  for (const button of scope.querySelectorAll("button[data-operation]")) {
    button.addEventListener("click", async () => {
      const operation = button.dataset.operation;
      const action = button.dataset.action;
      if (operation === "delete_client") {
        const confirmed = window.confirm(`Delete client "${client.name}"?`);
        if (!confirmed) {
          return;
        }
      }

      button.disabled = true;
      try {
        await runOperation({
          operation,
          client: client.name,
          action,
        });
      } catch (error) {
        showError(`${operation} ${client.name}`, error);
      } finally {
        button.disabled = false;
      }
    });
  }

  for (const button of scope.querySelectorAll("button[data-log]")) {
    button.addEventListener("click", async () => {
      button.disabled = true;
      try {
        const payload = await request(`/api/clients/${client.name}/logs?tail=200`);
        showJob({
          status: payload.logs.status,
          command: `logs ${client.name}`,
          output: payload.logs.output || "No output.",
        });
      } catch (error) {
        showError(`logs ${client.name}`, error);
      } finally {
        button.disabled = false;
      }
    });
  }
}

function attachFormActions(scope, client) {
  for (const form of scope.querySelectorAll("form[data-operation-form]")) {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const operation = form.dataset.operationForm;
      const formData = Object.fromEntries(new FormData(form).entries());
      const payload = { operation, ...formData };
      if (client) {
        payload.client = client.name;
      }

      const submitter = form.querySelector('button[type="submit"]');
      if (submitter) {
        submitter.disabled = true;
      }

      try {
        await runOperation(payload);
      } catch (error) {
        showError(operation, error);
      } finally {
        if (submitter) {
          submitter.disabled = false;
        }
      }
    });
  }
}

function renderClients(clients) {
  clientCount.textContent = `${clients.length} env${clients.length > 1 ? "s" : ""}`;
  clientsGrid.replaceChildren();

  if (!clients.length) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "No client yet.";
    clientsGrid.append(empty);
    return;
  }

  for (const client of clients) {
    const fragment = clientTemplate.content.cloneNode(true);
    const card = fragment.querySelector(".card");

    fragment.querySelector(".client-name").textContent = client.name;
    fragment.querySelector(".client-branch").textContent = client.branch || "unknown branch";
    fragment.querySelector(".client-project").textContent = client.project || "n/a";
    fragment.querySelector(".client-port").textContent = client.port || "n/a";
    fragment.querySelector(".client-site").textContent = client.site_name || "n/a";
    fragment.querySelector(".client-admin").textContent = client.admin_password || "n/a";
    fragment.querySelector(".client-apps").textContent = client.configured_app_names.join(", ");

    const statusNode = fragment.querySelector(".client-status");
    statusNode.textContent = client.status;
    statusNode.classList.add(badgeTone(client.status));

    const services = fragment.querySelector(".client-services");
    if (client.services.length) {
      for (const service of client.services) {
        const chip = document.createElement("span");
        const state = service.health ? `${service.state}/${service.health}` : service.state;
        chip.className = `service-chip ${badgeTone(service.state)}`;
        chip.textContent = `${service.service}: ${state}`;
        services.append(chip);
      }
    } else {
      const chip = document.createElement("span");
      chip.className = "service-chip badge-stopped";
      chip.textContent = "No active service";
      services.append(chip);
    }

    const openLink = fragment.querySelector(".open-link");
    openLink.href = client.url || "#";
    if (!client.url) {
      openLink.setAttribute("aria-disabled", "true");
      openLink.classList.add("disabled");
    }

    attachButtonActions(card, client);
    attachFormActions(card, client);
    clientsGrid.append(card);
  }
}

async function pollJob(jobId) {
  const payload = await request(`/api/jobs/${jobId}`);
  const { job } = payload;
  showJob(job);
  if (job.status === "running" || job.status === "queued") {
    window.setTimeout(() => pollJob(jobId), 1500);
    return;
  }
  activeJobId = null;
  await loadDashboard();
}

function followJob(jobId) {
  activeJobId = jobId;
  pollJob(jobId).catch((error) => {
    activeJobId = null;
    showError("job polling", error);
  });
}

createForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = Object.fromEntries(new FormData(createForm).entries());
  try {
    await runOperation({ operation: "create_client", ...payload });
    createForm.reset();
    const branchField = createForm.querySelector('input[name="branch"]');
    if (branchField) {
      branchField.value = "version-15";
    }
  } catch (error) {
    showError("create_client", error);
  }
});

attachFormActions(document, null);

for (const button of document.querySelectorAll("button[data-operation]")) {
  if (button.closest("#clientCardTemplate")) {
    continue;
  }
  button.addEventListener("click", async () => {
    button.disabled = true;
    try {
      await runOperation({ operation: button.dataset.operation });
    } catch (error) {
      showError(button.dataset.operation, error);
    } finally {
      button.disabled = false;
    }
  });
}

refreshButton.addEventListener("click", () => {
  if (!activeJobId) {
    loadDashboard().catch((error) => showError("refresh", error));
  }
});

loadDashboard().catch((error) => showError("initial load", error));
