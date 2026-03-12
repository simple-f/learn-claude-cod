#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置管理模块

融合课程：s05 (Skills 知识加载)
"""

import os
import logging
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv


class Config:
    """配置类"""
    
    def __init__(self):
        # OpenAI 配置
        self.openai_api_key: str = ""
        
        # 路径配置
        self.vector_db_path: str = "./data/vector_db"
        self.knowledge_path: str = "./data/knowledge"
        self.log_path: str = "./data/logs"
        
        # 服务配置
        self.log_level: str = "INFO"
        self.web_port: int = 8000
        self.session_timeout: int = 3600  # 1 小时
        
        # 模型配置
        self.max_context_length: int = 4000
        self.stream_delay: int = 100  # 毫秒
        
        # RAG 配置
        self.rag_top_k: int = 3
        self.embedding_model: str = "all-MiniLM-L6-v2"
    
    @classmethod
    def load(cls, env_file: str = ".env") -> 'Config':
        """从环境变量加载配置"""
        config = cls()
        
        # 加载 .env 文件
        env_path = Path(__file__).parent.parent / env_file
        if env_path.exists():
            load_dotenv(env_path)
        
        # 读取配置
        config.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        config.vector_db_path = os.getenv("VECTOR_DB_PATH", "./data/vector_db")
        config.knowledge_path = os.getenv("KNOWLEDGE_PATH", "./data/knowledge")
        config.log_level = os.getenv("LOG_LEVEL", "INFO")
        config.web_port = int(os.getenv("WEB_PORT", "8000"))
        config.session_timeout = int(os.getenv("SESSION_TIMEOUT", "3600"))
        config.max_context_length = int(os.getenv("MAX_CONTEXT_LENGTH", "4000"))
        config.stream_delay = int(os.getenv("STREAM_DELAY", "100"))
        
        # 创建必要目录
        Path(config.vector_db_path).mkdir(parents=True, exist_ok=True)
        Path(config.knowledge_path).mkdir(parents=True, exist_ok=True)
        Path(config.log_path).mkdir(parents=True, exist_ok=True)
        
        return config
    
    def validate(self) -> bool:
        """验证配置"""
        if not self.openai_api_key:
            logger.warning("OPENAI_API_KEY 未配置，将使用模拟响应")
        
        if not Path(self.knowledge_path).exists():
            raise ValueError(f"知识库路径不存在：{self.knowledge_path}")
        
        return True
    
    def setup_logging(self):
        """配置日志系统"""
        log_file = Path(self.log_path) / "app.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        logging.basicConfig(
            level=getattr(logging, self.log_level.upper(), logging.INFO),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        
        logger = logging.getLogger(__name__)
        logger.info(f"日志系统已初始化，级别：{self.log_level}")
    
    def __str__(self) -> str:
        """字符串表示"""
        return (
            f"Config(log_level={self.log_level}, "
            f"web_port={self.web_port}, "
            f"session_timeout={self.session_timeout})"
        )
