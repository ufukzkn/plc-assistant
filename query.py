import re

ADDRESS_PATTERN = re.compile(r'(?<![\w.])(?:(?:CIO|H|W|D|A)?\s*\d+\.\d{1,2}|[TCD]\s*\d+)(?![\w.])', re.IGNORECASE)

def normalize(s):
    m=re.fullmatch(r'(CIO|H|W|D|A)?\s*(\d+)\.(\d{1,2})',s.upper())
    if m:
        if int(m[3])>15: raise ValueError('Bit numarası 0–15 olmalı.')
        return f'{m[1] or "CIO"}{int(m[2])}.{int(m[3]):02d}'
    m=re.fullmatch(r'([TCD])\s*(\d+)',s.upper())
    if m:return f'{m[1]}{int(m[2]):04d}' if m[1] in 'TC' else f'D{int(m[2])}'
    raise ValueError('Adres tanınmadı.')

def resolve(text,rows,labels=None):
    tokens=ADDRESS_PATTERN.findall(text.upper())
    addresses=set(normalize(x.strip()) for x in tokens)
    if not addresses and labels:
        import unicodedata
        def norm(t):return ''.join(c for c in unicodedata.normalize('NFKD',t.lower().replace('ı','i')) if not unicodedata.combining(c))
        t=norm(text)
        matches=[a for a,label in labels.items() if norm(label) in t]
        if not matches and 'klepe' in t and re.search(r'\b1\b',t) and ('acil' in t or 'acilm' in t):
            matches=[a for a,label in labels.items() if norm(label)=='oto klepe-1 ac']
        addresses=set(matches)
    if len(addresses)!=1:raise ValueError('Tek bir PLC adresi yazın. Örnek: 110.00 çıkış vermiyor')
    a=addresses.pop(); matches=[r for r in rows if r[0]==a]
    if len(matches)!=1:raise ValueError(f'{a}: '+('Birden fazla üretici var; listeden inceleyin.' if matches else 'Desteklenen üretici bulunamadı.'))
    return matches[0]
