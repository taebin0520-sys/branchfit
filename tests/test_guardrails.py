"""AI 가드레일 테스트 (기획서 9~10절).

이 파일은 pandas 없이도 동작합니다.
contract / validator / briefing 레이어는 순수 dict만 다루기 때문입니다.
"""

from __future__ import annotations

import copy

import pytest

from branchfit import briefing, config, contract as contract_mod, validator

REGION = {
    "region_code": "11680",
    "region_name": "강남구",
    "total_pop": 552_847,
    "elderly_pop": 96_412,
    "biz_count": 81_743,
    "ibk_branches": 18,
    "biz_per_1k": 0.22020,
    "pop_per_10k": 0.32562,
    "elderly_ratio": 17.4406,
    "biz_percentile": 68.0,
    "pop_percentile": 92.0,
    "population_size_percentile": 92.0,
    "business_size_percentile": 100.0,
    "biz_density_label": config.LABEL_MID,
    "pop_density_label": config.LABEL_HIGH,
    "boundary_adjacent": True,
    "density_label_conflict": True,
}

BRANCH = {
    "branch_id": "IBK-11680-01",
    "branch_name": "역삼영업점",
    "branch_type": "영업점",
    "region_code": "11680",
    "region_name": "강남구",
    "name_source": "synthetic_placeholder",
}

PEERS = [
    {"region_name": "송파구", "biz_per_1k": 0.204, "biz_percentile": 40.0},
    {"region_name": "서초구", "biz_per_1k": 0.212, "biz_percentile": 52.0},
]


@pytest.fixture()
def contract():
    return contract_mod.build_contract(branch=BRANCH, region=REGION, peers=PEERS)


@pytest.fixture()
def good_briefing(contract):
    return briefing.build_template_briefing(contract)


# ---------------------------------------------------------------------------
# contract
# ---------------------------------------------------------------------------

def test_contract_has_all_spec_fields(contract):
    """기획서 9.2에 명시된 필드가 모두 있어야 합니다."""
    for field in [
        "schema_version",
        "dataset_version",
        "region",
        "metrics",
        "result",
        "peers",
        "notable_indicator_id",
        "review_reasons",
        "next_internal_data_candidates",
        "evidence_ids",
        "limitations",
        "audience",
    ]:
        assert field in contract


def test_contract_excludes_unverified_branch_fields(contract):
    """미확보 필드(주소·좌표·운영상태)는 애초에 만들지 않습니다."""
    for field in ("address", "latitude", "longitude", "status", "distance"):
        assert field not in contract["branch"]


def test_notable_indicator_priority_conflict_first(contract):
    """지표 충돌 + 경계 인접이 동시일 때 충돌이 우선."""
    assert contract["notable_indicator_id"] == "NI-CONFLICT"


def test_review_reasons_always_include_timepoint_and_district_limits(contract):
    ids = {reason["id"] for reason in contract["review_reasons"]}
    assert "RR-06" in ids  # 기준시점 상이
    assert "RR-07" in ids  # 자치구 단위 지표


def test_next_internal_data_candidates_always_three(contract):
    assert len(contract["next_internal_data_candidates"]) == 3


# ---------------------------------------------------------------------------
# 템플릿 fallback은 항상 통과해야 한다 (화면이 비지 않도록)
# ---------------------------------------------------------------------------

def test_template_briefing_passes_validation(contract, good_briefing):
    result = validator.validate(good_briefing, contract)
    assert result.ok, result.errors


def test_generate_briefing_without_llm_uses_template(contract):
    outcome = briefing.generate_briefing(contract, llm_caller=None)
    assert outcome["mode"] == "template"
    assert validator.validate(outcome["briefing"], contract).ok


# ---------------------------------------------------------------------------
# 검증 실패 케이스
# ---------------------------------------------------------------------------

def mutate(base, **changes):
    copied = copy.deepcopy(base)
    copied.update(changes)
    return copied


def test_blocks_invented_number(contract, good_briefing):
    bad = mutate(
        good_briefing,
        summary=good_briefing["summary"] + " 최근접 대체 점포는 1.4km 거리입니다.",
    )
    result = validator.validate(bad, contract)
    assert not result.ok
    assert any("숫자" in error for error in result.errors)


def test_allows_rounded_form_of_input_number(contract, good_briefing):
    """0.22 → 0.2 처럼 입력값을 줄여 쓰는 것은 허용."""
    bad = mutate(
        good_briefing,
        context_points=good_briefing["context_points"] + ["주지표는 약 0.2 수준입니다."],
    )
    assert validator.validate(bad, contract).ok


def test_blocks_invented_region_name(contract, good_briefing):
    bad = mutate(
        good_briefing,
        context_points=good_briefing["context_points"] + ["성북구와 함께 보면 좋습니다."],
    )
    result = validator.validate(bad, contract)
    assert not result.ok
    assert any("지역명" in error for error in result.errors)


def test_blocks_invented_branch_name(contract, good_briefing):
    bad = mutate(
        good_briefing,
        evidence_points=good_briefing["evidence_points"] + ["삼성기업금융센터가 인접합니다."],
    )
    result = validator.validate(bad, contract)
    assert not result.ok
    assert any("점포" in error for error in result.errors)


@pytest.mark.parametrize(
    "sentence",
    [
        "본 점포는 통·폐합해야 합니다.",
        "폐쇄를 권고합니다.",
        "우선 검토 대상으로 추천합니다.",
        "수익성이 낮습니다.",
        "방문 고객이 감소할 것으로 예상됩니다.",
        "거래량이 적습니다.",
    ],
)
def test_blocks_forbidden_expressions(contract, good_briefing, sentence):
    bad = mutate(good_briefing, summary=sentence)
    result = validator.validate(bad, contract)
    assert not result.ok


def test_allows_limitation_wording_that_mentions_forbidden_words(contract, good_briefing):
    """'수익성을 알 수 없습니다'처럼 한계를 밝히는 문장은 막지 않아야 합니다."""
    ok = mutate(
        good_briefing,
        limitation_points=good_briefing["limitation_points"]
        + ["공개 외부데이터만으로는 점포 수익성과 거래량을 알 수 없습니다."],
    )
    result = validator.validate(ok, contract)
    assert result.ok, result.errors


def test_blocks_missing_field(contract, good_briefing):
    bad = {k: v for k, v in good_briefing.items() if k != "summary"}
    assert not validator.validate(bad, contract).ok


def test_blocks_extra_field(contract, good_briefing):
    bad = mutate(good_briefing, recommendation="폐쇄")
    assert not validator.validate(bad, contract).ok


def test_blocks_non_dict(contract):
    assert not validator.validate("브리핑입니다", contract).ok


# ---------------------------------------------------------------------------
# 재시도 → fallback
# ---------------------------------------------------------------------------

def test_retries_once_then_falls_back(contract):
    calls = []

    def always_bad(_contract):
        calls.append(1)
        return {"summary": "폐쇄를 권고합니다."}

    outcome = briefing.generate_briefing(contract, llm_caller=always_bad)
    assert outcome["mode"] == "template_fallback"
    assert len(calls) == config.LLM_MAX_RETRY + 1
    assert len(outcome["attempts"]) == config.LLM_MAX_RETRY + 1
    assert validator.validate(outcome["briefing"], contract).ok


def test_second_attempt_can_succeed(contract, good_briefing):
    state = {"n": 0}

    def flaky(_contract):
        state["n"] += 1
        if state["n"] == 1:
            return {"summary": "추천합니다."}
        return good_briefing

    outcome = briefing.generate_briefing(contract, llm_caller=flaky)
    assert outcome["mode"] == "llm"
    assert state["n"] == 2


def test_network_error_falls_back(contract):
    def boom(_contract):
        raise OSError("연결 실패")

    outcome = briefing.generate_briefing(contract, llm_caller=boom)
    assert outcome["mode"] == "template_fallback"
    assert validator.validate(outcome["briefing"], contract).ok
