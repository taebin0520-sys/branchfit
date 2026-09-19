"""검토 사유 / notable indicator / 추가 확인 필요영역 선정 (기획서 9절).

역할 분담이 핵심입니다.
    코드  : '어떤 사유를 보여줄지' 결정 (여기)
    AI    : 그 사유를 읽기 쉬운 문장으로 재구성 (briefing.py)
AI가 사유 자체를 만들어내면 근거 추적이 불가능해지므로,
사유는 config.REVIEW_REASONS에 있는 고정 상수에서만 고릅니다.
"""

from __future__ import annotations

from typing import Any

from . import config


def select_notable_indicator(result: dict[str, Any]) -> str:
    """가장 먼저 짚어야 할 신호 1개를 결정론적 우선순위로 고릅니다.

    우선순위 근거:
      1) 지표 충돌  - 두 관점이 엇갈리므로 해석 주의가 가장 필요
      2) 경계 인접  - 라벨이 구간 경계에 걸쳐 있어 라벨만 믿으면 위험
      3) 저/고밀도  - 중간 구간보다 설명할 내용이 분명함
      4) 중간       - 위 신호가 모두 없을 때
    """
    if result["density_label_conflict"]:
        return "NI-CONFLICT"
    if result["boundary_adjacent"]:
        return "NI-BOUNDARY"
    if result["biz_density_label"] == config.LABEL_LOW:
        return "NI-BIZ-LOW"
    if result["biz_density_label"] == config.LABEL_HIGH:
        return "NI-BIZ-HIGH"
    return "NI-BIZ-MID"


def select_review_reasons(result: dict[str, Any]) -> list[str]:
    """표시할 검토 사유 ID 목록을 고릅니다 (고정 상수 중에서만 선택)."""
    reasons: list[str] = []

    # 사업체 기준 상대 라벨 → RR-01/02/03 중 하나
    label_to_id = {
        config.LABEL_LOW: "RR-01",
        config.LABEL_MID: "RR-02",
        config.LABEL_HIGH: "RR-03",
    }
    reasons.append(label_to_id[result["biz_density_label"]])

    if result["density_label_conflict"]:
        reasons.append("RR-04")
    if result["boundary_adjacent"]:
        reasons.append("RR-05")

    # RR-06(기준시점 상이), RR-07(자치구 단위 지표)은 항상 노출합니다.
    # P0의 가장 중요한 한계라서 상황에 따라 숨기지 않습니다.
    reasons.append("RR-06")
    reasons.append("RR-07")
    return reasons


def select_next_internal_data_candidates() -> list[str]:
    """외부데이터로 확인 불가한 추가 확인 필요영역 (기획서 11절).

    P0에서는 3개 항목을 항상 모두 노출합니다.
    '이번엔 해당 없음'으로 숨길 수 있게 만들면
    담당자가 한계를 못 보고 넘어갈 수 있기 때문입니다.
    """
    return list(config.NEXT_INTERNAL_DATA_CANDIDATES.keys())


def expand(ids: list[str], catalog: dict[str, str]) -> list[dict[str, str]]:
    """ID 목록을 {id, text} 목록으로 펼칩니다 (화면/AI 입력 공용)."""
    return [{"id": key, "text": catalog[key]} for key in ids]
