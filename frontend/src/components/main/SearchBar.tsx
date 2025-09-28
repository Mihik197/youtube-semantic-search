import { useRef } from 'react'
import type { FormEvent } from 'react'

interface SearchBarProps {
  query: string
  onQueryChange: (value: string) => void
  onSubmit: () => void
  isLoading: boolean
  suggestions: string[]
  onSuggestionClick: (value: string) => void
}

export function SearchBar({
  query,
  onQueryChange,
  onSubmit,
  isLoading,
  suggestions,
  onSuggestionClick,
}: SearchBarProps) {
  const inputRef = useRef<HTMLInputElement>(null)

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!query.trim()) {
      inputRef.current?.focus()
      return
    }
    onSubmit()
  }

  return (
    <section className="search-form">
      <form onSubmit={handleSubmit} className="input-group mb-1">
        <input
          ref={inputRef}
          type="text"
          id="searchQuery"
          className="form-control form-control-lg shadow-none"
          placeholder="Find your saved videos with natural language..."
          aria-label="Search query"
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          disabled={isLoading}
        />
        <button className="btn btn-primary btn-lg" type="submit" disabled={isLoading} id="searchButton">
          {isLoading ? (
            <>
              <span className="spinner-border spinner-border-sm" role="status" aria-hidden="true" />
              <span className="ms-2">Searching...</span>
            </>
          ) : (
            <>
              <i className="bi bi-search" /> <span>Search</span>
            </>
          )}
        </button>
      </form>
      <div className="text-muted small px-2 mt-2">
        Try:
        {suggestions.map((suggestion, index) => (
          <span key={suggestion}>
            {' '}
            <a
              href="#"
              className="search-suggestion"
              onClick={(event) => {
                event.preventDefault()
                onSuggestionClick(suggestion)
                inputRef.current?.focus()
              }}
            >
              {suggestion}
            </a>
            {index < suggestions.length - 1 ? ',' : ''}
          </span>
        ))}
      </div>
    </section>
  )
}
