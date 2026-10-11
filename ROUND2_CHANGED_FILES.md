# Round 2 modified/new files

All source changes are incremental. No dependency version changed. Existing secure data stores are not included.

- `.github/workflows/repair-regressions.yml`
- `.gitignore`
- `INSTALL_WINDOWS.ps1`
- `REPAIR_STATUS.md`
- `ROUND2_README_FIRST.md`
- `RUN_WINDOWS.ps1`
- `TEST_RESULTS.md`
- `WINDOWS_SETUP.md`
- `core/audio_devices.py`
- `core/audio_handoff.py`
- `core/credential_input.py`
- `core/live_config.py`
- `core/provider_errors.py`
- `core/redaction.py`
- `core/wake_word.py`
- `dashboard/server.py`
- `dashboard/static/app.html`
- `docs/ROUND2_REPAIR_REPORT.md`
- `docs/SDK_VERIFICATION.md`
- `docs/SOURCE_AUDIT_INVENTORY.json`
- `docs/VOICE_RUNTIME_REPAIR.md`
- `docs/WINDOWS_ACCEPTANCE_ROUND2.md`
- `docs/round2-results/baseline-tests.txt`
- `docs/round2-results/crypto-interop.txt`
- `docs/round2-results/final-tests.txt`
- `docs/round2-results/js-smoke.txt`
- `docs/round2-results/live-probe-local.json`
- `docs/round2-results/live-probe-local.txt`
- `docs/round2-results/runtime-smoke.txt`
- `docs/round2-results/sdk-smoke-final.txt`
- `docs/round2-results/ui-smoke-final.txt`
- `main.py`
- `memory/config_manager.py`
- `readme.md`
- `tests/test_phase2.py`
- `tests/test_phase4.py`
- `tests/test_round2.py`
- `tests/test_voice_runtime.py`
- `tools/check_dashboard_crypto.py`
- `tools/live_probe.py`
- `tools/smoke_ui.py`
- `tools/voice_diagnostics.py`
- `ui.py`

Main repairs: main.py integrates compatibility, lifecycle, callback handoff, transcript handling and proactive/wake states; ui.py validates keys and displays truthful states; credential_input/live_config/audio_handoff are new focused modules. Dashboard server/page update authentication, message integrity and phone PCM. Original regression tests remain, with updated secure-protocol fixtures and realistic deferred-capture timing. test_round2.py adds 21 meaningful checks. Documentation/results, CI, opt-in provider/crypto diagnostics and external-venv scripts are added/updated.
