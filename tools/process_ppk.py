"""Convert concurrent receiver/base logs and run actual RTKLIB PPK."""
from pathlib import Path
import subprocess,json,sys,csv,collections,math
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1];R=ROOT/'reports'/(sys.argv[1] if len(sys.argv)>1 else 'nearby');OUT=R/'03_PPK';BIN=ROOT/'tools/rtklib/RTKLIB_EX_2.5.1'
plt.rcParams['font.family']='Yu Gothic'
events=json.loads((R/'01_Basic/test_events.json').read_text(encoding='utf-8'))
utc=next(e['utc'] for e in events if e['event']=='ntrip_connected');date=utc[:10].replace('-','/');hms=utc[11:19]
steps=[]
def run(name,args):
    p=subprocess.run([str(x) for x in args],capture_output=True,text=True,errors='replace',cwd=ROOT)
    (OUT/f'{name}_log.txt').write_text(p.stdout+p.stderr,encoding='utf-8')
    steps.append({'step':name,'command':[str(x) for x in args],'exit_code':p.returncode})
run('rover_conversion',[BIN/'convbin.exe','-r','ubx','-v','3.04','-os','-od','-o',OUT/'rover.obs','-n',OUT/'rover.nav',OUT/'rover.ubx'])
run('base_conversion',[BIN/'convbin.exe','-r','rtcm3','-tr',date,hms,'-v','3.04','-os','-o',OUT/'base.obs','-n',OUT/'base.nav',R/'02_RTK/concurrent_base.rtcm3'])
summary={'steps':steps,'time_approximation_utc':utc}
for name in ['rover','base']:
    epochs=[];header=[];in_header=True
    for l in (OUT/f'{name}.obs').read_text().splitlines():
        if in_header:header.append(l)
        if 'END OF HEADER' in l:in_header=False
        if l.startswith('>'):
            f=l.split();epochs.append({'gps_epoch':' '.join(f[1:7]),'satellites':int(f[8])})
    summary[name]={'epochs':len(epochs),'first':epochs[0] if epochs else None,'last':epochs[-1] if epochs else None,'observation_types':[l for l in header if 'SYS / # / OBS TYPES' in l]}
    with (OUT/f'{name}_rinex_epochs.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['gps_epoch','satellites']);w.writeheader();w.writerows(epochs)
    if name=='base':xyz=next(l[:60].split()[:3] for l in header if 'APPROX POSITION XYZ' in l)
run('ppk',[BIN/'rnx2rtkp.exe','-p','2','-f','3','-sys','G,R,E,J,C','-m','10','-v','3','-c','-t','-r',*xyz,'-o',OUT/'ppk.pos',OUT/'rover.obs',OUT/'base.obs',OUT/'rover.nav'])
solutions=[]
if (OUT/'ppk.pos').exists():
    for l in (OUT/'ppk.pos').read_text().splitlines():
        if l.startswith('%') or not l.strip():continue
        f=l.split()
        if len(f)>=7:
            solutions.append({'gps_time':f[0]+' '+f[1],'lat':float(f[2]),'lon':float(f[3]),'height_m':float(f[4]),'quality':int(f[5]),'satellites':int(f[6]),'age_s':float(f[13]),'ar_ratio':float(f[14])})
summary['ppk']={'solutions':len(solutions),'quality_counts':dict(collections.Counter(r['quality'] for r in solutions)),'base_ecef_m':xyz,'settings':'kinematic, combined forward/backward, L1+L2+L5, 10deg elevation mask, AR ratio 3, G/R/E/J/C'}
summary['ppk']['max_abs_age_s']=max((abs(r['age_s']) for r in solutions),default=None)
if solutions:
    with (OUT/'ppk_solutions.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(solutions[0]));w.writeheader();w.writerows(solutions)
    lat=sum(r['lat'] for r in solutions)/len(solutions);lon=sum(r['lon'] for r in solutions)/len(solutions)
    east=[(r['lon']-lon)*math.pi/180*6378137*math.cos(math.radians(lat)) for r in solutions];north=[(r['lat']-lat)*math.pi/180*6378137 for r in solutions]
    fig,axs=plt.subplots(1,2,figsize=(11,4));sc=axs[0].scatter(east,north,c=[r['quality'] for r in solutions],s=12,cmap='viridis');fig.colorbar(sc,ax=axs[0],ticks=[1,2,4],label='RTKLIB Q (1=FIX, 2=FLOAT, 4=DGPS)');axs[0].set(xlabel='平均位置からの東方向変位 (m)',ylabel='北方向変位 (m)',title='PPK解のばらつき（絶対誤差ではありません）');axs[0].axis('equal');axs[1].plot([r['quality'] for r in solutions],drawstyle='steps-post');axs[1].set(xlabel='出力エポック番号',ylabel='RTKLIB Q',title='PPK解析の解状態');fig.tight_layout();fig.savefig(OUT/'ppk_results.png',dpi=160);plt.close(fig)
(OUT/'ppk_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
