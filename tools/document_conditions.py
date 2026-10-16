"""Document assumptions and actual processing inputs from recorded evidence."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / 'reports'
BEGIN, END = '<!-- verification-conditions:start -->', '<!-- verification-conditions:end -->'

def add(path, content):
    text = path.read_text(encoding='utf-8')
    if BEGIN in text:
        before, remaining = text.split(BEGIN, 1)
        _, after = remaining.split(END, 1)
        text = before.rstrip() + after
    title, rest = text.split('\n', 1)
    path.write_text(title + '\n\n' + BEGIN + '\n' + content.strip() + '\n' + END + '\n' + rest, encoding='utf-8')

def run():
    env = json.loads((R / 'environment.json').read_text(encoding='utf-8'))
    pp = json.loads((R / 'nearby/03_PPK/ppk_summary.json').read_text(encoding='utf-8'))
    events = json.loads((R / 'nearby/01_Basic/test_events.json').read_text(encoding='utf-8'))
    connected = next(e for e in events if e['event'] == 'ntrip_connected')
    restored = next(e for e in events if e['event'] == 'restore_check')
    jst = timezone(timedelta(hours=9))
    def local(s):
        return datetime.fromisoformat(s).astimezone(jst).strftime('%Y-%m-%d %H:%M:%S')
    dependencies = '\n'.join(f'| {name} | {version} |' for name, version in env['dependencies'].items())
    common = f'''## 共通の前提条件・使用環境

| 項目 | 今回の条件・確認方法 |
|---|---|
| 対象機器 | SparkFun NEO-F9P搭載L1/L5モジュール（Switch Science製品9456）。実機MON-VERでNEO-F9P、FW HPGL1L5 1.40、PROTVER 27.40を確認 |
| PCとの接続 | USB Type-CでPCへ直接接続。ケーブル交換後にCOM7、USB VID:PID=1546:01A9を確認 |
| アンテナと設置 | ユーザー申告ではアンテナを窓際に設置。型番、L1/L5対応仕様、ケーブル長、グランドプレーン、固定具、設置高さ・周囲遮蔽物は記録していない |
| 観測環境 | 窓際に置いた状態で観測。屋外の開けた空・測量標石上の観測ではない。意図的な移動操作は行っていないが、厳密な静止固定は計測していない |
| 実行環境 | Windows / PowerShell、Python {env['python'].split()[0]}（64 bit）。OSビルド・PC性能は試験時に記録していない |
| USBのシリアル設定 | pyserialで115200、既定の8N1、読み取りタイムアウト0.2秒。115200は仮想COMを開く際の指定値であり、USB実効帯域やUART出力設定の実測値ではない |
| 受信機の設定変更 | 設定はRAMのみ変更。初期値を読み取り、各試験終了時に復元・読み戻し一致を確認。コールドリセットや不揮発保存は行っていない |
| 評価対象 | その時点の受信状態を引き継いだ短時間の動作確認。コールドスタート性能、長時間の安定性、移動中の性能は今回の評価範囲に含まれない |
| 精度評価の基準 | 既知座標の真値、別の測量機による対照測定、PPS波形測定は用意していない。hAcc/vAccやPPKのばらつきを絶対位置誤差と同一視しない |
| 時刻の扱い | レポートの日付・観測時刻はJST、イベントのutcはUTC、RINEX・PPKはGPST。RAWXでうるう秒18秒を確認。PC時計のUTC同期精度は未評価 |

### 使用したソフトウェア

| ソフトウェア・ライブラリ | バージョン |
|---|---|
{dependencies}
| RTKLIB EX / CONVBIN / RNX2RTKP | 2.5.1 |
| Markdown（HTMLレポート生成のみ） | 3.11 |

pyserialでUSB通信、pyubx2/pynmeagpsで受信メッセージの解析、pyrtcmでPC側RTCMのCRC検証・信号識別、matplotlibでグラフを作成した。GNSS観測は実機ログであり、シミュレーションや合成データではない。Markdownは表示用の変換にだけ使用した。

ソフトウェア版の記録元はenvironment.json、Python依存の指定はtools/requirements.txt。RTKLIBの入手元・アーカイブのSHA256・実行引数は③PPKレポートとppk_summary.jsonを参照。
'''
    add(R / 'README.md', common)
    add(R / '01_Basic/REPORT.md', common + '''

## この試験の設定・集計方法

| 項目 | 条件 |
|---|---|
| 更新周期試験 | CFG-RATE-MEASを1000 / 200 / 100 ms、CFG-RATE-NAVを1に設定。各試験は1 Hzを40秒、5 Hzを25秒、10 Hzを25秒。設定ACKと読み戻しを確認 |
| 最初の出力条件 | 既存NMEA出力を維持し、USBへNAV-PVT/SAT/SIG/TIMEUTC、RXM-RAWX/SFRBX/RTCM、TIM-TPを追加。RAWX等の出力率は各測位エポックに対して1 |
| 出力削減の再試験 | USB/UART1のNMEA出力を一時停止。NAV-SAT/SIG/TIMEUTCの出力率を1/5/10にして各測位周期でも約1 Hzの通知とした。NAV-PVTとRAWXは各エポック出力 |
| 更新間隔 | 同じ試験区間の連続NAV-PVTのiTOW差を使用。GPS週の折り返しを考慮。PCへ届いた間隔だけで測位更新周期を判定していない |
| 実効Hz・推定欠測 | 実効Hz=1000×区間内のiTOW間隔数÷間隔合計ms。推定欠測は設定周期とiTOW差から算出。区間端や設定直後の過渡を含む短時間の集計である |
| 衛星数・C/N0 | 使用衛星数はNAV-PVTのnumSV。追跡衛星数とC/N0集計はNAV-SATのC/N0>0を対象とし、各エポックの中央値と最大値を算出。仰角による追加除外はしていない |
| GNSS時刻 | NAV-TIMEUTCのvalidUTC、およびNAV-PVTのvalidDate/validTime/fullyResolvedを使用 |
| PPS | TP1有効・周期設定とTIM-TP通知を確認。オシロスコープ、カウンタ等は接続していないため、電気出力・ジッタ・絶対時刻精度は未検証 |

検証コード：tools/verify_receiver.py、tools/analyze_measurements.py。根拠はoriginal_config.json、test_events.json、receiver_messages.jsonl、pvt.csv。初期試験と出力削減再試験は別の時刻に行っており、衛星配置・信号強度を完全に同条件へ固定した比較ではない。
''')
    add(R / '02_RTK/REPORT.md', common + f'''

## RTK試験の前提・補正源・判定方法

| 項目 | 条件 |
|---|---|
| 評価の正本となる補正源 | geortk.jp:2101 / btf_nishiyamacho3。今回の接続は認証なし、NTRIPのICY 200 OKを確認 |
| 基線長 | ソーステーブルの丸め座標と単独測位の受信位置から約7.5 kmと概算。厳密に測量した基線長ではない |
| 観測時間（JST） | NTRIP初回接続 {local(connected['utc'])} ～ 終了時の設定復元確認 {local(restored['utc'])}。短時間の1セッションであり、日・天候・設置を変えた反復試験ではない |
| 測位・RAW出力 | 1 Hz。USB/UART1のNMEA出力を一時停止し、UBXで測位・衛星・RAW・補正通知を取得 |
| 試験の順番 | 約180秒接続 → 約60秒ソケット切断 → 約120秒再接続。切断中はネットワーク補正を受信機に入力しない |
| 補正受信の根拠 | PC側NTRIP受信に加え、受信機RXM-RTCMのcrcFailedとmsgUsedを確認。PC受信のみを実機の利用成功と扱っていない |
| FLOAT/FIX判定 | NAV-PVTのgnssFixOkが有効かつcarrSoln=1をFLOAT、carrSoln=2をFIXとして集計。RTKLIBのPPK判定とは別の結果 |
| 復帰時間 | 実際のNTRIP接続成功イベントから、最初に状態を確認したメッセージのPC受信時刻までの差。1 Hz観測・USB伝送・PC処理の遅延を含むため、約0.77秒を高精度な受信機内部の収束時間とは解釈しない |
| FIX維持率 | 初回FIX以降の接続区間を評価する設計だが、今回リアルタイムFIXがないため算出していない。FIX未達を0秒で成功した値として扱わない |
| 信号の共通性 | 基準局でE1/E5aを確認しても、移動局の今回のRINEXにはGalileo観測がない。GPSも移動局・近傍局とも今回L1のみ。全衛星系で共通の二周波観測が揃った条件ではない |

初期AITOYA補正源は約437 km離れていたため、近距離RTKの性能判定には採用していない。近傍局選定・切替前後のデータを混ぜてFIX時間や維持率を算出していない。
根拠：nearby/test_events.jsonは①のnearbyフォルダ内、補正入力は②のnearby/injection.csv、状態は①のnearby/receiver_messages.jsonl。PC時計の絶対同期精度・ネットワークの片道遅延は測定していない。
''')
    command_blocks = []
    for step in pp['steps']:
        args = step['command']
        # Preserve flags and values while using reviewable workspace-relative paths.
        normalized = []
        for arg in args:
            if arg.startswith(str(ROOT)):
                arg = str(Path(arg).relative_to(ROOT)).replace('\\', '/')
            normalized.append('"' + arg + '"' if ' ' in arg else arg)
        command_blocks.append(f"### {step['step']}（終了コード {step['exit_code']}）\n\n```text\n" + ' '.join(normalized) + '\n```')
    add(R / '03_PPK/REPORT.md', common + f'''

## 従来局の解析に使用したデータ・ソフトウェア・設定

| 項目 | 今回の入力・前提 |
|---|---|
| 移動局の入力 | nearby/rover.ubx。実機のRAWX（擬似距離・搬送波位相・Doppler等）とSFRBXを記録。CONVBINでnearby/rover.obsとrover.navへ変換 |
| 基準局の入力 | ②のnearby/concurrent_base.rtcm3。移動局と並行収録したgeortk.jp / btf_nishiyamacho3のRTCMをCONVBINでnearby/base.obsへ変換。地理院からダウンロードしたRINEXではない |
| 観測時間範囲（GPST） | 移動局 {pp['rover']['first']['gps_epoch']} ～ {pp['rover']['last']['gps_epoch']}。基準局 {pp['base']['first']['gps_epoch']} ～ {pp['base']['last']['gps_epoch']} |
| 観測数・周期 | 移動局{pp['rover']['epochs']}エポック、基準局{pp['base']['epochs']}エポック、約1 Hz。基準局はNTRIP切断中の約60秒が欠測 |
| 航法暦 | 移動局SFRBXから生成したrover.navの放送暦。外部の精密暦SP3・精密時計CLKは使用していない。今回の補正源からbase.navは生成されていない |
| 変換ソフト | RTKLIB EX 2.5.1 / CONVBIN。RINEX 3.04。移動局はSNRとDopplerを含める -os -od、基準局はSNRを含める -os |
| RTCMの日付の基準 | -tr 2026/10/08 15:30:12。接続イベントのUTC近傍をCONVBINに与えてRTCMの週・日付を解釈。GPSTに変換した観測時刻はRINEXヘッダーに保存 |
| PPK解析ソフト | RTKLIB EX 2.5.1 / RNX2RTKP。入力順は移動局OBS、基準局OBS、移動局NAV |
| 測位モード | -p 2：kinematic。アンテナは窓際へ設置したが、解析をstaticモードへ拘束せず各エポックの解を評価 |
| 解の方向 | -c：forward/backward combined。リアルタイム受信機のFLOAT/FIXとは異なる後処理結果 |
| 周波数設定 | -f 3：L1+L2+L5を解析対象として許容。実際に全帯域の共通観測が存在することを意味しない |
| 衛星系設定 | -sys G,R,E,J,C：GPS / GLONASS / Galileo / QZSS / BeiDouを許容。実際に移動局RINEXに記録された衛星系はG/R/C |
| 仰角マスク | -m 10：10度 |
| アンビギュイティ検定 | -v 3：ratio閾値3。判定を通ったことだけで真値との一致を証明しない |
| 基準局座標 | -r指定のECEF X=-3722449.1636 m、Y=3703871.7156 m、Z=3608134.2255 m。基準局RINEXヘッダーから取得し、測量成果との独立照合はしていない |
| 未指定の処理条件 | -kによる追加設定ファイルは使用していない。上記以外はRTKLIB EX 2.5.1の内蔵既定値。電離層・対流圏・誤差モデル等の全既定値ダンプは保存していないため、同じ実行ファイルでの再現を前提とする |
| 欠測と観測時刻差 | 出力ppk.posのageの最大絶対値は{pp['ppk']['max_abs_age_s']}秒。切断中の同時刻基準局観測を後から補充した解析ではない |

### 実際に変換された観測信号

移動局はGPS L1、GLONASS L1、BeiDou B1I/B2a。基準局はGPS L1、GLONASS L1、Galileo E1/E5a、BeiDou B1I/B2aの観測がある。BeiDou B2aのRINEX観測コード表現は移動局がC5X/L5X、基準局がC5P/L5Pであり、コード表現も同一ではない。共通信号の採用処理は使用したRTKLIB実装に従う。全衛星・全周波数が組み合わされて測位に使用されたことを、この設定値だけから保証しない。

### グラフと判定の前提

PPK位置図は全出力解の平均緯度・経度を原点とし、地球半径6378137 mを用いた近傍の東・北変位近似で描画した。既知の真値を原点とした誤差図ではない。孤立したFIX候補の約3.4～5.6 mは、FLOAT解の緯度・経度中央値を原点にした水平距離であり、位置図の平均原点と区別する。
PPKのQ=1をFIX候補、Q=2をFLOAT、Q=4をDGPSとして数えた。FIX3点を除外して解析をやり直した結果ではなく、全360解を保存している。正解座標や独立した観測機による検証はなく、安定したセンチメートル精度を確認できたとは扱わない。

### 再現に使うコマンド

以下はプロジェクト直下を基準に、実行記録のパスだけを相対表示したもの。完全なWindows絶対パスを含む引数はnearby/ppk_summary.json、処理ログはnearby/*_log.txtに保存。PowerShellで実行ファイルを直接起動する場合は行頭へ `&` を付ける。

''' + '\n\n'.join(command_blocks))
    print('Documented conditions in overview and all three category reports')

if __name__ == '__main__':
    run()
