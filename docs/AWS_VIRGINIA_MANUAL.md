# 버지니아 3-Tier 실습 — EC2는 직접 생성

대상: `junseok0929/ZZIK`, `feat/smart-curation`, 시작 커밋 `33affbf`, DB revision `0003`.
리전: 미국 동부(버지니아 북부), `us-east-1`. 작성일: 2026-09-19.

이 문서는 배포 준비물이다. 실제 AWS 리소스 생성이나 서버 연결 완료를 뜻하지 않는다. EC2의 AMI·인스턴스 유형·키 페어·볼륨은 사용자가 콘솔에서 선택한다. 교육 계정에서 허용한 유형과 기존 IAM 역할을 먼저 확인한다. 크레딧 유무가 서비스 할당량이나 IAM 권한을 보장하지는 않는다.

## 구성

```text
브라우저 → HTTPS Web EC2 / Nginx (public subnet)
                         ↓ TCP 8000, 사설 IP
                   App EC2 / API + worker (private subnet)
                         ├─ RDS PostgreSQL (private, TCP 5432)
                         ├─ S3 비공개 버킷 (gateway endpoint)
                         └─ Rekognition (HTTPS, NAT 경유)
```

새 VPC를 사용하면 기존 실습 환경과 주소 충돌을 피하기 쉽다. 아래 CIDR은 새 VPC의 제안값이며 기존 네트워크와 겹치면 변경한다.

## 1. VPC: 콘솔에서 먼저 준비

[버지니아 VPC 콘솔](https://us-east-1.console.aws.amazon.com/vpc/home?region=us-east-1#vpcs:)에서 **VPC 생성 → VPC 등**을 선택한다.

| 설정 | 실습 값 |
|---|---|
| 이름 | zzik-lab |
| IPv4 CIDR | 10.20.0.0/16 |
| 가용 영역 | 2개 |
| 퍼블릭 서브넷 | 2개 |
| 프라이빗 서브넷 | 2개 |
| NAT 게이트웨이 | 한 가용 영역에 1개 (실습용 단일 경로) |
| VPC 엔드포인트 | S3 Gateway |
| DNS 호스트 이름·해석 | 활성화 |

App은 외부 패키지 설치와 Rekognition 호출을 위해 outbound 경로가 필요하다. 여기서는 NAT를 사용한다. S3 Gateway만으로 일반 인터넷이나 Rekognition에 연결되지는 않는다. RDS 서브넷 그룹은 서로 다른 두 AZ의 private subnet을 포함해야 한다. [AWS VPC 구성](https://docs.aws.amazon.com/vpc/latest/userguide/create-a-vpc-with-private-subnets-and-nat-gateways-using-aws-cli.html), [S3 Gateway](https://docs.aws.amazon.com/vpc/latest/privatelink/vpc-endpoints-s3.html), [RDS 서브넷](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_CreateDBInstance.html).

## 2. 보안 그룹: 소스는 다른 그룹 ID로 연결

| 그룹 | 인바운드 | 소스 |
|---|---|---|
| zzik-web-sg | TCP 80: 연결 확인용 | 내 현재 공인 IP /32 |
| zzik-web-sg | TCP 443: HTTPS 구성 후 | 실습 접속자 IP 범위 |
| zzik-web-sg | TCP 22: SSH를 쓸 때만 | 내 현재 공인 IP /32 |
| zzik-app-sg | TCP 8000 | zzik-web-sg |
| zzik-app-sg | TCP 22: SSH 점프를 쓸 때만 | zzik-web-sg |
| zzik-db-sg | TCP 5432 | zzik-app-sg |

App과 DB의 포트를 `0.0.0.0/0`에 열지 않는다. 실습 초기 아웃바운드는 기본 허용을 유지하고, 확인 후 목적지별로 제한한다. 이 구성에서 HTTPS는 Web Nginx에서 종료한다. ALB를 추가한다면 신뢰 프록시·보안 그룹·인증서 설정도 별도로 변경해야 한다.

## 3. S3와 인스턴스 역할

S3 버킷은 `us-east-1`에 생성한다. 전역에서 유일한 이름을 선택하고 Block Public Access 전체 활성화, ACL 비활성화, 기본 SSE-S3 암호화를 사용한다. 앱 prefix는 `zzik/`로 통일한다. 버전 관리를 켜면 앱 삭제 뒤 이전 버전도 보존되므로 별도 수명주기·실습 정리 계획이 필요하다.

App EC2에는 EC2 신뢰 관계를 가진 인스턴스 역할을 연결한다. [`app-role-policy.json`](../infra/aws/app-role-policy.json)의 버킷과 계정 ID를 바꿔 필요한 prefix/collection 권한을 부여한다. 교육 계정에서 IAM 생성이 막히면 제공된 역할 중 해당 권한이 있는 것을 사용한다. Web에는 사진·Rekognition 권한이 필요 없다. Session Manager를 사용할 서버의 역할에는 교육 계정에서 허용된 SSM 권한도 필요하다. 액세스 키를 앱 소스나 프론트에 넣지 않는다.

## 4. EC2 두 대: 사용자 수동 선택

| 항목 | Web EC2 | App EC2 |
|---|---|---|
| 이름 | zzik-web | zzik-app |
| AMI | 사용자 선택 | 사용자 선택 |
| 검증할 실행 환경 | Nginx, Node.js 24+ | Python 3.13, systemd |
| 인스턴스 유형 | 교육 계정 허용 범위에서 선택 | 이미지 처리 메모리 고려해 선택 |
| VPC | zzik-lab | zzik-lab |
| 서브넷 | public | private (NAT와 같은 AZ 우선) |
| 공인 IPv4 | 활성화 | 비활성화 |
| 보안 그룹 | zzik-web-sg | zzik-app-sg |
| IAM 프로파일 | 관리 접속에 필요한 역할 | S3/Rekognition + 관리 접속 역할 |
| IMDS | v2 필수 | v2 필수 |
| 키 페어·EBS | 직접 선택 | 직접 선택 |

AMI가 정해지면 그 배포판에 맞는 설치 명령을 사용한다. Amazon Linux 2023을 선택할 경우 시스템 `python3`는 3.9이므로 `python3.13`을 별도로 설치하고 명시적으로 실행해야 한다. 시스템 Python 링크를 바꾸지 않는다. [AL2023 Python](https://docs.aws.amazon.com/linux/al2023/ug/python.html). Node.js 24도 최신 AL2023 패키지에 포함되어 있다. [공식 릴리스](https://docs.aws.amazon.com/linux/al2023/release-notes/relnotes-2023.9.20251110.html).

App 관리 접속은 Session Manager를 우선 확인한다. 없다면 Web 경유 SSH ProxyJump를 사용하되 개인키는 로컬 PC에 보관한다. 키를 Web 서버에 복사하지 않는다. NAT와 IAM 역할이 갖춰져도 SSM Agent가 설치·실행되어 있어야 한다.

## 5. RDS PostgreSQL

- 표준 생성, PostgreSQL 17의 계정에서 지원되는 minor 버전.
- 실습용 단일 DB 인스턴스. 크기·스토리지는 교육 정책에 맞게 직접 선택.
- 식별자 `zzik-db`, 초기 DB 이름 `zzik`.
- VPC `zzik-lab`, private 두 AZ 서브넷 그룹, `zzik-db-sg`, 퍼블릭 액세스 **아니요**.
- 저장 암호화 활성화. 자동 백업 보존 기간과 삭제 방지 여부를 실습 종료 계획에 맞춰 선택.
- DB 계정·비밀번호는 AWS 콘솔/서버 설정으로만 입력한다. 대화나 Git에 붙여넣지 않는다.

생성 후 엔드포인트와 5432 포트를 기록한다. 서버 인증서는 [AWS RDS CA truststore](https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem)를 사용하고 연결은 `sslmode=verify-full`로 검증한다.

## 6. App 배포

1. 이 브랜치의 배포 수정까지 포함한 같은 커밋을 두 EC2에서 사용한다. 소스 경로 `/opt/zzik`, 서비스 사용자 `zzik`.
2. 선택한 AMI에 맞춰 Python 3.13·git을 설치하고 `/opt/zzik/.venv`를 만든다. 기존 [`systemd 가이드`](../infra/systemd/README.md)의 가상환경 생성 시 Python 실행파일을 확인한다.
3. 의존성 설치: `/opt/zzik/.venv/bin/pip install -r /opt/zzik/backend/requirements.lock`.
4. [`runtime.env.example`](../infra/aws/runtime.env.example)을 서버의 `/etc/zzik/runtime.env`로 복사해 실제 값으로 채운다. 파일은 root 소유, 모드 600. DB URL의 비밀번호는 URL 인코딩한다. API와 worker가 같은 파일을 읽는다.
5. CA 파일을 `/etc/zzik/global-bundle.pem`에 두고 서비스 사용자가 읽을 수 있도록 644로 설정한다.
6. API 유닛의 `APP_TIER_PRIVATE_IP`, `WEB_TIER_PRIVATE_IP`를 실제 사설 주소로 바꾼다. DB 대상과 백업을 확인한 뒤 `zzik-migrate`를 실행하여 `0003`까지 적용한다.
7. 성공하면 API와 worker를 시작한다. App 사설 IP의 `/api/health/ready`를 조회한다.

Rekognition은 별도 서버를 생성하는 서비스가 아니다. 올바른 역할·리전·네트워크를 갖추고 실제 요청으로 확인한다. 기준 인물 등록 후 1~3장의 허용된 테스트 사진부터 사용한다. 성공 여부는 실제 호출 기록·S3 객체·DB 작업 상태로 판단한다.

## 7. Web 배포와 HTTPS

Node.js 24 이상에서 `npm --prefix frontend ci`, `npm --prefix frontend run build`를 실행한다. **`build:demo`를 배포하면 실제 API에 연결되지 않는다.** `frontend/dist/`를 Nginx 웹 루트에 배치한다.

[`web-connectivity.conf.example`](../infra/aws/web-connectivity.conf.example)의 App 사설 IP를 바꿔 80번 포트의 연결 확인에 사용한다. Nginx 기본 서버 설정과 충돌하지 않도록 설치 전 확인하고 `nginx -t` 후 reload한다. SELinux 사용 배포판은 Nginx upstream 연결 허용 정책도 확인한다.

첫 HTTP 단계에서는 화면·health 연결만 확인한다. 실제 로그인·사진 사용 전에 도메인/DNS와 신뢰할 수 있는 TLS 인증서를 Nginx에 연결하고 443을 활성화한다. `ALLOWED_ORIGINS`는 실제 HTTPS origin, `COOKIE_SECURE=true`를 유지한다. 도메인이 아직 없으면 인증서 구성 방법을 먼저 정한다.

## 8. 완료 검증과 종료

- HTTPS → Web → App → RDS readiness 성공.
- S3에 실제 원본 저장, 비회원 접근 차단, 승인된 멤버의 서명 URL 다운로드.
- 기준 인물 등록, 얼굴 있는 사진/없는 사진 분석, 실패 상태 및 재시도.
- 스마트 앨범·인물 검색·멤버 라벨, 보정·두 계정 승인·최종본.
- API/worker 재시작 후 원본·버전·승인 유지.
- 확인한 커밋, 리전, 리소스 ID, 검증 시각과 결과만 기록. 비밀키·세션·서명 URL은 기록하지 않는다.

실습 종료 시 EC2·RDS·NAT·EIP·S3·Rekognition collection을 모두 목록으로 확인한다. 인스턴스만 중지해도 스토리지·네트워크 자원 비용이 남을 수 있다. 데이터 백업 여부를 결정한 뒤 리소스별로 정리하고, 앱 삭제와 AWS 자원 삭제를 구분한다.

다음 연결에 필요한 비밀 아닌 정보: 선택한 AMI 이름/OS·아키텍처, Web/App 인스턴스 ID와 사설 IP, RDS 엔드포인트, S3 버킷명, IAM 역할명, 사용할 도메인. 비밀번호·액세스 키·개인키는 공유하지 않는다.
