"""AI 입력 데이터 계약(contract) 빌더 (기획서 9.2).

이 모듈은 pandas를 쓰지 않습니다. 순수 dict만 다룹니다.
이유: '계산 레이어(pandas)' 와 'AI/검증 레이어(dict)' 의 경계를 명확히 하면
      - AI에 넘어가는 값이 무엇인지 한눈에 보이고
      - 검증(validator)을 표준 라이브러리만으로 테스트할 수 있습니다.

핵심 원칙: AI는 이 JSON 안에 있는 값만 말할 수 있습니다.
여기에 없는 숫자·지역명·점포명이 브리핑에 등장하면 검증에서 탈락시킵니다.
"""

from __future__ import annotations

from typing import Any

from . import config, review


def _round(value: Any, digits: int) -> Any:
    if value is None:
        return None
    return round(float(value), digits)


def build_contract(
    branch: dict[str, Any],
    region: dict[str, Any],
    peers: list[dict[str, Any]],
    audience: str = "은행 점포전략 담당자",
) -> dict[str, Any]:
    """개별 점포 1건에 대한 AI 입력 JSON을 만듭니다.

    Parameters
    ----------
    branch : 선택된 점포 (branch_id, branch_name, branch_type, region_code, region_name)
    region : 지표까지 계산된 소속 자치구 1행
    peers  : find_peers 결과를 dict 목록으로 변환한 것
    """
    result = {
        "biz_density_label": region["biz_density_label"],
        "pop_density_label": region["pop_density_label"],
        "boundary_adjacent": bool(region["boundary_adjacent"]),
        "density_label_conflict": bool(region["density_label_conflict"]),
    }

    notable_id = review.select_notable_indicator(result)
    reason_ids = review.select_review_reasons(result)
    candidate_ids = review.select_next_internal_data_candidates()

    return {
        "schema_version": config.SCHEMA_VERSION,
        "dataset_version": config.DATASET_VERSION,
        "audience": audience,
        # ---- 개별 점포: 검증된 식별정보만. 주소·좌표·운영상태는 미확보이므로 넣지 않음
        "branch": {
            "branch_id": branch["branch_id"],
            "branch_name": branch["branch_name"],
            "branch_type": branch["branch_type"],
            "name_source": branch.get("name_source", "unknown"),
        },
        "region": {
            "region_code": region["region_code"],
            "region_name": region["region_name"],
            "total_pop": int(region["total_pop"]),
            "elderly_pop": int(region["elderly_pop"]),
            "biz_count": int(region["biz_count"]),
            "ibk_branches": int(region["ibk_branches"]),
            "population_label": config.POPULATION_LABEL,
            "ibk_branches_seoul_total": config.EXPECTED_BRANCH_TOTAL,
        },
        # ---- 표시용으로 반올림한 값. 라벨/판정은 이미 원값으로 끝났음
        "metrics": {
            "biz_per_1k": _round(region["biz_per_1k"], config.ROUND_DENSITY),
            "pop_per_10k": _round(region["pop_per_10k"], config.ROUND_DENSITY),
            "biz_percentile": _round(region["biz_percentile"], config.ROUND_PERCENTILE),
            "pop_percentile": _round(region["pop_percentile"], config.ROUND_PERCENTILE),
            "elderly_ratio": _round(region["elderly_ratio"], config.ROUND_RATIO),
            "population_size_percentile": _round(
                region["population_size_percentile"], config.ROUND_PERCENTILE
            ),
            "business_size_percentile": _round(
                region["business_size_percentile"], config.ROUND_PERCENTILE
            ),
        },
        "result": result,
        "peers": [
            {
                "region_name": p["region_name"],
                "biz_per_1k": _round(p["biz_per_1k"], config.ROUND_DENSITY),
                "biz_percentile": _round(p["biz_percentile"], config.ROUND_PERCENTILE),
            }
            for p in peers
        ],
        "notable_indicator_id": notable_id,
        "notable_indicator_text": config.NOTABLE_INDICATORS[notable_id],
        "review_reasons": review.expand(reason_ids, config.REVIEW_REASONS),
        "next_internal_data_candidates": review.expand(
            candidate_ids, config.NEXT_INTERNAL_DATA_CANDIDATES
        ),
        "evidence_ids": list(config.METRIC_EVIDENCE_IDS),
        "limitations": list(config.LIMITATIONS),
    }


# ---------------------------------------------------------------------------
# 검증에 쓰일 '허용 목록' 추출
# ---------------------------------------------------------------------------

def allowed_numbers(contract: dict[str, Any]) -> set[float]:
    """브리핑에 등장해도 되는 숫자 집합.

    contract 안의 모든 수치 + 그 수치를 0~3자리로 반올림한 형태를 모두 허용합니다.
    (AI가 '0.22' 로 줄여 쓰는 것은 허용, '0.31' 로 바꿔 쓰는 것은 차단)
    """
    values: set[float] = set(config.ALLOWED_CONTEXT_NUMBERS)

    def walk(node: Any) -> None:
        if isinstance(node, bool):
            return
        if isinstance(node, (int, float)):
            number = float(node)
            values.add(number)
            for digits in range(0, 4):
                values.add(round(number, digits))
            return
        if isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(contract["region"])
    walk(contract["metrics"])
    walk(contract["peers"])
    return values


def allowed_names(contract: dict[str, Any]) -> set[str]:
    """브리핑에 등장해도 되는 고유명(지역명·점포명) 집합."""
    names = set(config.ALLOWED_PROPER_NOUNS)
    names.add(contract["branch"]["branch_name"])
    names.add(contract["region"]["region_name"])
    for peer in contract["peers"]:
        names.add(peer["region_name"])
    return names
