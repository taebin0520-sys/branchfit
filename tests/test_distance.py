"""거리 계산 뼈대 테스트. 좌표는 테스트용 가상 값입니다(실제 점포 아님)."""

import pandas as pd
import pytest

from branchfit.distance import distance_text, haversine_km, nearest_other_branch


def _df(rows):
    return pd.DataFrame(
        rows, columns=["branch_id", "branch_name", "lat", "lon", "coord_status"]
    )


def test_haversine_zero():
    assert haversine_km(37.5, 127.0, 37.5, 127.0) == 0


def test_haversine_one_degree_latitude():
    # 위도 1도 ≈ 111.2km
    assert haversine_km(37.0, 127.0, 38.0, 127.0) == pytest.approx(111.2, abs=0.2)


def test_excludes_self_and_picks_nearest():
    df = _df([
        ["A", "가점", 37.50, 127.00, "ok"],
        ["B", "나점", 37.51, 127.00, "ok"],
        ["C", "다점", 37.60, 127.00, "ok"],
    ])
    r = nearest_other_branch(df, "A")
    assert r["branch_id"] == "B"


def test_selected_branch_without_coord_returns_none():
    df = _df([
        ["A", "가점", None, None, "missing"],
        ["B", "나점", 37.51, 127.00, "ok"],
    ])
    assert nearest_other_branch(df, "A") is None
    assert "좌표 미확인" in distance_text(None)


def test_missing_candidates_are_skipped():
    df = _df([
        ["A", "가점", 37.50, 127.00, "ok"],
        ["B", "나점", None, None, "missing"],
        ["C", "다점", 37.60, 127.00, "ok"],
    ])
    assert nearest_other_branch(df, "A")["branch_id"] == "C"


def test_tie_breaks_by_branch_id():
    df = _df([
        ["A", "가점", 37.50, 127.00, "ok"],
        ["C", "다점", 37.51, 127.00, "ok"],
        ["B", "나점", 37.49, 127.00, "ok"],
    ])
    assert nearest_other_branch(df, "A")["branch_id"] == "B"


def test_text_has_no_forbidden_words():
    text = distance_text({"branch_id": "B", "branch_name": "나점", "distance_km": 0.5})
    for word in ["대체", "폐쇄", "통합"]:
        assert word not in text
