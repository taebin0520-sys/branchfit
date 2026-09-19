"""데이터 → 지표 → Peer → AI 입력 → 브리핑을 한 줄로 잇는 조립 모듈.

각 모듈은 자기 일만 하고, 순서를 아는 것은 이 파일 하나뿐입니다.
화면(app.py)과 테스트가 모두 이 함수들만 호출하게 해서
'화면에서 본 값'과 '테스트한 값'이 같은 경로로 나오도록 만듭니다.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from . import briefing as briefing_mod
from . import contract as contract_mod
from . import data, metrics, peers


def build_region_table() -> pd.DataFrame:
    """지역 데이터 + 파생지표 테이블."""
    regions = data.load_regions()
    return metrics.add_region_metrics(regions)


def build_tables() -> tuple[pd.DataFrame, pd.DataFrame]:
    """(지표 포함 지역 테이블, 점포 테이블). 정합성 검증까지 통과한 결과."""
    regions, branches = data.load_all()
    return metrics.add_region_metrics(regions), branches


def build_contract_for_branch(
    region_table: pd.DataFrame,
    branch_table: pd.DataFrame,
    branch_id: str,
) -> dict[str, Any]:
    """점포 1건 → AI 입력 JSON."""
    rows = branch_table.loc[branch_table["branch_id"] == branch_id]
    if rows.empty:
        raise KeyError(f"존재하지 않는 branch_id: {branch_id}")
    branch = rows.iloc[0].to_dict()

    region_rows = region_table.loc[
        region_table["region_code"] == branch["region_code"]
    ]
    if region_rows.empty:
        raise KeyError(f"소속 자치구 데이터 없음: {branch['region_code']}")
    region = region_rows.iloc[0].to_dict()

    peer_rows = peers.find_peers(region_table, branch["region_code"])

    return contract_mod.build_contract(
        branch=branch,
        region=region,
        peers=peer_rows.to_dict(orient="records"),
    )


def build_briefing_for_branch(
    region_table: pd.DataFrame,
    branch_table: pd.DataFrame,
    branch_id: str,
    *,
    llm_caller=None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """(contract, briefing 결과) 를 함께 반환합니다.

    화면에서 '근거(JSON)'와 '브리핑'을 나란히 보여주려면 둘 다 필요합니다.
    """
    contract = build_contract_for_branch(region_table, branch_table, branch_id)
    outcome = briefing_mod.generate_briefing(contract, llm_caller=llm_caller)
    return contract, outcome
