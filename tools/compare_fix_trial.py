"""Compare real standalone/RTK measurements and independently check PPK directions."""
import sys,json,csv,collections,subprocess,math,statistics,hashlib
from pathlib import Path
from datetime import datetime,timezone,timedelta
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
R=ROOT/'reports'/sys.argv[1]
OUT=R/'03_PPK'
BIN=ROOT/'tools/rtklib/RTKLIB_EX_2.5.1'
plt.rcParams['font.family']='Yu Gothic'
records=[json.loads(l) for l in (R/'01_Basic/receiver_messages.jsonl').read_text().splitlines()]
events=json.loads((R/'01_Basic/test_events.json').read_text(encoding='utf-8'))
pvt=[r for r in records if r['identity']=='NAV-PVT']
rtcm=[r['data'] for r in records if r['identity']=='RXM-RTCM']
valid=[r for r in pvt if r['data'].get('gnssFixOk')]
steps=[]
def run(name,args):
    command=[str(a) for a in args]
    p=subprocess.run(command,capture_output=True,text=True,errors='replace')
    (OUT/(name+'_log.txt')).write_text(p.stdout+p.stderr,encoding='utf-8')
    steps.append(dict(name=name,command=command,exit_code=p.returncode))
    if p.returncode:raise RuntimeError(name+' failed')
def parse_pos(path):
    rows=[]
    for l in path.read_text().splitlines():
        if l.startswith('%') or not l.strip():continue
        f=l.split()
        rows.append(dict(time=f[0]+' '+f[1],lat=float(f[2]),lon=float(f[3]),height=float(f[4]),q=int(f[5]),ns=int(f[6]),age=float(f[13]),ratio=float(f[14])))
    return rows
def longest_run(rows,predicate):
    best=cur=0;previous=None
    for r in rows:
        t=datetime.strptime(r['time'],'%Y/%m/%d %H:%M:%S.%f')
        if predicate(r):cur=cur+1 if previous and (t-previous).total_seconds()<=1.5 else 1
        else:cur=0
        best=max(best,cur);previous=t
    return best
xyz=next(l[:60].split()[:3] for l in (OUT/'base.obs').read_text().splitlines() if 'APPROX POSITION XYZ' in l)
config=OUT/'comparison_ppk.conf'
config.write_text('pos2-maxage = 1\n',encoding='ascii')
common=[BIN/'rnx2rtkp.exe','-k',config,'-f','3','-sys','G,R,E,J,C','-m','10','-v','3','-t','-r',*xyz]
inputs=[OUT/'rover.obs',OUT/'base.obs',OUT/'rover.nav']
if not all(p.exists() for p in inputs):raise FileNotFoundError('Required rover/base OBS or rover NAV missing')
if (OUT/'base.nav').exists():inputs.append(OUT/'base.nav')
solutions={}
alt=R/'02_RTK/alternative'
alternative_inputs=None
if (alt/'capture.json').exists():
    first=json.loads((alt/'capture.json').read_text())['events'][0]['utc']
    run('alternative_conversion',[BIN/'convbin.exe','-r','rtcm3','-tr',first[:10].replace('-','/'),first[11:19],'-v','3.04','-o',OUT/'alternative_base.obs','-n',OUT/'alternative_base.nav',alt/'base.rtcm3'])
    altxyz=next(l[:60].split()[:3] for l in (OUT/'alternative_base.obs').read_text().splitlines() if 'APPROX POSITION XYZ' in l)
    alternative_inputs=[p for p in [OUT/'rover.obs',OUT/'alternative_base.obs',OUT/'rover.nav',OUT/'alternative_base.nav'] if p.exists()]
for name,mode,direction in [('kinematic_forward','2',[]),('kinematic_backward','2',['-b']),('kinematic_combined','2',['-c']),('static_forward','3',[]),('static_backward','3',['-b']),('static_combined','3',['-c'])]:
    run(name,[*common,'-p',mode,*direction,'-o',OUT/(name+'.pos'),*inputs])
    solutions[name]=parse_pos(OUT/(name+'.pos'))
    if solutions[name]:
        with (OUT/(name+'.csv')).open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(solutions[name][0]));w.writeheader();w.writerows(solutions[name])
run('single_code',[BIN/'rnx2rtkp.exe','-p','0','-f','3','-sys','G,R,E,J,C','-m','10','-t','-o',OUT/'single_code.pos',OUT/'rover.obs',OUT/'rover.nav',*([OUT/'base.nav'] if (OUT/'base.nav').exists() else [])])
single=parse_pos(OUT/'single_code.pos')
common_times={r['time'] for r in solutions['kinematic_combined']}
single=[r for r in single if r['time'] in common_times and r['q']==5]
if alternative_inputs:
    for name,mode in [('alternative_kinematic_combined','2'),('alternative_static_combined','3')]:
        run(name,[BIN/'rnx2rtkp.exe','-k',config,'-p',mode,'-f','3','-sys','G,R,E,J,C','-m','10','-v','3','-c','-t','-r',*altxyz,'-o',OUT/(name+'.pos'),*alternative_inputs])
        solutions[name]=parse_pos(OUT/(name+'.pos'))
l5=R/'02_RTK/alternative_l5'
if (l5/'capture.json').exists():
    first=json.loads((l5/'capture.json').read_text())['events'][0]['utc']
    run('l5_base_conversion',[BIN/'convbin.exe','-r','rtcm3','-tr',first[:10].replace('-','/'),first[11:19],'-v','3.04','-o',OUT/'l5_base.obs','-n',OUT/'l5_base.nav',l5/'base.rtcm3'])
    l5xyz=next(l[:60].split()[:3] for l in (OUT/'l5_base.obs').read_text().splitlines() if 'APPROX POSITION XYZ' in l)
    for name,mode in [('l5_kinematic_combined','2'),('l5_static_combined','3')]:
        l5inputs=[p for p in [OUT/'rover.obs',OUT/'l5_base.obs',OUT/'rover.nav',OUT/'l5_base.nav'] if p.exists()]
        run(name,[BIN/'rnx2rtkp.exe','-k',config,'-p',mode,'-f','3','-sys','G,R,E,J,C','-m','10','-v','3','-c','-t','-r',*l5xyz,'-o',OUT/(name+'.pos'),*l5inputs])
        solutions[name]=parse_pos(OUT/(name+'.pos'))
    inputs+=l5inputs

# Each method is centered on its own median: this measures repeatability, not truth error.
origin=(statistics.median(r['data']['lat'] for r in valid),statistics.median(r['data']['lon'] for r in valid))
def en(rows):
    lat=np.array([r['lat'] for r in rows]);lon=np.array([r['lon'] for r in rows])
    return (lon-origin[1])*math.pi/180*6378137*math.cos(math.radians(origin[0])),(lat-origin[0])*math.pi/180*6378137
def stats(rows):
    if not rows:return dict(epochs=0)
    e,n=en(rows);e=e-np.median(e);n=n-np.median(n);radius=np.hypot(e,n)
    return dict(epochs=len(rows),horizontal_rms_about_median_m=float(np.sqrt(np.mean(radius**2))),horizontal_p95_about_median_m=float(np.percentile(radius,95)),east_std_m=float(np.std(e)),north_std_m=float(np.std(n)),median_lat=float(np.median([r['lat'] for r in rows])),median_lon=float(np.median([r['lon'] for r in rows])))
groups={}
for name,predicate in [('Standalone',lambda r:r['phase']=='standalone' and not r['data'].get('diffSoln') and r['data']['carrSoln']==0),('RTK FLOAT',lambda r:r['phase']=='rtk_connected' and r['data']['carrSoln']==1),('RTK FIX',lambda r:r['phase']=='rtk_connected' and r['data']['carrSoln']==2)]:
    groups[name]=[dict(lat=r['data']['lat'],lon=r['data']['lon'],hacc=r['data']['hAcc']/1000,elapsed=r['elapsed_s']) for r in valid if predicate(r)]
groups['PPK FLOAT']=[r for r in solutions['kinematic_combined'] if r['q']==2]
groups['PPK FIX']=[r for r in solutions['kinematic_combined'] if r['q']==1]
groups['GNSS single (same PPK epochs)']=single
single_times={r['time'] for r in single}
groups['PPK (same GNSS epochs, all Q)']=[r for r in solutions['kinematic_combined'] if r['time'] in single_times]
summary={name:stats(rows) for name,rows in groups.items()}
for name in ['Standalone','RTK FLOAT','RTK FIX']:
    if groups[name]:summary[name]['median_receiver_hacc_m']=statistics.median(r['hacc'] for r in groups[name])
ppk={name:dict(epochs=len(rows),quality_counts=dict(collections.Counter(r['q'] for r in rows)),longest_fix_run_epochs=longest_run(rows,lambda r:r['q']==1),max_age_s=max((abs(r['age']) for r in rows),default=None)) for name,rows in solutions.items()}
forward={r['time']:r for r in solutions['kinematic_forward']}
backward={r['time']:r for r in solutions['kinematic_backward']}
agreed=[]
for t,a in forward.items():
    b=backward.get(t)
    if b and a['q']==b['q']==1:
        ea,na=en([a,b]);agreed.append(dict(time=t,horizontal_difference_m=float(math.hypot(ea[0]-ea[1],na[0]-na[1])),height_difference_m=abs(a['height']-b['height'])))
cn=[];raw_signal=collections.Counter();resets=collections.Counter();last_lock={}
for r in records:
    d=r['data']
    if r['identity']=='NAV-SAT':
        values=[d.get(f'cno_{i:02}',0) for i in range(1,d['numSvs']+1)]
        values=[v for v in values if v>0]
        if values:cn.append(statistics.median(values))
    if r['identity']=='RXM-RAWX':
        for i in range(1,d['numMeas']+1):
            key=(d[f'gnssId_{i:02}'],d[f'svId_{i:02}'],d[f'sigId_{i:02}'])
            lock=d.get(f'locktime_{i:02}',0)
            if key in last_lock and lock<last_lock[key]:resets[key]+=1
            last_lock[key]=lock
            if d.get(f'cpValid_{i:02}'):raw_signal[(d[f'gnssId_{i:02}'],d[f'sigId_{i:02}'])]+=1
rtk=[r for r in valid if r['phase']=='rtk_connected']
fixed=[r for r in rtk if r['data']['carrSoln']==2]
connected=next(e for e in events if e['event']=='ntrip_connected')
phase_durations={e['phase']:e['duration_s'] for e in events if e['event']=='phase_start'}
start_jst=datetime.fromisoformat(events[0]['utc']).astimezone(timezone(timedelta(hours=9))).isoformat()
result=dict(comparison=summary,ppk=ppk,forward_backward_fixed_common_epochs=len(agreed),forward_backward_agreement=agreed,
            rtk_epochs=len(rtk),rtk_fixed_epochs=len(fixed),rtk_fix_fraction=len(fixed)/len(rtk) if rtk else None,
            time_to_first_rtk_fix_s=fixed[0]['elapsed_s']-connected['elapsed_s'] if fixed else None,
            rtcm=dict(messages=len(rtcm),crc_failed=sum(d['crcFailed'] for d in rtcm),used=sum(d['msgUsed']==2 for d in rtcm)),
            median_cn0_dbhz=statistics.median(cn) if cn else None,valid_phase_signal_counts={str(k):v for k,v in raw_signal.items()},locktime_decreases_by_signal={str(k):v for k,v in resets.items()},
            restore_matches=next((e['matches'] for e in events if e['event']=='restore_check'),None),steps=steps,
            input_sha256={str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [*inputs,config,*(alternative_inputs or [])]},
            limitation='No surveyed antenna truth; dispersion and receiver estimates are not absolute accuracy. Separate sequential intervals, unequal durations, static assumption not independently verified.')
static_forward={r['time']:r for r in solutions['static_forward']}
static_agreement=[]
for b in solutions['static_backward']:
    a=static_forward.get(b['time'])
    if a and a['q']==b['q']==1:
        e,n=en([a,b]);static_agreement.append(dict(time=b['time'],horizontal_difference_m=float(math.hypot(e[0]-e[1],n[0]-n[1])),height_difference_m=abs(a['height']-b['height'])))
result['static_forward_backward_agreement']=static_agreement
original_inputs=[OUT/'rover.ubx',R/'02_RTK/concurrent_base.rtcm3',alt/'base.rtcm3',l5/'base.rtcm3']
result['original_data_sha256']={str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in original_inputs if p.exists()}
(R/'comparison.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
fig,ax=plt.subplots(figsize=(8,6))
for name,rows in groups.items():
    if name=='PPK (same GNSS epochs, all Q)':continue
    if rows:
        e,n=en(rows);ax.scatter(e,n,s=8,alpha=.6,label=f'{name} (n={len(rows)})')
ax.set(xlabel='共通原点から東 (m)',ylabel='共通原点から北 (m)',title='単独・RTK・PPKの実測位置（真値に対する誤差ではない）');ax.axis('equal');ax.grid(alpha=.3);ax.legend();fig.tight_layout();fig.savefig(R/'comparison.png',dpi=160);plt.close(fig)
fig,axes=plt.subplots(2,1,figsize=(11,6))
axes[0].plot([r['elapsed_s'] for r in pvt],[r['data']['carrSoln'] if r['data'].get('gnssFixOk') else -1 for r in pvt]);axes[0].set(xlabel='記録開始から秒',ylabel='受信機の解状態',yticks=[-1,0,1,2],yticklabels=['無効','単独/DGNSS','FLOAT','FIX'])
time_origin=min((datetime.strptime(r['time'],'%Y/%m/%d %H:%M:%S.%f') for rows in solutions.values() for r in rows),default=None)
for name,rows in solutions.items():
    axes[1].plot([(datetime.strptime(r['time'],'%Y/%m/%d %H:%M:%S.%f')-time_origin).total_seconds() for r in rows],[r['q'] for r in rows],label=name,alpha=.7)
axes[1].set(xlabel='最初のPPK解から経過秒（GPSTで共通軸）',ylabel='RTKLIB Q',yticks=[1,2,4,5],yticklabels=['FIX','FLOAT','DGPS','Single']);axes[1].legend(fontsize=8)
for ax in axes:ax.grid(alpha=.3)
fig.tight_layout();fig.savefig(R/'fix_states.png',dpi=160);plt.close(fig)
table=['| 方法 | 有効点数 | 水平RMS m | 水平95%半径 m | 受信機hAcc中央値 m |','|---|---:|---:|---:|---:|']
fmt=lambda v:'—' if v is None else f'{v:.3f}'
for name,s in summary.items():table.append(f"| {name} | {s['epochs']} | {fmt(s.get('horizontal_rms_about_median_m'))} | {fmt(s.get('horizontal_p95_about_median_m'))} | {fmt(s.get('median_receiver_hacc_m'))} |")
lines=['# 窓際GNSS：無料RTK・PPKと単独測位の比較','',f"観測開始JST: {start_jst}。アンテナはユーザー確認で屋内窓際。受信機NEO-F9P / COM7。",'',
       '## 無料の近隣基準局','', 'ソーステーブルを今回再取得。概略位置から約5.71 km（ntrip1.bizstation.jp/3C722D56）、6.88 km（geortk.jp/geosense_f9p_rtcm）、7.52 km（geortk.jp/btf_nishiyamacho3）。座標が丸められているため概算距離。', '',
       f"[GEORTK公式](https://geortk.jp/)で基準局データ利用無料を確認。今回の実機採用設定：{connected['host']}:2101 / {connected['mountpoint']}、認証なし。全局への接続は公開ソーステーブルの認証Nを確認し、認証・支払いなしで取得できた。今回の生RTCM・OBSを保存。", '',
       '## 条件と結果','', f"GPS L5が無効だったためRAM上で有効化。同じ設定・1 Hzで補正なし{phase_durations.get('standalone',0)}秒、連続RTK{phase_durations.get('rtk_connected',0)}秒。初回取得・信号捕捉の過渡状態を含み、測定順による影響もある。補正なし分類はgnssFixOk=1、carrSoln=0、diffSoln=0。RTKはgnssFixOk=1とcarrSoln=1/2で分類。", '',
       f"RTK: 有効{len(rtk)}点、FIX {len(fixed)}点。最初のFIXまで: {result['time_to_first_rtk_fix_s']}秒。RTCM通知{len(rtcm)}、CRC失敗{result['rtcm']['crc_failed']}、利用通知{result['rtcm']['used']}。設定復元一致: {result['restore_matches']}。", '',
       *table,'', '**RMSと95%半径は各方法の中央値周りのばらつき。絶対位置誤差ではない。既知のアンテナ座標がないため、センチメートルの絶対精度達成や何倍の精度向上とは断定できない。hAccは受信機の推定値でありPPKには同等の値を割り当てない。**', '',
       'Standaloneは受信機が補正なしで出した位置。GNSS single (same PPK epochs)は同じRAWをRTKLIBの単独コード測位で再計算し、PPK出力と共通の時刻だけを抽出した比較。受信機とは測位アルゴリズムが異なる。PPKのFLOAT/FIX各集団は全共通時刻の部分集合なので、状態別の数値はさらに時刻選択の影響を受ける。', '',
       '## PPKの検証','', 'RTKLIB EX 2.5.1。RAWX/SFRBXと同時収録RTCMをRINEX変換。放送暦は移動局で取得したNAVを使用。基準局NAVが生成された場合のみ併用。L1/L2/L5指定（L2のない移動局にL2を生成しない）、仰角10度、AR ratio 3、基準局との最大時刻差1秒。kinematicのforward/backward/combinedと静止仮定のstatic combinedを比較。ratioを下げてFIXを強制していない。基準局座標はRTCM由来RINEXヘッダー。位相中心・座標系・測量成果は独立照合していない。', '',
       '| 解析 | 解数 | Q別件数 | 最長連続FIX点数 |','|---|---:|---|---:|']
for name,s in ppk.items():lines.append(f"| {name} | {s['epochs']} | {s['quality_counts']} | {s['longest_fix_run_epochs']} |")
lines+=['',f'kinematicのForward/backwardでともにFIXになった共通時刻は{len(agreed)}点、staticでは{len(static_agreement)}点。各時刻の位置一致をcomparison.jsonに保存。Q=1だけでは誤FIXを排除できない。静止解析のばらつき縮小は静止仮定の効果を含むため単独測位の精度改善とは比較しない。','',
        'alternativeは約5.71 kmの局（ntrip1.bizstation.jp/3C722D56）の同時収録データによるPPK。主局の観測途中から収録したため重なり時間は短い。基線長だけで優劣を判定しない。','',
        'l5は約40.94 kmの局（ntrip1.bizstation.jp/3C66E6DA）。今回GPS L5、Galileo E5a、QZSS L5、BeiDou B2aを配信することを実データで確認。32.10 kmの局も確認したがGalileo E5a/GPS L5を含まず、採用しなかった。距離と共通帯域を両方評価。l5の同時収録はさらに短い区間。','',
        f"C/N0のエポック中央値の中央値: {result['median_cn0_dbhz']} dB-Hz。RAWX locktime減少（追尾の途切れ等の指標、サイクルスリップの独立確定ではない）は合計{sum(resets.values())}回。信号ごとの詳細はcomparison.json。GPS L5を設定で有効にしても、その帯域で有効な搬送波が実際に得られるとは限らない。屋内遮蔽・反射の影響が疑われるが原因を単独特定する試験ではない。",'',
        '## 保存と再現','', 'comparison.jsonに集計・解析コマンド・入力SHA256、01_Basicに受信ログと設定復元、02_RTKに無料局一覧と同時補正、03_PPKにUBX/RINEX/各方向のPOS・CSVを保存。', '',
        f'再集計: `python tools/process_ppk.py {sys.argv[1]}` → `python tools/compare_fix_trial.py {sys.argv[1]}`。再観測時は新しいsession名を指定。', '',
        '![位置比較](comparison.png)','![状態比較](fix_states.png)']
if not alternative_inputs:lines=[l for l in lines if not l.startswith('alternativeは')]
if not (l5/'capture.json').exists():lines=[l for l in lines if not l.startswith('l5は')]
lines=[l.replace('None秒。','未達。') for l in lines]
(R/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
sys.path.insert(0,str(ROOT/'.deps'))
import markdown,base64
body=markdown.markdown('\n'.join(lines),extensions=['tables','fenced_code'])
for filename in ['comparison.png','fix_states.png']:
    body=body.replace(f'src="{filename}"','src="data:image/png;base64,'+base64.b64encode((R/filename).read_bytes()).decode()+'"')
(R/'REPORT.html').write_text('<!doctype html><html lang="ja"><meta charset="utf-8"><title>GNSS 実測比較</title><style>body{max-width:1100px;margin:40px auto;padding:0 20px;font:16px/1.8 "Yu Gothic",sans-serif;color:#20333d}table{border-collapse:collapse;width:100%;font-size:14px}th,td{border:1px solid #ccd6db;padding:10px;text-align:left}th{background:#eff5f7}img{max-width:100%}code{overflow-wrap:anywhere}a{color:#076575}</style>'+body+'</html>',encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in ['steps','input_sha256','forward_backward_agreement','static_forward_backward_agreement']},indent=2,ensure_ascii=False))
