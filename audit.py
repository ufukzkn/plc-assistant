from ladder import build

def report(rows,logic):
    lines=[]; counts={'Yapısal':0,'Kenar belirsiz':0,'Eksik':0}
    for a,k,o,*_ in rows:
        cmds=logic.get(o,[]); nodes=build(cmds)
        unknown=[x for op,x in cmds if op=='?']
        edge=any(op in ('@AND','%AND?') for op,x in cmds)
        status='Eksik' if not nodes or len(nodes)!=(2 if k=='KEEP' else 1) or k not in ('OUT','KEEP','TIM') else 'Kenar belirsiz' if edge else 'Yapısal'
        counts[status]+=1
        lines.append(f'{a} | {k} | {o} | {status}'+(' | Ham: '+', '.join(unknown) if unknown else ''))
    return f'Toplam {len(rows)} hedef\n'+ ' | '.join(f'{k}: {v}' for k,v in counts.items())+'\nYapısal = desteklenen komut dizisi; saha doğrulaması değildir. MOV mantığı desteklenmiyor. %AND? = deneysel kenar biçimi, yönü doğrulanmadı.\n\n'+'\n'.join(lines)
