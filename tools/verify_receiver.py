"""Real receiver test; volatile settings only, restored in finally."""
import sys, time, json, threading, socket, csv, argparse
from pathlib import Path
from datetime import datetime, timezone
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.deps'))
import serial
from pyubx2 import UBXReader, UBXMessage, POLL
parser=argparse.ArgumentParser()
parser.add_argument('port',nargs='?',default='COM7')
parser.add_argument('--host',default='ntrip.aitoya.net')
parser.add_argument('--mount',default='MOSAIC-RTCM3')
parser.add_argument('--session',default='')
parser.add_argument('--rtk-only',action='store_true')
parser.add_argument('--rates-only',action='store_true')
parser.add_argument('--lean',action='store_true')
parser.add_argument('--baseline-seconds',type=float,default=0)
parser.add_argument('--rtk-seconds',type=float,default=180)
parser.add_argument('--outage-seconds',type=float,default=60)
parser.add_argument('--resumed-seconds',type=float,default=120)
parser.add_argument('--enable-gps-l5',action='store_true')
args=parser.parse_args()
R=ROOT/'reports'/args.session
for folder in ['01_Basic','02_RTK','03_PPK']:(R/folder).mkdir(parents=True,exist_ok=True)
RAW=R/'03_PPK'/'rover.ubx'
keys=['CFG_RATE_MEAS','CFG_RATE_NAV','CFG_USBINPROT_RTCM3X']+[f'CFG_MSGOUT_UBX_{m}_USB' for m in ['NAV_PVT','NAV_SAT','NAV_SIG','NAV_TIMEUTC','RXM_RAWX','RXM_SFRBX','RXM_RTCM','TIM_TP']]
if args.lean:keys+=['CFG_USBOUTPROT_NMEA','CFG_UART1OUTPROT_NMEA']
if args.enable_gps_l5:keys+=['CFG_SIGNAL_GPS_L5_ENA']
if args.session and (R/'01_Basic'/'receiver_messages.jsonl').exists():
    raise RuntimeError('Session already exists; choose a new session name')
tpkeys=['CFG_TP_TP1_ENA','CFG_TP_PULSE_DEF','CFG_TP_FREQ_TP1','CFG_TP_FREQ_LOCK_TP1','CFG_TP_PERIOD_TP1','CFG_TP_PERIOD_LOCK_TP1','CFG_TP_USE_LOCKED_TP1','CFG_TP_TIMEGRID_TP1']

def run():
    s=serial.Serial(args.port,115200,timeout=.2)
    reader=UBXReader(s,protfilter=3)
    start=time.monotonic(); phase='initial'; events=[]; original={}; pvt=[]; sats=[]; signals=[]; raws=[]; rtcm=[]; counts={}; stop=threading.Event(); inject=threading.Event()
    log=(R/'01_Basic'/'receiver_messages.jsonl').open('w',encoding='utf-8')
    rawfile=RAW.open('wb')
    def event(kind,**kw):
        row={'elapsed_s':time.monotonic()-start,'utc':datetime.now(timezone.utc).isoformat(),'phase':phase,'event':kind,**kw}; events.append(row); print(json.dumps(row,ensure_ascii=False),flush=True)
        (R/'01_Basic'/'test_events.json').write_text(json.dumps(events,indent=2,ensure_ascii=False),encoding='utf-8')
    def read():
        try: raw,m=reader.read()
        except Exception as e: event('parse_error',error=str(e)); return None
        if m is None:return None
        if raw.startswith(b'\xb5\x62'):rawfile.write(raw)
        ident=m.identity; counts[ident]=counts.get(ident,0)+1
        d={k:v for k,v in vars(m).items() if not k.startswith('_')}
        common={'elapsed_s':time.monotonic()-start,'phase':phase}
        log.write(json.dumps({**common,'identity':ident,'data':d},default=str)+'\n')
        if ident=='NAV-PVT':pvt.append({**common,**{k:getattr(m,k,None) for k in ['iTOW','fixType','gnssFixOk','carrSoln','numSV','lat','lon','hAcc','vAcc','validDate','validTime','fullyResolved','year','month','day','hour','min','second']}})
        if ident=='NAV-SAT':
            for i in range(1,m.numSvs+1):sats.append({**common,'iTOW':m.iTOW,**{k:getattr(m,f'{k}_{i:02}',None) for k in ['gnssId','svId','cno','elev','azim','svUsed']}})
        if ident=='NAV-SIG':
            for i in range(1,m.numSigs+1):signals.append({**common,'iTOW':m.iTOW,**{k:getattr(m,f'{k}_{i:02}',None) for k in ['gnssId','svId','sigId','cno','qualityInd','prUsed','crUsed']}})
        if ident=='RXM-RAWX':raws.append({**common,**{k:getattr(m,k,None) for k in ['rcvTow','week','numMeas','leapS','leapSec']},'valid_phase':sum(bool(getattr(m,f'cpValid_{i:02}',0)) for i in range(1,m.numMeas+1))})
        if ident=='RXM-RTCM':rtcm.append({**common,**d})
        return m
    def collect(duration):
        until=time.monotonic()+duration
        report_at=time.monotonic()+30
        while time.monotonic()<until:
            read()
            if time.monotonic()>=report_at:
                rawfile.flush();log.flush()
                event('progress',remaining_s=round(until-time.monotonic()),last_pvt=pvt[-1] if pvt else None,
                      fix_epochs=sum(x['carrSoln']==2 and x['gnssFixOk'] for x in pvt),raw_epochs=len(raws))
                report_at=time.monotonic()+30
        rawfile.flush(); log.flush()
    def poll(ks):
        s.write(UBXMessage.config_poll(0,0,ks).serialize())
        until=time.monotonic()+4
        while time.monotonic()<until:
            m=read()
            if m and m.identity=='CFG-VALGET':return {k:getattr(m,k) for k in ks if hasattr(m,k)}
        return {}
    def setconfig(pairs):
        s.write(UBXMessage.config_set(1,0,pairs).serialize())
        until=time.monotonic()+3
        while time.monotonic()<until:
            m=read()
            if m and m.identity in ['ACK-ACK','ACK-NAK'] and m.clsID==6 and m.msgID==0x8a:
                event('config_ack',success=m.identity=='ACK-ACK',settings=pairs)
                return m.identity=='ACK-ACK'
        event('config_ack_timeout',settings=pairs); return False
    def ntrip():
        try:
            while not stop.is_set():
              if not inject.wait(timeout=.2):continue
              with socket.create_connection((args.host,2101),timeout=8) as sock, (R/'02_RTK'/'concurrent_base.rtcm3').open('ab') as base:
                sock.sendall(f'GET /{args.mount} HTTP/1.0\r\nUser-Agent: NTRIP GNSSVerification/1.0\r\n\r\n'.encode())
                header=b''
                while not header.endswith(b'\r\n'):
                    b=sock.recv(1)
                    if not b:raise RuntimeError('Disconnected during response')
                    header+=b
                if not header.startswith(b'ICY 200'):raise RuntimeError(repr(header))
                sock.settimeout(1); event('ntrip_connected',response=header.decode().strip(),host=args.host,mountpoint=args.mount)
                injection_path=R/'02_RTK'/'injection.csv'; empty=not injection_path.exists()
                with injection_path.open('a',newline='') as f:
                    w=csv.writer(f)
                    if empty:w.writerow(['elapsed_s','phase','received_bytes','injected_bytes'])
                    while not stop.is_set() and inject.is_set():
                        try:b=sock.recv(32768)
                        except socket.timeout:continue
                        if not b:break
                        base.write(b); sent=s.write(b) if inject.is_set() else 0
                        w.writerow([time.monotonic()-start,phase,len(b),sent]); f.flush()
                event('ntrip_disconnected')
        except Exception as e:event('ntrip_error',error=str(e))
    worker=None
    try:
        s.write(UBXMessage('MON','MON-VER',POLL).serialize()); collect(2)
        original=poll(keys)
        (R/'01_Basic'/'original_config.json').write_text(json.dumps(original,indent=2))
        tp=poll(tpkeys); (R/'01_Basic'/'timepulse_config.json').write_text(json.dumps(tp,indent=2))
        if len(original)!=len(keys):raise RuntimeError('Cannot snapshot all settings; no modifications made')
        if not setconfig([(k,1) for k in keys if 'MSGOUT' in k]+[('CFG_USBINPROT_RTCM3X',1),('CFG_RATE_NAV',1)]+([('CFG_USBOUTPROT_NMEA',0),('CFG_UART1OUTPROT_NMEA',0)] if args.lean else [])+([('CFG_SIGNAL_GPS_L5_ENA',1)] if args.enable_gps_l5 else [])):
            raise RuntimeError('Receiver rejected measurement configuration')
        event('measurement_readback',values=poll(keys))
        if args.baseline_seconds:
            phase='standalone';setconfig([('CFG_RATE_MEAS',1000)])
            event('phase_start',duration_s=args.baseline_seconds);collect(args.baseline_seconds)
        for hz,duration in ([] if args.rtk_only else [(1,40),(5,25),(10,25)]):
            phase=f'rate_{hz}hz'; event('phase_start',duration_s=duration)
            setconfig([('CFG_RATE_MEAS',1000//hz)])
            if args.lean:setconfig([(f'CFG_MSGOUT_UBX_{m}_USB',hz) for m in ['NAV_SAT','NAV_SIG','NAV_TIMEUTC']])
            readback=poll(['CFG_RATE_MEAS','CFG_RATE_NAV']);event('rate_readback',values=readback)
            collect(duration)
        if args.rates_only:return
        phase='rtk_connected';setconfig([('CFG_RATE_MEAS',1000)]);inject.set()
        worker=threading.Thread(target=ntrip,daemon=True);worker.start();event('phase_start',duration_s=args.rtk_seconds);collect(args.rtk_seconds)
        if args.outage_seconds:
            phase='correction_off';inject.clear();event('phase_start',duration_s=args.outage_seconds);collect(args.outage_seconds)
        if args.resumed_seconds:
            phase='correction_resumed';inject.set();event('phase_start',duration_s=args.resumed_seconds);collect(args.resumed_seconds)
    except Exception as e:event('test_error',error=str(e))
    finally:
        stop.set()
        if worker:worker.join(timeout=10)
        phase='restore'
        if original:
            setconfig(list(original.items())); check=poll(keys);event('restore_check',matches=check==original,values=check)
        rawfile.close();log.close();s.close()
        for name,rows in [('01_Basic/pvt.csv',pvt),('01_Basic/satellites.csv',sats),('01_Basic/signals.csv',signals),('03_PPK/raw_epochs.csv',raws),('02_RTK/receiver_rtcm.csv',rtcm)]:
            if rows:
                with (R/name).open('w',newline='',encoding='utf-8') as f:
                    fields=list(dict.fromkeys(k for row in rows for k in row));w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
        (R/'01_Basic'/'test_events.json').write_text(json.dumps(events,indent=2,ensure_ascii=False),encoding='utf-8')
        (R/'01_Basic'/'message_counts.json').write_text(json.dumps(counts,indent=2))
        print(json.dumps({'counts':counts,'raw_epochs':len(raws),'pvt_epochs':len(pvt)},indent=2),flush=True)
if __name__=='__main__':run()
