"""Build final Japanese reports after all real tests and PPK complete."""
from pathlib import Path
import json,shutil
ROOT=Path(__file__).resolve().parents[1];R=ROOT/'reports'
def load(p):return json.loads((R/p).read_text(encoding='utf-8'))
def write(p,s):(R/p).write_text(s,encoding='utf-8')
a=load('metrics.json');b=load('rates_lean/metrics.json');n=load('nearby/metrics.json');ppk=load('nearby/03_PPK/ppk_summary.json')
events=load('nearby/01_Basic/test_events.json')
restores={s:next((e.get('matches') for e in load(Path(s)/'01_Basic/test_events.json') if e['event']=='restore_check'),None) for s in ['', 'rates_lean','nearby']}
for src,dst in [('nearby/01_Basic','01_Basic/nearby'),('nearby/02_RTK','02_RTK/nearby'),('nearby/03_PPK','03_PPK/nearby'),('rates_lean/01_Basic','01_Basic/rates_lean')]:
    shutil.copytree(R/src,R/dst,dirs_exist_ok=True)
for src,dst in [('rates_lean/01_Basic/update_intervals.png','01_Basic/update_intervals_lean.png'),('nearby/02_RTK/rtk_states.png','02_RTK/nearby_states.png'),('nearby/03_PPK/raw_continuity.png','03_PPK/nearby_raw_continuity.png'),('nearby/03_PPK/ppk_results.png','03_PPK/ppk_results.png')]:
    if (R/src).exists():shutil.copy2(R/src,R/dst)
def rates(m):
    return '\n'.join(f"| {k} | {v['epochs']} | {v['median_interval_ms']} | {v['effective_hz']:.4f} | {v['estimated_missing_epochs']} |" for k,v in m['rates'].items())
fix=n['first_fix_elapsed_s'];status='FIXを確認' if fix is not None else 'FLOATを確認、FIXは試験時間内に得られず'
phase_table='\n'.join(f"| {k} | {v['pvt_epochs']} | {v['float_epochs']} | {v['fix_epochs']} | {v['rawx_epochs']} | {v['rawx_max_gap_s']} | {v['sfrbx_messages']} |" for k,v in n['phases'].items())
basic=f'''# ① 基本動作・設定：実機検証結果

検証日：2026-10-09 JST。受信機：NEO-F9P、FW HPGL1L5 1.40、PROTVER 27.40。USB COM7、VID:PID=1546:01A9。
当初USB未検出だったが、ユーザーが別ケーブルに交換後、USB列挙・MON-VER応答・継続データ受信に成功。アンテナはユーザー申告で窓際へ設置。屋外開放環境での試験ではない。

| 確認項目 | 判定・根拠 |
|---|---|
| USB通信 | 確認済み。型番応答、設定ACK、連続UBX取得 |
| 衛星受信 | 3D測位確認。C/N0中央値の時間中央値 {a['cn0']['median_of_epoch_medians_dbhz']} dB-Hz、最大 {a['cn0']['max_dbhz']} dB-Hz。C/N0>0の衛星数は最大 {a['cn0']['max_tracked_satellites']}。使用衛星数はpvt.csvのnumSV参照 |
| 1/5/10 Hz設定 | 全設定でACK・読み戻し一致。実測周期と欠測は下表 |
| GNSS時刻 | NAV-TIMEUTCのvalidUTC=1を{a['utc_valid_epochs']}エポック確認。NAV-PVTのvalidDate/validTime/fullyResolvedも保存 |
| PPS設定・通知 | TP1有効、周期1,000,000 us、TIM-TPを{a['timepulse_messages']}件保存 |
| PPS端子の波形・精度 | 未検証。オシロスコープ/カウンタ等で端子パルスの測定が必要。TIM-TP通知のみで実際の電気出力を合格扱いしない |

## 更新周期：通常出力のままRAW等を追加
| 設定 | NAV-PVT数 | 中央値 ms | 実効 Hz | 推定欠測エポック |
|---|---:|---:|---:|---:|
{rates(a)}

5/10 Hzで出力バッファ不足を示すNMEA `txbuf alloc` を観測。10 Hz時のRAWX最大間隔は{a['phases']['rate_10hz']['rawx_max_gap_s']:.3f}秒。更新周期設定の成功と、全メッセージを欠けなく同時記録できることは別に評価する。

## 出力を減らした再試験
USB/UART1のNMEA出力を一時停止し、NAV-SAT/SIG/TIMEUTCを約1 Hzに抑えた。NAV-PVT/RAWXの出力設定は各測位エポックごと。
| 設定 | NAV-PVT数 | 中央値 ms | 実効 Hz | 推定欠測エポック |
|---|---:|---:|---:|---:|
{rates(b)}

推定欠測は同一試験区間内のiTOW差から算出。区間端の取りこぼしは評価範囲外。設定直後の移行も含むため定常性能の厳密な保証値ではない。

設定はRAMのみ変更し、終了時に元の値へ復元。読み戻し一致：{restores}。不揮発保存・受信機ファームウェア更新は行っていない。

## データ・グラフ
- receiver_messages.jsonl：解析済み全メッセージ、経過秒、試験区間。
- pvt.csv / satellites.csv / signals.csv / cn0_summary.csv。
- original_config.json / timepulse_config.json / test_events.json。
- receiver_overview.png / cn0.png / update_intervals.png / update_intervals_lean.png。
- 再試験の全データ：[rates_lean](rates_lean/)。
- windows_devices_before_reconnect.json と windows_devices.json：接続前後の列挙結果。

受信機のhAcc/vAccは内部推定値。既知点との誤差を実測したものではない。
'''
write('01_Basic/REPORT.md',basic)
rtk=f'''# ② RTK測位：{status}

検証日：2026-10-09 JST。窓際・静止条件。初期試験と近傍局試験を分けて保存した。

## 無料で採用した近傍局
ホスト `geortk.jp`、ポート `2101`、マウントポイント `btf_nishiyamacho3`、ユーザー名/パスワードなしで接続成功。[配信元公式](https://geortk.jp/) は基準局データの利用無料と案内している。
ソーステーブル座標と受信位置からの概算距離は約7.5 km。Galileoの1C/5Q（E1/E5a）を実データで確認。GPSは今回L1のみであり、全衛星系で二周波補正が揃う配信ではない。
設定場所：tools/continue_tests.py、tools/verify_receiver.pyの --host / --mount 引数。認証情報ファイルは不要。

## 実機結果
- RXM-RTCM：{n['rtcm']['messages']}件、CRC失敗 {n['rtcm']['crc_failed']}件、受信機が利用した通知 {n['rtcm']['used']}件。
- RTCM種別・件数：{n['rtcm']['types']}。
- 最初のFLOAT：試験開始から {n['first_float_elapsed_s']} 秒。
- 初回FIX：{n['first_fix_elapsed_s']}（nullは未達）。
- 接続からFIXまで：{n['time_to_fix_from_connection_s']} 秒。
- FLOATからFIXまで：{n['float_to_fix_s']} 秒。
- 初回FIX後のFIX維持率：{n['fix_retention_after_first_fix']}。
- 再接続から再FIXまで：{n['recovery_s']} 秒。
- 再接続からFLOATへ復帰：{n['float_recovery_s']} 秒（PC受信時刻に基づく概算）。
- ソケット切断からFLOAT喪失：{n['outage_to_float_loss_s']} 秒（PC受信時刻に基づく概算）。

FIX未達時の維持率・FIX復帰時間は算出不能としてnullにした。FIXしなかったという観測と、装置がFIX不能という結論は異なる。窓際の遮蔽・マルチパス、信号帯域の共通性が制約となり、屋外開放環境での再試験が必要。

| 試験区間 | PVT数 | FLOAT数 | FIX数 | RAWX数 | RAWX最大間隔 s | SFRBX数 |
|---|---:|---:|---:|---:|---:|---:|
{phase_table}

近傍局試験は接続180秒→切断60秒→再接続120秒。切断時にはソケットを閉じ、再接続時に新しいNTRIP要求を行った。実際の接続/切断時刻は [イベント](../01_Basic/nearby/test_events.json) 参照。受信機の補正有効期限は初期設定のまま観察した。

## 初期試験の位置づけ
登録不要の `ntrip.aitoya.net:2101/MOSAIC-RTCM3` にも接続・CRC検証・受信機入力成功。初回ネットワーク収録は約35.6秒、30,519 bytes、324完全フレーム、CRC/解析エラー0件。
実機位置取得後、受信機が `DGNSS long baseline (437 km)` を通知したため、近距離RTKの評価には採用しなかった。初期試験は補正入力だけを60秒停止する計画だったが、実際の配信受信は経過216.2秒で終了し、予定停止開始275.2秒より前に途絶えた。したがって初期試験の断絶原因・再開結果は計画的切断試験として評価しない。近傍局のソケット切断・再接続試験を評価の正本にした。[AITOYA公式案内](https://ntrip.aitoya.net/)

## 保存物
nearby_states.png が近傍局の状態グラフ。rtk_states.png は437 km基線の初期試験。ntrip_capture.png はPC側ネットワーク試験。
近傍局の生RTCM・入力バイト数は [近傍局データ](nearby/)、候補比較はbase_candidates.jsonと各候補フォルダに保存。
ソーステーブルからの距離は丸め座標による概算であり、基線の厳密測量値ではない。
'''
write('02_RTK/REPORT.md',rtk)
pp=f'''# ③ PPK用データ保存・解析：実測ログで実行

検証日：2026-10-09 JST。RTKLIB EX 2.5.1を使用。

| 確認項目 | 結果 |
|---|---|
| UBX-RXM-RAWX保存 | 確認済み。近傍局試験で{n['message_counts'].get('RXM-RAWX',0)}件 |
| UBX-RXM-SFRBX保存 | 確認済み。近傍局試験で{n['message_counts'].get('RXM-SFRBX',0)}件 |
| RTK中のRAW同時保存 | FLOATを含む補正接続中に記録。FIX中の同時保存はFIX未達なら未確認 |
| NTRIP切断中のRAW継続 | 60秒切断区間にRAWX {n['phases'].get('correction_off',{}).get('rawx_epochs',0)}件、SFRBX {n['phases'].get('correction_off',{}).get('sfrbx_messages',0)}件 |
| RAW→RINEX | 実機rover.ubxからRINEX 3.04 OBS/NAVを生成 |
| 基準局RINEX | 同時収録の近傍局RTCMからbase.obsを生成 |
| PPK実行 | RNX2RTKPで実行。解{ppk['ppk']['solutions']}件、Q別件数 {ppk['ppk']['quality_counts']} |

## RINEXとPPK条件
移動局観測：{ppk['rover']['epochs']}エポック。基準局観測：{ppk['base']['epochs']}エポック。基準局はNTRIP切断中の約60秒が欠測。PPK解の最大観測時刻差は{ppk['ppk']['max_abs_age_s']}秒で、断絶区間の同時刻基準局データを別途取得した試験ではない。実際の時刻範囲はppk_summary.jsonおよびRINEXヘッダー参照。時刻系はGPSであり、レポートの日付はJST。
基準局は無料の `geortk.jp:2101/btf_nishiyamacho3`。PPK用にリアルタイムRTCMを同時保存してRINEX化したもので、測量用の保証された成果・アンテナ較正値ではない。
PPK条件：{ppk['ppk']['settings']}。基準局座標は基準局RINEXヘッダーのECEF {ppk['ppk']['base_ecef_m']} mを明示指定。航法暦は移動局SFRBX由来のrover.navを使用した。
RTKLIB Qは1=FIX、2=FLOAT、4=DGPS、5=SINGLE。今回のPPKはFIX 3エポック（約0.83%）、FLOAT 356エポック、DGPS 1エポックであり、安定したFIX解は確認できない。PPK実行成功と安定したFIX解の取得は別に評価する。FIX判定3点はFLOAT位置中央値から約3.4～5.6 m離れた孤立点であり、正しいFIXとは認定していない（fix_candidates.json参照）。短いFIX判定は真値との比較未実施で、正しい整数アンビギュイティの独立検証も行っていない。移動局RINEXにはGPS L1・GLONASS L1・BeiDou B1I/B2aがあり、今回の記録にGalileo観測やGPS L5観測は含まれなかった。基準局にE5aがあっても、移動局で共通観測がなければ二周波RTKの条件は整わない。

## データ・グラフ
実測入力・変換出力・解析結果・コマンド・ログは [近傍局PPKデータ](nearby/) に保存：rover.ubx、rover.obs、rover.nav、base.obs、ppk.pos、ppk_solutions.csv、ppk_summary.json、各処理ログ。
nearby_raw_continuity.pngは切断区間を含むRAW継続グラフ、ppk_results.pngはPPK解状態と平均位置からのばらつき。既知の真値がないため絶対位置精度を実証するグラフではない。
このフォルダ直下のbase.obs/base_observations.pngは初期AITOYAネットワーク試験の短いRINEXであり、近傍局PPKには使っていない。

## 再現
プロジェクト直下で `python tools/process_ppk.py nearby`。実行したCONVBIN/RNX2RTKPの完全な引数・終了コードはppk_summary.jsonに記録。
[RTKLIB公式リリース](https://github.com/rtklibexplorer/RTKLIB/releases/tag/v2.5.1) のアーカイブSHA256：0B20C940B1939B0701F0EE027DAF5225221120DBFF50C3F563F8705FD0B496F5。
別の無料基準局RINEX入手先：[国土地理院](https://terras.gsi.go.jp/)、[提供内容](https://terras.gsi.go.jp/purvey_info.html)。今回は同時取得した近傍局データを使用し、地理院データはダウンロードしていない。
'''
write('03_PPK/REPORT.md',pp)
write('README.md',f'''# RTK-GNSS 動作検証レポート

検証日：2026-10-09 JST。NEO-F9PをUSB COM7で実測。アンテナは窓際。

| 区分 | 結果 | レポート |
|---|---|---|
| ① 基本動作・設定 | USB・衛星受信・1/5/10 Hz設定・GNSS時刻を確認。出力過多で欠測あり。PPS端子波形は未検証 | [詳細](01_Basic/REPORT.md) |
| ② RTK測位 | 無料の近傍基準局で{status}。切断・再接続を実施 | [詳細](02_RTK/REPORT.md) |
| ③ PPK用保存 | RAWX/SFRBX、切断中の保存継続、RINEX変換、PPK実行を確認。PPK解{ppk['ppk']['solutions']}件、Q別{ppk['ppk']['quality_counts']} | [詳細](03_PPK/REPORT.md) |

各分類フォルダに実測グラフを保存し、近傍局データは各分類のnearbyフォルダ、周期再試験は01_Basic/rates_leanにまとめた。スクリプト用の元データ一式もnearbyとrates_leanに残した。metrics.jsonが初期試験、nearby/metrics.jsonが近傍局試験の集計。
**全項目の合格を確認したものではない。** FIX未達ならFIX時間・維持率・FIX復帰時間は未評価。PPSの電気的出力と絶対位置精度は別途実測が必要。
無料接続設定は `geortk.jp:2101/btf_nishiyamacho3`、認証なし。設定はRAMのみ変更し終了時に復元、読み戻し結果：{restores}。

## 再実行
`python tools/verify_receiver.py COM7 --rtk-only --lean --session new_test --host geortk.jp --mount btf_nishiyamacho3`
`python tools/analyze_measurements.py new_test`
`python tools/process_ppk.py new_test`
既存セッション名を再利用するとログが混在する可能性があるため、新しいsession名を使う。
製品：[Switch Science 9456](https://www.switch-science.com/products/9456)。
''')
from document_conditions import run as document_conditions
document_conditions()
from document_gsi import run as document_gsi
document_gsi()
print('Final reports written')
