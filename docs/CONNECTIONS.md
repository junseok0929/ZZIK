# 찍 연결 점검

저장소 루트에서 실행한다. 이 명령은 연결 상태를 **JSON으로만** 출력하며 설정·DB 데이터·이미지·AWS 리소스를 변경하지 않는다.

```sh
.venv/bin/python scripts/check_connections.py
.venv/bin/python scripts/check_connections.py --compact
```

기본 실행은 현재 `.env`와 프로세스 환경변수를 앱과 같은 설정 방식으로 읽는다. DB 접속은 수행하지만 AWS 서비스 API는 호출하지 않는다.

| 확인 항목 | 수행 방식 |
|---|---|
| 현재 모드 | `FACE_ANALYSIS_PROVIDER`, `STORAGE_BACKEND`, AWS 리전, S3 버킷 설정 여부 |
| DB | 읽기 전용 연결로 `SELECT 1`, 필요한 테이블·열·Alembic revision 확인 |
| 로컬 저장소 | 기존 폴더의 존재와 `os.access` 읽기·쓰기·접근 권한 확인; 폴더나 파일을 만들지 않음 |
| fixture | manifest 존재·읽기·해시 키와 얼굴 배열 형식 확인; 이미지 분석은 하지 않음 |
| AWS 자격 증명 | 환경변수의 키 쌍 존재, SDK가 읽는 활성 프로필의 키 쌍·런타임 제공자 설정 여부만 확인 |

기본 점검에서는 `get_credentials()`를 호출하지 않는다. 따라서 `credential_process` 명령 실행, SSO 갱신, 역할 수임, 컨테이너 자격 증명 endpoint, EC2 IMDS를 조회하지 않는다. 로컬 프로필 검사 동안만 `AWS_EC2_METADATA_DISABLED=true`를 적용하고 기존 값을 복원한다. EC2 역할이나 외부 인증 제공자를 확인하지 못했다는 결과가 실제 자격 증명 부재를 확정하지는 않는다. [Boto3 자격 증명 제공자 문서](https://docs.aws.amazon.com/boto3/latest/guide/credentials.html).

비밀번호·키·토큰·DB URL·프로필 이름·버킷 이름·AWS 계정 번호·ARN·컬렉션 이름·SDK 원문 오류는 출력하지 않는다. 오류는 고정된 코드와 안내로 변환한다. 폴더 쓰기 권한 확인은 실제 저장 테스트가 아니며, DB 준비 상태는 API·worker가 실행 중임을 증명하지 않는다.

## AWS 읽기 확인

다음 옵션을 명시한 경우에만 AWS SDK 표준 자격 증명 체인을 사용해 연결을 확인한다. 이 프로젝트 작업에서는 실제 `--aws-check` 호출을 실행하지 않았다.

```sh
.venv/bin/python scripts/check_connections.py --aws-check
```

실행하는 서비스 호출은 다음 세 종류뿐이다.

1. STS `get_caller_identity()` — 인증을 확인하고 응답의 계정·ARN은 버린다. [공식 명세](https://docs.aws.amazon.com/boto3/latest/reference/services/sts/client/get_caller_identity.html).
2. S3 `head_bucket(Bucket=...)` — 버킷이 설정된 경우에만 조회한다. 설정이 없으면 `skipped`다. 존재·접근 오류를 세부적으로 구별할 수 없는 경우도 있다. [공식 명세](https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/head_bucket.html).
3. Rekognition `list_collections(MaxResults=1)` — 첫 응답만 받고 컬렉션 이름은 출력하지 않는다. 추가 페이지를 조회하지 않는다. [공식 명세](https://docs.aws.amazon.com/boto3/latest/reference/services/rekognition/client/list_collections.html).

이미지 전송, DetectFaces·CompareFaces·DetectLabels, 인덱싱, 컬렉션 생성, 객체 저장·삭제는 수행하지 않는다. SDK 서비스 연결·읽기 timeout은 각각 3초이며 재시도를 하지 않는다. 표준 자격 증명 체인이 사용하는 SSO·역할 인증 갱신이나 사용자가 설정한 credential process에는 별도 소요 시간이 생길 수 있다.

읽기 점검에는 해당 권한이 필요하다. 특히 `rekognition:ListCollections`는 실제 얼굴 비교에 필요한 권한과 별도이므로 운영 역할에 없을 수 있다. 이 경우 진단은 실패하지만 얼굴 비교 권한의 유무까지 결론 내리지 않는다. 반대로 세 읽기 점검이 성공해도 얼굴 분석 권한, S3 객체 쓰기·삭제 권한, 이미지 분석 정확도까지 확인한 것은 아니다. 그 범위는 [AI_VALIDATION.md](AI_VALIDATION.md)의 검증 절차를 따른다.

## JSON과 종료 코드

최상위 `schema_version`은 현재 `1`이다. `mode`, `safety`, `checks`, `blockers`, `summary`가 정상 결과에 포함된다. 환경변수 형식·의존성 오류로 점검 자체를 시작하지 못하면 `error.code=PREFLIGHT_FAILED`를 반환한다. 원문 예외는 출력하지 않는다.

- `summary.selected_checks_passed`: 현재 선택한 모드에 필요한 실행된 점검에 차단 오류가 없는지 나타낸다.
- `summary.configured_mode_ready`: 확인한 범위에서 `true`/`false`. 실제 AWS 모드를 선택하고 `--aws-check`를 실행하지 않았다면 연결 미확인으로 `null`이다.
- `summary.aws_reads_verified`: 명시적으로 요청한 AWS 읽기 점검의 통과 여부다. 버킷 미설정으로 생략된 S3는 통과 대상에 포함하지 않으므로 `checks.aws.s3_bucket`도 함께 확인한다.
- `summary.photo_analysis_verified`: 이 명령은 사진을 분석하지 않으므로 항상 `false`다.
- `blockers[].affects_selected_mode`: 현재 실행 모드를 막는 항목인지 나타낸다. 예를 들어 fixture/local에서 S3 버킷이 없어도 로컬 실행을 막지는 않는다.

종료 코드 `0`은 현재 실행한 필수 점검이 통과했음을 의미한다. `1`은 해당 점검 실패 또는 명령 실행 오류다. AWS 검증을 생략한 상태에서도 로컬 점검은 `0`일 수 있으므로 실제 연결 판단에는 JSON의 상태를 함께 사용한다. 알 수 없는 CLI 옵션은 argparse의 일반 종료 코드 `2`를 사용한다.

## 이번 환경의 확인 결과

2026-09-17 기본 점검에서 다음 상태를 확인했다. 이후 설정이나 실행 환경이 바뀌면 명령을 다시 실행해야 한다.

- 현재 모드: `fixture` + `local`, 리전 `ap-northeast-2`.
- PostgreSQL 연결·필요 스키마·현재 migration 확인 성공.
- 로컬 저장 폴더 존재와 읽기·쓰기 접근 권한 확인 성공.
- 샘플 manifest 18개 항목 읽기 성공.
- 로컬 AWS 키 쌍과 런타임 제공자 설정은 발견되지 않음. EC2 역할은 조회하지 않음.
- S3 버킷 미설정. 실제 AWS 읽기 또는 사진 분석은 실행하지 않음.

따라서 현재 로컬 저장·샘플 흐름은 준비되어 있지만 일반 사진을 실제 AI로 분석하려면 AWS 자격 증명과 권한을 제공한 뒤 `FACE_ANALYSIS_PROVIDER=rekognition`으로 명시적으로 설정해야 한다. S3 사용은 별도로 버킷과 저장 모드를 설정한다. 이 점검 명령은 모드를 자동으로 전환하지 않는다.

구현 검증은 모의 AWS 응답과 임시 로컬 파일로 수행한다.

```sh
.venv/bin/python -m pytest backend/tests/test_connections.py -q
```
