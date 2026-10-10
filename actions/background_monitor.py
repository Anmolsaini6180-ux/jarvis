"""
BackgroundMonitor — user-configured topic watching.
Checks DDG news once per day per topic; alerts JARVIS when a new headline appears.
No crypto, no finance, no uninvited tracking.
"""
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path


# ── Blocked categories (never monitor regardless of what user says) ────────────

_BLOCKED = {
    # Brand / asset names — spelled the same in every language
    "bitcoin", "ethereum", "dogecoin", "solana", "binance",
    "nft", "blockchain", "defi", "altcoin", "memecoin", "coin", "token",
    # spellings of the "crypto" root across different languages
    "crypto", "kripto", "cripto", "krypto", "крипто", "仮想通貨", "暗号資産",
    "cryptocurrency",
}

def _is_blocked(topic: str) -> bool:
    tokens=set(re.findall(r'\w+',topic.casefold()))
    return bool(tokens & _BLOCKED)


# ── Slug / hash helpers ────────────────────────────────────────────────────────

def _slug(topic: str) -> str:
    import unicodedata
    normalized=unicodedata.normalize('NFKC',topic).casefold().strip()
    return 'topic_'+hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:24]

def _title_hash(title: str) -> str:
    return hashlib.md5(title.encode("utf-8", errors="ignore")).hexdigest()[:12]


# ── Memory I/O ─────────────────────────────────────────────────────────────────

def _load() -> dict:
    from memory.memory_manager import load_memory
    data = load_memory().get("monitors", {})
    return data if isinstance(data, dict) else {}

def _save(monitors: dict) -> None:
    from memory.memory_manager import MEMORY_PATH
    from core.storage import update
    update(MEMORY_PATH,lambda data:data.__setitem__('monitors',monitors))


# ── Public API ─────────────────────────────────────────────────────────────────

def add_monitor(topic: str) -> str:
    topic = topic.strip()
    if not topic:
        return "Please specify a topic to monitor."
    if _is_blocked(topic):
        return "I don't monitor crypto or financial topics."
    monitors = _load()
    slug = _slug(topic)
    for record in monitors.values():
        if _slug(record.get('topic',''))==slug:return f"Already monitoring: {record['topic']}"
    monitors[slug] = {
        "topic":      topic,
        "added":      datetime.now().strftime("%Y-%m-%d"),
        "last_check": "",
        "last_hash":  "",
    }
    _save(monitors)
    print("[Monitor] Monitor added; topic redacted")
    return f"Now monitoring: {topic}"


def remove_monitor(topic: str) -> str:
    topic = topic.strip().lower()
    monitors = _load()
    # exact slug match first
    slug = _slug(topic)
    if slug in monitors:
        label = monitors.pop(slug)["topic"]
        _save(monitors)
        return f"Stopped monitoring: {label}"
    # partial match fallback
    for key, val in list(monitors.items()):
        if topic in val.get("topic", "").lower():
            label = monitors.pop(key)["topic"]
            _save(monitors)
            return f"Stopped monitoring: {label}"
    return f"Not found in monitored topics: {topic}"


def list_monitors() -> list[str]:
    return [v.get("topic", k) for k, v in _load().items()]


def check_all() -> list[str]:
    """
    Run all pending topic checks (once per day per topic).
    Returns a list of [MONITOR_ALERT] strings — empty if nothing new.
    """
    from actions.web_search import _ddg_news

    monitors = _load()
    if not monitors:
        return []

    today   = datetime.now().strftime("%Y-%m-%d")
    alerts  = []
    changed = False

    for slug, data in monitors.items():
        if data.get("last_check") == today:
            continue                     # already checked today

        topic = data.get("topic", slug)
        try:
            results = _ddg_news(topic, max_results=5)
            if not results:
                monitors[slug]["last_check"] = today
                changed = True
                continue

            top   = results[0]
            title = top.get("title", "").strip()
            if not title:
                continue

            h = _title_hash(title)
            monitors[slug]["last_check"] = today
            changed = True

            if h == data.get("last_hash"):
                continue                 # same headline as last check — no alert

            monitors[slug]["last_hash"] = h

            snippet = top.get("snippet", "")[:150]
            source  = top.get("source", "")
            parts   = [f"[MONITOR_ALERT] {topic}", f"Headline: {title}"]
            if snippet:
                parts.append(snippet)
            if source:
                parts.append(f"Source: {source}")
            alerts.append("\n".join(parts))
            print("[Monitor] New headline found; private topic redacted")

        except Exception as e:
            print(f"[Monitor] Check failed: {type(e).__name__}; topic redacted")

    if changed:
        _save(monitors)

    return alerts


def _monitor_transaction(fn):
    from functools import wraps
    @wraps(fn)
    def run(*args,**kwargs):
        from memory.memory_manager import MEMORY_PATH
        from core.storage import transaction
        with transaction(MEMORY_PATH):return fn(*args,**kwargs)
    return run
add_monitor=_monitor_transaction(add_monitor)
remove_monitor=_monitor_transaction(remove_monitor)
check_all=_monitor_transaction(check_all)
