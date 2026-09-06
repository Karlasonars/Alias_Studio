"""The stage chains (E20 / D-19): which stages run, in what order, per mode.

Two chains over one machine. `jobs/queue.run_stages` takes its stage list
as a parameter and never names a stage; what it needs from a chain is the
ORDER, so the checkpoint contract (§4) — `artifacts_ok`, the
`upstream_stale` cascade, resume, cancel at a boundary — applies to any
list it is handed. The stories chain is therefore a second list, not the
clips chain with five stages skipped: a skip mechanism does not exist, and
every stage after `ingest` raises `prior-stage-missing` when a prior it
reads is absent, so skipping would still need every stage the story chain
needs and add a mechanism on top.

This module is the light-import copy of the truth: `cli._stages(mode)`
builds the instances (behind the torch import tax), and a test pins the
two equal for every chain. Everything that enumerates stages WITHOUT
running them — the resume picker, `--from-stage`'s choices, the
diagnostic bundle, the hardware profile, the progress deck — reads from
here, so a stage that joins a chain shows up everywhere in one edit.

Nothing here imports the package: config.py reads it to validate a
job's mode and hardware_profile.py to size its estimate, and both sit
below every stage.
"""

from __future__ import annotations

DEFAULT_MODE = "clips"

CLIPS_CHAIN: tuple[str, ...] = (
    "ingest", "asr", "diarize", "events", "candidates", "score", "camera", "render",
)

#: mode → the stages that run for it, in order. A mode not in this table
#: does not exist; `chain_for` refuses it rather than guessing a chain.
CHAINS: dict[str, tuple[str, ...]] = {
    "clips": CLIPS_CHAIN,
}

#: Every stage name any chain runs, first appearance first — what a
#: choice list or an allowlist wants when it must accept any job's stages.
ALL_STAGES: tuple[str, ...] = tuple(
    dict.fromkeys(name for chain in CHAINS.values() for name in chain)
)


def chain_for(mode: str | None) -> tuple[str, ...]:
    """The stage names for one mode. A missing or empty mode is the clips
    chain: every settings snapshot written before the field existed lacks
    it, and those jobs are clips jobs (§4 rule 3, applied to the chain
    itself). An unknown mode raises — running the wrong chain silently
    would be worse than a described failure."""
    key = mode or DEFAULT_MODE
    try:
        return CHAINS[key]
    except KeyError:
        raise ValueError(f"unknown mode {key!r}; known: {sorted(CHAINS)}") from None
