#!/bin/bash
# Amazon Linux 2023 EC2 의 "사용자 데이터"에 붙여 넣는다. 비밀값은 넣지 않는다(.env 는 접속해서 만든다).
set -euxo pipefail
dnf install -y docker git
systemctl enable --now docker
usermod -aG docker ec2-user
# Docker Compose·Buildx 플러그인 (버전 고정)
mkdir -p /usr/local/lib/docker/cli-plugins
curl -fsSL https://github.com/docker/compose/releases/download/v2.29.7/docker-compose-linux-x86_64 \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
curl -fsSL https://github.com/docker/buildx/releases/download/v0.17.1/buildx-v0.17.1.linux-amd64 \
  -o /usr/local/lib/docker/cli-plugins/docker-buildx
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose /usr/local/lib/docker/cli-plugins/docker-buildx
# 작은 인스턴스에서 프론트 빌드가 메모리 부족으로 죽지 않도록 2GB 스왑
if [ ! -f /swapfile ]; then
  dd if=/dev/zero of=/swapfile bs=1M count=2048
  chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  echo '/swapfile swap swap defaults 0 0' >> /etc/fstab
fi
sudo -u ec2-user git clone https://github.com/junseok0929/ZZIK.git /home/ec2-user/zzik || true
