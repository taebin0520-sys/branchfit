"""최근접 IBK 영업점 거리 계산 (뼈대).

- 좌표는 공식 주소를 변환한 값만 사용합니다. 추정 좌표는 넣지 않습니다.
- 좌표가 없는 점포(coord_status != "ok")는 계산에서 빠집니다.
- 화면 문구는 거리와 점포명만 담습니다. 판단·권고성 표현은 쓰지 않습니다.
"""

from __future__ import annotations

import math

import pandas as pd

EARTH_RADIUS_KM = 6371.0088


def valid_coordinates(lat, lon) -> bool:
    try:
        lat, lon = float(lat), float(lon)
        return math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180
    except (TypeError, ValueError, OverflowError):
        return False


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """두 좌표 사이의 직선거리(km). 지구를 구로 보고 계산합니다."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def nearest_other_branch(branches: pd.DataFrame, branch_id: str) -> dict | None:
    """선택 점포에서 가장 가까운 다른 IBK 영업점을 찾습니다.

    반환값: {"branch_id", "branch_name", "distance_km"} 또는
            선택 점포 좌표가 없거나 비교할 점포가 없으면 None.
    동일 거리면 branch_id 오름차순으로 고릅니다.
    """
    required = {"coord_status", "lat", "lon", "branch_id", "branch_name"}
    if not required.issubset(branches.columns):
        return None
    valid = [valid_coordinates(r.lat, r.lon) for r in branches.itertuples()]
    ok = branches[(branches["coord_status"] == "ok") & pd.Series(valid, index=branches.index)]
    me = ok[ok["branch_id"] == branch_id]
    if me.empty:
        return None  # 선택 점포 좌표 미확인

    lat, lon = float(me.iloc[0]["lat"]), float(me.iloc[0]["lon"])
    others = ok[ok["branch_id"] != branch_id].copy()
    if others.empty:
        return None

    others["distance_km"] = [
        haversine_km(lat, lon, float(r.lat), float(r.lon)) for r in others.itertuples()
    ]
    # 부동소수점 흔들림 방지: 고정 정밀도로 반올림한 뒤 정렬
    others["distance_km"] = others["distance_km"].round(6)
    best = others.sort_values(["distance_km", "branch_id"]).iloc[0]
    return {
        "branch_id": best["branch_id"],
        "branch_name": best["branch_name"],
        "distance_km": round(float(best["distance_km"]), 2),
    }


def distance_text(result: dict | None) -> str:
    """화면 표시용 고정 문구."""
    if result is None:
        return "가장 가까운 다른 IBK 영업점: 좌표 미확인"
    return (
        f"가장 가까운 다른 IBK 영업점: {result['branch_name']} · "
        f"{result['distance_km']:.2f}km (직선거리)"
    )


LIMIT_NOTE = "IBK 영업점만 반영, 타행 제외, 직선거리(실제 이동거리 아님)"


def attach_coords(branches: pd.DataFrame, coords: dict) -> pd.DataFrame:
    """{branch_id: (lat, lon) 또는 None} 를 점포 표에 붙인 사본을 돌려줍니다.

    값이 None이거나 dict에 없는 점포는 coord_status="missing" 입니다.
    원본 표는 바꾸지 않습니다.
    """
    out = branches.copy()
    lats, lons, status = [], [], []
    for bid in out["branch_id"]:
        pair = coords.get(bid)
        if not isinstance(pair, (tuple, list)) or len(pair) != 2 or not valid_coordinates(*pair):
            lats.append(None)
            lons.append(None)
            status.append("missing")
        else:
            lats.append(float(pair[0]))
            lons.append(float(pair[1]))
            status.append("ok")
    out["lat"], out["lon"], out["coord_status"] = lats, lons, status
    return out
