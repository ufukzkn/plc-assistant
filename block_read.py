"""Bounded, read-only FINS 0101 batching. Preserve the old single-item response API."""
import re
from collections import defaultdict
from functools import lru_cache
MAX_ITEMS=16
# Small gaps may be read to avoid a separate USB round trip.
MAX_STEP=3
PATTERN=r'0101(B0|B1|B2|B3|82|09|89)([0-9A-F]{4})00([0-9A-F]{4})'

@lru_cache(maxsize=4096)
def fields(cmd):
    m=re.fullmatch(PATTERN,cmd)
    if not m:raise ValueError('Salt okunur FINS komutu gerekli')
    area=m[1];start=int(m[2],16);count=int(m[3],16);end=start+count-1
    if not 1<=count<=MAX_ITEMS or end>65535:raise ValueError('Blok aralığı geçersiz')
    if area in ('09','89') and not (end<=4095 or 32768<=start<=end<=36863):raise ValueError('TC blok aralığı geçersiz')
    return area,start,count

def make(area,start,count=1):
    cmd=f'0101{area}{start:04X}00{count:04X}';fields(cmd);return cmd

def batches(commands, disabled=(), enabled=True):
    plan = _batch_plan(tuple(sorted(set(commands))), frozenset(disabled), enabled)
    return {command: list(members) for command, members in plan}


@lru_cache(maxsize=64)
def _batch_plan(commands, disabled, enabled):
    groups=defaultdict(list);result={}
    for cmd in commands:
        area,start,count=fields(cmd)
        if count!=1:raise ValueError('Tekil adres planı gerekli')
        if not enabled or area in disabled or area=='89':result[cmd]=[cmd];continue
        groups[(area,start>=32768 if area=='09' else False)].append((start,cmd))
    for (area,_),items in groups.items():
        block=[]
        def flush():
            if block:result[make(area,block[0][0],block[-1][0]-block[0][0]+1)]=[c for _,c in block]
        for start,cmd in items:
            if block and (start-block[-1][0]>MAX_STEP or start-block[0][0]>=MAX_ITEMS):flush();block=[]
            block.append((start,cmd))
        flush()
    return tuple((command, tuple(members)) for command, members in result.items())

def unpack(cmd,response,members):
    area,start,count=fields(cmd);width=2 if area=='09' else 4
    raw=str(response.get('response','')).strip().upper()
    if not response.get('ok') or not re.fullmatch(r'01010000[0-9A-F]{'+str(width*count)+'}',raw):raise ValueError('Blok FINS yanıtı geçersiz')
    data=[raw[i:i+width] for i in range(8,len(raw),width)]
    if area=='09' and any(v not in ('00','01') for v in data):raise ValueError('TC bit yanıtı geçersiz')
    result={}
    for member in members:
        a,n,k=fields(member)
        if a!=area or k!=1 or not start<=n<start+count:raise ValueError('Blok eşlemesi geçersiz')
        result[member]={'ok':True,'response':'01010000'+data[n-start]}
    return result

def read_batched(send,commands,disabled,enabled=True):
    """send returns one fresh bridge response; failed blocks retry as singles."""
    commands=tuple(sorted(set(commands)));plan=_batch_plan(commands,frozenset(disabled),enabled)
    if not plan:raise ValueError('Okunacak adres yok')
    result=send([cmd for cmd, _ in plan]);out={};retry=[];fallback_areas=set()
    for cmd,members in plan:
        response=result['responses'].get(cmd,{})
        if fields(cmd)[2]==1:out[cmd]=response;continue
        try:out.update(unpack(cmd,response,members))
        except ValueError:
            retry.extend(members);fallback_areas.add(fields(cmd)[0])
    if retry:
        second=send(retry)
        if second['plc']!=result['plc']:raise ValueError('PLC adı değişti')
        out.update({c:second['responses'].get(c,{}) for c in retry})
        # Only cache rejection when the single reads really succeeded.
        for area in fallback_areas:
            relevant=[c for c in retry if fields(c)[0]==area]
            try:
                for c in relevant:unpack(c,out[c],[c])
            except ValueError:continue
            disabled.add(area)
    return {'plc':result['plc'],'responses':out,'stats':{'commands':len(plan)+len(retry),'single':len(commands),'fallback':len(retry),'disabled':sorted(disabled),'enabled':enabled}}
