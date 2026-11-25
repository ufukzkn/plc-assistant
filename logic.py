import struct
from cikis import decode, words

def addr(a,v):
    if a==0x12:return {0x400f:'P_ON',0x400e:'P_OFF'}.get(v)
    if a==3 and 0xe000<=v<=0xefff:return f'T{v-0xe000:04d}'
    if a==4:return f'CIO{v//16}.{v%16:02d}'
    if a==5:
        if 0x8000<=v<0x8400:return f'H{(v-0x8000)//16}.{v%16:02d}'
        if 0xe000<=v<0xe600:return f'W{(v-0xe000)//16}.{v%16:02d}'

def extract(b, rows=None):
    if rows is None:
        rows = decode(b)
    targets={int(r[2],16):r for r in rows}; result={}; start=0x8c0; shared=None
    for index, (op, v) in words(b):
        i = 0x8c0 + index * 4
        if (op,v)==(0x2400,0):start=i+4; shared=None
        if i not in targets:continue
        r=targets[i]; commands=[]; j=start
        # Reference-confirmed shared P_ON branch encoding for simple OUT rungs.
        if r[1]=='OUT' and i-j==12 and b[j:j+8]==bytes.fromhex('e212400ffa122000') and b[j+8:j+10] in (bytes.fromhex('e244'),bytes.fromhex('e243')):
            shared=[('LD','P_ON')]; commands=shared.copy(); j+=8
        elif r[1]=='OUT' and i-j==8 and b[j:j+4]==bytes.fromhex('e2122000') and shared is not None and b[j+4:j+6] in (bytes.fromhex('e244'),bytes.fromhex('e243')):
            commands=shared.copy(); j+=4
        else:shared=None
        while j<i:
            o,w=struct.unpack_from('>HH',b,j); raw=b[j:j+4].hex(' '); a=addr(o&31,w)
            if o==0xe340 and w==0:commands.append(('ORLD',''))
            elif o==0xe320 and w==0:commands.append(('ANDLD',''))
            elif o>>8==0xe2 and a and (o&0xe0) in (0,32,64,96,128):commands.append(({0:'LD',32:'LDNOT',64:'AND',96:'ANDNOT',128:'OR'}[o&0xe0],a))
            elif o>>8==0xe2 and a and o&0xe0==192 and b[j+4:j+12] in (bytes.fromhex('cb800000c2525002'),bytes.fromhex('cba00000c2525002')):
                # Second pattern is an inferred edge variant; never infer its live state.
                commands.append(('@AND' if b[j+4]==0xcb and b[j+5]==0x80 else '%AND?',a));j+=8
            else:commands.append(('?',raw))
            j+=4
        result[r[2]]=commands
        start=i+(12 if r[1] in ('TIM','MOV') else 4)
    return result

def evaluate(commands,values):
    def AND(a,b):return 0 if 0 in (a,b) else 1 if a==b==1 else None
    def OR(a,b):return 1 if 1 in (a,b) else 0 if a==b==0 else None
    stack=[]
    for op,a in commands:
        if op=='?':return None
        v=1 if a=='P_ON' else 0 if a=='P_OFF' else values.get(a)
        if op in ('LDNOT','ANDNOT'):v=None if v is None else 1-v
        if op in ('LD','LDNOT'):stack.append(v)
        elif op in ('ANDLD','ORLD'):
            if len(stack)<2:return None
            b=stack.pop();stack[-1]=(AND if op=='ANDLD' else OR)(stack[-1],b)
        elif stack:stack[-1]=(OR if op=='OR' else AND)(stack[-1],None if op in ('@AND','%AND?') else v)
        else:return None
    return stack
