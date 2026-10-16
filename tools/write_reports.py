"""Write reports from actual saved evidence, without synthetic GNSS samples."""
import csv, json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT = Path(__file__).resolve().parents[1]
R = ROOT / 'reports'
plt.rcParams['font.family'] = 'Yu Gothic'
def write(path, text): (R/path).write_text(text, encoding='utf-8')
result = json.loads((R/'02_RTK/ntrip_result.json').read_text(encoding='utf-8'))
devices = json.loads((R/'01_Basic/windows_devices.json').read_text(encoding='utf-8-sig'))
rows = []
for line in (R/'03_PPK/base.obs').read_text().splitlines():
    if line.startswith('>'):
        f = line.split()
        rows.append({'gps_epoch': ' '.join(f[1:7]), 'satellites': int(f[8])})
with (R/'03_PPK/base_epochs.csv').open('w', newline='', encoding='utf-8') as f:
    w=csv.DictWriter(f, fieldnames=['gps_epoch','satellites']); w.writeheader(); w.writerows(rows)
fig, ax = plt.subplots(figsize=(9,4))
ax.plot(range(len(rows)), [r['satellites'] for r in rows], marker='.')
ax.set(xlabel='最初のエポックからの経過秒（GPS時刻）', ylabel='観測衛星数', title='AITOYA基準局 RINEX観測データ（移動局のデータではありません）')
ax.grid(alpha=.3); fig.tight_layout(); fig.savefig(R/'03_PPK/base_observations.png', dpi=160); plt.close(fig)
fig, ax = plt.subplots(figsize=(7,4))
ax.bar(['COMポート', 'USB機器'], [len(devices['serial_ports']),len(devices['usb_devices'])])
ax.set(ylabel='Windowsが検出した機器数', title='PC側の機器検出結果（衛星受信結果ではありません）')
fig.tight_layout(); fig.savefig(R/'01_Basic/device_detection.png', dpi=160); plt.close(fig)
write(Path('01_Basic/REPORT.md'), '''# ① 基本動作・設定：接続待ち

検証日：2026-10-09（JST）。接続申告：受信機とPCをUSB Type-Cで直接接続。
Windows PnP列挙、System.IO.Ports、pyserialの3経路で確認し、COMポートは0件。USB機器一覧にもu-bloxを識別できる機器はなく、現在接続中のエラー機器も検出されなかった。受信機の故障・ドライバー不良と断定する証拠はない。

| 確認項目 | 結果 | 理由・必要な実測 |
|---|---|---|
| PCとのUSB通信 | 未成立 | 受信機が列挙されず、UBX応答試験に進めない |
| 衛星数・C/N0 | 未実施 | UBX-NAV-SAT/SIGを取得できない。0衛星という意味ではない |
| 1/5/10 Hz設定 | 未実施 | CFG-RATE設定応答・設定読み戻し・NAV-PVT iTOW間隔の実測が必要 |
| GNSS時刻 | 未実施 | NAV-PVT/NAV-TIMEUTCの有効フラグを含め確認が必要 |
| PPS | 未実施 | USBでの時刻メッセージ確認と端子の電気的パルス確認は別。TIMEPULSE端子をオシロスコープ等で測定する必要がある |

## 証拠
- windows_devices.json：JST記録時刻、ポート一覧、USB機器一覧、問題機器一覧。
- device_detection.png：Windows機器検出数。衛星・C/N0・測位周期のグラフは未取得のため作成していない。

## 再開条件
電源LEDを確認し、通信実績のあるUSBケーブルと別USBポートで再接続する。アンテナはSMA端子に接続し、L1/L5対応を確認して見通しのよい屋外へ固定する。COMポートが現れたら型番・ファームウェアをMON-VERで確認して測定を開始する。
''')
write(Path('02_RTK/REPORT.md'), f'''# ② RTK測位：PC側NTRIP受信成功、実機測位は未実施

検証日：2026-10-09（JST）。実測開始UTC：{result['utc_started']}。

## 無料で使った接続設定
- ホスト：ntrip.aitoya.net
- ポート：2101
- マウントポイント：MOSAIC-RTCM3
- 認証：今回の接続ではユーザー名・パスワードなしで成功。
- 設定場所：tools/probe_ntrip.py の HOST, PORT, MOUNT。
- 配信元：[AITOYA BASE](https://ntrip.aitoya.net/)。公式案内の利用目安は高田馬場から約20 km圏内。移動局位置が不明なため基線長は未評価。

## 実測結果
応答 `{result['status_line']}`、受信時間 {result['duration_s']:.3f} 秒、受信量 {result['bytes']:,} bytes。
完全フレーム {result['valid_frames']} 件でCRC検証成功、検出した完全フレームのCRC/解析エラー {result['invalid_frames']} 件。冒頭・末尾の不完全フレームはこの分母に含めない。
種別ごとの件数：{result['message_counts']}。

RTCMのMSM観測信号：{result['msm_signals']}。
この区間のGPSはL1/L2、GalileoはE1/E5bで、GPS L5・Galileo E5aを確認できない。NEO-F9PのL1/L5と二周波の組合せが一致する補正源としては、この配信を採用確定できない。RTCMメッセージ番号が対応していても信号の互換性・実機利用確認とは別である。

| 確認項目 | 結果 |
|---|---|
| NTRIP接続 | PC側で成功 |
| 対応RTCMの受信 | PC側で1006/1033/1074/1084/1094/1124/1230等を確認。受信機への入力・利用は未確認 |
| FLOAT→FIX | 未実施（受信機未検出） |
| FIXまでの時間・維持率 | 測定不能、0秒・0%として扱わない |
| 補正断絶・再接続後の復帰 | 未実施 |

## 保存データ
base.rtcm3（配信実データ）、sourcetable.txt、response_header.txt、network_chunks.csv、rtcm_frames.csv、ntrip_result.json、ntrip_capture.png。
グラフはネットワーク受信量とCRC検証済みメッセージ件数であり、測位精度・FIX維持率のグラフではない。

## 再開後の試験条件
アンテナを静止固定し、NAV-PVTのgnssFixOK/carrSolnとRXM-RTCMのCRC・使用状態を記録する。補正開始から初回FIX、最初のFLOATからFIXを別々に計時する。初回FIX後の連続区間でFIX秒数/有効観測秒数を算出し欠測時間も併記。補正入力を60秒停止してRAW保存を継続し、再開から再FIXまでを記録する。初回FIXが得られない場合、維持率は算出しない。

参考：[NEO-F9P統合マニュアル](https://docs.sparkfun.com/SparkFun_u-blox_NEO-F9P/assets/component_documentation/NEO-F9P_IntegrationManual_UBX-22028362.pdf) の対応RTCM一覧。
''')
write(Path('03_PPK/REPORT.md'), f'''# ③ PPK用データ保存：基準局RINEX取得、移動局データ待ち

検証日：2026-10-09（JST）。無料のAITOYA配信RTCMを保存し、RTKLIB EX 2.5.1のCONVBINでRINEX 3.04観測ファイルへ変換した。

| 確認項目 | 結果 |
|---|---|
| NEO-F9P RAWX記録 | 未実施、受信機未検出 |
| NEO-F9P SFRBX記録 | 未実施、受信機未検出 |
| RTK中のRAW同時保存 | 未実施 |
| NTRIP断絶中のRAW継続 | 未実施 |
| 移動局RAW→RINEX | 未実施、移動局UBXなし |
| 基準局RINEX入手 | 成功：配信RTCMからbase.obsを生成。移動局と同時刻のデータではない |
| PPK解析 | 未実施：移動局観測・航法データがない |

## 基準局RINEXの実測内容
base.obsは{len(rows)}エポック。時刻系はGPSで、UTCより18秒進んだ時刻として出力されている。最初と最後の時刻はRINEXヘッダー参照。
base_epochs.csvとbase_observations.pngに各エポックの観測衛星数を保存した。
観測ヘッダーのGPSはC1C/L1C・C2W/L2W、GalileoはC1C/L1C・C7Q/L7Q。L5/E5aを含まないためNEO-F9Pの二周波PPK向け補正源としての適合性は未確認。
航法メッセージは今回の配信に含まれずbase.navは生成されなかった。解析には受信機SFRBX等から生成する航法暦が別途必要。

## 再現コマンド（PowerShell、プロジェクト直下）
```powershell
$gnssRoot = (Get-Location).Path
& .\\tools\\rtklib\\RTKLIB_EX_2.5.1\\convbin.exe -r rtcm3 -tr 2026/10/08 15:17:15 -v 3.04 -os -o "$gnssRoot\\reports\\03_PPK\\base.obs" -n "$gnssRoot\\reports\\03_PPK\\base.nav" "$gnssRoot\\reports\\02_RTK\\base.rtcm3"
```
`-tr`は今回の取得日のUTC近傍を与えた。別日に収録したRTCMにはその日の時刻を指定する。入力パスはWindowsの絶対パスを使用する。

## 今後の無料データ候補
[国土地理院 電子基準点データ提供](https://terras.gsi.go.jp/) から近傍局・同時刻のRINEXを選ぶ。局は移動局位置が得られてから選定する。公開内容・遅延・必要手続きの確認が必要で、今回ダウンロードは実施していない。30秒観測は今回の短時間RTK試験と同じ評価条件にはならない。[提供情報](https://terras.gsi.go.jp/purvey_info.html)

RTKLIB入手先：[rtklibexplorer公式リリース](https://github.com/rtklibexplorer/RTKLIB/releases/tag/v2.5.1)。tools/rtklibにCONVBINおよびRNX2RTKPを展開済み。RNX2RTKPの実行は適切な同時刻の移動局・基準局観測と航法ファイルが揃ってから行う。
''')
write(Path('README.md'), '''# RTK-GNSS 動作検証レポート

2026-10-09（JST）。**検証は部分完了。実機試験は受信機のUSB認識待ち。**

| 区分 | 現在の結果 | 詳細 |
|---|---|---|
| ① 基本動作・設定 | COMポート0件、実機試験に進めず | [レポート](01_Basic/REPORT.md) |
| ② RTK測位 | 無料NTRIPのPC側受信成功、実機FIX未確認 | [レポート](02_RTK/REPORT.md) |
| ③ PPK用保存 | 基準局RINEX変換成功、移動局RAW・PPK未実施 | [レポート](03_PPK/REPORT.md) |

各フォルダに実測データとそのグラフを保存。未取得の測位データは生成していない。
NEO-F9PはL1/L5受信機。今回の無料配信の観測信号はL5/E5aを含まず、二周波RTKの適合性は未確認。
再開には受信機の電源LED・通信可能なUSBケーブル・COMポート出現を確認する必要がある。USB通信が成立してもPPS端子のパルス実測には測定器が必要。

## 再実行
`python tools/probe_ntrip.py`：無料NTRIPを約35秒取得（既存の02_RTKデータを置き換える）。受信機には接続しない。
`python tools/write_reports.py`：保存データからレポートと機器検出・RINEX観測グラフを再生成。
Python依存は.depsに置いたpyubx2/pyrtcmと、ホストのpyserial/matplotlibを使用。

製品参照：[Switch Science 9456](https://www.switch-science.com/products/9456)。仕様の記載と実機検証の合否は区別した。
''')
print({'base_epochs':len(rows), 'ports':devices['serial_ports'], 'reports':str(R)})
