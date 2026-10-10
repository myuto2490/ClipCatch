# セキュリティポリシー

## 対象バージョン

最新のリリースのみ修正の対象です。

## 脆弱性の報告

脆弱性を見つけた場合は、公開の Issue ではなく GitHub の
[Private vulnerability reporting](https://github.com/myuto2490/ClipCatch/security/advisories/new) から報告してください。
内容を確認し、できるだけ早く対応します。

## ClipCatch の安全への配慮

- yt-dlp・ffmpeg・Deno・aria2c は各プロジェクトの公式配布物からのみ取得します
- yt-dlp は公式の SHA-256 チェックサムと照合し、一致しない場合は使いません
- 取得したツールはユーザーのデータフォルダに置き、アプリ本体は書き換えません
- 通信は OS の TLS 実装と証明書ストアを使います
