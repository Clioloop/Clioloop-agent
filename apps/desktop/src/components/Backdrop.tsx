import { Leva, useControls } from 'leva'
import { type CSSProperties, useEffect, useState } from 'react'

const BLEND_MODES = [
  'normal',
  'multiply',
  'screen',
  'overlay',
  'darken',
  'lighten',
  'color-dodge',
  'color-burn',
  'hard-light',
  'soft-light',
  'difference',
  'exclusion',
  'hue',
  'saturation',
  'color',
  'luminosity'
] as const

type BlendMode = (typeof BLEND_MODES)[number]
const assetPath = (path: string) => `${import.meta.env.BASE_URL}${path.replace(/^\/+/, '')}`

export function Backdrop() {
  const [controlsOpen, setControlsOpen] = useState(false)

  useEffect(() => {
    if (!import.meta.env.DEV) {
      return
    }

    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null

      const editing =
        target?.isContentEditable ||
        target instanceof HTMLInputElement ||
        target instanceof HTMLTextAreaElement ||
        target instanceof HTMLSelectElement

      if (editing || event.repeat || event.altKey || event.ctrlKey || event.metaKey) {
        return
      }

      if (event.shiftKey && event.code === 'KeyY') {
        setControlsOpen(open => !open)
      }
    }

    window.addEventListener('keydown', onKeyDown)

    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])

  const shape = useControls(
    'UI / Shape',
    { radiusScalar: { value: 0.2, min: 0, max: 2, step: 0.1, label: 'radius scalar' } },
    { collapsed: true }
  )

  useEffect(() => {
    document.documentElement.style.setProperty('--radius-scalar', String(shape.radiusScalar))
  }, [shape.radiusScalar])

  const statue = useControls(
    'Backdrop / Statue',
    {
      enabled: { value: true, label: 'on' },
      opacity: { value: 0.025, min: 0, max: 1, step: 0.005 },
      blendMode: { value: 'difference' as BlendMode, options: BLEND_MODES, label: 'blend' },
      invert: { value: true, label: 'invert color' },
      saturate: { value: 1, min: 0, max: 3, step: 0.05, label: 'saturate' },
      brightness: { value: 1, min: 0, max: 2, step: 0.05, label: 'brightness' },
      objectPosition: {
        value: 'top left',
        options: ['top left', 'top right', 'bottom left', 'bottom right', 'center', 'top', 'bottom', 'left', 'right'],
        label: 'position'
      },
      scale: { value: 160, min: 100, max: 300, step: 5, label: 'height (dvh)' }
    },
    { collapsed: true }
  )

  return (
    <>
      <Leva collapsed hidden={!import.meta.env.DEV || !controlsOpen} titleBar={{ title: 'backdrop', drag: true }} />

      <video
        aria-hidden
        autoPlay
        className="pointer-events-none fixed inset-0 z-0 h-dvh w-dvw object-cover"
        loop
        muted
        playsInline
        poster={assetPath('brand/banner.png')}
        preload="metadata"
      >
        <source src={assetPath('brand/backgroundvideoloop.mp4')} type="video/mp4" />
      </video>

      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 z-1"
        style={{
          background:
            'linear-gradient(135deg, color-mix(in srgb, var(--ui-bg-chrome) 82%, transparent), rgba(18, 3, 33, 0.68) 44%, rgba(6, 30, 36, 0.78)), radial-gradient(ellipse at 12% 0%, rgba(196, 181, 253, 0.24), transparent 44%), radial-gradient(ellipse at 86% 100%, rgba(45, 212, 191, 0.15), transparent 48%)'
        }}
      />

      {statue.enabled && (
        <div
          aria-hidden
          className="pointer-events-none fixed inset-0 z-2"
          style={{
            mixBlendMode: 'screen',
            opacity: Math.max(statue.opacity, 0.055)
          }}
        >
          <img
            alt=""
            className="w-auto min-w-dvw object-cover"
            fetchPriority="low"
            src={assetPath('ds-assets/filler-bg0.jpg')}
            style={{
              height: `${statue.scale}dvh`,
              objectPosition: statue.objectPosition,
              filter: `invert(calc(${statue.invert ? 1 : 0} * var(--backdrop-invert-mul, 1))) saturate(${statue.saturate}) brightness(${statue.brightness})`
            }}
          />
        </div>
      )}
    </>
  )
}
