import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchTopicDetail, fetchTopics } from '../../api/client'
import type { TopicDetailResponse, TopicListResponse, TopicSummary, VideoResult } from '../../types/api'
import type { ResultsPayload } from '../../types/ui'

interface TopicSectionProps {
  onDisplayResults: (payload: ResultsPayload) => void
  onLoadingChange: (loading: boolean) => void
  onError: (message: string) => void
  activeTopicId: number | null
  onActiveTopicChange: (id: number | null) => void
}

type TopicSort = 'size_desc' | 'alpha' | 'alpha_desc'

export function TopicSection({
  onDisplayResults,
  onLoadingChange,
  onError,
  activeTopicId,
  onActiveTopicChange,
}: TopicSectionProps) {
  const [sort, setSort] = useState<TopicSort>('size_desc')
  const [includeNoise, setIncludeNoise] = useState(false)

  const {
    data,
    error,
    isLoading,
    refetch,
    isFetching,
  } = useQuery<TopicListResponse, Error>({
    queryKey: ['topics', sort, includeNoise],
    queryFn: ({ signal }) => fetchTopics({ sort, includeNoise }, signal),
    staleTime: 5 * 60 * 1000,
    refetchOnWindowFocus: false,
  })

  const clusters = useMemo(() => data?.clusters ?? [], [data])

  useEffect(() => {
    if (activeTopicId !== null && clusters.every((cluster) => cluster.id !== activeTopicId)) {
      onActiveTopicChange(null)
    }
  }, [clusters, activeTopicId, onActiveTopicChange])

  const handleSelectTopic = async (cluster: TopicSummary) => {
    onActiveTopicChange(cluster.id)
    onLoadingChange(true)
    try {
      const detail: TopicDetailResponse = await fetchTopicDetail(cluster.id)
      const videos: VideoResult[] = (detail.videos ?? []).map((video) => ({
        id: video.id,
        title: video.title ?? 'Untitled',
        channel: video.channel ?? 'Unknown Channel',
        url: video.url,
        thumbnail: video.thumbnail,
        score: 0,
        document: '',
        metadata: {
          id: video.id,
          title: video.title,
          channel: video.channel,
          url: video.url,
          published_at: video.published_at,
          duration_seconds: video.duration_seconds,
        },
      }))
      const label = detail.cluster?.label ?? cluster.label ?? `Topic ${cluster.id}`
      onDisplayResults({
        context: 'topic',
        title: `Topic: ${label} (${videos.length})`,
        badge: String(videos.length),
        results: videos,
        emptyMessage: 'No videos found in this topic right now.',
      })
    } catch (err) {
      console.error('Failed to load topic detail', err)
      onError(err instanceof Error ? err.message : 'Failed to load topic detail')
      onActiveTopicChange(null)
    } finally {
      onLoadingChange(false)
    }
  }

  return (
    <section className="px-3 mb-4" id="topicsSection">
      <div className="d-flex align-items-center mb-2 gap-2 topic-header-row">
        <h5 className="mb-0 flex-grow-1 text-truncate" title="Topics">
          Topics
        </h5>
        <div className="btn-group btn-group-sm" role="group" aria-label="Topic sorting" id="topicSortButtons">
          <button
            type="button"
            className={`btn btn-outline-secondary ${sort === 'size_desc' ? 'active' : ''}`}
            onClick={() => setSort('size_desc')}
            disabled={isFetching && sort === 'size_desc'}
            title="Sort by size"
          >
            <i className="bi bi-diagram-3" />
          </button>
          <button
            type="button"
            className={`btn btn-outline-secondary ${sort === 'alpha' || sort === 'alpha_desc' ? 'active' : ''}`}
            onClick={() => setSort((prev) => (prev === 'alpha' ? 'alpha_desc' : 'alpha'))}
            disabled={isFetching && (sort === 'alpha' || sort === 'alpha_desc')}
            title="Sort alphabetically"
          >
            <i className={`bi ${sort === 'alpha_desc' ? 'bi-sort-alpha-up' : 'bi-sort-alpha-down'}`} />
          </button>
        </div>
      </div>
      <div className="form-check form-switch form-switch-sm mb-2">
        <input
          className="form-check-input"
          type="checkbox"
          role="switch"
          id="toggleNoiseTopics"
          checked={includeNoise}
          onChange={(event) => setIncludeNoise(event.target.checked)}
        />
        <label className="form-check-label small" htmlFor="toggleNoiseTopics">
          Show noise
        </label>
      </div>

      {isLoading ? (
        <div id="topicsLoading" className="topic-skeleton-list">
          {Array.from({ length: 3 }).map((_, index) => (
            <div className="topic-skeleton" key={`topic-skeleton-${index}`} />
          ))}
        </div>
      ) : error ? (
        <div id="topicsError" className="alert alert-danger small" role="alert">
          Failed to load topics.
          <button type="button" className="btn btn-link btn-sm ps-1" onClick={() => refetch()}>
            Retry
          </button>
        </div>
      ) : (
        <ul className="list-unstyled topic-list" id="topicList" role="list" aria-label="Topics list">
          {clusters.length === 0 ? (
            <li className="topic-item">No topics available</li>
          ) : (
            clusters.map((cluster: TopicSummary) => {
              const percent = Math.min(100, Math.max(0, cluster.percent ?? 0))
              const keywords = (cluster.top_keywords ?? []).slice(0, 3).join(', ')
              return (
                <li
                  key={cluster.id}
                  className={`topic-item ${activeTopicId === cluster.id ? 'active' : ''}`}
                  tabIndex={0}
                  data-topic-id={cluster.id}
                  onClick={() => handleSelectTopic(cluster)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault()
                      handleSelectTopic(cluster)
                    }
                  }}
                >
                  <div className="topic-bar-wrapper w-100">
                    <div className="flex-grow-1 text-truncate" title={cluster.label}>
                      {cluster.label}
                    </div>
                    <span className="badge bg-secondary-subtle text-secondary-emphasis topic-count" title="Videos in topic">
                      {cluster.size}
                    </span>
                  </div>
                  <div className="topic-bar w-100 mt-1" aria-label={`${percent.toFixed(2)}% of corpus`}>
                    <span style={{ width: `${percent.toFixed(2)}%` }} />
                  </div>
                  <div className="topic-kws" title={keywords}>
                    {keywords || '—'}
                  </div>
                </li>
              )
            })
          )}
        </ul>
      )}
    </section>
  )
}
