import re

def plan(address):
    a=address.upper()
    if a=='P_ON': return None, None
    m=re.fullmatch(r'(CIO|H|W|D|A)?(\d+)\.(\d{1,2})',a)
    if m:
        area,n,b=m.groups(); n=int(n); b=int(b)
        if n>65535 or b>15: raise ValueError('Adres aralığı')
        return f'0101{ {None:0xB0,"CIO":0xB0,"H":0xB2,"W":0xB1,"D":0x82,"A":0xB3}[area]:02X}{n:04X}000001',b
    m=re.fullmatch(r'([TC])(\d+)',a)
    if m:
        n=int(m[2]);
        if n>4095: raise ValueError('TC aralığı')
        return f'010109{n+(32768 if m[1]=="C" else 0):04X}000001',None
    raise ValueError('Desteklenmeyen adres')

_WORD_RESPONSE = re.compile(r"01010000[0-9A-Fa-f]{4}")
_FLAG_RESPONSE = re.compile(r"010100000[01]")


def raw_value(response, flag=False):
    raw = response.strip()
    pattern = _FLAG_RESPONSE if flag else _WORD_RESPONSE
    if not pattern.fullmatch(raw):
        raise ValueError('FINS yanıtı geçersiz: ' + raw)
    return int(raw[8:], 16)


def decode(response, bit):
    value = raw_value(response, flag=bit is None)
    return value if bit is None else (value >> bit) & 1
