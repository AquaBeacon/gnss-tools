"""Capture public NTRIP with CRC validation; no receiver connection required."""
import sys, socket, time, json, csv, io
from pathlib import Path
from datetime import datetime, timezone
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '.deps'))
from pyrtcm import RTCMReader
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'reports' / '02_RTK'
OUT.mkdir(parents=True, exist_ok=True)
HOST, PORT, MOUNT = 'ntrip.aitoya.net', 2101, 'MOSAIC-RTCM3'

def connect(path):
    s = socket.create_connection((HOST, PORT), timeout=8)
    s.settimeout(3)
    s.sendall((f'GET /{path} HTTP/1.0\r\nUser-Agent: NTRIP GNSSVerification/1.0\r\nAccept: */*\r\nConnection: close\r\n\r\n').encode())
    return s

def run():
    result = {'utc_started': datetime.now(timezone.utc).isoformat(), 'host': HOST, 'port': PORT, 'mountpoint': MOUNT, 'authentication': 'none', 'receiver_connected': False}
    try:
        with connect('') as s:
            data = bytearray()
            until = time.monotonic() + 8
            while time.monotonic() < until:
                try: b = s.recv(65536)
                except socket.timeout: break
                if not b: break
                data.extend(b)
                if b'ENDSOURCETABLE' in data: break
            (OUT / 'sourcetable.txt').write_bytes(data)
        rows, chunks, payload = [], [], bytearray()
        with connect(MOUNT) as s:
            header = bytearray()
            while b'\r\n' not in header:
                b = s.recv(1)
                if not b: raise RuntimeError('Disconnected before response')
                header.extend(b)
            status = header.decode(errors='replace').strip()
            result['status_line'] = status
            if '200' not in status: raise RuntimeError(status)
            # ICY v1 ends at status CRLF; HTTP responses include a full header.
            if status.startswith('HTTP/'):
                while b'\r\n\r\n' not in header:
                    b = s.recv(1)
                    if not b: raise RuntimeError('Incomplete HTTP headers')
                    header.extend(b)
            (OUT / 'response_header.txt').write_bytes(header)
            start = time.monotonic()
            while time.monotonic() - start < 35:
                try: b = s.recv(65536)
                except socket.timeout: continue
                if not b: break
                payload.extend(b)
                chunks.append({'elapsed_s': time.monotonic()-start, 'bytes': len(b), 'cumulative_bytes': len(payload)})
            result['duration_s'] = time.monotonic()-start
        (OUT / 'base.rtcm3').write_bytes(payload)
        pos, invalid = 0, 0
        while pos + 6 <= len(payload):
            if payload[pos] != 0xd3: pos += 1; continue
            size = ((payload[pos+1] & 3) << 8) | payload[pos+2]
            frame = bytes(payload[pos:pos+size+6])
            if len(frame) < size+6: break
            try:
                msg = RTCMReader.parse(frame, validate=1)
                row = {'offset': pos, 'message_type': msg.identity, 'bytes': len(frame)}
                if hasattr(msg, 'NCell'):
                    result.setdefault('msm_signals', {}).setdefault(msg.identity, set()).update(str(getattr(msg, f'CELLSIG_{i:02}')) for i in range(1, msg.NCell+1))
                rows.append(row)
            except Exception:
                invalid += 1
            pos += size+6
        result['bytes'] = len(payload)
        result['valid_frames'] = len(rows)
        result['invalid_frames'] = invalid
        result['message_counts'] = {t: sum(r['message_type']==t for r in rows) for t in sorted({r['message_type'] for r in rows})}
        result['msm_signals'] = {k: sorted(v) for k,v in result.get('msm_signals', {}).items()}
        for name, data in [('network_chunks.csv', chunks), ('rtcm_frames.csv', rows)]:
            if data:
                with (OUT / name).open('w', newline='') as f:
                    w = csv.DictWriter(f, fieldnames=data[0]); w.writeheader(); w.writerows(data)
        fig, ax = plt.subplots(1, 2, figsize=(11,4))
        ax[0].plot([r['elapsed_s'] for r in chunks], [r['cumulative_bytes'] for r in chunks])
        ax[0].set(xlabel='Elapsed time (s)', ylabel='Received bytes', title='NTRIP network capture (PC only)')
        counts = result['message_counts']
        ax[1].bar(list(counts), list(counts.values()))
        ax[1].set(xlabel='RTCM type (CRC valid)', ylabel='Frames', title='Received RTCM message types')
        ax[1].tick_params(axis='x', rotation=60)
        fig.tight_layout(); fig.savefig(OUT / 'ntrip_capture.png', dpi=160); plt.close(fig)
    except Exception as e:
        result['error'] = f'{type(e).__name__}: {e}'
    (OUT / 'ntrip_result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == '__main__': run()
