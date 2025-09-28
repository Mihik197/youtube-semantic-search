let sentinel = null;
let observer = null;

export function initChannels(app) {
	const { ui } = app;
	const state = app.state.channel;

	if (!ui.channelList) return;

	bindSortButtons();
	bindSearch();
	initObserver();
	resetAndFetch(true);

	function bindSortButtons() {
		const popularBtn = document.getElementById("sortPopularBtn");
		const alphaBtn = document.getElementById("sortAlphaBtn");

		if (popularBtn) {
			popularBtn.addEventListener("click", () => {
				if (state.fetching) return;
				const mode = popularBtn.getAttribute("data-mode");
				if (mode === "desc") {
					state.currentSort = "count_asc";
					popularBtn.setAttribute("data-mode", "asc");
					const iconDir = document.getElementById("popularDirIcon");
					if (iconDir) iconDir.className = "bi bi-arrow-up-short ms-1";
				} else {
					state.currentSort = "count_desc";
					popularBtn.setAttribute("data-mode", "desc");
					const iconDir = document.getElementById("popularDirIcon");
					if (iconDir) iconDir.className = "bi bi-arrow-down-short ms-1";
				}
				popularBtn.classList.add("active");
				alphaBtn?.classList.remove("active");
				resetAndFetch();
			});
		}

		if (alphaBtn) {
			alphaBtn.addEventListener("click", () => {
				if (state.fetching) return;
				const isActive = alphaBtn.classList.contains("active");
				if (!isActive) {
					state.currentSort = "alpha";
					alphaBtn.classList.add("active");
					popularBtn?.classList.remove("active");
					resetAndFetch();
				} else {
					state.currentSort = state.currentSort === "alpha" ? "alpha_desc" : "alpha";
					resetAndFetch();
				}
				if (state.currentSort === "alpha") {
					alphaBtn.innerHTML = '<i class="bi bi-sort-alpha-down"></i>';
				} else if (state.currentSort === "alpha_desc") {
					alphaBtn.innerHTML = '<i class="bi bi-sort-alpha-up"></i>';
				}
			});
		}
	}

	function bindSearch() {
		const input = document.getElementById("channelSearchInput");
		if (!input) return;
		const debounced = debounce((event) => {
			const newTerm = event.target.value.trim().toLowerCase();
			if (newTerm === state.searchTerm) return;
			state.searchTerm = newTerm;
			resetAndFetch();
		}, 250);
		input.addEventListener("input", debounced);
	}

	function initObserver() {
		sentinel = document.createElement("li");
		sentinel.id = "channelListSentinel";
		sentinel.className = "channel-sentinel";
		sentinel.textContent = "Loading more…";
		sentinel.setAttribute("aria-hidden", "true");

		observer = new IntersectionObserver(
			(entries) => {
				entries.forEach((entry) => {
					if (entry.isIntersecting) {
						if (!state.fetching && state.dataCache.loaded < state.dataCache.total_available) {
							fetchPage();
						}
					}
				});
			},
			{ root: ui.channelList, threshold: 0, rootMargin: "0px 0px 120px 0px" },
		);

		ui.channelList.addEventListener("scroll", () => {
			if (state.fetching) return;
			if (state.dataCache.loaded >= state.dataCache.total_available) return;
			const el = ui.channelList;
			if (el.scrollHeight - el.scrollTop - el.clientHeight < 140) {
				fetchPage();
			}
		});
	}

	function resetAndFetch(showSkeleton = false) {
		state.dataCache.channels = [];
		state.dataCache.loaded = 0;
		state.offset = 0;
		if (ui.channelList) {
			ui.channelList.innerHTML = "";
		}
		fetchPage(false, showSkeleton || state.firstLoad);
		state.firstLoad = false;
	}

	async function fetchPage(retry = false, showSkeleton = false) {
		if (state.fetching) return;
		state.fetching = true;
		ui.channelsError?.classList.add("d-none");
		if (showSkeleton) {
			ui.channelsLoading?.classList.remove("d-none");
			ui.channelList.classList.add("d-none");
		}
		ui.channelList?.classList.add("loading");
		try {
			const qParam = state.searchTerm ? `&q=${encodeURIComponent(state.searchTerm)}` : "";
			const response = await fetch(
				`/channels?sort=${encodeURIComponent(state.currentSort)}&limit=${state.pageSize}&offset=${state.offset}${qParam}`,
			);
			if (!response.ok) throw new Error(`HTTP ${response.status}`);
			const data = await response.json();
			if (state.offset === 0) {
				state.dataCache.total_available = data.total_available ?? data.distinct_channels ?? 0;
			}
			state.dataCache.channels.push(...data.channels);
			state.dataCache.loaded += data.channels.length;
			state.offset += data.channels.length;
			renderFiltered();
			if (!data.error && data.has_more) {
				const el = ui.channelList;
				if (el && el.scrollHeight <= el.clientHeight + 10 && state.dataCache.loaded < state.dataCache.total_available) {
					setTimeout(() => {
						if (!state.fetching) fetchPage();
					}, 50);
				}
			}
		} catch (error) {
			console.error("Failed to load channels page", error);
			if (!retry) {
				setTimeout(() => fetchPage(true), 400);
				return;
			}
			ui.channelsError?.classList.remove("d-none");
		} finally {
			ui.channelsLoading?.classList.add("d-none");
			ui.channelList.classList.remove("d-none");
			ui.channelList?.classList.remove("loading");
			state.fetching = false;
		}
	}

	function renderFiltered() {
		if (!ui.channelList) return;
		const previousScroll = ui.channelList.scrollTop;
		const active = state.activeFilter;
		const filtered = state.dataCache.channels;
		const shouldRebuild =
			state.offset <= state.pageSize ||
			ui.channelList.querySelectorAll("li.channel-item").length === 0;
		if (shouldRebuild) {
			ui.channelList.innerHTML = "";
		}

		if (typeof bootstrap !== "undefined" && bootstrap.Tooltip) {
			document.querySelectorAll("#channelList [data-bs-toggle=\"tooltip\"]").forEach((el) => {
				const tip = bootstrap.Tooltip.getInstance(el);
				if (tip) tip.dispose();
			});
		}

		if (filtered.length === 0) {
			const li = document.createElement("li");
			li.className = "channel-item";
			li.textContent = state.searchTerm ? "No matching channels" : "No channel data available";
			ui.channelList.appendChild(li);
		} else {
			const existingChannels = new Set(
				Array.from(ui.channelList.querySelectorAll("li.channel-item")).map((li) =>
					li.getAttribute("data-channel"),
				),
			);

			filtered.forEach((channel) => {
				if (!shouldRebuild && existingChannels.has(channel.channel)) return;
				const li = document.createElement("li");
				li.className = "channel-item";
				li.setAttribute("role", "listitem");
				li.setAttribute("tabindex", "0");
				li.setAttribute("data-channel", channel.channel);
				li.innerHTML = `
					<span class="channel-avatar-wrapper">${app.results.avatarImgPlain({
						channel: channel.channel,
						channel_thumbnail: channel.channel_thumbnail,
					})}</span>
					<span class="channel-name full">${app.utils.escapeHtml(channel.channel)}</span>
					<span class="badge bg-secondary-subtle text-secondary-emphasis channel-count" title="Saved videos for channel">${channel.count}</span>`;
				li.addEventListener("click", () => selectChannel(li));
				li.addEventListener("keydown", (event) => {
					if (event.key === "Enter" || event.key === " ") {
						event.preventDefault();
						selectChannel(li);
					}
				});
				ui.channelList.appendChild(li);
				if (active && active === channel.channel) li.classList.add("active");
			});

			if (sentinel) {
				if (state.dataCache.loaded < state.dataCache.total_available) {
					ui.channelList.appendChild(sentinel);
					observer?.observe(sentinel);
				} else if (sentinel.parentElement) {
					observer?.unobserve(sentinel);
					sentinel.remove();
				}
			}

			if (sentinel && state.dataCache.loaded < state.dataCache.total_available) {
				const rect = sentinel.getBoundingClientRect();
				const parentRect = ui.channelList.getBoundingClientRect();
				if (rect.bottom <= parentRect.bottom) {
					setTimeout(() => {
						if (!state.fetching) fetchPage();
					}, 30);
				}
			}

			ui.channelList.scrollTop = previousScroll;
		}

		ui.channelList.classList.remove("d-none");
	}

	function selectChannel(listItem) {
		const channel = listItem.getAttribute("data-channel");
		ui.channelList.querySelectorAll(".channel-item").forEach((item) => item.classList.remove("active"));
		listItem.classList.add("active");
		state.activeFilter = channel;
		fetchChannelVideos(channel);
	}

	async function fetchChannelVideos(channel) {
		if (!channel) return;
		try {
			app.utils.setLoading(true);
			const response = await fetch(`/channel_videos?channel=${encodeURIComponent(channel)}`);
			if (!response.ok) throw new Error(`HTTP ${response.status}`);
			const data = await response.json();
			app.results.render(data.results || []);
			const headerEl = document.getElementById("resultsHeader");
			if (headerEl) {
				let watchTime = null;
				try {
					const found = state.dataCache.channels.find((c) => c.channel === channel);
					watchTime = found && found.watch_time ? found.watch_time : null;
				} catch (error) {
					watchTime = null;
				}
				headerEl.textContent = `${channel} (${data.count ?? (data.results ? data.results.length : 0)} videos${watchTime ? ` • ${watchTime}` : ""})`;
			}
		} catch (error) {
			console.error("Failed to load channel videos", error);
		} finally {
			app.utils.setLoading(false);
		}
	}

	function debounce(fn, delay) {
		let timeoutId;
		return function wrapped(...args) {
			clearTimeout(timeoutId);
			timeoutId = setTimeout(() => fn.apply(this, args), delay);
		};
	}

	app.channels = {
		resetAndFetch,
		fetchChannelVideos,
	};
}
