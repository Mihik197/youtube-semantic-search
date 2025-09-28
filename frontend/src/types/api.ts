export interface AppConfig {
    db_count: number
    collection_name: string
    collection_empty: boolean
    default_results: number
    embedding_model: string
}

export interface ApiError {
    error: string
    message?: string
}

export interface VideoResult {
    id: string
    title: string
    channel: string
    channel_id?: string | null
    url: string
    score?: number
    thumbnail?: string | null
    channel_thumbnail?: string | null
    tags?: string | null
    document?: string
    metadata?: Record<string, unknown>
    original_rank?: number
    rerank_position?: number
    llm_score?: number
    published_at?: string
    duration_seconds?: number
}

export interface SearchResponse {
    results: VideoResult[]
    count: number
    rerank?: Record<string, unknown>
}

export interface ChannelSummary {
    channel: string
    count: number
    channel_thumbnail?: string | null
    percent?: number
    watch_time?: string | null
}

export interface ChannelPage {
    channels: ChannelSummary[]
    total_videos: number
    distinct_channels: number
    total_available: number
    offset: number
    limit: number | null
    returned: number
    has_more: boolean
    sort: string
    q?: string | null
}

export interface ChannelVideosResponse {
    results: VideoResult[]
    count: number
    channel: string
}

export interface TopicSummary {
    id: number
    label: string
    size: number
    percent?: number
    top_keywords?: string[]
}

export interface TopicListResponse {
    clusters: TopicSummary[]
    count: number
    total: number
    generated_at?: string
    total_videos?: number
    noise_ratio?: number
}

export interface TopicDetailResponse {
    cluster?: TopicSummary | null
    cluster_id: number
    videos: TopicVideo[]
    count: number
}

export interface TopicVideo {
    id: string
    title: string
    channel: string
    url: string
    thumbnail?: string | null
    published_at?: string | null
    duration_seconds?: number | null
}
