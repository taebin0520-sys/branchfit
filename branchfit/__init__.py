"""BranchFit — 개별 점포 통·폐합 검토 지원 AI 에이전트 (P0).

레이어 구조
    config    고정 상수 (기획서의 '정한 값')
    data      원천 CSV 로딩 + 정합성 검증
    metrics   결정론적 지역 맥락 지표 계산
    peers     규모 유사 Peer 자치구 선정
    review    검토 사유 / notable indicator 선정
    contract  AI 입력 JSON 빌드 (여기부터 pandas 없음)
    validator AI 출력 검증 (수치 대조 / 고유명 / 금지표현)
    briefing  LLM 호출 + 결정론적 템플릿 fallback
    pipeline  위 순서를 잇는 조립부
"""

from . import config  # noqa: F401

__all__ = ["config"]
__version__ = "0.1.0"
