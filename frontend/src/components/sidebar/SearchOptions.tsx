import { useCallback, useEffect, useRef } from 'react'

interface SearchOptionsProps {
  value: number
  onChange: (value: number) => void
  min?: number
  max?: number
}

export function SearchOptions({ value, onChange, min = 1, max = 50 }: SearchOptionsProps) {
  const rangeRef = useRef<HTMLInputElement>(null)
  const bubbleRef = useRef<HTMLSpanElement>(null)

  const syncBubble = useCallback(() => {
    const range = rangeRef.current
    const bubble = bubbleRef.current
    if (!range || !bubble) return
    const minValue = Number(range.min || min)
    const maxValue = Number(range.max || max)
    const percent = (value - minValue) / (maxValue - minValue)
    const sliderWidth = range.getBoundingClientRect().width
    const bubbleWidth = bubble.getBoundingClientRect().width
    const offset = percent * (sliderWidth - 16) + 8 - bubbleWidth / 2
    const clamped = Math.max(0, Math.min(offset, sliderWidth - bubbleWidth))
    bubble.style.left = `${clamped}px`
  }, [value, min, max])

  useEffect(() => {
    syncBubble()
  }, [syncBubble])

  useEffect(() => {
    const handleResize = () => syncBubble()
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [syncBubble])

  return (
    <section className="px-3 mb-4" aria-labelledby="results-slider-label">
      <h5 className="mb-3" id="results-slider-label">
        Search Options
      </h5>
      <div className="mb-4 position-relative" id="resultsSliderWrapper">
        <label htmlFor="numResults" className="form-label mb-1">
          Results to show
        </label>
        <div className="range-bubble-container mb-2">
          <span className="range-bubble" id="numResultsBubble" role="status" aria-live="polite" ref={bubbleRef}>
            {value}
          </span>
        </div>
        <input
          ref={rangeRef}
          type="range"
          className="form-range results-range"
          id="numResults"
          min={min}
          max={max}
          value={value}
          onChange={(event) => onChange(Number(event.target.value))}
          aria-valuemin={min}
          aria-valuemax={max}
          aria-valuenow={value}
        />
        <div className="d-flex justify-content-between small text-muted mt-1" aria-hidden="true">
          <span>{min}</span>
          <span>{Math.round((min + max) / 2)}</span>
          <span>{max}</span>
        </div>
      </div>
    </section>
  )
}
