#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能客服系统 - 主入口

融合课程：
- adv02 (Session 管理)
- adv04 (RAG 知识检索)
- adv06 (流式输出)

使用方法：
    python src/main.py
"""

import asyncio
import sys
import logging
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agent import CustomerServiceAgent
from src.config import Config

# 配置日志
logger = logging.getLogger(__name__)


async def main():
    """主函数"""
    print("=" * 60)
    print("🤖 智能客服系统")
    print("=" * 60)
    
    # 1. 加载配置
    config = Config.load()
    config.setup_logging()  # 配置日志系统
    logger.info(f"配置加载成功：{config.log_level}")
    print(f"✅ 配置加载成功：{config.log_level}")
    
    # 2. 初始化 Agent
    agent = CustomerServiceAgent(config)
    logger.info("Agent 初始化成功")
    print("✅ Agent 初始化成功")
    
    # 3. 加载知识库
    agent.load_knowledge(config.knowledge_path)
    logger.info(f"知识库加载成功：{config.knowledge_path}")
    print(f"✅ 知识库加载成功")
    
    # 4. 开始对话
    print("\n" + "=" * 60)
    print("🤖 客服助手已就绪，输入你的问题（输入 quit 退出）：")
    print("=" * 60 + "\n")
    
    user_id = "user_001"  # 简化：单用户模式
    
    while True:
        try:
            # 获取用户输入
            user_input = input("👤 你：").strip()
            
            # 退出命令
            if user_input.lower() in ["quit", "exit", "bye"]:
                logger.info("用户退出对话")
                print("\n👋 再见！")
                break
            
            # 跳过空输入
            if not user_input:
                continue
            
            logger.info(f"用户输入：{user_input}")
            
            # 5. 处理对话
            print("🤖 客服：", end="", flush=True)
            answer = await agent.chat(user_id, user_input)
            print()  # 换行
            
            logger.info(f"回答：{answer[:100]}...")
            
        except KeyboardInterrupt:
            logger.info("用户中断对话")
            print("\n\n👋 中断退出")
            break
        except Exception as e:
            logger.error(f"对话错误：{e}", exc_info=True)
            print(f"\n❌ 错误：{e}")
    
    print("\n" + "=" * 60)
    print("感谢使用智能客服系统！")
    print("=" * 60)
    
    # 输出统计信息
    stats = agent.get_stats()
    logger.info(f"对话统计：{stats}")
    print(f"\n📊 对话统计：{stats['total_queries']} 次询问，{stats['successful_queries']} 次成功，{stats['failed_queries']} 次失败")


if __name__ == "__main__":
    asyncio.run(main())
