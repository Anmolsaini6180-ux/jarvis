# Voice runtime repair and Windows acceptance

This update edits the uploaded project rather than rewriting it. The user's complete-repair request governs this update; the attached handoff's one-phase-per-session instruction was treated as reference material. No AGENTS.md was present in the uploaded tree. Original files were backed up before edits. The original 83 regression tests passed independently on Python 3.12.14/Linux.

## Verified causes and changes

1. **Cloud-dependent audio lifetime:** microphone and playback previously started only after a successful Gemini Live connect, inside its TaskGroup. Both now have independent lifetime supervisors and queues. Device exceptions retry locally without cancelling the provider session. Optional monitor/dashboard tasks are isolated. The microphone opens only after explicit activation/testing or a saved enabled wake/PTT preference; diagnostic frames are discarded locally.
2. **False sleeping/online status:** PTT release, provider failures and key setup previously wrote arbitrary SLEEPING/LISTENING states. Runtime state now uses a locked enum/transition table and capability priority. Key save reports configuration saved, not online. A provider connection requires the SDK's setup-complete acknowledgment. UI state, capability/device status and actual microphone frame activity are exposed in the existing Controls drawer.
3. **Provider errors misclassified:** bad-key INVALID_ARGUMENT previously disabled optional Live features before identifying auth failure; any 1007 could be mislabelled as invalid key. Classification now handles SDK HTTP and SDK-wrapped WebSocket errors, structured API_KEY_INVALID details, direct socket/TLS/timeouts and httpx transport errors. Explicit invalid auth stops retries. Retryable connection failures stop after six attempts; Retry Provider and credential updates restart deliberately. Handshakes have a 20-second deadline, not a 20-second session limit. No automatic provider/model replacement or VPN claim is made.
4. **PTT turn not finalized:** release now queues audio_stream_end after accepted PCM, with explicit 16 kHz MIME metadata. Qt fallback uses actual key press/release and focus-deactivation events instead of a timer that could release before keyboard auto-repeat. Windows retains one GetAsyncKeyState worker. Ctrl+Space can still conflict with VS Code/IME shortcuts; Windows polling does not consume the chord.
5. **Wake setup fragile:** runtime pip was removed. An explicit setup extra installs openWakeWord 0.6.0. The UI downloads only official ONNX resources to temporary storage, bounds sizes/timeouts, verifies them with ONNX Runtime, then publishes files atomically to `%LOCALAPPDATA%\Jarvis\wake-models`. A single-flight setup lock prevents duplicate UI downloads. Existing site-packages/user files are not deleted. Model startup/shutdown is serialized; prediction no longer treats another keyword's score as Jarvis. Detection pauses during speech/mute, with cooldown/model reset. Setup availability is distinct from a running detector.
6. **No independent audible diagnostic:** Windows SAPI can explicitly synthesize a WAV without an AI key. PCM is sent to the application's single selected playback queue rather than SAPI's default speaker. Synthesis and device playback failures are reported separately. STOP aborts the actual output stream, drains PCM/input queues, cancels tracked work and prevents late diagnostic synthesis from enqueueing after cancellation. The output supervisor reopens aborted/lost streams.

The exact Windows pip failure, OneDrive/file conflict, Windows privacy setting, account/model access and acoustic behavior remain **unconfirmed**. No phase1_evidence.json was provided. A safer model location mitigates the observed site-packages conflict without proving its cause.

## Supported behavior and limits

- Gemini Live remains the configured conversational STT, tool-routing and native-audio path. Existing tools, memory, plugins, credential vault, phone dashboard and avatar remain in place.
- Manual Start Listening opens a 30-second follow-up window by default. Speech and completed playback reset inactivity. Change the window in Controls; it applies after restart. PTT hold/release works independently; a wake activation opens the follow-up gate even when PTT is also enabled.
- No microphone frames are uploaded without a connected configured provider and an active manual/wake/PTT gate. Test Microphone consumes frames locally. A previous saved wake preference explicitly enables local wake monitoring; mute suppresses detection and upload.
- **Pretrained phrase is Hey Jarvis. Plain Jarvis is NOT implemented/verified.** A custom trained model and measured accuracy are required for that exact phrase. Manual/PTT activation remains available when the detector fails. A wake acknowledgment sound is not implemented.
- English/Hindi/Hinglish response preference is available. Transcription quality, accent coverage and multilingual command recognition are unmeasured with an account/microphone.
- Limited deterministic **typed** offline commands: `what time is it?`, `time kya hai`, `open Notepad`, `Notepad kholo`, `open Chrome`, `Chrome kholo`, optionally prefixed with Jarvis. Launch uses existing action validation and reports dispatch/window-unverified status. STOP remains local, including typed Jarvis stop. A dedicated Gemini stop_response tool interrupts work without shutting the app; shutdown requires an explicit exit/close request. Other offline commands are not invented.
- A separate full local STT/conversation/provider-switching pipeline is **not implemented**. Existing dormant STT/TTS/LLM modules are not advertised as working runtime providers. Gemini unavailable means spoken transcription is unavailable. No Whisper/Vosk models are downloaded automatically.
- Windows SAPI is an explicit Test Voice selection. Controls can opt into SAPI fallback for limited local text commands or a Gemini text reply with no audio. It cannot replace a failed physical output device or fabricate a missing AI response. SAPI voices/languages depend on Windows installation. `local_voice_name` may select an installed SAPI voice by its exact description through the safe settings API; a dedicated SAPI voice picker is not implemented.
- Existing input/output pickers persist device names safely. WASAPI streams request shared-mode conversion; default-device fallback and frame-stall recovery remain. All driver behavior requires Windows testing.
- No hardware latency guarantee: input blocks are 64 ms at 16 kHz, received PCM slices are about 50 ms, normal output batches are capped around 200 ms. STOP aborts output; acoustic stop latency and provider response latency require measurement. No offline Hinglish performance claim is made.

## Installation and launch (PowerShell / VS Code)

Close the existing app first. Back up the entire existing project privately, including configuration/credential ciphertext, memory, plugins and generated projects. Extract this source into a separate folder; merge only source files after reviewing the changed-file list. Preserve the current `.venv` and all user data. Do not copy the Linux test venv.

```powershell
Set-Location 'C:\Users\SAINI\OneDrive\Desktop\Jarvis'
# Use the existing Python 3.12 venv:
.\.venv\Scripts\python.exe setup.py
# Optional wake dependency installation (explicit, no runtime pip):
.\.venv\Scripts\python.exe setup.py --extras wake
.\.venv\Scripts\python.exe tools\diagnostics.py --voice
code .
.\.venv\Scripts\python.exe main.py
```

If `.venv` does not exist, create it first with `py -3.12 -m venv .venv`. Do not recreate/delete an existing environment as a repair shortcut. In VS Code select `Jarvis\.venv\Scripts\python.exe`. No PowerShell execution-policy changes or admin terminal are needed.

Use the existing Wake Word download button after installing the wake extra, then enable the feature. Do not expect dependency installation alone to download/verify a model. Windows dependency markers in openWakeWord exclude Linux-only tflite-runtime. A Linux cross-target pip resolution attempt evaluated that Linux marker and failed; it is **not** proof of successful Windows installation. The Windows package/runtime installation remains a manual check. Core Google SDK pin is unchanged at 2.29.0. New optional dependency file: `requirements/wake.txt` (openwakeword==0.6.0, onnxruntime>=1.17,<2); pywin32 was already a Windows core dependency.

To dismiss first-time AI setup and test local hardware without a key, choose **LOCAL AUDIO TESTS WITHOUT API KEY**. Controls provides Test Microphone, Test Voice, Start/Stop Listening, Retry Provider and Update Gemini Credential. Enter keys only in the local credential UI; DPAPI storage is preserved. Configure supported Gemini model access through the existing JARVIS_LIVE_MODEL environment setting only after verifying account support; no fallback changes it silently.

## Diagnostics

```powershell
# Readiness inventory only; no microphone capture/provider request:
.\.venv\Scripts\python.exe tools\diagnostics.py --voice
# Explicit local capture, synthesis/playback, wake initialization and key polling:
.\.venv\Scripts\python.exe tools\diagnostics.py --voice --mic-test 5 --tts-test --wake-test --hotkey-test
# Explicit Google Live handshake only; no microphone audio sent:
.\.venv\Scripts\python.exe tools\diagnostics.py --voice --provider
# Regression checks:
.\.venv\Scripts\python.exe setup.py --extras test
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Report: `voice_diagnostics.json`. PASS only establishes the stated check, never audible playback, speech identity, wake accuracy or command execution when only an import/handshake was tested. Hardware flags are opt-in. Default speaker voice test uses the saved selected output. Windows settings: Privacy & security > Microphone > enable microphone access and desktop app access; Sound > Input/Output > select/test intended devices. Check hardware mute, volume/mixer and exclusive-access apps before changing code. No permissions are changed automatically.

## Mandatory manual acceptance checklist

| Test | This environment | Windows check |
|---|---|---|
| 1 Startup | Offscreen real entry initialized/shut down, hardware/transport excluded | Launch exact main.py command; inspect provider/mic readiness independently |
| 2 Microphone | Mock PCM callback passed; real capture not tested | Test Microphone, speak, confirm meter and actual captured signal on selected device |
| 3 Voice output | SAPI unavailable on Linux; not tested | Test Voice; human confirms audible speech from selected output |
| 4 PTT | PCM/end marker ordering mocked; actual Qt press/release passed offscreen | Hold Ctrl+Space, say open Notepad, release; verify transcription, tool dispatch and speech |
| 5 Wake | Download/validation/publication mocked; no acoustic test | Say Hey Jarvis with initialized model; measure misses/false positives; plain Jarvis unsupported |
| 6 Windows command | Existing launcher regressions mocked | Notepad window actually opens within existing permission policy |
| 7 AI reply | SDK config/schema passed; provider not tested | Valid supported account, ask time/general question, hear reply |
| 8 Sleep recovery | State/manual recovery automated/mocked | Wait configured inactivity window, wake/manual/PTT again |
| 9 Invalid credentials | Mocked actual runtime: one auth attempt, no endless retry | Local mic/voice tests remain available; update local credential UI |
| 10 Network loss | Mocked actual runtime: six-attempt cap/cleanup | Disable/re-enable network, verify responsive HUD and deliberate Retry Provider |
| 11 STOP | Mock queue drain/output abort/cancel passed | Interrupt real voice promptly; no late speech; activate again |
| 12 Restart | Lifetime task cleanup mocked; offscreen shutdown passed | Close/relaunch, verify settings/device release/no duplicate hooks |

Do not mark primary voice acceptance complete until tests 2–8/11–12 are physically verified. A key/account restriction or missing exact wake model cannot be repaired by bypassing security or inventing success.

## Rollback

Keep the original uploaded source ZIP and private full-folder backup. Stop the app, restore only changed source/docs/requirements from the original source backup, and remove newly added source files listed in the change manifest if rolling back completely. Restore `.venv` from your own pre-install backup or use its previous dependency lock; do not delete user data. New config fields are additive and can remain, or be removed through `save_config`/a deliberate secure configuration migration. Wake resources in LOCALAPPDATA are separate; they do not overwrite original site-packages resources. Preserve all DPAPI files and matching credential references together. Never post your backup/credentials/memory publicly.
