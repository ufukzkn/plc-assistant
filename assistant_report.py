"""Conservative, offline Turkish explanations; labels scoped to exact reference BIN."""
import hashlib
from ladder import build,state
REFERENCE='e4e8d55c8acfe17801df5ffd854fe341833c2d6b7f2edaa189a554f129f01c3e'
LABELS={'CIO110.00':'OTO KLEPE-1 AÇ','W11.00':'ACİL STOP ALARMI','H10.00':'FAN MANUAL/AUTO','H10.01':'KLEPELER MANUAL/AUTO','H10.03':'FAN MANUAL START-STOP','W11.01':'KLEPE-1 MOTOR İNVERTER ALARMI','W11.05':'KLEPE-1 BELİRLENEN ZAMANDA AÇILMADI','W10.00':'RESET BUTONU','H15.00':'SICAKLIĞA GÖRE KLEPE AÇMA-KAPAMA RÖLESİ'}
def labels_for(data):
    return LABELS.copy() if hashlib.sha256(data).hexdigest()==REFERENCE else {}
def explain(a,kind,cmds,rows,logic,vals,labels):
    def name(x):return x+(' – '+labels[x] if x in labels else '')
    v=vals.get(a); lines=['ARIZA ASİSTANI | '+name(a)]
    if v is None:return '\n'.join(lines+['Canlı değer bekleniyor; teşhis için güncel okuma gerekli.'])
    lines.append(f'Okunan değer: {v}'+((' (aktif)' if v else ' (pasif)') if kind in ('OUT','KEEP','TIM') else ''))
    nodes=build(cmds)
    if not nodes or kind not in ('OUT','KEEP','TIM') or len(nodes)!=(2 if kind=='KEEP' else 1):return '\n'.join(lines+['Bu komutun mantığı henüz desteklenmiyor.'])
    def reasons(n):
        if state(n,vals)!=0:return []
        if len(n)==2:
            op,x=n;return [f'{name(x)} = {vals.get(x, "?")} (beklenen: {0 if op in ("LDNOT","ANDNOT") else 1})']
        if n[0]=='parallel':return ['Paralel alternatiflerin ikisi de kapalı: ['+'; '.join(reasons(n[1]))+'] VE ['+'; '.join(reasons(n[2]))+']']
        return reasons(n[1])+reasons(n[2])
    s=state(nodes[0],vals)
    lines.append(('SET' if kind=='KEEP' else 'Giriş')+' koşulu: '+{0:'sağlanmıyor',1:'sağlanıyor',None:'belirsiz'}[s])
    if kind=='KEEP':lines.append('RESET koşulu: '+{0:'sağlanmıyor',1:'sağlanıyor',None:'belirsiz'}[state(nodes[1],vals)])
    if s==0:lines+=['Mevcut engeller:']+['• '+x for x in dict.fromkeys(reasons(nodes[0]))]
    if labels and a=='CIO110.00' and v==0 and s==0:
        if vals.get('W11.00')==1:
            lines.append('• Acil stop alarmı aktif. Acil stop güvenlik devresini yetkili personelle kontrol edin; köprüleme yapmayın.')
            m=[r for r in rows if r[0]=='W11.00']; ns=build(logic.get(m[0][2],[])) if len(m)==1 else None
            if ns and len(ns)==2 and state(ns[0],vals)==1 and vals.get('CIO0.00')==0:lines.append('  CIO0.00 = 0; alarmın mevcut SET koşulu sağlanıyor. Fiziksel neden henüz bilinmiyor.')
        if vals.get('H10.01')==0:lines.append('• Klepelerin manuel/otomatik seçim devresini kontrol edin.')
        if vals.get('H10.00')==0 and vals.get('H10.03')==0:lines.append('• Fan otomatik/manuel çalışma izinlerini kontrol edin.')
    lines.append('Not: Anlık okumalar eşzamanlı değildir; kilitleme geçmişi ve kenar tetikleri kesin bilinmez.')
    lines.append('Adres açıklamaları: '+('ATIKSU referans PDF eşlemesi (BIN SHA256 doğrulandı).' if labels else 'Bu programa ait doğrulanmış açıklama yok.'))
    return '\n'.join(lines)
