"""2단계: 점포 검토 참고 자료 A4 1장 PDF 회귀 테스트 (추가만)."""
import re
from io import BytesIO

import pytest
from pypdf import PdfReader

from branchfit import config, pipeline, report, validator
from branchfit.briefing import build_template_briefing


@pytest.fixture(scope="module")
def tables():
    return pipeline.build_tables()


def _make(tables, idx=0, nearest=None, summary=None):
    regions, branches = tables
    branch = branches.iloc[idx].to_dict()
    contract = pipeline.build_contract_for_branch(regions, branches, branch["branch_id"])
    b = build_template_briefing(contract)
    if summary is not None:
        b = {**b, "summary": summary}
    outcome = {"briefing": b, "mode": "template"}
    pdf = PdfReader(BytesIO(report.build_review_pdf(contract, outcome, branch, nearest)))
    return pdf, branch


def _text(pdf):
    return "\n".join(p.extract_text() for p in pdf.pages)


@pytest.mark.parametrize("idx", [0, 50, 100, -1])
def test_pdf_is_single_a4_page(tables, idx):
    pdf, _ = _make(tables, idx)
    assert len(pdf.pages) == 1


@pytest.mark.parametrize("idx", [0, 50, 100, -1])
def test_korean_branch_name_and_seven_sections_extract(tables, idx):
    pdf, branch = _make(tables, idx)
    text = _text(pdf)
    assert report.TITLE in text
    assert branch["branch_name"] in text
    for heading in ["1. 점포 기본정보", "2. 지역 맥락 지표", "3. 가장 가까운 다른 IBK 영업점",
                    "4. AI 브리핑", "5. 한계", "6. 출처", "7. 기준시점"]:
        assert heading in text
    assert "점포 2025-12-31" in text
    assert "인구 2026년 7월" in text
    assert "사업체 2024년" in text


def test_no_forbidden_expressions_in_pdf_body(tables):
    pdf, _ = _make(tables)
    result = validator.ValidationResult()
    validator.check_forbidden(_text(pdf).replace("\n", ""), result)
    assert result.ok, result.errors
    for word in ["판정", "추천", "권고", "대구"]:
        assert word not in _text(pdf)


def test_forbidden_summary_blocks_pdf(tables):
    with pytest.raises(ValueError, match="금지표현"):
        _make(tables, summary="이 점포는 폐쇄해야 합니다.")


def test_missing_coordinates_shows_unconfirmed(tables):
    pdf, _ = _make(tables, nearest=None)
    assert "좌표 미확인" in _text(pdf)


def test_nearest_shows_name_and_km_without_coordinates(tables):
    _, branches = tables
    other = branches.iloc[1]["branch_name"]
    nearest = {"branch_id": "x", "branch_name": other, "distance_km": 0.83,
               "lat": 37.5701234, "lon": 126.9765432}
    pdf, _ = _make(tables, nearest=nearest)
    text = _text(pdf)
    assert f"{other} · 0.83km" in text
    assert "좌표 미확인" not in text
    assert "37.57" not in text and "126.97" not in text
    assert not re.search(r"\b3[3-8]\.\d{4,}", text)


def test_full_summary_not_truncated(tables):
    long = "광화문 소속 자치구의 지역 맥락을 설명하는 문장입니다. " * 6
    pdf, _ = _make(tables, summary=long.strip())
    assert "요약 일부" not in _text(pdf)
    assert len(pdf.pages) == 1


def test_overflow_drops_items_in_order_not_font_size(tables):
    """요약이 길어지면 출처 URL → 거리 보조문구 → 사업체 대조 문구 순으로 빠지고,
    핵심 항목과 글자 크기(9pt)는 유지됩니다."""
    assert report.BODY_SIZE == 9
    assert report.DROP_ORDER == ("source_url", "distance_note", "biz_check_note")
    markers = ["https://", "좌표가 확보된", "대조: 확인 필요"]
    dropped_seen = [False, False, False]
    for n in range(60, 130, 2):
        try:
            pdf, branch = _make(tables, summary=("자치구 단위 지역 맥락 설명 문장입니다. " * n).strip())
        except ValueError:
            break
        assert len(pdf.pages) == 1
        text = _text(pdf)
        present = [m in text for m in markers]
        # 뒤 순위 항목이 빠졌다면 앞 순위 항목은 반드시 먼저 빠져 있어야 함
        for i in range(1, 3):
            if not present[i]:
                assert not present[i - 1]
        for i, p in enumerate(present):
            dropped_seen[i] |= not p
        for core in [branch["branch_name"], "좌표 미확인", "현업 검증 전", "15006875", "2025-12-31"]:
            assert core in text
    assert all(dropped_seen)


def test_too_long_raises_instead_of_clipping(tables):
    with pytest.raises(ValueError, match="A4 한 장"):
        _make(tables, summary="설명 문장입니다. " * 400)
