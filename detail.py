import tkinter as tk
from tkinter import ttk,filedialog
import threading,queue,tempfile,time
from session import session
from pathlib import Path
from datetime import datetime
from logic import evaluate
from ladder import draw,build,state
from diagnosis import addresses,trace
from assistant_report import explain
from question_corpus import suggest
from question_entry import QuestionEntry

def open_detail(app, selected=None,auto=False,question=None):
    from main import read_targets,stats_text
    sel=app.tree.selection()
    if (not sel and selected is None) or app.busy:return
    a,kind,offset,*_=selected if selected is not None else app.tree.item(sel[0],'values'); cmds=app.logic.get(offset,[])
    app.detail_open=True
    w=tk.Toplevel(app.root);w.title(f'{a} | {kind} | V4.0.2');w.geometry('1100x800');w.transient(app.root);w.grab_set()
    status=tk.StringVar(value='Deneysel komut çözümü; ? = çözümlenmedi.'); vals={}; running=False; busy=False; q=queue.Queue(); last_ok=None; stale=False; timer=None; items=[]; pv=[None]; failures=0; started=0
    interval=app.interval
    tree=ttk.Treeview(w,columns=('op','a','v'),show='headings');
    for k,t in [('op','Komut'),('a','Adres / ham kod'),('v','Anlık değer')]:tree.heading(k,text=t)
    tree.tag_configure('stale',foreground='#999999');tree.tag_configure('on',foreground='#16803b');tree.tag_configure('off',foreground='#666666');
    def toggle():
        if tree.winfo_manager():tree.pack_forget()
        else:tree.pack(before=panes,fill='x')
    ttk.Button(w,text='Mnemonic göster / gizle',command=toggle).pack(anchor='w')
    panes=ttk.Panedwindow(w,orient='vertical');panes.pack(fill='both',expand=True)
    frame=ttk.Frame(panes);panes.add(frame,weight=3)
    canvas=tk.Canvas(frame,height=230,background='white'); sx=ttk.Scrollbar(frame,orient='horizontal',command=canvas.xview);sy=ttk.Scrollbar(frame,orient='vertical',command=canvas.yview);canvas.configure(xscrollcommand=sx.set,yscrollcommand=sy.set);sx.pack(side='bottom',fill='x');sy.pack(side='right',fill='y');canvas.pack(fill='both',expand=True)
    report=ttk.Frame(panes);panes.add(report,weight=2)
    bar=ttk.Frame(report);bar.pack(fill='x')
    ttk.Label(bar,text='Arıza raporu — ayırıcıyı sürükleyerek genişletin').pack(side='left')
    ttk.Button(bar,text='Raporu büyüt',command=lambda:panes.sashpos(0,80)).pack(side='right')
    ttk.Button(bar,text='Dengeli görünüm',command=lambda:panes.sashpos(0,max(80,panes.winfo_height()//2))).pack(side='right')
    lower=ttk.Panedwindow(report,orient='vertical');lower.pack(fill='both',expand=True)
    report_body=ttk.Frame(lower);lower.add(report_body,weight=2)
    info=tk.Text(report_body,height=8,wrap='word',state='disabled'); scroll=ttk.Scrollbar(report_body,orient='vertical',command=info.yview);info.configure(yscrollcommand=scroll.set);scroll.pack(side='right',fill='y');info.pack(fill='both',expand=True)
    from conversation import route,summary,intent
    current = (selected if selected is not None else app.tree.item(sel[0], 'values'))[:4]
    chat=ttk.LabelFrame(lower,text='Sohbet — ayırıcıyı sürükleyin');lower.add(chat,weight=3)
    controls=ttk.Frame(chat);controls.pack(side='bottom',fill='x')
    history=tk.Text(chat,height=8,wrap='word',state='disabled',padx=10,pady=8); hs=ttk.Scrollbar(chat,command=history.yview);history.configure(yscrollcommand=hs.set);hs.pack(side='right',fill='y');history.pack(fill='both',expand=True)
    history.tag_configure('user',foreground='#175a9c',font=('TkDefaultFont',10,'bold'));history.tag_configure('assistant',foreground='#17643b',font=('TkDefaultFont',10,'bold'))
    askvar = tk.StringVar()
    def expand_chat():
        panes.sashpos(0,55);lower.sashpos(0,45)
    def balance_chat():
        panes.sashpos(0,max(80,panes.winfo_height()//3));lower.sashpos(0,max(60,lower.winfo_height()//2))
    ttk.Button(controls,text='Sohbeti büyüt',command=expand_chat).pack(side='right')
    ttk.Button(controls,text='Dengele',command=balance_chat).pack(side='right')
    deferred=getattr(app,"deferred_questions",[]);app.deferred_questions=[]
    pending=[question or (a+' neden?')] if auto else []
    def append(text):
        history.config(state='normal')
        for line in text.splitlines():
            tag='user' if line.startswith('Sen:') else 'assistant' if line.startswith('Asistan:') else None
            history.insert('end',line+'\n',tag or ())
        history.insert('end','\n');history.see('end');history.config(state='disabled')
    for text in getattr(app,'chat_history',[]):append(text)
    def ask():
        text=askvar.get().strip()
        if not text:return
        try:r=current if intent(text)=="alarms" else route(text,app.rows,current,app.labels)
        except ValueError as e:append(str(e));return
        askvar.set('')
        if busy:
            (pending if r[0]==a and not deferred else deferred).append(text);append('Soru alındı; güncel okuma sonrası cevaplanacak: '+text);return
        if r[0]!=a:
            app.deferred_questions=deferred[:];stop();w.destroy();open_detail(app,r,auto=True,question=text);return
        pending.append(text)
        if app.online:read()
        else:append('Canlı PLC bağlantısı gerekli.');pending.clear()
    def clear_chat():
        pending.clear();deferred.clear();app.chat_history=[];history.config(state='normal');history.delete('1.0','end');history.config(state='disabled')
    ttk.Button(controls,text='Temizle',command=clear_chat).pack(side='right')
    ttk.Button(controls, text='Sor', command=ask).pack(side='right', anchor='n')
    question_entry = QuestionEntry(controls, askvar,
                                   lambda text: suggest(text, app.rows, app.labels, a), ask)
    question_entry.pack(side='left', fill='x', expand=True)
    ttk.Label(w,textvariable=status,wraplength=800).pack()
    def export():
        path=filedialog.asksaveasfilename(parent=w,defaultextension=".txt",filetypes=[("Metin","*.txt")])
        if path:
            try:Path(path).write_text(status.get()+"\n\n"+info.get("1.0","end-1c")+"\n\nSOHBET\n"+history.get("1.0","end-1c"),encoding="utf-8-sig")
            except OSError as e:status.set(str(e))
    ttk.Button(bar,text="Raporu kaydet",command=export).pack(side="right")
    def set_report(msg):
        if info.get('1.0','end-1c')==msg:return
        pos=info.yview()[0];info.configure(state='normal');info.delete('1.0','end');info.insert('end',msg);info.configure(state='disabled');info.yview_moveto(pos)
    zoom=1.0
    def apply_zoom():
        canvas.scale('all',0,0,zoom,zoom)
        for item in canvas.find_all():
            if canvas.type(item)=='text':canvas.itemconfigure(item,font=('TkDefaultFont',max(7,round(10*zoom))))
        if canvas.bbox('all'):canvas.configure(scrollregion=canvas.bbox('all'))
    def change_zoom(delta):
        nonlocal zoom
        zoom=max(.65,min(2.0,zoom+delta));render()
    ttk.Button(bar,text='+',command=lambda:change_zoom(.15)).pack(side='right')
    ttk.Button(bar,text='−',command=lambda:change_zoom(-.15)).pack(side='right')
    def render():
        draw(canvas,cmds,vals,kind,a,stale,follow_address);apply_zoom()
        for i,(op,x) in enumerate(cmds):
            v=1 if x=='P_ON' else 0 if x=='P_OFF' else vals.get(x)
            row=(op,x,'—' if not x else '?' if v is None else v)
            tag='stale' if stale else 'on' if v is not None and op not in ('@AND','%AND?') and (1-v if op in ('LDNOT','ANDNOT') else v)==1 else 'off'
            if i==len(items):items.append(tree.insert('','end',values=row,tags=(tag,)))
            elif tuple(map(str,tree.item(items[i],'values')))!=tuple(map(str,row)) or tuple(tree.item(items[i],'tags'))!=(tag,):tree.item(items[i],values=row,tags=(tag,))
        if stale:
            set_report('Güncel veri yok. Son değerler yalnızca geçmiş bilgi; teşhis durduruldu.');return
        s=evaluate(cmds,vals); msg='Mantık sonucu: doğrulanamadı.'
        if s is not None and len(s)==(2 if kind=='KEEP' else 1) and kind in ('OUT','KEEP','TIM'):
            fmt=lambda v: 'Belirsiz' if v is None else str(v)
            msg=('SET='+fmt(s[0])+' | RESET='+fmt(s[1])) if kind=='KEEP' else 'Giriş koşulu: '+fmt(s[0])
        nodes=build(cmds)
        if nodes and s and s[0]==0:
            def blockers(n):
                if state(n,vals)!=0:return []
                if len(n)==2:return [n[1]+' ('+n[0]+')']
                return blockers(n[1])+blockers(n[2])
            msg+='\nSağlanmayan SET/giriş yolları: '+', '.join(dict.fromkeys(blockers(nodes[0])))
        msg+='\nÇıkış: '+str(vals.get(a,'?'))+'\nKenar tetikleri ve farklı tarama anları nedeniyle kesin kök neden çıkarılmaz.'
        if s and s[0]==0:
            candidates=[]
            for x,v in vals.items():
                if v in (0,1) and x!=a:
                    z=evaluate(cmds,{**vals,x:1-v})
                    if z and z[0]==1:candidates.append(x)
            msg+='\nTek bit değişimiyle koşulu etkileyebilen adaylar: '+(', '.join(candidates) or 'Yok / birden fazla engel olabilir.')
        msg+='\n\nOtomatik kaynak takibi (eşzamanlı olmayan ölçümler):\n'+'\n'.join(trace(a,app.rows,app.logic,vals))
        if kind=="TIM":
            from timer_pv import describe
            msg+="\n"+describe(current[3],pv[0])
        set_report(explain(a,kind,cmds,app.rows,app.logic,vals,app.labels)+"\n\nTEKNİK AYRINTILAR\n"+msg)
    def read():
        nonlocal busy,timer,started
        if busy:return
        if timer is not None:w.after_cancel(timer);timer=None
        if app.live_busy:
            timer=w.after(50,read);return
        if not app.online:status.set('Canlı okuma için önce PLC programını USB üzerinden alın.');return
        busy=True;started=time.monotonic();
        if not last_ok:status.set('USB | İlk veri bekleniyor...')
        p=app.path.get();name=app.plc;enabled=app.block_enabled.get()
        targets=addresses(a,app.rows,app.logic)|{r[0] for r in app.rows}|{x for x,l in app.labels.items() if "ALARM" in l or "AÇILMADI" in l}
        def worker():
            try:
                from timer_pv import command
                pc=command(a) if kind=="TIM" else None
                out,responses,stats=read_targets(p,name,targets,[pc] if pc else [],enabled=enabled)
                q.put((out,'',responses.get(pc) if pc else None,stats,round((time.monotonic()-started)*1000)))
            except Exception as e:q.put(({},str(e),None,None,round((time.monotonic()-started)*1000)))
        threading.Thread(target=worker,daemon=True).start();w.after(25,poll)
    def poll():
        nonlocal busy,running,last_ok,stale,timer,failures
        try:v,e,pv[0],stats,elapsed=q.get_nowait()
        except queue.Empty:w.after(25,poll);return
        busy=False
        if e or not v or any(v.get(x) is None for x in addresses(a,app.rows,app.logic) if x not in ('P_ON','P_OFF') and x in v) or v.get(a) is None:
            stale=True;failures+=1;render();app.update_values({},0);session.close()
            status.set('USB | Güncel veri yok | '+(e or 'Eksik adres yanıtı')+' | Son veri: '+(last_ok or 'yok'))
            if running and failures<4:timer=w.after(2000,tick)
            else:running=False;pending.clear();deferred.clear();append('Okuma başarısız; bekleyen sorular cevaplanamadı. Yeniden başlatabilirsiniz.')
            return
        failures=0;vals.clear();vals.update(v);stale=False;last_ok=datetime.now().strftime('%H:%M:%S');render();gap=app.update_values(v,elapsed,stats);status.set(f'{app.plc} | USB | Son veri: {last_ok} | Okuma: {elapsed} ms | Örnek aralığı: {gap} ms | Eşzamanlı değil'+stats_text(stats))
        while pending:
            question_text=pending.pop(0)
            answer='Sen: '+question_text+'\nAsistan: '+summary(current,app.rows,app.logic,vals,app.labels,question_text,pv[0])+' | '+last_ok
            app.chat_history=(getattr(app,'chat_history',[])+[answer])[-30:];append(answer)
        if deferred:
            text=deferred.pop(0);askvar.set(text);ask();return
        if running:timer=w.after(int(interval.get()),tick)
    def tick():
        nonlocal timer
        timer=None
        if running:read()
    def start():
        nonlocal running,failures
        failures=0
        if app.online and not running:running=True;read()
    def stop():
        nonlocal running,timer
        running=False
        if timer is not None:w.after_cancel(timer);timer=None
    def close():
        if not busy:stop();app.detail_open=False;w.destroy()
    f=ttk.Frame(w);f.pack();
    ttk.Label(f,text="Yenileme bekleme (ms):").pack(side="left")
    ttk.Combobox(f,textvariable=interval,values=("250","500","1000","2000"),state="readonly",width=7).pack(side="left")
    ttk.Checkbutton(f,text='Blok okuma',variable=app.block_enabled).pack(side='left',padx=5)
    for t,c in [('Bir kez oku',read),('İzlemeyi başlat',start),('Durdur',stop),('Kapat',close)]:ttk.Button(f,text=t,command=c).pack(side='left')
    def follow(event):
        if busy:return
        sel=tree.selection()
        if not sel:return
        follow_address(tree.item(sel[0],'values')[1])
    def follow_address(x):
        if busy:return
        matches=[r for r in app.rows if r[0]==x]
        if len(matches)==1:
            stop();w.destroy();open_detail(app,matches[0])
        else:status.set('Tekil üretici bulunamadı: '+x+' | '+str(len(matches))+' eşleşme')
    tree.bind('<Double-1>',follow)
    w.protocol('WM_DELETE_WINDOW',close);render()
    if app.online:w.after(100,start)
