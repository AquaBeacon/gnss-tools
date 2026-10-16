# gnss-tools

NEO-F9P受信機・RTK/PPK検証。

python -m pip install -r tools/requirements.txt でPython依存を導入します。tools/verify_receiver.py --help で引数を確認します。実測スクリプトには受信機操作・ネットワーク接続があるため、用途を確認して実行します。

- [tools/requirements.txt](tools/requirements.txt)
- [tools/verify_receiver.py](tools/verify_receiver.py)

## 開発とライセンス

[開発ガイド](DEVELOPMENT.md)にセットアップ・入口・確認方法をまとめています。自作部分は [Apache License 2.0](LICENSE)。[第三者素材・依存の扱い](THIRD_PARTY.md)も参照してください。
