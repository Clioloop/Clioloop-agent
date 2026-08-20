type TerminalReader = (start: number, count: number) => Record<string, unknown>
type TerminalCloser = (taskId?: string) => boolean

let reader: TerminalReader | null = null
let closer: TerminalCloser | null = null

export function registerDesktopTerminalBridge(next: {
  read: TerminalReader
  close: TerminalCloser
}): () => void {
  reader = next.read
  closer = next.close

  return () => {
    if (reader === next.read) {
      reader = null
    }

    if (closer === next.close) {
      closer = null
    }
  }
}

export function readDesktopTerminal(start = 0, count = 12_000): Record<string, unknown> {
  return reader?.(start, count) ?? { available: false, text: '', start: 0, count: 0 }
}

export function closeDesktopTerminal(taskId = ''): boolean {
  return closer?.(taskId) ?? false
}
