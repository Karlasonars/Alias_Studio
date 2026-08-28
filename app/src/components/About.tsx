import { useEffect, useState } from 'react'
import { getVersion } from '@tauri-apps/api/app'
import { openUrl } from '@tauri-apps/plugin-opener'
import Markdown from './Markdown'
import { buildInfo, type BuildInfo } from '../buildInfo'
import licenseText from '../../../LICENSE?raw'
import vendoredText from '../../../VENDORED-LICENSES.md?raw'
import readmeText from '../../../README.md?raw'

/**
 * Settings → About (E16-F03 / T-18). AGPL-3.0 in the UI, built on
 * T-17's one-source pattern: the licence is LICENSE itself, the
 * third-party record is VENDORED-LICENSES.md itself, and the
 * modification statement AGPL requires is README's "What this build
 * adds" section — all inlined at build time, nothing retyped to drift.
 *
 * The version number comes from getVersion() (tauri.conf.json, its one
 * defined place) and the commit from buildInfo (baked by vite.config.ts
 * at build time), because "the source of the version you are running"
 * means the commit in your build, not whatever main holds today. A
 * build without git (a source archive) has no commit to link, and the
 * screen says so instead of pointing at a URL that may not exist.
 */

const REPO = 'https://github.com/Karlasonars/Alias_Studio'
const UPSTREAM = 'https://github.com/Blueturboguy07/publikclip'

/** README's modification statement, extracted by heading so the README
 * stays the single author of it. Empty if the heading is ever renamed —
 * which the About test treats as a failure, not a quiet omission. */
export function modificationsSection(): string {
  const start = readmeText.indexOf('## What this build adds')
  if (start < 0) return ''
  const rest = readmeText.slice(start)
  const next = rest.indexOf('\n## ')
  return next > 0 ? rest.slice(0, next) : rest
}

function Ext({ url, children }: { url: string; children: React.ReactNode }) {
  return (
    <button className="md-link" title={url} onClick={() => openUrl(url).catch(() => {})}>
      {children}
    </button>
  )
}

export default function About({ build = buildInfo }: { build?: BuildInfo }) {
  const [version, setVersion] = useState<string | null>(null)

  useEffect(() => {
    getVersion()
      .then(setVersion)
      .catch(() => setVersion(null))
  }, [])

  const shortCommit = build.commit.slice(0, 12)
  const exactSourceUrl = build.tag
    ? `${REPO}/releases/tag/${build.tag}`
    : `${REPO}/tree/${build.commit}`

  return (
    <div className="privacy-doc about-doc">
      <h1>Alias Studio</h1>
      <p className="about-version mono">
        {version ? `version ${version}` : 'version unknown'}
        {build.commit
          ? ` · commit ${shortCommit}${build.dirty ? ' (with local changes)' : ''}`
          : ' · local build — no commit recorded'}
      </p>

      <p>
        Free software under the <strong>GNU AGPL-3.0</strong>: you may use, study,
        modify and share it, and anyone who distributes it — this build included —
        must offer the matching source.
      </p>

      {build.commit ? (
        <p>
          <Ext url={exactSourceUrl}>
            Source for exactly this build{build.tag ? ` (${build.tag})` : ` (commit ${shortCommit})`}
          </Ext>{' '}
          · <Ext url={`${REPO}/releases`}>all releases</Ext> ·{' '}
          <Ext url={REPO}>repository</Ext>
          {build.dirty && (
            <span className="about-dirty">
              {' '}
              — this build carries uncommitted local changes on top of that commit.
            </span>
          )}
        </p>
      ) : (
        <p>
          This build was made without git, so no commit is recorded — the source
          that corresponds to it is the source tree it was built from. Released
          versions live at <Ext url={`${REPO}/releases`}>{REPO.replace('https://', '')}/releases</Ext>,
          each with its own source archive.
        </p>
      )}

      <p>
        Alias Studio is a modified build of{' '}
        <Ext url={UPSTREAM}>publikclip</Ext> (AGPL-3.0). The changes are stated
        below, as the licence requires. The app is not a network service; if it
        ever becomes one, the same source offer extends to that use (AGPL §13).
      </p>

      <Markdown text={modificationsSection()} />

      <details className="about-details">
        <summary>Third-party code, models and fonts</summary>
        <Markdown text={vendoredText} />
      </details>

      <details className="about-details">
        <summary>GNU Affero General Public License, version 3 — full text</summary>
        <pre className="about-license">{licenseText}</pre>
      </details>
    </div>
  )
}
