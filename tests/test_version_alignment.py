"""데이터셋 버전 표기가 config 하나로 연결되는지 확인합니다."""

import importlib.util
from pathlib import Path

from branchfit import config, data

ROOT = Path(__file__).resolve().parents[1]


def _load(rel):
    spec = importlib.util.spec_from_file_location(rel.replace("/", "_"), ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_branch_version_follows_dataset_version():
    assert config.BRANCH_DATASET_VERSION == config.DATASET_VERSION


def test_data_files_exist_for_current_version():
    assert data.REGION_FILE.exists(), data.REGION_FILE
    assert data.BRANCH_FILE.exists(), data.BRANCH_FILE


def test_scripts_use_same_version():
    assert _load("scripts/import_official_branches.py").VERSION == config.DATASET_VERSION
    assert _load("scripts/prepare_branches_v5.py").OUTPUT_VERSION == config.DATASET_VERSION
