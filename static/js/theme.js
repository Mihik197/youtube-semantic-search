export function initTheme(app) {
	const { ui } = app;

	function updateThemeIndicators(theme) {
		if (ui.themeLabel) {
			ui.themeLabel.textContent = theme === "dark" ? "Dark" : "Light";
		}
		const sun = document.querySelector(".theme-icon.sun");
		const moon = document.querySelector(".theme-icon.moon");
		if (sun && moon) {
			if (theme === "dark") {
				sun.classList.add("d-none");
				moon.classList.remove("d-none");
			} else {
				moon.classList.add("d-none");
				sun.classList.remove("d-none");
			}
		}
	}

	const savedTheme = localStorage.getItem("theme") || "light";
	document.documentElement.setAttribute("data-bs-theme", savedTheme);

	if (ui.themeSwitch) {
		ui.themeSwitch.checked = savedTheme === "dark";
		updateThemeIndicators(savedTheme);
		ui.themeSwitch.addEventListener("change", (event) => {
			const theme = event.target.checked ? "dark" : "light";
			document.documentElement.setAttribute("data-bs-theme", theme);
			localStorage.setItem("theme", theme);
			updateThemeIndicators(theme);
		});
	} else {
		updateThemeIndicators(savedTheme);
	}

	app.theme = { updateThemeIndicators };
}
