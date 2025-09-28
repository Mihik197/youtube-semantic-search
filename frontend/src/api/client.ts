import type {
    AppConfig,
    ChannelPage,
    ChannelVideosResponse,
    SearchResponse,
    TopicDetailResponse,
    TopicListResponse,
} from '../types/api'

const JSON_HEADERS = {
    'Content-Type': 'application/json',
}

async function handleResponse<T>(response: Response): Promise<T> {
    if (!response.ok) {
        let message = `Request failed with status ${response.status}`
        try {
            const data = await response.json()
            if (typeof data === 'object' && data && 'error' in data && typeof data.error === 'string') {
                message = data.error
            }
        } catch (err) {
            // ignore json parsing errors
        }
        throw new Error(message)
    }
    return (await response.json()) as T
}

export async function fetchAppConfig(signal?: AbortSignal): Promise<AppConfig> {
    const response = await fetch('/app-config', { signal })
    return handleResponse<AppConfig>(response)
}

export async function searchVideos(query: string, numResults: number, signal?: AbortSignal): Promise<SearchResponse> {
    const response = await fetch('/search', {
        method: 'POST',
        headers: JSON_HEADERS,
        body: JSON.stringify({ query, num_results: numResults }),
        signal,
    })
    return handleResponse<SearchResponse>(response)
}

export interface ChannelPageParams {
    sort: string
    limit: number
    offset: number
    q?: string
}

export async function fetchChannelPage(params: ChannelPageParams, signal?: AbortSignal): Promise<ChannelPage> {
    const searchParams = new URLSearchParams()
    searchParams.set('sort', params.sort)
    searchParams.set('limit', String(params.limit))
    searchParams.set('offset', String(params.offset))
    if (params.q) {
        searchParams.set('q', params.q)
    }
    const response = await fetch(`/channels?${searchParams.toString()}`, { signal })
    return handleResponse<ChannelPage>(response)
}

export async function fetchChannelVideos(channel: string, signal?: AbortSignal): Promise<ChannelVideosResponse> {
    const response = await fetch(`/channel_videos?channel=${encodeURIComponent(channel)}`, { signal })
    return handleResponse<ChannelVideosResponse>(response)
}

export interface TopicListParams {
    sort: string
    includeNoise: boolean
}

export async function fetchTopics(params: TopicListParams, signal?: AbortSignal): Promise<TopicListResponse> {
    const searchParams = new URLSearchParams()
    searchParams.set('sort', params.sort)
    searchParams.set('include_noise', String(params.includeNoise))
    const response = await fetch(`/topics?${searchParams.toString()}`, { signal })
    return handleResponse<TopicListResponse>(response)
}

export async function fetchTopicDetail(clusterId: number, signal?: AbortSignal): Promise<TopicDetailResponse> {
    const response = await fetch(`/topics/${clusterId}`, { signal })
    return handleResponse<TopicDetailResponse>(response)
}
