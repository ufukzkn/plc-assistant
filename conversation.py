"""Offline follow-up routing and conservative snapshot summaries."""
import re
from collections import Counter
from query import ADDRESS_PATTERN, resolve
from question_corpus import is_status_question, normalize_text as norm
from diagnosis import trace
from assistant_report import explain
from ladder import build,state

def intent(text):
    t=norm(text)
    if 'alarm' in t and ('hangi' in t or 'alarmlar' in t or 'listele' in t):return 'alarms'
    if any(x in t for x in ('nerede','kullanil','hangi devre','hangi cikis')):return 'references'
    return 'detail'

def route(text, rows, current=None,labels=None):
    if ADDRESS_PATTERN.search(text.upper()):
        return resolve(text,rows,labels)
    t=norm(text)
    if labels and 'pano' in t and any(x in t for x in ('acilis','sure','saymis')):
        matches=[r for r in rows if r[0]=='T0001' and r[1]=='TIM']
        if len(matches)==1:return matches[0]
    try:return resolve(text,rows,labels)
    except ValueError:pass
    if current and is_status_question(text):return current
    if current and any(x in text.lower() for x in ('neden','reset','set','süre','değer','koşul','tamamlan','tekrar','durum')):return current
    raise ValueError('Bir PLC adresi veya mevcut adresle ilgili takip sorusu yazın.')

def summary(row,rows,logic,vals,labels,question,pv=None):
    a,kind,offset,raw=row
    if intent(question)=='alarms':
        alarms=[(x,l) for x,l in labels.items() if 'alarm' in norm(l) or 'acilmadi' in norm(l)]
        if not alarms:return 'Doğrulanmış alarm açıklamaları yok; alarm listesi çıkarılamıyor.'
        return 'Tanımlı alarm adresleri (programın tamamı olmayabilir):\n'+'\n'.join(f'{x} — {l}: '+{1:'AKTİF',0:'pasif'}.get(vals.get(x),'okunamadı') for x,l in alarms)
    if intent(question)=='references':
        hits=[f'{r[0]} — {labels.get(r[0], r[1])} | BIN {r[2]}' for r in rows if any(x==a and op!='?' for op,x in logic.get(r[2],[]))]
        return f'{a} — çözümlenen doğrudan kullanımlar (eksik komutlar hariç):\n'+('\n'.join(hits) or 'Bulunamadı.')
    if vals.get(a) is None:return 'Güncel okuma bekleniyor.'
    nodes=build(logic.get(offset,[])); fmt=lambda x:{0:'sağlanmıyor',1:'sağlanıyor',None:'belirsiz'}[x]
    lines=[f'{a} — {labels.get(a,kind)}: '+('aktif (1)' if vals[a]==1 else 'pasif (0)' if vals[a]==0 else str(vals[a]))]
    if kind=='KEEP' and nodes and len(nodes)==2 and 'reset' in question.lower():
        lines.append('RESET koşulu: '+fmt(state(nodes[1],vals)))
        def leaves(n):return [n] if len(n)==2 else leaves(n[1])+leaves(n[2])
        for op,x in leaves(nodes[1]):lines.append(f'{op} {x}: '+str(vals.get(x,1 if x=='P_ON' else 0 if x=='P_OFF' else '?')))
    elif kind=='TIM' and nodes and len(nodes)==1:
        lines.append('Giriş koşulu: '+fmt(state(nodes[0],vals)))
        from timer_pv import describe
        lines.append('Zamanlayıcı tamamlanmış.' if vals[a]==1 else 'Zamanlayıcı henüz tamamlanmamış.')
        lines.append(describe(raw,pv))
        if vals[a]==0 and state(nodes[0],vals)==0:lines.append('Giriş koşulu sağlanmıyor.')
    else:
        report=explain(a,kind,logic.get(offset,[]),rows,logic,vals,labels)
        lines.extend(line for line in report.splitlines()[2:] if not line.startswith(('Not:', 'Adres açıklamaları:')))
        if kind=='KEEP' and nodes and len(nodes)==2 and state(nodes[1],vals)==0:
            def reset_leaves(n):return [n] if len(n)==2 else reset_leaves(n[1])+reset_leaves(n[2])
            lines.append('RESET girişleri: '+', '.join(f'{op} {x} = {vals.get(x, 1 if x=="P_ON" else 0 if x=="P_OFF" else "?")}' for op,x in reset_leaves(nodes[1])))
        if kind=='KEEP' and nodes and len(nodes)==2 and vals[a]==1 and state(nodes[0],vals)==1:
            def active_leaves(n):
                if state(n,vals)!=1:return []
                if len(n)==2:return [n]
                return active_leaves(n[1])+active_leaves(n[2])
            for op,x in active_leaves(nodes[0]):
                if x not in ('P_ON','P_OFF'):
                    lines.append(f'SET yolunu sağlayan kontak: {x} {labels.get(x, "")} = {vals.get(x,"?")} ({op}).')
            if a=='W11.00' and labels.get(a)=='ACİL STOP ALARMI' and vals.get('CIO0.00')==0:
                lines.append('CIO0.00 girişinin 0 olması alarmın mevcut SET yolunu sağlıyor. Yetkili personelle acil stop güvenlik devresini ve giriş sinyalini kontrol edin; köprüleme yapmayın.')
        counts=Counter()
        for line in trace(a,rows,logic,vals):
            m=re.fullmatch(r'\s*([A-Z]+\d+(?:\.\d+)?) = [01]',line)
            if m and m[1]!=a:counts[m[1]]+=1
        for x,n in counts.most_common():
            if n>1:lines.append(f'Ortak kaynak adayı: {x} {labels.get(x, "")} = {vals.get(x,"?")} ({n} iz yolu)')
        if kind=='KEEP' and vals[a]==0 and nodes and len(nodes)==2 and state(nodes[1],vals)==1:lines.append('RESET yolu şu anda sağlanıyor; kilitleme geçmişi bilinmiyor.')
        if a=='CIO110.00' and vals.get('T0001')==1 and labels:lines.append('T0001 tamamlanma biti aktif; bu kontak mevcut örnekte engel değil.')
        lines.append('Kaynak devreleri ve ayrıntılı koşullar arıza raporunda gösteriliyor.')
    return '\n'.join(lines+['Eşzamanlı olmayan örnek; kesin fiziksel kök neden değildir.'])
