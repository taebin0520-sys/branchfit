"""pytest가 프로젝트 루트를 import 경로에 넣도록 합니다.

이렇게 해두면 `pytest` 를 프로젝트 루트에서 그냥 실행해도
`from branchfit import ...` 가 동작합니다. (별도 설치 불필요)
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
