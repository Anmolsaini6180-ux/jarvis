"""Model-specific Live configuration, shared by runtime and opt-in probes.

Capability evidence: official Gemini 3.1 model and Live capabilities pages,
checked 2026-10-11. A schema-valid setup is not a verified account handshake.
"""
from copy import deepcopy
from dataclasses import dataclass
import os
import re
from google.genai import types

@dataclass(frozen=True)
class Capabilities:
    proactive: bool = False
    thinking: str = ''
    async_tools: bool = False

def capabilities(model):
    name = model.removeprefix('models/')
    if name == 'gemini-3.1-flash-live-preview':
        return Capabilities(thinking='level')
    if name.startswith('gemini-2.5-flash-native-audio'):
        return Capabilities(proactive=True, thinking='budget', async_tools=True)
    # Unknown models use a conservative setup until individually verified.
    return Capabilities()

def api_version():
    version = os.environ.get('JARVIS_LIVE_API_VERSION', 'v1beta').strip()
    if version not in {'v1beta', 'v1alpha'}:
        raise ValueError('JARVIS_LIVE_API_VERSION must be v1beta or v1alpha')
    return version

def validate_schema(schema, depth=0):
    """The SDK accepts unknown type strings; reject them before serialization."""
    if not isinstance(schema, dict) or depth > 20:
        raise ValueError('Invalid or too deeply nested tool schema')
    kind = schema.get('type', '')
    if kind not in {'OBJECT', 'ARRAY', 'STRING', 'INTEGER', 'NUMBER', 'BOOLEAN', 'NULL'}:
        raise ValueError('Unsupported tool schema type')
    if kind == 'OBJECT':
        props = schema.get('properties', {})
        required = schema.get('required', [])
        if not isinstance(props, dict) or len(props)>1000 or not isinstance(required,list) or any(not isinstance(k,str) or k not in props for k in required):
            raise ValueError('Invalid properties or required fields')
        for value in props.values():validate_schema(value, depth+1)
        extra = schema.get('additionalProperties', schema.get('additional_properties'))
        if isinstance(extra, dict):validate_schema(extra, depth+1)
    if kind == 'ARRAY':validate_schema(schema.get('items'), depth+1)

def compatible_declarations(declarations, model, notify=lambda message: None):
    """Validate each declaration separately; keep supported tools available."""
    out = []
    seen = set()
    for declaration in declarations:
        name = 'unnamed'
        try:
            d = deepcopy(declaration if isinstance(declaration, dict) else declaration.model_dump(exclude_none=True))
            name = d.get('name', 'unnamed')
            if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,63}', name) or name in seen:
                raise ValueError('Invalid or duplicate name')
            if not capabilities(model).async_tools:
                d.pop('behavior', None)
            if 'parameters' in d:validate_schema(d['parameters'])
            obj = types.FunctionDeclaration(**d)
            out.append(obj.model_dump(exclude_none=True))
            seen.add(name)
        except (ValueError, TypeError):
            # Exception messages can contain plugin schema/private data.
            notify('Tool declaration isolated: ' + str(name)[:64] + '; invalid SDK schema/name.')
    return out

def compatible_config(config, model, notify=lambda message: None):
    cfg = deepcopy(config)
    cap = capabilities(model)
    if not cap.proactive:
        cfg.pop('proactivity', None)
        cfg.pop('enable_affective_dialog', None)
    if cfg.get('thinking_config'):
        if cap.thinking == 'level':
            cfg['thinking_config'] = types.ThinkingConfig(thinking_level='LOW')
        elif not cap.thinking:
            cfg.pop('thinking_config', None)
    for tool in cfg.get('tools', []):
        if isinstance(tool, dict) and 'function_declarations' in tool:
            tool['function_declarations'] = compatible_declarations(tool['function_declarations'], model, notify)
    cfg['tools'] = [t for t in cfg.get('tools', []) if not isinstance(t, dict) or t.get('function_declarations')]
    if not cfg['tools']:
        cfg.pop('tools', None)
    return types.LiveConnectConfig(**cfg)

def probe_stages(config):
    """Cumulative isolation steps using the application's effective setup."""
    data = config.model_dump(exclude_none=True)
    current = {'response_modalities': data['response_modalities']}
    yield 'minimal Live setup', types.LiveConnectConfig(**current)
    groups = [('audio voice', ['speech_config']),
              ('transcription', ['input_audio_transcription', 'output_audio_transcription']),
              ('system instruction', ['system_instruction']),
              ('tool declarations', ['tools']),
              ('resumption/compression', ['session_resumption', 'context_window_compression'])]
    for name, keys in groups:
        added = {key: data[key] for key in keys if key in data}
        if added:
            current.update(added)
            yield name, types.LiveConnectConfig(**current)
    for key in sorted(set(data) - set(current)):
        current[key] = data[key]
        yield 'optional ' + key, types.LiveConnectConfig(**current)
