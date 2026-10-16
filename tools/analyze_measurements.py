"""Analyze actual receiver JSONL and emit phase-aware plots and metrics."""
import sys,json,csv,collections,math,statistics
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
R=ROOT/'reports'/(sys.argv[1] if len(sys.argv)>1 else '')
plt.rcParams['font.family']='Yu Gothic'
rows=[]
for line in (R/'01_Basic/receiver_messages.jsonl').read_text().splitlines():
    try:rows.append(json.loads(line))
    except json.JSONDecodeError:pass
def messages(ident):return [r for r in rows if r['identity']==ident]
p=messages('NAV-PVT');raw=messages('RXM-RAWX');rtcm=messages('RXM-RTCM');sats=messages('NAV-SAT');utc=messages('NAV-TIMEUTC');tp=messages('TIM-TP')
def savecsv(path,data):
    if not data:return
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in data for k in r)));w.writeheader();w.writerows(data)
savecsv(R/'01_Basic/pvt.csv',[{'elapsed_s':r['elapsed_s'],'phase':r['phase'],**r['data']} for r in p])
metrics={'message_counts':dict(collections.Counter(r['identity'] for r in rows)),'rates':{},'phases':{},'utc_valid_epochs':sum(r['data'].get('validUTC')==1 for r in utc),'timepulse_messages':len(tp)}
fig,axs=plt.subplots(3,1,figsize=(11,9),sharex=True)
for phase in dict.fromkeys(r['phase'] for r in p):
    ps=[r for r in p if r['phase']==phase]; ts=[r['elapsed_s'] for r in ps]
    axs[0].plot(ts,[r['data']['numSV'] for r in ps],label=phase)
    axs[1].plot(ts,[r['data']['carrSoln'] if r['data'].get('gnssFixOk') else -1 for r in ps])
    axs[2].plot(ts,[r['data']['hAcc']/1000 for r in ps])
    diffs=[(b['data']['iTOW']-a['data']['iTOW'])%604800000 for a,b in zip(ps,ps[1:])]
    if phase.startswith('rate_') and diffs:
        hz=int(phase.split('_')[1][:-2]); step=1000/hz
        expected=sum(diffs)/step+1
        metrics['rates'][phase]={'epochs':len(ps),'median_interval_ms':statistics.median(diffs),'effective_hz':1000*(len(ps)-1)/sum(diffs),'gaps':sum(d>step*1.5 for d in diffs),'estimated_missing_epochs':round(expected-len(ps)),'interval_counts':dict(collections.Counter(diffs))}
    rs=[r for r in raw if r['phase']==phase]; rd=[b['data']['rcvTow']-a['data']['rcvTow'] for a,b in zip(rs,rs[1:])]
    metrics['phases'][phase]={'pvt_epochs':len(ps),'valid_position_epochs':sum(bool(r['data'].get('gnssFixOk')) for r in ps),'float_epochs':sum(r['data']['carrSoln']==1 and r['data'].get('gnssFixOk') for r in ps),'fix_epochs':sum(r['data']['carrSoln']==2 and r['data'].get('gnssFixOk') for r in ps),'rawx_epochs':len(rs),'rawx_max_gap_s':max(rd) if rd else None,'sfrbx_messages':sum(r['phase']==phase for r in messages('RXM-SFRBX'))}
axs[0].set(ylabel='測位に使用した衛星数',title='受信機の実測結果');axs[0].legend(ncol=3,fontsize=8)
axs[1].set(ylabel='RTK状態',yticks=[-1,0,1,2],yticklabels=['無効','単独/DGNSS','FLOAT','FIX'])
axs[2].set(ylabel='受信機の水平精度推定値 (m)',xlabel='記録開始からの秒数');axs[2].set_yscale('log')
for ax in axs:ax.grid(alpha=.3)
fig.tight_layout();fig.savefig(R/'01_Basic/receiver_overview.png',dpi=160);plt.close(fig)
fig,ax=plt.subplots(figsize=(10,4))
for phase in ['rate_1hz','rate_5hz','rate_10hz']:
    ps=[r for r in p if r['phase']==phase]
    if len(ps)>1:ax.plot([r['elapsed_s'] for r in ps[1:]],[(b['data']['iTOW']-a['data']['iTOW'])%604800000 for a,b in zip(ps,ps[1:])],'.',label=phase)
ax.set(xlabel='経過秒',ylabel='NAV-PVT iTOW差 (ms)',title='更新周期の実測（PC受信時刻ではなくGNSSエポック差）');ax.legend();ax.grid(alpha=.3);fig.tight_layout();fig.savefig(R/'01_Basic/update_intervals.png',dpi=160);plt.close(fig)
cno=[]
for r in sats:
    d=r['data'];v=[d.get(f'cno_{i:02}',0) for i in range(1,d['numSvs']+1)];v=[x for x in v if x>0]
    if v:cno.append({'elapsed_s':r['elapsed_s'],'tracked_satellites':len(v),'median_cn0_dbhz':statistics.median(v),'max_cn0_dbhz':max(v)})
savecsv(R/'01_Basic/cn0_summary.csv',cno)
fig,ax=plt.subplots(figsize=(10,4));ax.plot([r['elapsed_s'] for r in cno],[r['median_cn0_dbhz'] for r in cno],label='C/N0>0の衛星の中央値');ax.plot([r['elapsed_s'] for r in cno],[r['max_cn0_dbhz'] for r in cno],label='最大値');ax.set(xlabel='経過秒',ylabel='C/N0 (dB-Hz)',title='衛星信号強度');ax.legend();ax.grid(alpha=.3);fig.tight_layout();fig.savefig(R/'01_Basic/cn0.png',dpi=160);plt.close(fig)
if cno:metrics['cn0']={'median_of_epoch_medians_dbhz':statistics.median(r['median_cn0_dbhz'] for r in cno),'max_dbhz':max(r['max_cn0_dbhz'] for r in cno),'max_tracked_satellites':max(r['tracked_satellites'] for r in cno)}
metrics['rtcm']={'messages':len(rtcm),'crc_failed':sum(r['data']['crcFailed'] for r in rtcm),'used':sum(r['data']['msgUsed']==2 for r in rtcm),'types':dict(collections.Counter(r['data']['msgType'] for r in rtcm))}
fix=[r for r in p if r['data']['carrSoln']==2 and r['data'].get('gnssFixOk')]
floats=[r for r in p if r['data']['carrSoln']==1 and r['data'].get('gnssFixOk')]
events=json.loads((R/'01_Basic/test_events.json').read_text(encoding='utf-8')) if (R/'01_Basic/test_events.json').exists() else []
connected=[e for e in events if e['event']=='ntrip_connected']
metrics['first_float_elapsed_s']=floats[0]['elapsed_s'] if floats else None
metrics['first_fix_elapsed_s']=fix[0]['elapsed_s'] if fix else None
metrics['time_to_fix_from_connection_s']=fix[0]['elapsed_s']-connected[0]['elapsed_s'] if fix and connected else None
metrics['float_to_fix_s']=fix[0]['elapsed_s']-floats[0]['elapsed_s'] if fix and floats else None
metrics['fix_retention_after_first_fix']=None
metrics['recovery_s']=None
metrics['float_recovery_s']=None
metrics['outage_to_float_loss_s']=None
if fix:
    eligible=[r for r in p if r['elapsed_s']>=fix[0]['elapsed_s'] and r['phase']=='rtk_connected']
    if eligible:metrics['fix_retention_after_first_fix']=sum(r['data']['carrSoln']==2 and r['data'].get('gnssFixOk') for r in eligible)/len(eligible)
resumed=[e for e in connected if e['phase']=='correction_resumed']
if resumed:
    recovered=[r for r in fix if r['elapsed_s']>=resumed[0]['elapsed_s']]
    if recovered:metrics['recovery_s']=recovered[0]['elapsed_s']-resumed[0]['elapsed_s']
    rf=[r for r in floats if r['elapsed_s']>=resumed[0]['elapsed_s']]
    if rf:metrics['float_recovery_s']=rf[0]['elapsed_s']-resumed[0]['elapsed_s']
disconnected=[e for e in events if e['event']=='ntrip_disconnected' and e['phase']=='correction_off']
if disconnected:
    lost=[r for r in p if r['phase']=='correction_off' and r['elapsed_s']>=disconnected[0]['elapsed_s'] and r['data']['carrSoln']==0]
    if lost:metrics['outage_to_float_loss_s']=lost[0]['elapsed_s']-disconnected[0]['elapsed_s']
fig,ax=plt.subplots(figsize=(10,4));ax.plot([r['elapsed_s'] for r in p],[r['data']['carrSoln'] if r['data'].get('gnssFixOk') else -1 for r in p],drawstyle='steps-post')
for e in events:
    if e['event']=='phase_start' and 'correction' in e['phase']:ax.axvline(e['elapsed_s'],linestyle='--',label=e['phase'])
ax.set(xlabel='経過秒',ylabel='解状態',yticks=[-1,0,1,2],yticklabels=['無効','単独/DGNSS','FLOAT','FIX'],title='補正接続・断絶・再開時の測位状態');ax.grid(alpha=.3)
if any(e['event']=='phase_start' and 'correction' in e['phase'] for e in events):ax.legend()
fig.tight_layout();fig.savefig(R/'02_RTK/rtk_states.png',dpi=160);plt.close(fig)
fig,axs=plt.subplots(2,1,figsize=(11,6),sharex=True)
for phase in dict.fromkeys(r['phase'] for r in raw):
    rs=[r for r in raw if r['phase']==phase]
    axs[0].plot([r['elapsed_s'] for r in rs],[r['data']['numMeas'] for r in rs],label=phase)
    axs[1].plot([r['elapsed_s'] for r in rs],[sum(r['data'].get(f'cpValid_{i:02}',0) for i in range(1,r['data']['numMeas']+1)) for r in rs])
axs[0].set(ylabel='RAWX観測信号数',title='RTK試験中のRAW保存継続');axs[0].legend(ncol=3,fontsize=8);axs[1].set(xlabel='経過秒',ylabel='搬送波位相有効数')
for ax in axs:ax.grid(alpha=.3)
fig.tight_layout();fig.savefig(R/'03_PPK/raw_continuity.png',dpi=160);plt.close(fig)
(R/'metrics.json').write_text(json.dumps(metrics,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(metrics,ensure_ascii=False,indent=2))
