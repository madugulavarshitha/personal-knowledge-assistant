const systemStatus = document.getElementById("systemStatus");
const noteInput = document.getElementById("noteInput");
const addNoteBtn = document.getElementById("addNoteBtn");
const clearNoteBtn = document.getElementById("clearNoteBtn");
const searchInput = document.getElementById("searchInput");
const searchBtn = document.getElementById("searchBtn");
const summaryText = document.getElementById("summaryText");
const tagsList = document.getElementById("tagsList");
const insightsList = document.getElementById("insightsList");
const answerText = document.getElementById("answerText");

const uploadMap = {
    pdf: {
        input: document.getElementById("pdfInput"),
        endpoint: "/api/upload_pdf"
    },
    audio: {
        input: document.getElementById("audioInput"),
        endpoint: "/api/upload_audio"
    },
    video: {
        input: document.getElementById("videoInput"),
        endpoint: "/api/upload_video"
    }
};

function setStatus(message) {
    systemStatus.textContent = message;
}

function clearResults(message = "Results will appear here.") {
    summaryText.textContent = "No summary yet";
    tagsList.innerHTML = '<span class="chip muted-chip">Waiting</span>';
    insightsList.innerHTML = '<li>No insights available yet.</li>';
    answerText.textContent = message;
}

function normalizePayload(payload) {
    return payload.data || payload || {};
}

function renderAnalysis(payload) {
    const data = normalizePayload(payload);
    summaryText.textContent = data.summary || "Summary not available";
    tagsList.innerHTML = "";
    insightsList.innerHTML = "";

    const tags = Array.isArray(data.tags) ? data.tags : [];
    const insights = Array.isArray(data.insights) ? data.insights : [];
    const related = Array.isArray(data.related_notes) ? data.related_notes : [];

    if (tags.length === 0) {
        tagsList.innerHTML = '<span class="chip">No tags</span>';
    } else {
        tags.forEach((tag) => {
            const chip = document.createElement("span");
            chip.className = "chip";
            chip.textContent = tag;
            tagsList.appendChild(chip);
        });
    }

    if (insights.length === 0 && related.length === 0) {
        const item = document.createElement("li");
        item.textContent = "No insights available yet.";
        insightsList.appendChild(item);
    }

    insights.forEach((insight) => {
        const item = document.createElement("li");
        item.textContent = insight;
        insightsList.appendChild(item);
    });

    related.forEach((note) => {
        const item = document.createElement("li");
        item.textContent = `Related: ${note}`;
        insightsList.appendChild(item);
    });

    answerText.textContent = data.answer || data.summary || "Analysis completed.";
}

async function postJson(endpoint, body) {
    const response = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
    });

    if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.error || "Request failed");
    }

    return response.json();
}

async function postFile(endpoint, file) {
    const form = new FormData();
    form.append("file", file);

    const response = await fetch(endpoint, {
        method: "POST",
        body: form
    });

    if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.error || "Upload failed");
    }

    return response.json();
}

async function addNote() {
    const note = noteInput.value.trim();

    if (!note) {
        setStatus("Add a note");
        noteInput.focus();
        return;
    }

    addNoteBtn.disabled = true;
    setStatus("Analyzing");
    clearResults("Analyzing your new note...");

    try {
        const data = await postJson("/api/add_note", { note });
        renderAnalysis(data);
        setStatus("Saved");
    } catch (error) {
        answerText.textContent = error.message;
        setStatus("Error");
    } finally {
        addNoteBtn.disabled = false;
    }
}

async function uploadSource(type, button) {
    const config = uploadMap[type];
    const file = config.input.files[0];

    if (!file) {
        setStatus("Choose a file");
        return;
    }

    button.disabled = true;
    setStatus("Uploading");
    clearResults(`Processing ${type} upload...`);

    try {
        const data = await postFile(config.endpoint, file);
        renderAnalysis(data);
        setStatus("Processed");
    } catch (error) {
        answerText.textContent = error.message;
        setStatus("Error");
    } finally {
        button.disabled = false;
    }
}

async function searchKnowledge() {
    const query = searchInput.value.trim();

    if (!query) {
        setStatus("Ask a question");
        searchInput.focus();
        return;
    }

    searchBtn.disabled = true;
    setStatus("Searching");
    clearResults("Searching your knowledge base...");

    try {
        const data = await postJson("/api/search", { query });
        summaryText.textContent = "Search Result";
        tagsList.innerHTML = '<span class="chip">Search</span>';
        insightsList.innerHTML = '<li>Previous result cleared. Showing the latest answer only.</li>';
        answerText.textContent = data.answer || "No answer returned.";
        setStatus("Ready");
    } catch (error) {
        answerText.textContent = error.message;
        setStatus("Error");
    } finally {
        searchBtn.disabled = false;
    }
}

addNoteBtn.addEventListener("click", addNote);
clearNoteBtn.addEventListener("click", () => {
    noteInput.value = "";
    noteInput.focus();
});
searchBtn.addEventListener("click", searchKnowledge);
searchInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
        searchKnowledge();
    }
});

document.querySelectorAll("[data-upload]").forEach((button) => {
    button.addEventListener("click", () => uploadSource(button.dataset.upload, button));
});

clearResults();
