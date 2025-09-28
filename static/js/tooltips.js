export function initTooltips(app) {
	function initialize() {
		if (typeof bootstrap !== "undefined" && bootstrap.Tooltip) {
			const tooltipTriggerList = Array.from(
				document.querySelectorAll('[data-bs-toggle="tooltip"]'),
			);
			tooltipTriggerList.forEach((el) => new bootstrap.Tooltip(el));
		}
	}

	initialize();

	app.tooltips = {
		init: initialize,
		refresh: initialize,
	};
}
