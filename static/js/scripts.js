document.addEventListener("DOMContentLoaded", () => {
    // --- DOM Element Cache ---
    const ui = {
        themeSwitch: document.getElementById("themeSwitch"),
        searchForm: document.querySelector(".search-form"),
        searchQuery: document.getElementById("searchQuery"),
        searchButton: document.getElementById("searchButton"),
        searchSuggestions: document.querySelectorAll(".search-suggestion"),
        numResults: document.getElementById("numResults"),
        numResultsValue: document.getElementById("numResultsValue"),
        emptyState: document.getElementById("emptyState"),
        searchProgress: document.getElementById("searchProgress"),
        resultsArea: document.getElementById("resultsArea"),
        resultsContainer: document.getElementById("resultsContainer"),
        resultCount: document.getElementById("resultCount"),
        noResults: document.getElementById("noResults"),
        videoModal: document.getElementById("videoModal"),
        videoModalLabel: document.getElementById("videoModalLabel"),
        videoIframe: document.getElementById("videoIframe"),
        videoInfo: document.getElementById("videoInfo"),
        embeddingText: document.getElementById("embeddingText"),
        metadataJson: document.getElementById("metadataJson"),
        watchOnYouTube: document.getElementById("watchOnYouTube"),
        copyEmbedding: document.getElementById("copyEmbedding"),
        copyMetadata: document.getElementById("copyMetadata"),
    };

    // --- Initialization ---
    initTheme();
    initTooltips();
    initSearch();
    initModal();

    // --- Theme Switcher ---
    function initTheme() {
        const savedTheme = localStorage.getItem("theme") || "light";
        document.documentElement.setAttribute("data-bs-theme", savedTheme);
        if (ui.themeSwitch) {
            ui.themeSwitch.checked = savedTheme === "dark";
            ui.themeSwitch.addEventListener("change", (e) => {
                const theme = e.target.checked ? "dark" : "light";
                document.documentElement.setAttribute("data-bs-theme", theme);
                localStorage.setItem("theme", theme);
            });
        }
    }

    // --- Bootstrap Tooltips ---
    function initTooltips() {
        if (typeof bootstrap !== "undefined" && bootstrap.Tooltip) {
            const tooltipTriggerList = [].slice.call(
                document.querySelectorAll('[data-bs-toggle="tooltip"]')
            );
            tooltipTriggerList.map(
                (tooltipTriggerEl) => new bootstrap.Tooltip(tooltipTriggerEl)
            );
        }
    }

    // --- Search Functionality ---
    function initSearch() {
        ui.searchButton?.addEventListener("click", performSearch);
        ui.searchQuery?.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                e.preventDefault();
                performSearch();
            }
        });

        ui.numResults?.addEventListener("input", function () {
            ui.numResultsValue.textContent = this.value;
        });

        ui.searchSuggestions.forEach((suggestion) => {
            suggestion.addEventListener("click", (e) => {
                e.preventDefault();
                ui.searchQuery.value = suggestion.textContent.trim();
                ui.searchQuery.focus();
            });
        });
    }

    async function performSearch() {
        const query = ui.searchQuery.value.trim();
        if (!query) {
            ui.searchQuery.focus();
            return;
        }

        setLoadingState(true);

        try {
            const response = await fetch("/search", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    query: query,
                    num_results: parseInt(ui.numResults.value),
                }),
            });

            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }

            const data = await response.json();
            displayResults(data.results);
        } catch (error) {
            console.error("Search error:", error);
            showErrorState(error.message);
        } finally {
            setLoadingState(false);
        }
    }

    function setLoadingState(isLoading) {
        if (isLoading) {
            ui.searchButton.disabled = true;
            ui.searchButton.innerHTML = `<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Searching...`;
            ui.emptyState.classList.add("d-none");
            ui.resultsArea.classList.add("d-none");
            ui.noResults.classList.add("d-none");
            ui.searchProgress.classList.remove("d-none");
        } else {
            ui.searchButton.disabled = false;
            ui.searchButton.innerHTML = `<i class="bi bi-search"></i> Search`;
            ui.searchProgress.classList.add("d-none");
        }
    }

    function showErrorState(message) {
        ui.resultsArea.classList.add("d-none");
        ui.noResults.innerHTML = `
            <i class="bi bi-exclamation-triangle-fill"></i>
            <div>
                <strong>Search Error</strong>
                <p class="mb-0">${message}</p>
            </div>`;
        ui.noResults.classList.remove("d-none");
    }

    // --- Results Display ---
    function displayResults(results) {
        if (!results || results.length === 0) {
            ui.resultsArea.classList.add("d-none");
            ui.noResults.classList.remove("d-none");
            return;
        }

        ui.resultsContainer.innerHTML = "";
        ui.resultCount.textContent = results.length;

        results.forEach((video, index) => {
            const card = createVideoCard(video);
            ui.resultsContainer.appendChild(card);
            setTimeout(() => card.classList.add("visible"), 50 * index);
        });

        ui.resultsArea.classList.remove("d-none");
        initTooltips(); // Re-initialize for new elements
        
        document.querySelectorAll(".view-details").forEach((button) => {
            button.addEventListener("click", () => openVideoModal(button.dataset));
        });
    }

    function createVideoCard(video) {
        const scoreClass = getScoreClass(video.score);
        const card = document.createElement("div");
        card.className = "col video-card-wrapper";
        card.innerHTML = `
            <div class="card video-card h-100">
                <div class="position-relative">
                    <img src="${video.thumbnail || 'https://via.placeholder.com/480x360?text=No+Thumbnail'}" 
                         class="card-img-top" alt="${video.title}" loading="lazy">
                    <span class="score-badge ${scoreClass}">${video.score.toFixed(3)}</span>
                </div>
                <div class="card-body">
                    <h5 class="card-title">${video.title}</h5>
                    <p class="channel-name"><i class="bi bi-person-circle"></i> ${video.channel}</p>
                </div>
                <div class="card-footer d-flex justify-content-between align-items-center">
                    <button class="btn btn-sm btn-outline-primary view-details" 
                            data-video-id="${video.id}"
                            data-video-url="${video.url}"
                            data-video-title="${video.title}"
                            data-video-channel="${video.channel}"
                            data-video-document="${encodeURIComponent(video.document)}"
                            data-video-metadata="${encodeURIComponent(JSON.stringify(video.metadata))}"
                            data-bs-toggle="tooltip" title="View video details">
                        <i class="bi bi-info-circle"></i> Details
                    </button>
                    <a href="${video.url}" target="_blank" class="btn btn-sm btn-danger"
                       data-bs-toggle="tooltip" title="Open in YouTube">
                        <i class="bi bi-youtube"></i> Watch
                    </a>
                </div>
            </div>
        `;
        return card;
    }

    function getScoreClass(score) {
        if (score >= 0.8) return "bg-success";
        if (score >= 0.6) return "bg-primary";
        if (score >= 0.4) return "bg-info";
        if (score >= 0.2) return "bg-warning";
        return "bg-secondary";
    }

    // --- Modal Functionality ---
    function initModal() {
        ui.videoModal?.addEventListener("hidden.bs.modal", () => {
            ui.videoIframe.src = "about:blank";
        });

        ui.copyEmbedding?.addEventListener("click", () => {
            copyToClipboard(ui.embeddingText.textContent, ui.copyEmbedding);
        });

        ui.copyMetadata?.addEventListener("click", () => {
            copyToClipboard(ui.metadataJson.textContent, ui.copyMetadata);
        });
    }

    function openVideoModal(dataset) {
        const { videoId, videoUrl, videoTitle, videoChannel, videoDocument, videoMetadata } = dataset;
        const metadata = JSON.parse(decodeURIComponent(videoMetadata));

        ui.videoModalLabel.textContent = videoTitle;
        ui.videoIframe.src = `https://www.youtube.com/embed/${videoId}`;
        ui.watchOnYouTube.href = videoUrl;

        ui.videoInfo.innerHTML = `
            <table class="table table-hover">
                <tbody>
                    <tr><th class="w-25">Title</th><td>${videoTitle}</td></tr>
                    <tr><th>Channel</th><td>${videoChannel}</td></tr>
                    <tr><th>YouTube ID</th><td><code>${videoId}</code></td></tr>
                </tbody>
            </table>`;
        
        ui.embeddingText.textContent = decodeURIComponent(videoDocument);
        ui.metadataJson.textContent = JSON.stringify(metadata, null, 2);

        const modal = new bootstrap.Modal(ui.videoModal);
        modal.show();
    }

    function copyToClipboard(text, button) {
        navigator.clipboard.writeText(text).then(() => {
            const originalText = button.innerHTML;
            button.innerHTML = '<i class="bi bi-check-lg"></i> Copied!';
            setTimeout(() => {
                button.innerHTML = originalText;
            }, 2000);
        }, (err) => {
            console.error('Could not copy text: ', err);
            const originalText = button.innerHTML;
            button.innerHTML = 'Error!';
            setTimeout(() => {
                button.innerHTML = originalText;
            }, 2000);
        });
    }
});