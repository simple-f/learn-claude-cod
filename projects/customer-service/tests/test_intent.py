#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
意图识别测试

测试内容：
- 规则匹配
- 意图分类
- 置信度
- 多意图识别
"""

import pytest
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.intent.rule_matcher import RuleMatcher


@pytest.fixture
def matcher():
    """规则匹配器"""
    return RuleMatcher()


class TestRuleMatcher:
    """规则匹配器测试"""
    
    def test_match_return(self, matcher):
        """测试退货意图"""
        test_cases = [
            "我想退货",
            "怎么退货",
            "这个不要了",
            "退掉这个商品"
        ]
        
        for text in test_cases:
            intent = matcher.match(text)
            assert intent == "return", f"期望 return，实际{intent}：{text}"
        
        print("✅ 退货意图识别成功")
    
    def test_match_refund(self, matcher):
        """测试退款意图"""
        test_cases = [
            "怎么退款",
            "退款多久到账",
            "退钱"
        ]
        
        for text in test_cases:
            intent = matcher.match(text)
            assert intent == "refund", f"期望 refund，实际{intent}：{text}"
        
        print("✅ 退款意图识别成功")
    
    def test_match_shipping(self, matcher):
        """测试物流意图"""
        test_cases = [
            "多久能发货",
            "物流查询",
            "快递什么时候到"
        ]
        
        for text in test_cases:
            intent = matcher.match(text)
            assert intent == "shipping", f"期望 shipping，实际{intent}：{text}"
        
        print("✅ 物流意图识别成功")
    
    def test_match_invoice(self, matcher):
        """测试发票意图"""
        test_cases = [
            "能开发票吗",
            "专票怎么开",
            "发票问题"
        ]
        
        for text in test_cases:
            intent = matcher.match(text)
            assert intent == "invoice", f"期望 invoice，实际{intent}：{text}"
        
        print("✅ 发票意图识别成功")
    
    def test_match_discount(self, matcher):
        """测试优惠意图"""
        test_cases = [
            "有优惠吗",
            "能打折吗",
            "便宜点"
        ]
        
        for text in test_cases:
            intent = matcher.match(text)
            assert intent == "discount", f"期望 discount，实际{intent}：{text}"
        
        print("✅ 优惠意图识别成功")
    
    def test_match_support(self, matcher):
        """测试售后意图"""
        test_cases = [
            "质量有问题",
            "坏了怎么修",
            "售后服务"
        ]
        
        for text in test_cases:
            intent = matcher.match(text)
            assert intent == "support", f"期望 support，实际{intent}：{text}"
        
        print("✅ 售后意图识别成功")
    
    def test_match_faq(self, matcher):
        """测试默认 FAQ 意图"""
        test_cases = [
            "你好",
            "在吗",
            "随便问问"
        ]
        
        for text in test_cases:
            intent = matcher.match(text)
            assert intent == "faq", f"期望 faq，实际{intent}：{text}"
        
        print("✅ FAQ 意图识别成功")
    
    def test_add_rule(self, matcher):
        """测试添加规则"""
        matcher.add_rule("test_intent", r"测试.*意图")
        
        intent = matcher.match("测试一下意图")
        assert intent == "test_intent", f"期望 test_intent，实际{intent}"
        
        print("✅ 添加规则成功")
    
    def test_get_intents(self, matcher):
        """测试获取所有意图"""
        intents = matcher.get_intents()
        
        assert len(intents) > 0, "意图列表为空"
        assert "return" in intents, "缺少退货意图"
        assert "refund" in intents, "缺少退款意图"
        
        print(f"✅ 意图列表：{intents}")
    
    def test_accuracy(self, matcher):
        """测试准确率"""
        test_data = [
            ("我想退货", "return"),
            ("怎么退款", "refund"),
            ("多久能发货", "shipping"),
            ("能开发票吗", "invoice"),
            ("有优惠吗", "discount"),
            ("质量有问题", "support"),
            ("你好", "faq"),
        ]
        
        correct = 0
        for text, expected in test_data:
            intent = matcher.match(text)
            if intent == expected:
                correct += 1
        
        accuracy = correct / len(test_data)
        assert accuracy >= 0.8, f"准确率过低：{accuracy:.2f}"
        
        print(f"✅ 准确率：{accuracy:.1%} ({correct}/{len(test_data)})")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
