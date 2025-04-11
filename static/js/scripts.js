// scripts.js
document.addEventListener("DOMContentLoaded", function () {
	// Elements
	const searchForm = document.querySelector(".search-form");
	const searchQuery = document.getElementById("searchQuery");
	const searchButton = document.getElementById("searchButton");
	const searchSuggestions = document.querySelectorAll(".search-suggestion");
	const numResults = document.getElementById("numResults");
	const numResultsValue = document.getElementById("numResultsValue");
	const emptyState = document.getElementById("emptyState");
	const searchProgress = document.getElementById("searchProgress");
	const resultsArea = document.getElementById("resultsArea");
	const resultsContainer = document.getElementById("resultsContainer");
	const resultCount = document.getElementById("resultCount");
	const noResults = document.getElementById("noResults");

	// Video modal elements
	const videoModal = document.getElementById("videoModal");
	const videoModalLabel = document.getElementById("videoModalLabel");
	const videoIframe = document.getElementById("videoIframe");
	const videoInfo = document.getElementById("videoInfo");
	const embeddingText = document.getElementById("embeddingText");
	const metadataJson = document.getElementById("metadataJson");
	const watchOnYouTube = document.getElementById("watchOnYouTube");

	// Initialize tooltips
	if (typeof bootstrap !== "undefined" && bootstrap.Tooltip) {
		const tooltipTriggerList = [].slice.call(
			document.querySelectorAll('[data-bs-toggle="tooltip"]')
		);
		tooltipTriggerList.map(function (tooltipTriggerEl) {
			return new bootstrap.Tooltip(tooltipTriggerEl);
		});
	}

	// Update number of results slider value display
	numResults.addEventListener("input", function () {
		numResultsValue.textContent = this.value;
		numResultsValue.style.transform = "scale(1.2)";
		setTimeout(() => {
			numResultsValue.style.transform = "scale(1)";
		}, 200);
	});

	// Search suggestions
	searchSuggestions.forEach((suggestion) => {
		suggestion.addEventListener("click", function (e) {
			e.preventDefault();
			searchQuery.value = this.textContent.trim();
			searchQuery.focus();

			// Animate the input
			searchQuery.classList.add("pulse-animation");
			setTimeout(() => {
				searchQuery.classList.remove("pulse-animation");
			}, 500);
		});
	});

	// Handle form submission
	searchButton.addEventListener("click", performSearch);
	searchQuery.addEventListener("keydown", function (e) {
		if (e.key === "Enter") {
			e.preventDefault();
			performSearch();
		}
	});

	function performSearch() {
		const query = searchQuery.value.trim();
		if (!query) {
			// Shake the input to indicate error
			searchQuery.classList.add("shake-animation");
			setTimeout(() => {
				searchQuery.classList.remove("shake-animation");
			}, 500);
			return;
		}

		// Animate the search button
		searchButton.classList.add("searching");
		searchButton.disabled = true;

		// Show loading state
		emptyState.classList.add("d-none");
		resultsArea.classList.add("d-none");
		noResults.classList.add("d-none");
		searchProgress.classList.remove("d-none");

		// Prepare the request
		const requestData = {
			query: query,
			num_results: parseInt(numResults.value),
		};

		// Make the search request
		fetch("/search", {
			method: "POST",
			headers: {
				"Content-Type": "application/json",
			},
			body: JSON.stringify(requestData),
		})
			.then((response) => {
				if (!response.ok) {
					throw new Error("Search request failed");
				}
				return response.json();
			})
			.then((data) => {
				// Hide loading state
				searchProgress.classList.add("d-none");
				searchButton.classList.remove("searching");
				searchButton.disabled = false;

				if (data.results && data.results.length > 0) {
					displayResults(data.results);
				} else {
					noResults.classList.remove("d-none");
				}
			})
			.catch((error) => {
				console.error("Error during search:", error);
				searchProgress.classList.add("d-none");
				searchButton.classList.remove("searching");
				searchButton.disabled = false;

				// Show error message
				noResults.innerHTML = `
                <i class="bi bi-exclamation-triangle-fill"></i>
                <div>
                    <strong>Search error</strong>
                    <p class="mb-0">${error.message}</p>
                </div>
            `;
				noResults.classList.remove("d-none");
			});
	}

	function displayResults(results) {
		// Clear previous results
		resultsContainer.innerHTML = "";

		// Update result count
		resultCount.textContent = results.length;

		// Create and append result cards with animation delay
		results.forEach((video, index) => {
			const scoreClass = getScoreClass(video.score);
			const card = document.createElement("div");
			card.className = "col";
			card.style.opacity = "0";
			card.style.transform = "translateY(20px)";

			// Calculate video duration ago
			const duration = video.metadata.duration_ago || "Unknown";

			card.innerHTML = `
                <div class="card video-card h-100">
                    <div class="position-relative">
                        <img src="${
							video.thumbnail ||
							"https://via.placeholder.com/480x360?text=No+Thumbnail"
						}" 
                             class="card-img-top" alt="${video.title}"
                             loading="lazy">
                        <span class="score-badge ${scoreClass}">${video.score.toFixed(
				3
			)}</span>
                    </div>
                    <div class="card-body">
                        <h5 class="card-title">${video.title}</h5>
                        <p class="channel-name"><i class="bi bi-person-circle"></i> ${
							video.channel
						}</p>
                        ${
							video.tags
								? `<p class="tags small text-muted"><i class="bi bi-tags"></i> ${video.tags}</p>`
								: ""
						}
                    </div>
                    <div class="card-footer d-flex justify-content-between">
                        <button class="btn btn-sm btn-outline-primary view-details" 
                                data-video-id="${video.id}" 
                                data-video-url="${video.url}"
                                data-video-title="${video.title}"
                                data-video-channel="${video.channel}"
                                data-video-document="${encodeURIComponent(
									video.document
								)}"
                                data-video-metadata="${encodeURIComponent(
									JSON.stringify(video.metadata)
								)}"
                                data-bs-toggle="tooltip" 
                                title="View video details">
                            <i class="bi bi-info-circle"></i> Details
                        </button>
                        <a href="${
							video.url
						}" target="_blank" class="btn btn-sm btn-danger"
                           data-bs-toggle="tooltip" 
                           title="Open in YouTube">
                            <i class="bi bi-youtube"></i> Watch
                        </a>
                    </div>
                </div>
            `;

			resultsContainer.appendChild(card);

			// Animate card entrance with delay
			setTimeout(() => {
				card.style.transition =
					"opacity 0.5s ease, transform 0.5s ease";
				card.style.opacity = "1";
				card.style.transform = "translateY(0)";
			}, 50 * index); // Stagger the animations
		});

		// Reinitialize tooltips after adding new elements
		if (typeof bootstrap !== "undefined" && bootstrap.Tooltip) {
			const tooltips = [].slice.call(
				document.querySelectorAll('[data-bs-toggle="tooltip"]')
			);
			tooltips.map((el) => new bootstrap.Tooltip(el));
		}

		// Add event listeners to detail buttons
		document.querySelectorAll(".view-details").forEach((button) => {
			button.addEventListener("click", function () {
				openVideoModal(this);
			});
		});

		// Show results area with animation
		resultsArea.style.opacity = "0";
		resultsArea.classList.remove("d-none");
		setTimeout(() => {
			resultsArea.style.transition = "opacity 0.5s ease";
			resultsArea.style.opacity = "1";
		}, 10);
	}

	function getScoreClass(score) {
		if (score >= 0.8) return "bg-success";
		if (score >= 0.6) return "bg-primary";
		if (score >= 0.4) return "bg-info";
		if (score >= 0.2) return "bg-warning";
		return "bg-secondary";
	}

	function openVideoModal(button) {
		const videoId = button.dataset.videoId;
		const videoUrl = button.dataset.videoUrl;
		const videoTitle = button.dataset.videoTitle;
		const videoChannel = button.dataset.videoChannel;
		const document = decodeURIComponent(button.dataset.videoDocument);
		const metadata = JSON.parse(
			decodeURIComponent(button.dataset.videoMetadata)
		);

		// Set modal title
		videoModalLabel.textContent = videoTitle;

		// Set iframe source (embedding the YouTube video)
		videoIframe.src = `https://www.youtube.com/embed/${videoId}`;

		// Set "Watch on YouTube" link
		watchOnYouTube.href = videoUrl;

		// Fill in the info tab
		videoInfo.innerHTML = `
            <table class="table table-hover">
                <tr>
                    <th class="w-25">Title</th>
                    <td>${videoTitle}</td>
                </tr>
                <tr>
                    <th>Channel</th>
                    <td><a href="https://www.youtube.com/channel/${
						metadata.channelId || ""
					}" target="_blank">${videoChannel}</a></td>
                </tr>
                <tr>
                    <th>YouTube ID</th>
                    <td><code>${videoId}</code></td>
                </tr>
                <tr>
                    <th>Match Score</th>
                    <td>
                        <div class="progress" style="height: 10px;">
                            <div class="progress-bar ${getScoreClass(
								metadata.score || 0
							)}" 
                                 role="progressbar" 
                                 style="width: ${
										(metadata.score || 0) * 100
									}%;" 
                                 aria-valuenow="${(metadata.score || 0) * 100}" 
                                 aria-valuemin="0" 
                                 aria-valuemax="100"></div>
                        </div>
                        <span class="small ms-2">${(
							metadata.score || 0
						).toFixed(3)}</span>
                    </td>
                </tr>
                ${
					metadata.tags_str
						? `
                <tr>
                    <th>Tags</th>
                    <td>${formatTags(metadata.tags_str)}</td>
                </tr>`
						: ""
				}
            </table>
        `;

		// Fill in the embedding text tab
		embeddingText.textContent = document;

		// Fill in the metadata tab
		metadataJson.textContent = JSON.stringify(metadata, null, 2);

		// Show the modal
		const modal = new bootstrap.Modal(videoModal);
		modal.show();
	}

	function formatTags(tagsStr) {
		if (!tagsStr) return "";

		return tagsStr
			.split(",")
			.map((tag) => {
				const trimmed = tag.trim();
				if (trimmed) {
					return `<span class="badge bg-light text-dark me-1 mb-1">${trimmed}</span>`;
				}
				return "";
			})
			.join("");
	}

	// Add CSS for animations
	const style = document.createElement("style");
	style.textContent = `
        @keyframes shake {
            0%, 100% { transform: translateX(0); }
            10%, 30%, 50%, 70%, 90% { transform: translateX(-5px); }
            20%, 40%, 60%, 80% { transform: translateX(5px); }
        }
        
        @keyframes pulse {
            0% { transform: scale(1); }
            50% { transform: scale(1.05); }
            100% { transform: scale(1); }
        }
        
        .shake-animation {
            animation: shake 0.5s ease-in-out;
        }
        
        .pulse-animation {
            animation: pulse 0.5s ease-in-out;
        }
        
        .searching {
            position: relative;
            pointer-events: none;
        }
        
        .searching:after {
            content: "";
            position: absolute;
            width: 16px;
            height: 16px;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            margin: auto;
            border: 3px solid transparent;
            border-top-color: white;
            border-radius: 50%;
            animation: button-loading-spinner 1s ease infinite;
        }
        
        @keyframes button-loading-spinner {
            from {
                transform: rotate(0turn);
            }
            to {
                transform: rotate(1turn);
            }
        }
    `;
	document.head.appendChild(style);

	// Clean up when modal is closed
	videoModal.addEventListener("hidden.bs.modal", function () {
		videoIframe.src = "";
	});
});
