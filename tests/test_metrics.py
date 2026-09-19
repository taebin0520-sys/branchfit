"""지표 계산 테스트 (기획서 6~7절).

pandas가 설치된 환경에서 실행됩니다.
pandas 없이 돌리는 데이터 QA는 `python scripts/selfcheck.py` 를 쓰세요.
"""

from __future__ import annotations

import pandas as pd
import pytest

from branchfit import config, data, metrics


def test_percentile_rank_follows_spec_rule():
    """rank(method="min", pct=True) * 100 규칙 확인."""
    series = pd.Series([10, 20, 30, 40])
    result = metrics.percentile_rank(series).tolist()
    assert result == [25.0, 50.0, 75.0, 100.0]


def test_percentile_rank_ties_share_lowest_rank():
    """동률은 '더 낮은 순위'를 공유해야 합니다(재현성)."""
    series = pd.Series([10, 10, 30, 40])
    result = metrics.percentile_rank(series).tolist()
    assert result == [25.0, 25.0, 75.0, 100.0]


@pytest.mark.parametrize(
    "percentile,expected",
    [
        (4.0, config.LABEL_LOW),
        (30.0, config.LABEL_LOW),      # 경계 포함 (p<=30)
        (30.0001, config.LABEL_MID),
        (50.0, config.LABEL_MID),
        (69.9999, config.LABEL_MID),
        (70.0, config.LABEL_HIGH),     # 경계 포함 (p>=70)
        (100.0, config.LABEL_HIGH),
    ],
)
def test_label_boundaries_are_inclusive(percentile, expected):
    assert metrics.label_for(percentile) == expected


@pytest.mark.parametrize(
    "percentile,expected",
    [
        (27.9, False),
        (28.0, True),
        (32.0, True),
        (32.1, False),
        (50.0, False),
        (68.0, True),
        (72.0, True),
        (72.1, False),
    ],
)
def test_boundary_adjacent_band(percentile, expected):
    assert metrics.is_boundary_adjacent(percentile) is expected


def test_add_region_metrics_formulas():
    df = pd.DataFrame(
        [
            {
                "region_code": "11110",
                "region_name": "가구",
                "total_pop": 100_000,
                "elderly_pop": 20_000,
                "biz_count": 10_000,
                "ibk_branches": 5,
            },
            {
                "region_code": "11140",
                "region_name": "나구",
                "total_pop": 200_000,
                "elderly_pop": 30_000,
                "biz_count": 40_000,
                "ibk_branches": 4,
            },
        ]
    )
    out = metrics.add_region_metrics(df).set_index("region_name")

    # 5 / 10000 * 1000 = 0.5
    assert out.loc["가구", "biz_per_1k"] == pytest.approx(0.5)
    # 5 / 100000 * 10000 = 0.5
    assert out.loc["가구", "pop_per_10k"] == pytest.approx(0.5)
    assert out.loc["가구", "elderly_ratio"] == pytest.approx(20.0)
    # 4 / 40000 * 1000 = 0.1
    assert out.loc["나구", "biz_per_1k"] == pytest.approx(0.1)


def test_real_dataset_label_distribution_is_7_10_8():
    """기획서 14절 QA: 저밀도 7 / 중간 10 / 고밀도 8."""
    table = metrics.add_region_metrics(data.load_regions())
    assert metrics.label_distribution(table) == {
        config.LABEL_LOW: 7,
        config.LABEL_MID: 10,
        config.LABEL_HIGH: 8,
    }


def test_real_dataset_passes_integrity_checks():
    """25행 / IBK 182 / 자치구별 점포 수 일치."""
    regions, branches = data.load_all()
    assert len(regions) == config.EXPECTED_REGION_COUNT
    assert int(regions["ibk_branches"].sum()) == config.EXPECTED_BRANCH_TOTAL
    assert len(branches) == config.EXPECTED_BRANCH_TOTAL
