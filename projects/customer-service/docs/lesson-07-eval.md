# 第 7 课：效果评估

> 评估智能客服系统效果

---

## 📖 学习目标

完成本课后，你将能够：

- ✅ 设计评估指标体系
- ✅ 实现自动化测试
- ✅ 进行 A/B 测试
- ✅ 收集用户反馈

**预计时间：** 2-3 小时

---

## 🎯 一、评估指标体系

### 1.1 技术指标

| 指标 | 说明 | 目标值 |
|------|------|--------|
| **响应时间** | 平均响应时间 | < 2 秒 |
| **准确率** | 正确答案比例 | > 85% |
| **召回率** | 检索到相关知识比例 | > 90% |
| **F1 分数** | 准确率和召回率调和平均 | > 0.85 |
| **意图识别准确率** | 意图识别正确比例 | > 90% |

### 1.2 业务指标

| 指标 | 说明 | 目标值 |
|------|------|--------|
| **解决率** | 首次对话解决问题比例 | > 70% |
| **转人工率** | 转接人工客服比例 | < 20% |
| **用户满意度** | 用户评分（1-5 分） | > 4.0 |
| **平均对话轮数** | 解决问题的平均轮数 | < 5 轮 |

### 1.3 成本指标

| 指标 | 说明 | 目标值 |
|------|------|--------|
| **单次对话成本** | API 调用成本 | < ¥0.01 |
| **人力节省** | 替代人工客服比例 | > 50% |
| **ROI** | 投资回报率 | > 300% |

---

## 💻 二、自动化测试

### 2.1 测试数据集

```python
# tests/test_data.py
TEST_CASES = [
    {
        "question": "怎么退货？",
        "expected_intent": "return",
        "expected_keywords": ["订单", "退货", "流程"]
    },
    {
        "question": "退款多久到账？",
        "expected_intent": "refund",
        "expected_keywords": ["退款", "到账", "工作日"]
    },
    {
        "question": "多久能发货？",
        "expected_intent": "shipping",
        "expected_keywords": ["发货", "工作日", "当天"]
    },
    # ... 更多测试用例
]
```

### 2.2 单元测试

```python
# tests/test_rag.py
import pytest
from src.rag.retriever import RAGRetriever
from src.config import Config

@pytest.fixture
def retriever():
    config = Config.load()
    r = RAGRetriever(config)
    r.load_documents("data/knowledge")
    return r

@pytest.mark.asyncio
async def test_retrieve(retriever):
    """测试检索功能"""
    results = await retriever.retrieve("怎么退货？", top_k=3)
    
    assert len(results) > 0
    assert "退货" in results[0] or "订单" in results[0]

@pytest.mark.asyncio
async def test_retrieve_latency(retriever):
    """测试检索延迟"""
    import time
    
    start = time.time()
    await retriever.retrieve("怎么退货？", top_k=3)
    duration = time.time() - start
    
    assert duration < 0.1  # 延迟 < 100ms
```

### 2.3 集成测试

```python
# tests/test_agent.py
import pytest
from src.agent import CustomerServiceAgent
from src.config import Config

@pytest.fixture
def agent():
    config = Config.load()
    a = CustomerServiceAgent(config)
    a.load_knowledge("data/knowledge")
    return a

@pytest.mark.asyncio
async def test_chat(agent):
    """测试对话功能"""
    answer = await agent.chat("user_001", "怎么退货？")
    
    assert len(answer) > 0
    assert "退货" in answer or "订单" in answer

@pytest.mark.asyncio
async def test_session_management(agent):
    """测试会话管理"""
    # 第一轮
    await agent.chat("user_002", "我想退货")
    
    # 第二轮（应该记住上下文）
    answer = await agent.chat("user_002", "订单号是 123456")
    
    assert "123456" in answer or "收到" in answer
```

### 2.4 运行测试

```bash
# 安装测试依赖
pip install pytest pytest-asyncio

# 运行所有测试
pytest tests/ -v

# 运行特定测试
pytest tests/test_rag.py::test_retrieve -v

# 生成覆盖率报告
pytest --cov=src tests/
```

---

## 🧪 三、A/B 测试

### 3.1 A/B 测试设计

**测试场景：** 对比两种回答策略

- **A 组：** 简洁回答（100 字以内）
- **B 组：** 详细回答（300 字以内）

**指标：** 用户满意度

### 3.2 实现代码

```python
# src/ab_test.py
import random

class ABTest:
    def __init__(self):
        self.groups = {}  # user_id -> group (A or B)
    
    def get_group(self, user_id: str) -> str:
        """获取用户分组"""
        if user_id not in self.groups:
            # 随机分组
            self.groups[user_id] = random.choice(["A", "B"])
        return self.groups[user_id]
    
    def record_feedback(self, user_id: str, rating: int):
        """记录用户反馈"""
        group = self.get_group(user_id)
        # 存储到数据库
        # ...
    
    def get_results(self) -> Dict:
        """获取测试结果"""
        results = {
            "A": {"count": 0, "total_rating": 0},
            "B": {"count": 0, "total_rating": 0}
        }
        
        for user_id, group in self.groups.items():
            rating = self._get_user_rating(user_id)
            if rating:
                results[group]["count"] += 1
                results[group]["total_rating"] += rating
        
        # 计算平均分
        for group in results:
            if results[group]["count"] > 0:
                results[group]["avg_rating"] = \
                    results[group]["total_rating"] / results[group]["count"]
        
        return results
```

### 3.3 结果分析

```python
# 分析 A/B 测试结果
from scipy import stats

def analyze_ab_test(group_a, group_b):
    """统计分析"""
    # t 检验
    t_stat, p_value = stats.ttest_ind(group_a, group_b)
    
    print(f"A 组平均分：{np.mean(group_a):.2f}")
    print(f"B 组平均分：{np.mean(group_b):.2f}")
    print(f"p 值：{p_value:.4f}")
    
    if p_value < 0.05:
        print("✅ 差异显著")
    else:
        print("❌ 差异不显著")
```

---

## 💬 四、用户反馈

### 4.1 反馈收集

```python
# src/feedback.py
from typing import Optional

class FeedbackCollector:
    def __init__(self):
        self.feedbacks = []
    
    def submit(self, user_id: str, rating: int, comment: Optional[str] = None):
        """提交反馈"""
        self.feedbacks.append({
            "user_id": user_id,
            "rating": rating,
            "comment": comment,
            "timestamp": time.time()
        })
    
    def get_stats(self) -> Dict:
        """获取统计"""
        if not self.feedbacks:
            return {"avg_rating": 0, "count": 0}
        
        ratings = [f["rating"] for f in self.feedbacks]
        return {
            "avg_rating": sum(ratings) / len(ratings),
            "count": len(ratings),
            "distribution": {
                "5": sum(1 for r in ratings if r == 5),
                "4": sum(1 for r in ratings if r == 4),
                "3": sum(1 for r in ratings if r == 3),
                "2": sum(1 for r in ratings if r == 2),
                "1": sum(1 for r in ratings if r == 1),
            }
        }
```

### 4.2 反馈界面

```html
<!-- frontend/feedback.html -->
<div id="feedback">
    <p>请为本次服务评分：</p>
    <div class="stars">
        <span onclick="rate(1)">⭐</span>
        <span onclick="rate(2)">⭐</span>
        <span onclick="rate(3)">⭐</span>
        <span onclick="rate(4)">⭐</span>
        <span onclick="rate(5)">⭐</span>
    </div>
    <textarea id="comment" placeholder="留下您的意见..."></textarea>
    <button onclick="submit()">提交</button>
</div>

<script>
let currentRating = 0;

function rate(rating) {
    currentRating = rating;
    // 更新 UI
}

async function submit() {
    await fetch('/api/feedback', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            rating: currentRating,
            comment: document.getElementById('comment').value
        })
    });
    alert('感谢反馈！');
}
</script>
```

---

## 📊 五、性能基准

### 5.1 基准测试

```python
# tests/benchmark.py
import asyncio
import time
from locust import HttpUser, task, between

class CustomerServiceUser(HttpUser):
    wait_time = between(1, 3)
    
    @task
    def chat(self):
        questions = [
            "怎么退货？",
            "退款多久到账？",
            "多久能发货？"
        ]
        
        self.client.post("/api/chat", json={
            "user_id": "test_user",
            "message": random.choice(questions)
        })
```

### 5.2 运行基准测试

```bash
# 安装 Locust
pip install locust

# 运行测试
locust -f tests/benchmark.py --host=http://localhost:8000

# 访问 http://localhost:8089
# 设置并发用户数，开始测试
```

### 5.3 性能报告

| 并发用户 | P50 | P95 | P99 | 错误率 |
|----------|-----|-----|-----|--------|
| 10 | 0.5s | 1.0s | 1.5s | 0% |
| 50 | 0.8s | 1.5s | 2.0s | 0.1% |
| 100 | 1.2s | 2.0s | 3.0s | 0.5% |
| 200 | 2.0s | 3.5s | 5.0s | 2% |

---

## ✅ 六、动手实践

### 6.1 练习 1：编写测试用例

```python
# 添加 10 个测试用例到 tests/test_data.py
TEST_CASES = [
    # ... 你的测试用例
]
```

### 6.2 练习 2：运行自动化测试

```bash
# 运行所有测试
pytest tests/ -v

# 查看覆盖率
pytest --cov=src tests/
```

### 6.3 练习 3：收集用户反馈

```python
# 集成反馈收集
# 修改前端添加评分功能
```

---

## 📝 七、课后作业

### 必做题

1. **编写测试用例**
   - 至少 10 个测试用例
   - 覆盖所有意图

2. **运行自动化测试**
   - 通过所有测试
   - 查看覆盖率报告

3. **设计评估指标**
   - 为你的场景设计指标
   - 设定目标值

### 选做题

1. **实现 A/B 测试**
   - 对比两种策略
   - 分析结果

2. **性能基准测试**
   - 压力测试
   - 找出瓶颈

3. **用户反馈分析**
   - 收集反馈
   - 提出改进建议

---

## 📚 八、参考资料

### 8.1 测试

- [pytest 文档](https://docs.pytest.org/)
- [Locust 性能测试](https://locust.io/)

### 8.2 A/B 测试

- [A/B 测试最佳实践](https://www.optimizely.com/optimization-glossary/ab-testing/)
- [统计学基础](https://en.wikipedia.org/wiki/A/B_testing)

### 8.3 用户反馈

- [NPS 净推荐值](https://www.qualtrics.com/experience-management/nps/)
- [CSAT 客户满意度](https://www.surveymonkey.com/mp/customer-satisfaction-score-csat/)

---

## 🎓 九、课程总结

恭喜完成智能客服系统课程！

**你已掌握：**
- ✅ RAG 知识检索
- ✅ Session 管理
- ✅ 流式输出
- ✅ 意图识别
- ✅ 部署监控
- ✅ 效果评估

**下一步：**
- 📖 学习下一个实战项目
- 🏗️ 应用到生产环境
- 🤝 贡献代码到社区

---

**持续更新中...**

_最后更新：2026-03-12_

_作者：付艺锦 + ai2 (claw 后端机器人)_
