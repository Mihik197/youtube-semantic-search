import clsx from 'clsx'
import type { VideoResult } from '../../types/api'
import { scoreBadgeClass } from '../../utils/video'
import { ChannelAvatar } from '../common/ChannelAvatar'

interface VideoCardProps {
  video: VideoResult
  onSelect: (video: VideoResult) => void
}

const PLACEHOLDER_THUMB = 'https://via.placeholder.com/480x360?text=No+Thumbnail'

export function VideoCard({ video, onSelect }: VideoCardProps) {
  const score = typeof video.score === 'number' ? video.score : undefined
  return (
    <div className="col video-card-wrapper">
      <div className="card video-card h-100">
        <div className="position-relative thumb-wrapper">
          <img
            src={video.thumbnail || PLACEHOLDER_THUMB}
            className="card-img-top"
            alt={video.title}
            loading="lazy"
          />
          {typeof score === 'number' && (
            <span className={clsx('score-badge', scoreBadgeClass(score))}>{score.toFixed(3)}</span>
          )}
        </div>
        <div className="card-body">
          <h5 className="card-title">{video.title}</h5>
          <p className="channel-name">
            <ChannelAvatar
              name={video.channel}
              thumbnail={video.channel_thumbnail}
              channelId={video.channel_id}
              size="sm"
            />
            <span>{video.channel || 'Unknown Channel'}</span>
          </p>
        </div>
        <div className="card-footer d-flex justify-content-between align-items-center">
          <button
            type="button"
            className="btn btn-sm btn-outline-primary"
            onClick={() => onSelect(video)}
            title="View video details"
          >
            <i className="bi bi-info-circle" /> Details
          </button>
          <a
            href={video.url}
            target="_blank"
            rel="noopener noreferrer"
            className="btn btn-sm btn-danger"
            title="Open in YouTube"
          >
            <i className="bi bi-youtube" /> Watch
          </a>
        </div>
      </div>
    </div>
  )
}
