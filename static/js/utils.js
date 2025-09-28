export function createUtils(app) {
	const { ui } = app;

	function escapeHtml(str) {
		if (typeof str !== "string") return "";
		return str.replace(/[&<>'"]/g, (c) => ({
			"&": "&amp;",
			"<": "&lt;",
			">": "&gt;",
			'"': "&quot;",
			"'": "&#39;",
		}[c]));
	}

	function copyToClipboard(text, button) {
		navigator.clipboard.writeText(text).then(
			() => {
				const originalText = button.innerHTML;
				button.innerHTML = '<i class="bi bi-check-lg"></i> Copied!';
				setTimeout(() => {
					button.innerHTML = originalText;
				}, 2000);
			},
			(err) => {
				console.error("Could not copy text: ", err);
				const originalText = button.innerHTML;
				button.innerHTML = "Error!";
				setTimeout(() => {
					button.innerHTML = originalText;
				}, 2000);
			},
		);
	}

	function scoreClass(score) {
		if (score >= 0.8) return "bg-success";
		if (score >= 0.6) return "bg-primary";
		if (score >= 0.4) return "bg-info";
		if (score >= 0.2) return "bg-warning";
		return "bg-secondary";
	}

	function setLoading(isLoading) {
		if (!ui.searchButton) return;
		if (isLoading) {
			ui.searchButton.disabled = true;
			ui.searchButton.innerHTML =
				'<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Searching...';
			ui.emptyState?.classList.add("d-none");
			ui.resultsArea?.classList.add("d-none");
			ui.noResults?.classList.add("d-none");
			ui.searchProgress?.classList.remove("d-none");
		} else {
			ui.searchButton.disabled = false;
			ui.searchButton.innerHTML = '<i class="bi bi-search"></i> Search';
			ui.searchProgress?.classList.add("d-none");
		}
	}

	function showError(message) {
		ui.resultsArea?.classList.add("d-none");
		if (ui.noResults) {
			ui.noResults.innerHTML = `
				<i class="bi bi-exclamation-triangle-fill"></i>
				<div>
					<strong>Search Error</strong>
					<p class="mb-0">${message}</p>
				</div>`;
			ui.noResults.classList.remove("d-none");
		}
	}

	return {
		bindGlobal() {},
		escapeHtml,
		copyToClipboard,
		scoreClass,
		setLoading,
		showError,
	};
}
