# Publishing the repository

Run Git commands from the project folder containing `app/` and the README, not its parent folder. Review the source and synthetic screenshots before publishing. The real local library and generated files stay on your computer.

```powershell
git status --short
git add .
git diff --cached --stat
git diff --cached --name-only
git commit -m "Publish Article Intelligence research workspace"
```

Create an empty repository on your GitHub account (without adding a README or license there), then replace the example remote with your repository URL:

```powershell
git remote add origin https://github.com/YOUR_USERNAME/article-intelligence.git
git push -u origin main
```

If Git asks for your identity, configure your own name and email locally before committing. Use a GitHub-provided private email if you prefer. No remote or commit author is configured during repository preparation.

`data/`, `output/`, `.venv/`, local environment files, Streamlit secrets, database sidecars, and logs are excluded. Keep public screenshots in `docs/images/` and use synthetic content there. Avoid `git add -f` for ignored files. Downloaded article text, PDFs, full backups, local evaluation caches, and API keys do not belong in the public repository.

The Windows/Python 3.13 workflow runs after the first push. It uses the official [checkout](https://github.com/actions/checkout/releases/tag/v7.0.1) and [setup-python](https://github.com/actions/setup-python/releases/tag/v7.1.0) actions pinned to their release commits, installs a test browser, runs the tests, and builds the offline demo. A successful local run is not a claim that hosted CI has already passed.
