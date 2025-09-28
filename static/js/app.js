import { createUtils } from "./utils.js";
import { initTheme } from "./theme.js";
import { initTooltips } from "./tooltips.js";
import { initSearch } from "./search.js";
import { createResults } from "./results.js";
import { initModal } from "./modal.js";
import { initChannels } from "./channels.js";
import { initTopics } from "./topics.js";

const app = {
	ui: {},
	state: {
		channel: {
			currentSort: "count_desc",
			dataCache: { channels: [], total_available: 0, loaded: 0, limit: 50 },
			searchTerm: "",
			offset: 0,
			pageSize: 50,
			fetching: false,
			activeFilter: null,
			firstLoad: true,
		},
	},
};

function cacheDom() {
	app.ui = {
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
		channelsError: document.getElementById("channelsError"),
		topicList: document.getElementById("topicList"),
		topicsLoading: document.getElementById("topicsLoading"),
		topicsError: document.getElementById("topicsError"),
		toggleNoiseTopics: document.getElementById("toggleNoiseTopics"),
		topicSortSizeDesc: document.getElementById("topicSortSizeDesc"),
		topicSortAlpha: document.getElementById("topicSortAlpha"),
	};
}

function initApp() {
	cacheDom();
	app.utils = createUtils(app);
	app.results = createResults(app);
	app.utils.bindGlobal();
	initTheme(app);
	initTooltips(app);
	initSearch(app);
	initModal(app);
	initChannels(app);
	initTopics(app);
}

document.addEventListener("DOMContentLoaded", initApp);

export default app;
