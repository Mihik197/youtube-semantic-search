import type { VideoResult } from '../types/api'

export function scoreBadgeClass(score?: number): string {
    if (typeof score !== 'number') {
        return 'bg-secondary'
    }
    if (score >= 0.8) return 'bg-success'
    if (score >= 0.6) return 'bg-primary'
    if (score >= 0.4) return 'bg-info'
    if (score >= 0.2) return 'bg-warning'
    return 'bg-secondary'
}

export function channelInitial(name?: string): string {
    const letter = (name?.trim().charAt(0) ?? '').toUpperCase()
    if (letter) return letter
    return '?'
}

export function fallbackAvatarColor(letter: string): string {
    const palette = ['#6f42c1', '#d63384', '#fd7e14', '#20c997', '#0d6efd', '#6610f2', '#198754', '#e83e8c', '#fd7e14', '#0dcaf0']
    const code = letter.charCodeAt(0)
    const index = Number.isFinite(code) ? code % palette.length : 0
    return palette[index]
}

export function toVideoResult(video: VideoResult): VideoResult {
    return {
        ...video,
        score: typeof video.score === 'number' ? video.score : 0,
    }
}
