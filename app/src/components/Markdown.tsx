import { Fragment } from 'react'
import { openUrl } from '@tauri-apps/plugin-opener'

/**
 * The repo-document renderer, factored out of PrivacyNotice when the
 * About screen (T-18) needed the same one-source pattern for documents
 * that use tables and links (VENDORED-LICENSES.md, README's
 * modifications section). It covers exactly the markdown those documents
 * use — headings, paragraphs, bullets, **bold**, [links](url) and pipe
 * tables — and nothing more: anything fancier belongs in a document only
 * if this renderer learns it first.
 *
 * Links open through the opener plugin, never as <a href>: a real anchor
 * would navigate the Tauri webview away from the app.
 */

const LINK = /\[([^\]]+)\]\(([^)]+)\)/g

function inline(text: string, key: number) {
  const nodes: React.ReactNode[] = []
  let last = 0
  let n = 0
  for (const m of text.matchAll(LINK)) {
    if (m.index > last) nodes.push(bold(text.slice(last, m.index), n++))
    const url = m[2]
    nodes.push(
      <button
        key={n++}
        className="md-link"
        title={url}
        onClick={() => openUrl(url).catch(() => {})}
      >
        {m[1]}
      </button>
    )
    last = m.index + m[0].length
  }
  if (last < text.length) nodes.push(bold(text.slice(last), n++))
  return <Fragment key={key}>{nodes}</Fragment>
}

function bold(text: string, key: number) {
  const parts = text.split(/\*\*(.+?)\*\*/g)
  return (
    <Fragment key={key}>
      {parts.map((part, i) => (i % 2 === 1 ? <strong key={i}>{part}</strong> : part))}
    </Fragment>
  )
}

function cells(row: string): string[] {
  return row
    .trim()
    .replace(/^\||\|$/g, '')
    .split('|')
    .map((c) => c.trim())
}

export default function Markdown({ text }: { text: string }) {
  const blocks: React.ReactNode[] = []
  let paragraph: string[] = []
  let bullets: string[] = []
  let table: string[] = []

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
    if (table.length) {
      const [head, ...body] = table
      blocks.push(
        <div className="md-table-scroll" key={blocks.length}>
          <table>
            <thead>
              <tr>
                {cells(head).map((c, i) => (
                  <th key={i}>{inline(c, 0)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {body.map((row, r) => (
                <tr key={r}>
                  {cells(row).map((c, i) => (
                    <td key={i}>{inline(c, 0)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )
      table = []
    }
  }

  for (const line of text.split('\n')) {
    const trimmed = line.trim()
    if (trimmed.startsWith('|')) {
      if (paragraph.length || bullets.length) flush()
      if (!/^\|[\s\-:|]+\|$/.test(trimmed)) table.push(trimmed) // skip the |---| separator
    } else if (!trimmed) {
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
      if (paragraph.length || table.length) flush()
      bullets.push(trimmed.slice(2))
    } else if (bullets.length) {
      // markdown continuation line of the previous bullet
      bullets[bullets.length - 1] += ' ' + trimmed
    } else {
      if (table.length) flush()
      paragraph.push(trimmed)
    }
  }
  flush()

  return <>{blocks}</>
}
