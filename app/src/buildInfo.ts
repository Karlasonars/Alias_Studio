/** The build's identity, baked in by vite.config.ts from git at build
 * time. This module is the ONLY reader of the __BUILD_*__ defines, and
 * the app's version number is deliberately NOT here: the version has one
 * defined place (tauri.conf.json) and one reader (getVersion() at
 * runtime) — a second copy would drift, and a guard in
 * pipeline/tests/test_vendored_licenses.py fails if the version value
 * ever appears as a literal in app/src.
 *
 * An empty commit means git was not available when the bundle was built
 * — someone building from a source archive rather than a clone. That is
 * a legitimate state the About screen must describe, not hide: their
 * source offer is the tree they built from. */
export interface BuildInfo {
  commit: string
  tag: string
  dirty: boolean
}

declare const __BUILD_COMMIT__: string
declare const __BUILD_TAG__: string
declare const __BUILD_DIRTY__: boolean

export const buildInfo: BuildInfo = {
  commit: typeof __BUILD_COMMIT__ === 'undefined' ? '' : __BUILD_COMMIT__,
  tag: typeof __BUILD_TAG__ === 'undefined' ? '' : __BUILD_TAG__,
  dirty: typeof __BUILD_DIRTY__ === 'undefined' ? false : __BUILD_DIRTY__
}
