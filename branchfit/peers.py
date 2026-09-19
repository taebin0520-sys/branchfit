"""Peer 자치구 선정 (기획서 8절).

Peer의 정의를 오해하기 쉬우므로 다시 적어둡니다.
    Peer = '점포밀도가 비슷한 곳'이 아니라 '규모가 비슷한 비교지역'
    → 총인구 규모 percentile + 사업체 규모 percentile 의 거리로 찾습니다.
Peer는 추천지역·우수지역·열위지역이 아닙니다.
"""

from __future__ import annotations

import pandas as pd

from . import config

#: Peer 거리 계산에 쓰는 두 변수 (밀도 percentile이 아니라 '규모' percentile)
SIZE_COLUMNS = ["population_size_percentile", "business_size_percentile"]

#: 화면에 노출하는 Peer 컬럼 (기획서 8절: 이 3개만 표시)
DISPLAY_COLUMNS = ["region_name", "biz_per_1k", "biz_percentile"]


def find_peers(
    regions: pd.DataFrame,
    region_code: str,
    k: int = config.PEER_COUNT,
) -> pd.DataFrame:
    """region_code와 규모가 가장 유사한 자치구 k곳을 반환합니다.

    거리 = |총인구 규모 percentile 차| + |사업체 규모 percentile 차|
    """
    base_rows = regions.loc[regions["region_code"] == region_code]
    if base_rows.empty:
        raise KeyError(f"존재하지 않는 region_code: {region_code}")
    base = base_rows.iloc[0]

    # 자기 자신 제외 + 규모 percentile 결측 지역 제외 (기획서 8절)
    candidates = regions.loc[regions["region_code"] != region_code].dropna(
        subset=SIZE_COLUMNS
    ).copy()

    distance = sum(
        (candidates[col] - base[col]).abs() for col in SIZE_COLUMNS
    )

    # 부동소수점 오차로 동률이 깨지는 것을 막기 위해 고정 정밀도로 반올림.
    # 이 한 줄이 v2 QA에서 발견된 Peer 동률 불안정 문제의 수정 지점입니다.
    candidates["peer_distance"] = distance.round(config.PEER_DISTANCE_PRECISION)

    # 동률은 region_code 오름차순. kind="mergesort"는 안정 정렬이라
    # 같은 입력에 대해 항상 같은 순서를 보장합니다.
    ordered = candidates.sort_values(
        ["peer_distance", "region_code"], kind="mergesort"
    )
    return ordered.head(k).reset_index(drop=True)


def peers_for_display(peers: pd.DataFrame) -> pd.DataFrame:
    """화면 노출용 컬럼만 잘라냅니다."""
    return peers[DISPLAY_COLUMNS].copy()
