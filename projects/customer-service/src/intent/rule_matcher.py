#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
意图识别 - 规则匹配模块

融合课程：s03 (TodoWrite 任务规划)

功能：
1. 关键词匹配
2. 正则表达式匹配
3. 意图分类
"""

import re
from typing import Dict, List, Tuple


class RuleMatcher:
    """规则匹配器"""
    
    def __init__(self):
        """初始化匹配器"""
        # 意图规则库
        self.rules = {
            # 退货相关
            "return": [
                r"退货",
                r"退.*货",
                r"不要.*了",
                r"想退",
            ],
            
            # 退款相关
            "refund": [
                r"退款",
                r"退.*钱",
                r"钱.*退",
            ],
            
            # 物流相关
            "shipping": [
                r"发货",
                r"物流",
                r"快递",
                r"多久.*到",
                r"什么时候.*到",
            ],
            
            # 发票相关
            "invoice": [
                r"发票",
                r"专票",
                r"普票",
                r"开票",
            ],
            
            # 优惠相关
            "discount": [
                r"优惠",
                r"折扣",
                r"便宜",
                r"打折",
            ],
            
            # 售后相关
            "support": [
                r"维修",
                r"售后",
                r"质量.*问题",
                r"坏了",
            ],
        }
        
        # 编译正则表达式
        self.compiled_rules = {}
        for intent, patterns in self.rules.items():
            self.compiled_rules[intent] = [
                re.compile(pattern, re.IGNORECASE)
                for pattern in patterns
            ]
    
    def match(self, text: str) -> str:
        """
        匹配意图
        
        参数:
            text: 用户输入
        
        返回:
            意图标签
        """
        scores: Dict[str, int] = {}
        
        # 遍历所有规则
        for intent, patterns in self.compiled_rules.items():
            for pattern in patterns:
                if pattern.search(text):
                    scores[intent] = scores.get(intent, 0) + 1
        
        # 返回得分最高的意图
        if scores:
            best_intent = max(scores, key=scores.get)
            return best_intent
        
        # 默认意图
        return "faq"
    
    def add_rule(self, intent: str, pattern: str):
        """
        添加规则
        
        参数:
            intent: 意图标签
            pattern: 正则表达式
        """
        if intent not in self.rules:
            self.rules[intent] = []
            self.compiled_rules[intent] = []
        
        self.rules[intent].append(pattern)
        self.compiled_rules[intent].append(
            re.compile(pattern, re.IGNORECASE)
        )
    
    def get_intents(self) -> List[str]:
        """获取所有意图标签"""
        return list(self.rules.keys())
