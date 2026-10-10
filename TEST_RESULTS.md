# Actual verification results

Baseline: `python -m compileall -q .` passed for the 49 original Python modules. This does not validate imports, GUI or integrations. `python -m unittest discover -s tests -v` initially ran 3 disposable-file probes: **all 3 failed** (rename escape, copy collision, undo overwrote newer data). Original source is preserved in baseline commit.

Phase 1: `python -m unittest discover -s tests -v` ran **24 tests, passed, zero skips**. Temporary files, archives and trusted local subprocess fixtures exercised real I/O/exit 7/timeout/cancellation. No generated project was executed on the host. Docker unavailable path was exercised; no real container isolation claim.

Phase 2: cumulative suite ran **37 tests, passed, zero skips**. FastAPI/Starlette TestClient exercised real ASGI HTTP/WebSocket handlers with in-memory transport; no listening remote service, real account or real message. Fake messaging adapters verify preview gate, recipient recheck and accepted-state reporting. Certificate failure is mocked; TLS serving is refused. Upload/request/queue/rate limits are exercised.

Hardware/API tests remain separate from these regression tests. Windows GUI/audio, real browser profiles, OS keychain and Gemini account behavior have not been measured on this Linux cloud machine.
