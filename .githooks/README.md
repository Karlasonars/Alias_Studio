# .githooks

Git hooks that live in the repository instead of in `.git/hooks`, so a fresh
clone gets them and an agent working in a new worktree does not silently lose
them.

## Enable

Once per clone:

```bash
git config core.hooksPath .githooks
```

On Windows, run it from Git Bash or PowerShell — either works; git resolves the
path itself.

## What runs

| Hook | Runs | Takes |
|---|---|---|
| `pre-push` | `ruff check` and `tests/test_house_rules.py` | ~15 s |

Not the full test suite. A hook slow enough to be annoying gets bypassed, and a
bypassed hook protects nothing — the full suite is CI's job (`guards.yml`).

## Bypass

```bash
git push --no-verify
```

Legitimate when you are pushing docs from a machine with no Python env, or when
you already know CI will catch what you are fixing next.

**Not** legitimate as a way past a failing guard. If a guard fails, the change
is wrong — not the guard. `CLAUDE.md` §5 is explicit that editing a guard test
to make it pass is the one change that is never correct.
