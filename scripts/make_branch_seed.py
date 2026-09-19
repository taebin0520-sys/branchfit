"""개별 점포(Point Data Layer) 씨드 CSV를 생성하는 스크립트.

왜 스크립트로 만드는가
----------------------
기획서 5.1의 Point Data Layer는 182개 개별 점포를 다룹니다.
182줄을 손으로 관리하면 자치구별 합계가 지역 데이터(ibk_branches)와
어긋나기 쉽습니다. (v2 QA에서 실제로 발생한 유형의 오류)

그래서 '자치구별 점포 수'를 단일 출처(seoul_districts CSV)로 두고,
점포 목록은 거기서 파생 생성합니다. 합계 불일치가 구조적으로 불가능해집니다.

주의: 점포명은 합성(synthetic) 값입니다.
기획서 5.1 "미확정 정보는 생성하지 않습니다" 원칙에 따라
좌표·주소·운영상태 같은 미확보 필드는 아예 만들지 않고,
점포명도 name_source 컬럼에 synthetic_placeholder로 표시합니다.

실행:
    python scripts/make_branch_seed.py
"""

from __future__ import annotations

import csv
from pathlib import Path

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"
REGION_CSV = RAW_DIR / "seoul_districts_2026-09-08_v3.csv"
BRANCH_CSV = RAW_DIR / "ibk_branches_2026-09-08_v3.csv"

# 자치구별 점포명 후보 (해당 자치구 내 지역명 기반, 합성 라벨용).
# 리스트 길이는 자치구별 ibk_branches 이상이어야 합니다.
LOCALITY_NAMES: dict[str, list[str]] = {
    "종로구": ["종로", "광화문", "혜화", "명륜", "평창", "사직", "무악", "창신"],
    "중구": [
        "을지로", "명동", "충무로", "남대문", "장충", "신당", "황학",
        "다산", "광희", "회현", "서울역", "중림", "청구",
    ],
    "용산구": ["한남", "이태원", "후암", "효창", "원효로"],
    "성동구": ["왕십리", "성수", "행당", "금호", "옥수", "마장", "용답"],
    "광진구": ["구의", "자양", "화양", "중곡", "군자"],
    "동대문구": ["청량리", "제기", "전농", "장안", "답십리", "휘경"],
    "중랑구": ["면목", "상봉", "중화", "묵동", "신내"],
    "성북구": ["돈암", "장위", "석관", "월곡", "안암"],
    "강북구": ["미아", "수유", "번동", "우이"],
    "도봉구": ["창동", "방학", "쌍문", "도봉"],
    "노원구": ["상계", "중계", "하계", "공릉", "월계"],
    "은평구": ["불광", "연신내", "응암", "수색", "구산"],
    "서대문구": ["홍제", "연희", "신촌", "충정로", "홍은"],
    "마포구": ["공덕", "아현", "합정", "망원", "상암", "성산", "서교"],
    "양천구": ["목동", "신정", "신월", "오목교", "목동중앙", "양천"],
    "강서구": ["화곡", "등촌", "가양", "발산", "방화", "마곡", "공항", "염창"],
    "구로구": [
        "구로", "신도림", "개봉", "오류", "고척", "가리봉", "항동", "온수",
        "구로디지털",
    ],
    "금천구": [
        "가산", "독산", "시흥", "가산디지털", "벚꽃로", "금천", "남구로",
        "시흥대로",
    ],
    "영등포구": [
        "여의도", "영등포", "당산", "대림", "신길", "양평", "문래", "도림",
        "여의도중앙", "영등포시장", "선유로", "국회대로",
    ],
    "동작구": ["노량진", "사당", "상도", "흑석", "신대방"],
    "관악구": ["봉천", "신림", "서울대입구", "난곡", "남현"],
    "서초구": [
        "서초", "방배", "반포", "잠원", "양재", "내곡", "우면", "남부터미널",
        "교대", "서초중앙", "효령로",
    ],
    "강남구": [
        "역삼", "삼성", "대치", "논현", "신사", "청담", "압구정", "도곡",
        "개포", "일원", "수서", "세곡", "자곡", "학동", "언주", "선릉",
        "테헤란로", "강남대로",
    ],
    "송파구": [
        "잠실", "가락", "문정", "석촌", "방이", "오금", "풍납", "삼전",
        "거여", "마천",
    ],
    "강동구": ["천호", "길동", "둔촌", "암사", "성내", "고덕"],
}

# 출장소 4곳 (기획서 5.1: 출장소 4곳은 최종 포함 대상).
# (자치구, 해당 자치구 내 몇 번째 점포인가) — 결정론적으로 고정합니다.
SUB_OFFICES = {
    ("강남구", 18),
    ("중구", 13),
    ("영등포구", 12),
    ("구로구", 9),
}


def load_regions() -> list[dict[str, str]]:
    with REGION_CSV.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def build_rows(regions: list[dict[str, str]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for region in regions:
        name = region["region_name"]
        count = int(region["ibk_branches"])
        names = LOCALITY_NAMES[name]
        if len(names) < count:
            raise ValueError(
                f"{name}: 점포명 후보 {len(names)}개 < 필요 {count}개"
            )
        for seq in range(1, count + 1):
            is_sub = (name, seq) in SUB_OFFICES
            branch_type = "출장소" if is_sub else "영업점"
            rows.append(
                {
                    "branch_id": f"IBK-{region['region_code']}-{seq:02d}",
                    "branch_name": f"{names[seq - 1]}{branch_type}",
                    "branch_type": branch_type,
                    "region_code": region["region_code"],
                    "region_name": name,
                    "name_source": "synthetic_placeholder",
                }
            )
    return rows


def main() -> None:
    regions = load_regions()
    rows = build_rows(regions)

    expected = sum(int(r["ibk_branches"]) for r in regions)
    if len(rows) != expected:
        raise AssertionError(f"점포 수 불일치: {len(rows)} != {expected}")

    with BRANCH_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    sub = sum(1 for r in rows if r["branch_type"] == "출장소")
    print(f"생성 완료: {BRANCH_CSV}")
    print(f"  총 점포 수: {len(rows)}  (영업점 {len(rows) - sub} / 출장소 {sub})")


if __name__ == "__main__":
    main()
