"""새로 만든 코드·문구에 판단·권고성 표현이 들어가지 않았는지 확인합니다."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = ["대체", "폐쇄", "통합"]
NEW_FILES = [
    "branchfit/distance.py",
    "branchfit/geocode.py",
    "branchfit/branch_prep.py",
    "scripts/prepare_branches_v5.py",
]


def test_new_modules_have_no_forbidden_words():
    for rel in NEW_FILES:
        text = (ROOT / rel).read_text(encoding="utf-8")
        for word in FORBIDDEN:
            assert word not in text, f"{rel} 에 '{word}' 포함"
