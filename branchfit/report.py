"""One-page A4 review reference; uses only the current validated UI result."""
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

from . import briefing, config, distance


def build_review_pdf(contract: dict, outcome: dict, branch: dict, nearest=None) -> bytes:
    """Returns exactly one A4 page. Oversized content fails instead of being clipped."""
    font = "BranchFitNanumGothic"
    if font not in pdfmetrics.getRegisteredFontNames():
        font_path = Path(__file__).resolve().parents[1] / "assets/fonts/NanumGothic-Regular.ttf"
        pdfmetrics.registerFont(TTFont(font, str(font_path)))
    region, metric = contract["region"], contract["metrics"]
    source_status = (
        "공공 CSV 점포명·주소" if branch.get("name_source") == "official"
        else "합성 점포명 - 실명·주소 교체 전"
    )
    address = branch.get("address")
    address = address if isinstance(address, str) and address.strip() else "주소 미확인"
    ai = outcome["briefing"]["summary"]
    # The page is explicitly a condensed reference, not the full briefing export.
    if len(ai) > 360:
        ai = ai[:360] + "… (요약 일부; 전체 문장은 앱에서 확인)"
    sections = [
        ("기본정보", [
            f"{branch['branch_name']} / {branch['branch_type']} / {region['region_name']}",
            str(address), f"점포 데이터: {source_status}",
        ]),
        ("지역 지표 - 개별 점포 실적 아님", [
            f"총인구 {region['total_pop']:,}명 / 65세 이상 {region['elderly_pop']:,}명 / 사업체 {region['biz_count']:,}개",
            f"IBK 영업점 {region['ibk_branches']}개 / 사업체 1천 개당 {metric['biz_per_1k']}개 / 인구 1만 명당 {metric['pop_per_10k']}개",
            "사업체 시군구 확정 통계표 대조: 확인 필요",
        ]),
        ("거리", [distance.distance_text(nearest), distance.LIMIT_NOTE,
                    "좌표 확보된 비교 대상에 한함; 누락 점포가 있으면 전체 최근접을 보장하지 않음."]),
        ("AI 요약", [briefing.MODE_LABELS[outcome["mode"]], ai]),
        ("한계", [
            "자치구 집계 지표로 같은 구의 점포는 같은 값. 상대 라벨은 프로젝트 표현 기준.",
            "내부 이용실적·수익성·금융수요 미측정. 자료 시점이 다름. 공식 사전영향평가를 대신하지 않음.",
            "현업 니즈는 가설 / 현업 검증 전 / 디자이너 시안 반영 전.",
        ]),
        ("추가 확인", [x["text"] for x in contract["next_internal_data_candidates"]]),
        ("출처·기준시점", [
            f"{e['source']} / {e['reference_date'] or '기준시점 미확인'} / {e['url'] or 'URL 미확인'}"
            for key, e in config.EVIDENCE.items()
            if key in {"EV-POP", "EV-BIZ", "EV-IBK", "EV-IBK-XCHK"}
        ]),
    ]
    width, height = A4
    for size in (9, 8.5, 8):
        buf = BytesIO()
        canvas = Canvas(buf, pagesize=A4)
        canvas.setTitle("BranchFit 검토 참고 자료")
        body = ParagraphStyle("body", fontName=font, fontSize=size,
                              leading=size * 1.4, wordWrap="CJK", textColor=colors.HexColor("#334155"))
        heading = ParagraphStyle("heading", parent=body, fontSize=size + 1,
                                 textColor=colors.HexColor("#0f172a"))
        y, margin = height - 36, 36
        canvas.setFont(font, 17)
        canvas.drawString(margin, y, "BranchFit | 검토 참고 자료")
        y -= 23
        lines = [(None, ["판정·추천 없음 / 보완 중 프로토타입 / 작성 " +
                        datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="minutes")])]
        fits = True
        for title, items in lines + sections:
            if title:
                y -= 6
                p = Paragraph(escape(title), heading)
                _, h = p.wrap(width - 2 * margin, height)
                p.drawOn(canvas, margin, y - h)
                y -= h + 3
            for item in items:
                p = Paragraph(escape(str(item)), body)
                _, h = p.wrap(width - 2 * margin, height)
                if y - h < 42:
                    fits = False
                    break
                p.drawOn(canvas, margin, y - h)
                y -= h + 2
            if not fits:
                break
        if fits:
            canvas.setFont(font, 8)
            canvas.drawString(margin, 24, f"지역 {config.DATASET_VERSION} / 점포 {config.BRANCH_DATASET_VERSION} / 1 of 1")
            canvas.showPage()
            canvas.save()
            return buf.getvalue()
    raise ValueError("A4 한 장에 들어가지 않습니다. 입력 내용과 요약 길이를 확인하세요.")
