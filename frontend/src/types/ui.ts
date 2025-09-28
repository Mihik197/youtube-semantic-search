import type { VideoResult } from './api'

export type ResultContext = 'initial' | 'search' | 'channel' | 'topic'

export interface ResultsPayload {
    context: ResultContext
    title: string
    badge?: string
    results: VideoResult[]
    emptyMessage?: string
}
