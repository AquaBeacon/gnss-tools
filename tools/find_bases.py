import socket, math, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
rows=[]
for host in ['geortk.jp','ntrip1.bizstation.jp']:
    try:
        with socket.create_connection((host,2101),timeout=6) as s:
            s.settimeout(3);s.sendall(b'GET / HTTP/1.0\r\nUser-Agent: NTRIP GNSSVerification/1.0\r\n\r\n');data=b''
            while b'ENDSOURCETABLE' not in data:
                b=s.recv(65536)
                if not b:break
                data+=b
        (ROOT/'reports/02_RTK'/f'{host}_sourcetable.txt').write_bytes(data)
        for l in data.decode(errors='replace').splitlines():
            f=l.split(';')
            if len(f)>11 and f[0]=='STR':
                try:
                    lat,lon=float(f[9]),float(f[10]);a,b,c,d=map(math.radians,[lat,lon,34.68688,135.06037]);dist=6371*2*math.asin(math.sqrt(math.sin((a-c)/2)**2+math.cos(a)*math.cos(c)*math.sin((b-d)/2)**2))
                    rows.append({'host':host,'mountpoint':f[1],'distance_km':dist,'format':f[3],'details':f[4],'receiver':f[13] if len(f)>13 else '', 'auth':f[15] if len(f)>15 else ''})
                except ValueError:pass
    except Exception as e:print(host,str(e))
rows.sort(key=lambda r:r['distance_km'])
(ROOT/'reports/02_RTK/base_candidates.json').write_text(json.dumps(rows,indent=2))
print(json.dumps(rows[:15],indent=2))
