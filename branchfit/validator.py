"""AI 브리핑 검증기 (기획서 10절).

검증 순서
    1) 구조 검증        - 필드 존재/타입 (JSON Schema 역할)
    2) 수치 대조        - 입력에 없는 숫자가 등장하면 탈락
    3) 고유명 검출      - 입력에 없는 지역명·점포명이 등장하면 탈락
    4) 금지표현 검사    - 결정·추천·예측 표현이 등장하면 탈락

이 모듈도 pandas를 쓰지 않습니다(표준 라이브러리만).
검증기는 시스템의 마지막 안전장치이므로 의존성을 최소로 둡니다.
"""

from __future__ import annotations

import re
from typing import Any

from . import config, contract as contract_mod

#: 브리핑 출력 구조. {필드명: (타입, 최소 개수)}
BRIEFING_FIELDS: dict[str, tuple[type, int]] = {
    "summary": (str, 1),
    "evidence_points": (list, 2),
    "context_points": (list, 1),
    "limitation_points": (list, 2),
    "next_check_points": (list, 3),
}

#: '~구'로 끝나지만 지역명이 아닌 일반 단어.
#: 한국어는 명사 뒤에 조사가 붙으므로("부산진구와", "인구는") 정규식 뒤쪽 조건으로는
#: 지역명과 일반명사를 구분할 수 없습니다. 그래서 '허용 고유명을 먼저 지우고
#: 남은 ~구 토큰 중 일반명사만 걸러내는' 방식을 씁니다.
_GU_STOPWORDS = config.REGION_TOKEN_STOPWORDS | {
    "인구",
    "총인구",
    "고령인구",
    "유동인구",
    "생활인구",
    "지역구",
    "선거구",
    "연구",
    "요구",
    "도구",
    "기구",
    "지구",
    "입구",
    "출구",
    "가구",
    "대구",
}

_DATE_LIKE = re.compile(r"\d{4}-\d{2}-\d{2}(?:_v\d+)?")
_THOUSAND_SEP = re.compile(r"(?<=\d),(?=\d)")
_NUMBER = re.compile(r"\d+(?:\.\d+)?")
_GU_TOKEN = re.compile(r"[가-힣]{2,5}구")
_BRANCH_TOKEN = re.compile(r"[가-힣A-Za-z0-9]{2,12}(?:영업점|출장소|지점|센터)")


def _known_tokens(contract: dict[str, Any]) -> set[str]:
    """입력에서 유래한 '지워도 되는' 문자열 모음.

    고유명·식별자·필드명을 먼저 제거한 뒤에 검사하면
    - 'pop_per_10k'의 10을 AI가 만든 숫자로 오탐하는 일
    - '남구로영업점'에서 '남구'를 다른 지역명으로 오탐하는 일
    을 둘 다 막을 수 있습니다.
    """
    return (
        contract_mod.allowed_names(contract)
        | {contract["branch"]["branch_id"]}
        | set(contract["metrics"].keys())
        | set(contract["region"].keys())
    )


def _scrub(text: str, tokens: set[str]) -> str:
    """긴 토큰부터 제거합니다(짧은 토큰이 긴 토큰을 먼저 깨뜨리지 않도록)."""
    for token in sorted(tokens, key=len, reverse=True):
        text = text.replace(token, " ")
    return text


class ValidationResult:
    """검증 결과. 실패 사유를 모두 모아 두어 디버깅/로그에 쓸 수 있게 합니다."""

    def __init__(self) -> None:
        self.errors: list[str] = []

    @property
    def ok(self) -> bool:
        return not self.errors

    def add(self, message: str) -> None:
        self.errors.append(message)

    def __repr__(self) -> str:  # pragma: no cover - 디버깅 편의용
        status = "PASS" if self.ok else "FAIL"
        return f"<ValidationResult {status} errors={self.errors}>"


# ---------------------------------------------------------------------------
# 1) 구조 검증
# ---------------------------------------------------------------------------

def check_structure(briefing: Any, result: ValidationResult) -> None:
    if not isinstance(briefing, dict):
        result.add("브리핑이 객체(JSON object)가 아닙니다.")
        return

    for field, (expected_type, minimum) in BRIEFING_FIELDS.items():
        if field not in briefing:
            result.add(f"필드 누락: {field}")
            continue
        value = briefing[field]
        if not isinstance(value, expected_type):
            result.add(f"{field} 타입 오류: {type(value).__name__}")
            continue
        if expected_type is str:
            if len(value.strip()) < minimum:
                result.add(f"{field}가 비어 있습니다.")
        else:
            if len(value) < minimum:
                result.add(f"{field} 항목 수 부족: {len(value)} < {minimum}")
            if any(not isinstance(item, str) or not item.strip() for item in value):
                result.add(f"{field}에 문자열이 아닌/빈 항목이 있습니다.")

    unknown = set(briefing) - set(BRIEFING_FIELDS)
    if unknown:
        result.add(f"허용되지 않은 필드: {sorted(unknown)}")


# ---------------------------------------------------------------------------
# 텍스트 평탄화
# ---------------------------------------------------------------------------

def flatten_text(briefing: dict[str, Any]) -> str:
    parts: list[str] = []
    for field in BRIEFING_FIELDS:
        value = briefing.get(field)
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, list):
            parts.extend(str(item) for item in value)
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# 2) 수치 대조
# ---------------------------------------------------------------------------

def check_numbers(text: str, contract: dict[str, Any], result: ValidationResult) -> None:
    allowed = contract_mod.allowed_numbers(contract)

    # region_code / branch_id 처럼 '문자열로 저장된 숫자'도 허용 목록에 넣습니다.
    code = contract["region"]["region_code"]
    if str(code).isdigit():
        allowed.add(float(code))

    # 날짜·버전 문자열은 숫자 검사에서 제외합니다 (2026-07-31 → 2026, 7, 31 오탐 방지).
    cleaned = _scrub(_DATE_LIKE.sub(" ", text), _known_tokens(contract))
    # '1,234개'처럼 천 단위 구분기호가 붙은 숫자를 하나로 합칩니다.
    cleaned = _THOUSAND_SEP.sub("", cleaned)

    unknown = sorted(
        {
            token
            for token in _NUMBER.findall(cleaned)
            if float(token) not in allowed
        }
    )
    if unknown:
        result.add(f"입력에 없는 숫자 사용: {unknown}")


# ---------------------------------------------------------------------------
# 3) 고유명 검출
# ---------------------------------------------------------------------------

def check_proper_nouns(
    text: str, contract: dict[str, Any], result: ValidationResult
) -> None:
    # 허용된 고유명을 먼저 지웁니다. 남은 지역명·점포명은 모두 '입력에 없는 것'입니다.
    scrubbed = _scrub(text, _known_tokens(contract))

    bad_regions = sorted(
        {
            token
            for token in _GU_TOKEN.findall(scrubbed)
            if token not in _GU_STOPWORDS
        }
    )
    if bad_regions:
        result.add(f"입력에 없는 지역명 사용: {bad_regions}")

    bad_branches = sorted(set(_BRANCH_TOKEN.findall(scrubbed)))
    if bad_branches:
        result.add(f"입력에 없는 점포·기관명 사용: {bad_branches}")


# ---------------------------------------------------------------------------
# 4) 금지표현 검사
# ---------------------------------------------------------------------------

def check_forbidden(text: str, result: ValidationResult) -> None:
    for pattern, reason in config.FORBIDDEN_PATTERNS:
        match = re.search(pattern, text)
        if match:
            result.add(f"금지표현({reason}): '{match.group(0)}'")


# ---------------------------------------------------------------------------
# 통합
# ---------------------------------------------------------------------------

def validate(briefing: Any, contract: dict[str, Any]) -> ValidationResult:
    """브리핑 전체를 검증합니다. 통과하면 result.ok == True."""
    result = ValidationResult()

    check_structure(briefing, result)
    if not result.ok:
        # 구조가 깨졌으면 텍스트 검사를 진행할 수 없습니다.
        return result

    text = flatten_text(briefing)
    check_numbers(text, contract, result)
    check_proper_nouns(text, contract, result)
    check_forbidden(text, result)
    return result
