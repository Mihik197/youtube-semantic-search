export function createResults(app) {
	const { ui } = app;
	const utils = () => app.utils;

	function computeFallback(name) {
		const letter = (name || "?").trim().charAt(0).toUpperCase() || "?";
		const colors = [
			"#6f42c1",
			"#d63384",
			"#fd7e14",
			"#20c997",
			"#0d6efd",
			"#6610f2",
			"#198754",
			"#e83e8c",
			"#fd7e14",
			"#0dcaf0",
		];
		const color = colors[letter.charCodeAt(0) % colors.length];
		return { letter, color };
	}

	function fallbackAvatar(name) {
		const { letter, color } = computeFallback(name);
		return `<span class="channel-avatar avatar-fallback" style="--avatar-bg:${color}" aria-hidden="true">${letter}</span>`;
	}

	function avatarImg(video) {
		const url = video.channel_thumbnail;
		const safeName = utils().escapeHtml(video.channel || "");
		const channelId = video.channel_id;
		const channelUrl = channelId
			? `https://www.youtube.com/channel/${channelId}`
			: `https://www.youtube.com/results?search_query=${encodeURIComponent(video.channel || "")}`;

		if (url) {
			const { letter, color } = computeFallback(video.channel || "");
			const fallbackInline = `this.onerror=null;const span=document.createElement('span');span.className='channel-avatar avatar-fallback';span.style.setProperty('--avatar-bg','${color}');span.setAttribute('aria-hidden','true');span.textContent='${letter}';this.replaceWith(span);`;
			return `<a href="${channelUrl}" target="_blank" class="channel-avatar-link" aria-label="Open ${safeName} channel on YouTube" rel="noopener">
				<img src="${url}" class="channel-avatar" alt="${safeName} channel avatar" loading="lazy" onerror="${fallbackInline}" />
			</a>`;
		}

		return `<a href="${channelUrl}" target="_blank" class="channel-avatar-link" aria-label="Open ${safeName} channel on YouTube" rel="noopener">${fallbackAvatar(video.channel)}</a>`;
	}

	function avatarImgPlain(video) {
		const url = video.channel_thumbnail;
		const safeName = utils().escapeHtml(video.channel || "");
		if (url) {
			const { letter, color } = computeFallback(video.channel || "");
			const fallbackInline = `this.onerror=null;const span=document.createElement('span');span.className='channel-avatar avatar-fallback';span.style.setProperty('--avatar-bg','${color}');span.setAttribute('aria-hidden','true');span.textContent='${letter}';this.replaceWith(span);`;
			return `<img src="${url}" class="channel-avatar" alt="${safeName} channel avatar" loading="lazy" onerror="${fallbackInline}" />`;
		}
		return fallbackAvatar(video.channel);
	}

	function card(video, index) {
		const cardEl = document.createElement("div");
		cardEl.className = "col video-card-wrapper";
		const scoreClass = utils().scoreClass(video.score);
		cardEl.innerHTML = `
			<div class="card video-card h-100">
				<div class="position-relative thumb-wrapper">
					<img src="${video.thumbnail || "https://via.placeholder.com/480x360?text=No+Thumbnail"}" class="card-img-top" alt="${video.title}" loading="lazy">
					<span class="score-badge ${scoreClass}">${video.score.toFixed(3)}</span>
				</div>
				<div class="card-body">
					<h5 class="card-title">${video.title}</h5>
					<p class="channel-name">
						${avatarImg(video)}
						<span>${video.channel}</span>
					</p>
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
					<a href="${video.url}" target="_blank" class="btn btn-sm btn-danger" data-bs-toggle="tooltip" title="Open in YouTube">
						<i class="bi bi-youtube"></i> Watch
					</a>
				</div>
			</div>`;
		setTimeout(() => cardEl.classList.add("visible"), 50 * index);
		return cardEl;
	}

	function render(resultsList) {
		if (!Array.isArray(resultsList) || resultsList.length === 0) {
			ui.resultsArea?.classList.add("d-none");
			ui.noResults?.classList.remove("d-none");
			return;
		}

		ui.resultsContainer.innerHTML = "";
		if (ui.resultCount) {
			ui.resultCount.textContent = resultsList.length;
		}
		const fragment = document.createDocumentFragment();
		resultsList.forEach((video, index) => {
			fragment.appendChild(card(video, index));
		});
		ui.resultsContainer.appendChild(fragment);
		ui.resultsArea.classList.remove("d-none");
		app.tooltips?.refresh();
		ui.resultsContainer.querySelectorAll(".view-details").forEach((btn) => {
			btn.addEventListener("click", () => app.modal?.open(btn.dataset));
		});
	}

	return {
		render,
		card,
		avatarImg,
		avatarImgPlain,
		fallbackAvatar,
	};
}
