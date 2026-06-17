'use client'

import { type ComponentProps, useEffect, useState } from 'react'

import { ZoomableImage } from '@/components/chat/zoomable-image'
import { filePathFromMediaPath, mediaExternalUrl } from '@/lib/media'

// Turn a raw image reference (http(s)/data URL, or a local filesystem path the
// agent wrote to $CLIO_HOME/cache/images) into something an <img> can actually
// load in the Electron renderer. A bare path resolves against the app origin
// and 404s, so we read it into a data URL via the desktop bridge (the same
// path markdown media uses), falling back to file:// when the bridge is absent.
async function resolveImageSrc(path: string): Promise<string> {
  if (/^(?:https?|data):/i.test(path)) {
    return path
  }

  if (!window.clioDesktop?.readFileDataUrl) {
    return mediaExternalUrl(path)
  }

  try {
    return await window.clioDesktop.readFileDataUrl(filePathFromMediaPath(path))
  } catch {
    return mediaExternalUrl(path)
  }
}

type ResolvedImageProps = Omit<ComponentProps<typeof ZoomableImage>, 'src'> & { src: string }

/**
 * ZoomableImage that accepts a raw path/URL and resolves it to a loadable src.
 * Remote/data URLs render immediately; local paths resolve asynchronously.
 */
export function ResolvedImage({ src, ...props }: ResolvedImageProps) {
  const [resolved, setResolved] = useState(() => (/^(?:https?|data):/i.test(src) ? src : ''))

  useEffect(() => {
    let active = true

    if (/^(?:https?|data):/i.test(src)) {
      setResolved(src)

      return
    }

    void resolveImageSrc(src).then(next => {
      if (active) {
        setResolved(next)
      }
    })

    return () => {
      active = false
    }
  }, [src])

  if (!resolved) {
    return null
  }

  return <ZoomableImage src={resolved} {...props} />
}
