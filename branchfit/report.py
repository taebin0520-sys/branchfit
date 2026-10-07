"""점포 검토 참고 자료 - A4 한 장 PDF.

현재 화면에 표시된 검증 결과만 사용합니다(새 수치를 만들지 않음).
- 글자 크기는 고정합니다. 한 장을 넘으면 우선순위가 낮은 항목부터 뺍니다.
- 본문 전체에 기존 금지표현 검사(validator.check_forbidden)를 그대로 적용합니다.
- 좌표값은 출력하지 않습니다(가장 가까운 점포명과 km만).
- 파일을 서버에 저장하지 않고 bytes로 돌려줍니다(화면 다운로드 버튼용).
"""
from __future__ import annotations

from datetime import datetime
from io import BytesIO
from pathlib import Path
from zoneinfo import ZoneInfo
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph

from . import briefing, config, distance, validator

TITLE = "점포 검토 참고 자료"
FONT_NAME = "BranchFitNanumGothic"
FONT_PATH = Path(__file__).resolve().parents[1] / "assets/fonts/NanumGothic-Regular.ttf"
BODY_SIZE = 9  # 고정. 넘치면 글자를 줄이지 않고 항목을 줄입니다.

#: 한 장을 넘을 때 빼는 순서(앞에서부터 차례로 누적 제외).
DROP_ORDER = ("source_url", "distance_note", "biz_check_note")

_SOURCE_KEYS = ("EV-POP", "EV-BIZ", "EV-IBK")


def _register_font() -> str:
    if FONT_NAME not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(FONT_NAME, str(FONT_PATH)))
    return FONT_NAME


def _year_month(date_str: str | None) -> str:
    if not date_str:
        return "기준시점 미확인"
    y, m = date_str[:4], date_str[5:7]
    return f"{y}년 {int(m)}월"


def _year(date_str: str | None) -> str:
    return f"{date_str[:4]}년" if date_str else "기준시점 미확인"


def reference_dates_text() -> str:
    """데이터별 기준시점. 점포=일자, 인구=기준월, 사업체=기준연."""
    ev = config.EVIDENCE
    return (
        f"점포 {ev['EV-IBK']['reference_date'] or '기준시점 미확인'} / "
        f"인구 {_year_month(ev['EV-POP']['reference_date'])} / "
        f"사업체 {_year(ev['EV-BIZ']['reference_date'])}"
    )


def build_sections(contract: dict, outcome: dict, branch: dict, nearest=None,
                   drop: frozenset[str] = frozenset()) -> list[tuple[str, list[str]]]:
    """PDF 7개 항목. drop 에 든 선택 항목은 뺍니다."""
    region, metric = contract["region"], contract["metrics"]
    address = branch.get("address")
    address = address if isinstance(address, str) and address.strip() else "주소 미확인"
    source_status = (
        "공공 CSV 점포명·주소" if branch.get("name_source") == "official"
        else "합성 점포명 - 실명·주소 교체 전"
    )

    indicators = [
        f"총인구 {region['total_pop']:,}명 / 65세 이상 {region['elderly_pop']:,}명",
        f"사업체 1천 개당 IBK 영업점 {metric['biz_per_1k']}개 ({contract['result']['biz_density_label']})",
        f"인구 1만 명당 IBK 영업점 {metric['pop_per_10k']}개 ({contract['result']['pop_density_label']})",
    ]
    if "biz_check_note" not in drop:
        indicators.append("사업체 시군구 확정 통계표 대조: 확인 필요")

    near = [distance.distance_text(nearest)]
    if "distance_note" not in drop:
        near.append("좌표가 확보된 점포끼리만 비교하며, 누락 점포가 있으면 전체 최근접을 보장하지 않습니다.")

    sources = [f"점포 데이터 상태: {source_status}"]
    for key in _SOURCE_KEYS:
        e = config.EVIDENCE[key]
        line = e["source"]
        if "source_url" not in drop and e.get("url"):
            line += f" / {e['url']}"
        sources.append(line)

    return [
        ("1. 점포 기본정보", [
            f"점포명 {branch['branch_name']} / 유형 {branch['branch_type']} / 소속 자치구 {region['region_name']}",
            f"주소 {address}",
        ]),
        ("2. 지역 맥락 지표 (자치구 단위, 개별 점포 실적 아님)", indicators),
        ("3. 가장 가까운 다른 IBK 영업점", near),
        ("4. AI 브리핑", [briefing.MODE_LABELS[outcome["mode"]], outcome["briefing"]["summary"]]),
        ("5. 한계", [
            distance.LIMIT_NOTE + ", 자치구 단위 지표(같은 구의 점포는 같은 값)",
            "내부 이용실적·수익성·금융수요 미측정. 공식 사전영향평가를 대신하지 않음.",
            "현업 니즈는 가설 / 현업 검증 전.",
        ]),
        ("6. 출처", sources),
        ("7. 기준시점", [reference_dates_text()]),
    ]


def body_text(sections: list[tuple[str, list[str]]], subtitle: str = "") -> str:
    parts = [TITLE, subtitle]
    for title, items in sections:
        parts.append(title)
        parts.extend(items)
    return "\n".join(p for p in parts if p)


def _render(sections, subtitle: str) -> bytes | None:
    """한 장에 들어가면 PDF bytes, 넘치면 None."""
    font = _register_font()
    width, height = A4
    margin = 36
    buf = BytesIO()
    canvas = Canvas(buf, pagesize=A4)
    canvas.setTitle(TITLE)
    body = ParagraphStyle("body", fontName=font, fontSize=BODY_SIZE, leading=BODY_SIZE * 1.4,
                          wordWrap="CJK", textColor=colors.HexColor("#334155"))
    heading = ParagraphStyle("heading", parent=body, fontSize=BODY_SIZE + 1,
                             textColor=colors.HexColor("#0f172a"))
    y = height - margin
    canvas.setFont(font, 17)
    canvas.drawString(margin, y - 12, TITLE)
    y -= 28
    canvas.setFont(font, BODY_SIZE)
    canvas.drawString(margin, y - BODY_SIZE, subtitle)
    y -= BODY_SIZE + 8

    for title, items in sections:
        y -= 6
        for text, style in [(title, heading)] + [(i, body) for i in items]:
            p = Paragraph(escape(str(text)), style)
            _, h = p.wrap(width - 2 * margin, height)
            if y - h < 42:
                return None
            p.drawOn(canvas, margin, y - h)
            y -= h + 2

    canvas.setFont(font, 8)
    canvas.drawString(margin, 24, f"지역 {config.DATASET_VERSION} / 점포 {config.BRANCH_DATASET_VERSION} / 1 of 1")
    canvas.showPage()
    canvas.save()
    return buf.getvalue()


def build_review_pdf(contract: dict, outcome: dict, branch: dict, nearest=None) -> bytes:
    """A4 한 장 PDF bytes. 금지표현이 있거나 항목을 줄여도 넘치면 ValueError."""
    subtitle = ("서울 25개 자치구 / 보완 중 프로토타입 / 작성 "
                + datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="minutes"))

    full = build_sections(contract, outcome, branch, nearest)
    check = validator.ValidationResult()
    validator.check_forbidden(body_text(full, subtitle), check)
    if not check.ok:
        raise ValueError("PDF 본문에 금지표현이 있어 만들지 않습니다: " + "; ".join(check.errors))

    drop: set[str] = set()
    for step in (None,) + DROP_ORDER:
        if step:
            drop.add(step)
        pdf = _render(build_sections(contract, outcome, branch, nearest, frozenset(drop)), subtitle)
        if pdf is not None:
            return pdf
    raise ValueError("A4 한 장에 들어가지 않습니다. AI 요약 길이를 확인하세요.")
