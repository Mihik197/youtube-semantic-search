const topicState = { sort: "size_desc", includeNoise: false, loading: false, clusters: [], active: null };

export function initTopics(app) {
	const { ui } = app;
	if (!ui.topicList) return;

	bindSort();
	bindNoiseToggle();
	fetchTopics();

	function bindSort() {
		ui.topicSortSizeDesc?.addEventListener("click", () => {
			if (topicState.loading) return;
			topicState.sort = "size_desc";
			ui.topicSortSizeDesc.classList.add("active");
			ui.topicSortAlpha?.classList.remove("active");
			if (ui.topicSortAlpha) {
				ui.topicSortAlpha.innerHTML = '<i class="bi bi-sort-alpha-down"></i>';
			}
			fetchTopics();
		});

		ui.topicSortAlpha?.addEventListener("click", () => {
			if (topicState.loading) return;
			if (topicState.sort === "alpha") {
				topicState.sort = "alpha_desc";
				ui.topicSortAlpha.innerHTML = '<i class="bi bi-sort-alpha-up"></i>';
			} else {
				topicState.sort = "alpha";
				ui.topicSortAlpha.innerHTML = '<i class="bi bi-sort-alpha-down"></i>';
			}
			ui.topicSortAlpha.classList.add("active");
			ui.topicSortSizeDesc?.classList.remove("active");
			fetchTopics();
		});
	}

	function bindNoiseToggle() {
		ui.toggleNoiseTopics?.addEventListener("change", () => {
			topicState.includeNoise = ui.toggleNoiseTopics.checked;
			fetchTopics();
		});
	}

	async function fetchTopics() {
		const { topicList, topicsLoading, topicsError } = ui;
		topicState.loading = true;
		topicsError?.classList.add("d-none");
		topicsLoading?.classList.remove("d-none");
		topicList?.classList.add("d-none");
		try {
			const response = await fetch(`/topics?sort=${encodeURIComponent(topicState.sort)}&include_noise=${topicState.includeNoise}`);
			if (!response.ok) throw new Error(`HTTP ${response.status}`);
			const data = await response.json();
			topicState.clusters = data.clusters || [];
			renderTopics();
		} catch (error) {
			console.error("Failed to load topics", error);
			topicsError?.classList.remove("d-none");
		} finally {
			topicsLoading?.classList.add("d-none");
			topicState.loading = false;
		}
	}

	function renderTopics() {
		const { topicList } = ui;
		if (!topicList) return;
		topicList.innerHTML = "";
		if (topicState.clusters.length === 0) {
			const li = document.createElement("li");
			li.className = "topic-item";
			li.textContent = "No topics available";
			topicList.appendChild(li);
		} else {
			const total = topicState.clusters.reduce((acc, cluster) => acc + (cluster.size || 0), 0) || 1;
			topicState.clusters.forEach((cluster) => {
				const li = document.createElement("li");
				li.className = "topic-item";
				li.setAttribute("data-topic-id", cluster.id);
				li.setAttribute("tabindex", "0");
				const pct = Math.min(100, Math.max(0, cluster.percent ?? (cluster.size / total) * 100));
				const kws = (cluster.top_keywords || []).slice(0, 3).join(", ");
				li.innerHTML = `
					<div class="topic-bar-wrapper w-100">
						<div class="flex-grow-1 text-truncate" title="${app.utils.escapeHtml(cluster.label)}">${app.utils.escapeHtml(cluster.label)}</div>
						<span class="badge bg-secondary-subtle text-secondary-emphasis topic-count" title="Videos in topic">${cluster.size}</span>
					</div>
					<div class="topic-bar w-100 mt-1" aria-label="${pct.toFixed(2)}% of corpus"><span style="width:${pct.toFixed(2)}%"></span></div>
					<div class="topic-kws" title="${app.utils.escapeHtml(kws)}">${app.utils.escapeHtml(kws)}</div>`;
				li.addEventListener("click", () => selectTopic(cluster.id, li));
				li.addEventListener("keydown", (event) => {
					if (event.key === "Enter" || event.key === " ") {
						event.preventDefault();
						selectTopic(cluster.id, li);
					}
				});
				topicList.appendChild(li);
				if (topicState.active === cluster.id) li.classList.add("active");
			});
		}
		topicList.classList.remove("d-none");
	}

	async function selectTopic(clusterId, listItem) {
		const { topicList } = ui;
		if (!topicList) return;
		Array.from(topicList.querySelectorAll(".topic-item")).forEach((el) => el.classList.remove("active"));
		if (listItem) listItem.classList.add("active");
		topicState.active = clusterId;
		try {
			app.utils.setLoading(true);
			const response = await fetch(`/topics/${clusterId}`);
			if (!response.ok) throw new Error(`HTTP ${response.status}`);
			const data = await response.json();
			const videos = data.videos || [];
			app.results.render(
				videos.map((video) => ({
					id: video.id,
					title: video.title,
					channel: video.channel,
					channel_thumbnail: null,
					channel_id: null,
					url: video.url,
					score: 0.0,
					thumbnail: video.thumbnail,
					document: "",
					metadata: video,
				})),
			);
			const headerEl = document.getElementById("resultsHeader");
			if (headerEl) headerEl.textContent = `Topic: ${data.cluster?.label || clusterId} (${videos.length})`;
		} catch (error) {
			console.error("Failed to load topic detail", error);
		} finally {
			app.utils.setLoading(false);
		}
	}

	app.topics = {
		refresh: fetchTopics,
	};
}
