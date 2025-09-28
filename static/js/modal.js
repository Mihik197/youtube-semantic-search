export function initModal(app) {
	const { ui, utils } = app;

	function open(dataset) {
		if (!ui.videoModal) return;
		const { videoId, videoUrl, videoTitle, videoChannel, videoDocument, videoMetadata } = dataset;
		let metadata;
		try {
			metadata = JSON.parse(decodeURIComponent(videoMetadata));
		} catch (error) {
			console.error("Failed to parse video metadata", error);
			metadata = {};
		}

		if (ui.videoModalLabel) {
			ui.videoModalLabel.textContent = videoTitle;
		}
		if (ui.videoIframe) {
			ui.videoIframe.src = `https://www.youtube.com/embed/${videoId}`;
		}
		if (ui.watchOnYouTube) {
			ui.watchOnYouTube.href = videoUrl;
		}
		if (ui.videoInfo) {
			ui.videoInfo.innerHTML = `
				<table class="table table-hover">
					<tbody>
						<tr><th class="w-25">Title</th><td>${videoTitle}</td></tr>
						<tr><th>Channel</th><td>${videoChannel}</td></tr>
						<tr><th>YouTube ID</th><td><code>${videoId}</code></td></tr>
					</tbody>
				</table>`;
		}
		if (ui.embeddingText) {
			ui.embeddingText.textContent = decodeURIComponent(videoDocument);
		}
		if (ui.metadataJson) {
			ui.metadataJson.textContent = JSON.stringify(metadata, null, 2);
		}

		const modalInstance = new bootstrap.Modal(ui.videoModal);
		modalInstance.show();
	}

	ui.videoModal?.addEventListener("hidden.bs.modal", () => {
		if (ui.videoIframe) {
			ui.videoIframe.src = "about:blank";
		}
	});

	ui.copyEmbedding?.addEventListener("click", () => {
		if (!ui.embeddingText) return;
		utils.copyToClipboard(ui.embeddingText.textContent, ui.copyEmbedding);
	});

	ui.copyMetadata?.addEventListener("click", () => {
		if (!ui.metadataJson) return;
		utils.copyToClipboard(ui.metadataJson.textContent, ui.copyMetadata);
	});

	app.modal = { open };
}
