# Chromium sandbox configuration

`chromium-seccomp.json` derives from [Microsoft Playwright v1.64.1](https://github.com/microsoft/playwright/blob/v1.64.1/utils/docker/seccomp_profile.json), distributed under the accompanying `LICENSE.playwright` (Apache-2.0). One marked Artint rule permits the `chroot` syscall: Chromium needs it inside its new user namespace, whereas the upstream profile conditionally permits it only with the outer `SYS_CHROOT` capability. All host capabilities remain dropped; allowing this syscall does not grant that capability. The profile otherwise keeps upstream's default-deny policy and namespace rules. This is not equivalent to disabling seccomp or adding `SYS_ADMIN`.

The application requests `chromium_sandbox=True` and never retries without sandboxing. Compose runs UID 10001, drops all capabilities, sets no-new-privileges, uses a read-only root filesystem, and provides writable temporary memory and named library/PDF volumes. A host/kernel may still disallow user namespaces. In that case browser-assisted capture fails with an actionable message; HTML-only capture and the library remain available. Do not solve that failure with privileged mode, an unconfined profile or `--no-sandbox`.

The default runtime target excludes test dependencies. `docker build --target test` creates a separate validation image. Build and browser installation need network access; fixture tests do not contact publishers or model services. Dependency versions and the Python base digest are pinned; apt repository state and build outputs are not claimed to be bit-for-bit reproducible.

## Validate optional topic discovery

From the repository root, with Docker available:

```powershell
.\.venv\Scripts\python.exe scripts/validate_container.py --topics --report output/container-topics/report.json
```

This builds runtime/test images with `INSTALL_TOPICS=1` in a random disposable Compose project. It verifies the normal confined runtime, source/PDF/research restoration and recreation, then seeds a separately named collection of original fictional topic articles into that disposable library. The test image serves a loopback-only scripted embedding endpoint in the runtime's shared network namespace. The browser exercises discovery, JSON export, point-to-theme selection and cached reruns; a second app recreation checks that another discovery can reuse all its vectors.

No host Ollama, publisher fetch, model download or container GPU is used by this validation. Its original fixture validates the protocol, runtime backend and UI; it does not measure model quality. The seeder requires the explicit install-smoke flag, an existing valid installation marker and the original one-article fixture, and refuses an unrelated library. The validator checks pre-existing container/volume identities after removing only its owned project containers, network and volumes. Image/build caches remain available for later builds.

Without `--topics`, validation explicitly selects the lightweight runtime even if `ARTINT_TOPICS` was set in the caller's environment. CI defines separate `base` and `topics` container jobs; editing that workflow is not evidence of a hosted pass.

Chromium 1248 and FFmpeg 1013 are copied from the digest-pinned official Playwright Python 1.64.1 image into the Python 3.13 runtime. Firefox/WebKit and the upstream Python installation are not copied. This avoids an additional browser-CDN download during the build. Update the asset revisions and image digest together with `playwright` in the dependency files. The application uses full Chromium's current headless mode.
