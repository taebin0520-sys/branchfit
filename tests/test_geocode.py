"""지오코딩 테스트. 네트워크를 쓰지 않고 가짜 응답만 사용합니다."""

import pandas as pd

from branchfit.distance import attach_coords, distance_text, nearest_other_branch
from branchfit.geocode import geocode_address, geocode_branches


def test_no_key_returns_none_without_calling_network():
    def boom(url, headers):
        raise AssertionError("네트워크 호출이 일어나면 안 됩니다")

    assert geocode_address("서울 중구 가", None, http_get=boom) is None


def test_parses_kakao_response_x_is_lon():
    fake = lambda url, headers: {"documents": [{"x": "127.01", "y": "37.55"}]}
    assert geocode_address("서울 중구 가", "KEY", http_get=fake) == (37.55, 127.01)


def test_empty_result_and_errors_become_none():
    assert geocode_address("a", "KEY", http_get=lambda u, h: {"documents": []}) is None

    def raises(url, headers):
        raise OSError("timeout")

    assert geocode_address("a", "KEY", http_get=raises) is None


def test_geocode_branches_without_address_column_is_all_none():
    df = pd.DataFrame({"branch_id": ["A", "B"], "branch_name": ["가", "나"]})
    assert geocode_branches(df, "KEY") == {"A": None, "B": None}


def test_end_to_end_with_mock_and_missing_selected():
    df = pd.DataFrame({
        "branch_id": ["A", "B", "C"],
        "branch_name": ["가점", "나점", "다점"],
        "address": ["a", "b", "c"],
    })
    table = {"a": (37.50, 127.0), "b": (37.51, 127.0), "c": None}
    coords = geocode_branches(df, "KEY", geocoder=lambda addr, key: table[addr])
    full = attach_coords(df, coords)
    assert full["coord_status"].tolist() == ["ok", "ok", "missing"]
    assert nearest_other_branch(full, "A")["branch_id"] == "B"
    assert distance_text(nearest_other_branch(full, "C")) .endswith("좌표 미확인")
