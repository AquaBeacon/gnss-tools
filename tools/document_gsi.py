"""Append an idempotent, evidence-based GSI comparison to the reports."""
from pathlib import Path
import json, re
ROOT=Path(__file__).resolve().parents[1]
R=ROOT/'reports'

def append(path,text):
    content=path.read_text(encoding='utf-8')
    content=re.sub(r'\n<!-- gsi-comparison:start -->.*?<!-- gsi-comparison:end -->\n?', '',content,flags=re.S)
    content=content.replace('今回は同時取得した近傍局データを使用し、地理院データはダウンロードしていない。','当初の解析には同時取得した近傍局データを使用した。地理院データによる追加解析は下記を参照。')
    path.write_text(content+'\n<!-- gsi-comparison:start -->\n'+text+'\n<!-- gsi-comparison:end -->\n',encoding='utf-8')

def run():
    source=R/'03_PPK/gsi/comparison_summary.json'
    if not source.exists():return
    s=json.loads(source.read_text(encoding='utf-8'))
    labels={'gsi_rover_nav':'地理院OBS＋移動局NAV（1秒出力）','gsi_official_nav':'地理院OBS＋地理院NAV（1秒出力）','gsi_gr_30s':'地理院OBS＋地理院NAV（G/R・30秒抽出）','community_gr_30s':'従来局OBS＋地理院NAV（G/R・30秒抽出）'}
    table='| 解析 | 出力解数 | FIX | FLOAT | DGPS | 最大時刻差 |\n|---|---:|---:|---:|---:|---:|\n'
    table+='| 従来局OBS＋移動局NAV（従来結果） | 360 | 3 | 356 | 1 | 30秒 |\n'
    for name,result in s['runs'].items():
        q=result['quality_counts']
        table+=f"| {labels[name]} | {result['solutions']} | {q.get('1',0)} | {q.get('2',0)} | {q.get('4',0)} | {result['max_abs_age_s']:g}秒 |\n"
    text='''## 国土地理院のデータによる追加PPK検証

無料公開データのダウンロードとPPK実行を確認した。地理院OBSと地理院NAVを用いた解析では360解、FLOAT 18・DGPS 342・FIX 0。今回の短時間・窓際の移動局データでは安定したFIXを確認できず、従来局の結果より良くなったとは判断できない。

### 取得元と前提条件

| 項目 | 内容 |
|---|---|
| 提供元 | [国土地理院 電子基準点データ提供サービス](https://terras.gsi.go.jp/) の公開ダウンロード。今回の操作ではアカウント・認証・料金なしで取得できた |
| 基準局 | 明石Ａ / AKASHI-A / 局番号221245 / RINEX局名1245。API上で稼働中を確認。旧局「明石950358」は廃止済みのため使っていない |
| 基線の概算 | 約8.81 km。移動局概略座標と局メタデータから求めた地表距離で、測量値ではない |
| 基準局機器 | RINEXヘッダー：TRIMBLE ALLOY、FW 6.15,22/JUL/2022、アンテナTRM59800.80 GSI4 |
| 取得指定 | UTC 2026-10-08 15時台、GRJE、RINEX 3.02。リクエスト本文と応答HTMLを保存 |
| 実ファイルの時間系 | OBSヘッダーはGPST 2026-10-08 15:00:00～15:59:30。120エポック、30秒間隔。ファイル中の時刻を基準に移動局との重なりを確認し、手動で18秒ずらす処理はしていない |
| 移動局 | 従来と同じnearby/rover.obs。GPST 15:30:30.001～15:36:30.001、361エポック。新規の実機観測は行っていない |
| 基準局座標 | RINEXヘッダーのECEF X=-3711148.5910、Y=3715501.1187、Z=3607795.0860 mを-rで指定。ANTENNA: DELTA H/E/Nは0/0/0。測量成果表との照合、外部ANTEXによる位相中心補正は行っていない |
| 航法暦 | 地理院の同時取得ファイル.26n（GPS）、.26g（GLONASS）、.26l（Galileo）、.26q（QZSS）。放送暦であり精密暦・精密時計ではない。比較用に従来の移動局NAVを使う解析も実施 |
| 共通観測 | 地理院はG/R/J/E、移動局はG/R/C。今回の共通衛星系はGPSとGLONASSで、移動局の共通帯域はL1。地理院入力にはBeiDouが含まれず、従来局との信号条件が異なる |
| 共通解析設定 | RTKLIB EX 2.5.1、kinematic、forward/backward combined、-f 3、仰角10度、AR ratio 3、-k設定ファイルなし。他は同じ実行ファイルの内蔵既定値 |
| 1秒出力の扱い | 移動局は1秒、地理院基準局は30秒の入力。30秒OBSを1秒観測へ補間生成していない。最近傍観測を用いた解のage最大は15秒 |
| 30秒比較 | 両基準局に同じ地理院NAV、G/R、-ti 30を指定。age最大0.00秒（.pos出力の小数2桁丸め）。従来局の60秒欠測は残し、共通エポックだけに限定していないため出力解数は異なる |

### 実行結果

'''+table+'''
4通りの追加解析はすべて終了コード0で出力ファイルを生成した。ただし「実行成功」は「高精度測位成功」を意味しない。30秒抽出では入力から出力候補は13時刻になるが、全時刻で解は得られていない。従来局の3点のFIX候補についても、先に記載した通り正しさは未確認。

地理院にはNTRIP切断中に対応する時刻の基準局観測も存在する。これにより基準局欠測を後処理で補えることは確認したが、入力周期・利用可能な信号・基準局座標・航法暦が異なるため、解数やFIX率だけから基準局の優劣は判断できない。窓際環境、短い観測時間、GPS/GLONASSのL1共通観測などは制約となり得るが、今回の試験だけでFIX未達の原因を特定していない。

### グラフ・保存物・再現

追加グラフは `gsi/gsi_quality_comparison.png`（4解析のQ時系列）と `gsi/gsi_position_age.png`（地理院OBS＋NAVの位置ばらつき・age）。位置の原点は地理院解析の全出力解の緯度・経度中央値。地球半径6378137 mによる近傍変位近似であり、真値に対する絶対誤差ではない。Q=1はFIX、2はFLOAT、4はRTKLIBのDGPS分類で、誤差の保証値ではない。

入力OBS、NAV、元のgzip/tar.gz、各.pos・CSV・実行ログ、完全なコマンドと入力SHA256、取得時刻・配布ファイルSHA256を[gsiフォルダ](gsi/)へ保存。主な記録は[比較サマリー](gsi/comparison_summary.json)、[取得履歴](gsi/download_manifest.json)、[取得指定](gsi/request.json)。取得ファイル名は1245281p.26o.gzと1245281p.26N.tar.gz。

保存済みデータからの再解析：プロジェクト直下で `python tools/process_gsi_ppk.py`。レポート更新は `python tools/document_gsi.py` → `python tools/build_html_reports.py`。取得処理は `tools/download_gsi.py` に保存したが、任意時間配布の公開期間後には同じダウンロード要求が利用できない場合があるため、再現には保存済み原本を使う。
'''
    append(R/'03_PPK/REPORT.md',text)
    # This standalone report uses paths relative to its own gsi directory.
    standalone=text.replace('(gsi/','(').replace('`gsi/','`').replace('[gsiフォルダ](gsi/)','[gsiフォルダ](./)')
    (R/'03_PPK/gsi/REPORT.md').write_text('# 国土地理院データによるPPK追加検証\n\n'+standalone,encoding='utf-8')
    append(R/'README.md','## 国土地理院データの追加検証\n\n明石Ａ（約8.81 km）の30秒間隔RINEXを取得し、同じ移動局RAWのPPKを再実行。地理院OBS＋NAVで360解（FLOAT 18、DGPS 342、FIX 0）。取得条件・比較・グラフは[③PPK詳細](03_PPK/REPORT.html)を参照。')

if __name__=='__main__':run()
