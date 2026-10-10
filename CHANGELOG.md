# Changelog

このプロジェクトの変更点を記録します。書式は [Keep a Changelog](https://keepachangelog.com/ja/1.1.0/) に、
バージョンは [Semantic Versioning](https://semver.org/lang/ja/) に従います。
1.0.0 に達するまでは、マイナーバージョン（0.x）の更新で設定や動作が変わることがあります。

## [Unreleased]

### Added

- 設定で表示する言語（システムに合わせる / 日本語 / English）を選べるようにした

## [0.1.0] - 2026-10-10

最初の公開版です。[VideoDownloader](https://github.com/myuto2490/VideoDownloader) の macOS 版（Swift）の機能を
引き継ぎ、Python と Qt で macOS と Windows の両方に対応させました。

### Added

- URL を入れると、サムネイル・タイトル・投稿者・再生時間をカードで表示
- 形式（MP4 / 最高画質 / MP3 / M4A）と最大解像度（4K〜480p）の選択
- 進捗・転送量・速度・残り時間・後処理の段階の表示とキャンセル
- yt-dlp・ffmpeg・Deno の自動取得と、yt-dlp のチェックサム検証・更新
- aria2c による多重接続の高速化（macOS は Homebrew、Windows は公式リリースから導入）
- 保存後の映像の途切れの検査
- ブラウザの Cookie の利用、プレイリストの一括保存、yt-dlp の個人設定ファイルの読み込み
- クリップボードの URL の自動入力、ドラッグ＆ドロップ、キーボードショートカット
- 背面にいるときの完了通知、ClipCatch 自身の更新の確認
- ライト／ダークとアクセントカラーへの追従、日本語と英語の表示
- macOS 用 .dmg（Apple シリコン / Intel）と Windows 用インストーラ・ポータブル版

[Unreleased]: https://github.com/myuto2490/ClipCatch/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/myuto2490/ClipCatch/releases/tag/v0.1.0
