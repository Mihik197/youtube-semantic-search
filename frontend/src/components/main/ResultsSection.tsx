import type { VideoResult } from '../../types/api'
import type { ResultContext } from '../../types/ui'
import { VideoCard } from './VideoCard'

interface ResultsSectionProps {
  context: ResultContext
  title: string
  badge?: string
  results: VideoResult[]
  emptyMessage?: string
  isLoading: boolean
  collectionEmpty: boolean
  onVideoSelect: (video: VideoResult) => void
}

export function ResultsSection({
  context,
  title,
  badge,
  results,
  emptyMessage,
  isLoading,
  collectionEmpty,
  onVideoSelect,
}: ResultsSectionProps) {
  const showInitial = context === 'initial'
  const showResults = results.length > 0
  const showNoResults = !isLoading && !showResults && context !== 'initial'

  return (
    <>
      <section id="emptyState" className={showInitial ? '' : 'd-none'}>
        {collectionEmpty ? (
          <div className="alert alert-warning" role="alert">
            <i className="bi bi-exclamation-triangle-fill" />
            <div>
              <strong>No videos in database</strong>
              <p className="mb-0">
                Please run <code>python ingest_data.py</code> first to import your Watch Later videos.
              </p>
            </div>
          </div>
        ) : (
          <div className="initial-message">
            <i className="bi bi-search" />
            <p>Enter a search query to find videos in your Watch Later list</p>
          </div>
        )}
      </section>

      <section id="searchProgress" className={isLoading ? 'text-center' : 'text-center d-none'}>
        <div className="spinner-border" role="status">
          <span className="visually-hidden">Searching...</span>
        </div>
        <p>Searching for relevant videos...</p>
      </section>

      <section id="resultsArea" className={showResults ? '' : 'd-none'}>
        <div className="d-flex justify-content-between align-items-center mb-4">
          <h2 className="mb-0" id="resultsHeader">
            {title}
          </h2>
          {badge ? (
            <span id="resultCount" className="badge rounded-pill bg-secondary-subtle text-secondary-emphasis">
              {badge}
            </span>
          ) : null}
        </div>
        <div id="resultsContainer" className="row row-cols-1 row-cols-md-2 row-cols-xl-3 g-4 results-container">
          {results.map((video, index) => (
            <VideoCard
              key={video.id || video.url || `result-${index}`}
              video={video}
              onSelect={onVideoSelect}
            />
          ))}
        </div>
      </section>

      <section id="noResults" className={showNoResults ? 'alert alert-info' : 'alert alert-info d-none'} role="alert">
        <i className="bi bi-info-circle-fill" />
        <div>
          <strong>No videos found</strong>
          <p className="mb-0">{emptyMessage ?? 'Try a different search query or different keywords.'}</p>
        </div>
      </section>
    </>
  )
}
