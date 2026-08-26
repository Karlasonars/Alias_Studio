import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../../api'
import type { EditContext, EditState } from '../../types'

/** The document: the edit being made, the context it is made against, and
 *  the single write path (persist). The two refs mirror the state so the
 *  player's rAF loop can read the latest values without re-subscribing —
 *  and they are assigned during render, deliberately, so they are never one
 *  frame behind the state they mirror. Move them into an effect and the
 *  preview plays against a stale edit with nothing going red. */
export function useClipEdit(jobId: string, clipIndex: number) {
  const [ctx, setCtx] = useState<EditContext | null>(null)
  const [edit, setEdit] = useState<EditState | null>(null)
  const [error, setError] = useState<string | null>(null)
  const editRef = useRef<EditState | null>(null)       // rAF reads latest edit
  editRef.current = edit
  const ctxRef = useRef<EditContext | null>(null)
  ctxRef.current = ctx

  const reload = useCallback(() => {
    api.editContext(jobId, clipIndex)
      .then((c) => {
        setCtx(c)
        setEdit(c.edit)
      })
      .catch((e) => setError(String(e)))
  }, [jobId, clipIndex])

  useEffect(reload, [reload])

  async function persist(next: EditState) {
    setEdit(next)
    await api.saveClipEdits(jobId, clipIndex, next)
  }

  return { ctx, edit, setEdit, error, setError, editRef, ctxRef, persist }
}
