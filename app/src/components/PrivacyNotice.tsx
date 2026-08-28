import Markdown from './Markdown'
import privacyText from '../../../PRIVACY.md?raw'

/**
 * Settings → Privacy. The text is PRIVACY.md at the repository root,
 * inlined at build time via Vite's ?raw import — the app can only ever
 * show the exact file that ships in the repo, so the two cannot drift
 * (one source; the pytest guard keeps that source complete). Rendering
 * lives in Markdown.tsx, shared with the About screen since T-18.
 */
export default function PrivacyNotice() {
  return (
    <div className="privacy-doc">
      <Markdown text={privacyText} />
    </div>
  )
}
