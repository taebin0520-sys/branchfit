"""Peer 선정 테스트 (기획서 8절)."""

from __future__ import annotations

import pandas as pd
import pytest

from branchfit import config, metrics, peers, pipeline


def sample_table() -> pd.DataFrame:
    """규모 percentile을 직접 지정한 최소 테이블.

    add_region_metrics를 거치지 않고 필요한 컬럼만 만들어,
    Peer 로직만 따로 검증합니다.
    """
    return pd.DataFrame(
        [
            # code,  pop_size_p, biz_size_p  → 기준(11110)과의 거리
            {"region_code": "11110", "region_name": "기준", "population_size_percentile": 50.0, "business_size_percentile": 50.0},
            {"region_code": "11140", "region_name": "가까움", "population_size_percentile": 52.0, "business_size_percentile": 51.0},  # 3
            {"region_code": "11170", "region_name": "동률A", "population_size_percentile": 55.0, "business_size_percentile": 50.0},  # 5
            {"region_code": "11200", "region_name": "동률B", "population_size_percentile": 45.0, "business_size_percentile": 50.0},  # 5
            {"region_code": "11230", "region_name": "멀다", "population_size_percentile": 10.0, "business_size_percentile": 90.0},  # 80
        ]
    )


def test_peer_distance_is_sum_of_two_size_percentile_gaps():
    result = peers.find_peers(sample_table(), "11110")
    assert result["peer_distance"].tolist() == [3.0, 5.0]


def test_peer_excludes_self():
    result = peers.find_peers(sample_table(), "11110")
    assert "11110" not in result["region_code"].tolist()


def test_peer_tie_breaks_by_region_code_ascending():
    """거리가 같으면 region_code가 작은 쪽이 먼저."""
    result = peers.find_peers(sample_table(), "11110", k=3)
    assert result["region_name"].tolist() == ["가까움", "동률A", "동률B"]
    # 동률A(11170) < 동률B(11200)
    assert result["region_code"].tolist()[1:] == ["11170", "11200"]


def test_peer_ignores_rows_with_missing_size_percentile():
    table = sample_table()
    table.loc[table["region_code"] == "11140", "population_size_percentile"] = None
    result = peers.find_peers(table, "11110")
    assert "11140" not in result["region_code"].tolist()


def test_peer_is_deterministic_regardless_of_input_order():
    """입력 행 순서를 뒤집어도 같은 Peer가 나와야 합니다."""
    table = pipeline.build_region_table()
    for code in table["region_code"]:
        forward = peers.find_peers(table, code)["region_code"].tolist()
        backward = peers.find_peers(
            table.iloc[::-1].reset_index(drop=True), code
        )["region_code"].tolist()
        assert forward == backward, code


def test_real_dataset_returns_two_peers_for_every_region():
    table = pipeline.build_region_table()
    for code in table["region_code"]:
        assert len(peers.find_peers(table, code)) == config.PEER_COUNT


def test_unknown_region_code_raises():
    with pytest.raises(KeyError):
        peers.find_peers(sample_table(), "99999")


def test_display_columns_are_limited_to_spec():
    """기획서 8절: 화면에는 region_name, biz_per_1k, biz_percentile만 표시."""
    table = pipeline.build_region_table()
    result = peers.peers_for_display(peers.find_peers(table, table.loc[0, "region_code"]))
    assert list(result.columns) == ["region_name", "biz_per_1k", "biz_percentile"]
