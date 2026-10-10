# Repair changelog

Applies to the uploaded original Mark LV ZIP (SHA256 `10f8c2f7ac10505dc6337229fec2de3ab26c2884764df64eefea8b0330dabf48`). Work is isolated on branch `repairs/mark-lv`; original source is retained in baseline commit `59f65af`. No AGENTS.md was found. Attached audit instructions were treated as evidence to verify, not as authorization independent of the user's repair request.

## Phase 1: file safety and truthful execution

Introduced shared scope/path validation, Windows filename checks and link/junction/reparse rejection. Default automatic scope is `Documents/JarvisWorkspace`; file selection grants one file, and broader task folders need a local HUD grant. Existing configuration, credentials, memory, plugins and assistant control files are protected from model file operations. Legacy projects are not relocated/deleted; explicitly select their project folders.

Copy/move/rename/create collisions preserve existing destinations. Explicit edits use atomic replacement and disk-backed snapshots; backup failure aborts the write even for large content. Directory copies stage before publication; large file copies/restores stream with bounded memory and verify pre-publication conflicts. Undo checks content/mtime and reports conflicts instead of deleting newer work. Recovery manifests/copies survive restart; the undo callback stack does not. Existing backups are not garbage-collected automatically.

Generated desktop Python `exec` was replaced by a typed JSON file-action interface. Code runners return status/exit code/stdout/stderr/timeout/cancellation/duration and do not infer success from output keywords. Optional Docker execution uses reviewed digest-pinned local images and restricted disposable mounts; missing isolation never falls back to host execution. Read-only/network-free runners cannot verify GUI/server/persistent-output applications. Successful exits remain functionally unverified.

Development dependencies become exact-version distribution proposals for review. Automatic pip mutation/import-name guessing is removed; manual project environments remain distinct from the assistant venv. Quoted argv and topological dependency ordering replace unsafe command/path assumptions. Missing generated files produce a partial-generation report before execution. Generic app launching refuses workspace executables/scripts; generated projects are reviewed before manually opening an IDE, whose extensions can execute host code. Screenshot analysis does not apply arbitrary extracted code. Screenshots/reports use scoped outputs; URL wallpaper downloads are bounded. Desktop command failures are checked; native settings actions without target verification explicitly say unverified. Volume fallback now attempts an actual bounded keyboard level change instead of two mute presses; Windows scalar volume read/write and conflict-aware settings undo require real-device checking.

ZIP/TAR extraction stages into a new destination, rejects traversal/absolute/link/device/encrypted/case-collision members and enforces source/member/decompression/count/ratio budgets. Other archive adapters are explicitly unavailable.

## Phase 2: messaging and remote control

Preserved a usable draft workflow and introduced a verified messaging-adapter contract. Integrated sends require a unique stable recipient, complete plain-text/scrollable local HUD preview and recipient recheck immediately before sending. Attempted/accepted/delivered/read are separate receipt-based states. No verified real driver ships, so current WhatsApp/other requests honestly report draft/send-unavailable; blind keystrokes were removed.

Confirmations cannot replace an unrelated pending action, have an expiry, preserve the entire review body and are cancelled before acquiring the mutation slot if STOP was requested. Local UI approval is not a model parameter.

Dashboard activation is explicit from the local UI. Serving is TLS-only; invalid certificates fail closed. No automatic firewall/elevation/network-policy changes; insecure-browser flag instructions were removed and HTML attribute encoding hardened. Sessions expire, logout/revocation close active WebSockets, authorization is rechecked during long-lived connections, device/session counts and pairing attempts are bounded. Command/audio queues, body/WS/upload sizes are bounded, malformed inputs fail cleanly, uploads reject reserved paths and collisions. Manual URLs no longer refer to a removed port alias. Pairing is process-scoped, not durable account management; all paired clients remain privileged.

## Phase 3: responsiveness and cancellation

Added task IDs, bounded FIFO mutation queue, progress, recent status/history and STOP/CANCEL/Escape in the existing HUD. Reception submits work without awaiting long execution; separate ordered response delivery preserves tool-call IDs and refuses stale/reconnected session results. Cancellation returns responses for queued calls, drains queued work even after history eviction, reaches executor contexts and multi-step path/dev checkpoints, and terminates trusted subprocess trees/optional containers.

Uncooperative Python/library calls retain their mutation slot until returning and are marked stalled; no forced thread-kill or instant-stop guarantee is claimed. Native text typing/waits are cooperative between bounded chunks. Audio buffers are bounded and shutdown signals workers/confirmations/media/dashboard resources instead of calling `os._exit`. Missing PortAudio permits UI/text input while accurately reporting local audio unavailable.

The local speaking guard remains. Existing echo-tail filtering is heuristic, and full duplex barge-in is not implemented/verified. Manual stop remains the practical interruption control. The evaluated AEC/VAD design and hardware test boundary are documented.

## Phase 4: durable state and migration

Settings, memory and monitor mutations use atomic locked transactions across threads/local processes, with backups. Damaged state is recovered visibly from a valid backup while retaining the damaged copy; no valid backup raises an explicit error. Existing unrelated settings are merged/preserved.

Credentials use current-user Windows DPAPI or an allowed native macOS/Linux keyring. Plaintext migration protects/verifies full prior settings and backup before replacing fields with credential references. Migration backup names are installation-specific and immutable; `config/credential_migrations.json` records their references/status. Credential readers share the resolution API. Native backend failure preserves legacy plaintext with a warning, refuses new plaintext and does not silently reset the configuration. DPAPI ciphertext is account-bound and should be backed up with its references.

Diagnostic streams redact known credentials/patterns; console tool arguments/results, private message bodies, memory values and monitoring topics are not printed. Intended UI transcript/draft/content remains visible to the user. Redaction is best-effort for arbitrary unknown secrets; personal memory/reminders/recovery files are not encrypted by this change.

Reminders get UUID IDs, timezone-aware persisted records and registered/failed states. Scheduler errors are reported; actual OS notifications are not claimed from mocks. Explicit ambiguous/nonexistent DST times require an offset. Existing saved Unicode monitors are matched by normalized topic before adding SHA256-based identifiers; substring false positives were removed.

Core and optional dependencies are separate, setup is project-relative/venv-only, runtime auto-install APIs now provide diagnostics, and a tested Linux dependency snapshot is supplied. No Windows lock/native-library readiness claim is made.

## Phase 5: integration accuracy

Browser operations disclose controlled profile/tab, verify input readback and optional expected URL/text. Chromium uses a dedicated profile following Playwright guidance; launch-only and business outcomes remain unverified. Weather clearly reports search-only behavior.

Documents use bounded chunking with source/page/slide references and explicit coverage. Large code edits refuse partial-file patches. Safe XML parsing replaces JSON routing. Runtime tool/plugin arguments are validated before effects; actual SDK declarations are checked.

Plugin review happens before importing the whole hashed Python bundle, including helper changes. Trusted plugins retain account privileges, so import failure handling is not described as sandboxing. Original inactive local model/STT/TTS files remain; offline conversation is clearly not implemented. REST text generation replaces automatic audio-transcription code output and unverified model ladders. Official-source/model/SDK verification evidence is documented without quota/price claims.

Added lightweight-mode and English/Hinglish preference controls, refreshed prompts/README, targeted regression suite and Windows/Linux CI definitions. The existing application was extended; no Android/learning/business rewrite was added.

## Migration precautions and rollback

Close the old app and privately back up application/data/browser-profile/project/reminder folders first. Extract repaired source separately, then merge existing data without restoring old application modules over repairs. See WINDOWS_SETUP.md. Never delete a damaged config or recovery copy to suppress an error.

To roll back, use the preserved original source with a compatible private **pre-migration** data backup. Old code cannot understand new `$credential` references; do not point it at migrated settings expecting plaintext keys. Re-enter/recover credentials securely under the appropriate OS account. Keep the repaired migration/recovery backups until you decide they are no longer needed.


## Voice runtime update (2026-10-10)

Read [Voice runtime repair and Windows acceptance](docs/VOICE_RUNTIME_REPAIR.md) before using older voice guidance above. Audio lifetime, provider classification, PTT finalization, state/HUD controls and explicit SAPI diagnostics were changed. Wake dependencies now install through `setup.py --extras wake`; the UI downloads verified ONNX models and never invokes runtime pip. The supported pretrained phrase is **Hey Jarvis**, not plain Jarvis. Conversation remains Gemini Live; a limited typed local command fallback does not provide offline speech transcription/conversation. Physical Windows/audio/provider acceptance is pending. Exact changed files are in `VOICE_CHANGED_FILES.txt`.
