"""Explicit no-audio-upload REST/Live isolation using the runtime's exact setup."""
import argparse
import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.redaction import install
install()
from core.credential_input import validate_gemini_key
from core.live_config import api_version, probe_stages
from core.provider_errors import classify, connect_with_timeout

def runtime_config():
    import main
    from core.action_loader import discover_actions
    from core.plugin_loader import discover_plugins
    root = Path(__file__).resolve().parents[1]
    reserved = {d['name'] for d in main.TOOL_DECLARATIONS}
    actions = discover_actions(root/'actions', reserved, logger=lambda message: None)
    plugins = discover_plugins(root/'plugins', reserved | actions.names(), logger=lambda message: None)
    obj = SimpleNamespace(_action_registry=actions, _plugin_registry=plugins,
                          _resume_handle=None, _enhanced_live=True, _tuned_live=True, _diagnostic=True)
    obj._tuning_config = lambda: main.JarvisLive._tuning_config(obj)
    return main.JarvisLive._build_config(obj)

async def probe(client, model, config, seconds=20):
    """Each setup is independent. Stop at the first failed addition, no retries."""
    rows = []
    try:
        async with asyncio.timeout(seconds):
            await client.aio.models.get(model=model)
        rows.append({'check':'REST authentication/model metadata', 'status':'PASS',
                     'detail':'Metadata request succeeded; this does not establish Live access.'})
    except Exception as error:
        failure = classify(error)
        rows.append({'check':'REST authentication/model metadata', 'status':'FAIL',
                     'detail':failure.kind+': '+failure.message})
        # Model metadata can be unavailable even when a preview Live endpoint
        # exists. Never infer Live access from either outcome; probe it separately.
        if failure.kind in {'AUTH','FORBIDDEN','CREDENTIAL_FORMAT','QUOTA','DNS','TLS','TIMEOUT','NETWORK'}:
            return rows
    blocked = False
    previous_setup = None
    for label, setup in probe_stages(config):
        if blocked:
            rows.append({'check':label, 'status':'SKIPPED','detail':'Earlier setup failed; isolate it before adding more fields.'})
            continue
        try:
            async with connect_with_timeout(client, model, setup, seconds):
                pass
            rows.append({'check':label, 'status':'PASS','detail':'Actual Live setup acknowledgment; no speech/audio sent.'})
            previous_setup = setup
        except Exception as error:
            failure = classify(error)
            rows.append({'check':label, 'status':'FAIL','detail':failure.kind+': '+failure.message})
            blocked = True
            if label == 'tool declarations' and failure.kind == 'CONFIG' and previous_setup:
                # Bound connection count; report each rejected declaration instead
                # of silently disabling the entire tool registry in the application.
                from google.genai import types
                declarations = [d for t in setup.tools for d in (t.function_declarations or [])]
                for declaration in declarations[:32]:
                    single = previous_setup.model_dump(exclude_none=True)
                    single['tools'] = [{'function_declarations':[declaration]}]
                    try:
                        async with connect_with_timeout(client,model,types.LiveConnectConfig(**single),seconds):pass
                        rows.append({'check':'single tool '+declaration.name,'status':'PASS','detail':'Actual setup acknowledgment for this declaration.'})
                    except Exception as tool_error:
                        reason = classify(tool_error)
                        rows.append({'check':'single tool '+declaration.name,'status':'FAIL','detail':reason.kind+': '+reason.message})
                        if reason.kind != 'CONFIG':break
                if len(declarations)>32:
                    rows.append({'check':'remaining individual tools','status':'SKIPPED','detail':'32-declaration isolation limit; check remaining tools separately.'})
    return rows

async def run(network=False):
    from core.gemini import live_model
    model = live_model()
    config = runtime_config()
    rows = [{'check':'SDK setup serialization','status':'PASS',
             'detail':f'Actual pinned SDK; model={model}, api={api_version()}; no account claim.'}]
    # Serialization must execute, rather than just constructing a Python object.
    json.dumps(config.model_dump(mode='json', exclude_none=True))
    if not network:
        rows.append({'check':'REST/Live account probes','status':'SKIPPED','detail':'Use --network explicitly; no microphone audio is sent.'})
        return rows
    client = None
    try:
        from memory.config_manager import get_gemini_key
        key = validate_gemini_key(get_gemini_key())
        from google import genai
        client = genai.Client(api_key=key, http_options={'api_version':api_version(),'timeout':20000})
        rows.extend(await probe(client, model, config))
    except Exception as error:
        failure = classify(error)
        rows.append({'check':'Credential/client initialization','status':'FAIL','detail':failure.kind+': '+failure.message})
    finally:
        if client:
            await client.aio.aclose()
            client.close()
    return rows

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--network', action='store_true', help='Contact the configured Google account; may consume connection quota.')
    parser.add_argument('--out', default='live_probe.json')
    args = parser.parse_args()
    rows = asyncio.run(run(args.network))
    Path(args.out).write_text(json.dumps(rows, indent=2), encoding='utf-8')
    for row in rows:print(row['status']+': '+row['check']+' — '+row['detail'])
    return int(any(row['status']=='FAIL' for row in rows))

if __name__=='__main__':raise SystemExit(main())
