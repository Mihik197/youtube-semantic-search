import { useMemo, useState } from 'react'
import clsx from 'clsx'
import { channelInitial, fallbackAvatarColor } from '../../utils/video'

interface ChannelAvatarProps {
  name?: string
  thumbnail?: string | null
  channelId?: string | null
  size?: 'sm' | 'md'
  link?: string | null
  className?: string
  wrapperClassName?: string
  imgClassName?: string
}

export function ChannelAvatar({
  name,
  thumbnail,
  channelId,
  size = 'md',
  link,
  className,
  wrapperClassName,
  imgClassName,
}: ChannelAvatarProps) {
  const [errored, setErrored] = useState(false)
  const displayName = name ?? ''
  const initial = useMemo(() => channelInitial(displayName), [displayName])
  const color = useMemo(() => fallbackAvatarColor(initial), [initial])

  const dimensions = size === 'sm' ? 20 : 24

  const avatarImg = !errored && thumbnail ? (
    <img
      src={thumbnail}
      alt={`${displayName || 'Channel'} avatar`}
      className={clsx('channel-avatar', imgClassName)}
      loading="lazy"
      onError={() => setErrored(true)}
      style={{ width: dimensions, height: dimensions }}
    />
  ) : (
    <span
      className={clsx('channel-avatar avatar-fallback', className)}
      style={{
        background: `var(--avatar-bg, ${color})`,
        width: dimensions,
        height: dimensions,
        fontSize: size === 'sm' ? '0.65rem' : '0.75rem',
      }}
      aria-hidden="true"
    >
      {initial}
    </span>
  )

  const href = link
    ? link
    : channelId
    ? `https://www.youtube.com/channel/${channelId}`
    : displayName
    ? `https://www.youtube.com/results?search_query=${encodeURIComponent(displayName)}`
    : undefined

  if (href) {
    return (
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className={clsx('channel-avatar-link', wrapperClassName)}
        title={displayName}
      >
        {avatarImg}
      </a>
    )
  }

  return <span className={clsx('channel-avatar-wrapper', wrapperClassName)}>{avatarImg}</span>
}
