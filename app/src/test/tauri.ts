/* The Tauri boundary, for tests. There is no Tauri runtime under vitest:
 * the real `invoke`/`listen` come from @tauri-apps/api and reach a Rust
 * process that does not exist here. Test files mock those two modules
 * (plus plugin-opener) with the fakes below — a dispatcher keyed by
 * command name, and an event bus tests can emit into. Product code is
 * untouched: the mock happens at the module seam vitest already owns.
 *
 * Deliberately NOT here: anything that fakes behaviour. A test declares
 * exactly the commands it expects via `commands`; an unexpected command
 * rejects loudly instead of returning undefined into product code.
 */
import { vi } from 'vitest'

type Handler = (event: { payload: unknown }) => void

export const commands: Record<string, (args?: Record<string, unknown>) => unknown> = {}
const listeners: Record<string, Handler[]> = {}

export const invokeMock = vi.fn(async (cmd: string, args?: Record<string, unknown>) => {
  const handler = commands[cmd]
  if (!handler) throw new Error(`no test handler for Tauri command '${cmd}'`)
  return handler(args)
})

export const listenMock = vi.fn(async (name: string, handler: Handler) => {
  ;(listeners[name] ??= []).push(handler)
  return () => {
    listeners[name] = (listeners[name] ?? []).filter((h) => h !== handler)
  }
})

/** Deliver an event as the Rust shell would (app.emit → every listener). */
export function emit(name: string, payload: unknown): void {
  for (const handler of listeners[name] ?? []) handler({ payload })
}

export function callsTo(cmd: string): number {
  return invokeMock.mock.calls.filter(([c]) => c === cmd).length
}

/** Fresh boundary per test: no commands, no listeners, zeroed call log. */
export function resetTauri(): void {
  for (const key of Object.keys(commands)) delete commands[key]
  for (const key of Object.keys(listeners)) delete listeners[key]
  invokeMock.mockClear()
  listenMock.mockClear()
}

/** The commands App.tsx fires on mount, answered with a quiet idle app.
 * update_checks_enabled answers false so the launch update check (T-16)
 * stops before importing the updater plugin — tests that want the check
 * override it and mock the plugin module themselves. */
export function idleAppCommands(): void {
  commands.update_checks_enabled = () => false
  commands.get_setup_state = () => ({ has_gemini_key: true, onboarded: true })
  commands.list_job_dirs = () => []
  commands.ig_status = () => ({ connected: false })
  commands.get_hardware_profile = () => null
  commands.queue_state = () => ({
    jobs: [],
    paused: false,
    active_job_id: null,
    ready: true
  })
}
