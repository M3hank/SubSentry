"""Allow running SubSentry as: python -m subsentry"""

import sys

from subsentry.cli import main

if __name__ == "__main__":
    sys.exit(main())
