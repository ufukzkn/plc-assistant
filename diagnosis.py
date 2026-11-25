from ladder import build,state

def blockers(n,vals):
    if state(n,vals)!=0:return []
    if len(n)==2:return [n[1]]
    return list(dict.fromkeys(blockers(n[1],vals)+blockers(n[2],vals)))

def trace(target,rows,logic,vals,depth=0,seen=()):
    prefix='  '*depth; v=vals.get(target,'?'); lines=[f'{prefix}{target} = {v}']
    if target in seen:return lines+[prefix+'  Döngü: takip durdu.']
    matches=[r for r in rows if r[0]==target]
    if len(matches)!=1:return lines+[prefix+'  '+('Birden fazla üretici; kesin kaynak yok.' if matches else 'Desteklenen üretici yok; saha / diğer komutları kontrol edin.')]
    if depth>=5:return lines+[prefix+'  Derinlik sınırı.']
    r=matches[0]; nodes=build(logic.get(r[2],[])); kind=r[1]
    if not nodes or kind not in ('OUT','KEEP','TIM') or len(nodes)!=(2 if kind=='KEEP' else 1):return lines+[prefix+'  Mantık doğrulanamadı.']
    lines.append(prefix+'  '+kind+' koşulları: '+', '.join(('Belirsiz' if state(n,vals) is None else str(state(n,vals))) for n in nodes))
    # Active KEEP: explain current SET path, not historical latch cause.
    if kind=='KEEP' and v==1:
        lines.append(prefix+'  SET girişleri (geçmiş kilitleme nedeni kesin değil):')
        def leaves(n):return [n[1]] if len(n)==2 else leaves(n[1])+leaves(n[2])
        xs=leaves(nodes[0]) if state(nodes[0],vals)==1 else []
    else:
        xs=blockers(nodes[0],vals)
        if state(nodes[0],vals) is None:
            lines.append(prefix+'  SET/giriş belirsiz: kenar veya eksik veri; kesin neden yok.')
        if kind=='KEEP' and state(nodes[1],vals)==1:
            lines.append(prefix+'  RESET koşulu sağlanıyor; geçmiş durum bilinmiyor.')
    for x in dict.fromkeys(xs):
        if x not in ('P_ON','P_OFF'):lines.extend(trace(x,rows,logic,vals,depth+1,seen+(target,)))
    return lines

def addresses(target,rows,logic,depth=5):
    seen=set(); pending=[(target,0)]
    while pending:
        a,d=pending.pop(0)
        if a in seen or d>depth:continue
        seen.add(a)
        for r in rows:
            if r[0]==a:
                pending.extend((x,d+1) for op,x in logic.get(r[2],[]) if x and op!='?' and x not in ('P_ON','P_OFF'))
    return seen
