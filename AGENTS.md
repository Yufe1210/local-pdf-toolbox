# Repository maintenance rules

## Documentation synchronization

- `docs/requirements.md` is the source of truth for confirmed product requirements and scope.
- `docs/implementation-plan.md` records architecture, milestones, current status, and acceptance criteria.
- `docs/release-and-update.md` records packaging, installer, update, versioning, and release decisions.
- Update the relevant documents in the same commit whenever behavior, scope, feature status, packaging, supported platforms, privacy behavior, versioning, or update behavior changes.
- Keep the status tables accurate: do not mark planned work as completed before it has been implemented and verified.
- Keep the root `README.md` concise and link to the detailed documents instead of duplicating them.

## Git workflow

- Work on a focused branch for non-trivial features; use `feature/<name>`, `fix/<name>`, or `docs/<name>`.
- Make small commits with Conventional Commit-style subjects such as `feat:`, `fix:`, `docs:`, `test:`, `build:`, and `chore:`.
- Do not commit `.venv`, caches, PyInstaller `build/` or `dist/`, release installers, temporary PDFs, or generated previews.
- Before committing code, run `uv run pytest` and any packaging or rendering checks relevant to the change.
- Before committing documentation-only changes, run `git diff --check`.
