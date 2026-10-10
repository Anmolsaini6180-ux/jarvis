# Repair tracker

Source: uploaded `Mark-LV-main.zip`, SHA256 `10f8c2f7ac10505dc6337229fec2de3ab26c2884764df64eefea8b0330dabf48`. No AGENTS.md was present in the workspace/source. Audit findings are independently checked against source. Original source is committed as `59f65af`; repairs are on `repairs/mark-lv`.

| Finding | Source | Change | Verification | Remaining limitation | Status |
|---|---|---|---|---|---|
| Model project paths escape root | dev_agent.py write/fix | shared project_path rejects traversal/absolute/links/Windows ambiguities; plan validation | Phase 1 path tests | local malicious filesystem races not an OS boundary | fixed |
| Rename validates only source | file_controller.py rename_file | basename plus final destination validation | baseline regression now passes | Windows junction hardware smoke pending | fixed |
| Copy collisions and lost originals | file_controller.py copy_file | reject collisions, atomic file creation | baseline collision test passes | directory copy failure can leave partial output, reported | mitigated |
| Undo destroys later edits | core/undo.py; file_controller.py | hashes/mtime and conflict-aware recovery | baseline and move conflict tests | settings undo needs separate review | partially fixed |
| Large writes without recovery | core/safe_files.py | disk snapshot before atomic replacement, failure aborts | >1 MB restore and backup-failure tests | recovery data needs user backup/retention | fixed |
| Generated code has host access | dev_agent/code_helper/file_processor | optional Docker-only runner; never host fallback | unavailable runner and trusted fixture subprocess tests | real Docker/Windows not tested; read-only project runner | mitigated |
| Desktop restricted exec bypass | desktop.py | typed JSON interface; no exec/eval | real typed create and rejected Python tests | only supported typed tools available | fixed |
| Return code / timeout false success | core/execution.py and code runners | structured outcomes, no functional success inference | exit 7, timeout, cancellation, success-unverified tests | GUI/server functional checks depend on actual project | fixed |
| Dependency mutation / import guessing | dev_agent.py | pinned proposal, explicit review, project .venv instructions | subprocess not invoked by proposals | automatic isolated dependency installation not implemented | mitigated |
| Quoting/dependency order | execution.py; dev_agent.py | shlex argv and topological sort | quoted args and ordering tests | JS/npm dependency pipeline limited | fixed |
| Screenshot code silently applied | code_helper.py | analysis only, explicit edit needed | source inspection | visual interpretation needs cloud account | fixed |
| Archive traversal/links/bombs | core/archives.py; file_processor.py | new destination, staging, member/byte/ratio limits | traversal/TAR links/limits/normal extraction tests | ZIP/TAR only; no 7z/RAR adapter | fixed |
| Missing verified WhatsApp driver / blind send | send_message.py | usable draft; explicit verified-adapter contract; recipient/content HUD confirmation | fake adapters, missing driver and identity-change tests | no real verified platform adapters bundled | mitigated |
| Revocation retains bearer/WS | dashboard/server.py | invalidate tokens, close sockets, clear queues and keys | ASGI HTTP and WebSocket revocation tests | LAN/device/cert trust smoke pending | fixed |
| Session lifecycle, bounds, rate limits | dashboard/server.py; dashboard_security.py | 1h sessions, logout, pairing rate, bounded queues/body/WS/upload | expiry, queue, pairing, upload tests | full internet exposure not supported | fixed |
| HTTP fallback/firewall elevation | dashboard/server.py | TLS-only fail closed, explicit local UI activation, no network mutations | certificate failure test + source review | OS certificate trust and firewall remain manual | fixed |
| Receive awaits tools / cancellation / audio | main.py; core/tasks.py | implementation in progress | pending | pending | unresolved |
| Persistence / credentials / reminders / monitoring | memory; actions/reminder.py | implementation in progress | pending | pending | unresolved |
| Browser/document/XML/offline/claims/setup | remaining integrations | implementation in progress | pending | pending | unresolved |
