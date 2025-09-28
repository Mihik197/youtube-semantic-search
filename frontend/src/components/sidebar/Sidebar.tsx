import { SearchOptions } from './SearchOptions'
import { ChannelSection } from './ChannelSection'
import { TopicSection } from './TopicSection'
import type { ResultsPayload } from '../../types/ui'

interface SidebarProps {
  numResults: number
  onNumResultsChange: (value: number) => void
  dbCount: number
  collectionName: string
  embeddingModel: string
  collectionEmpty: boolean
  onDisplayResults: (payload: ResultsPayload) => void
  onLoadingChange: (loading: boolean) => void
  onError: (message: string) => void
  activeChannel: string | null
  onActiveChannelChange: (channel: string | null) => void
  activeTopicId: number | null
  onActiveTopicChange: (id: number | null) => void
}

export function Sidebar({
  numResults,
  onNumResultsChange,
  dbCount,
  collectionName,
  embeddingModel,
  collectionEmpty,
  onDisplayResults,
  onLoadingChange,
  onError,
  activeChannel,
  onActiveChannelChange,
  activeTopicId,
  onActiveTopicChange,
}: SidebarProps) {
  return (
    <aside className="col-md-3 col-lg-2 d-md-block sidebar">
      <div className="position-sticky pt-3">
        <header className="sidebar-header">
          <h3>
            <i className="bi bi-youtube" /> Watch Later
          </h3>
          <p className="text-muted">Your personal video search engine</p>
        </header>

        <SearchOptions value={numResults} onChange={onNumResultsChange} />

        <ChannelSection
          onDisplayResults={onDisplayResults}
          onLoadingChange={onLoadingChange}
          onError={onError}
          activeChannel={activeChannel}
          onActiveChannelChange={onActiveChannelChange}
        />

        <TopicSection
          onDisplayResults={onDisplayResults}
          onLoadingChange={onLoadingChange}
          onError={onError}
          activeTopicId={activeTopicId}
          onActiveTopicChange={onActiveTopicChange}
        />

        <footer className="sidebar-footer">
          <div
            className={`status-card p-3 mb-3 ${collectionEmpty ? 'bg-warning' : 'bg-success text-white'}`}
          >
            <div className="d-flex justify-content-between align-items-center mb-2">
              <span className="fw-medium">
                <i className="bi bi-database-fill" /> Database Status
              </span>
              <span
                className={`badge ${collectionEmpty ? 'bg-warning text-dark' : 'bg-white text-success'} rounded-pill`}
              >
                {dbCount} videos
              </span>
            </div>
            <div className={`small ${collectionEmpty ? 'text-dark' : 'text-white'} opacity-75`}>
              {collectionEmpty ? 'Please run ingestion script first' : 'All videos indexed and ready to search'}
            </div>
          </div>

          <div className="small text-muted p-2">
            <div className="mb-1 d-flex align-items-center">
              <i className="bi bi-box me-2" />
              <span>
                Model:
                <code className="ms-1">{embeddingModel}</code>
              </span>
            </div>
            <div className="d-flex align-items-center">
              <i className="bi bi-collection me-2" />
              <span>
                Collection:
                <code className="ms-1">{collectionName}</code>
              </span>
            </div>
          </div>
        </footer>
      </div>
    </aside>
  )
}
