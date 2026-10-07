# 1단계 진행 메모

## 코드로 끝난 것 (68 tests 통과)
- branchfit/distance.py : 직선거리, 가장 가까운 다른 IBK 영업점, 좌표 붙이기, 화면 문구
- branchfit/geocode.py : 카카오 주소→좌표 (실행 중 호출, 파일 저장 없음, 키 없으면 None)
- branchfit/branch_prep.py + scripts/prepare_branches_v5.py : 공공데이터 CSV → v5 변환 (단계별 행 수 리포트)
- config.BRANCH_DATASET_VERSION : 점포 파일 버전 분리 (기본값은 기존과 동일)
- app.py : 점포 기본정보 아래 거리 영역 추가 (주소 없음 / 키 없음 / 버튼 후 계산)

## 사용자가 직접 해야 하는 것
1. 공공데이터포털 15006875 CSV를 data/raw/ 에 넣기
2. `python scripts/prepare_branches_v5.py --csv <파일> --list-columns` 로 컬럼 확인
3. ATM 구분 기준을 정해 `--dry-run` 실행 → 단계별 행 수 확인 (② 185 / ③ 182 기대)
4. 통과하면 --dry-run 없이 실행 → config.BRANCH_DATASET_VERSION 을 안내된 값으로 변경
5. 카카오 REST API 키 발급 → .streamlit/secrets.toml 또는 환경변수 KAKAO_REST_API_KEY
6. 카카오 약관 원문에서 좌표 저장·표시 조건 직접 확인 [확인 필요]

## 아직 실제로 돌려 보지 못한 것
- 실제 CSV 컬럼 / ATM 구분 / 필터 결과
- 실제 카카오 API 응답 (x=경도, y=위도 가정은 공식 문서로 재확인 필요)
- 거리 버튼의 실제 클릭 동작 (함수 단위 테스트만 통과)
