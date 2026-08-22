"""Fixups for third-party bugs that only manifest on Windows. Imported once,
early, from cli.py — before any pipeline stage runs.
"""

from __future__ import annotations

import importlib
import inspect
import os
import sys
import warnings


def patch_speechbrain_lazy_import() -> None:
    """speechbrain's LazyModule.ensure_module is meant to raise a clean
    AttributeError whenever it's Python's own `inspect` module doing the
    introspecting, so that any unrelated inspect.stack()/getmodule() call
    elsewhere in the process (e.g. librosa's lazy_loader resolving an
    unrelated submodule) fails a plain hasattr() check instead of forcing a
    real import of an optional, often-missing integration such as
    speechbrain.integrations.k2_fsa.

    The guard checks `filename.endswith("/inspect.py")`, which never matches
    on Windows (backslash paths) — so it silently never fires there, and the
    real ImportError propagates instead, crashing whatever unrelated stage
    happened to call hasattr() on the lazy module (observed: librosa.load()
    in the diarize stage, triggered purely by inspect walking the stack).

    Reproduced against speechbrain 1.x. Fix: compare basenames instead of a
    hardcoded separator — this is otherwise a verbatim copy of the upstream
    method (speechbrain/utils/importutils.py, LazyModule.ensure_module).
    """
    try:
        from speechbrain.utils import importutils
    except ImportError:
        return

    def ensure_module(self, stacklevel: int):
        importer_frame = None
        try:
            importer_frame = inspect.getframeinfo(sys._getframe(stacklevel + 1))
        except AttributeError:
            warnings.warn(
                "Failed to inspect frame to check if we should ignore "
                "importing a module lazily. This relies on a CPython "
                "implementation detail, report an issue if you see this with "
                "standard Python and include your version number."
            )
        if importer_frame is not None and os.path.basename(importer_frame.filename) == "inspect.py":
            raise AttributeError()

        if self.lazy_module is None:
            try:
                if self.package is None:
                    self.lazy_module = importlib.import_module(self.target)
                else:
                    self.lazy_module = importlib.import_module(f".{self.target}", self.package)
            except Exception as e:
                raise ImportError(f"Lazy import of {self!r} failed") from e

        return self.lazy_module

    importutils.LazyModule.ensure_module = ensure_module


def apply_all() -> None:
    if os.name == "nt":
        patch_speechbrain_lazy_import()
