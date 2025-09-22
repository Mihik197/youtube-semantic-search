// Modular namespace pattern (single bundle to avoid changing HTML script includes)
// Each sub-module exposes init and internal helpers. Order of initialization is managed centrally.
document.addEventListener("DOMContentLoaded", () => {
    const App = {
        ui: {},
        state: {
            channel: {
                currentSort: 'count_desc',
                dataCache: { channels: [], total_available: 0, loaded: 0, limit: 50 },
                searchTerm: '',
                offset: 0,
                pageSize: 50,
                fetching: false,
                activeFilter: null,
                firstLoad: true
            }
        },
        init() {
            this.cacheDom();
            this.Theme.init();
            this.Tooltips.init();
            this.Utils.bindGlobal();
            this.Search.init();
            this.Modal.init();
            this.Channels.init();
            this.Topics.init();
        },
        cacheDom() {
            this.ui = {
                themeSwitch: document.getElementById("themeSwitch"),
                searchForm: document.querySelector(".search-form"),
                searchQuery: document.getElementById("searchQuery"),
                searchButton: document.getElementById("searchButton"),
                searchSuggestions: document.querySelectorAll(".search-suggestion"),
                numResults: document.getElementById("numResults"),
                numResultsBubble: document.getElementById("numResultsBubble"),
                themeLabel: document.getElementById("themeLabel"),
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
                channelList: document.getElementById("channelList"),
                channelsLoading: document.getElementById("channelsLoading"),
                channelsError: document.getElementById("channelsError")
                , topicList: document.getElementById('topicList')
                , topicsLoading: document.getElementById('topicsLoading')
                , topicsError: document.getElementById('topicsError')
                , toggleNoiseTopics: document.getElementById('toggleNoiseTopics')
                , topicSortSizeDesc: document.getElementById('topicSortSizeDesc')
                , topicSortAlpha: document.getElementById('topicSortAlpha')
            };
        },
        Utils: {
            bindGlobal() {},
            escapeHtml(str) {
                if (typeof str !== 'string') return '';
                return str.replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\'':'&#39;'}[c]));
            },
            copyToClipboard(text, button) {
                navigator.clipboard.writeText(text).then(() => {
                    const originalText = button.innerHTML;
                    button.innerHTML = '<i class="bi bi-check-lg"></i> Copied!';
                    setTimeout(() => { button.innerHTML = originalText; }, 2000);
                }, (err) => {
                    console.error('Could not copy text: ', err);
                    const originalText = button.innerHTML;
                    button.innerHTML = 'Error!';
                    setTimeout(() => { button.innerHTML = originalText; }, 2000);
                });
            },
            scoreClass(score) {
                if (score >= 0.8) return "bg-success";
                if (score >= 0.6) return "bg-primary";
                if (score >= 0.4) return "bg-info";
                if (score >= 0.2) return "bg-warning";
                return "bg-secondary";
            },
            setLoading(isLoading) {
                const ui = App.ui;
                if (!ui.searchButton) return;
                if (isLoading) {
                    ui.searchButton.disabled = true;
                    ui.searchButton.innerHTML = `<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Searching...`;
                    ui.emptyState?.classList.add('d-none');
                    ui.resultsArea?.classList.add('d-none');
                    ui.noResults?.classList.add('d-none');
                    ui.searchProgress?.classList.remove('d-none');
                } else {
                    ui.searchButton.disabled = false;
                    ui.searchButton.innerHTML = `<i class="bi bi-search"></i> Search`;
                    ui.searchProgress?.classList.add('d-none');
                }
            },
            showError(message) {
                const ui = App.ui;
                ui.resultsArea?.classList.add('d-none');
                if (ui.noResults) {
                    ui.noResults.innerHTML = `
                        <i class="bi bi-exclamation-triangle-fill"></i>
                        <div>
                            <strong>Search Error</strong>
                            <p class="mb-0">${message}</p>
                        </div>`;
                    ui.noResults.classList.remove('d-none');
                }
            }
        },
        Theme: {
            init() {
                const ui = App.ui;
                const savedTheme = localStorage.getItem("theme") || "light";
                document.documentElement.setAttribute("data-bs-theme", savedTheme);
                if (ui.themeSwitch) {
                    ui.themeSwitch.checked = savedTheme === "dark";
                    this.updateThemeIndicators(savedTheme);
                    ui.themeSwitch.addEventListener("change", (e) => {
                        const theme = e.target.checked ? "dark" : "light";
                        document.documentElement.setAttribute("data-bs-theme", theme);
                        localStorage.setItem("theme", theme);
                        this.updateThemeIndicators(theme);
                    });
                }
            },
            updateThemeIndicators(theme) {
                const ui = App.ui;
                if (ui.themeLabel) ui.themeLabel.textContent = theme === 'dark' ? 'Dark' : 'Light';
                const sun = document.querySelector('.theme-icon.sun');
                const moon = document.querySelector('.theme-icon.moon');
                if (sun && moon) {
                    if (theme === 'dark') { sun.classList.add('d-none'); moon.classList.remove('d-none'); }
                    else { moon.classList.add('d-none'); sun.classList.remove('d-none'); }
                }
            }
        },
        Tooltips: {
            init() {
                if (typeof bootstrap !== "undefined" && bootstrap.Tooltip) {
                    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
                    tooltipTriggerList.map(el => new bootstrap.Tooltip(el));
                }
            },
            refresh() { this.init(); }
        },
        Search: {
            init() {
                const ui = App.ui;
                ui.searchButton?.addEventListener('click', () => this.perform());
                ui.searchQuery?.addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); this.perform(); }});
                ui.numResults?.addEventListener('input', function(){
                    if (ui.numResultsBubble) {
                        ui.numResultsBubble.textContent = this.value;
                        ui.numResults.setAttribute('aria-valuenow', this.value);
                        App.Search.updateRangeBubblePosition();
                    }
                });
                ui.searchSuggestions.forEach(s => s.addEventListener('click', e => { e.preventDefault(); ui.searchQuery.value = s.textContent.trim(); ui.searchQuery.focus(); }));
                setTimeout(() => this.updateRangeBubblePosition(), 0);
                window.addEventListener('resize', () => this.updateRangeBubblePosition());
            },
            updateRangeBubblePosition() {
                const ui = App.ui;
                const range = ui.numResults; const bubble = ui.numResultsBubble;
                if (!range || !bubble) return;
                const min = parseInt(range.min) || 0; const max = parseInt(range.max) || 100; const val = parseInt(range.value);
                const percent = (val - min) / (max - min);
                const sliderWidth = range.getBoundingClientRect().width;
                const bubbleWidth = bubble.getBoundingClientRect().width;
                let x = percent * (sliderWidth - 16) + 8 - (bubbleWidth / 2);
                if (x < 0) x = 0;
                const maxX = sliderWidth - bubbleWidth;
                if (x > maxX) x = maxX;
                bubble.style.left = `${x}px`;
            },
            async perform() {
                const ui = App.ui;
                const query = ui.searchQuery.value.trim();
                if (!query) { ui.searchQuery.focus(); return; }
                App.Utils.setLoading(true);
                try {
                    const resp = await fetch('/search', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ query, num_results: parseInt(ui.numResults.value) }) });
                    if (!resp.ok) throw new Error(`HTTP error! Status: ${resp.status}`);
                    const data = await resp.json();
                    App.Results.render(data.results);
                    const headerEl = document.getElementById('resultsHeader');
                    if (headerEl) headerEl.textContent = 'Search Results';
                } catch (e) {
                    console.error('Search error:', e);
                    App.Utils.showError(e.message);
                } finally {
                    App.Utils.setLoading(false);
                }
            }
        },
        Results: {
            render(results) {
                const ui = App.ui;
                if (!results || results.length === 0) {
                    ui.resultsArea?.classList.add('d-none');
                    ui.noResults?.classList.remove('d-none');
                    return;
                }
                ui.resultsContainer.innerHTML = '';
                ui.resultCount.textContent = results.length;
                const frag = document.createDocumentFragment();
                results.forEach((video, idx) => {
                    frag.appendChild(this.card(video, idx));
                });
                ui.resultsContainer.appendChild(frag);
                ui.resultsArea.classList.remove('d-none');
                App.Tooltips.refresh();
                ui.resultsContainer.querySelectorAll('.view-details').forEach(btn => btn.addEventListener('click', () => App.Modal.open(btn.dataset)));
            },
            card(video, index) {
                const card = document.createElement('div');
                card.className = 'col video-card-wrapper';
                const scoreClass = App.Utils.scoreClass(video.score);
                card.innerHTML = `
                    <div class="card video-card h-100">
                        <div class="position-relative thumb-wrapper">
                            <img src="${video.thumbnail || 'https://via.placeholder.com/480x360?text=No+Thumbnail'}" class="card-img-top" alt="${video.title}" loading="lazy">
                            <span class="score-badge ${scoreClass}">${video.score.toFixed(3)}</span>
                        </div>
                        <div class="card-body">
                            <h5 class="card-title">${video.title}</h5>
                                <p class="channel-name">
                                    ${this.avatarImg(video)}
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
                setTimeout(() => card.classList.add('visible'), 50 * index);
                return card;
            }
            , avatarImg(video) {
                const url = video.channel_thumbnail;
                const safeName = App.Utils.escapeHtml(video.channel || '');
                const channelId = video.channel_id;
                const channelUrl = channelId ? `https://www.youtube.com/channel/${channelId}` : `https://www.youtube.com/results?search_query=${encodeURIComponent(video.channel || '')}`;
                if (url) {
                    return `<a href="${channelUrl}" target="_blank" class="channel-avatar-link" aria-label="Open ${safeName} channel on YouTube" rel="noopener">` +
                        `<img src="${url}" class="channel-avatar" alt="${safeName} channel avatar" loading="lazy" onerror="this.onerror=null;this.replaceWith(App.Results.fallbackAvatar('${safeName}'));" />` +
                        `</a>`;
                }
                return `<a href="${channelUrl}" target="_blank" class="channel-avatar-link" aria-label="Open ${safeName} channel on YouTube" rel="noopener">${this.fallbackAvatar(safeName)}</a>`;
            }
            , avatarImgPlain(video) { // Non-clickable version for channel list
                const url = video.channel_thumbnail;
                const safeName = App.Utils.escapeHtml(video.channel || '');
                if (url) {
                    return `<img src="${url}" class="channel-avatar" alt="${safeName} channel avatar" loading="lazy" onerror="this.onerror=null;this.replaceWith(App.Results.fallbackAvatar('${safeName}'));" />`;
                }
                return this.fallbackAvatar(safeName);
            }
            , fallbackAvatar(name) {
                const letter = (name || '?').trim().charAt(0).toUpperCase() || '?';
                const colors = ['#6f42c1','#d63384','#fd7e14','#20c997','#0d6efd','#6610f2','#198754','#e83e8c','#fd7e14','#0dcaf0'];
                const color = colors[letter.charCodeAt(0) % colors.length];
                return `<span class="channel-avatar avatar-fallback" style="--avatar-bg:${color}" aria-hidden="true">${letter}</span>`;
            }
        },
        Modal: {
            init() {
                const ui = App.ui;
                ui.videoModal?.addEventListener('hidden.bs.modal', () => { ui.videoIframe.src = 'about:blank'; });
                ui.copyEmbedding?.addEventListener('click', () => App.Utils.copyToClipboard(ui.embeddingText.textContent, ui.copyEmbedding));
                ui.copyMetadata?.addEventListener('click', () => App.Utils.copyToClipboard(ui.metadataJson.textContent, ui.copyMetadata));
            },
            open(dataset) {
                const ui = App.ui;
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
        },
        Channels: {
            init() {
                const ui = App.ui;
                if (!ui.channelList) return;
                this.bindSortButtons();
                this.bindSearch();
                this.initObserver();
                this.resetAndFetch();
            },
            bindSortButtons() {
                const state = App.state.channel;
                const popularBtn = document.getElementById('sortPopularBtn');
                const alphaBtn = document.getElementById('sortAlphaBtn');
                if (popularBtn) {
                    popularBtn.addEventListener('click', () => {
                        if (state.fetching) return;
                        const mode = popularBtn.getAttribute('data-mode');
                        if (mode === 'desc') {
                            state.currentSort = 'count_asc';
                            popularBtn.setAttribute('data-mode', 'asc');
                            const iconDir = document.getElementById('popularDirIcon');
                            if (iconDir) iconDir.className = 'bi bi-arrow-up-short ms-1';
                        } else {
                            state.currentSort = 'count_desc';
                            popularBtn.setAttribute('data-mode', 'desc');
                            const iconDir = document.getElementById('popularDirIcon');
                            if (iconDir) iconDir.className = 'bi bi-arrow-down-short ms-1';
                        }
                        popularBtn.classList.add('active');
                        alphaBtn?.classList.remove('active');
                        this.resetAndFetch();
                    });
                }
                if (alphaBtn) {
                    alphaBtn.addEventListener('click', () => {
                        if (state.fetching) return;
                        const isActive = alphaBtn.classList.contains('active');
                        if (!isActive) {
                            state.currentSort = 'alpha';
                            alphaBtn.classList.add('active');
                            popularBtn?.classList.remove('active');
                            this.resetAndFetch();
                        } else {
                            state.currentSort = state.currentSort === 'alpha' ? 'alpha_desc' : 'alpha';
                            this.resetAndFetch();
                        }
                        if (state.currentSort === 'alpha') {
                            alphaBtn.innerHTML = '<i class="bi bi-sort-alpha-down"></i>';
                        } else if (state.currentSort === 'alpha_desc') {
                            alphaBtn.innerHTML = '<i class="bi bi-sort-alpha-up"></i>';
                        }
                    });
                }
            },
            bindSearch() {
                const input = document.getElementById('channelSearchInput');
                if (!input) return;
                const debounced = (function(fn, delay){
                    let t; return function(...args){ clearTimeout(t); t = setTimeout(()=>fn.apply(this,args), delay); };
                })( (e) => {
                    const st = App.state.channel;
                    const newTerm = e.target.value.trim().toLowerCase();
                    if (newTerm === st.searchTerm) return;
                    st.searchTerm = newTerm;
                    this.resetAndFetch();
                }, 250);
                input.addEventListener('input', debounced);
            },
            initObserver() {
                const ui = App.ui; const st = App.state.channel;
                const sentinel = document.createElement('li');
                sentinel.id = 'channelListSentinel';
                sentinel.className = 'channel-sentinel';
                sentinel.textContent = 'Loading more…';
                sentinel.setAttribute('aria-hidden', 'true');
                this._sentinel = sentinel;
                const observer = new IntersectionObserver(entries => {
                    entries.forEach(entry => {
                        if (entry.isIntersecting) {
                            console.debug('[Channels][Observer] Sentinel intersecting', { fetching: st.fetching, loaded: st.loaded, total: st.total_available });
                            if (!st.fetching && st.loaded < st.total_available) {
                                this.fetchPage();
                            }
                        }
                    });
                }, { root: ui.channelList, threshold: 0, rootMargin: '0px 0px 120px 0px' });
                this._observer = observer;
                // Fallback scroll listener (safety net)
                ui.channelList.addEventListener('scroll', () => {
                    if (st.fetching) return;
                    if (st.loaded >= st.total_available) return;
                    const el = ui.channelList;
                    if (el.scrollHeight - el.scrollTop - el.clientHeight < 140) {
                        console.debug('[Channels][FallbackScroll] Near bottom trigger');
                        this.fetchPage();
                    }
                });
            },
            resetAndFetch() {
                const st = App.state.channel;
                const ui = App.ui;
                st.dataCache.channels = [];
                st.dataCache.loaded = 0;
                st.offset = 0;
                // Preserve container to avoid layout shift; show skeleton only on very first initialization
                ui.channelList.innerHTML = '';
                this.fetchPage(false, st.firstLoad);
                st.firstLoad = false;
            },
            async fetchPage(retry=false, showSkeleton=false) {
                const st = App.state.channel;
                const ui = App.ui;
                console.debug('Fetching channels page', { offset: st.offset, sort: st.currentSort, q: st.searchTerm });
                st.fetching = true;
                ui.channelsError?.classList.add('d-none');
                if (showSkeleton) {
                    ui.channelsLoading?.classList.remove('d-none');
                    ui.channelList.classList.add('d-none');
                }
                ui.channelList?.classList.add('loading');
                try {
                    const qParam = st.searchTerm ? `&q=${encodeURIComponent(st.searchTerm)}` : '';
                    const resp = await fetch(`/channels?sort=${encodeURIComponent(st.currentSort)}&limit=${st.pageSize}&offset=${st.offset}${qParam}`);
                    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
                    const data = await resp.json();
                    if (st.offset === 0) {
                        st.dataCache.total_available = data.total_available ?? data.distinct_channels ?? 0;
                    }
                    console.debug('[Channels] Fetch success', { returned: data.channels.length, newOffset: st.offset + data.channels.length, totalAvailable: st.dataCache.total_available, hasMore: data.has_more });
                    st.dataCache.channels.push(...data.channels);
                    st.dataCache.loaded += data.channels.length;
                    st.offset += data.channels.length;
                    this.renderFiltered();
                    // Auto-fill if list isn't scrollable yet and more data available
                    if (!data.error && data.has_more) {
                        const el = ui.channelList;
                        if (el.scrollHeight <= el.clientHeight + 10 && st.dataCache.loaded < st.dataCache.total_available) {
                            setTimeout(() => { if (!st.fetching) this.fetchPage(); }, 50);
                        }
                    }
                } catch (e) {
                    console.error('Failed to load channels page', e);
                    console.debug('[Channels] Fetch error', e);
                    if (!retry) { setTimeout(() => this.fetchPage(true), 400); return; }
                    ui.channelsError?.classList.remove('d-none');
                } finally {
                    ui.channelsLoading?.classList.add('d-none');
                    ui.channelList.classList.remove('d-none');
                    ui.channelList?.classList.remove('loading');
                    st.fetching = false;
                }
            },
            renderFiltered() {
                const ui = App.ui; const st = App.state.channel;
                if (!ui.channelList) return;
                const prevScroll = ui.channelList.scrollTop;
                const active = st.activeFilter;
                // Server already filtered by searchTerm; just use cache
                const filtered = st.dataCache.channels;
                // Rebuild list always when offset == returned length? Simpler: rebuild on first page or if performing a search (offset <= pageSize)
                let rebuild = (st.offset <= st.pageSize) || ui.channelList.querySelectorAll('li.channel-item').length === 0;
                if (rebuild) ui.channelList.innerHTML = '';
                console.debug('[Channels] renderFiltered', { rebuild, totalFiltered: filtered.length, loaded: st.dataCache.loaded, searchTerm: st.searchTerm });
                // Destroy existing tooltips to prevent lingering bubbles
                if (typeof bootstrap !== 'undefined' && bootstrap.Tooltip) {
                    document.querySelectorAll('#channelList [data-bs-toggle="tooltip"]').forEach(el => {
                        const tip = bootstrap.Tooltip.getInstance(el);
                        if (tip) tip.dispose();
                    });
                }
                if (filtered.length === 0) {
                    const li = document.createElement('li');
                    li.className = 'channel-item';
                    li.textContent = st.searchTerm ? 'No matching channels' : 'No channel data available';
                    ui.channelList.appendChild(li);
                } else {
                    const existingChannels = new Set(Array.from(ui.channelList.querySelectorAll('li.channel-item')).map(li => li.getAttribute('data-channel')));
                        filtered.forEach(ch => {
                        if (!rebuild && existingChannels.has(ch.channel)) return;
                        const li = document.createElement('li');
                        li.className = 'channel-item';
                        li.setAttribute('role', 'listitem');
                        li.setAttribute('tabindex', '0');
                        li.setAttribute('data-channel', ch.channel);
                        li.innerHTML = `
                            <span class="channel-avatar-wrapper">${App.Results.avatarImgPlain({ channel: ch.channel, channel_thumbnail: ch.channel_thumbnail })}</span>
                            <span class="channel-name full">${App.Utils.escapeHtml(ch.channel)}</span>
                            <span class="badge bg-secondary-subtle text-secondary-emphasis channel-count" title="Saved videos for channel">${ch.count}</span>`;
                        li.addEventListener('click', () => this.select(li));
                        li.addEventListener('keydown', (ev) => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); this.select(li); } });
                        ui.channelList.appendChild(li);
                        if (active && active === ch.channel) li.classList.add('active');
                    });
                    // Append sentinel if more pages available
                    if (this._sentinel) {
                        if (st.dataCache.loaded < st.dataCache.total_available) {
                            ui.channelList.appendChild(this._sentinel);
                            if (this._observer) this._observer.observe(this._sentinel);
                            console.debug('[Channels] Sentinel appended', { loaded: st.dataCache.loaded, total: st.dataCache.total_available });
                        } else if (this._sentinel.parentElement) {
                            if (this._observer) this._observer.unobserve(this._sentinel);
                        }
                    }
                    // If sentinel immediately visible (short list), trigger next fetch
                    if (this._sentinel && st.dataCache.loaded < st.dataCache.total_available) {
                        const rect = this._sentinel.getBoundingClientRect();
                        const parentRect = ui.channelList.getBoundingClientRect();
                        if (rect.bottom <= parentRect.bottom) {
                            setTimeout(() => { if (!st.fetching) this.fetchPage(); }, 30);
                            console.debug('[Channels] Immediate fetch due to visible sentinel');
                        }
                    }
                    // Preserve previous scroll (especially after load more)
                    ui.channelList.scrollTop = prevScroll;
                }
                ui.channelList.classList.remove('d-none');
            },
            // updateLoadMore removed (infinite scroll)
            select(li) {
                const ui = App.ui; const st = App.state.channel;
                const channel = li.getAttribute('data-channel');
                ui.channelList.querySelectorAll('.channel-item').forEach(item => item.classList.remove('active'));
                li.classList.add('active');
                st.activeFilter = channel;
                this.fetchChannelVideos(channel);
            },
            async fetchChannelVideos(channel) {
                if (!channel) return;
                try {
                    App.Utils.setLoading(true);
                    const resp = await fetch(`/channel_videos?channel=${encodeURIComponent(channel)}`);
                    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
                    const data = await resp.json();
                    App.Results.render(data.results || []);
                    const headerEl = document.getElementById('resultsHeader');
                    if (headerEl) {
                        // Attempt to find watch_time for the active channel from cached channel list
                        let wt = null;
                        try {
                            const st = App.state.channel;
                            const found = st.dataCache.channels.find(c => c.channel === channel);
                            wt = found && found.watch_time ? found.watch_time : null;
                        } catch(e) {}
                        headerEl.textContent = `${channel} (${data.count ?? data.results.length} videos${wt ? ' • ' + wt : ''})`;
                    }
                } catch (e) {
                    console.error('Failed to load channel videos', e);
                } finally {
                    App.Utils.setLoading(false);
                }
            }
        }
        , Topics: {
            state: { sort: 'size_desc', includeNoise: false, loading: false, clusters: [], active: null },
            init() {
                const ui = App.ui;
                if (!ui.topicList) return;
                this.bindSort();
                this.bindNoiseToggle();
                this.fetch();
            },
            bindSort() {
                const ui = App.ui; const st = this.state;
                ui.topicSortSizeDesc?.addEventListener('click', () => { if (st.loading) return; st.sort = 'size_desc'; ui.topicSortSizeDesc.classList.add('active'); ui.topicSortAlpha.classList.remove('active'); this.fetch(); });
                ui.topicSortAlpha?.addEventListener('click', () => { if (st.loading) return; if (st.sort === 'alpha') { st.sort = 'alpha_desc'; ui.topicSortAlpha.innerHTML = '<i class="bi bi-sort-alpha-up"></i>'; } else { st.sort = 'alpha'; ui.topicSortAlpha.innerHTML = '<i class="bi bi-sort-alpha-down"></i>'; } ui.topicSortAlpha.classList.add('active'); ui.topicSortSizeDesc.classList.remove('active'); this.fetch(); });
            },
            bindNoiseToggle() {
                const ui = App.ui; const st = this.state;
                if (ui.toggleNoiseTopics) {
                    ui.toggleNoiseTopics.addEventListener('change', () => { st.includeNoise = ui.toggleNoiseTopics.checked; this.fetch(); });
                }
            },
            async fetch() {
                const ui = App.ui; const st = this.state;
                st.loading = true;
                ui.topicsError?.classList.add('d-none');
                ui.topicsLoading?.classList.remove('d-none');
                ui.topicList?.classList.add('d-none');
                try {
                    const resp = await fetch(`/topics?sort=${encodeURIComponent(st.sort)}&include_noise=${st.includeNoise}`);
                    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
                    const data = await resp.json();
                    st.clusters = data.clusters || [];
                    this.render();
                } catch (e) {
                    console.error('Failed to load topics', e);
                    ui.topicsError?.classList.remove('d-none');
                } finally {
                    ui.topicsLoading?.classList.add('d-none');
                    st.loading = false;
                }
            },
            render() {
                const ui = App.ui; const st = this.state;
                if (!ui.topicList) return;
                ui.topicList.innerHTML = '';
                if (st.clusters.length === 0) {
                    const li = document.createElement('li');
                    li.className = 'topic-item';
                    li.textContent = 'No topics available';
                    ui.topicList.appendChild(li);
                } else {
                    const total = st.clusters.reduce((a,c) => a + (c.size||0), 0) || 1;
                    st.clusters.forEach(c => {
                        const li = document.createElement('li');
                        li.className = 'topic-item';
                        li.setAttribute('data-topic-id', c.id);
                        li.setAttribute('tabindex', '0');
                        const pct = Math.min(100, Math.max(0, c.percent ?? (c.size/total*100)));
                        const kws = (c.top_keywords || []).slice(0,3).join(', ');
                        li.innerHTML = `
                            <div class="topic-bar-wrapper w-100">
                                <div class="flex-grow-1 text-truncate" title="${App.Utils.escapeHtml(c.label)}">${App.Utils.escapeHtml(c.label)}</div>
                                <span class="badge bg-secondary-subtle text-secondary-emphasis topic-count" title="Videos in topic">${c.size}</span>
                            </div>
                            <div class="topic-bar w-100 mt-1" aria-label="${pct.toFixed(2)}% of corpus"><span style="width:${pct.toFixed(2)}%"></span></div>
                            <div class="topic-kws" title="${App.Utils.escapeHtml(kws)}">${App.Utils.escapeHtml(kws)}</div>`;
                        li.addEventListener('click', () => this.select(c.id, li));
                        li.addEventListener('keydown', (ev) => { if (ev.key==='Enter' || ev.key===' ') { ev.preventDefault(); this.select(c.id, li); } });
                        ui.topicList.appendChild(li);
                    });
                }
                ui.topicList.classList.remove('d-none');
            },
            async select(clusterId, li) {
                const ui = App.ui; const st = this.state;
                ui.topicList.querySelectorAll('.topic-item').forEach(el => el.classList.remove('active'));
                if (li) li.classList.add('active');
                st.active = clusterId;
                try {
                    App.Utils.setLoading(true);
                    const resp = await fetch(`/topics/${clusterId}`);
                    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
                    const data = await resp.json();
                    const vids = data.videos || [];
                    App.Results.render(vids.map(v => ({
                        id: v.id,
                        title: v.title,
                        channel: v.channel,
                        channel_thumbnail: null,
                        channel_id: null,
                        url: v.url,
                        score: 0.0,
                        thumbnail: v.thumbnail,
                        document: '',
                        metadata: v
                    })));
                    const headerEl = document.getElementById('resultsHeader');
                    if (headerEl) headerEl.textContent = `Topic: ${data.cluster?.label || clusterId} (${vids.length})`;
                } catch (e) {
                    console.error('Failed to load topic detail', e);
                } finally {
                    App.Utils.setLoading(false);
                }
            }
        }
    };

    App.init();
});