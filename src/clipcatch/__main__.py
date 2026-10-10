"""`python -m clipcatch` とパッケージ版の起動口。"""

import sys


def main() -> int:
    from clipcatch.app import run

    return run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
