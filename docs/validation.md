# Validation record

Updated: 2026-10-29. These results concern installation/runtime portability, not extraction completeness or AI answer quality. Baseline source commit: `9067fad`; the implementation changes below are local and have not been pushed or released.

Later Windows checkpoint (general analytics/research usability): **231 passed, 1 opt-in live-server installation test skipped**. Separate synthetic browser checks verified general/specialist modes, topics/status/day scopes, CSV membership, both themes, 390px layout, page-jump navigation and article-to-Research handoff. The 112-article/PDF personal library remained hash-identical. This later checkpoint has not been repeated on Linux/Docker; the Milestone A matrix below is historical evidence for that milestone, not a claim that subsequent changes have been validated everywhere. See [milestones](../milestones.md) for the bounded cache/analytics performance measurements and pending human evaluation.

## Historical Milestone A verification matrix

| Check | Result | Actual environment/evidence |
| --- | --- | --- |
| Unchanged Windows baseline | PASS | Python 3.13.14, pip check, 196 tests with installed Chrome |
| Updated Windows regression suite | PASS | Python 3.13.14; 203 passed, 1 live-server test skipped in the ordinary full suite |
| Windows live UI | PASS | Separate disposable server/library: search, reading dialog, notes, downloaded PDF bytes and parsed PDF text |
| Fresh native Linux install | PASS | Ubuntu 26.04 WSL2 x86_64, separately installed CPython 3.13.14; fresh source/venv, runtime/dev install, pip check |
| Native Linux regression/browser | PASS | 203 passed, 1 live-server test skipped in the ordinary full suite; actual Chromium 156.0.8078.4 namespace/PID/network/seccomp status verified |
| Native Linux live UI | PASS | Separate disposable server/library: same search, notes and PDF checks, without Ollama |
| Original synthetic demo | PASS | 36 articles, isolated destination; no publisher/model calls |
| Offline PDF/export/portable restore | PASS | Windows, native Ubuntu and container; notes/PDF hash preserved; repeat restore idempotent; hard-link creation exercised |
| Docker build/runtime | PASS | Docker Desktop Linux engine 29.7.2, Compose 5.3.1; Python 3.13.14 on Debian 12, local x86_64 image |
| Container full suite and live UI | PASS | 204 tests, including browser-policy fixture and real UI/PDF download |
| Container sandbox/security settings | PASS | Non-root UID, read-only rootfs, all host capabilities dropped, no-new-privileges, default-deny seccomp plus documented namespace/chroot rules; Chromium's own status checked |
| Container recreation persistence | PASS | New Compose project and isolated named volumes; synthetic article, note, highlight and PDF hash survived force-recreation |
| Actual Docker build context audit | PASS | 69 allowlisted files at audit time; no private/generated paths, PDFs, databases, backups, env files or caches |
| Existing personal library preservation | PASS | Read-only hash baseline for all real tables and 105 PDFs; final check matches 105 saved articles |
| New hosted CI matrix | NOT RUN | Windows/Python 3.13, Ubuntu 24.04/Python 3.13 and Docker jobs configured; needs an explicitly requested push to execute |
| Native macOS / ARM64 / GPUs | NOT RUN | Not declared supported by this milestone |
| Host Ollama connectivity/model quality | NOT RUN | Optional; model service intentionally unavailable in installation smoke checks |
| AppArmor policy loading on Ubuntu 24.04 | NOT RUN | Scoped profile generation/syntax exercised; WSL kernel lacks the full AppArmor interface. Hosted CI uses the scoped profile if namespace restrictions are active |

## Commands and observations

Windows, from the repository root:

```powershell
$env:RUN_BROWSER_TESTS = '1'
$env:ARTICLE_BROWSER_CHANNEL = 'chrome'
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest -q tests
.\.venv\Scripts\python.exe scripts/check_install.py --browser
.\.venv\Scripts\python.exe scripts/smoke_install.py
.\.venv\Scripts\python.exe scripts/validate_native.py
```

Native Linux used a fresh source copy without Windows caches or user data. A checksum-verified temporary uv bootstrap provided CPython 3.13.14 without replacing the OS Python. The clean copy then ran the normal `python3.13 -m venv .venv`, `.venv/bin/python -m pip install -r requirements.txt`, pip check and development install with Linux runtime constraints. Ubuntu browser system packages were installed with administrator privileges using Playwright's `install-deps chromium`.

```bash
export ARTICLE_BROWSER_CHANNEL=chromium
export RUN_BROWSER_TESTS=1
export PLAYWRIGHT_BROWSERS_PATH=/path/to/validated-matching-browser-cache
.venv/bin/python -m pytest -q tests
.venv/bin/python scripts/check_install.py --browser
.venv/bin/python scripts/smoke_install.py
.venv/bin/python scripts/seed_demo.py
.venv/bin/python scripts/validate_native.py
```

The ordinary suite skips the live-server test because no server URL is supplied. `validate_native.py` supplies an isolated server and runs that additional test. The Docker validator supplies its isolated running app when executing the complete test image, so all 204 tests run together there.

```sh
docker compose config --quiet
docker build --target runtime -t artint:milestone-a .
python scripts/validate_container.py --report output/container-validation.json
```

The container validator uses a random Compose project and a dynamic host-loopback port, an empty env file, fresh named volumes and an intentionally unreachable model URL. It checks health, actual sandbox status, search/export/restore, persistence after recreation and live UI behaviour. It cleans only that project's containers/volumes. The separate test image includes dev dependencies and extraction-evaluator fixtures; these do not enter the runtime target.

Local evidence is under ignored `output/milestone-a/`: `container-validation.json`, `native-browser.log`, `native-ui.log`, `fresh-native.log`, `context-audit.json` and the real-library hash baseline. Those are local validation artifacts, not publisher fixtures to distribute.

## Issues found and resolved

- Windows `.pyc` files reused from a shared WSL checkout caused two source-inspection test failures. A separate Linux cache and a fresh source checkout removed this environment contamination; application behaviour was not rewritten to mask it.
- `/tmp` was cleared when WSL restarted. The isolated validation interpreter was moved to persistent temporary storage for the duration of checks.
- The browser CDN repeatedly timed out from Linux/container networking. The Dockerfile now obtains matching Chromium/FFmpeg from the digest-pinned official Playwright image. Native validation reused those same binaries. No certificate check or publisher restriction was disabled.
- Dropping all host capabilities exposed the upstream seccomp profile's capability-gated `chroot` rule. A marked syscall allowance lets Chromium chroot inside its own user namespace without granting outer `SYS_CHROOT` or `SYS_ADMIN` capabilities. Namespace/PID/network/seccomp checks and the real capture fixture then passed.
- Chromium's current sandbox page labels its first layer `Namespace`; diagnostics verify the actual current page rather than accepting launch success alone.

## Milestone A release checks

- [x] Preserve the existing library and retain schema version 6.
- [x] Validate Windows, native Ubuntu/WSL and local Docker without Ollama.
- [x] Keep private data outside Git and the actual Docker context/runtime.
- [x] Verify sandboxed browser policy, safe exports, restore and persistent volumes.
- [x] Document explicit migration, backup, loopback binding and removal behaviour.
- [ ] Run the new hosted CI jobs after an authorized push; investigate any runner-specific differences.
- [ ] Review the scoped AppArmor loading path on an AppArmor-enabled native host/runner.
- [ ] Tag a release or publish an image only after an explicit request and the selected release gates pass.

Milestone A's local verification is complete for the environments above. Hosted-runner/AppArmor checks remain explicit release follow-ups. Milestone B now has extraction-review tooling, but its human-reviewed quality gate remains open. Later analytics/research changes have their separate Windows checkpoint above and still need Linux/Docker revalidation; these historical checks establish no accuracy percentage.
