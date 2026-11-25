import atexit,json,os,re,subprocess,tempfile,threading,time
from pathlib import Path
from block_read import fields,read_batched

class Session:
    def __init__(self):
        self.lock=threading.RLock();self.proc=None;self.folder=None;self.cdm=None;self.disabled=set()
    def close(self):
        with self.lock:
            if self.proc:
                try:
                    Path(self.folder.name,'stop').touch();self.proc.wait(timeout=3)
                except Exception:
                    self.proc.kill();self.proc.wait()
            self.proc=None;self.cdm=None;self.disabled.clear()
            if self.folder:self.folder.cleanup();self.folder=None
    def read(self,cdm,commands,enabled=True):
        with self.lock:
            if self.cdm!=cdm or self.proc is None or self.proc.poll() is not None:self.disabled.clear()
            return read_batched(lambda cmds:self._read(cdm,cmds),commands,self.disabled,enabled)
    def _read(self,cdm,commands):
        if not commands:raise ValueError("Okunacak adres yok")
        for c in commands:fields(c)
        with self.lock:
            try:
                if self.proc is None or self.proc.poll() is not None or self.cdm!=cdm:
                    self.close();self.folder=tempfile.TemporaryDirectory();self.cdm=cdm
                    ps=Path(os.environ.get('SystemRoot',r'C:\Windows'))/'SysWOW64/WindowsPowerShell/v1.0/powershell.exe'
                    self.proc=subprocess.Popen([str(ps),'-NoProfile','-STA','-ExecutionPolicy','Bypass','-File',str(Path(__file__).with_name('session.ps1')),'-Folder',self.folder.name,'-Cdm',cdm],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                d=Path(self.folder.name);p=d/'request.tmp';p.write_text(json.dumps({'commands':commands}),encoding='utf-8');p.replace(d/'request.json')
                deadline=time.monotonic()+30
                while time.monotonic()<deadline:
                    if (d/'error.txt').exists():raise RuntimeError((d/'error.txt').read_text(encoding='utf-8-sig'))
                    if (d/'result.json').exists():
                        q=d/'result.json';r=json.loads(q.read_text(encoding='utf-8-sig'));q.unlink()
                        if r.get('error'):raise RuntimeError(r['error'])
                        return r
                    if self.proc.poll() is not None:raise RuntimeError('USB oturumu kapandı')
                    time.sleep(.01)
                raise TimeoutError('USB okuma zaman aşımı')
            except Exception:
                self.close();raise
session=Session()
atexit.register(session.close)
