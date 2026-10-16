"""Bounded supplementary base recording; never connects to the rover serial port."""
import socket,time,json,sys,io,collections
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'.deps'))
from pyrtcm import RTCMReader
host,mount,folder,duration=sys.argv[1:]
out=ROOT/folder;out.mkdir(parents=True,exist_ok=False)
events=[];end=time.monotonic()+float(duration)
with (out/'base.rtcm3').open('wb') as f:
    while time.monotonic()<end:
        try:
            with socket.create_connection((host,2101),timeout=8) as s:
                s.settimeout(2);s.sendall(f'GET /{mount} HTTP/1.0\r\nUser-Agent: NTRIP GNSSVerification/1.0\r\n\r\n'.encode())
                header=b''
                while not header.endswith(b'\r\n'):
                    b=s.recv(1)
                    if not b:raise RuntimeError('Header disconnect')
                    header+=b
                if not header.startswith(b'ICY 200'):raise RuntimeError(repr(header))
                events.append(dict(utc=datetime.now(timezone.utc).isoformat(),event='connected'))
                print(events[-1],flush=True);last=time.monotonic()
                while time.monotonic()<end:
                    try:b=s.recv(65536)
                    except socket.timeout:
                        if time.monotonic()-last>15:raise TimeoutError('No corrections for 15s')
                        continue
                    if not b:break
                    f.write(b);f.flush();last=time.monotonic()
        except Exception as e:
            events.append(dict(utc=datetime.now(timezone.utc).isoformat(),event='error',error=str(e)))
            print(events[-1],flush=True);time.sleep(2)
signals={};counts=collections.Counter()
for raw,m in RTCMReader(io.BytesIO((out/'base.rtcm3').read_bytes())):
    if m:
        counts[m.identity]+=1
        for i in range(1,getattr(m,'NCell',0)+1):signals.setdefault(m.identity,set()).add(str(getattr(m,f'CELLSIG_{i:02}')))
result=dict(host=host,mount=mount,events=events,counts=dict(counts),signals={k:sorted(v) for k,v in signals.items()})
(out/'capture.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
