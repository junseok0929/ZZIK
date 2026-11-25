# 1단계 배포: S3 + EC2 + Lambda + Claude API

사진은 S3에, 앱(Nginx·FastAPI·PostgreSQL)은 퍼블릭 EC2 한 대에 두고, 사진 분석은 S3 업로드 이벤트로 실행되는 Lambda가 Claude API로 한다.

```
사용자 → EC2(Nginx·FastAPI·PostgreSQL) → S3(display.jpg 저장)
                 ↑                              │ 업로드 이벤트
                 └──── 분석 결과(토큰) ──── Lambda ──→ Claude API
```

- 리전은 모두 서울(`ap-northeast-2`). VPC는 기본 VPC의 퍼블릭 서브넷만 쓴다.
- Claude는 사진의 장면·태그·인원 수만 분류한다. 사람이 누구인지는 판별하지 않으므로 인물 연결은 앱에서 직접 지정한다.
- 아래 `BUCKET`, `ACCOUNT_ID`, `EC2_IP` 같은 대문자 값은 본인 값으로 바꾼다.

## 0. 준비물

| 항목 | 내용 |
| --- | --- |
| 권한 | EC2·S3·Lambda·IAM 역할 연결·CloudWatch Logs·Budgets (역할 생성이 막혀 있으면 아래 두 역할을 미리 받는다) |
| Claude API 키 | 강사에게 받는다. 채팅·저장소에 붙여 넣지 않고 Lambda 환경 변수에만 넣는다 |
| 내부 토큰 | `openssl rand -hex 32` 로 만든 값. EC2 `.env`와 Lambda에 같은 값을 넣는다 |

## 1. 예산 알림

콘솔 → Billing → Budgets 에서 월 예산(예: 1만 원)과 80% 알림을 만든다.

## 2. S3 버킷

```bash
aws s3api create-bucket --bucket BUCKET --region ap-northeast-2 \
  --create-bucket-configuration LocationConstraint=ap-northeast-2
aws s3api put-public-access-block --bucket BUCKET --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
```

사진은 공개하지 않는다. 앱이 권한을 확인한 뒤 120초짜리 서명 URL로만 내려준다.

## 3. IAM 역할 두 개

| 역할 | 신뢰 대상 | 붙일 정책 |
| --- | --- | --- |
| `zzik-ec2-role` (인스턴스 프로파일) | EC2 | `iam/ec2-s3-policy.json` (BUCKET 치환) |
| `zzik-lambda-role` | Lambda | `iam/lambda-s3-read-policy.json` (BUCKET 치환) + AWS 관리형 `AWSLambdaBasicExecutionRole` |

EC2와 Lambda 모두 액세스 키 없이 역할로 S3에 접근한다.

## 4. EC2

- AMI: Amazon Linux 2023, 유형: `t3.small` 이상, 기본 VPC의 퍼블릭 서브넷, 공인 IP 자동 할당
- IAM 인스턴스 프로파일: `zzik-ec2-role`
- 보안 그룹 인바운드: HTTP 80 (0.0.0.0/0), SSH 22 (**내 IP만**). PostgreSQL 5432는 열지 않는다
- 사용자 데이터: `ec2-user-data.sh` 내용을 붙여 넣는다 (Docker, Compose, 스왑, 저장소 clone)

## 5. 찍 배포 (EC2에 SSH 접속 후)

```bash
cd ~/zzik
cp deploy/aws-stage1/env.aws.example .env
vi .env        # POSTGRES_PASSWORD, S3_BUCKET, INTERNAL_API_TOKEN, ALLOWED_ORIGINS=http://EC2_IP
chmod 600 .env
docker compose up --build -d
curl --fail http://localhost/api/health/ready
```

브라우저에서 `http://EC2_IP` 로 접속해 회원가입 → 앨범 생성 → 사진 업로드 → 보정 → 승인 → 다운로드를 확인한다. 이 시점에는 분석 상태가 "대기"로 남는다(Lambda를 아직 연결하지 않았으므로).

## 6. Lambda

```bash
cd lambda/analyze_photo && zip -j /tmp/analyze_photo.zip handler.py && cd -
aws lambda create-function --function-name zzik-analyze-photo --region ap-northeast-2 \
  --runtime python3.12 --handler handler.lambda_handler --zip-file fileb:///tmp/analyze_photo.zip \
  --role arn:aws:iam::ACCOUNT_ID:role/zzik-lambda-role --timeout 120 --memory-size 256 \
  --environment "Variables={CLAUDE_API_KEY=강사에게_받은_키,RESULT_URL=http://EC2_IP/api/internal/analysis-results,INTERNAL_API_TOKEN=EC2와_같은_토큰,CLAUDE_MODEL=claude-haiku-5-5,CLAUDE_TEMPERATURE=0}"
# 한꺼번에 많이 호출되지 않도록 동시 실행 상한
aws lambda put-function-concurrency --function-name zzik-analyze-photo --reserved-concurrent-executions 5
```

- 환경 변수에 키를 넣을 때는 터미널 기록에 남지 않도록 콘솔(Lambda → 구성 → 환경 변수)에서 넣어도 된다.
- `CLAUDE_MODEL` 은 받은 키로 쓸 수 있는 모델 이름으로 맞춘다. 최신 모델 이름은 https://docs.claude.com 에서 확인한다.
- 일부 모델이 `temperature` 를 받지 않으면 `CLAUDE_TEMPERATURE` 를 빈 값으로 둔다.

## 7. S3 → Lambda 트리거

```bash
aws lambda add-permission --function-name zzik-analyze-photo --statement-id s3-invoke \
  --action lambda:InvokeFunction --principal s3.amazonaws.com \
  --source-arn arn:aws:s3:::BUCKET --source-account ACCOUNT_ID
# s3-notification.json 의 LAMBDA_ARN 을 함수 ARN 으로 바꾼 뒤
aws s3api put-bucket-notification-configuration --bucket BUCKET \
  --notification-configuration file://deploy/aws-stage1/s3-notification.json
```

트리거는 `moacut/albums/…/display.jpg` 에만 걸린다. 원본(최대 25MB) 대신 1600px 표시용 이미지를 보내 Claude 이미지 한도와 비용을 줄인다.

## 8. 동작 확인

1. 사진을 올리면 수십 초 안에 분석 상태가 "완료"로 바뀌고 장면·태그가 붙는다.
2. 태그 필터와 "혼자/함께" 필터(사람 수 기준)로 분류가 보인다.
3. Lambda 로그: CloudWatch Logs `/aws/lambda/zzik-analyze-photo` 에 `Saved …` 가 찍힌다.
4. 분석 실패 사진은 앱의 "다시 분석"을 누르면 EC2가 S3 객체를 자기 자신에게 복사해 Lambda를 다시 실행한다.

## 9. 문제 해결

| 증상 | 확인할 것 |
| --- | --- |
| 계속 "대기" | S3 트리거 접두사·접미사, Lambda 권한(`add-permission`), Lambda 로그 |
| Lambda 로그에 401 | Lambda와 EC2 `.env` 의 `INTERNAL_API_TOKEN` 이 같은지 |
| Lambda 로그에 연결 시간 초과 | `RESULT_URL` 의 EC2 IP, 보안 그룹 80 포트 |
| 분석 "실패" + `CLAUDE_ANALYSIS_FAILED` | API 키, 모델 이름, 사용량 한도 |
| 로그인 직후 403 | `.env` 의 `ALLOWED_ORIGINS` 가 브라우저 주소(`http://EC2_IP`)와 같은지 |

EC2를 중지했다가 켜면 공인 IP가 바뀐다. 그때는 `.env` 의 `ALLOWED_ORIGINS` 와 Lambda 의 `RESULT_URL` 을 함께 바꾼다.

## 10. 한계와 정리

- 도메인·HTTPS 가 없어 로그인 정보가 HTTP 로 오간다. 실습용으로만 쓰고 실제 비밀번호는 쓰지 않는다.
- EC2 한 대라 단일 장애 지점이다. 이걸 없애는 것이 계획서의 확장 단계(ALB+ASG, RDS, SQS 등)다.
- 실습 후: `docker compose exec -T db pg_dump -U moacut -d moacut -Fc > backup.dump` 로 백업하고, EC2 종료 → S3 객체·버킷 삭제 → Lambda 삭제 순서로 정리한다.
