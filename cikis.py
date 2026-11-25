import struct,sys,csv,tkinter as tk
from tkinter import filedialog,ttk,messagebox
from pathlib import Path

def words(b):
    end = len(b) - (len(b) - 0x8c0) % 4
    return enumerate(struct.iter_unpack('>HH', memoryview(b)[0x8c0:end]))

def decode(b):
    # Experimental layout of the supplied CJ2M upload only.
    if len(b)<0x8c4 or b[0x8c0:0x8c4]!=bytes.fromhex('61440100'):
        raise ValueError('Bu BIN yapısı doğrulanmış örnekle eşleşmiyor.')
    rows=[]
    for index, (op, v) in words(b):
        i = 0x8c0 + index * 4
        if (op,v)==(0xbb40,0x00c0) and i+12<=len(b):
            a,t,c,sv=struct.unpack_from('>HHHH',b,i+4)
            if a==0x5000 and 0xe000<=t<=0xefff and c==0x6540:
                rows.append((f'T{t-0xe000:04d}', 'TIM', f'{i:04X}', f'#{sv:X}'))
            continue
        if (op,v)==(0xb240,0x0140) and i+12<=len(b):
            a,src,c,dst=struct.unpack_from('>HHHH',b,i+4)
            if a==0x6000 and c==0x5401:
                rows.append((f'D{dst}', 'MOV', f'{i:04X}', f'{src:04X} → D{dst}'))
            continue
        if op not in (0xfa04,0xfa05,0xf304,0xf305): continue
        if op&255==4: area='CIO'; n=v
        elif 0x8000<=v<0x8400: area='H'; n=v-0x8000
        elif 0xe000<=v<0xe600: area='W'; n=v-0xe000
        else: continue
        rows.append((f'{area}{n//16}.{n%16:02}', 'KEEP' if op>>8==0xf3 else 'OUT',f'{i:04X}',f'{op:04X} {v:04X}'))
    return rows

def main():
    root=tk.Tk();root.title('PLC Assistant - BIN çıkış testi (deneysel)');root.geometry('780x560')
    label=tk.StringVar(value='BIN dosyası seçin. Yalnızca doğrulanmış örnek düzeni desteklenir.')
    tree=ttk.Treeview(root,columns=('a','c','o','r'),show='headings');
    for k,t in zip(('a','c','o','r'),('Adres','Komut','Dosya konumu','Ham kod / SV / hedef')): tree.heading(k,text=t);tree.column(k,width=170)
    def load():
        p=filedialog.askopenfilename(filetypes=[('BIN','*.bin')]);
        if not p:return
        tree.delete(*tree.get_children())
        try:
            rows=decode(Path(p).read_bytes())
            for r in rows:tree.insert('', 'end',values=r)
            label.set(f'{len(rows)} yazma hedefi; fiziksel I/O ayrımı doğrulanmadı.')
        except Exception as e:label.set(str(e))
    ttk.Button(root,text='BIN dosyası aç',command=load).pack(pady=8);ttk.Label(root,textvariable=label).pack();tree.pack(fill='both',expand=True,padx=8,pady=8);root.mainloop()
if __name__=='__main__':main()
