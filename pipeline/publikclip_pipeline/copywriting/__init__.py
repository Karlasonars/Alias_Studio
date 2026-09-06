"""Copywriting engines: titles, descriptions, hooks — and moment labels.

All of them turn an already-cut clip into something a viewer clicks and
stays with. Titles, descriptions and hooks are deliberately OUTSIDE the
stage pipeline — they are cheap, re-runnable on demand, and a user
regenerating a title should never invalidate a render: a title is
metadata beside the file.

Labels (labels.py, E18-F04) are the one exception, for the same reason
inverted: a moment's label is burned into the ranking video's pixels, so
it IS the file. render/ranking.py calls that engine from inside the
render stage, once per moment, and keeps the result on the render
checkpoint — generated once, reused verbatim by every later render,
never regenerated, and never part of the stage's fingerprint: an output
of the render, not a setting of it.
"""
