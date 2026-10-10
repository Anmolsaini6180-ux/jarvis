# Mark LV / Jarvis — repaired desktop assistant

This is the repaired version of the uploaded Mark LV source. The existing Qt HUD, holographic avatar, Gemini Live conversation, browser tools, settings, memory and useful desktop actions remain. Windows 10/11 is the primary target; macOS/Linux paths are retained where practical. Verification was performed on a Linux cloud development machine, not on every supported platform.

Start with [WINDOWS_SETUP.md](WINDOWS_SETUP.md). Read [CHANGELOG_REPAIRS.md](CHANGELOG_REPAIRS.md), [REPAIR_STATUS.md](REPAIR_STATUS.md) and [TEST_RESULTS.md](TEST_RESULTS.md) for migrations, evidence and remaining limitations.

## Current behavior

- File actions use a task workspace (`Documents/JarvisWorkspace`) and explicit local HUD file/folder grants. Selecting one file does not authorize its parent directory. Collision attempts preserve existing data; edits keep disk-backed recovery copies. Undo refuses to replace newer changes.
- Code generation/editing is available with a configured Gemini account. Generated execution requires an optional reviewed, digest-pinned local Docker image. Without enforceable isolation, execution is unavailable; it never falls back to running generated code as the host user. A successful exit is not a functional verification.
- Messages produce usable drafts. Sending needs a separately installed verified adapter, unique recipient selection and a complete recipient/message HUD review. No verified messaging driver is bundled; blind Enter/keystroke sending was removed.
- The existing HUD includes task IDs/progress, recent status, STOP/CANCEL and Escape. Tools use a bounded FIFO mutation worker, independent of session reception. Cancellation is cooperative; an uncooperative library call can retain its mutation slot until it returns.
- Local microphone input remains gated during assistant speech. Manual stop is the reliable fallback; full duplex voice interruption is not implemented/verified. Read [docs/VOICE_INTERRUPTION.md](docs/VOICE_INTERRUPTION.md).
- Interactive browser automation reports its browser, profile and active tab. Chromium uses a separate persistent automation profile, which may need a separate sign-in. Native browser launches report a request, not verified page loading. Page/input postconditions do not prove purchases or message delivery.
- Weather opens a search and reports that no weather values were retrieved. Flight extraction is a limited scrape/model interpretation, not verified pricing, booking or payment.
- Document analysis reports processed coverage and source character/page/slide references. It has extraction/request budgets; PDF OCR and complete visual/layout coverage are not promised. XML uses a safe XML parser. ZIP/TAR extraction is bounded; RAR/7z extraction is not implemented.
- Plugins require a local review before importing their Python code, including helpers. Trusted plugins run with your user permissions; the review gate is not a sandbox.
- Lightweight mode lowers animation/metrics rates and pauses proactive/monitor background tasks on reconnect. Response preference supports auto, English and Hinglish while retaining code/names/numbers.

## Configuration and data

Settings/memory/monitoring use locked, atomic transactions and backups. Damaged JSON is recovered from a known-good backup with a warning and a preserved damaged copy; absence of a valid backup is an error, not an empty reset.

Windows credentials migrate to current-user DPAPI ciphertext under `config/credentials/`; macOS/Linux require a usable native OS keyring. Existing plaintext is preserved with a warning if migration cannot run. New plaintext credentials are refused. Keep configuration and credential backups together, and migrate on the same OS account. Memory, reminders and recovery copies remain local plaintext personal data; protect your account and backups.

Memory storage is bounded to approximately 200,000 serialized characters; new ordinary entry values keep 380 characters plus a truncation marker. Prompt core has a 900-character target, but identity is always included and can exceed that target; its key index has a 420-character budget. At most three 280-character session summaries are retained for continuation; explicit recall uses local lexical matching, not a vector/semantic database. Old entries can be trimmed at the storage budget with a notification. The memory HUD supports entry deletion; back up the JSON for export. It is not unlimited memory.

Gemini conversation audio, requested screenshots/images/documents, prompts and selected memory context may leave this machine. Browser/search services and optional integrations also make network requests. Muting the microphone does not disable every network feature. This is not a complete local-only privacy mode. API access, supported models, billing and quotas depend on the account/provider; no unlimited or zero-cost cloud use is promised.

The local LLM/STT/TTS modules are retained as inactive components. They are not routed into the active Gemini Live conversation. **Offline conversation is not implemented.** Opt-in local wake-word detection is a separate feature, not proof of offline conversation support.

## Development

Use Python 3.12 in a virtual environment. `setup.py` resolves manifests relative to the project, refuses dependency installation outside a venv, and installs only selected optional groups. `requirements.txt` remains a full-feature compatibility manifest. `requirements/lock-linux-py312.txt` records the exact packages used by this Linux verification environment; it is not a Windows lock or a guarantee that native libraries/hardware exist.

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe setup.py --extras browser documents dashboard media windows
.venv\Scripts\python.exe -m pip install -r requirements/test.txt
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

CI defines Windows/Linux Python 3.12 regression jobs. It was added here; hosted CI has not been run by this task. Tests use disposable files and mocked accounts/transports; they send no real messages or schedule real OS jobs.

Standalone Android, new business integrations and a learning platform remain separate projects.

## License

The original personal/non-commercial [Creative Commons BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/) licensing statement is retained. This repair does not change licensing or ownership.
