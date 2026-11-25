"""Experimental FINS timer PV read, separate from completion flag."""
import re
def command(a):
    m=re.fullmatch(r'T(\d+)',a)
    if not m or int(m[1])>4095:raise ValueError('Timer adresi')
    return f'010189{int(m[1]):04X}000001'
def describe(sv,response):
    r=(response or {}).get('response','').strip().upper()
    if not (response or {}).get('ok') or not re.fullmatch(r'01010000[0-9A-F]{4}',r):
        return f'Timer SV: {sv} | PV: okunamadı (deneysel; tamamlanma biti ayrı).'
    raw=r[8:]; text=f'Timer SV: {sv} | PV ham: {raw} (deneysel)'
    if re.fullmatch(r'[0-9]{4}',raw) and re.fullmatch(r'#[0-9]{1,4}',sv):
        text+=f' | TIM BCD 0,1 s varsayımıyla kalan: {int(raw)/10:g} s / ayar: {int(sv[1:])/10:g} s'
    return text+' | CX-Programmer ile doğrulayın.'
