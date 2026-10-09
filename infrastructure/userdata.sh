#!/bin/bash
# ChronosMesh EC2 Auto-Setup Script
# Runs on first boot of the Ubuntu instance
set -e
exec > /var/log/chronosmesh-setup.log 2>&1

echo "=== ChronosMesh Auto-Setup Starting ==="
echo "Timestamp: $(date)"

# 1. Update system
apt-get update -y
apt-get upgrade -y

# 2. Install Docker
apt-get install -y docker.io docker-compose-v2 git curl wget

# Start and enable Docker
systemctl start docker
systemctl enable docker
usermod -aG docker ubuntu

# 3. Add swap for t2/t3 micro instances
if [ ! -f /swapfile ]; then
    fallocate -l 2G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

# 4. Clone ChronosMesh
cd /home/ubuntu
git clone https://github.com/Akshith1413/ChronosMesh.git
cd ChronosMesh

# 5. Start the lightweight stack (API + optional Prometheus/Grafana)
docker compose -f docker-compose.guru.yml up -d --build

echo "=== ChronosMesh Setup Complete ==="
echo "API available at: http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4):8000"
echo "Setup finished at: $(date)"
