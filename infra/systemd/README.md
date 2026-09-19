# systemd 유닛 (컨테이너 없이 EC2에 배치할 때)

Docker 없이 App EC2에서 FastAPI와 worker를 서비스로 등록하는 예시다. **이 저장소에서 실제 EC2에 적용해 검증한 결과는 없다.** 아래 값은 배치 환경에 맞게 바꿔야 한다.

- `WEB_TIER_PRIVATE_IP` → Web EC2(Nginx)의 사설 IP. uvicorn이 이 주소에서 온 프록시 헤더만 신뢰한다.
- `/opt/zzik` → 소스와 `.venv`를 둔 경로.
- `/etc/zzik/runtime.env` → `docs/AWS_DEPLOYMENT.md`의 runtime.env 예시와 같은 형식. `chmod 600`, 소유자 root.
- `/var/lib/zzik` → `STORAGE_ROOT=local`을 쓸 때만 필요하다. `STORAGE_BACKEND=s3`면 `ReadWritePaths`를 지워도 된다.

API는 `127.0.0.1:8000`에만 바인딩한다. 외부 노출은 Web EC2의 Nginx가 담당하고, 보안 그룹에서 8000 포트를 Web EC2에만 열어야 한다. 유닛 파일이 로컬 바인딩이라도 보안 그룹 제한을 대신하지는 않는다.

## 준비

```sh
sudo useradd --system --home /opt/zzik --shell /usr/sbin/nologin zzik
sudo mkdir -p /opt/zzik /etc/zzik /var/lib/zzik
sudo chown -R zzik:zzik /opt/zzik /var/lib/zzik
sudo -u zzik python3 -m venv /opt/zzik/.venv
sudo -u zzik /opt/zzik/.venv/bin/pip install --require-hashes -r /opt/zzik/backend/requirements.lock
sudo install -m 600 -o root -g root runtime.env /etc/zzik/runtime.env
```

## 마이그레이션 후 시작

애플리케이션을 시작하기 전에 스키마를 먼저 올린다. 현재 최신 revision은 `0003`이다.

```sh
sudo -u zzik env $(sudo cat /etc/zzik/runtime.env | grep -v '^#' | xargs) \
  /opt/zzik/.venv/bin/alembic -c /opt/zzik/backend/alembic.ini upgrade head
sudo install -m 644 infra/systemd/zzik-api.service infra/systemd/zzik-worker.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now zzik-api zzik-worker
systemctl status zzik-api zzik-worker
curl --fail http://127.0.0.1:8000/api/health/ready
```

## 배포와 롤백

```sh
sudo systemctl stop zzik-worker zzik-api
# 소스 교체 및 필요한 경우 alembic upgrade head
sudo systemctl start zzik-api zzik-worker
journalctl -u zzik-api -u zzik-worker --since '10 min ago'
```

worker를 먼저 멈추고 API를 나중에 멈춘다. worker는 `SIGTERM`을 받으면 진행 중인 작업을 끝내거나 lease를 놓아주므로, `TimeoutStopSec`(180초) 안에서 정상 종료를 기다리는 것이 작업 유실을 막는다. 스키마 되돌리기는 `docs/AWS_DEPLOYMENT.md`의 주의사항을 따른다.
