# 第 6 课：部署与监控

> 生产环境部署与监控

---

## 📖 学习目标

完成本课后，你将能够：

- ✅ 实现 Docker 容器化部署
- ✅ 配置性能监控
- ✅ 收集与分析日志
- ✅ 设置告警规则

**预计时间：** 3-4 小时

---

## 🎯 一、Docker 容器化

### 1.1 为什么用 Docker？

**传统部署问题：**
- ❌ 环境不一致（开发/生产）
- ❌ 依赖冲突
- ❌ 部署复杂

**Docker 优势：**
- ✅ 环境一致
- ✅ 一键部署
- ✅ 易于扩展

### 1.2 Dockerfile

```dockerfile
# Dockerfile
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码
COPY src/ ./src/
COPY data/ ./data/

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV LOG_LEVEL=INFO

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["python", "src/web_server.py"]
```

### 1.3 docker-compose.yml

```yaml
# docker-compose.yml
version: '3.8'

services:
  customer-service:
    build: .
    ports:
      - "8000:8000"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - VECTOR_DB_PATH=/app/data/vector_db
      - LOG_LEVEL=INFO
    volumes:
      - ./data:/app/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  # 可选：Redis 用于 Session 存储
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    restart: unless-stopped

volumes:
  redis_data:
```

### 1.4 部署命令

```bash
# 构建镜像
docker-compose build

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down

# 扩容（3 个实例）
docker-compose up -d --scale customer-service=3
```

---

## 📊 二、性能监控

### 2.1 监控指标

| 指标 | 说明 | 告警阈值 |
|------|------|----------|
| **响应时间** | API 平均响应时间 | > 2 秒 |
| **错误率** | 5xx 错误比例 | > 1% |
| **QPS** | 每秒请求数 | > 100 |
| **内存使用** | 容器内存占用 | > 500MB |
| **CPU 使用** | 容器 CPU 占用 | > 80% |

### 2.2 Prometheus 监控

```python
# src/monitor/metrics.py
from prometheus_client import Counter, Histogram, generate_latest
import time

# 定义指标
REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
REQUEST_DURATION = Histogram('http_request_duration_seconds', 'HTTP request duration')

# 中间件
async def metrics_middleware(request, call_next):
    start_time = time.time()
    
    response = await call_next(request)
    
    duration = time.time() - start_time
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code
    ).inc()
    REQUEST_DURATION.observe(duration)
    
    return response

# 暴露指标端点
@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type="text/plain")
```

### 2.3 Grafana 看板

```json
{
  "dashboard": {
    "title": "智能客服监控",
    "panels": [
      {
        "title": "QPS",
        "targets": [
          {
            "expr": "rate(http_requests_total[1m])"
          }
        ]
      },
      {
        "title": "响应时间",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, http_request_duration_seconds_bucket)"
          }
        ]
      },
      {
        "title": "错误率",
        "targets": [
          {
            "expr": "rate(http_requests_total{status=~\"5..\"}[1m]) / rate(http_requests_total[1m])"
          }
        ]
      }
    ]
  }
}
```

---

## 📝 三、日志收集

### 3.1 日志配置

```python
# src/config.py
import logging

def setup_logging(log_level: str = "INFO"):
    """配置日志"""
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("data/logs/app.log"),
            logging.StreamHandler()
        ]
    )
```

### 3.2 结构化日志

```python
# src/agent.py
import json
import logging

logger = logging.getLogger(__name__)

async def chat(self, user_id: str, message: str):
    """处理对话（带日志）"""
    start_time = time.time()
    
    try:
        # 记录请求
        logger.info(json.dumps({
            "event": "chat_request",
            "user_id": user_id,
            "message": message
        }))
        
        # 处理逻辑
        answer = await self._process(message)
        
        # 记录响应
        duration = time.time() - start_time
        logger.info(json.dumps({
            "event": "chat_response",
            "user_id": user_id,
            "duration": duration,
            "answer_length": len(answer)
        }))
        
        return answer
        
    except Exception as e:
        # 记录错误
        logger.error(json.dumps({
            "event": "chat_error",
            "user_id": user_id,
            "error": str(e)
        }), exc_info=True)
        raise
```

### 3.3 ELK 日志栈

```yaml
# docker-compose.logging.yml
version: '3.8'

services:
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.5.0
    environment:
      - discovery.type=single-node
    volumes:
      - es_data:/usr/share/elasticsearch/data

  logstash:
    image: docker.elastic.co/logstash/logstash:8.5.0
    volumes:
      - ./logstash.conf:/usr/share/logstash/pipeline/logstash.conf

  kibana:
    image: docker.elastic.co/kibana/kibana:8.5.0
    ports:
      - "5601:5601"

volumes:
  es_data:
```

---

## 🚨 四、告警配置

### 4.1 告警规则

```yaml
# alerting_rules.yml
groups:
  - name: customer-service-alerts
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[1m]) / rate(http_requests_total[1m]) > 0.01
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "错误率过高"
          description: "错误率超过 1%"

      - alert: HighLatency
        expr: histogram_quantile(0.95, http_request_duration_seconds_bucket) > 2
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "响应时间过长"
          description: "P95 响应时间超过 2 秒"

      - alert: ServiceDown
        expr: up{job="customer-service"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "服务宕机"
          description: "客服服务已宕机"
```

### 4.2 告警通知

```yaml
# alertmanager.yml
route:
  receiver: 'slack-notifications'
  group_by: ['alertname']
  group_wait: 30s
  group_interval: 5m

receivers:
  - name: 'slack-notifications'
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/XXX/YYY/ZZZ'
        channel: '#alerts'
        title: '{{ .GroupLabels.alertname }}'
        text: '{{ range .Alerts }}{{ .Annotations.description }}{{ end }}'
```

---

## ✅ 五、动手实践

### 5.1 练习 1：Docker 部署

```bash
# 1. 构建镜像
cd projects/customer-service
docker build -t customer-service .

# 2. 运行容器
docker run -d -p 8000:8000 \
  --env OPENAI_API_KEY=sk-xxx \
  customer-service

# 3. 测试
curl http://localhost:8000/health
```

### 5.2 练习 2：配置监控

```bash
# 1. 启动 Prometheus
docker run -d -p 9090:9090 prom/prometheus

# 2. 访问 http://localhost:9090
# 3. 查询指标：http_requests_total
```

### 5.3 练习 3：查看日志

```bash
# 查看 Docker 日志
docker logs customer-service

# 实时日志
docker logs -f customer-service

# 查看应用日志
tail -f data/logs/app.log
```

---

## 📝 六、课后作业

### 必做题

1. **Docker 部署**
   - 编写 Dockerfile
   - 成功运行容器

2. **配置监控**
   - 集成 Prometheus
   - 查看监控指标

3. **日志收集**
   - 配置结构化日志
   - 分析日志内容

### 选做题

1. **配置告警**
   - 设置告警规则
   - 测试告警通知

2. **性能优化**
   - 压力测试
   - 找出瓶颈

3. **高可用部署**
   - 多实例部署
   - 负载均衡

---

## 📚 七、参考资料

### 7.1 Docker

- [Docker 官方文档](https://docs.docker.com/)
- [Docker 最佳实践](https://docs.docker.com/develop/develop-images/dockerfile_best-practices/)

### 7.2 监控

- [Prometheus 文档](https://prometheus.io/docs/)
- [Grafana 看板](https://grafana.com/grafana/dashboards/)

### 7.3 日志

- [ELK Stack 文档](https://www.elastic.co/guide/index.html)
- [结构化日志最佳实践](https://www.loggly.com/ultimate-guide/structured-logging-basics/)

---

## 🎯 八、下节预告

**第 7 课：效果评估**

- ✅ 评估指标设计
- ✅ 自动化测试
- ✅ A/B 测试
- ✅ 用户反馈

**前置知识：**
- 理解部署监控
- 完成本课实践
- 配置过告警

---

**持续更新中...**

_最后更新：2026-03-12_

_作者：付艺锦 + ai2 (claw 后端机器人)_
