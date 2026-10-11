# Windows/account acceptance — Round 2

All physical/account rows start UNVERIFIED. Record date, OS/Python, sanitized device names, selected model/API version and result; never include credentials or private conversation audio. Use PASS only after the stated actual outcome; FAIL for an executed failure, SKIPPED for an unrun test. NEEDS_HARDWARE/NEEDS_ACCOUNT designate required validation.

| Check | Procedure and required evidence | Current status |
|---|---|---|
| Startup | Launch via external venv; HUD remains responsive and reports independent readiness, not healthy online solely from init. | NEEDS_HARDWARE |
| Key format/storage | Enter a dummy curl/header paste; rejected without crash/network. Save a legitimately issued single key; restart under the same Windows user; verify protected storage/load, never log it. | NEEDS_ACCOUNT / NEEDS_WINDOWS |
| SDK/Live isolation | Run local probe then explicit --network; REST and acknowledged Live stages report independently. Find first failing addition; do not infer Live from TCP/REST success. | NEEDS_ACCOUNT |
| Mic consent | Fresh settings without wake/PTT: input enumeration must not open capture. Click Test Microphone; choose actual input and speak; frames/peak/live meter respond. No uploads during diagnostic. | NEEDS_HARDWARE |
| Mic formats/noise | Silence, normal/long speech, noisy room, mute/unmute; inspect actual 16 kHz mono PCM and overflow/drop counters. Increasing counters require different device/API and a recorded comparison. | NEEDS_HARDWARE |
| Device recovery | Disconnect USB/Bluetooth, reconnect/change default device; app reports actual fallback name and recovers without duplicated workers/handles. | NEEDS_HARDWARE |
| Test Voice | Click local SAPI Test Voice without API key; human confirms selected speaker and intelligible speech. Synthesis/output-write success alone is insufficient. | NEEDS_HARDWARE |
| PTT | Enable Ctrl+Space; hold, speak and release with app focused and another app focused; visible capture, ordered stream-end, usable transcript and actual permitted action. | NEEDS_HARDWARE / NEEDS_ACCOUNT |
| Wake | Explicitly install dependency/download verified ONNX resources; enable; READY alone must not claim running. Say Hey Jarvis; immediate activation, configured follow-up expiry/re-wake; mute/playback should gate detection. Log false positives/misses. | NEEDS_HARDWARE |
| Real voice commands | Try open Notepad, time, Chrome, YouTube and Hinglish volume request; verify actual outcomes/permission gates, not strings. Local offline typed commands are limited; offline STT is unavailable. | NEEDS_ACCOUNT / NEEDS_HARDWARE |
| AI/audio | Ask English, Hindi and Hinglish questions; transcript reaches session, response audio heard once on chosen output, avatar follows playback; no perfect-accent claim. | NEEDS_ACCOUNT / NEEDS_HARDWARE |
| STOP | Interrupt long speech by button/Escape/PTT as appropriate; physical audio and queued actions stop, Jarvis stays running; next interaction succeeds. Hands-free voice barge-in is not claimed. | NEEDS_HARDWARE / NEEDS_ACCOUNT |
| Bad auth/network | Use mocked regressions for invalid key/1007; do not intentionally disclose a real invalid key. Temporarily disconnect your network; bounded retries and explicit Retry Provider work; local diagnostics stay available, stale session/audio not reused. | NEEDS_HARDWARE / NEEDS_ACCOUNT |
| Restart/memory | Restart twice; approved preferences/memory/plugins/reminders/credentials remain, one worker per subsystem, no stale mic lock. Existing automated memory/security tests use disposable data. | NEEDS_HARDWARE |
| Proactive | Check-ins off unless opted in. Enable deliberately; verify quiet hours (default 22–08), mute/sleep and playback suppress them. Existing opt-in reminders must still deliver. | NEEDS_HARDWARE / NEEDS_ACCOUNT |
| Phone security | Update/reload phone page; pair on trusted LAN via verified TLS certificate. Test text, file upload/download, PCM, reconnect, logout/revoke/expiry. Bearer token must be absent from WS/download URLs; one-use ticket closes on replay. No public exposure or TLS bypass. | NEEDS_HARDWARE |
| Automation/security | Run existing regressions, then permitted browser/app/file actions and generation in approved workspace. Confirmation required for consequential operations; verify user-facing outcome. | NEEDS_HARDWARE |
| Windows CI | Execute workflow on actual Windows 10/11/Python 3.12; offscreen GUI smoke does not validate physical hardware. | SKIPPED |

Acceptance is pending until required rows are physically/account-verified. Attach sanitized probe reports only. The source ZIP contains no account access or local/private models.
