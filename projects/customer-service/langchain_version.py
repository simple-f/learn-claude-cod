#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能客服系统 - LangChain 版本

对比课程：第 8 课（LangChain vs 我们的实现）

依赖安装：
    pip install langchain langchain-community openai faiss-cpu

使用方法：
    python langchain_version.py
"""

from langchain.agents import initialize_agent, Tool
from langchain.llms import OpenAI
from langchain.memory import ConversationBufferMemory
from langchain.vectorstores import FAISS
from langchain.embeddings import OpenAIEmbeddings
from langchain.chains import RetrievalQA
from langchain.document_loaders import TextLoader
from langchain.text_splitter import CharacterTextSplitter
import os
from dotenv import load_dotenv


def main():
    """主函数"""
    print("=" * 60)
    print("🤖 智能客服系统 - LangChain 版本")
    print("=" * 60)
    
    # 加载环境变量
    load_dotenv()
    
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ 错误：OPENAI_API_KEY 未配置")
        print("请复制 .env.example 为 .env 并填入 API Key")
        return
    
    # 1. 加载知识库
    print("\n📚 加载知识库...")
    try:
        loader = TextLoader("data/knowledge/faq.txt", encoding="utf-8")
        documents = loader.load()
        text_splitter = CharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        texts = text_splitter.split_documents(documents)
        print(f"✅ 加载 {len(texts)} 个文档片段")
    except Exception as e:
        print(f"❌ 加载知识库失败：{e}")
        print("请确保 data/knowledge/faq.txt 存在")
        return
    
    # 2. 创建向量数据库
    print("💾 创建向量数据库...")
    embeddings = OpenAIEmbeddings()
    vectorstore = FAISS.from_documents(texts, embeddings)
    print(f"✅ 向量数据库创建成功 ({len(texts)} 个向量)")
    
    # 3. 创建检索器
    print("🔍 创建检索器...")
    retriever = vectorstore.as_retriever(search_kwargs={"k": 3})
    
    # 4. 创建 QA Chain
    print("🔗 创建 QA Chain...")
    qa_chain = RetrievalQA.from_chain_type(
        llm=OpenAI(temperature=0),
        chain_type="stuff",
        retriever=retriever,
        return_source_documents=True
    )
    
    # 5. 创建内存（对话历史）
    print("💭 创建内存...")
    memory = ConversationBufferMemory(
        memory_key="chat_history",
        return_messages=True
    )
    
    # 6. 创建工具
    print("🛠️ 创建工具...")
    tools = [
        Tool(
            name="知识库查询",
            func=qa_chain.run,
            description="用于查询产品知识和常见问题"
        )
    ]
    
    # 7. 初始化 Agent
    print("🤖 初始化 Agent...")
    agent = initialize_agent(
        tools,
        OpenAI(temperature=0.7),
        agent="conversational-react-description",
        memory=memory,
        verbose=True
    )
    print("✅ Agent 初始化成功")
    
    # 8. 开始对话
    print("\n" + "=" * 60)
    print("🤖 客服助手已就绪，输入你的问题（输入 quit 退出）：")
    print("=" * 60 + "\n")
    
    while True:
        try:
            # 获取用户输入
            user_input = input("👤 你：").strip()
            
            # 退出命令
            if user_input.lower() in ["quit", "exit", "bye"]:
                print("\n👋 再见！")
                break
            
            # 跳过空输入
            if not user_input:
                continue
            
            # 9. 运行 Agent
            print("🤖 客服：", end="", flush=True)
            response = agent.run(user_input)
            print(response)
            
        except KeyboardInterrupt:
            print("\n\n👋 中断退出")
            break
        except Exception as e:
            print(f"\n❌ 错误：{e}")
    
    print("\n" + "=" * 60)
    print("感谢使用智能客服系统 - LangChain 版本！")
    print("=" * 60)


if __name__ == "__main__":
    main()
