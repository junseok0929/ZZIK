# 찍 · 개발 환경

여행 사진을 모으고, 인물별로 찾고, 원본을 보존하며 보정본을 함께 확정하는 한국어 웹 앱입니다. 제공된 두 참고 이미지에 맞춰 파란색 데스크톱 사진 라이브러리와 코랄색 모바일 앨범·보정 화면을 구현했습니다.

## 가장 빠른 실행

### macOS 로컬 실행

Node.js 24 이상, Python 3.13, Homebrew PostgreSQL 17이 필요합니다. 이미 구성된 이 작업 공간에서는 아래 명령으로 시작합니다.

```bash
git clone https://github.com/seopseopi/ZZIK.git
cd ZZIK
# PostgreSQL 17이 없다면 한 번만 실행
brew install postgresql@17
bash scripts/dev.sh
```

접속: **http://127.0.0.1:5173**. 처음 화면에서 **샘플 앨범 둘러보기**를 누르세요. 이 명령은 의존성을 설치하고 로컬 PostgreSQL(54329), 마이그레이션, 샘플 데이터, API(8000), worker, 프론트(5173)를 준비합니다. `Ctrl+C`로 앱 프로세스를 종료해도 데이터는 남습니다. 같은 포트에서 이미 실행 중인 서버가 있다면 먼저 해당 서버를 종료하세요.

기존 `.env`가 외부 DB를 가리키면 로컬 PostgreSQL을 시작하지 않습니다. 샘플 데이터는 `DEMO_ENABLED=true`와 `FACE_ANALYSIS_PROVIDER=fixture`인 경우에만 준비합니다. 프론트 포트가 사용 중이면 다른 포트로 바꾸지 않고 오류로 종료합니다.

- 지수: `jisu@moacut.local`
- 민지: `minji@moacut.local`
- 서연: `seoyeon@moacut.local`
- 유진: `yujin@moacut.local`
- 공통 샘플 비밀번호: `MoacutDemo123!`

샘플 계정은 `python -m backend.app.seed`를 명시적으로 실행할 때만 생성됩니다. 일반 로그인과 동일한 인증을 거치며, 계정 전환 우회 API는 없습니다. seed는 재실행해도 기존 데이터를 덮어쓰거나 사진을 중복 생성하지 않습니다.

### Docker Compose

Docker가 설치되어 있으면 운영체제별 Python/PostgreSQL 설치 없이 실행할 수 있습니다.

```bash
cp .env.example .env  # .env가 이미 있으면 생략
docker compose up --build -d
docker compose exec api python -m app.seed
```

접속: **http://localhost:8080**. PostgreSQL과 파일은 Docker 볼륨에 저장됩니다. `docker compose down`은 볼륨을 보존합니다. Docker 구성은 코드 검토 완료이며 이 작업 환경에서 Docker 실행은 검증하지 않았습니다.

## 개별 실행

프로젝트 루트에서 환경을 설치합니다.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.lock
npm --prefix frontend ci
bash scripts/postgres-local.sh
.venv/bin/alembic -c backend/alembic.ini upgrade head
.venv/bin/python -m backend.app.seed
```

아래 세 명령은 각각 다른 터미널에서 실행합니다.

```bash
.venv/bin/uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
.venv/bin/python -m backend.app.worker
npm --prefix frontend run dev -- --host 127.0.0.1
```

API 문서: http://127.0.0.1:8000/docs. `/api/health/live`는 프로세스, `/api/health/ready`는 DB와 스키마 준비 상태를 확인합니다. worker는 서버와 별도 프로세스입니다. API만 켜면 파일 업로드는 저장되지만 분석은 대기합니다.

## 실제 연결과 샘플의 차이

기본 모드는 `STORAGE_BACKEND=local`, `FACE_ANALYSIS_PROVIDER=fixture`입니다. 샘플 사진 18종의 **정확한 파일 해시**가 일치할 때만 고정 분석을 반환하며 화면에 샘플 표시가 있습니다. 새 사진의 파일 저장·보정·수동 인물 지정·승인은 사용할 수 있지만 샘플에 없는 사진의 자동 분석은 `실제 분석 연결 필요`로 실패합니다. 이를 AI 성공으로 대체하지 않습니다.

실제 사진 분석은 `.env`에서 `FACE_ANALYSIS_PROVIDER=rekognition`, `AWS_REGION=...`을 설정하고 AWS SDK 표준 자격증명 또는 EC2 역할을 제공하세요. 파일을 S3에 저장하려면 `STORAGE_BACKEND=s3`, `S3_BUCKET=...`, `S3_PREFIX=...`도 설정합니다. 환경변수를 바꾸면 API와 worker를 함께 재시작하세요. 기존 로컬 파일이 자동으로 S3로 이전되지는 않으므로 기존 앨범 유지 시 별도의 파일 이전이 필요합니다.

등록 없는 인물 그룹은 Rekognition 컬렉션을 사용하는 별도 실제 어댑터입니다. fixture 모드에서는 분석 불가 이유가 표시됩니다. 자연어 검색은 등록 인물·태그·날짜를 조합하는 제한된 검색이며 의미 기반 검색이 아닙니다. GPS가 없는 사진에 장소를 지어내지 않습니다. 샘플 이미지는 디자인 참고 이미지의 추출본이므로 실제 촬영 메타데이터가 없습니다.

실제 AWS·S3·역지오코딩·얼굴 정확도 검증은 수행하지 않았습니다. 자세한 조건은 [AI 검증표](AI_VALIDATION.md), [AWS 배포](AWS_DEPLOYMENT.md)를 참고하세요.

앨범 상단의 **사진 정리 현황**에서 상태별 장수·실패 원인·저장된 분석 기록을 확인하고 실패한 사진만 다시 요청할 수 있습니다. **앨범 설정**에서는 이름·소개·여행 시간대, 초대코드와 멤버를 관리합니다. 사진 상세의 **사진 정보 → 사진 삭제**는 업로더 또는 앨범 소유자에게 표시됩니다.

연결 설정은 다음 명령으로 점검합니다. 기본 점검은 DB와 로컬 설정을 확인하며 AWS 호출이나 데이터 변경을 하지 않습니다. 실제 AWS 읽기 확인은 별도 옵션이 필요하며, 사진 분석의 성공을 보증하지 않습니다.

```bash
.venv/bin/python scripts/check_connections.py
# 자격 증명을 설정한 후 실제 AWS 읽기 연결 확인
.venv/bin/python scripts/check_connections.py --aws-check
```

## 검증 명령

```bash
# 전용 테스트 DB만 사용합니다. scripts/postgres-local.sh가 만들어 줍니다.
TEST_DATABASE_URL=postgresql+psycopg://moacut:moacut-local-only@127.0.0.1:54329/moacut_test .venv/bin/python -m pytest -q backend/tests
npm --prefix frontend run build
# API/worker/frontend 실행 상태에서
npm --prefix frontend run test:e2e
```

브라우저 테스트는 설치된 Google Chrome을 사용합니다. 자세한 실제 실행 결과와 제한은 [구현 상태](IMPLEMENTATION_STATUS.md)에 기록합니다.

## 문서

- [진행 상태·검증 결과](IMPLEMENTATION_STATUS.md)
- [두 계정으로 시연하기](DEMO_GUIDE.md)
- [구조·데이터·보정 정책](ARCHITECTURE.md)
- [API 계약](API_CONTRACT.md)
- [AWS 설정·배포·롤백](AWS_DEPLOYMENT.md)
- [샘플 자산 출처](ASSETS.md)
- [실제 AI 검증 여부](AI_VALIDATION.md)
- [연결 점검 명령·확인 범위](CONNECTIONS.md)

의존성은 lockfile로 고정합니다. 원본 파일은 보존하며 JPEG 보정본은 원본에서 다시 렌더링합니다. 승인 대상은 버전별로 기록하고, 인물 변경이나 승인 취소로 조건이 깨지면 최종본을 해제합니다.
