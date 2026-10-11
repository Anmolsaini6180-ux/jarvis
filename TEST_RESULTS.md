> **Round 2 (2026-10-11):** Current Live/credential/dashboard fixes and evidence are in [ROUND2_REPAIR_REPORT.md](docs/ROUND2_REPAIR_REPORT.md). Use the external-venv instructions at the top of [WINDOWS_SETUP.md](WINDOWS_SETUP.md). The sections below retain earlier repair history; conflicting setup/configuration claims are superseded.

# Actual verification results

Environment: Linux cloud machine, Python **3.12.14**. Dedicated test venv: `/workspace/marklv-testenv`. Results below are development evidence; they do not establish end-to-end Windows voice/account/container readiness. No real messages, paid/API conversations, real OS reminders, destructive user-file tests, firewall changes, service installations or publication were performed.

## Baseline and phase checkpoints

| Checkpoint | Command from `/workspace/jarvis` | Actual outcome |
|---|---|---|
| Original source syntax | `python -m compileall -q .` | Passed for 49 original Python modules; no import/integration claim |
| Baseline disposable-file probes | `python -m unittest discover -s tests -v` | 3 tests executed, **3 failed**: rename escape, copy overwrite, undo destroyed newer edit |
| Phase 1 | `python -m unittest discover -s tests -v` | 24 passed, zero skips |
| Phase 2 | same cumulative command | 37 passed, zero skips |
| Phase 3 | same cumulative command | 44 passed, zero skips |
| Phase 4 | same cumulative command | 56 passed, zero skips |
| Final Phase 5 / cross-phase regressions | `/workspace/marklv-testenv/bin/python -m unittest discover -s tests -v` | **83 executed, 83 passed, zero failures/errors/skips** in final run |

Intermediate integration runs exposed issues and were not counted as final passes: a 71-test run had one failure/two errors (missing code-analysis import, missing launcher `Path` import, test omitted required browser action); a 75-test run exposed a WebSocket test expecting closure before consuming the existing initial history message; a 78-test run caught a missing workspace accessor. Those issues were corrected and the relevant cases remain in the final suite. Temporary source syntax mistakes were corrected before packaging. No assertion was removed to manufacture passing results.

## Final commands and independent smoke checks

| Command / operation | Actual result | What it does not prove |
|---|---|---|
| `python -m venv /workspace/marklv-testenv` then venv `python -m pip install -r requirements-core.txt -r requirements/test.txt` | Fresh dependency environment installed successfully with standard TLS/package checks; no host-interpreter installation | Windows/native libraries, audio devices, optional media/doc adapters |
| venv `python -m pip install -r requirements/lock-linux-py312.txt` | Recorded Linux package snapshot reinstallation passed; existing packages satisfied | Windows lock/cross-platform reproducibility, artifact-hash lock (this freeze has no hashes) |
| venv `python -m pip check` | `No broken requirements found.` | Importability of every optional native module or functional integrations |
| venv `python -m compileall -q actions core memory dashboard main.py ui.py setup.py` | Passed | Runtime/behavior correctness by itself |
| Import `core.storage`, `credentials`, `tasks`, `gemini`, `action_loader`, `plugin_loader`, `actions.desktop`, `dev_agent`, `file_processor`, `dashboard.server`, `ui`, `main` | All 12 affected modules imported. Main accurately logged missing PortAudio. No cloud session opened | Full application startup with a live account |
| Actual discovery + `google.genai.types.FunctionDeclaration` construction | 18 active bundled actions; their declarations validated by the installed SDK | Every optional tool's external driver/dependency/account readiness |
| venv `python tools/smoke_sdk.py` | Real plain/tuned/enhanced `LiveConnectConfig` objects constructed; **26 declarations** including core tools in each. Disposable settings; no API request | Account/model acceptance of preview settings or real Live protocol behavior |
| `XDG_CACHE_HOME=/tmp/marklv-qt-cache /workspace/marklv-testenv/bin/python tools/smoke_ui.py` | Actual offscreen Qt HUD/avatar construction, task status, STOP button/shortcut signal wiring with a fake callback, and full Unicode/plain-text scrollable confirmation passed; disposable settings | Real display/input, video backend/audio, acoustic interruption, Windows visual layout/performance |
| venv `python tools/check_dashboard_js.py` with existing Node | Both actual inline scripts passed `node --check`; actual encoder escaped tag/attribute payload; insecure-origin bypass instructions absent | A browser DOM/XSS penetration test, real TLS/phone microphone test. Node remains optional |
| From `/tmp`: venv `python /workspace/jarvis/setup.py --dry-run --extras browser documents` | Printed absolute project-relative manifest paths; no installation attempted | Installing optional document/browser native components |
| venv `python tools/diagnostics.py --audio` | Modules found; `credential_present=false`, `audio_usable=false`, PortAudio `OSError` reported; offline conversation labelled not implemented; runner optional | Hardware/account capability readiness |
| `git diff --check` | Passed after whitespace cleanup | Behavior/security correctness |
| Saved onboarding installation script executed in current machine | Venv refresh, exact Linux package install and pip check passed; draft `install_script`/`start_skill` save returned `status=saved`, `requires_publish=true` | Publication or future-task restoration of local repair commits |

The final regression log, SDK/UI/JavaScript smoke output and diagnostics JSON accompany the delivery. Package integrity/contents are checked after creating the tracked-file ZIP; packaging is not an application test.

## Regression scope and effect boundaries

- **Real disposable filesystem operations:** traversal/absolute/reserved/ADS spelling, symlink root/member rejection, basename rename, selected-file-only scope, protected metadata, copy collisions, large disk recovery, backup failure, newer-edit undo conflicts, source/editor changes during copy/write preparation, screenshot collision/output rejection, ZIP/TAR traversal/link/size/collision and normal extraction. No real user file was used.
- **Real trusted subprocess fixtures:** exit 7, exit zero with `verified=false`, timeout and cancellation/process-tree termination paths using temporary trusted Python commands. Generated/untrusted code was never run on the host. Docker command/mount/isolation flags and unavailable isolation use mocks; no container was started.
- **Actual ASGI handlers, in-memory TestClient transport:** unauthorized/revoked/expired HTTP and WebSockets, logout, pairing rate, malformed commands/WS, body/upload/command bounds, queue saturation and bounded slow-client broadcasts. No network listener/real phone. TLS certificate failure is mocked and serving refused; real certificate serving/trust unrun.
- **Fake messaging adapters/recipients:** draft availability, human review gate, identity recheck, acceptance/receipt states and missing drivers. No real message sent. Actual Qt confirmation rendering is checked separately offscreen.
- **Task and receive logic:** FIFO/bounded rejection, cooperative cancellation, context propagation, stalled-worker serialization, reconnect/old-result suppression, audio bounds and cancellation despite history eviction. The actual receive method is executed with a fake transport; it is not a live SDK/account test. Native typing is tested with a fake keyboard, never a real window.
- **Persistence:** real concurrent thread/process JSON transactions, corrupt backup recovery/no silent reset, preserved unrelated settings, Unicode/legacy monitors. Native credentials use a mocked verified vault; no Windows DPAPI/macOS/Linux secure-backend proof. Reminder OS scheduling/transport is mocked, unique scripts compiled and timezone errors tested; no real jobs registered/fired.
- **Integrations:** actual safe XML parsing/entity rejection, source-budget/chunk references and file generation with fake model output, strict arguments before effects, plugin sentinel import blocked before trust and revoked after helper change, fake browser readback/postcondition/context, mocked Windows launcher/native failure. No paid/cloud/browser/profile/driver effects.

## Warnings, skips and checks not run

Current FastAPI/Starlette TestClient emits a dependency deprecation warning for `httpx`; its handlers/tests still executed. Qt emits font support warnings in offscreen rendering. Neither warning is hidden or treated as hardware readiness. Earlier headless PyAutoGUI/MouseInfo import resource warnings were addressed by checking X11 availability before importing optional desktop input.

Final Linux suite has **zero skips**. On Windows without symlink creation privilege, the real-link tests explicitly report skipped/unrun; they must never be added to passed counts. Do not elevate the app merely to obtain a green test count. Use disposable junction/link smoke checks when the platform permits them.

Hosted CI definitions were added for Windows/Linux Python 3.12, but hosted jobs were **not run** here. No macOS native smoke was performed. Account quota/billing/latency and acoustic response speed were not measured. No actual PDF/Office/media/browser whole-workflow verification is claimed from optional module presence or fake model tests.

## Remaining hardware/account checks

1. Windows 10/11 clean install, native DPAPI migration/readback under the intended account, COM/volume/keyboard controls, NTFS junction checks and real UI shutdown.
2. Microphone/speaker device selection, echo tail/manual stop/PTT/wake behavior with headphones/speakers/noise. Full duplex barge-in remains unimplemented.
3. An explicitly authorized Gemini account/session: model availability, preview-setting compatibility, actual receive/tool responses/reconnect, chosen language and billing/quota behavior. No latency target claimed.
4. Reviewed digest-pinned Docker image/engine: actual mount/network/capability/resource boundaries, dependency availability, timeout/tree/container cleanup. No host fallback.
5. Browser profiles/sign-in/locks and meaningful page outcomes; optional PDF/Office/media adapters and ffmpeg; no assumed purchase/send result.
6. Trusted-LAN HTTPS certificate trust, real phone revocation/expiry/WS reconnection/mic permissions; no firewall/insecure-browser-policy changes during these repair tests.
7. Real same-minute reminder registration/notification timing across sleep/timezone changes, with explicit user intent to create jobs. Recurring/edit/cancel/missed-reminder management and verified messaging adapters need further implementation; offline conversation remains not implemented.

## Source delivery verification

The tracked source ZIP passed `zipfile.ZipFile.testzip()` (CRC check), includes all four requested repair/setup documents, and excludes runtime configuration, recovery data, bytecode and virtual environments. Both original tracked image/avatar assets were compared byte-for-byte against baseline commit `59f65af` and preserved. `git bundle verify /workspace/artifacts/Mark-LV-repairs.bundle` passed; the bundle contains the local repair branch and complete history. These are packaging checks, not additional regression tests. The bundle history includes disposable test snapshots from an earlier repair commit; the final source ZIP excludes those snapshots. No push or publication was performed.


## Voice runtime update — 2026-10-10

Environment: Linux, Python 3.12.14, isolated development venv under workspace. No Windows audio devices, SAPI, Gemini credentials/account or real phone were available.

- Original uploaded-source regression baseline: **83 tests passed** independently.
- Updated full unittest suite: **104 tests passed** (83 previous + 21 voice regressions). New tests cover locked states/capability priority, exact local routing, real SDK objects with mocked auth/config/close/quota responses, HTTPX/DNS/TLS classification, actual run-loop auth/no-retry and six-attempt network cap with fake transport, mocked callback PCM dispatch, isolated device/optional failures, PTT end-marker ordering, mocked STOP/output abort, cleanup and atomic verified-resource wake setup with fake downloads/validator.
- Compileall: passed for actions/core/memory/dashboard/main.py/ui.py/setup.py.
- Actual offscreen HUD construction, Start Listening click and Qt Ctrl+Space press/release: passed. No physical microphone/speaker claim.
- Actual offscreen main entry initialized/shut down with disposable configuration, missing credential, excluded hardware/dashboard: passed. No provider network call.
- Actual google-genai 2.29.0 Live config/schema construction: passed for plain/tuned/enhanced configurations. No account call.
- Diagnostic inventory executed: Python/UI/SDK imports passed; sounddevice native PortAudio load, device enumeration, missing credential and absent optional wake resources failed as expected in this environment. Hardware/account-dependent rows SKIPPED, not PASS.
- Cross-target Windows wake pip resolution: NOT PASSED. pip evaluated the Linux-only tflite-runtime dependency marker on the Linux host and could not resolve it for Windows. Package metadata excludes that dependency on native Windows; native Windows installation is still untested. No unsafe dependency bypass was used to install wake support.
- Physical microphone/speaker/PTT/wake/Notepad/AI/STT/SAPI/restart acceptance: **requires physical Windows/account validation**, not tested here. Exact plain Jarvis acoustic activation, full local STT/conversation, provider switching, a SAPI voice-picker UI and wake acknowledgment sound remain unimplemented.

Initial restricted-sandbox runs stalled at cross-thread socket wakeups. Re-running with permitted networking allowed the local ASGI/async regression suite to finish; no live account test was substituted. See output verification logs and docs/VOICE_RUNTIME_REPAIR.md for acceptance/rollback.
