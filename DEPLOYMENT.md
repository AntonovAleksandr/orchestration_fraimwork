# Deployment Guide - Framework v2.0.0

**Production deployment for Orchestration Framework**

---

## Quick Start (Development)

```bash
# 1. Clone repository
git clone https://github.com/your-org/orchestration_framework.git
cd orchestration_framework

# 2. Copy environment configuration
cp .env.example .env

# 3. Start services
docker-compose up -d redis

# 4. Initialize state store
python -m .claude.orchestration.state_store

# 5. Run tests
python -m pytest .claude/orchestration/test_phase3.py -v

# 6. Start using
from state_store import StateStore
store = StateStore(".tasks/state.db")
```

**Time: 5 minutes**

---

## Full Deployment (Production)

### 1. Infrastructure Setup

#### Option A: Docker Compose (Recommended)

```bash
# Start all services
docker-compose up -d

# Verify services are healthy
docker-compose ps
docker-compose logs -f

# Logs should show:
# redis_1: Ready to accept connections
# postgres_1: database system is ready to accept connections
# prometheus_1: Server is ready to receive web requests
# grafana_1: HTTP server listening on port 3000
```

#### Option B: Kubernetes

```yaml
# deployments/orchestration-worker.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: orchestration-config
data:
  STATE_STORE_DB_PATH: /persistent/state.db
  REDIS_URL: redis://redis-service:6379
  WORKER_TYPE: kubernetes
  LOG_LEVEL: INFO

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: orchestration-worker
spec:
  replicas: 3
  selector:
    matchLabels:
      app: orchestration-worker
  template:
    metadata:
      labels:
        app: orchestration-worker
    spec:
      containers:
      - name: worker
        image: your-registry/orchestration-worker:v2.0.0
        ports:
        - containerPort: 8000
        envFrom:
        - configMapRef:
            name: orchestration-config
        volumeMounts:
        - name: state-storage
          mountPath: /persistent
        healthCheck:
          exec:
            command:
            - python
            - -c
            - "import state_store; state_store.StateStore().health()"
          initialDelaySeconds: 10
          periodSeconds: 5
      volumes:
      - name: state-storage
        persistentVolumeClaim:
          claimName: orchestration-pvc
```

```bash
# Deploy to K8s
kubectl apply -f deployments/
kubectl get pods -l app=orchestration-worker
```

### 2. Database Setup

#### SQLite (Default, Single Node)

```bash
# Already created by StateStore on first run
ls -la .tasks/state.db

# For backing up
cp .tasks/state.db backups/state-$(date +%Y%m%d-%H%M%S).db
```

#### PostgreSQL (Scaling, HA)

```bash
# Start PostgreSQL
docker-compose --profile postgres up -d postgres

# Run migrations
python scripts/migrate-to-postgres.py

# Verify tables created
docker-compose exec postgres psql -U orch_user -d orchestration -c "\dt"

# Expected output:
#  public | tasks
#  public | phases
#  public | artifacts
#  public | checkpoints
#  public | locks
#  public | audit_log
```

#### Redis Setup

```bash
# Verify Redis is running
redis-cli ping
# Output: PONG

# Check memory usage
redis-cli info memory

# Configure persistence
# Already configured in docker-compose.yml with appendonly yes
redis-cli CONFIG GET appendonly
# Output: 1) "appendonly" 2) "yes"

# Monitor activity
redis-cli MONITOR
```

### 3. Configuration

#### Development (.env)

```bash
# Copy and customize
cp .env.example .env

# Minimal configuration
cat > .env << EOF
STATE_STORE_DB_PATH=.tasks/state.db
REDIS_URL=redis://localhost:6379
WORKER_ID=dev-worker-001
WORKER_TYPE=local
LOG_LEVEL=DEBUG
ENVIRONMENT=development
EOF
```

#### Staging (.env.staging)

```bash
cat > .env.staging << EOF
STATE_STORE_DB_PATH=/persistent/state.db
REDIS_URL=redis://redis-staging:6379
POSTGRES_HOST=postgres-staging
POSTGRES_DB=orchestration_staging
WORKER_ID=staging-worker-001
WORKER_TYPE=local
LOG_LEVEL=INFO
ENVIRONMENT=staging
CLOUD_PROVIDER=aws_lambda
CLOUD_REGION=us-east-1
EOF
```

#### Production (.env.prod)

```bash
cat > .env.prod << EOF
# Production MUST use secure values!
# Load from Secrets Manager, not .env file

STATE_STORE_DB_PATH=/persistent/prod/state.db
REDIS_URL=redis://redis-prod-cluster:6379
POSTGRES_HOST=postgres-prod-rds.example.com
POSTGRES_DB=orchestration_prod
POSTGRES_USER=${POSTGRES_USER}  # From Secrets Manager
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}  # From Secrets Manager

WORKER_ID=prod-worker-$(hostname)
WORKER_TYPE=kubernetes
WORKER_MAX_RETRIES=5
WORKER_STALL_TIMEOUT=60

CLOUD_PROVIDER=aws_lambda
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}  # From IAM
AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}  # From IAM

COORDINATOR_ID=prod-coordinator-001
COORDINATOR_WATCHDOG_ENABLED=true

LOG_LEVEL=INFO
LOG_FORMAT=json
STRUCTURED_LOGGING=true
PROMETHEUS_ENABLED=true
OTEL_ENABLED=true

ENVIRONMENT=production
DEBUG=false
EOF
```

### 4. Monitoring Setup

#### Prometheus

```yaml
# monitoring/prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'orchestration-worker'
    static_configs:
      - targets: ['localhost:8000']
```

#### Grafana Dashboard

```bash
# Access Grafana
# URL: http://localhost:3000
# User: admin
# Password: (from .env GRAFANA_PASSWORD)

# Import orchestration dashboard
# Settings → Data Sources → Add Prometheus
# Dashboards → Import → 12345 (orchestration-dashboard)
```

#### Key Metrics to Monitor

```
orchestration_worker_heartbeat_missing - Stalled workers
orchestration_phase_duration_seconds - Phase execution time
orchestration_error_count - Errors by type
orchestration_cloud_cost_cents - Cloud spending
orchestration_skill_load_errors - Skill loading failures
orchestration_coordinator_wait_time - Coordinator wait times
```

### 5. Backup & Recovery

#### Backup Strategy

```bash
#!/bin/bash
# backup.sh - Automated backup

BACKUP_DIR=backups/$(date +%Y-%m-%d)
mkdir -p $BACKUP_DIR

# SQLite backup
cp .tasks/state.db $BACKUP_DIR/state.db

# PostgreSQL backup (if used)
docker-compose exec postgres pg_dump -U orch_user orchestration \
  > $BACKUP_DIR/postgres-dump.sql

# Redis backup
redis-cli BGSAVE
cp /var/lib/redis/dump.rdb $BACKUP_DIR/redis.rdb

# Verify backup
ls -lh $BACKUP_DIR
```

#### Recovery Procedure

```bash
#!/bin/bash
# restore.sh - Restore from backup

BACKUP_PATH=$1

if [ ! -d "$BACKUP_PATH" ]; then
  echo "Backup not found: $BACKUP_PATH"
  exit 1
fi

# Stop services
docker-compose down

# Restore SQLite
cp $BACKUP_PATH/state.db .tasks/state.db

# Restore PostgreSQL
docker-compose up -d postgres
docker-compose exec postgres psql -U orch_user orchestration \
  < $BACKUP_PATH/postgres-dump.sql

# Restore Redis
docker-compose up -d redis
redis-cli < $BACKUP_PATH/redis.rdb

# Start all services
docker-compose up -d

echo "✅ Restored from $BACKUP_PATH"
```

### 6. Health Checks

#### Startup Verification

```bash
#!/bin/bash
# health-check.sh

echo "🔍 Checking orchestration services..."

# SQLite
if [ -f ".tasks/state.db" ]; then
  echo "✅ SQLite: state.db exists"
else
  echo "❌ SQLite: state.db not found"
  exit 1
fi

# Redis
if redis-cli ping | grep -q "PONG"; then
  echo "✅ Redis: responding"
else
  echo "❌ Redis: not responding"
  exit 1
fi

# State Store
python -c "
from state_store import StateStore
store = StateStore()
health = store.health()
if health['sqlite'] == 'healthy':
  print('✅ State Store: healthy')
else:
  print('❌ State Store: unhealthy')
  exit(1)
"

# Skills Registry
python -c "
from skill_registry import SkillRegistry
registry = SkillRegistry()
issues = registry.verify_all()
if not issues:
  print('✅ Skills: all verified')
else:
  print('❌ Skills: issues found')
  for issue in issues:
    print(f'  - {issue}')
"

echo "✅ All services healthy"
```

### 7. Upgrade Procedure

#### From v1.0.1 → v2.0.0

```bash
#!/bin/bash
# upgrade-v2.sh

echo "📦 Upgrading to v2.0.0..."

# 1. Backup current state
cp .tasks/state.db backups/state-v1.0.1.db

# 2. Pull latest code
git fetch origin
git checkout v2.0.0

# 3. Run migrations
python scripts/migrate-v1-to-v2.py

# 4. Verify state store
python -c "
from state_store import StateStore
store = StateStore()
tasks = store.get_active_tasks()
print(f'✅ Migrated {len(tasks)} active tasks')
"

# 5. Restart services
docker-compose restart

# 6. Verify
bash health-check.sh

echo "✅ Upgraded to v2.0.0"
```

### 8. Scaling

#### Horizontal Scaling

```yaml
# deployments/worker-autoscale.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: orchestration-worker-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: orchestration-worker
  minReplicas: 3
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

#### Database Scaling

```bash
# Switch from SQLite to PostgreSQL for >100k tasks/day
python scripts/migrate-to-postgres.py

# Add read replicas for high read volume
# AWS RDS: Multi-AZ + Read Replicas
# Cloud SQL: Cloud SQL Proxy + Read Replicas
```

---

## Deployment Checklist

### Pre-Deployment

- [ ] Code reviewed and tested
- [ ] All tests passing (23+ tests)
- [ ] Documentation updated
- [ ] Security review complete
- [ ] Performance benchmarked
- [ ] Backup plan in place

### Deployment

- [ ] Environment variables configured (.env)
- [ ] Database migrations run
- [ ] State Store initialized
- [ ] Skills registry verified
- [ ] Health checks passing
- [ ] Monitoring configured
- [ ] Alerts configured

### Post-Deployment

- [ ] Metrics verified in Prometheus
- [ ] Dashboards visible in Grafana
- [ ] Logs flowing to aggregation
- [ ] No error spikes
- [ ] Response times normal
- [ ] Cost monitoring active

### Rollback Triggers

If ANY of these occur, initiate rollback:
- Error rate > 5%
- Latency > 10x baseline
- Disk usage > 90%
- Memory usage > 85%
- Coordinator unresponsive >5 min

---

## Support & Troubleshooting

### Common Issues

#### "SQLite database is locked"

```bash
# Check for stale locks
lsof .tasks/state.db

# Restart services
docker-compose restart

# If persists, migrate to PostgreSQL
```

#### "Redis connection timeout"

```bash
# Verify Redis is running
docker-compose ps redis

# Check logs
docker-compose logs redis

# Restart if needed
docker-compose restart redis
```

#### "Worker stalled"

```bash
# Check worker logs
docker-compose logs orchestration-worker

# Verify state in database
sqlite3 .tasks/state.db "SELECT * FROM tasks WHERE status='running';"

# Restart worker
docker-compose restart orchestration-worker
```

### Support Contacts

- **Documentation:** [docs/PHASE3-COMPLETE.md](docs/PHASE3-COMPLETE.md)
- **Issues:** GitHub Issues
- **Security:** security@your-org.com

---

**Status: PRODUCTION READY**

Deploy with confidence. Persistent state, auto-recovery, and cost monitoring included.
