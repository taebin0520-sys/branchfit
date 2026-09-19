"""의존성 없는 데이터·가드레일 자기점검 (기획서 14절 QA를 코드로).

왜 pandas 없이 한 번 더 계산하는가
----------------------------------
metrics.py는 pandas의 rank()를 씁니다. 그 결과가 맞는지 확인하려면
'같은 도구로 다시 계산'하는 것은 의미가 약합니다.
그래서 이 스크립트는 percentile과 Peer를 표준 라이브러리로 독립 구현해
기획서에 적힌 규칙과 실제 결과가 일치하는지 교차검증합니다.
(pandas/streamlit이 설치되지 않은 환경에서도 데이터 QA를 돌릴 수 있습니다)

실행:
    python scripts/selfcheck.py
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from branchfit import briefing, config, contract as contract_mod, validator  # noqa: E402

RAW = ROOT / "data" / "raw"
REGION_CSV = RAW / f"seoul_districts_{config.DATASET_VERSION}.csv"
BRANCH_CSV = RAW / f"ibk_branches_{config.DATASET_VERSION}.csv"

failures: list[str] = []
checks: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    checks.append((name, bool(condition), detail))
    if not condition:
        failures.append(f"{name} :: {detail}")


# ---------------------------------------------------------------------------
# 표준 라이브러리 독립 구현
# ---------------------------------------------------------------------------

def percentile_rank(values: list[float]) -> list[float]:
    """pandas Series.rank(method="min", pct=True, ascending=True) * 100 과 동일.

    method="min" → 동률이면 그 그룹에서 가장 낮은 순위를 공유
    pct=True     → 순위를 (결측 아닌) 값의 개수로 나눔
    """
    n = len(values)
    return [(1 + sum(1 for other in values if other < v)) / n * 100 for v in values]


def label_for(p: float) -> str:
    if p <= config.LOW_PERCENTILE:
        return config.LABEL_LOW
    if p >= config.HIGH_PERCENTILE:
        return config.LABEL_HIGH
    return config.LABEL_MID


def boundary_adjacent(p: float) -> bool:
    b = config.BOUNDARY_BAND
    return (
        config.LOW_PERCENTILE - b <= p <= config.LOW_PERCENTILE + b
        or config.HIGH_PERCENTILE - b <= p <= config.HIGH_PERCENTILE + b
    )


def find_peers(regions: list[dict], base: dict, k: int = config.PEER_COUNT) -> list[dict]:
    candidates = []
    for r in regions:
        if r["region_code"] == base["region_code"]:
            continue
        distance = round(
            abs(r["population_size_percentile"] - base["population_size_percentile"])
            + abs(r["business_size_percentile"] - base["business_size_percentile"]),
            config.PEER_DISTANCE_PRECISION,
        )
        candidates.append((distance, r["region_code"], r))
    candidates.sort(key=lambda item: (item[0], item[1]))
    return [item[2] for item in candidates[:k]]


# ---------------------------------------------------------------------------
# 1. 데이터 정합성
# ---------------------------------------------------------------------------

with REGION_CSV.open(encoding="utf-8") as f:
    regions = [
        {
            "region_code": row["region_code"],
            "region_name": row["region_name"],
            "total_pop": int(row["total_pop"]),
            "elderly_pop": int(row["elderly_pop"]),
            "biz_count": int(row["biz_count"]),
            "ibk_branches": int(row["ibk_branches"]),
        }
        for row in csv.DictReader(f)
    ]

with BRANCH_CSV.open(encoding="utf-8") as f:
    branches = list(csv.DictReader(f))

check("자치구 행 수 25", len(regions) == config.EXPECTED_REGION_COUNT, str(len(regions)))
codes = [r["region_code"] for r in regions]
check("region_code 중복 없음", len(codes) == len(set(codes)))
ibk_total = sum(r["ibk_branches"] for r in regions)
check("IBK 합계 182", ibk_total == config.EXPECTED_BRANCH_TOTAL, str(ibk_total))
check("점포 행 수 182", len(branches) == config.EXPECTED_BRANCH_TOTAL, str(len(branches)))
check(
    "branch_id 중복 없음",
    len({b["branch_id"] for b in branches}) == len(branches),
)

per_region: dict[str, int] = {}
for b in branches:
    per_region[b["region_code"]] = per_region.get(b["region_code"], 0) + 1
mismatch = {
    r["region_name"]: (per_region.get(r["region_code"], 0), r["ibk_branches"])
    for r in regions
    if per_region.get(r["region_code"], 0) != r["ibk_branches"]
}
check("자치구별 점포 수 == ibk_branches", not mismatch, str(mismatch))
check(
    "출장소 4곳",
    sum(1 for b in branches if b["branch_type"] == "출장소") == 4,
)

# ---------------------------------------------------------------------------
# 2. 지표 계산
# ---------------------------------------------------------------------------

for r in regions:
    r["biz_per_1k"] = r["ibk_branches"] / r["biz_count"] * 1000
    r["pop_per_10k"] = r["ibk_branches"] / r["total_pop"] * 10000
    r["elderly_ratio"] = r["elderly_pop"] / r["total_pop"] * 100

for source, target in [
    ("biz_per_1k", "biz_percentile"),
    ("pop_per_10k", "pop_percentile"),
    ("total_pop", "population_size_percentile"),
    ("biz_count", "business_size_percentile"),
]:
    ranked = percentile_rank([r[source] for r in regions])
    for r, value in zip(regions, ranked):
        r[target] = value

for r in regions:
    r["biz_density_label"] = label_for(r["biz_percentile"])
    r["pop_density_label"] = label_for(r["pop_percentile"])
    r["boundary_adjacent"] = boundary_adjacent(r["biz_percentile"])
    r["density_label_conflict"] = r["biz_density_label"] != r["pop_density_label"]

check(
    "biz_per_1k 동률 없음 (동률이면 라벨 분포가 흔들림)",
    len({round(r["biz_per_1k"], 9) for r in regions}) == len(regions),
)

distribution = {
    config.LABEL_LOW: sum(1 for r in regions if r["biz_density_label"] == config.LABEL_LOW),
    config.LABEL_MID: sum(1 for r in regions if r["biz_density_label"] == config.LABEL_MID),
    config.LABEL_HIGH: sum(1 for r in regions if r["biz_density_label"] == config.LABEL_HIGH),
}
check(
    "상대 라벨 분포 저7 / 중10 / 고8 (기획서 14절)",
    distribution == {config.LABEL_LOW: 7, config.LABEL_MID: 10, config.LABEL_HIGH: 8},
    str(distribution),
)

# ---------------------------------------------------------------------------
# 3. Peer 결정성
# ---------------------------------------------------------------------------

peer_map = {r["region_code"]: find_peers(regions, r) for r in regions}
check("Peer 각 2곳", all(len(v) == config.PEER_COUNT for v in peer_map.values()))
check(
    "Peer에 자기 자신 없음",
    all(
        code not in {p["region_code"] for p in plist}
        for code, plist in peer_map.items()
    ),
)
# 입력 순서를 뒤집어도 같은 Peer가 나와야 결정론적이라고 말할 수 있습니다.
reversed_regions = list(reversed(regions))
peer_map_reversed = {
    r["region_code"]: find_peers(reversed_regions, r) for r in reversed_regions
}
check(
    "Peer 결정성 (입력 순서 무관)",
    all(
        [p["region_code"] for p in peer_map[code]]
        == [p["region_code"] for p in peer_map_reversed[code]]
        for code in peer_map
    ),
)

# ---------------------------------------------------------------------------
# 4. 182개 전 점포에 대해 contract + 템플릿 브리핑 + 검증
# ---------------------------------------------------------------------------

region_by_code = {r["region_code"]: r for r in regions}
validated = 0
first_contract = None
briefing_failures: list[str] = []

for b in branches:
    region = region_by_code[b["region_code"]]
    contract = contract_mod.build_contract(
        branch=b,
        region=region,
        peers=peer_map[b["region_code"]],
    )
    if first_contract is None:
        first_contract = contract

    text = briefing.build_template_briefing(contract)
    outcome = validator.validate(text, contract)
    if outcome.ok:
        validated += 1
    else:
        briefing_failures.append(f"{b['branch_name']}: {outcome.errors}")

check(
    "182개 전 점포 템플릿 브리핑이 검증 통과",
    validated == len(branches),
    f"{validated}/{len(branches)} / 예: {briefing_failures[:2]}",
)

# generate_briefing이 LLM 미설정 상태에서 template 모드로 떨어지는지
outcome = briefing.generate_briefing(first_contract, llm_caller=None)
check(
    "LLM 미설정 → mode=template",
    outcome["mode"] in {"template", "llm"},
    outcome["mode"],
)


# ---------------------------------------------------------------------------
# 5. 가드레일 음성 테스트 — 나쁜 출력은 반드시 막혀야 한다
# ---------------------------------------------------------------------------

base = briefing.build_template_briefing(first_contract)


def mutated(**changes) -> dict:
    copy = {k: (list(v) if isinstance(v, list) else v) for k, v in base.items()}
    copy.update(changes)
    return copy


negative_cases = [
    (
        "없는 숫자 생성 차단",
        mutated(summary=base["summary"] + " 반경 1.7km 내 대체 점포가 4곳 있습니다."),
        "숫자",
    ),
    (
        "없는 지역명 생성 차단",
        mutated(context_points=base["context_points"] + ["부산진구와 유사합니다."]),
        "지역명",
    ),
    (
        "없는 점포명 생성 차단",
        mutated(evidence_points=base["evidence_points"] + ["강남기업금융센터가 인접합니다."]),
        "점포",
    ),
    (
        "폐쇄 권고 차단",
        mutated(summary="본 점포는 통·폐합해야 합니다."),
        "금지표현",
    ),
    (
        "추천 표현 차단",
        mutated(summary="본 점포를 우선 검토 대상으로 추천합니다."),
        "금지표현",
    ),
    (
        "수익성 추론 차단",
        mutated(context_points=base["context_points"] + ["수익성이 낮은 편입니다."]),
        "금지표현",
    ),
    (
        "예측 차단",
        mutated(context_points=base["context_points"] + ["방문 고객이 감소할 것으로 예상됩니다."]),
        "금지표현",
    ),
    ("필드 누락 차단", {k: v for k, v in base.items() if k != "summary"}, "구조"),
    ("허용되지 않은 필드 차단", mutated(recommendation="폐쇄"), "구조"),
    ("항목 수 부족 차단", mutated(next_check_points=["하나만"]), "구조"),
]

for name, bad, keyword in negative_cases:
    outcome = validator.validate(bad, first_contract)
    check(f"[음성] {name}", not outcome.ok, f"errors={outcome.errors}")

# 정상 케이스는 반드시 통과해야 한다 (과차단 방지)
check("[양성] 정상 템플릿 통과", validator.validate(base, first_contract).ok,
      str(validator.validate(base, first_contract).errors))


# ---------------------------------------------------------------------------
# 결과 출력
# ---------------------------------------------------------------------------

print(f"dataset_version = {config.DATASET_VERSION}")
print(f"schema_version  = {config.SCHEMA_VERSION}")
print("-" * 68)
for name, ok, detail in checks:
    mark = "PASS" if ok else "FAIL"
    line = f"[{mark}] {name}"
    if not ok and detail:
        line += f"  <- {detail}"
    print(line)
print("-" * 68)
print(f"라벨 분포: {distribution}")
print(f"통과 {sum(1 for _, ok, _ in checks if ok)} / 전체 {len(checks)}")

if failures:
    print("\n실패 항목:")
    for item in failures:
        print(f"  - {item}")
    sys.exit(1)
print("\n전체 PASS")
