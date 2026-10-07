"""카카오 로컬 API 주소 → 좌표 변환 (실행 중 호출 전용).

규칙
- 좌표는 파일·저장소에 쓰지 않습니다. 메모리(dict)로만 다룹니다.
- API 키는 호출하는 쪽이 인자로 넘깁니다. 이 파일에는 키를 두지 않습니다.
- 키가 없거나 호출이 실패하거나 결과가 없으면 None 입니다. 추정 좌표는 만들지 않습니다.
- 네트워크 호출 함수(http_get)를 바꿔 끼울 수 있어, 테스트는 네트워크 없이 돌립니다.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Callable

import pandas as pd

KAKAO_ADDRESS_URL = "https://dapi.kakao.com/v2/local/search/address.json"
TIMEOUT_SEC = 5


def _default_http_get(url: str, headers: dict) -> dict:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=TIMEOUT_SEC) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


def geocode_address(
    address: str,
    api_key: str | None,
    http_get: Callable[[str, dict], dict] | None = None,
) -> tuple[float, float] | None:
    """주소 1건 → (위도, 경도). 실패하면 None."""
    if not api_key or not isinstance(address, str) or not address.strip():
        return None
    http_get = http_get or _default_http_get
    url = f"{KAKAO_ADDRESS_URL}?{urllib.parse.urlencode({'query': address.strip()})}"
    try:
        data = http_get(url, {"Authorization": f"KakaoAK {api_key}"})
        docs = data.get("documents") or []
        if not docs:
            return None
        # 카카오 응답: x = 경도, y = 위도
        return float(docs[0]["y"]), float(docs[0]["x"])
    except Exception:  # 네트워크·형식 오류는 모두 '좌표 없음'으로 처리
        return None


def geocode_branches(
    branches: pd.DataFrame,
    api_key: str | None,
    geocoder: Callable[[str, str | None], tuple[float, float] | None] | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> dict:
    """점포 표 전체를 변환합니다. 반환: {branch_id: (lat, lon) 또는 None}.

    address 컬럼이 없거나 키가 없으면 전부 None 입니다.
    """
    geocoder = geocoder or geocode_address
    result: dict = {}
    total = len(branches)
    has_address = "address" in branches.columns
    for i, row in enumerate(branches.itertuples(index=False), start=1):
        addr = getattr(row, "address", None) if has_address else None
        result[row.branch_id] = geocoder(addr, api_key) if addr else None
        if progress:
            progress(i, total)
    return result
