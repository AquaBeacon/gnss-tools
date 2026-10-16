"""Write a concise cross-session report from completed measured results."""
import json,sys,base64
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.deps'))
import markdown
R=ROOT/'reports'
names=['fix_trial_20261009_evening','fix_trial_20261009_l5']
data=[json.loads((R/n/'comparison.json').read_text(encoding='utf-8')) for n in names]
lines=['# 無料局でのRTK・PPK FIX試験と通常GNSSの比較','',
       '2026-10-09 JST、NEO-F9P / COM7、アンテナは屋内窓際（ユーザー確認）。GPS L5をRAMで有効にして実測し、終了時に元の設定へ復元。観測・補正・RINEX・解析コマンドはすべて保存済み。','',
       '| 実機RTKの補正局 | 概算距離 | 接続観測 | RTK FIX点数 | PPK移動解析のFIX点数 | 最長連続PPK FIX点数 |','|---|---:|---:|---:|---:|---:|']
for d,base,km,seconds in zip(data,['geortk.jp:2101/btf_nishiyamacho3','ntrip1.bizstation.jp:2101/3C66E6DA'],[7.52,40.94],[900,600]):
    p=d['ppk']['kinematic_combined']
    lines.append(f"| {base} | {km:.2f} km | {seconds}秒 | {d['rtk_fixed_epochs']} / {d['rtk_epochs']} | {p['quality_counts'].get('1',0)} / {p['epochs']} | {p['longest_fix_run_epochs']} |")
lines+=['','PPKはRTKLIB Q=1をFIX判定として数えた。1 Hzの連続点数であり、2点連続は約1秒の時間幅。Q=1だけで正しいセンチメートル解とは保証しない。','',
        '静止仮定のPPKも実施。最初の観測中に同時収録した40.94 km局の静止combined解析では55点のFIX判定、最長32点連続があった。これは約31秒の区間だが、静止仮定による拘束を含み、正しさ・長時間安定性は未確認。移動解析と混ぜてFIX維持率を算出しない。','',
        '| セッション | 移動PPKで前向き・後向き双方がFIXの共通点数 | 静止PPKで双方がFIXの共通点数 | 設定復元一致 |','|---|---:|---:|---|']
for n,d in zip(names,data):lines.append(f"| {n} | {d['forward_backward_fixed_common_epochs']} | {len(d['static_forward_backward_agreement'])} | {d['restore_matches']} |")
total=sum(d['rtk_fixed_epochs'] for d in data)
lines+=['',f'RTK FIXは合計{total}点。PPKの一時的なFIX候補と、継続・再現性を確認したFIX達成は区別する。既知のアンテナ座標がないため、絶対精度の検証は未実施。','',
        '## 通常GNSSとの比較','', '最初のセッションの同一901時刻・同一RAWで、補正なしのRTKLIB単独コード測位とPPKを比較した。PPKはFLOAT・FIX・DGPSをすべて含む。基準局との観測時刻差は最大1秒。','',
        '| 計算方式 | 点数 | 水平RMS（各方式の中央値周り） | 水平95%半径 |','|---|---:|---:|---:|']
for key,label in [('GNSS single (same PPK epochs)','通常GNSS：単独コード測位'),('PPK (same GNSS epochs, all Q)','PPK：全解状態')]:
    s=data[0]['comparison'][key];lines.append(f"| {label} | {s['epochs']} | {s['horizontal_rms_about_median_m']:.2f} m | {s['horizontal_p95_about_median_m']:.2f} m |")
lines+=['','L5対応局へ切り替えた追加観測でも、同一593時刻のRAW同士で比較した。PPKは592点がFLOAT、1点がDGPS。','',
        '| L5対応局での追加観測 | 点数 | 水平RMS（各方式の中央値周り） | 水平95%半径 |','|---|---:|---:|---:|']
for key,label in [('GNSS single (same PPK epochs)','通常GNSS：単独コード測位'),('PPK (same GNSS epochs, all Q)','PPK：全解状態')]:
    s=data[1]['comparison'][key];lines.append(f"| {label} | {s['epochs']} | {s['horizontal_rms_about_median_m']:.2f} m | {s['horizontal_p95_about_median_m']:.2f} m |")
baseline=data[0]['comparison']['Standalone'];rtk=data[0]['comparison']['RTK FLOAT']
lines+=['',f"受信機が出したhAccの中央値は、補正なしの2分間で{baseline['median_receiver_hacc_m']:.2f} m、近距離RTK-FLOATで{rtk['median_receiver_hacc_m']:.2f} m。これは受信機の精度推定値であり、実際の位置誤差ではない。二つの実機区間は時刻・長さが異なるので、ばらつきから公平な精度改善倍率は算出しない。",'',
        '**上のRMS・95%半径は位置のばらつきであり、真値に対する誤差ではない。PPKでばらつきは減ったが、センチメートル精度達成とは言えない。**','',
        '## 無料局と共通信号','',
        '[GEORTK公式](https://geortk.jp/)は基準局データ利用無料と案内。近隣では約5.71 km（3C722D56）、6.88 km（geosense_f9p_rtcm）、7.52 km（btf_nishiyamacho3）を新しいソーステーブルで認証Nの候補として確認。5.71 km局も同時収録してPPKを比較。','',
        'NEO-F9PはL1/L5対応。最寄り局やL1/L2局だけではL5が揃わない。約40.94 kmの3C66E6DAではGPS L5、Galileo E5a、QZSS L5、BeiDou B2aを実データで確認し、実機RTKとPPKを追加。すべて今回の取得は認証・支払いなし。距離はソーステーブルの丸め座標からの概算。','',
        '## 受信環境と次の実機条件','',
        '終了後の読み取りでCFG_NAVHPG_DGNSSMODE=3（RTK_FIXED）を確認。FLOAT専用モードによるFIX禁止ではない。RTCMの1005と各MSMの基準局IDも双方の実機セッションで0に一致（rtcm_station_id_check.json）。GPS L5は観測中に有効化し、終了時は初期値0に復元。Galileo E5a、BeiDou B2a、QZSS L5は1。','',
        f"補正通知のCRC失敗は両セッション合計{sum(d['rtcm']['crc_failed'] for d in data)}件。最初の観測のC/N0中央値は{data[0]['median_cn0_dbhz']:.1f} dB-Hz、RAWXのlocktime減少は{sum(data[0]['locktime_decreases_by_signal'].values())}回。追尾の途切れ等を示すが、サイクルスリップの独立検証ではない。補正通信は成立しており、屋内の遮蔽・反射が制約になっている可能性がある。原因を単独特定した試験ではない。",'',
        '次はL1/L5対応アンテナを、空が広く見える屋外に固定する条件で再観測する。屋内で待ち時間を延ばすだけではFIXを保証できない。アンテナ型番・窓材・グランドプレーンは未確認。絶対精度を比較する場合は既知座標も必要。','',
        '再観測（未使用session名に変更）：','',
        '```powershell','python tools/verify_receiver.py COM7 --rtk-only --lean --session outdoor_new --host ntrip1.bizstation.jp --mount 3C66E6DA --rtk-seconds 1200 --outage-seconds 0 --resumed-seconds 0 --enable-gps-l5','python tools/process_ppk.py outdoor_new','python tools/compare_fix_trial.py outdoor_new','```','',
        '## 詳細データ','']
for n in names:lines.append(f'- [{n} 詳細レポート]({n}/REPORT.html)、[集計JSON]({n}/comparison.json)')
lines+=['','![位置の比較](fix_trial_20261009_evening/comparison.png)']
source='\n'.join(lines)+'\n'
(R/'FIX_COMPARISON.md').write_text(source,encoding='utf-8')
body=markdown.markdown(source,extensions=['tables','fenced_code'])
img=R/'fix_trial_20261009_evening/comparison.png'
body=body.replace('src="fix_trial_20261009_evening/comparison.png"','src="data:image/png;base64,'+base64.b64encode(img.read_bytes()).decode()+'"')
(R/'FIX_COMPARISON.html').write_text('<!doctype html><html lang="ja"><meta charset="utf-8"><title>RTK・PPK実測比較</title><style>body{max-width:1100px;margin:40px auto;padding:0 20px;font:16px/1.8 "Yu Gothic",sans-serif;color:#20333d}table{border-collapse:collapse;width:100%;font-size:14px}th,td{border:1px solid #ccd6db;padding:10px;text-align:left}th{background:#eff5f7}img{max-width:100%}code{overflow-wrap:anywhere}pre{white-space:pre-wrap}a{color:#076575}</style>'+body+'</html>',encoding='utf-8')
print('Saved FIX_COMPARISON.md and FIX_COMPARISON.html')
