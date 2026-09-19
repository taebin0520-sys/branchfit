"""AI 에이전트 브리핑 생성 + 실패 대응 (기획서 9~10절).

흐름 (기획서 10절 그대로)
    구조화 입력 → LLM 호출 → 검증 → 통과하면 노출
                              → 실패하면 1회 재시도
                              → 재실패하면 결정론적 템플릿 fallback

중요한 설계 결정 두 가지
1) 템플릿 fallback은 '고정 상수 문구 + contract의 숫자'로만 만듭니다.
   따라서 fallback은 검증을 항상 통과합니다. = 화면이 절대 비지 않습니다.
2) LLM 호출은 표준 라이브러리(urllib)로 합니다.
   외부 SDK를 붙이지 않아 설치 의존성이 줄고, OpenAI 호환 엔드포인트면
   base_url만 바꿔서 그대로 동작합니다.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from . import config, validator

# ---------------------------------------------------------------------------
# 시스템 프롬프트: 가드레일을 자연어로도 한 번 더 못박습니다.
# (자연어 지시만으로는 못 믿기 때문에 validator가 뒤에서 다시 검사합니다)
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """당신은 은행 점포전략 담당자를 돕는 '근거 요약 에이전트'입니다.
당신의 역할은 결정이 아니라 정리입니다.

반드시 지킬 규칙:
1. 입력 JSON에 있는 숫자만 사용합니다. 계산·추정·반올림 변경을 하지 않습니다.
2. 입력 JSON에 없는 지역명, 점포명, 기관명, 거리, 주소, 운영상태를 쓰지 않습니다.
3. 점포의 통·폐합 여부, 폐쇄, 유지, 추천, 권고, 우선순위를 말하지 않습니다.
4. 금융수요, 수익성, 거래량, 방문객 수를 추론하거나 예측하지 않습니다.
5. 지표가 서로 다른 이유를 임의로 추측하지 않습니다. 다르다는 사실만 씁니다.
6. limitations와 next_internal_data_candidates는 입력에 있는 내용만 옮깁니다.
7. biz_per_1k 같은 영문 필드명 대신 '사업체 1천 개당 IBK 영업점 수'처럼 한국어로 씁니다.

출력은 아래 키만 가진 JSON 객체 하나입니다. 다른 키를 추가하지 마십시오.
{
  "summary": "2~3문장. 어떤 점포이고 소속 자치구의 상대 위치가 어디인지.",
  "evidence_points": ["확인된 외부데이터 수치 나열. 2개 이상"],
  "context_points": ["지역 맥락과 Peer 비교. 1개 이상"],
  "limitation_points": ["입력 limitations 중 중요한 것. 2개 이상"],
  "next_check_points": ["입력 next_internal_data_candidates 3개를 그대로"]
}"""


# ---------------------------------------------------------------------------
# 결정론적 템플릿 (fallback / LLM 미설정 시 기본값)
# ---------------------------------------------------------------------------

def build_template_briefing(contract: dict[str, Any]) -> dict[str, Any]:
    """contract만으로 브리핑을 조립합니다. 항상 검증을 통과해야 합니다."""
    branch = contract["branch"]
    region = contract["region"]
    metric = contract["metrics"]
    result = contract["result"]

    summary = (
        f"{branch['branch_name']}은 {region['region_name']}에 위치한 IBK "
        f"{branch['branch_type']}입니다. "
        f"소속 자치구의 사업체 1천 개당 IBK 영업점 수는 "
        f"{metric['biz_per_1k']}개로, {region['population_label']} 내 "
        f"percentile {metric['biz_percentile']} 위치이며 "
        f"{result['biz_density_label']} 구간입니다. "
        f"{contract['notable_indicator_text']}"
    )

    evidence_points = [
        f"소속 자치구 총인구는 {region['total_pop']:,}명, 65세 이상 인구는 "
        f"{region['elderly_pop']:,}명이며 고령인구 비율은 "
        f"{metric['elderly_ratio']}% 입니다.",
        f"소속 자치구 사업체 수는 {region['biz_count']:,}개, 자치구 내 IBK 영업점 수는 "
        f"{region['ibk_branches']}개입니다. "
        f"서울 분석 대상 IBK 영업점은 모두 "
        f"{region['ibk_branches_seoul_total']}개입니다.",
        f"지역 맥락 주지표인 사업체 1천 개당 IBK 영업점 수는 "
        f"{metric['biz_per_1k']}개, percentile {metric['biz_percentile']} 입니다.",
        f"지역 맥락 보조지표인 인구 1만 명당 IBK 영업점 수는 "
        f"{metric['pop_per_10k']}개, percentile {metric['pop_percentile']}로 "
        f"{result['pop_density_label']} 구간입니다.",
    ]

    context_points: list[str] = []
    if contract["peers"]:
        peer_text = ", ".join(
            f"{p['region_name']}(사업체 1천 개당 {p['biz_per_1k']}개, "
            f"percentile {p['biz_percentile']})"
            for p in contract["peers"]
        )
        context_points.append(
            f"총인구와 사업체 규모가 유사한 비교지역은 {peer_text} 입니다. "
            f"규모가 비슷한 지역과 나란히 보기 위한 참고지역이며 지역 간 우열을 "
            f"뜻하지 않습니다."
        )
    context_points.append(config.FIXED_PHRASES[result["biz_density_label"]])
    if result["density_label_conflict"]:
        context_points.append(config.FIXED_PHRASES["density_label_conflict"])
    if result["boundary_adjacent"]:
        context_points.append(config.FIXED_PHRASES["boundary_adjacent"])

    # 한계는 '검토 사유' 중 항상 노출되는 항목 + 입력 limitations 일부를 씁니다.
    limitation_points = [
        reason["text"]
        for reason in contract["review_reasons"]
        if reason["id"] in {"RR-06", "RR-07"}
    ]
    limitation_points.append(contract["limitations"][0])
    limitation_points.append(contract["limitations"][1])
    limitation_points.append(
        "본 브리핑은 통·폐합 여부를 판정하지 않으며, 최종 판단은 담당자가 수행합니다."
    )

    next_check_points = [item["text"] for item in contract["next_internal_data_candidates"]]

    return {
        "summary": summary,
        "evidence_points": evidence_points,
        "context_points": context_points,
        "limitation_points": limitation_points,
        "next_check_points": next_check_points,
    }


# ---------------------------------------------------------------------------
# LLM 호출
# ---------------------------------------------------------------------------

def llm_configured() -> bool:
    return bool(os.environ.get(config.ENV_API_KEY))


def call_llm(contract: dict[str, Any]) -> dict[str, Any]:
    """OpenAI 호환 chat completions 엔드포인트를 호출해 JSON을 받아옵니다."""
    api_key = os.environ.get(config.ENV_API_KEY)
    if not api_key:
        raise RuntimeError(f"{config.ENV_API_KEY} 환경변수가 없습니다.")

    base_url = os.environ.get(config.ENV_BASE_URL, config.DEFAULT_BASE_URL).rstrip("/")
    model = os.environ.get(config.ENV_MODEL, config.DEFAULT_MODEL)

    payload = {
        "model": model,
        # temperature를 0으로 두는 이유: 같은 점포를 다시 조회했을 때
        # 브리핑 문장이 매번 달라지면 검토 이력 비교가 어려워집니다.
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps(contract, ensure_ascii=False, indent=2),
            },
        ],
    }
    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=config.LLM_TIMEOUT_SECONDS) as response:
        body = json.loads(response.read().decode("utf-8"))

    content = body["choices"][0]["message"]["content"]
    return json.loads(content)


# ---------------------------------------------------------------------------
# 통합 진입점
# ---------------------------------------------------------------------------

def generate_briefing(
    contract: dict[str, Any],
    *,
    llm_caller=None,
) -> dict[str, Any]:
    """브리핑을 생성하고, 어떤 경로로 생성됐는지까지 함께 돌려줍니다.

    Returns
    -------
    {
      "briefing": {...},
      "mode": "llm" | "template" | "template_fallback",
      "attempts": [{"attempt": 1, "errors": [...]}, ...],
    }

    mode를 반환하는 이유: 화면에 'AI 생성' / '템플릿 대체'를 반드시 표시해야
    담당자가 브리핑의 성격을 오해하지 않습니다.
    """
    caller = llm_caller or (call_llm if llm_configured() else None)

    if caller is None:
        return {
            "briefing": build_template_briefing(contract),
            "mode": "template",
            "attempts": [],
        }

    attempts: list[dict[str, Any]] = []
    for attempt in range(1, config.LLM_MAX_RETRY + 2):
        try:
            candidate = caller(contract)
        except (urllib.error.URLError, OSError, ValueError, KeyError) as exc:
            attempts.append({"attempt": attempt, "errors": [f"호출 실패: {exc}"]})
            continue

        outcome = validator.validate(candidate, contract)
        attempts.append({"attempt": attempt, "errors": list(outcome.errors)})
        if outcome.ok:
            return {"briefing": candidate, "mode": "llm", "attempts": attempts}

    return {
        "briefing": build_template_briefing(contract),
        "mode": "template_fallback",
        "attempts": attempts,
    }


MODE_LABELS = {
    "llm": "AI 에이전트 생성 (검증 통과)",
    "template": "결정론적 템플릿 (LLM 미설정)",
    "template_fallback": "결정론적 템플릿 (AI 출력 검증 실패로 대체)",
}


def render_markdown(briefing: dict[str, Any]) -> str:
    """브리핑 dict를 화면 표시용 마크다운으로 바꿉니다."""
    sections = [
        ("요약", [briefing["summary"]]),
        ("확인된 외부데이터 근거", briefing["evidence_points"]),
        ("지역 맥락", briefing["context_points"]),
        ("해석 시 한계", briefing["limitation_points"]),
        ("추가 확인 필요영역", briefing["next_check_points"]),
    ]
    lines: list[str] = []
    for title, items in sections:
        lines.append(f"**{title}**")
        lines.append("")
        for item in items:
            lines.append(f"- {item}")
        lines.append("")
    return "\n".join(lines)
