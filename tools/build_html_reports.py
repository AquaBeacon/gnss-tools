"""Create offline HTML reports with embedded graphs from saved Markdown evidence."""
import base64
import html
import os
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.deps'))
import markdown

R = ROOT / 'reports'
CSS = '''
:root{color-scheme:light;--ink:#202c38;--muted:#5d6a77;--line:#dce3e8;--green:#126650;--amber:#835408}
*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:90px}
body{margin:0;background:#f3f6f7;color:var(--ink);font:16px/1.85 -apple-system,BlinkMacSystemFont,"Segoe UI","Yu Gothic",Meiryo,sans-serif}
a{color:#176b80;text-underline-offset:3px}a:hover{color:#104b5b}
.wrap{max-width:1160px;margin:auto;padding:38px 28px 70px}
.eyebrow{color:var(--green);font-size:12px;letter-spacing:.13em;font-weight:700}
h1{font-size:clamp(27px,4vw,40px);line-height:1.45;letter-spacing:-.02em;margin:10px 0 16px}
h2{font-size:25px;line-height:1.6;margin:0 0 18px}h3{font-size:20px;margin:30px 0 12px}
p{margin:12px 0}.meta,.caption{color:var(--muted);font-size:14px}
nav{position:sticky;top:0;z-index:3;background:#ffffffed;border-bottom:1px solid var(--line);backdrop-filter:blur(10px)}
nav .inner{max-width:1160px;margin:auto;display:flex;gap:24px;padding:14px 28px;flex-wrap:wrap}nav a{font-size:14px;text-decoration:none;font-weight:650}
.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin:28px 0}
.card{background:white;border:1px solid var(--line);border-radius:12px;padding:22px}.card strong{display:block;font-size:18px;margin:6px 0}
.pill{display:inline-block;font-size:12px;line-height:1.7;border-radius:5px;padding:3px 9px;background:#e6f2ed;color:var(--green);font-weight:700}.pill.warn{background:#fff1da;color:var(--amber)}
.notice{border-left:4px solid #c18830;background:#fff6e8;padding:16px 20px;margin:24px 0;border-radius:0 8px 8px 0}
section{background:white;border:1px solid var(--line);border-radius:14px;padding:32px;margin:30px 0}
.sectionhead{display:flex;align-items:flex-start;justify-content:space-between;gap:20px}.sectionhead a{white-space:nowrap;font-size:13px}
figure{margin:22px 0;border:1px solid var(--line);border-radius:10px;overflow:hidden;background:#fff}
figure img{display:block;width:100%;height:auto}figcaption{padding:12px 16px;background:#f7f9fa;border-top:1px solid var(--line);font-size:14px;color:var(--muted)}
.tablewrap{overflow-x:auto;margin:18px 0}table{border-collapse:collapse;width:100%;font-size:14px;line-height:1.75}th,td{padding:12px 14px;border:1px solid var(--line);vertical-align:top;text-align:left}th{background:#edf3f5;font-weight:700}tr:nth-child(even) td{background:#fafcfc}
code{font-family:Consolas,monospace;font-size:.87em;background:#edf2f5;padding:2px 5px;border-radius:4px;overflow-wrap:anywhere}
pre{padding:18px;overflow:auto;background:#edf2f5;border-radius:8px}pre code{padding:0}
ul{padding-left:24px}li{margin:7px 0;overflow-wrap:anywhere}details{margin:22px 0;border-top:1px solid var(--line);padding-top:16px}summary{cursor:pointer;color:var(--muted);font-weight:650}
footer{font-size:13px;color:var(--muted);border-top:1px solid var(--line);padding-top:20px}
@media(max-width:760px){.wrap{padding:24px 14px 40px}.cards{grid-template-columns:1fr}section{padding:20px 16px}.sectionhead{display:block}nav .inner{gap:10px 18px;padding:10px 14px}th,td{padding:9px;min-width:85px}}
@media print{body{background:white;font-size:11px}nav,.sectionhead a{display:none}.wrap{max-width:none;padding:0}.cards{gap:8px}.card,section{break-inside:auto;border-color:#ccc;box-shadow:none}section{padding:16px;margin:20px 0;break-before:page}figure{break-inside:avoid}h2,h3{break-after:avoid}a{color:inherit}details{display:none}figcaption{font-size:10px}}
'''

SECTIONS = [
    {'folder': '01_Basic', 'id': 'basic', 'title': '① 基本動作・設定',
     'status': '基本動作を確認', 'summary': 'USB通信・衛星受信・更新周期設定・GNSS時刻を確認。高頻度出力に一部欠測。PPS端子波形は未検証。',
     'figures': [
         ('cn0.png', '衛星信号強度：初期実機試験のC/N0。窓際条件での記録です。'),
         ('update_intervals.png', '通常出力での更新間隔。1/5/10 Hz設定と一部の欠測を確認。'),
         ('update_intervals_lean.png', '出力を減らした再試験。欠測は改善しましたが、完全には解消していません。')],
     'extra': [('receiver_overview.png', '初期試験の衛星数・解状態・水平精度推定値。RTK区間は437 km離れた初期補正源の試験です。')]},
    {'folder': '02_RTK', 'id': 'rtk', 'title': '② RTK測位',
     'status': 'FLOAT確認・FIX未達', 'summary': '約7.5 kmの無料基準局を使用。60秒のNTRIP切断と再接続を実施し、約0.77秒でFLOATへ復帰。',
     'figures': [('nearby_states.png', '近傍局でのRTK状態。180秒接続 → 60秒切断 → 120秒再接続。リアルタイムFIXは未達。')],
     'extra': [('ntrip_capture.png', '初期AITOYA配信のPC側受信量とRTCM種別。近傍局の測位結果とは別の試験です。'), ('rtk_states.png', '437 km離れた初期補正源での記録。計画的な切断・復帰試験の評価には用いていません。')]},
    {'folder': '03_PPK', 'id': 'ppk', 'title': '③ PPK用データ保存・解析',
     'status': '地理院データでも解析済み', 'summary': '切断中もRAW記録を継続。従来局に加え地理院・明石ＡでPPKを実行。地理院OBS＋NAVは360解（FLOAT 18・DGPS 342・FIX 0）。',
     'figures': [('nearby_raw_continuity.png', '近傍局のRTK試験中のRAW保存。60秒切断中もRAWXを60エポック記録。'), ('ppk_results.png', 'PPK結果：FLOAT 356点・FIX判定3点・DGPS 1点。変位は平均位置からのばらつきで、絶対誤差ではありません。')],
     'extra': [('base_observations.png', '初期AITOYA配信から変換した基準局RINEX。近傍局PPKの入力には使用していません。'), ('raw_continuity.png', '初期試験のRAW保存状況。出力過多となった10 Hz区間の欠測を含みます。')]},
]
SECTIONS[2]['figures'] += [
    ('gsi/gsi_quality_comparison.png', '地理院データの追加解析4通り。従来局の30秒比較も併記。FIXはいずれも0点。条件と出力解数は本文参照。'),
    ('gsi/gsi_position_age.png', '地理院OBS＋地理院NAVの位置ばらつきと観測時刻差。中央値を原点とし、絶対誤差を示すものではありません。')]

def figure(folder, filename, caption):
    path = R / folder / filename
    encoded = base64.b64encode(path.read_bytes()).decode('ascii')
    return f'<figure><img src="data:image/png;base64,{encoded}" alt="{html.escape(caption, quote=True)}"><figcaption>{html.escape(caption)}</figcaption></figure>'

def body_from_markdown(source, output, text_override=None, omit_common=False):
    text = source.read_text(encoding='utf-8') if text_override is None else text_override
    if omit_common:
        text = re.sub(r'## 共通の前提条件・使用環境.*?(?=## (?:この試験|RTK試験|(?:従来局の)?解析に使用))', '', text, flags=re.S)
    # Display the recorded numeric results without Python nulls or excessive digits.
    text = text.replace('None 秒', '未評価').replace('None（nullは未達）', '未達').replace('None。', '未評価。')
    text = text.replace('算出不能としてnullにした', '算出不能として未評価にした')
    text = re.sub(r'(?<![\w.])(\d+\.\d{6,})(?![\w.])', lambda m: f'{float(m[1]):.2f}', text)
    text = text.replace("{'': True, 'rates_lean': True, 'nearby': True}", '初期試験・周期再試験・近傍局試験のすべてで一致')
    text = text.replace("{'4': 1, '2': 356, '1': 3}", 'DGPS 1、FLOAT 356、FIX判定 3')
    # Markdown requires blank lines before lists; normalize existing source layout.
    text = re.sub(r'(?m)([^\n])\n(?=- )', r'\1\n\n', text)
    text = '\n'.join(text.splitlines()[1:])
    rendered = markdown.markdown(text, extensions=['tables', 'fenced_code', 'sane_lists'])
    rendered = re.sub(r'<(/?)h2>', r'<\1h3>', rendered)
    def link(match):
        target = html.unescape(match[1])
        if target.startswith(('https:', 'http:', '#')):
            return match[0]
        relative = os.path.relpath(source.parent / target, output.parent).replace('\\', '/')
        return 'href="' + html.escape(relative, quote=True) + '"'
    rendered = re.sub(r'href="([^"]+)"', link, rendered)
    return rendered.replace('<table>', '<div class="tablewrap"><table>').replace('</table>', '</table></div>')

def section(spec, output):
    folder = spec['folder']
    link = os.path.relpath(R / folder / 'REPORT.html', output.parent).replace('\\', '/')
    heading = f'<div class="sectionhead"><h2>{spec["title"]}</h2><a href="{link}">分類別HTMLを開く ↗</a></div>' if output.name == 'index.html' else f'<h2>{spec["title"]}</h2>'
    charts = ''.join(figure(folder, *f) for f in spec['figures'])
    extra = '<details><summary>初期試験・補足グラフを見る</summary>' + ''.join(figure(folder, *f) for f in spec['extra']) + '</details>'
    return f'<section id="{spec["id"]}">{heading}<p>{spec["summary"]}</p>{charts}<h3>検証条件・詳細結果</h3>{body_from_markdown(R / folder / "REPORT.md", output, omit_common=output.name == "index.html")}{extra}</section>'

def document(title, main, output):
    root = os.path.relpath(R / 'index.html', output.parent).replace('\\', '/')
    nav = f'<nav aria-label="レポート目次"><div class="inner"><a href="{root}">全体レポート</a>'
    nav += f'<a href="{root}#conditions">使用環境・前提条件</a>' + ''.join(f'<a href="{root}#{s["id"]}">{s["title"]}</a>' for s in SECTIONS) + '</div></nav>'
    return f'<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title><style>{CSS}</style></head><body>{nav}<main class="wrap"><header><div class="eyebrow">NEO-F9P / MEASUREMENT REPORT</div><h1>{html.escape(title)}</h1><p class="meta">2026年10月9日（JST） · NEO-F9P / HPGL1L5 1.40 · USB COM7 · アンテナ：窓際</p></header>{main}<footer>グラフ画像はHTML内に埋め込み済み。ネット接続なしで閲覧できます。CSV・UBX・RINEX・解析ログへのリンクを使う際は、reportsフォルダ一式を保存してください。<br>記録内容の出典と実行条件は各レポート本文に記載。既知点との比較による絶対位置精度の検証は行っていません。</footer></main></body></html>'

class Checker(HTMLParser):
    def __init__(self, path):
        super().__init__(); self.path = path; self.images = 0
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'img':
            assert attrs['src'].startswith('data:image/png;base64,')
            data = base64.b64decode(attrs['src'].split(',', 1)[1], validate=True)
            assert data.startswith(b'\x89PNG\r\n\x1a\n'); self.images += 1
        if tag == 'a':
            href = attrs['href'].split('#')[0]
            if href and not href.startswith(('https:', 'http:')):
                assert (self.path.parent / href).exists(), href

def run():
    output = R / 'index.html'
    cards = '<div class="cards">' + ''.join(f'<div class="card"><span class="pill {"warn" if s["id"] != "basic" else ""}">{s["status"]}</span><strong><a href="#{s["id"]}">{s["title"]}</a></strong><p>{s["summary"]}</p></div>' for s in SECTIONS) + '</div>'
    notice = '<div class="notice"><strong>全項目の合格を確認したものではありません。</strong><br>リアルタイムFIXは未達。PPKの短いFIX判定も安定した正しいFIXとは認定していません。PPS端子波形は未検証です。受信機設定は全試験後に復元し、読み戻し一致を確認しました。</div>'
    readme = (R / 'README.md').read_text(encoding='utf-8')
    conditions = ''
    if '<!-- verification-conditions:start -->' in readme:
        common = readme.split('<!-- verification-conditions:start -->', 1)[1].split('<!-- verification-conditions:end -->', 1)[0]
        conditions = '<section id="conditions"><h2>使用環境・前提条件</h2>' + body_from_markdown(R / 'README.md', output, text_override='# Conditions\n' + common) + '</section>'
    output.write_text(document('RTK-GNSS 動作検証レポート', cards + notice + conditions + ''.join(section(s, output) for s in SECTIONS), output), encoding='utf-8')
    paths = [output]
    for spec in SECTIONS:
        target = R / spec['folder'] / 'REPORT.html'
        target.write_text(document(spec['title'] + ' — 実機検証レポート', section(spec, target), target), encoding='utf-8'); paths.append(target)
    target = R / '03_PPK/gsi/REPORT.html'
    charts = ''.join(figure('03_PPK', *f) for f in SECTIONS[2]['figures'][-2:])
    target.write_text(document('国土地理院データによるPPK追加検証', '<section>'+charts+body_from_markdown(target.with_suffix('.md'), target)+'</section>', target), encoding='utf-8')
    paths.append(target)
    for path in paths:
        checker = Checker(path); checker.feed(path.read_text(encoding='utf-8'))
        assert checker.images > 0
        print(f'PASS {path.relative_to(ROOT)}: {checker.images} embedded graphs, links checked')

if __name__ == '__main__':
    run()
