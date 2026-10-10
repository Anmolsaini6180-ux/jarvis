# Windows 10/11 setup and migration

Use a normal user account, not an administrator terminal. This guide is for the repaired source; it does not assert that Windows/hardware/account tests have already passed. Python 3.12 was used for cloud verification.

## 1. Preserve your current installation

1. Close the old assistant. Copy its entire folder to a private backup location before replacing anything.
2. Preserve `config/`, `memory/`, `plugins/`, every generated project, `Documents/JarvisWorkspace`, `%USERPROFILE%/.jarvis_profiles`, and `%USERPROFILE%/.jarvis/reminders` if present. Existing OS scheduled tasks are not automatically deleted/migrated.
3. Extract the repaired ZIP into a new folder, for example `C:\Users\YourName\Mark-LV-repaired`. Do not unzip over your only copy of configuration/projects.
4. Copy your old configuration/memory/plugin/project data into the corresponding locations in the new folder, without replacing repaired `.py` files with old application code. Merge deliberately; never replace a populated data folder with an empty one. Keep native credential ciphertext and the corresponding `api_keys.json` references together if already migrated.
5. Keep the old assistant venv separate. Create a new assistant venv below. Legacy generated projects stay where they are; use the HUD to grant their individual project folders before edits/runs.

The repaired source ZIP contains no user configuration/credentials/memory/recovery snapshots, browser profiles or generated projects. Missing user data in that ZIP is expected.

## 2. Install core features

Install 64-bit Python 3.12 using its official installer. Enable the Python launcher. Open PowerShell in the extracted project folder (Shift + right-click → Open in Terminal), then run:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe setup.py
.venv\Scripts\python.exe tools\diagnostics.py --audio
.venv\Scripts\python.exe main.py
```

Using the venv Python directly avoids PowerShell activation-policy changes. `setup.py` refuses installation into the system interpreter and finds requirement files relative to itself. `--dry-run` prints the proposed commands without installing anything.

The first launch shows the existing local setup/key overlay. Enter your Gemini key there, not into a chat, source file or bug report. Cloud access can require billing and has account-specific quotas; check your account's official settings. The current SDK is pinned to `google-genai==2.29.0`. Default Live model is `models/gemini-3.1-flash-live-preview`; default REST text alias is `gemini-flash-latest`, as documented by the official examples. These examples do not guarantee your account has access. Locally configured `JARVIS_LIVE_MODEL`/`JARVIS_TEXT_MODEL` can select another verified supported model; optional Live settings may need compatibility checks.

## 3. Add only the optional features you need

```powershell
.venv\Scripts\python.exe setup.py --extras browser documents dashboard media windows
```

You may choose fewer groups, for example `--extras documents`. The groups mean browser automation/search, document formats/safe XML, phone dashboard, media/transcripts/camera and Windows controls/notifications respectively. `requirements.txt` remains the full compatibility installation; inactive local STT/TTS/LLM and absent community plugins are not mandatory dependencies.

For Playwright's Chromium download, explicitly run:

```powershell
.venv\Scripts\python.exe setup.py --extras browser --browsers
```

Chrome-family automation uses a separate persistent profile under `%USERPROFILE%/.jarvis_profiles`. It may need a separate sign-in; the tool discloses the browser/profile/tab. It does not attach to your already-open signed-in tab. Browser download/CDN access is optional and was not tested here. Native launch-only actions still report loading/window state as unverified.

Media conversion uses an independently installed `ffmpeg` executable on PATH; no service installation/elevation is performed by this repair. Optional local wake-word installation can download packages/models through its existing opt-in UI, but it does not enable offline conversation. Third-party/plugin dependencies need independent review.

## 4. Credential and state migration

The first configuration read attempts migration of existing plaintext Gemini/plugin credentials into current-user Windows DPAPI ciphertext under `config/credentials/`. The migration journal `config/credential_migrations.json` identifies immutable encrypted prior backups. It verifies encrypted storage before replacing plaintext fields with `$credential` references; the prior complete configuration and previous backup are protected as migration backups. All application credential readers now use the shared credential-aware API. Settings unrelated to the edited field are preserved.

On macOS/Linux, configure an unlocked native Keychain/SecretService/KWallet backend. If a secure backend is unavailable, existing plaintext is preserved with a visible warning; new plaintext keys are refused. On Windows, a DPAPI failure is an error, not a plaintext fallback. Do not edit `$credential` references manually. A different Windows account/computer may not decrypt the files: re-enter keys locally from your secure original records. Copying only `api_keys.json` is insufficient after migration.

If JSON is damaged, a valid `.bak` is restored with a warning and the damaged copy is retained as `.corrupt-<id>`. Without a valid backup, startup/state access fails clearly. Restore a known-good backup deliberately; do not delete the corrupt original to hide the error. Local memory/reminder/recovery backups still contain personal data in plaintext; keep backups private. Migration backups are not an indefinite full backup service.

Plugins are preserved but now need explicit trust review before import. Read every plugin/helper Python file. Use the existing plugin panel REVIEW confirmation, or this explicit local command:

```powershell
.venv\Scripts\python.exe tools\trust_plugin.py plugins\your_plugin.py --reviewed
```

Then restart. Changes to any helper invalidate bundle trust. Importing a trusted plugin runs Python with your user permissions; it is not sandboxed. Original missing WhatsApp driver is not fabricated: message drafts work, actual integrated sending remains unavailable until a reviewed verified adapter is supplied.

## 5. Workspace and generated execution

Default file scope is `%USERPROFILE%/Documents/JarvisWorkspace`. Explicit file selection/drop grants that file, not its parent folder. For Desktop/Downloads/existing projects, approve just the needed folder in the local HUD workspace-scope prompt. Grants expire with the process. Machine-root/home-wide grants, assistant credentials/configuration and linked/junction paths are refused.

Creating/copying/moving onto an existing destination fails and preserves it. Explicit write/edit operations retain disk snapshots under `config/recovery/`; undo checks for later edits. If it reports a conflict, newer work remains in place and the snapshot path is shown. Back up recovery data if needed. Undo closures are session-only; disk snapshots/manifests remain available for manual recovery after restart. There is no automatic cleanup of these backups.

Code generation/editing remains usable without Docker. Review generated files before manually opening an IDE; IDE extensions are privileged. Generic app launching refuses workspace executables/scripts, rather than bypassing isolated execution. To execute generated code, optionally install/configure Docker Desktop with a Linux engine, then review/build a local runner image yourself and obtain its real digest. Set `JARVIS_RUNNER_IMAGE` to your actual `repository@sha256:<64 hex digest>` before launch. The assistant inspects but never pulls the image automatically. No specific image is asserted safe or preinstalled. See [docs/EXECUTION_SECURITY.md](docs/EXECUTION_SECURITY.md).

The runner copies approved project files into disposable storage, mounts them read-only, disables network, drops privileges/capabilities and applies resource/time limits. Review project contents before running: protected assistant metadata/common secret filenames are blocked, but arbitrary secrets can be named anything. Container/kernel/daemon vulnerabilities remain outside this policy. GUI/network servers/persistent output workflows are unsupported by this runner policy; no host-permission fallback occurs. Dependencies must be reviewed and included in the runner image. Manual project venvs are for dependency isolation, not security, and projects containing protected metadata such as `.venv`, `.git` or `.env` are refused rather than silently filtered. Prepare a reviewed code-only directory for the runner.

When dependency proposals are generated, review exact distribution names/versions and transitive dependencies. Install manually into a separate **project** venv if needed; never use the assistant venv. Never execute untrusted generated code directly on the host merely because it has a venv.

## 6. Safe smoke checks

Start with disposable data inside `JarvisWorkspace`:

1. Create/read/rename/copy a small text file. Try copying onto an existing file: it must refuse and preserve the original. Modify an assistant-created file yourself before undo: undo must report a conflict and retain your newer content.
2. Select just one test file outside that folder. Reading that file should work; its unselected sibling should not become authorized.
3. Ask for a small generated program. Check the actual generated files. Without a configured reviewed Docker runner, execution must say unavailable/unverified. With a configured runner, test an exit-7 program and a timeout; neither may be described as a working app. Exit zero alone is still not functional verification.
4. Start a multi-step disposable task, then click STOP/CANCEL or press Escape while the app has focus. Check cancelled queue/history entries and that later steps do not run. A blocked third-party call may finish its current operation before stopping; do not expect rollback of completed actions.
5. Prepare a message to a fake recipient. Confirm it remains a draft with unavailable send status. Never use a real recipient for an integration smoke test.
6. For real voice checks, use headphones first: select input/output devices, test silence, ordinary reply and manual stop, then repeat with speakers/noise. Local barge-in during speech remains disabled. No acoustic performance was verified in cloud tests.
7. Review memory/settings persistence across restart; retain the configuration backup. Set two future reminders for the same minute only when you intend to create actual jobs, verify distinct IDs, then check actual notification timing. OS scheduling was mocked during development tests.

Install and run regressions using disposable fixtures:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements\test.txt
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe -m compileall -q actions core memory dashboard main.py ui.py setup.py
.venv\Scripts\python.exe tools\smoke_ui.py
```

Do not count skipped tests as passed. The offscreen smoke excludes multimedia/audio hardware. Use [TEST_RESULTS.md](TEST_RESULTS.md) for actual cloud commands and counts; hosted Windows CI has not yet run.

## 7. Optional phone dashboard

It starts OFF and listens only after the local Remote Control button activates it. It requires valid TLS; certificate failure disables serving rather than falling back to HTTP. The displayed manual URL is HTTPS on port 8000. Verify the locally generated certificate/fingerprint out of band before pairing; do not teach the browser to trust arbitrary certificates. No automatic firewall, elevation or network-policy modification occurs. Change your own LAN firewall settings only if you understand and intend the access.

Sessions expire after one hour; remembered devices expire after 30 days. Logout/revocation invalidates bearer tokens and active WebSockets. Session/device pairing is process-scoped; pairing must be repeated after restart. Every paired device is privileged to control the assistant; fine-grained roles and internet exposure are not implemented. Use a trusted LAN only, with no public port forwarding. The page has a Logout control; revoke devices through the authenticated dashboard API. Local explicit disable/revoke can be performed with the server API in trusted application code; no new local revoke button is claimed.

Keep the phone connection/UI logs visible. Reported connection to Jarvis is not proof that a downstream browser click/message succeeded. TLS, certificate trust, Windows firewall reachability and a real phone/WebSocket reconnection need separate checks.

## 8. Packaging from the repair branch

The source is on local branch `repairs/mark-lv`; it has not been pushed/published. To package the tracked repaired files without venvs/runtime personal data:

```powershell
git switch repairs/mark-lv
git status --short
git archive --format=zip --prefix=Mark-LV-repaired/ --output=..\Mark-LV-repaired.zip HEAD
```

Review uncommitted changes before packaging. Keep data backups separate. For local-only branch transfer, `git bundle create ..\Mark-LV-repairs.bundle --all` preserves commits; the supplied bundle also retains original baseline history. It contains no intended runtime configuration/data. Publishing cloud environment settings or pushing a branch is a separate user action; fresh-task restoration of local-only commits was not verified.
