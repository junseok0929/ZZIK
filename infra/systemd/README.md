# systemd 유닛 (컨테이너 없이 EC2에 배치할 때)

Docker 없이 App EC2에서 FastAPI와 worker를 서비스로 등록하는 예시다. **이 저장소에서 실제 EC2에 적용해 검증한 결과는 없다.** 아래 값은 배치 환경에 맞게 바꿔야 한다.

- `WEB_TIER_PRIVATE_IP` → Web EC2(Nginx)의 사설 IP. uvicorn이 이 주소에서 온 프록시 헤더만 신뢰한다.
- `APP_TIER_PRIVATE_IP` → App EC2의 사설 IP. API가 이 주소에서 수신한다.
- `/opt/zzik` → 소스와 `.venv`를 둔 경로.
- `/etc/zzik/runtime.env` → `docs/AWS_DEPLOYMENT.md`의 runtime.env 예시와 같은 형식. `chmod 600`, 소유자 root.
- `/var/lib/zzik` → `STORAGE_ROOT=local`을 쓸 때만 필요하다. `STORAGE_BACKEND=s3`면 `ReadWritePaths`를 지워도 된다.

API는 `APP_TIER_PRIVATE_IP:8000`에 바인딩한다. 별도 Web EC2의 Nginx가 이 주소로 전달한다. `127.0.0.1`로 바인딩하면 다른 EC2에서 연결할 수 없다. App 보안 그룹의 8000 포트는 Web 보안 그룹에서만 접근하도록 설정한다. API를 인터넷에 공개하지 않는다. API와 worker는 `/opt/zzik`를 공통 작업 경로로 사용한다.

## 준비

```sh
sudo useradd --system --home /opt/zzik --shell /usr/sbin/nologin zzik
sudo mkdir -p /opt/zzik /etc/zzik /var/lib/zzik
sudo chown -R zzik:zzik /opt/zzik /var/lib/zzik
sudo -u zzik python3 -m venv /opt/zzik/.venv
sudo -u zzik /opt/zzik/.venv/bin/pip install -r /opt/zzik/backend/requirements.lock
sudo install -m 600 -o root -g root runtime.env /etc/zzik/runtime.env
```

## 마이그레이션 후 시작

애플리케이션을 시작하기 전에 스키마를 먼저 올린다. 현재 최신 revision은 `0003`이다.

```sh
# API 유닛의 APP_TIER_PRIVATE_IP / WEB_TIER_PRIVATE_IP를 실제 값으로 바꾼 뒤 설치한다.
sudo install -m 644 infra/systemd/zzik-api.service infra/systemd/zzik-worker.service infra/systemd/zzik-migrate.service /etc/systemd/system/
sudo systemctl daemon-reload
# 백업과 대상 RDS를 확인한 후 실행. 환경변수 값은 명령행에 펼치지 않는다.
sudo systemctl start zzik-migrate
# 위 명령이 성공했을 때만 API와 worker를 시작한다.
sudo systemctl enable --now zzik-api zzik-worker
systemctl status zzik-api zzik-worker
curl --fail http://APP_TIER_PRIVATE_IP:8000/api/health/ready
```

## 배포와 롤백

```sh
sudo systemctl stop zzik-worker zzik-api
# 소스 교체 및 필요한 경우 alembic upgrade head
sudo systemctl start zzik-api zzik-worker
journalctl -u zzik-api -u zzik-worker --since '10 min ago'
```

worker를 먼저 멈추고 API를 나중에 멈춘다. worker는 `SIGTERM`을 받으면 진행 중인 작업의 정상 종료를 기다린다. 180초 후 강제 종료되면 DB lease 만료 후 복구하므로 즉시 lease를 반납한다고 가정하지 않는다. 스키마 되돌리기는 `docs/AWS_DEPLOYMENT.md`의 주의사항을 따른다.

`requirements.lock`은 버전 고정 파일이며 해시를 포함하지 않으므로 `--require-hashes`를 사용하지 않는다. 마이그레이션 유닛은 자동 활성화하지 않고 배포 때 명시적으로 실행한다. 실제 RDS 마이그레이션 성공과 Web→App 연결은 대상 EC2에서 별도로 확인해야 한다.
