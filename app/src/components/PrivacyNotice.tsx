import { Fragment } from 'react'
import privacyText from '../../../PRIVACY.md?raw'

/**
 * Settings → Privacy. The text is PRIVACY.md at the repository root,
 * inlined at build time via Vite's ?raw import — the app can only ever
 * show the exact file that ships in the repo, so the two cannot drift
 * (one source; the pytest guard keeps that source complete). The
 * renderer below covers only the markdown this document uses: headings,
 * paragraphs, bullets and **bold** — anything fancier belongs in the
 * document only if this renderer learns it first.
 */

function inline(text: string, key: number) {
  const parts = text.split(/\*\*(.+?)\*\*/g)
  return (
    <Fragment key={key}>
      {parts.map((part, i) => (i % 2 === 1 ? <strong key={i}>{part}</strong> : part))}
    </Fragment>
  )
}

export default function PrivacyNotice() {
  const blocks: React.ReactNode[] = []
  let paragraph: string[] = []
  let bullets: string[] = []

  const flush = () => {
    if (paragraph.length) {
      blocks.push(<p key={blocks.length}>{inline(paragraph.join(' '), 0)}</p>)
      paragraph = []
    }
    if (bullets.length) {
      blocks.push(
        <ul key={blocks.length}>
          {bullets.map((b, i) => (
            <li key={i}>{inline(b, 0)}</li>
          ))}
        </ul>
      )
      bullets = []
    }
  }

  for (const line of privacyText.split('\n')) {
    const trimmed = line.trim()
    if (!trimmed) {
      flush()
    } else if (trimmed.startsWith('### ')) {
      flush()
      blocks.push(<h3 key={blocks.length}>{inline(trimmed.slice(4), 0)}</h3>)
    } else if (trimmed.startsWith('## ')) {
      flush()
      blocks.push(<h2 key={blocks.length}>{inline(trimmed.slice(3), 0)}</h2>)
    } else if (trimmed.startsWith('# ')) {
      flush()
      blocks.push(<h1 key={blocks.length}>{inline(trimmed.slice(2), 0)}</h1>)
    } else if (trimmed.startsWith('- ')) {
      if (paragraph.length) flush()
      bullets.push(trimmed.slice(2))
    } else if (bullets.length) {
      // markdown continuation line of the previous bullet
      bullets[bullets.length - 1] += ' ' + trimmed
    } else {
      paragraph.push(trimmed)
    }
  }
  flush()

  return <div className="privacy-doc">{blocks}</div>
}
