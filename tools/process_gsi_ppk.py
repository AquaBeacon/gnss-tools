"""Reproduce GSI PPK comparisons offline from the archived official RINEX."""
from pathlib import Path
import collections, csv, hashlib, json, math, statistics, subprocess
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'reports/03_PPK/gsi'
OLD = ROOT / 'reports/03_PPK/nearby'
BIN = ROOT / 'tools/rtklib/RTKLIB_EX_2.5.1/rnx2rtkp.exe'
plt.rcParams['font.family'] = 'Yu Gothic'

def obs_info(path):
    lines = path.read_text().splitlines()
    header = lines[:next(i for i,l in enumerate(lines) if 'END OF HEADER' in l)+1]
    epochs = [' '.join(l.split()[1:7]) for l in lines if l.startswith('>')]
    return dict(epochs=len(epochs), first=epochs[0], last=epochs[-1],
                header=header, xyz=next(l[:60].split() for l in header if 'APPROX POSITION XYZ' in l))

def solve(name, base, nav, systems='G,R,E,J,C', interval=None):
    xyz = obs_info(base)['xyz']
    cmd = [str(BIN), '-p','2','-f','3','-sys',systems,'-m','10','-v','3','-c','-t','-r',*xyz]
    if interval: cmd += ['-ti',str(interval)]
    cmd += ['-o',str(OUT/f'{name}.pos'),str(OLD/'rover.obs'),str(base),*[str(n) for n in nav]]
    p = subprocess.run(cmd,capture_output=True,text=True,errors='replace',cwd=ROOT)
    (OUT/f'{name}_log.txt').write_text(p.stdout+p.stderr,encoding='utf-8')
    rows=[]
    for l in (OUT/f'{name}.pos').read_text().splitlines():
        if l.startswith('%') or not l.strip():continue
        f=l.split()
        rows.append(dict(gpst=f[0]+' '+f[1],lat=float(f[2]),lon=float(f[3]),height_m=float(f[4]),quality=int(f[5]),satellites=int(f[6]),age_s=float(f[13]),ar_ratio=float(f[14])))
    if rows:
        with (OUT/f'{name}.csv').open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    result=dict(command=cmd,exit_code=p.returncode,solutions=len(rows),quality_counts=dict(collections.Counter(r['quality'] for r in rows)),max_abs_age_s=max((abs(r['age_s']) for r in rows),default=None),base_ecef_m=xyz)
    assert p.returncode==0 and rows, result
    return result,rows

def run():
    station=next(s for s in json.loads((OUT/'ranked_stations.json').read_text(encoding='utf-8')) if s['observation_cd']=='221245')
    (OUT/'akashi_a_station.json').write_text(json.dumps(station,ensure_ascii=False,indent=2),encoding='utf-8')
    base=OUT/'1245281p.26o'
    gsi_nav=[OUT/f'1245281p.26{s}' for s in ['n','g','l','q']]
    summary=dict(station=station,base=obs_info(base),rover=obs_info(OLD/'rover.obs'),runs={})
    specs=[('gsi_rover_nav',base,[OLD/'rover.nav'],'G,R,E,J,C',None),
           ('gsi_official_nav',base,gsi_nav,'G,R,E,J,C',None),
           ('gsi_gr_30s',base,gsi_nav,'G,R',30),
           ('community_gr_30s',OLD/'base.obs',gsi_nav,'G,R',30)]
    allrows={}
    for name,b,n,sys,interval in specs:
        summary['runs'][name],allrows[name]=solve(name,b,n,sys,interval)
        print(name,summary['runs'][name]['quality_counts'],summary['runs'][name]['solutions'])
    summary['input_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [OLD/'rover.obs',OLD/'rover.nav',OLD/'base.obs',base,*gsi_nav,BIN]}
    (OUT/'comparison_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    fig,axs=plt.subplots(2,2,figsize=(12,8))
    titles=['地理院OBS＋移動局NAV（1秒）','地理院OBS＋地理院NAV（1秒）','地理院OBS＋地理院NAV（G/R・30秒）','従来局OBS＋地理院NAV（G/R・30秒）']
    for ax,(name,rows),title in zip(axs.flat,allrows.items(),titles):
        times=[(float(r['gpst'][14:16])*60+float(r['gpst'][17:]))-(30*60+30.001) for r in rows]
        if not name.endswith('30s'):
            x=[];y=[]
            for i,(t,r) in enumerate(zip(times,rows)):
                if i and t-times[i-1]>1.5:x.append(float('nan'));y.append(float('nan'))
                x.append(t);y.append(r['quality'])
            ax.step(x,y,where='post')
        ax.scatter(times,[r['quality'] for r in rows],s=12)
        ax.set(title=title,xlabel='観測開始からの経過時間 (s)',ylabel='Q (1=FIX / 2=FLOAT / 4=DGPS)',yticks=[1,2,4,5],xlim=(-5,365));ax.grid(alpha=.3)
    fig.tight_layout();fig.savefig(OUT/'gsi_quality_comparison.png',dpi=160);plt.close(fig)
    rows=allrows['gsi_official_nav'];lat=statistics.median(r['lat'] for r in rows);lon=statistics.median(r['lon'] for r in rows)
    east=[math.radians(r['lon']-lon)*6378137*math.cos(math.radians(lat)) for r in rows]
    north=[math.radians(r['lat']-lat)*6378137 for r in rows]
    fig,axs=plt.subplots(1,2,figsize=(11,4))
    axs[0].scatter(east,north,c=[r['quality'] for r in rows],s=12)
    axs[0].set(xlabel='解の中央値からの東変位 (m)',ylabel='北変位 (m)',title='地理院OBS＋地理院放送暦：位置のばらつき');axs[0].axis('equal')
    axs[1].plot([r['age_s'] for r in rows]);axs[1].set(xlabel='出力エポック番号',ylabel='基準局との観測時刻差 (s)',title='30秒間隔の基準局観測を使用')
    fig.tight_layout();fig.savefig(OUT/'gsi_position_age.png',dpi=160);plt.close(fig)

if __name__=='__main__':run()
