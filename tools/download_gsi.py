"""Download the archived request through GSI's public form workflow (no account)."""
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from html.parser import HTMLParser
import datetime, gzip, hashlib, io, json, re, tarfile

OUT=Path(__file__).resolve().parents[1]/'reports/03_PPK/gsi'
class Inputs(HTMLParser):
    def __init__(self):super().__init__();self.fields={}
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='input' and 'name' in a:self.fields[a['name']]=a.get('value','')

def run():
    payload=json.loads((OUT/'request.json').read_text())
    page=urlopen(Request('https://terras.gsi.go.jp/hour_download.php',data=urlencode(payload).encode()),timeout=45).read().decode()
    (OUT/'hour_response.html').write_text(page,encoding='utf-8')
    parser=Inputs();parser.feed(page);manifest=[]
    files=re.findall(r"one_file_download\('([^']+)','([^']+)','([^']+)','([^']+)'\)",page)
    if not files:raise RuntimeError('No downloadable files; hourly availability window may have expired.')
    for station,filename,kind,tmp in files:
        fields=dict(parser.fields)
        fields.update(satellite_type=payload['hour_satellite'],data_type=kind,observation_date='2026-10-08',d_mode='[hour] GRJE 3.02 2026/10/08.15 2026/10/08.16',d_obs_cd=station,d_file=filename,d_tmp_dir=tmp,d_satellite='DOWNLOAD',d_rv=payload['hour_rinex_ver'])
        response=urlopen(Request('https://terras.gsi.go.jp/download.php',data=urlencode(fields).encode()),timeout=60)
        data=response.read();(OUT/Path(filename).name).write_bytes(data)
        manifest.append(dict(filename=filename,bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),content_type=response.headers.get('Content-Type'),retrieved_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),endpoint=response.url))
        if filename.endswith('.tar.gz'):
            with tarfile.open(fileobj=io.BytesIO(data),mode='r:gz') as tar:
                for member in tar.getmembers():
                    if member.isfile():(OUT/Path(member.name).name).write_bytes(tar.extractfile(member).read())
        else:(OUT/Path(filename[:-3]).name).write_bytes(gzip.decompress(data))
    (OUT/'download_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')

if __name__=='__main__':run()
