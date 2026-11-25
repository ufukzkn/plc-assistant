import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from pathlib import Path
from functools import lru_cache
import os,subprocess,tempfile,json,threading,queue,re
from cikis import decode as parse
from usb import plan, raw_value
from logic import extract
from detail import open_detail
from assistant_report import labels_for
from session import session
from question_corpus import is_status_question, suggest
from question_entry import QuestionEntry

def address_plan(a):
    if re.fullmatch(r'D\d+',a):
        n=int(a[1:]); return f'010182{n:04X}000001','word'
    return plan(a)

def _response_value(response, flag):
    if not response.get('ok'):
        raise ValueError('Okuma başarısız')
    return raw_value(response['response'], flag=flag)


def value(response, bit):
    number = _response_value(response, flag=bit is None)
    return number if bit is None or bit == 'word' else (number >> bit) & 1


def parse_program(data):
    rows = parse(data)
    return rows, extract(data, rows), labels_for(data)


def bridge(req,d):
    if req.get("mode")!="upload":return session.read(req["cdm"],req["commands"])
    session.close()
    p=Path(d)/'request.json'; q=Path(d)/'result.json';p.write_text(json.dumps(req),encoding='utf-8')
    ps=Path(os.environ.get('SystemRoot',r'C:\Windows'))/'SysWOW64/WindowsPowerShell/v1.0/powershell.exe'
    proc=subprocess.run([str(ps),'-NoProfile','-STA','-ExecutionPolicy','Bypass','-File',str(Path(__file__).with_name('bridge.ps1')),'-Request',str(p),'-Result',str(q)],capture_output=True,timeout=180,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if not q.exists():raise RuntimeError(proc.stderr.decode(errors='replace') or 'Haberleşme sonucu yok')
    result=json.loads(q.read_text(encoding='utf-8-sig'))
    if result.get('error'):raise RuntimeError(result['error'])
    return result

@lru_cache(maxsize=64)
def _target_plan(targets, extra):
    addresses_by_command = {}
    for address in targets:
        try:
            command, bit = address_plan(address)
        except ValueError:
            continue
        if command:
            addresses_by_command.setdefault(command, []).append((address, bit))
    commands = tuple(sorted(addresses_by_command.keys() | extra))
    return commands, tuple((cmd, tuple(addresses)) for cmd, addresses in addresses_by_command.items())


def read_targets(cdm, name, targets, extra=(), enabled=True):
    targets = tuple(targets)
    commands, groups = _target_plan(frozenset(targets), frozenset(extra))
    result = session.read(cdm, list(commands), enabled)
    if result['plc'] != name:
        raise ValueError('PLC adı değişti')
    vals = {}
    for command, addresses in groups:
        try:
            number = _response_value(result['responses'].get(command, {}),
                                     flag=addresses[0][1] is None)
        except (ValueError, TypeError, AttributeError, KeyError):
            vals.update((address, None) for address, _ in addresses)
            continue
        for address, bit in addresses:
            vals[address] = (number >> bit) & 1 if isinstance(bit, int) else number
    if groups and all(value is None for value in vals.values()):
        raise RuntimeError('Hiçbir adres için geçerli PLC yanıtı alınamadı')
    ordered_values = {address: vals[address] for address in targets if address in vals}
    return ordered_values, result['responses'], result['stats']


def stats_text(stats):
    if not stats:return ''
    text=f" | FINS: {stats['commands']}/{stats['single']} tekil"
    if not stats['enabled']:text+=' | Tekil mod'
    elif stats['disabled']:text+=' | Tekil dönüş: '+','.join(stats['disabled'])
    elif stats['fallback']:text+=' | Tekil tekrar: '+str(stats['fallback'])
    else:text+=' | Blok mod'
    return text

class App:
    def __init__(self):
        self.root=tk.Tk();self.root.title('PLC Assistant V4.0.2 | Program ve çıkış listesi');self.root.geometry('1050x650');self.labels={};self.logic={};self.online=False;self.plc="";self.rows=[];self.values={};self.q=queue.Queue();self.busy=False;self.live_busy=False;self.detail_open=False;self.live=True;self.live_q=queue.Queue();self.last_sample=None
        self.path=tk.StringVar();self.search=tk.StringVar();self.kind=tk.StringVar(value='Tümü');self.status=tk.StringVar(value='Tek PLC içeren CDM seçin. Salt okunur.')
        f=ttk.Frame(self.root);f.pack(fill='x',padx=10,pady=10);ttk.Entry(f,textvariable=self.path,state='readonly').pack(side='left',fill='x',expand=True)
        self.buttons=[]
        for title,cmd in [('CDM seç',self.choose),('PLC programını oku ve listele',self.upload),('BIN aç',self.offline),('Seçili çıkışı incele',lambda:open_detail(self)),('Çözümleme raporu',self.audit)]:
            b=ttk.Button(f,text=title,command=cmd);b.pack(side='left',padx=3);self.buttons.append(b)
        f=ttk.Frame(self.root);f.pack(fill='x',padx=10);ttk.Label(f,text='Ara:').pack(side='left');ttk.Entry(f,textvariable=self.search).pack(side='left');ttk.Combobox(f,textvariable=self.kind,values=['Tümü','OUT','KEEP','TIM','MOV'],state='readonly',width=12).pack(side='left',padx=8)
        f=ttk.LabelFrame(self.root,text='Arıza asistanı');f.pack(fill='x',padx=10,pady=6)
        self.question = tk.StringVar()
        ttk.Button(f, text='Arızayı araştır', command=self.ask).pack(side='right', anchor='n', padx=5, pady=5)
        self.question_entry = QuestionEntry(f, self.question, self.suggest_question, self.ask)
        self.question_entry.pack(side='left', fill='x', expand=True, padx=5, pady=5)
        ttk.Label(self.root,text='Örnek: 110.00 çıkış vermiyor').pack(anchor='w',padx=15)
        self.tree=ttk.Treeview(self.root,columns=('a','c','o','r','v'),show='headings');
        for k,t,w in zip(('a','c','o','r','v'),('Adres','Komut','BIN konumu','Ham kod / SV / hedef','Canlı değer'),(130,100,100,250,130)):self.tree.heading(k,text=t);self.tree.column(k,width=w)
        self.tree.bind('<Double-1>',lambda e:open_detail(self));self.tree.pack(fill='both',expand=True,padx=10,pady=10);ttk.Label(self.root,textvariable=self.status,wraplength=1000).pack(pady=5);ttk.Label(self.root,text='Deneysel CJ2M çözümleyici: OUT / KEEP / TIM / MOV. Fiziksel I/O ayrımı ve diğer komutlar doğrulanmadı.').pack(pady=5)
        self.tree.bind('<<TreeviewSelect>>', lambda _: self.question_entry.refresh())
        self.interval=tk.StringVar(value='500');self.block_enabled=tk.BooleanVar(value=True); f=ttk.Frame(self.root);f.pack();ttk.Combobox(f,textvariable=self.interval,values=('250','500','1000','2000'),state='readonly',width=7).pack(side='left');ttk.Checkbutton(f,text='Blok okuma',variable=self.block_enabled).pack(side='left',padx=8);ttk.Button(f,text='Canlı izle',command=self.resume_live).pack(side='left');ttk.Button(f,text='Durdur',command=self.pause_live).pack(side='left');self.root.after(200,self.live_tick)
        self.search.trace_add('write',lambda *_:self.render());self.kind.trace_add('write',lambda *_:self.render());self.root.protocol('WM_DELETE_WINDOW',self.close)
    def selected_row(self):
        selection = self.tree.selection()
        if len(selection) == 1:
            return self.tree.item(selection[0], 'values')[:4]
        return None

    def suggest_question(self, text):
        selected = self.selected_row()
        return suggest(text, self.rows, self.labels, selected[0] if selected else None)

    def ask(self):
        from conversation import route, intent
        if self.busy:
            return
        question = self.question.get()
        current = self.selected_row() if is_status_question(question) else None
        try:
            row = (self.rows[0] if intent(question) == 'alarms' and self.rows
                   else route(question, self.rows, current, self.labels))
        except ValueError as error:
            messagebox.showinfo('Arıza asistanı', str(error))
            return
        open_detail(self, row, auto=True, question=question)

    def audit(self):
        from audit import report
        w=tk.Toplevel(self.root);w.title("Program çözümleme kapsamı");w.geometry("1000x650")
        t=tk.Text(w,wrap="word");t.pack(fill="both",expand=True);t.insert("end",report(self.rows,self.logic));t.config(state="disabled")
    def close(self):
        if not self.busy and not self.live_busy:session.close();self.root.destroy()
    def choose(self):
        if self.live_busy:return
        p=filedialog.askopenfilename(filetypes=[('CDM','*.cdm')]);
        if p:session.close();self.chat_history=[];self.labels={};self.online=False;self.logic={};self.path.set(p);self.rows=[];self.values={};self.render()
    def render(self):
        self.tree.delete(*self.tree.get_children());s=self.search.get().upper();k=self.kind.get()
        for r in self.rows:
            if s in ' '.join(r).upper() and (k=='Tümü' or r[1]==k):self.tree.insert('', 'end',values=(*r,self.values.get(r[0],'—')))
    def offline(self):
        if self.live_busy:return
        p=filedialog.askopenfilename(filetypes=[('BIN','*.bin')]);
        if not p:return
        session.close()
        self.chat_history=[];self.rows=[];self.values={}
        self.online=False;self.logic={};self.labels={}
        try:data=Path(p).read_bytes();self.rows,self.logic,self.labels=parse_program(data);self.status.set(f'{len(self.rows)} hedef | Offline BIN')
        except Exception as e:self.status.set(str(e))
        self.render()
    def pause_live(self):
        self.live=False;self.last_sample=None;self.status.set('Canlı liste durduruldu; değerler son örnektir.')
    def resume_live(self):
        self.live=True
    def update_values(self,vals,elapsed,stats=None):
        import time
        now=time.monotonic(); gap=round((now-self.last_sample)*1000) if self.last_sample else 0;self.last_sample=now
        self.values={r[0]:str(vals[r[0]]) if vals.get(r[0]) is not None else 'Bilinmiyor' for r in self.rows}
        for i in self.tree.get_children():
            row=self.tree.item(i,'values');self.tree.set(i,'v',self.values.get(row[0],'Bilinmiyor'))
        self.status.set(f'{self.plc} | USB | Okuma: {elapsed} ms | Örnek aralığı: {gap} ms | Eşzamanlı değil'+stats_text(stats));return gap
    def live_tick(self):
        if self.live_busy:
            try:vals,error,elapsed,stats=self.live_q.get_nowait()
            except queue.Empty:self.root.after(25,self.live_tick);return
            self.live_busy=False
            if error:self.update_values({},elapsed);self.status.set('USB | Güncel veri yok: '+error)
            else:self.update_values(vals,elapsed,stats)
            if not self.live and not self.detail_open:self.status.set('Canlı liste durduruldu; değerler son örnektir.')
            self.root.after(int(self.interval.get()),self.live_tick);return
        if self.online and self.live and not self.busy and not self.detail_open:
            self.live_busy=True;p=self.path.get();name=self.plc;targets={r[0] for r in self.rows};enabled=self.block_enabled.get()
            def worker():
                import time
                t=time.monotonic()
                try:vals,_,stats=read_targets(p,name,targets,enabled=enabled);error=''
                except Exception as e:vals={};error=str(e);stats=None
                self.live_q.put((vals,error,round((time.monotonic()-t)*1000),stats))
            threading.Thread(target=worker,daemon=True).start();self.root.after(25,self.live_tick);return
        self.root.after(int(self.interval.get()),self.live_tick)
    def upload(self):
        if self.busy or self.live_busy:return
        p=self.path.get()
        if not p or not Path(p).is_file():messagebox.showerror('CDM','CDM seçin');return
        self.online=False;self.chat_history=[];self.rows=[];self.values={};self.render();self.busy=True
        for b in self.buttons:b.config(state='disabled')
        self.status.set('Program okunuyor, ardından adres değerleri alınacak...');enabled=self.block_enabled.get();self.last_sample=None
        def worker():
            rows=[];vals={};name='';error='';logic={};labels={}
            try:
                with tempfile.TemporaryDirectory() as d:
                    dest=str(Path(d)/'program.bin');r=bridge({'cdm':p,'mode':'upload','dest':dest},d);name=r['plc'];data=Path(dest).read_bytes();rows,logic,labels=parse_program(data);values,_,_=read_targets(p,name,{r[0] for r in rows},enabled=enabled)
                    vals={a:str(v) if v is not None else 'Bilinmiyor' for a,v in values.items()}
            except Exception as e:error=str(e)
            self.q.put((rows,vals,name,error,logic,labels))
        threading.Thread(target=worker,daemon=True).start();self.root.after(150,self.poll)
    def poll(self):
        try:self.rows,self.values,name,error,self.logic,self.labels=self.q.get_nowait()
        except queue.Empty:self.root.after(150,self.poll);return
        self.busy=False;self.online=not error and bool(name);self.plc=name
        for b in self.buttons:b.config(state='normal')
        self.render();self.status.set(f'{name} | {len(self.rows)} hedef | {sum(v!="Bilinmiyor" for v in self.values.values())} adres okundu | '+(error or 'Anlık örnek; eşzamanlı değil.'))
if __name__=='__main__':App().root.mainloop()
