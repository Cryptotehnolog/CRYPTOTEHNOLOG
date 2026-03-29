# AI ПРОМТ: ФАЗА 18 - DISTRIBUTED DEPLOYMENT

## КОНТЕКСТ

Вы — Senior DevOps/SRE Engineer, специализирующийся на distributed systems, Kubernetes orchestration, и high-availability infrastructure.

**Фазы 0-17 завершены.** Доступны:
- Полная торговая система (15 фаз)
- Backtesting Engine (Фаза 16)
- Paper Trading (Фаза 17)
- Все компоненты протестированы и ready

**Текущая задача:** Реализовать production-ready Distributed Deployment с Kubernetes orchestration, service mesh, auto-scaling, zero-downtime updates, и disaster recovery.

---

## ⚠️ КРИТИЧЕСКИ ВАЖНО: РУССКИЙ ЯЗЫК

**ВСЕ** комментарии, YAML configs, документация должны быть **НА РУССКОМ ЯЗЫКЕ**.

### Kubernetes YAML — ТОЛЬКО русский комментарии:

```yaml
# Deployment для Strategy Manager (центральный orchestrator)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: strategy-manager
  namespace: cryptotehnolog
  labels:
    app: strategy-manager
    component: core
spec:
  # Количество реплик (для HA)
  replicas: 2
  
  strategy:
    type: RollingUpdate
    rollingUpdate:
      # Максимум unavailable pods при обновлении
      maxUnavailable: 0
      # Максимум extra pods при обновлении
      maxSurge: 1
  
  selector:
    matchLabels:
      app: strategy-manager
  
  template:
    metadata:
      labels:
        app: strategy-manager
    spec:
      # Anti-affinity: распределить по разным нодам для HA
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
          - weight: 100
            podAffinityTerm:
              labelSelector:
                matchExpressions:
                - key: app
                  operator: In
                  values:
                  - strategy-manager
              topologyKey: kubernetes.io/hostname
      
      containers:
      - name: strategy-manager
        image: cryptotehnolog/strategy-manager:v1.0.0
        
        # Resource limits (критично для production)
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
        
        # Health checks
        livenessProbe:
          httpGet:
            path: /health/live
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
          
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 5
        
        # Environment variables (из ConfigMap и Secrets)
        envFrom:
        - configMapRef:
            name: strategy-manager-config
        - secretRef:
            name: strategy-manager-secrets
        
        # Persistent volume для state
        volumeMounts:
        - name: state
          mountPath: /app/state
      
      volumes:
      - name: state
        persistentVolumeClaim:
          claimName: strategy-manager-state
```

### Logs — ТОЛЬКО русский:

```python
logger.info("🚀 Deploying в Kubernetes", namespace="cryptotehnolog", replicas=2)
logger.info("✅ Rolling update завершен", old_version="v1.0.0", new_version="v1.1.0")
logger.warning("⚠️  Pod restarted", pod="strategy-manager-abc123", reason="OOMKilled")
```

---

## 🔗 КОМПОНЕНТНЫЕ ИНТЕГРАЦИИ

### Роль компонента в системе:
Distributed Deployment — production infrastructure для высокой доступности, масштабируемости, и надежности. Orchestrates все компоненты через Kubernetes, ensures zero-downtime updates, auto-scaling, disaster recovery, и monitoring.

### Архитектура deployment:

```
┌─────────────────────────────────────────────────┐
│              Kubernetes Cluster                 │
│                                                 │
│  ┌───────────────────────────────────────────┐ │
│  │         Ingress Controller                │ │
│  │  (NGINX: external traffic → services)     │ │
│  └────────────────┬──────────────────────────┘ │
│                   │                             │
│  ┌────────────────┴──────────────────────────┐ │
│  │         Service Mesh (Istio)              │ │
│  │  (traffic management, observability)      │ │
│  └────────────────┬──────────────────────────┘ │
│                   │                             │
│  ┌────────────────┴──────────────────────────┐ │
│  │           Core Services                   │ │
│  │                                           │ │
│  │  ┌──────────┐  ┌──────────┐  ┌────────┐ │ │
│  │  │ Strategy │  │ Market   │  │ Signal │ │ │
│  │  │ Manager  │  │ Data     │  │ Gen    │ │ │
│  │  │ (2 pods) │  │ (3 pods) │  │(2 pods)│ │ │
│  │  └──────────┘  └──────────┘  └────────┘ │ │
│  │                                           │ │
│  │  ┌──────────┐  ┌──────────┐  ┌────────┐ │ │
│  │  │Portfolio │  │Execution │  │  OMS   │ │ │
│  │  │Governor  │  │ Layer    │  │(2 pods)│ │ │
│  │  │ (2 pods) │  │ (3 pods) │  └────────┘ │ │
│  │  └──────────┘  └──────────┘              │ │
│  └───────────────────────────────────────────┘ │
│                                                 │
│  ┌───────────────────────────────────────────┐ │
│  │         Stateful Services                 │ │
│  │                                           │ │
│  │  ┌──────────┐  ┌──────────┐  ┌────────┐ │ │
│  │  │PostgreSQL│  │TimescaleDB│ │ Redis  │ │ │
│  │  │StatefulSet│ │StatefulSet│ │Cluster │ │ │
│  │  └──────────┘  └──────────┘  └────────┘ │ │
│  └───────────────────────────────────────────┘ │
│                                                 │
│  ┌───────────────────────────────────────────┐ │
│  │         Monitoring Stack                  │ │
│  │                                           │ │
│  │  ┌──────────┐  ┌──────────┐  ┌────────┐ │ │
│  │  │Prometheus│  │ Grafana  │  │ Loki   │ │ │
│  │  └──────────┘  └──────────┘  └────────┘ │ │
│  └───────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
```

### ConfigMap для компонентов:

```yaml
# ConfigMap для Strategy Manager
apiVersion: v1
kind: ConfigMap
metadata:
  name: strategy-manager-config
  namespace: cryptotehnolog
data:
  # Конфигурация стратегий
  STRATEGIES: "momentum,mean_reversion,breakout"
  SYMBOLS: "BTC/USDT,ETH/USDT,SOL/USDT"
  TIMEFRAME: "5m"
  
  # Интеграции с другими сервисами
  MARKET_DATA_URL: "http://market-data:8081"
  SIGNAL_GENERATOR_URL: "http://signal-generator:8082"
  RISK_ENGINE_URL: "http://risk-engine:8083"
  PORTFOLIO_GOVERNOR_URL: "http://portfolio-governor:8084"
  EXECUTION_LAYER_URL: "http://execution-layer:8085"
  
  # Database connections
  POSTGRES_HOST: "postgresql-primary.cryptotehnolog.svc.cluster.local"
  POSTGRES_PORT: "5432"
  POSTGRES_DB: "cryptotehnolog"
  
  TIMESCALEDB_HOST: "timescaledb.cryptotehnolog.svc.cluster.local"
  TIMESCALEDB_PORT: "5432"
  
  REDIS_HOST: "redis-cluster.cryptotehnolog.svc.cluster.local"
  REDIS_PORT: "6379"
  
  # Event Bus (Rust component)
  EVENT_BUS_URL: "http://event-bus:9000"
  
  # Logging
  LOG_LEVEL: "INFO"
  LOG_FORMAT: "json"
```

### Secrets для API keys:

```yaml
# Secret для exchange API keys (зашифровано)
apiVersion: v1
kind: Secret
metadata:
  name: exchange-api-keys
  namespace: cryptotehnolog
type: Opaque
data:
  # Base64 encoded (в production использовать Vault/Sealed Secrets)
  BYBIT_API_KEY: YmFzZTY0X2VuY29kZWRfa2V5
  BYBIT_API_SECRET: YmFzZTY0X2VuY29kZWRfc2VjcmV0
  OKX_API_KEY: YmFzZTY0X2VuY29kZWRfa2V5
  OKX_API_SECRET: YmFzZTY0X2VuY29kZWRfc2VjcmV0
  # ... и т.д.
```

### StatefulSet для PostgreSQL (HA):

```yaml
# PostgreSQL с репликацией для HA
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgresql
  namespace: cryptotehnolog
spec:
  serviceName: postgresql
  replicas: 3  # 1 primary + 2 replicas
  
  selector:
    matchLabels:
      app: postgresql
  
  template:
    metadata:
      labels:
        app: postgresql
    spec:
      containers:
      - name: postgresql
        image: postgres:15-alpine
        
        ports:
        - containerPort: 5432
          name: postgresql
        
        env:
        - name: POSTGRES_DB
          value: cryptotehnolog
        - name: POSTGRES_USER
          valueFrom:
            secretKeyRef:
              name: postgresql-secret
              key: username
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: postgresql-secret
              key: password
        
        # Persistent storage
        volumeMounts:
        - name: data
          mountPath: /var/lib/postgresql/data
        
        # Health checks
        livenessProbe:
          exec:
            command:
            - /bin/sh
            - -c
            - pg_isready -U ${POSTGRES_USER}
          initialDelaySeconds: 30
          periodSeconds: 10
        
        resources:
          requests:
            memory: "2Gi"
            cpu: "1000m"
          limits:
            memory: "4Gi"
            cpu: "2000m"
  
  # Persistent Volume Claims
  volumeClaimTemplates:
  - metadata:
      name: data
    spec:
      accessModes: [ "ReadWriteOnce" ]
      storageClassName: fast-ssd
      resources:
        requests:
          storage: 100Gi
```

### HorizontalPodAutoscaler (Auto-scaling):

```yaml
# Auto-scaling для Execution Layer (высокая нагрузка)
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: execution-layer-hpa
  namespace: cryptotehnolog
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: execution-layer
  
  # Минимум/максимум pods
  minReplicas: 2
  maxReplicas: 10
  
  # Метрики для scaling
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70  # Scale up при CPU > 70%
  
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80  # Scale up при Memory > 80%
  
  # Поведение scaling
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
      - type: Percent
        value: 50  # Увеличить на 50% за раз
        periodSeconds: 60
    scaleDown:
      stabilizationWindowSeconds: 300  # 5 минут стабилизации перед scale down
      policies:
      - type: Pods
        value: 1  # Уменьшать по 1 поду за раз
        periodSeconds: 120
```

### Service для external access:

```yaml
# Service для Strategy Manager
apiVersion: v1
kind: Service
metadata:
  name: strategy-manager
  namespace: cryptotehnolog
spec:
  selector:
    app: strategy-manager
  
  ports:
  - name: http
    port: 8080
    targetPort: 8080
    protocol: TCP
  
  # ClusterIP для internal access
  type: ClusterIP
  
  # Session affinity (если нужно)
  sessionAffinity: ClientIP
```

### Обработка ошибок и recovery:

#### 1. Pod failure recovery:

```yaml
# Deployment с restart policy
spec:
  template:
    spec:
      # Автоматический restart при падении
      restartPolicy: Always
      
      containers:
      - name: strategy-manager
        # ... config
        
        # Liveness probe: kill pod если unhealthy
        livenessProbe:
          httpGet:
            path: /health/live
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
          failureThreshold: 3  # 3 неудачных проверки → restart pod
        
        # Readiness probe: remove от Service если not ready
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 5
          failureThreshold: 2
```

**Recovery workflow:**
1. Liveness probe fails 3 раза
2. Kubernetes kills pod
3. Deployment controller creates new pod
4. Readiness probe passes → add to Service
5. Traffic flows к healthy pod

#### 2. Database backup и restore:

```yaml
# CronJob для PostgreSQL backups
apiVersion: batch/v1
kind: CronJob
metadata:
  name: postgresql-backup
  namespace: cryptotehnolog
spec:
  # Каждый день в 02:00 UTC
  schedule: "0 2 * * *"
  
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: backup
            image: postgres:15-alpine
            
            command:
            - /bin/sh
            - -c
            - |
              # Dump PostgreSQL database
              pg_dump -h $POSTGRES_HOST \
                      -U $POSTGRES_USER \
                      -d $POSTGRES_DB \
                      -F c \
                      -f /backup/cryptotehnolog-$(date +%Y%m%d).dump
              
              # Upload to S3 (или другой object storage)
              aws s3 cp /backup/cryptotehnolog-$(date +%Y%m%d).dump \
                        s3://cryptotehnolog-backups/postgresql/
            
            envFrom:
            - secretRef:
                name: postgresql-secret
            - secretRef:
                name: aws-credentials
            
            volumeMounts:
            - name: backup
              mountPath: /backup
          
          volumes:
          - name: backup
            emptyDir: {}
          
          restartPolicy: OnFailure
```

---

## ⚠️ КРИТИЧЕСКИЕ ОГРАНИЧЕНИЯ ФАЗЫ 18

**✅ Что реализовано:**
- Kubernetes orchestration
- High availability (multi-pod deployments)
- Auto-scaling (HPA)
- Zero-downtime updates (Rolling updates)
- Health checks (liveness, readiness)
- ConfigMaps и Secrets
- Persistent storage (StatefulSets)
- Monitoring integration (Prometheus)

**❌ Что НЕ реализовано:**
- Multi-cluster deployment (cross-region)
- Service mesh advanced features (Istio full)
- GitOps (ArgoCD/Flux)
- Advanced security (mTLS, OPA policies)
- Cost optimization (spot instances, bin packing)

---

## 🚀 DEPLOYMENT WORKFLOW

### Step 1: Build Docker images

```bash
# Build Strategy Manager
docker build -t cryptotehnolog/strategy-manager:v1.0.0 \
             -f docker/strategy-manager/Dockerfile .

# Push to registry
docker push cryptotehnolog/strategy-manager:v1.0.0
```

### Step 2: Deploy к Kubernetes

```bash
# Create namespace
kubectl create namespace cryptotehnolog

# Apply configs
kubectl apply -f k8s/configmaps/
kubectl apply -f k8s/secrets/
kubectl apply -f k8s/storage/
kubectl apply -f k8s/databases/
kubectl apply -f k8s/deployments/
kubectl apply -f k8s/services/
kubectl apply -f k8s/autoscaling/

# Verify
kubectl get pods -n cryptotehnolog
```

### Step 3: Zero-downtime update

```bash
# Update image version
kubectl set image deployment/strategy-manager \
  strategy-manager=cryptotehnolog/strategy-manager:v1.1.0 \
  -n cryptotehnolog

# Monitor rollout
kubectl rollout status deployment/strategy-manager -n cryptotehnolog

# Rollback если проблема
kubectl rollout undo deployment/strategy-manager -n cryptotehnolog
```

---

## ФАЙЛОВАЯ СТРУКТУРА

```
CRYPTOTEHNOLOG/
├── k8s/
│   ├── namespace.yaml
│   ├── configmaps/
│   │   ├── strategy-manager.yaml
│   │   ├── market-data.yaml
│   │   └── ...
│   ├── secrets/
│   │   ├── exchange-api-keys.yaml
│   │   ├── postgresql.yaml
│   │   └── ...
│   ├── storage/
│   │   └── persistent-volumes.yaml
│   ├── databases/
│   │   ├── postgresql-statefulset.yaml
│   │   ├── timescaledb-statefulset.yaml
│   │   └── redis-cluster.yaml
│   ├── deployments/
│   │   ├── strategy-manager.yaml
│   │   ├── market-data.yaml
│   │   ├── signal-generator.yaml
│   │   └── ...
│   ├── services/
│   │   └── *.yaml
│   └── autoscaling/
│       └── *.yaml
│
└── docker/
    ├── strategy-manager/
    │   └── Dockerfile
    ├── market-data/
    │   └── Dockerfile
    └── ...
```

---

## ACCEPTANCE CRITERIA

### High Availability
- [ ] Multi-pod deployments (2+ replicas)
- [ ] Anti-affinity rules
- [ ] Auto-restart на failures
- [ ] Database replication

### Scalability
- [ ] HorizontalPodAutoscaler
- [ ] CPU/Memory-based scaling
- [ ] StatefulSets для databases

### Reliability
- [ ] Health checks (liveness, readiness)
- [ ] Rolling updates (zero downtime)
- [ ] Rollback capability
- [ ] Automated backups

### Security
- [ ] Secrets management
- [ ] RBAC policies
- [ ] Network policies

---

## ИТОГОВАЯ ГОТОВНОСТЬ

**Фаза 18: Distributed Deployment** готова к реализации! 🚀
