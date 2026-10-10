# ClipCatch への貢献

不具合の報告や改善の提案を歓迎します。

## 不具合の報告・提案

[Issues](https://github.com/myuto2490/ClipCatch/issues/new/choose) からテンプレートを選んでください。
不具合の場合は、アプリ下部の **ログ** を開いて内容を添えてもらえると原因を特定しやすくなります
（個人情報や Cookie が含まれていないか確認してから貼ってください）。

特定のサイトだけでダウンロードできない場合は、まず ClipCatch の右上のメニューから yt-dlp を最新版に
更新してみてください。それでも直らない場合は、[yt-dlp](https://github.com/yt-dlp/yt-dlp/issues) 側の
問題であることが多いです。

設計やリリース手順の詳細は Wiki の [アーキテクチャ](https://github.com/myuto2490/ClipCatch/wiki/アーキテクチャ)・
[ビルドとリリース](https://github.com/myuto2490/ClipCatch/wiki/ビルドとリリース) を参照してください。

## 開発の流れ

ブランチは次のように使います。

| ブランチ | 用途 |
| --- | --- |
| `main` | 公開済みのリリース。タグ `vX.Y.Z` はここに付ける |
| `develop` | 次のリリースに向けて統合するブランチ |
| `feature/*` | 機能の追加（`develop` から作り、`develop` へマージ） |
| `fix/*` | 不具合の修正 |
| `docs/*` | ドキュメントのみの変更 |
| `release/*` | リリースの準備（`develop` から作り、`main` と `develop` へマージ） |

1. `develop` から作業用のブランチを作る
2. 変更してテストを通す
3. `develop` に向けて Pull Request を作る

## 開発環境

```sh
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

Pull Request の前に次を確認してください（CI でも同じものを実行します）。

```sh
ruff check .
ruff format --check .
pytest
```

## コードの方針

- `core/` には Qt に依存しない処理だけを置き、単体テストを書く
- 画面に表示する文字列は `tr("日本語", "English")` で両方の言語を書く
- 色は `ui/theme.py` の役割（`label`・`secondary`・`separator` など）から選び、直接の色指定は避ける
- macOS と Windows の差は `core/platform.py` にまとめる
- コメントは「なぜそうするのか」を日本語で書く

## アイコンとスクリーンショット

```sh
python tools/make_icon.py      # アイコンを作り直す（icon.icns は macOS でのみ作成可能）
python tools/screenshots.py    # README のスクリーンショットを作り直す
```
