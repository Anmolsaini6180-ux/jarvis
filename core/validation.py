"""Strict runtime argument checking for tool and plugin declarations."""
def validate_arguments(value,schema,path='parameters',depth=0):
    if depth>20:raise ValueError(f'{path}: argument nesting limit exceeded')
    if not isinstance(schema,dict):raise ValueError(f'{path}: invalid declaration')
    kind=str(schema.get('type','OBJECT')).upper()
    types={'OBJECT':dict,'ARRAY':list,'STRING':str,'INTEGER':int,'NUMBER':(int,float),'BOOLEAN':bool}
    expected=types.get(kind)
    if expected is None:raise ValueError(f'{path}: unsupported schema type {kind}')
    if not isinstance(value,expected) or (kind in {'INTEGER','NUMBER'} and isinstance(value,bool)):
        raise ValueError(f'{path}: expected {kind}')
    if kind=='NUMBER':
        import math
        if not math.isfinite(value):raise ValueError(f'{path}: finite number required')
    if 'enum' in schema and value not in schema['enum']:raise ValueError(f'{path}: invalid enum value')
    if kind=='OBJECT':
        if len(value)>1000 or any(not isinstance(k,str) for k in value):raise ValueError(f'{path}: invalid/oversized object')
        props=schema.get('properties',{})
        missing=set(schema.get('required',[]))-set(value)
        unknown=set(value)-set(props)
        if missing:raise ValueError(f'{path}: missing {sorted(missing)}')
        additional=schema.get('additionalProperties')
        if unknown and not additional:raise ValueError(f'{path}: unknown {sorted(unknown)}')
        for k,v in value.items():validate_arguments(v,props.get(k,additional),path+'.'+k,depth+1)
    elif kind=='ARRAY':
        if len(value)>1000:raise ValueError(f'{path}: too many items')
        for i,v in enumerate(value):validate_arguments(v,schema.get('items',{'type':'STRING'}),f'{path}[{i}]',depth+1)
    elif kind=='STRING' and len(value)>100_000:raise ValueError(f'{path}: input too long')
