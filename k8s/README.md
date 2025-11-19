# Kubernetes Deployment Guide

Bu doküman, SafeTradeLab Data Collector'ı Kubernetes cluster'ına deploy etmek için gerekli adımları içerir.

## Önkoşullar

- Kubernetes cluster (AWS EKS)
- kubectl CLI tool
- Docker registry erişimi (ECR veya Docker Hub)
- Helm (opsiyonel)

## 1. Docker Image Oluşturma ve Push Etme

### AWS ECR Kullanıyorsanız:

```bash
# ECR login
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin YOUR_AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com

# Repository oluştur (ilk kez)
aws ecr create-repository --repository-name safetradelab/datacollector --region us-east-1

# Docker image build et
docker build -t safetradelab/datacollector:latest .

# Tag et
docker tag safetradelab/datacollector:latest YOUR_AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/safetradelab/datacollector:latest

# Push et
docker push YOUR_AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/safetradelab/datacollector:latest
```

### Docker Hub Kullanıyorsanız:

```bash
# Docker Hub login
docker login

# Build
docker build -t YOUR_DOCKERHUB_USERNAME/datacollector:latest .

# Push
docker push YOUR_DOCKERHUB_USERNAME/datacollector:latest
```

## 2. Kubernetes Konfigürasyonlarını Güncelleme

### Secret'ları Güncelle

`k8s/secret.yaml` dosyasını düzenle:

```yaml
stringData:
  DB_PASSWORD: "YOUR_SECURE_PASSWORD"  # Güçlü bir şifre belirle
  BINANCE_API_KEY: "YOUR_BINANCE_API_KEY"
  BINANCE_API_SECRET: "YOUR_BINANCE_API_SECRET"
```

### Image URL'sini Güncelle

`k8s/datacollector-deployment.yaml` dosyasında image URL'ini güncelle:

```yaml
image: YOUR_AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/safetradelab/datacollector:latest
```

### Storage Class'ı Kontrol Et

`k8s/postgres-pvc.yaml` dosyasında storage class'ı cluster'ınıza uygun şekilde ayarla:

```yaml
storageClassName: gp2  # AWS EKS için gp2, gp3 veya başka bir class kullanabilirsiniz
```

## 3. Deploy Etme

### Sıralı Deploy (Önerilen)

```bash
# 1. Namespace oluştur
kubectl apply -f k8s/namespace.yaml

# 2. ConfigMap ve Secret'ları oluştur
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.yaml

# 3. PostgreSQL'i deploy et
kubectl apply -f k8s/postgres-pvc.yaml
kubectl apply -f k8s/postgres-deployment.yaml

# 4. PostgreSQL'in hazır olmasını bekle
kubectl wait --for=condition=ready pod -l app=postgres -n safetradelab --timeout=300s

# 5. Data collector'ı deploy et
kubectl apply -f k8s/datacollector-deployment.yaml
```

### Tek Komutla Deploy

```bash
kubectl apply -f k8s/
```

## 4. Deployment'ı Kontrol Etme

```bash
# Tüm kaynakları listele
kubectl get all -n safetradelab

# Pod'ların durumunu kontrol et
kubectl get pods -n safetradelab

# Pod loglarını görüntüle
kubectl logs -f deployment/datacollector -n safetradelab

# PostgreSQL loglarını görüntüle
kubectl logs -f deployment/postgres -n safetradelab

# Pod içine gir
kubectl exec -it deployment/datacollector -n safetradelab -- /bin/bash

# PostgreSQL'e bağlan
kubectl exec -it deployment/postgres -n safetradelab -- psql -U postgres -d safetradelab
```

## 5. Veritabanını Temizleme

Mevcut EC2'deki verileri temizlemek için cleanup script'i kullan:

### Local'den EC2'ye Bağlanarak:

```bash
# EC2'ye SSH ile bağlan
ssh -i your-key.pem ubuntu@your-ec2-ip

# Container içinde script'i çalıştır
docker exec -it safetradelab_collector python scripts/cleanup_database.py --stats

# Tüm verileri sil (onay ile)
docker exec -it safetradelab_collector python scripts/cleanup_database.py --all

# Onaysız silme
docker exec -it safetradelab_collector python scripts/cleanup_database.py --all --yes

# Belirli bir sembolü sil
docker exec -it safetradelab_collector python scripts/cleanup_database.py --symbol BTCUSDT
```

### Kubernetes'te Veritabanını Temizleme:

```bash
# Pod içinde script'i çalıştır
kubectl exec -it deployment/datacollector -n safetradelab -- python scripts/cleanup_database.py --stats

# Tüm verileri sil
kubectl exec -it deployment/datacollector -n safetradelab -- python scripts/cleanup_database.py --all --yes
```

## 6. Konfigürasyon Güncelleme

### ConfigMap Güncelleme:

```bash
# ConfigMap'i düzenle
kubectl edit configmap datacollector-config -n safetradelab

# Veya dosyayı düzenleyip tekrar apply et
kubectl apply -f k8s/configmap.yaml

# Deployment'ı restart et (yeni config için)
kubectl rollout restart deployment/datacollector -n safetradelab
```

### Secret Güncelleme:

```bash
# Secret'ı düzenle
kubectl edit secret datacollector-secrets -n safetradelab

# Veya dosyayı düzenleyip tekrar apply et
kubectl apply -f k8s/secret.yaml

# Deployment'ı restart et
kubectl rollout restart deployment/datacollector -n safetradelab
```

## 7. Scaling ve Resource Management

```bash
# Replica sayısını artır (DİKKAT: Veri toplayıcı için genelde 1 olmalı!)
kubectl scale deployment/datacollector --replicas=1 -n safetradelab

# Resource limits'i güncelle
kubectl edit deployment/datacollector -n safetradelab
```

## 8. Monitoring ve Troubleshooting

```bash
# Detaylı pod bilgisi
kubectl describe pod <pod-name> -n safetradelab

# Events'leri görüntüle
kubectl get events -n safetradelab --sort-by='.lastTimestamp'

# Resource kullanımı
kubectl top pods -n safetradelab
kubectl top nodes

# PostgreSQL bağlantısını test et
kubectl exec -it deployment/datacollector -n safetradelab -- python -c "from src.database.connection import db; print('Connected!' if db.test_connection() else 'Failed!')"
```

## 9. Backup ve Restore

### PostgreSQL Backup:

```bash
# Backup oluştur
kubectl exec -it deployment/postgres -n safetradelab -- pg_dump -U postgres safetradelab > backup.sql

# PVC'den backup al
kubectl exec deployment/postgres -n safetradelab -- tar czf - /var/lib/postgresql/data | cat > postgres-backup.tar.gz
```

### PostgreSQL Restore:

```bash
# Backup'tan restore et
kubectl exec -i deployment/postgres -n safetradelab -- psql -U postgres safetradelab < backup.sql
```

## 10. Cleanup / Silme

```bash
# Tüm kaynakları sil
kubectl delete namespace safetradelab

# Veya tek tek sil
kubectl delete -f k8s/datacollector-deployment.yaml
kubectl delete -f k8s/postgres-deployment.yaml
kubectl delete -f k8s/postgres-pvc.yaml
kubectl delete -f k8s/secret.yaml
kubectl delete -f k8s/configmap.yaml
kubectl delete -f k8s/namespace.yaml
```

## 11. Production Best Practices

### 11.1 Secret Management

Production'da secret'ları Git'e commit etmeyin! Bunun yerine:

- AWS Secrets Manager
- HashiCorp Vault
- Sealed Secrets

kullanın.

### 11.2 Resource Limits

`datacollector-deployment.yaml` ve `postgres-deployment.yaml` dosyalarındaki resource limits'i workload'unuza göre ayarlayın.

### 11.3 Monitoring

Prometheus ve Grafana ile monitoring ekleyin:

```bash
# Prometheus metrics endpoint ekleyin
# Loki ile log aggregation
# AlertManager ile alerting
```

### 11.4 Backup Strategy

- Otomatik PostgreSQL backupları için CronJob oluşturun
- S3'e backup'ları yükleyin
- Retention policy belirleyin

### 11.5 High Availability

**PostgreSQL için:**
- StatefulSet kullanın (tek Deployment yerine)
- Streaming replication ekleyin
- PgBouncer ekleyin

**Data Collector için:**
- Tek replica kullanın (duplicate data collection'ı önlemek için)
- Liveness ve readiness probe'ları ekleyin

## 12. Migration Checklist

EC2'den Kubernetes'e geçiş için:

- [ ] Docker image'ı build et ve push et
- [ ] Kubernetes config'lerini güncelle (secrets, image URL, storage class)
- [ ] Kubernetes cluster'ına deploy et
- [ ] Pod'ların çalıştığını doğrula
- [ ] Log'ları kontrol et
- [ ] Veritabanı bağlantısını test et
- [ ] Data collection'ın başladığını doğrula
- [ ] EC2'deki mevcut verileri backup al
- [ ] EC2'deki veritabanını temizle (opsiyonel)
- [ ] EC2 instance'ı durdur/sil
- [ ] Monitoring ve alerting kur
- [ ] Backup stratejisi uygula

## Destek

Sorularınız için:
- Kubernetes logs: `kubectl logs -f deployment/datacollector -n safetradelab`
- PostgreSQL logs: `kubectl logs -f deployment/postgres -n safetradelab`
- Events: `kubectl get events -n safetradelab`
