export function initSearch(app) {
	const { ui } = app;
	const { utils, results } = app;

	function updateRangeBubblePosition() {
		const range = ui.numResults;
		const bubble = ui.numResultsBubble;
		if (!range || !bubble) return;
		const min = parseInt(range.min, 10) || 0;
		const max = parseInt(range.max, 10) || 100;
		const val = parseInt(range.value, 10);
		const percent = (val - min) / (max - min || 1);
		const sliderWidth = range.getBoundingClientRect().width;
		const bubbleWidth = bubble.getBoundingClientRect().width;
		let x = percent * (sliderWidth - 16) + 8 - bubbleWidth / 2;
		if (x < 0) x = 0;
		const maxX = sliderWidth - bubbleWidth;
		if (x > maxX) x = maxX;
		bubble.style.left = `${x}px`;
	}

	async function perform() {
		const query = ui.searchQuery.value.trim();
		if (!query) {
			ui.searchQuery.focus();
			return;
		}

		utils.setLoading(true);
		try {
			const response = await fetch("/search", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({
					query,
					num_results: parseInt(ui.numResults.value, 10),
				}),
			});
			if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
			const data = await response.json();
			results.render(data.results);
			const headerEl = document.getElementById("resultsHeader");
			if (headerEl) headerEl.textContent = "Search Results";
		} catch (error) {
			console.error("Search error:", error);
			utils.showError(error.message);
		} finally {
			utils.setLoading(false);
		}
	}

	ui.searchButton?.addEventListener("click", () => perform());
	ui.searchQuery?.addEventListener("keydown", (event) => {
		if (event.key === "Enter") {
			event.preventDefault();
			perform();
		}
	});

	ui.numResults?.addEventListener("input", (event) => {
		if (ui.numResultsBubble) {
			const value = event.target.value;
			ui.numResultsBubble.textContent = value;
			ui.numResults.setAttribute("aria-valuenow", value);
			updateRangeBubblePosition();
		}
	});

	if (ui.searchSuggestions?.length) {
		Array.from(ui.searchSuggestions).forEach((suggestion) => {
			suggestion.addEventListener("click", (event) => {
				event.preventDefault();
				ui.searchQuery.value = suggestion.textContent.trim();
				ui.searchQuery.focus();
			});
		});
	}

	window.addEventListener("resize", updateRangeBubblePosition);
	setTimeout(updateRangeBubblePosition, 0);

	app.search = {
		perform,
		updateRangeBubblePosition,
	};
}
