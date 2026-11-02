# Local installation and recovery

Updated: 2026-10-31. Run commands from the repository folder containing `app/` and `requirements.txt`. Artint is a single-user local application. Ollama is optional; new AI generation requires Ollama 0.40.11 or newer for checked non-truncating context controls. Do not expose the unauthenticated app to other machines.

See [validation](validation.md) for the environments actually checked, including one native Windows RTX 5050 configuration. Native macOS, ARM64 and container GPU configurations are not validated. Docker validation does not establish native support on its host OS.

## Windows / PowerShell

Install Python 3.13, then:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe scripts/check_install.py --browser
.\.venv\Scripts\python.exe scripts/smoke_install.py
.\.venv\Scripts\python.exe -m streamlit run app/dashboard.py
```

Open http://127.0.0.1:8501. No activation or PowerShell execution-policy change is needed. Auto capture also supports installed Chrome/Edge. The smoke check creates and removes its own synthetic library; it does not open your configured library.

### Optional native Windows NVIDIA inference

Install Ollama and the models listed in the README. Quit an already-running Ollama tray app/server, then run this once before starting Artint:

```powershell
.\scripts\start_ollama_gpu.ps1
.\.venv\Scripts\python.exe -m streamlit run app/dashboard.py
```

The launcher discovers the NVIDIA GPU UUID and starts a hidden Ollama server on `127.0.0.1:11434`. It selects CUDA, disables Vulkan for that server, enables Flash Attention, defaults to the unquantized `f16` KV cache and limits concurrent requests to one. Artint separately selects 8K/16K generation context while retaining the model and 1,600-token output limit. Logs, the started PID and a `profile.json` manifest of requested settings are saved under ignored `output/ollama-gpu/`. Inspect the runner log for actual cache type and GPU placement; the manifest records requests, not proof that a backend honored them. The launcher does not stop existing servers, download models or alter persistent/parent environment settings. Ordinary Ollama tray launches do not inherit this project profile; use this launcher again after stopping the server or restarting Windows. If PowerShell blocks scripts, the equivalent process environment settings can be configured using the [official Ollama instructions](https://docs.ollama.com/faq#setting-environment-variables-on-windows); no execution-policy change is required by Artint.

To explicitly test a quantized KV cache, quit the existing Ollama server and launch:

```powershell
.\scripts\start_ollama_gpu.ps1 -KvCacheType q8_0
```

Then select `qwen3.5:9b` in Research settings if it is installed. Changing the cache profile does not change Artint's default model. `q8_0` reduces KV-cache memory, not all model/runtime memory, and has a model/task-dependent precision tradeoff. It applies to all models loaded by that server, including embeddings; compare cited answers and retrieval as well as latency/GPU placement. See [Ollama's cache documentation](https://docs.ollama.com/faq#how-can-i-set-the-quantization-type-for-the-kv-cache). To return to the default profile, stop that server and run the launcher without `-KvCacheType` (or explicitly use `-KvCacheType f16`). The launcher accepts only `f16` and `q8_0`, overrides inherited cache settings for its child server, and leaves the parent environment unchanged. No 4K application fallback is introduced.

On a machine with multiple NVIDIA GPUs, select the desired UUID explicitly:

```powershell
nvidia-smi --query-gpu=name,uuid --format=csv
.\scripts\start_ollama_gpu.ps1 -GpuUuid 'GPU-replace-with-the-detected-uuid'
```

During generation or semantic search, inspect actual placement:

```powershell
ollama ps
nvidia-smi
```

`ollama ps` reports GPU/CPU residency, rather than a speed guarantee. An empty list means no model is currently loaded; Artint requests embedding-model unload after the final batch to free memory for the answer model. GPU selection cannot guarantee an entire model fits in VRAM. On the checked 8 GB RTX 5050 laptop, `qwen3-embedding:0.6b` and `qwen3:8b` at 8K loaded entirely on CUDA; `qwen3:8b` at 16K offloaded 31 of 37 layers and retained some CPU work. The launcher does not force unsafe all-GPU allocation or quantize the KV cache. See the [adaptive-context checkpoint](validation.md#adaptive-context-checkpoint--2026-10-31), [earlier hardware checkpoint](validation.md#native-windows-nvidia-checkpoint--2026-10-30) and [Ollama GPU documentation](https://docs.ollama.com/gpu).

## Native Linux / Bash

Install CPython 3.13 separately from the operating system's Python. The clean Ubuntu 26.04 WSL2 check used a temporary uv-managed CPython 3.13.14; Ubuntu 26.04's default Python 3.14 was not substituted for the target. Use a Linux checkout and Linux virtual environment, preferably on the Linux filesystem. Do not share a Windows `.venv` or bytecode caches with WSL.

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip check
.venv/bin/python -m playwright install --with-deps chromium
.venv/bin/python scripts/check_install.py --browser
.venv/bin/python scripts/smoke_install.py
.venv/bin/python -m streamlit run app/dashboard.py
```

Open http://127.0.0.1:8501. Installing browser system libraries requires administrator privileges; browser binaries require a separate download. No models are downloaded. For the recorded Linux runtime resolution, add `-c requirements-linux-lock.txt` to the pip install. The direct requirements and this constraint set are both checked during validation; `requirements-lock.txt` is the earlier Windows/development snapshot.

If Python 3.13 is not available from your distribution, [uv's Python installation](https://docs.astral.sh/uv/guides/install-python/) is one option. Keep a separately installed interpreter; do not replace `/usr/bin/python3`.

### Ubuntu user-namespace restrictions

The browser launcher explicitly requests Chromium's sandbox and never falls back to an unsandboxed browser. `check_install.py --browser` checks Chromium's own namespace/PID/network/seccomp status on Linux.

Some Ubuntu installations restrict user namespaces through AppArmor. An administrator can review a profile scoped to the installed Chromium executable:

```bash
.venv/bin/python scripts/check_install.py --apparmor-profile > /tmp/artint-chromium.profile
cat /tmp/artint-chromium.profile
sudo apparmor_parser -r /tmp/artint-chromium.profile
.venv/bin/python scripts/check_install.py --browser
```

Generating a profile does not load it. This permission applies to the printed executable path; review who can modify that binary. Loading from `/tmp` is not persistent across reboot. For permanent configuration, have an administrator manage the reviewed profile. The CI step uses this scoped approach rather than disabling AppArmor or changing a system-wide namespace setting. See [Ubuntu's explanation](https://documentation.ubuntu.com/release-notes/24.04/#unprivileged-user-namespace-restrictions).

If the host cannot provide the required sandbox, use HTML-only capture or a supported container environment. Do not add `--no-sandbox`, privileged mode or `SYS_ADMIN` as an installation workaround.

## Docker Compose

Install/start Docker Engine or Docker Desktop with Linux containers and Compose. From the repository:

```sh
docker compose up --build -d --wait
docker compose exec artint python scripts/check_install.py --browser
```

Open http://127.0.0.1:8501. The app binds all interfaces **inside the container**; Docker publishes only on host loopback. It runs as UID 10001 with all host capabilities dropped, no-new-privileges, a read-only root filesystem and a scoped seccomp profile. Writable temporary storage and two named volumes are provided. This is local packaging, not a hardened public deployment.

If a native app already uses 8501, choose another host port before starting Compose:

```powershell
$env:ARTINT_PORT = '8503'
docker compose up --build -d --wait
```

```bash
ARTINT_PORT=8503 docker compose up --build -d --wait
```

Then open http://127.0.0.1:8503. Keep the same setting when recreating the service.

| Data | Container location | Compose volume |
| --- | --- | --- |
| SQLite library and migration backups | `/var/lib/artint/data/articles.db` and its directory | `library` |
| Individual reading PDFs | `/var/lib/artint/pdfs` | `pdfs` |

Volume names include the Compose project prefix. Use the same project/directory name to reopen the same library. Native `data/` and `output/` are not mounted or migrated automatically. Initial named volumes inherit the image's directory ownership; imported/bind-mounted folders must support the runtime UID, SQLite locking, atomic file operations and hard links. No automatic recursive permission changes are performed.

The image uses a digest-pinned Python 3.13 base, a complete recorded Linux runtime dependency set, and Chromium assets copied from the matching digest-pinned official Playwright image. Only Chromium/FFmpeg assets enter the runtime. The upstream browser image can make the first build download large layers. Version pins do not imply byte-identical builds: system package repositories can change. See [sandbox details and upstream license](../docker/README.md).

### Optional Ollama

Native installations default to `http://127.0.0.1:11434`. Compose defaults to `http://host.docker.internal:11434` and defines the host-gateway alias. Set `OLLAMA_BASE_URL` before recreating the service to choose another endpoint.

The alias identifies the host; it does not make a host service bound exclusively to loopback reachable on every Docker setup. Docker Desktop routing/firewall behaviour and native Linux bridge networking differ. On native Linux, use a model service on a private Docker network shared with Artint, or have an administrator configure a reachable host interface with restrictive access. Do not expose Ollama publicly to make the connection work. A remote model endpoint changes where article passages are sent.

Check model connectivity explicitly when needed:

```sh
docker compose exec artint python -c "from app.intelligence import OllamaClient; print(OllamaClient().models())"
```

This optional check was **not run** during Milestone A. No Ollama/GPU/model download was required for the verified library, PDF and UI workflows.

## Synthetic demo

Native generation is explicit and refuses a nonempty destination:

```sh
python scripts/seed_demo.py
```

Use your environment's Python executable. For Bash, start it with both storage overrides:

```bash
ARTICLE_LIBRARY_DB="$PWD/output/demo/library.db" ARTICLE_PDF_DIR="$PWD/output/demo/pdfs" \
  .venv/bin/python -m streamlit run app/dashboard.py
```

For PowerShell, follow the [README demo commands](../README.md#try-the-synthetic-demo). Clear overrides before reopening your normal library.

To view the demo in an isolated one-off container using a spare port:

```sh
docker compose run --rm --no-deps -p 127.0.0.1:8503:8501 \
  -e ARTICLE_LIBRARY_DB=/tmp/demo/library.db -e ARTICLE_PDF_DIR=/tmp/demo/pdfs \
  artint sh -c 'python scripts/seed_demo.py --output /tmp/demo && python -m streamlit run app/dashboard.py --server.address 0.0.0.0'
```

Only the `/tmp/demo` database is used; it disappears with that container. The example is Bash syntax. The synthetic articles and hand-authored analysis fixtures are not evidence of model quality.

## Backups, migration and removal

Use **Library -> Export library -> Backup & restore -> Prepare full backup** for a portable ZIP including saved text, notes, highlights, analyses and managed PDFs. Save the download outside a Docker build context. To migrate a native library, explicitly download that backup, open the container's UI, inspect it in Restore backup and approve the merge. PDF paths are rebased by the existing restore service; copying a Windows SQLite file alone leaves Windows PDF paths unresolved.

Container recreation and `docker compose down` preserve named volumes. Reopening with the same Compose project reconnects them. To export raw volumes for disaster recovery, stop Artint first and use Docker Desktop's volume export or your volume backup tooling on **both** volumes as one consistent pair. Restore them into matching volume paths/ownership before starting the service; a live raw copy of SQLite sidecars/files is not a validated backup method. Portable UI backups are the tested cross-environment route.

```sh
docker compose stop
docker compose up -d --wait
docker compose down
```

Do not add `--volumes` to the normal shutdown unless intentionally deleting a backed-up library. The automated container validator removes only randomly named validation volumes that it creates. For native removal, stop Streamlit and keep `data/`, `output/` and downloaded backups when removing the virtual environment or source checkout.

PDFs are selectable-text reading copies with source links, not pixel-perfect archives. Capture respects access restrictions; free RSS discovery has provider terms and is not assumed licensed for commercial use. Never redistribute private backups or publisher captures with the source/image.

## Diagnostics and troubleshooting

### Model readiness and residency checks

The ordinary installation diagnostic does not contact Ollama. To explicitly check the configured model endpoint without inference:

```powershell
.\.venv\Scripts\python.exe scripts/check_install.py --ollama
```

Use `.venv/bin/python` on Linux. `--ollama-url` overrides `OLLAMA_BASE_URL`; `--chat-model` and `--embedding-model` select installed names to check. Run this separately from `--browser`, `--health-url` or `--apparmor-profile`. It reads only the [model inventory](https://docs.ollama.com/api/tags), [running-model metadata](https://docs.ollama.com/api/ps) and runtime version. No model is loaded/downloaded, no article text is sent, and no library/database is opened. Metadata requests have short timeouts, bounded response sizes and no redirects. Endpoint URLs with embedded credentials/query tokens are rejected.

The CLI returns nonzero if the service/inventory is unavailable, selected models are missing or generation runtime compatibility cannot be established. Runtime compatibility follows the app's checked minimum. Installed-but-unloaded models can pass readiness; GPU residency is only available while models are loaded. A running-model API failure leaves residency unknown rather than pretending the model is on CPU. Readiness is metadata availability/compatibility, not a successful inference or quality benchmark.

The same snapshot is available through **Research → Research settings → Check model status**, with a readable timestamp and theme-aware table. Refresh explicitly after loading/unloading models; switching the endpoint/selected models or refreshing model inventory clears the old snapshot. Mixed residency near 100% is displayed as `>99.9%`, and near zero as `<0.1%`, so rounding cannot imply a fully GPU/CPU placement. Memory residency is not GPU activity, speed, device identity or proof of cache precision. For a remote endpoint the report describes that server's metadata, not the client's RTX GPU. The API does not expose KV-cache precision; use actual runner logs for that check.

- **Missing `.venv` executable:** run from the folder containing `app/`; create the virtual environment for that operating system first.
- **Docker API unavailable:** start Docker Desktop/the daemon and select Linux containers.
- **Port already allocated:** use another `ARTINT_PORT`; leave a running native library untouched.
- **Browser startup fails:** run `check_install.py --browser`; check libraries, executable permissions and user namespaces. HTML-only capture remains available.
- **Browser CDN times out:** check network access to Playwright's official download endpoints. Validation used matching browser assets from the official image after CDN timeouts. A local fallback is to build `artint:local`, use `docker create`/`docker cp` to export `/opt/playwright` into an ignored cache, and set `PLAYWRIGHT_BROWSERS_PATH` to that cache. The cache must match the installed Playwright version and Linux architecture.
- **WSL source-inspection failures:** use a fresh Linux checkout/cache. Windows-generated `.pyc` files can embed Windows source paths even when the Python minor version matches. A separate `PYTHONPYCACHEPREFIX` is another option.
- **Permission or restore errors:** verify volume ownership and hard-link support; do not delete the database or use broad recursive chmod/chown on your native library.
- **Offline AI warning:** keep using Library/Analytics/notes/PDFs, or configure Ollama explicitly in Research.

Release evidence and remaining platform checks are recorded in [validation](validation.md).
