import tkinter as tk

def build(cmds):
    s=[]
    for op,a in cmds:
        if op in ('LD','LDNOT'):s.append((op,a))
        elif op in ('ANDLD','ORLD') and len(s)>=2:
            b=s.pop();s[-1]=('series' if op=='ANDLD' else 'parallel',s[-1],b)
        elif op in ('AND','ANDNOT','OR','@AND','%AND?') and s:
            s[-1]=('parallel' if op=='OR' else 'series',s[-1],(op,a))
        else:return None
    return s

def state(n,vals):
    op=n[0]
    if op in ('series','parallel'):
        a,b=[state(x,vals) for x in n[1:]]
        return (0 if 0 in (a,b) else 1 if a==b==1 else None) if op=='series' else (1 if 1 in (a,b) else 0 if a==b==0 else None)
    v=1 if n[1]=='P_ON' else 0 if n[1]=='P_OFF' else vals.get(n[1])
    return None if op in ('@AND','%AND?') or v is None else 1-v if op in ('LDNOT','ANDNOT') else v

def size(n):
    if len(n)==2:return 135,65
    a,b=map(size,n[1:]);return (a[0]+b[0],max(a[1],b[1])) if n[0]=='series' else (max(a[0],b[0])+40,a[1]+b[1])

def draw(c,cmds,vals,kind,target,stale=False,follow=None):
    c.delete('all'); nodes=build(cmds)
    if nodes is None or len(nodes)!=(2 if kind=='KEEP' else 1):
        c.create_text(15,20,anchor='nw',text='Grafik oluşturulamadı: desteklenmeyen veya belirsiz komut dizisi.');return
    def color(n):return '#888888' if stale else {0:'#b42318',1:'#16803b',None:'#9a6700'}[state(n,vals)]
    def line(x,y,x2,y2,col):c.create_line(x,y,x2,y2,fill=col,width=2)
    def flow(a,b):return 0 if 0 in (a,b) else 1 if a==b==1 else None
    def fc(v):return "#888888" if stale else {0:"#999999",1:"#16803b",None:"#9a6700"}[v]
    def node(n,x,y,w,incoming=1):
        col=color(n);op=n[0]; outgoing=flow(incoming,state(n,vals))
        if len(n)==2:
            m=x+w/2;line(x,y,m-12,y,fc(incoming));line(m+12,y,x+w,y,fc(outgoing))
            line(m-12,y-10,m-12,y+10,col);line(m+12,y-10,m+12,y+10,col)
            if op in ('LDNOT','ANDNOT'):line(m-12,y+10,m+12,y-10,col)
            item=c.create_text(m,y-21,text=n[1],fill=col);c.create_text(m,y+21,text='PLC:'+str(1 if n[1]=='P_ON' else 0 if n[1]=='P_OFF' else vals.get(n[1],'?'))+' / '+('kenar ?' if op in ('@AND','%AND?') else str(state(n,vals))),fill=col)
            if follow:c.tag_bind(item,'<Double-1>',lambda e,a=n[1]:follow(a))
        elif op=='series':
            a=size(n[1])[0];b=size(n[2])[0];split=w*a/(a+b);node(n[1],x,y,split,incoming);node(n[2],x+split,y,w-split,flow(incoming,state(n[1],vals)))
        else:
            h1=size(n[1])[1];h2=size(n[2])[1];ya=y-h2/2;yb=y+h1/2
            line(x,y,x+20,y,fc(incoming));line(x+20,ya,x+20,yb,fc(incoming));line(x+w-20,ya,x+w-20,y,fc(flow(incoming,state(n[1],vals))));line(x+w-20,y,x+w-20,yb,fc(flow(incoming,state(n[2],vals))));line(x+w-20,y,x+w,y,fc(outgoing))
            node(n[1],x+20,ya,w-40,incoming);node(n[2],x+20,yb,w-40,incoming)
    y=25; width=max(size(n)[0] for n in nodes)
    for i,n in enumerate(nodes):
        h=size(n)[1];mid=y+h/2;c.create_text(12,y,anchor='nw',text=('SET' if i==0 else 'RESET') if kind=='KEEP' else 'Giriş');node(n,65,mid,width);c.create_text(65+width+65,mid,text=target+' '+kind,fill=color(n));y+=h+25
    c.configure(scrollregion=(0,0,width+210,y+15))
