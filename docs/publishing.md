# Publishing the repository

Run Git commands from the project folder containing `app/` and the README, not its parent folder. This is an update to the existing [Artint repository](https://github.com/varunsidr/Artint); no new repository or replacement remote is needed. Review the [unreleased changelog](../CHANGELOG.md), source and synthetic screenshots before pushing. The real library and generated files stay on your computer.

## Review and validate

These commands are instructions for the person publishing; documentation preparation does not execute a commit, push, tag, release or image publication.

```powershell
git status --short
git remote get-url origin
git diff --check
.\.venv\Scripts\python.exe -m pip check
$env:RUN_BROWSER_TESTS = '1'
.\.venv\Scripts\python.exe -m pytest -q
Remove-Item Env:RUN_BROWSER_TESTS
```

The expected remote is `https://github.com/varunsidr/Artint.git`. Check `git branch --show-current` before choosing the destination branch. If Git identity is missing, configure your own name and email locally; a GitHub-provided private email is optional. Repository preparation does not change Git author or authentication settings.

The latest Windows checkpoint is 286 passed with the opt-in live-server installation test skipped. The research/gold-authoring tools have separate targeted Ubuntu/WSL2 checks, not a full fresh-platform revalidation. Use `scripts/validate_native.py` for a disposable installation/server check. `scripts/validate_container.py` needs a running Docker engine and uses its own temporary Compose project. See [validation](validation.md) for earlier platform checks and later changes that still need revalidation. Source can be reviewed and pushed while explicitly marked work in progress; a release requires its own completed scope and verification.

## Stage and push the reviewed update

```powershell
git add .
git diff --cached --check
git diff --cached --stat
git diff --cached --name-only
git diff --cached
```

Inspect the staged paths and patch, including newly added Docker, review tooling, documentation and synthetic image files. Then commit and push when the staged result is ready:

```powershell
git commit -m "Add portable setup, extraction review tooling and general analytics"
git push origin main
```

`data/`, `output/`, `.venv/`, local environment files, Streamlit secrets, database sidecars, and logs are excluded. Keep public screenshots in `docs/images/` and use synthetic content there. Avoid `git add -f` for ignored files. Downloaded article text, PDFs, full backups, local evaluation caches, and API keys do not belong in the public repository.

The updated workflow defines Windows/Python 3.13, Ubuntu/Python 3.13 and disposable Docker jobs. It runs on pushes, pull requests and manual dispatch. Actions are pinned to release commits; jobs exercise browser policies, tests, the offline demo and installation paths. The expanded hosted workflow has not run for these local changes; inspect all job results after the push before claiming success.

Keep the changelog under **Unreleased** until an explicitly scoped release is ready. Human-reviewed extraction/answer-quality gates remain open. Do not attach publisher caches, personal libraries or benchmark timing results as evidence that those quality targets have passed. A source push does not imply a tag, GitHub release or container-image publication.
