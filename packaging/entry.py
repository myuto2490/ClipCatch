"""PyInstaller が実行ファイルの起点にするスクリプト。"""

import sys

from clipcatch.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
