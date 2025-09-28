import { useEffect, useMemo, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchAppConfig, searchVideos } from './api/client'
import type { AppConfig, VideoResult } from './types/api'
import type { ResultContext, ResultsPayload } from './types/ui'
import { Sidebar } from './components/sidebar/Sidebar'
import { SearchBar } from './components/main/SearchBar'
import { ResultsSection } from './components/main/ResultsSection'
import { VideoModal } from './components/VideoModal'

const SEARCH_SUGGESTIONS = ['python tutorials', 'history documentaries', 'cooking recipes']

interface ResultsViewState {
  context: ResultContext
  title: string
  badge?: string
  emptyMessage?: string
}

function App() {
  const {
    data: config,
    isLoading: isConfigLoading,
    error: configError,
  } = useQuery<AppConfig, Error>({
    queryKey: ['app-config'],
    queryFn: ({ signal }) => fetchAppConfig(signal),
    staleTime: Infinity,
  })

  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    if (typeof window === 'undefined') return 'light'
    const stored = window.localStorage.getItem('theme')
    return stored === 'dark' ? 'dark' : 'light'
  })

  useEffect(() => {
    document.documentElement.setAttribute('data-bs-theme', theme)
    if (typeof window !== 'undefined') {
      window.localStorage.setItem('theme', theme)
    }
  }, [theme])

  const [numResults, setNumResults] = useState<number>(10)
  const defaultResultsApplied = useRef(false)
  useEffect(() => {
    if (!config) return
    if (!defaultResultsApplied.current) {
      setNumResults(config.default_results)
      defaultResultsApplied.current = true
    }
  }, [config])

  const [searchQuery, setSearchQuery] = useState('')
  const [results, setResults] = useState<VideoResult[]>([])
  const [resultsView, setResultsView] = useState<ResultsViewState>({
    context: 'initial',
    title: 'Search Results',
  })
  const [isResultsLoading, setIsResultsLoading] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [selectedVideo, setSelectedVideo] = useState<VideoResult | null>(null)
  const [activeChannel, setActiveChannel] = useState<string | null>(null)
  const [activeTopicId, setActiveTopicId] = useState<number | null>(null)

  const searchAbortRef = useRef<AbortController | null>(null)
  useEffect(() => () => searchAbortRef.current?.abort(), [])

  const collectionEmpty = config?.collection_empty ?? false

  const handleSearch = async () => {
    const trimmed = searchQuery.trim()
    if (!trimmed) {
      setErrorMessage('Enter a search query to continue.')
      return
    }

    setErrorMessage(null)
    setActiveChannel(null)
    setActiveTopicId(null)
    setIsResultsLoading(true)

    searchAbortRef.current?.abort()
    const controller = new AbortController()
    searchAbortRef.current = controller

    try {
      const response = await searchVideos(trimmed, numResults, controller.signal)
      const fetched = response.results ?? []
      setResults(fetched)
      setResultsView({
        context: 'search',
        title: 'Search Results',
        badge: String(fetched.length),
        emptyMessage: fetched.length === 0 ? 'Try a different search query or different keywords.' : undefined,
      })
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') {
        return
      }
      const message = error instanceof Error ? error.message : 'Search failed.'
      setErrorMessage(message)
      setResults([])
      setResultsView({
        context: 'search',
        title: 'Search Results',
        badge: undefined,
        emptyMessage: 'Try a different search query or different keywords.',
      })
    } finally {
      setIsResultsLoading(false)
    }
  }

  const handleDisplayResults = (payload: ResultsPayload) => {
    setErrorMessage(null)
    setResults(payload.results)
    setResultsView({
      context: payload.context,
      title: payload.title,
      badge: payload.badge,
      emptyMessage: payload.emptyMessage,
    })
    if (payload.context === 'channel') {
      setActiveTopicId(null)
    } else if (payload.context === 'topic') {
      setActiveChannel(null)
    }
  }

  const handleResultsLoading = (loading: boolean) => {
    setIsResultsLoading(loading)
    if (loading) {
      setErrorMessage(null)
    }
  }

  const handleError = (message: string) => {
    setErrorMessage(message)
  }

  const themeLabel = useMemo(() => (theme === 'dark' ? 'Dark' : 'Light'), [theme])

  if (isConfigLoading) {
    return (
      <div className="d-flex align-items-center justify-content-center min-vh-100">
        <div className="spinner-border" role="status">
          <span className="visually-hidden">Loading application...</span>
        </div>
      </div>
    )
  }

  if (configError) {
    return (
      <div className="container py-5">
        <div className="alert alert-danger" role="alert">
          Failed to load configuration: {configError.message}
        </div>
      </div>
    )
  }

  if (!config) {
    return null
  }

  return (
    <div className="container-fluid">
      <div className="row">
        <Sidebar
          numResults={numResults}
          onNumResultsChange={setNumResults}
          dbCount={config.db_count}
          collectionName={config.collection_name}
          embeddingModel={config.embedding_model}
          collectionEmpty={collectionEmpty}
          onDisplayResults={handleDisplayResults}
          onLoadingChange={handleResultsLoading}
          onError={handleError}
          activeChannel={activeChannel}
          onActiveChannelChange={setActiveChannel}
          activeTopicId={activeTopicId}
          onActiveTopicChange={setActiveTopicId}
        />

        <main className="col-md-9 ms-sm-auto col-lg-10 px-md-4">
          <header className="main-header">
            <h1 className="display-5 fw-bold">
              <i className="bi bi-youtube text-danger" /> YouTube Search
            </h1>
            <div className="theme-switch-wrapper" title="Toggle dark mode">
              <span className="me-2 small fw-medium d-none d-md-inline" id="themeLabel">
                {themeLabel}
              </span>
              <label className="theme-switch" htmlFor="themeSwitch" aria-label="Toggle dark mode">
                <input
                  type="checkbox"
                  id="themeSwitch"
                  checked={theme === 'dark'}
                  onChange={(event) => setTheme(event.target.checked ? 'dark' : 'light')}
                />
                <div className="slider round" />
              </label>
              <i className={`bi bi-sun-fill theme-icon sun ${theme === 'dark' ? 'd-none' : ''}`} />
              <i className={`bi bi-moon-stars-fill theme-icon moon ${theme === 'dark' ? '' : 'd-none'}`} />
            </div>
          </header>

          {errorMessage ? (
            <div className="alert alert-danger" role="alert">
              {errorMessage}
            </div>
          ) : null}

          <div className="search-container">
            <SearchBar
              query={searchQuery}
              onQueryChange={setSearchQuery}
              onSubmit={handleSearch}
              isLoading={isResultsLoading}
              suggestions={SEARCH_SUGGESTIONS}
              onSuggestionClick={(suggestion) => setSearchQuery(suggestion)}
            />

            <ResultsSection
              context={resultsView.context}
              title={resultsView.title}
              badge={resultsView.badge}
              results={results}
              emptyMessage={resultsView.emptyMessage}
              isLoading={isResultsLoading}
              collectionEmpty={collectionEmpty}
              onVideoSelect={setSelectedVideo}
            />
          </div>
        </main>
      </div>

      <VideoModal video={selectedVideo} onHide={() => setSelectedVideo(null)} />
    </div>
  )
}

export default App
