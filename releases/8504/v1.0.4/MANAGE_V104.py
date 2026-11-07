#!/usr/bin/env python3
"""Isolated v1.0.4 Mac lab launcher; start/stop/status/verify only."""
from __future__ import annotations
import argparse, hashlib, json, os, signal, socket, subprocess, sys, time
from pathlib import Path
DIR=Path(__file__).resolve().parent
ROOT=Path.home()/'projects/mondo_eval/release_records/8504_8510/isolated'
APP=DIR/'streamlit_app_8504_stage5_immutable_save_v01.py'
PORT=18535
PID=DIR/'.streamlit_18535.pid'
LOG=DIR/'streamlit_18535.log'
def sha(b):return hashlib.sha256(b).hexdigest()
def meta():return json.loads((DIR/'MANIFEST_V104.json').read_text(encoding='utf-8'))
def verify():
    m=meta()
    if m.get('version')!='v1.0.4':raise RuntimeError('VERSION_MISMATCH')
    for n,expect in m['files'].items():
        path=DIR/n
        if not path.is_file() or path.is_symlink() or sha(path.read_bytes())!=expect:raise RuntimeError('SHA_MISMATCH:'+n)
    print('V104_INSTALLED_FILE_SHA_READBACK=PASS; API_CALLS=0; GITHUB_PUBLISHED=NO')
def command(pid):
    p=subprocess.run(['ps','-ww','-p',str(pid),'-o','command='],capture_output=True,text=True)
    return p.stdout.strip() if p.returncode==0 else ''
def is_ours(pid):
    s=command(pid)
    return bool(s) and ('-m streamlit run' in s and str(APP) in s and '--server.port '+str(PORT) in s)
def listening():
    s=socket.socket();s.settimeout(0.4)
    try:s.bind(('127.0.0.1',PORT));return False
    except OSError:return True
    finally:s.close()
def status():
    pid=int(PID.read_text()) if PID.exists() and PID.read_text().strip().isdigit() else None
    ok=bool(pid and is_ours(pid) and listening())
    print('V104_18535_STATUS='+('RUNNING' if ok else ('PORT_HELD_BY_OTHER' if listening() else 'STOPPED')))
    return ok
def start():
    verify()
    if status():print('V104_ALREADY_RUNNING; NO_NEW_PROCESS');return
    if listening():raise RuntimeError('PORT_18535_IN_USE; NO_PROCESS_TERMINATED')
    py=Path.home()/'projects/mondo_eval/venv_hybrid/bin/python'
    if not py.is_file() or not os.access(py,os.X_OK):raise RuntimeError('PINNED_PYTHON_MISSING')
    roots=[DIR,ROOT/'8504_8510_STAGE4C_DIRECT_8510_API_20261107_V01',ROOT/'8504_8510_STAGE4_CONSENT_PREVIEW_20261107_V01_FIX1',ROOT/'8504_8510_STAGE12_ISOLATED_V02_20261107']
    if not all(p.is_dir() and not p.is_symlink() for p in roots):raise RuntimeError('MAC_V14_RUNTIME_DEPENDENCY_MISSING')
    env=os.environ.copy();env['PYTHONDONTWRITEBYTECODE']='1'
    env['STAGE4C_PAID_API_ENABLED']='EXPLICIT_V14_SINGLE_PAID_API_CALL_APPROVED'
    env['PYTHONPATH']=os.pathsep.join([str(p) for p in roots]+([env['PYTHONPATH']] if env.get('PYTHONPATH') else []))
    argv=[str(py),'-m','streamlit','run',str(APP),'--server.address','127.0.0.1','--server.port',str(PORT),'--server.headless','true','--server.fileWatcherType','none','--browser.gatherUsageStats','false']
    with LOG.open('ab') as f:proc=subprocess.Popen(argv,env=env,cwd=str(Path.home()),stdout=f,stderr=subprocess.STDOUT,start_new_session=True,close_fds=True)
    PID.write_text(str(proc.pid)+'\n')
    for _ in range(25):
        if proc.poll() is not None:raise RuntimeError('STREAMLIT_EXITED; CHECK_LOG')
        if listening():break
        time.sleep(0.2)
    print('V104_LAUNCHED=http://127.0.0.1:18535/; LIVE_UI=EXPLICIT_BYOK_AND_CONSENT_ONLY; API_CALLS_ON_START=0; PID='+str(proc.pid))
def stop():
    if not PID.exists():print('V104_NO_PID_RECORD; NOTHING_STOPPED');return
    s=PID.read_text().strip()
    if not s.isdigit():raise RuntimeError('PID_RECORD_INVALID')
    pid=int(s)
    if not is_ours(pid):raise RuntimeError('PID_COMMAND_MISMATCH; NOTHING_TERMINATED')
    os.kill(pid,signal.SIGTERM)
    for _ in range(30):
        if not is_ours(pid):break
        time.sleep(0.2)
    if is_ours(pid):raise RuntimeError('STOP_TIMEOUT; NO_FORCED_KILL')
    PID.unlink(missing_ok=True)
    print('V104_STOP_ONLY_18535=PASS')
def main():
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=('verify','status','start','stop'))
    a=ap.parse_args().action
    if a=='verify':verify()
    elif a=='status':status()
    elif a=='start':start()
    else:stop()
if __name__=='__main__':
    try:main()
    except Exception as e:print('V104_MANAGER_HOLD='+type(e).__name__+': '+str(e),file=sys.stderr);sys.exit(2)
