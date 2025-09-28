import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useInfiniteQuery } from '@tanstack/react-query'
import { fetchChannelPage, fetchChannelVideos } from '../../api/client'
import type { ChannelPage, ChannelSummary, VideoResult } from '../../types/api'
import type { ResultsPayload } from '../../types/ui'
import { ChannelAvatar } from '../common/ChannelAvatar'

const PAGE_SIZE = 50

type SortMode = 'count_desc' | 'count_asc' | 'alpha' | 'alpha_desc'

interface ChannelSectionProps {
  onDisplayResults: (payload: ResultsPayload) => void
  onLoadingChange: (loading: boolean) => void
  onError: (message: string) => void
  activeChannel: string | null
  onActiveChannelChange: (channel: string | null) => void
}

export function ChannelSection({
  onDisplayResults,
  onLoadingChange,
  onError,
  activeChannel,
  onActiveChannelChange,
}: ChannelSectionProps) {
  const [sort, setSort] = useState<SortMode>('count_desc')
  const [searchTerm, setSearchTerm] = useState('')

  const listRef = useRef<HTMLUListElement>(null)
  const sentinelRef = useRef<HTMLLIElement>(null)

  const trimmedSearch = searchTerm.trim()
  const searchKey = trimmedSearch.toLowerCase()

  const {
    data,
    error,
    isLoading,
    isFetchingNextPage,
    fetchNextPage,
    hasNextPage,
    refetch,
  } = useInfiniteQuery<ChannelPage, Error>({
    queryKey: ['channels', sort, searchKey],
    queryFn: ({ pageParam = 0, signal }) =>
      fetchChannelPage(
        {
          sort,
          limit: PAGE_SIZE,
          offset: typeof pageParam === 'number' ? pageParam : 0,
          q: trimmedSearch ? trimmedSearch : undefined,
        },
        signal,
      ),
    initialPageParam: 0,
    getNextPageParam: (lastPage: ChannelPage) => {
      if (!lastPage.has_more) return undefined
      return (lastPage.offset ?? 0) + (lastPage.returned ?? 0)
    },
    staleTime: 2 * 60 * 1000,
    refetchOnWindowFocus: false,
  })

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = 0
    }
  }, [sort, searchTerm])

  useEffect(() => {
    const sentinel = sentinelRef.current
    const container = listRef.current
    if (!sentinel || !container) return
    if (!hasNextPage) return

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            fetchNextPage()
          }
        })
      },
      {
        root: container,
        rootMargin: '0px 0px 120px 0px',
        threshold: 0,
      },
    )

    observer.observe(sentinel)
    return () => {
      observer.disconnect()
    }
  }, [hasNextPage, fetchNextPage])

  const channels = useMemo(() => {
    if (!data) return [] as ChannelSummary[]
    return data.pages.flatMap((page: ChannelPage) => page.channels)
  }, [data])

  useEffect(() => {
    if (!activeChannel) return
    if (channels.every((channel) => channel.channel !== activeChannel)) {
      onActiveChannelChange(null)
    }
  }, [activeChannel, channels, onActiveChannelChange])

  const handleSortPopular = () => {
    setSort((prev) => (prev === 'count_desc' ? 'count_asc' : 'count_desc'))
  }

  const handleSortAlpha = () => {
    setSort((prev) => {
      if (prev === 'alpha') return 'alpha_desc'
      return 'alpha'
    })
  }

  const triggerFetchVideos = useCallback(
    async (summary: ChannelSummary) => {
      onActiveChannelChange(summary.channel)
      onLoadingChange(true)
      try {
        const response = await fetchChannelVideos(summary.channel)
        const results: VideoResult[] = response.results ?? []
        const watchLabel = summary.watch_time ? ` • ${summary.watch_time}` : ''
        onDisplayResults({
          context: 'channel',
          title: `${summary.channel} (${response.count ?? results.length} videos${watchLabel})`,
          badge: String(response.count ?? results.length),
          results,
          emptyMessage: 'No videos saved for this channel yet.',
        })
      } catch (err) {
        console.error('Failed to load channel videos', err)
        onError(err instanceof Error ? err.message : 'Failed to load channel videos')
        onActiveChannelChange(null)
      } finally {
        onLoadingChange(false)
      }
    },
    [onActiveChannelChange, onDisplayResults, onError, onLoadingChange],
  )

  const handleChannelClick = (summary: ChannelSummary) => {
    triggerFetchVideos(summary)
  }

  const isInitialLoading = isLoading

  return (
    <section className="px-3 mb-4" id="channelsSection">
      <div className="d-flex align-items-center mb-2 gap-2 channel-header-row">
        <h5 className="mb-0 flex-grow-1 text-truncate" title="Channels">
          Channels
        </h5>
        <div className="btn-group btn-group-sm" role="group" aria-label="Channel sorting" id="channelSortButtons">
          <button
            type="button"
            className={`btn btn-outline-secondary ${sort === 'count_desc' || sort === 'count_asc' ? 'active' : ''}`}
            onClick={handleSortPopular}
            title="Sort by count (toggle asc/desc)"
            aria-label="Sort by popularity"
          >
            <i className="bi bi-bar-chart-fill" />
            <i className={`bi ${sort === 'count_asc' ? 'bi-arrow-up-short' : 'bi-arrow-down-short'} ms-1`} id="popularDirIcon" />
          </button>
          <button
            type="button"
            className={`btn btn-outline-secondary ${sort === 'alpha' || sort === 'alpha_desc' ? 'active' : ''}`}
            onClick={handleSortAlpha}
            title="Sort alphabetically"
            aria-label="Sort alphabetically"
          >
            <i className={`bi ${sort === 'alpha_desc' ? 'bi-sort-alpha-up' : 'bi-sort-alpha-down'}`} />
          </button>
        </div>
      </div>
      <div className="mb-2">
        <input
          type="text"
          className="form-control form-control-sm"
          placeholder="Search channels..."
          aria-label="Filter channels by name"
          value={searchTerm}
          onChange={(event) => setSearchTerm(event.target.value)}
        />
      </div>

      {isInitialLoading ? (
        <div id="channelsLoading" className="channel-skeleton-list">
          {Array.from({ length: 5 }).map((_, index) => (
            <div className="channel-skeleton" key={`channel-skeleton-${index}`} />
          ))}
        </div>
      ) : error ? (
        <div id="channelsError" className="alert alert-danger small" role="alert">
          Failed to load channels.
          <button type="button" className="btn btn-link btn-sm ps-1" onClick={() => refetch()}>
            Retry
          </button>
        </div>
      ) : (
        <ul className="list-unstyled channel-list" id="channelList" ref={listRef} role="list" aria-label="Channels list">
          {channels.length === 0 ? (
            <li className="channel-item">{searchTerm ? 'No matching channels' : 'No channel data available'}</li>
          ) : (
            channels.map((channel: ChannelSummary) => (
              <li
                key={channel.channel}
                className={`channel-item ${activeChannel === channel.channel ? 'active' : ''}`}
                role="listitem"
                tabIndex={0}
                onClick={() => handleChannelClick(channel)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault()
                    handleChannelClick(channel)
                  }
                }}
                data-channel={channel.channel}
              >
                <span className="channel-meta">
                  <ChannelAvatar name={channel.channel} thumbnail={channel.channel_thumbnail} size="sm" />
                </span>
                <span className="channel-name full">{channel.channel}</span>
                <span className="badge bg-secondary-subtle text-secondary-emphasis channel-count" title="Saved videos for channel">
                  {channel.count}
                </span>
              </li>
            ))
          )}
          {hasNextPage ? (
            <li
              className="channel-sentinel"
              ref={sentinelRef}
              aria-hidden="true"
            >
              {isFetchingNextPage ? 'Loading more…' : 'Scroll for more'}
            </li>
          ) : null}
        </ul>
      )}
    </section>
  )
}
