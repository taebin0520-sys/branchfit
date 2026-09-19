"""결정론적 지역 맥락 지표 계산 (기획서 6~7절).

이 모듈의 계약:
    같은 입력 CSV → 항상 같은 출력.
    난수·시간·외부호출·LLM이 전혀 개입하지 않습니다.
AI는 여기서 나온 값을 '설명'만 하고, 절대 다시 계산하지 않습니다.
"""

from __future__ import annotations

import pandas as pd

from . import config


def percentile_rank(series: pd.Series) -> pd.Series:
    """기획서 7.2에 고정된 percentile 규칙.

        Series.rank(method="min", pct=True, ascending=True) * 100

    method="min"을 쓰는 이유: 동률일 때 '더 낮은 순위'를 함께 부여해
    누가 먼저 정렬되었는지에 따라 값이 흔들리지 않게 합니다(재현성).
    """
    return series.rank(method="min", pct=True, ascending=True) * 100


def label_for(percentile: float) -> str:
    """상대 라벨 3구간 (기획서 7.2).

    30/70은 통계기관·금융당국 기준이 아니라 BranchFit의 UI 표현 기준입니다.
    """
    if percentile <= config.LOW_PERCENTILE:
        return config.LABEL_LOW
    if percentile >= config.HIGH_PERCENTILE:
        return config.LABEL_HIGH
    return config.LABEL_MID


def is_boundary_adjacent(percentile: float) -> bool:
    """경계 인접 여부 (기획서 7.3). 28~32 또는 68~72.

    경고가 아니라 '경계에 가까우니 해석에 주의' 라는 중립 신호입니다.
    """
    band = config.BOUNDARY_BAND
    near_low = config.LOW_PERCENTILE - band <= percentile <= config.LOW_PERCENTILE + band
    near_high = (
        config.HIGH_PERCENTILE - band <= percentile <= config.HIGH_PERCENTILE + band
    )
    return bool(near_low or near_high)


def add_region_metrics(regions: pd.DataFrame) -> pd.DataFrame:
    """지역 데이터에 파생지표·percentile·라벨·판정 플래그를 붙입니다."""
    df = regions.copy()

    # --- 기획서 7.1 주지표 / 보조지표 ---------------------------------
    # 주지표를 사업체 기준으로 삼는 이유: 자치구별 사업체 규모 차이가 커서
    # 영업점 '개수' 자체를 그대로 비교하면 규모가 큰 자치구가 항상 많아 보입니다.
    df["biz_per_1k"] = df["ibk_branches"] / df["biz_count"] * 1000
    df["pop_per_10k"] = df["ibk_branches"] / df["total_pop"] * 10000

    # 인구구조 프로필 (판정에는 쓰지 않고 맥락 정보로만 표시)
    df["elderly_ratio"] = df["elderly_pop"] / df["total_pop"] * 100

    # --- 기획서 7.2 percentile -----------------------------------------
    df["biz_percentile"] = percentile_rank(df["biz_per_1k"])
    df["pop_percentile"] = percentile_rank(df["pop_per_10k"])

    # Peer 선정용 '규모' percentile. 위 밀도 percentile과 완전히 다른 변수입니다.
    # (기획서 8절: 밀도가 비슷한 곳이 아니라 규모가 비슷한 곳을 찾는 것이 목적)
    df["population_size_percentile"] = percentile_rank(df["total_pop"])
    df["business_size_percentile"] = percentile_rank(df["biz_count"])

    # --- 라벨 / 판정 플래그 --------------------------------------------
    # 반올림하지 않은 원 percentile로 판정합니다 (기획서 7.1 마지막 문장).
    df["biz_density_label"] = df["biz_percentile"].map(label_for)
    df["pop_density_label"] = df["pop_percentile"].map(label_for)

    df["boundary_adjacent"] = df["biz_percentile"].map(is_boundary_adjacent)
    df["density_label_conflict"] = (
        df["biz_density_label"] != df["pop_density_label"]
    )

    return df.sort_values("region_code").reset_index(drop=True)


def label_distribution(df: pd.DataFrame) -> dict[str, int]:
    """상대 라벨 분포. 기획서 14절 QA에서 저밀도 7 / 중간 10 / 고밀도 8 확인용.

    참고: 25개 지역의 biz_per_1k가 모두 서로 다르면 이 분포는
    percentile 규칙상 항상 7/10/8이 됩니다.
    (rank 1~7 → p<=28, 8~17 → 32~68, 18~25 → p>=72)
    따라서 이 값이 달라졌다면 '동률 발생' 또는 '데이터 행 수 변경'을 의미합니다.
    """
    counts = df["biz_density_label"].value_counts().to_dict()
    return {
        config.LABEL_LOW: int(counts.get(config.LABEL_LOW, 0)),
        config.LABEL_MID: int(counts.get(config.LABEL_MID, 0)),
        config.LABEL_HIGH: int(counts.get(config.LABEL_HIGH, 0)),
    }
