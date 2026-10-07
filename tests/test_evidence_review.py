"""Regression checks for missing evidence, distance failure and reference export."""
from io import BytesIO
from pathlib import Path

import pandas as pd
import pytest
from pypdf import PdfReader
from streamlit.testing.v1 import AppTest

from branchfit import data, distance, geocode, pipeline, report
from branchfit.briefing import build_template_briefing


def test_official_data_has_addresses_and_no_persisted_coordinates():
    regions, branches = data.load_all()
    assert set(branches["name_source"]) == {"official"}
    assert branches["address"].str.startswith("서울특별시 ").all()
    assert not {"lat", "lon", "latitude", "longitude"}.intersection(branches.columns)
    assert not branches["branch_name"].str.contains("기업금융센터|이동점포").any()
    assert len(branches) == int(regions["ibk_branches"].sum())


def test_failed_and_invalid_coordinates_do_not_become_distances():
    branches = pd.DataFrame({"branch_id": ["a", "b", "c"], "branch_name": ["가", "나", "다"]})
    full = distance.attach_coords(branches, {"a": (float("nan"), 127), "b": (91, 127), "c": (37, float("inf"))})
    assert set(full["coord_status"]) == {"missing"}
    assert distance.nearest_other_branch(full, "a") is None
    assert "좌표 미확인" in distance.distance_text(None)
    assert geocode.geocode_address("a", "key", http_get=lambda u, h: {"documents": [{"x": "127", "y": "nan"}]}) is None


def test_no_key_never_calls_injected_geocoder():
    branches = pd.DataFrame({"branch_id": ["a"], "address": ["서울특별시 종로구 1"]})
    def fail(*args):
        raise AssertionError("must not call")
    assert geocode.geocode_branches(branches, None, geocoder=fail) == {"a": None}


def test_one_page_a4_reference_contains_provenance_and_limits():
    regions, branches = pipeline.build_tables()
    branch = branches.iloc[0].to_dict()
    contract = pipeline.build_contract_for_branch(regions, branches, branch["branch_id"])
    outcome = {"briefing": build_template_briefing(contract), "mode": "template"}
    pdf = PdfReader(BytesIO(report.build_review_pdf(contract, outcome, branch)))
    assert len(pdf.pages) == 1
    page = pdf.pages[0]
    assert float(page.mediabox.width) == pytest.approx(595.28, abs=.1)
    assert float(page.mediabox.height) == pytest.approx(841.89, abs=.1)
    text = page.extract_text()
    for value in ["검토 참고 자료", branch["branch_name"], branch["address"], "좌표 미확인", "현업 검증 전", "2025-12-31", "15006875"]:
        assert value in text


def test_app_missing_key_shows_explicit_status_and_cards(monkeypatch):
    monkeypatch.delenv("KAKAO_REST_API_KEY", raising=False)
    monkeypatch.delenv("BRANCHFIT_LLM_API_KEY", raising=False)
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run(timeout=30)
    assert not app.exception
    assert any("좌표 미확인" in c.value for c in app.caption)
    assert any("현업 검증 전" in c.value for c in app.info)
    for title in ["**근거**", "**한계**", "**추가 확인**"]:
        assert any(c.value == title for c in app.markdown)
