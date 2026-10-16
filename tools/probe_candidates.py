import sys, socket, time, io, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'.deps'))
from pyrtcm import RTCMReader
for host,mount in [('ntrip1.bizstation.jp','3C722D56'),('geortk.jp','geosense_f9p_rtcm'),('geortk.jp','btf_nishiyamacho3')]:
    out=ROOT/'reports/02_RTK'/mount;out.mkdir(exist_ok=True)
    result={'host':host,'port':2101,'mountpoint':mount}
    try:
        with socket.create_connection((host,2101),timeout=5) as s:
            s.settimeout(2);s.sendall(f'GET /{mount} HTTP/1.0\r\nUser-Agent: NTRIP GNSSVerification/1.0\r\n\r\n'.encode());data=b'';end=time.monotonic()+12
            while time.monotonic()<end:
                try:b=s.recv(65536)
                except socket.timeout:continue
                if not b:break
                data+=b
            (out/'capture.bin').write_bytes(data);result['header']=data[:50].decode(errors='replace')
            messages=[];signals={}
            for raw,m in RTCMReader(io.BytesIO(data)):
                if m:
                    messages.append(m.identity)
                    if hasattr(m,'NCell'):signals.setdefault(m.identity,set()).update(str(getattr(m,f'CELLSIG_{i:02}')) for i in range(1,m.NCell+1))
            result.update(bytes=len(data),message_types=sorted(set(messages)),signals={k:sorted(v) for k,v in signals.items()})
    except Exception as e:result['error']=str(e)
    (out/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
