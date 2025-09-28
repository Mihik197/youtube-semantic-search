import { useEffect, useMemo, useState } from 'react'
import { Button, Modal, Nav, Tab } from 'react-bootstrap'
import type { VideoResult } from '../types/api'

interface VideoModalProps {
  video: VideoResult | null
  onHide: () => void
}

export function VideoModal({ video, onHide }: VideoModalProps) {
  const [copyState, setCopyState] = useState<'idle' | 'copied-text' | 'copied-meta'>('idle')

  useEffect(() => {
    if (!video) {
      setCopyState('idle')
    }
  }, [video])

  const metadataText = useMemo(() => {
    if (!video?.metadata) return '{}'
    try {
      return JSON.stringify(video.metadata, null, 2)
    } catch (error) {
      return '{}'
    }
  }, [video])

  const handleCopy = async (content: string, type: 'text' | 'meta') => {
    if (!content) return
    try {
      await navigator.clipboard.writeText(content)
      setCopyState(type === 'text' ? 'copied-text' : 'copied-meta')
      window.setTimeout(() => setCopyState('idle'), 2000)
    } catch (error) {
      console.error('Could not copy text to clipboard', error)
    }
  }

  const videoId = video?.id ?? ''
  const embedUrl = videoId ? `https://www.youtube.com/embed/${videoId}` : undefined

  return (
    <Modal show={Boolean(video)} onHide={onHide} centered dialogClassName="modal-xl" aria-labelledby="videoModalLabel">
      <Modal.Header closeButton>
        <Modal.Title id="videoModalLabel">{video?.title ?? 'Video Details'}</Modal.Title>
      </Modal.Header>
      <Modal.Body>
        {embedUrl ? (
          <div className="ratio ratio-16x9 mb-3">
            <iframe id="videoIframe" src={embedUrl} allowFullScreen title={video?.title ?? 'Video preview'} />
          </div>
        ) : null}
        <Tab.Container defaultActiveKey="info">
          <Nav variant="tabs" className="mb-3">
            <Nav.Item>
              <Nav.Link eventKey="info">
                <i className="bi bi-info-circle me-1" /> Information
              </Nav.Link>
            </Nav.Item>
            <Nav.Item>
              <Nav.Link eventKey="embedding">
                <i className="bi bi-file-text me-1" /> Embedding Text
              </Nav.Link>
            </Nav.Item>
            <Nav.Item>
              <Nav.Link eventKey="metadata">
                <i className="bi bi-code-square me-1" /> Raw Metadata
              </Nav.Link>
            </Nav.Item>
          </Nav>
          <Tab.Content>
            <Tab.Pane eventKey="info">
              <table className="table table-hover">
                <tbody>
                  <tr>
                    <th className="w-25">Title</th>
                    <td>{video?.title}</td>
                  </tr>
                  <tr>
                    <th>Channel</th>
                    <td>{video?.channel}</td>
                  </tr>
                  <tr>
                    <th>YouTube ID</th>
                    <td>
                      <code>{videoId}</code>
                    </td>
                  </tr>
                  {video?.published_at ? (
                    <tr>
                      <th>Published</th>
                      <td>{new Date(video.published_at).toLocaleString()}</td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </Tab.Pane>
            <Tab.Pane eventKey="embedding">
              <div className="d-flex justify-content-end">
                <Button
                  size="sm"
                  variant="outline-secondary"
                  className="copy-button"
                  onClick={() => handleCopy(video?.document ?? '', 'text')}
                  disabled={!video?.document}
                >
                  <i className="bi bi-clipboard" />{' '}
                  {copyState === 'copied-text' ? 'Copied!' : 'Copy'}
                </Button>
              </div>
              <pre id="embeddingText" className="mt-3">
                {video?.document ?? 'No embedding text available.'}
              </pre>
            </Tab.Pane>
            <Tab.Pane eventKey="metadata">
              <div className="d-flex justify-content-end">
                <Button
                  size="sm"
                  variant="outline-secondary"
                  className="copy-button"
                  onClick={() => handleCopy(metadataText, 'meta')}
                  disabled={!video?.metadata}
                >
                  <i className="bi bi-clipboard" />{' '}
                  {copyState === 'copied-meta' ? 'Copied!' : 'Copy'}
                </Button>
              </div>
              <pre id="metadataJson" className="mt-3">
                {metadataText}
              </pre>
            </Tab.Pane>
          </Tab.Content>
        </Tab.Container>
      </Modal.Body>
      <Modal.Footer>
        {video?.url ? (
          <Button
            as="a"
            href={video.url}
            target="_blank"
            rel="noopener noreferrer"
            variant="danger"
            id="watchOnYouTube"
          >
            <i className="bi bi-youtube" /> Watch on YouTube
          </Button>
        ) : null}
        <Button variant="secondary" onClick={onHide}>
          Close
        </Button>
      </Modal.Footer>
    </Modal>
  )
}
