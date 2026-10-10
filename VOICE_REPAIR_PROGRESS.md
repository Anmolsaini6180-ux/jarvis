# Voice / AI / runtime repair — progress tracker

Update this file at the end of every phase. Status values: `DONE-VERIFIED` (automated test or real run, stated which), `DONE-MOCKED`, `NEEDS-WINDOWS-CHECK`, `IN-PROGRESS`, `PENDING`, `BLOCKED`.

Primary success criterion (from the owner): start Jarvis, activate listening by wake word or push-to-talk, speak a command, have it processed, hear a spoken reply, with the HUD showing what is really happening. Anything needing a real microphone/speaker/account must be reported as such, never as passed.

## Phase status

| Phase | Name | Status | Notes |
|---|---|---|---|
| 1 | Investigation | DONE-VERIFIED (source audit + Linux reproduction) | `docs/PHASE1_ROOT_CAUSE_REPORT.md`. Windows/account evidence still to be collected with `tools/phase1_probe.py`. |
| 2 | Foundation/state/errors/audio lifetime | DONE-MOCKED | Runtime integration, auth/no-retry, bounded retries and lifetime cleanup tested. |
| 3 | Microphone service/device test/meter | NEEDS-WINDOWS-CHECK | Independent supervised stream, verified-frame status, selected device, local test and recovery implemented in main.py. WASAPI shared conversion added; actual drivers unverified. |
| 4 | Wake/PTT/sleep/manual | NEEDS-WINDOWS-CHECK | Atomic verified ONNX setup and lifecycle, actual Qt key release, PTT stream end, 30-second window implemented. Plain Jarvis model still unsupported. |
| 5 | Output/local Test Voice | NEEDS-WINDOWS-CHECK | Single independent playback queue, abort/recovery, explicit Windows SAPI diagnostic/fallback implemented; SAPI and audibility untested on Windows. |
| 6 | Provider/credentials/fallback | DONE-MOCKED | Structured SDK errors, setup acknowledgment, 20-second handshake deadline, six-attempt cap, retry/update controls; valid provider/account access untested. Full local conversation/provider switching not implemented. |
| 7 | HUD integration | DONE-MOCKED | Real runtime/capability/device status and controls added; offscreen UI activation/key events passed. Physical meters/animations need Windows. |
| 8 | Diagnostics/tests/docs/ZIP | DONE-VERIFIED (Linux automation) | See docs/VOICE_RUNTIME_REPAIR.md and new TEST_RESULTS section; physical/account checks remain pending. |

### Order change (pushback on the original phase order)
The original order was mic → TTS → wake/sleep → AI → pipeline → HUD. The Phase 1 audit shows mic lifetime, SLEEPING and the error handler are all coupled to one cloud session and one string-based handler (RC-1…RC-3). Repairing mic/TTS first would mean rewriting them again when the state machine lands. Proposed order: **2 Foundation → 3 Mic → 4 Wake/PTT → 5 Output → 6 Provider → 7 HUD → 8 Diagnostics/tests/docs**. The owner may veto; if so, still do the Foundation items F1–F3 inside whichever phase comes first.

## Phase 2 — Foundation (details)

* **F1 `core/runtime_state.py`** — enum states `STARTING, INITIALIZING, SLEEPING, LISTENING, HEARING_SPEECH, PROCESSING, SPEAKING, RECONNECTING, ERROR, STOPPED, MIC_UNAVAILABLE, PROVIDER_UNAVAILABLE`; explicit allowed-transition table; one lock; subscriber callbacks marshalled to the Qt thread; rejects invalid transitions and logs the rejection. Replace every `ui.set_state("...")` string call in `main.py` (≈L718, 937, 1280-1300 region, 2217-2225, 2352, 2385 and the `set_speaking` / `wake` / `sleep` / `_on_ptt` paths) and `ui._on_setup_done` (≈L5624). Keep `_awake`, `_is_speaking`, `_ptt_held` as *derived* views or remove.
* **F2 `core/errors.py`** — `classify(exc) -> ProviderError(kind, retryable, user_message, detail)`. Unwrap `BaseExceptionGroup` recursively; classify by `google.genai.errors.APIError.code/status`, websocket close codes, `socket.gaierror`, `ssl.SSLError`, `PortAudioError`, `TimeoutError`; no substring matching on `str(exc)`. Kinds at minimum: `AUTH_INVALID_KEY, AUTH_FORBIDDEN, MODEL_UNAVAILABLE, CONFIG_REJECTED (incl. close 1007), QUOTA, NETWORK_DNS, NETWORK_TLS, NETWORK_TIMEOUT, MIC_FAILURE, SPEAKER_FAILURE, UNKNOWN`. Unit-test with real SDK error objects (see `tools/phase1_repro_error_order.py` for how to build them).
* **F3 reconnect handler rewrite in `JarvisLive.run()`** — no feature-flag poisoning (`_tuned_live`/`_enhanced_live` are per-attempt, restored after success or key/model change, and only dropped on `CONFIG_REJECTED`); auth errors stop retrying and go to `PROVIDER_UNAVAILABLE` + key dialog; bounded exponential backoff with jitter and an attempt cap that ends in a visible `ERROR`; remove the hard-coded "(a VPN may be required)"; mic/speaker failures become `MIC_UNAVAILABLE`/`SPEAKER_FAILURE` and **do not** tear down the session or loop silently; optional tasks (monitors, proactive, dashboard relay) must not be able to cancel mic/session tasks.
* **F4** remove the false "JARVIS online" at `ui.py::_on_setup_done`; readiness text must come from the state machine.
* Tests: transition table (valid/invalid), thread-safety (many threads), classifier table, backoff bounds, "auth error → no retry", "mic failure → session survives" with a fake mic and fake session.

## Phase 3 — Mic (details)
`core/mic_service.py` that owns the `sounddevice.InputStream` independent of the cloud session (ring buffer, RMS/peak meter, device selection persisted via `memory/config_manager.py`, reconnect on device loss, busy-device error classification, exclusive-mode/sample-rate fallbacks, frame-count verification). Session consumes frames from the service. Settings UI: show selected mic, **Test Microphone**, live meter. A mic is "working" only after real frames with non-zero level were received (hardware PASS needs a human speaking).

## Phase 4 — Wake word / PTT / sleep (details)
* Detector start result must drive state (`SLEEPING` only if wake detection is actually running; otherwise state says wake unavailable and PTT/Start Listening remain live).
* Add a **Start Listening** button independent of wake word. Configurable follow-up window (default 30 s, reset on user speech); replace hard-coded `WAKE_SLEEP_TIMEOUT = 120`.
* PTT: send `audio_stream_end`/activity-end (or trailing silence) on release so the server finalises the turn; remove the `SLEEPING` clobber in `_on_ptt`; keep PTT independent of wake word; avoid duplicate hooks; make the chord configurable if feasible.
* Wake installer: atomic download to temp + verify + rename; classify partial installs (`is_installed()` must not be `find_spec` alone); capture the full pip/stderr tail into the log file (redacted); single-flight lock against double clicks; never delete user-owned data; decide the OneDrive/`.venv` guidance from the probe result. See decision D2 for the phrase.
* Optional subtle acknowledgement sound, configurable.

## Phase 5 — Output (details)
Playback service independent of the session (single active stream, STOP interrupts promptly, device recovery); **Test Voice** that works without an API key; synthesis failure vs playback failure reported separately. Dead modules `core/tts.py` / `core/stt.py` are *not* wired today; decision D1 decides whether to use them or a Windows-native option.

## Phase 6 — Provider (details)
Use the probe's `provider` rows to decide: genuinely bad key vs rejected Live setup (model/API version/field). Credential-update UI path; no key in logs; model fallback only with owner consent (`JARVIS_LIVE_MODEL` exists); clear "AI unavailable" mode that still allows mic/speaker tests and typed input. No offline conversation claims.

## Phase 7 — HUD
Bind HUD to the state machine; add status chips (mic, speaker, wake, STT/TTS where applicable, provider, retry countdown), mic meter, Test Mic / Test Voice / Start/Stop Listening. Preserve the existing look (reactor core, face, colours).

## Phase 8 — Diagnostics / tests / docs / ZIP
Extend `tools/diagnostics.py` to the 20 checks in master prompt §15 with PASS/FAIL/SKIPPED/NEEDS_HUMAN (never PASS from mocks); add voice-path tests to the CI workflow; update `readme.md`, `WINDOWS_SETUP.md`, `CHANGELOG_REPAIRS.md`, `TEST_RESULTS.md`; produce a clean source ZIP without `.venv`, `config/api_keys.json`, `config/credentials/`, memory, caches.

## Open decisions for the owner (do not guess; ask)

| ID | Decision | Recommendation |
|---|---|---|
| D1 | Voice architecture. (a) Keep Gemini Live as the only conversational path and add small **local** diagnostics (mic meter, speaker tone, Windows-native Test Voice via `pywin32` SAPI, typed input). (b) Build a full local STT→router→TTS pipeline (new faster-whisper/Vosk + TTS + intent router; large; offline Hinglish quality unproven). | (a) first. (b) only after (a) works end to end. Offline "supported local commands" needs an intent router that does not exist yet. |
| D2 | Wake phrase. Pretrained model = "Hey Jarvis". Plain "Jarvis" needs a custom-trained openWakeWord model (training effort, accuracy to be measured). | Ship "Hey Jarvis" honestly now; treat "Jarvis" as a separate optional task. |
| D3 | Project location. `.venv` inside OneDrive Desktop is a suspected cause of WinError 183 and a general risk (sync locks, reparse points). | Move project + `.venv` to a non-synced path such as `C:\Dev\Jarvis` after backing up `config`, `memory`, `plugins`. Confirm with probe output first. |
| D4 | Follow-up window default (30 s) and acknowledgement sound on/off. | 30 s, sound off by default. |

## Inputs still needed from the owner
1. `phase1_evidence.json` from the command in `docs/PHASE1_ROOT_CAUSE_REPORT.md` §6.
2. Answers to D1–D4.
3. Whether `wake_word_enabled` / `push_to_talk_enabled` are meant to be on (the probe prints them).


## Current update (2026-10-10)

The current user's complete repair request supersedes the attached handoff's one-phase-per-session scope. Source changes were made across the necessary runtime phases; hardware/account-dependent acceptance remains incomplete. No phase1_evidence.json was supplied, so the specific Windows installer/device/account hypotheses remain unconfirmed.

Implemented architecture choice: keep Gemini Live for conversation; add explicit local SAPI/audio tests and a tiny exact typed-command fallback. No cloud provider was silently replaced. Pretrained Hey Jarvis remains labelled honestly; plain Jarvis is unsupported. Follow-up default is 30 seconds; acknowledgment sound is not implemented. Project/data/.venv were not moved or deleted.

See `docs/VOICE_RUNTIME_REPAIR.md` for verified causes, actual implementation, limitations, exact installation/launch/diagnostic commands, rollback and all twelve acceptance tests. `VOICE_CHANGED_FILES.txt` lists exact changed/new files. Windows microphone permissions, actual capture/audibility, wake accuracy, global PTT, bilingual STT, account/model access, local SAPI and physical restart/STOP still require validation.
