# K-Brief 키워드 데이터 수집기

매주 일요일 18:17(KST)에 GitHub Actions가 아래 두 가지를 모아 `data/`에 저장합니다. 19:37에 실행되는 "K-Brief 키워드 매니저" 예약 작업이 이 데이터를 읽어 키워드 뱅크의 수요 점수와 배정에 반영합니다.

| 출처 | 가져오는 것 | 출력 |
|---|---|---|
| 네이버 검색광고 API 키워드도구 | `seeds.txt`의 씨앗마다 연관 키워드, 월간 검색수(PC·모바일, 최근 30일), 광고 경쟁 정도 | `data/naver/top.csv`, `data/naver/latest.csv`, `data/naver/history/` |
| Google Search Console API | K-Brief의 검색어·페이지별 노출·클릭·평균 순위(최근 28일, 3일 지연) | `data/gsc/queries.csv`, `data/gsc/query_pages.csv`, `data/gsc/history/` |
| 요약 | 상위 키워드, 지난주 대비 급상승, 씨앗별 상위, K-Brief 검색어 | `data/summary.md` |
| 상태 | 소스별 마지막 실행 성공·실패와 사유 | `data/status.json` |

키가 없는 소스는 자동으로 건너뜁니다(예: 네이버만 먼저 연결해도 동작).

---

## 1. 네이버 검색광고 API 키 발급 (약 10분)

1. https://searchad.naver.com 에서 네이버 아이디로 광고주 가입
2. 오른쪽 위 **광고시스템** → 상단 **도구** → **API 사용 관리**
3. **네이버 검색광고 API 서비스 신청** → 약관 확인 후 발급
4. 화면의 세 값을 메모: **CUSTOMER_ID**, **액세스라이선스**, **비밀키**

> 광고를 집행하지 않아도 키워드도구 조회는 할 수 있습니다. 발급할 때 이용약관을 한 번 확인하세요.

## 2. Search Console 서비스 계정 만들기 (선택, 약 15분)

1. https://console.cloud.google.com → 새 프로젝트 만들기(예: `k-brief-gsc`)
2. **API 및 서비스 → 라이브러리**에서 "Google Search Console API" 검색 → **사용**
3. **IAM 및 관리자 → 서비스 계정 → 서비스 계정 만들기**(역할은 지정하지 않아도 됨)
4. 만든 서비스 계정 → **키 → 키 추가 → 새 키 만들기 → JSON** → 파일 다운로드
5. Search Console(https://search.google.com/search-console) → **k-brief.com** 속성 → **설정 → 사용자 및 권한 → 사용자 추가**
   - 이메일: 서비스 계정 이메일(…@…iam.gserviceaccount.com)
   - 권한: **제한됨**(읽기만 하면 충분)

## 3. GitHub 저장소 만들기

1. GitHub에서 새 저장소 생성 — 이름 예: `k-brief-keywords`, **Public**(키워드 매니저가 로그인 없이 읽기 위해)
2. 이 폴더의 파일을 올립니다.
   - `README.md`, `requirements.txt`, `seeds.txt`, `scripts/` 폴더: **Add file → Upload files**로 끌어 놓기
   - 워크플로 파일: 숨김 폴더라 끌어 놓기에서 빠질 수 있으니 **Add file → Create new file**에서 파일 이름 칸에 `.github/workflows/keyword-data.yml`을 입력하고 내용을 붙여 넣기
3. **Settings → Secrets and variables → Actions → New repository secret**으로 4개 등록

| 이름 | 값 |
|---|---|
| `NAVER_AD_CUSTOMER_ID` | CUSTOMER_ID |
| `NAVER_AD_ACCESS_LICENSE` | 액세스라이선스 |
| `NAVER_AD_SECRET_KEY` | 비밀키 |
| `GSC_SERVICE_ACCOUNT_JSON` | 2-4에서 받은 JSON 파일 내용 전체(선택) |

4. **Actions** 탭 → `keyword-data` → **Run workflow**로 첫 실행 → 몇 분 뒤 `data/summary.md`와 `data/status.json` 확인

## 알아 둘 점

- **공개 범위**: 저장소가 공개이므로 `data/`의 키워드·검색수, 그리고 Search Console을 연결하면 K-Brief의 검색어·노출 수치도 누구나 볼 수 있습니다. API 키는 Secrets에만 있고 저장소에는 올라가지 않습니다. Search Console 수치를 공개하고 싶지 않으면 `GSC_SERVICE_ACCOUNT_JSON`을 등록하지 마세요.
- **씨앗 키워드 관리**: `seeds.txt`에서 한 줄씩 더하거나 지웁니다. 키워드 매니저가 보고에서 추가할 씨앗을 제안합니다.
- **검색수 해석**: 키워드도구 값은 최근 30일 기준이며 `< 10`은 10회 미만입니다(순위 계산에서는 5로 근사, `lt10` 표시). "광고 경쟁"은 광고주 경쟁 정도이지 블로그 글 경쟁과는 다릅니다.
- **예약 실행이 멈췄을 때**: 공개 저장소는 오랫동안 활동이 없으면 예약 워크플로가 자동으로 꺼질 수 있습니다. 매주 데이터 커밋이 생기므로 보통은 유지되지만, 꺼지면 Actions 탭에서 다시 켜세요.
- **실패 확인**: `data/status.json`에 소스별 실패 사유가 남습니다(예: Search Console 403 → 서비스 계정 권한 추가 누락).
