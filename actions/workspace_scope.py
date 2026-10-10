"""User-approved file scope request. The model cannot approve itself."""
from core import path_policy, confirm

def workspace_scope(parameters, **kwargs):
    raw=parameters['path'];directory=parameters.get('directory',False)
    try: path_policy.validate_spelling(raw)
    except Exception as e:return f'Invalid scope: {e}'
    return confirm.request('file-scope','Approve file workspace',
        f'{raw}\nAccess: {"folder and descendants" if directory else "this file only"}. Session-only; assistant credentials remain protected.',
        lambda:f'Approved scope: {path_policy.grant(raw,directory=directory)}')
TOOL={'name':'workspace_scope','description':'Request HUD approval for a specific file or project folder. Cannot grant home/system/sensitive scopes. Approval is session-only.',
      'parameters':{'type':'OBJECT','properties':{'path':{'type':'STRING'},'directory':{'type':'BOOLEAN'}},'required':['path']},'handler':workspace_scope}
