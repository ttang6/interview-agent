import os
import yaml
import random
import json
from typing import List, Dict
from neo4j import GraphDatabase
from random import randint

from langchain_core.messages import HumanMessage, SystemMessage, trim_messages
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableWithMessageHistory
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain_core.chat_history import BaseChatMessageHistory, InMemoryChatMessageHistory
from langchain.memory import ConversationBufferMemory
from langchain_community.llms import Tongyi

from config.api_config import DASHSCOPE_API_KEY, NEO4J_PASSWORD
from src.common.utils import read_pdf, read_json, clean_str, update_test_status, side_llm_request, generate_question_tags
from src.common.history import LocalChatHistory
from src.graph.graph import get_question, get_related_question
from src.common.history import LocalChatHistory

store = {}

def get_session_history(session_id: str) -> BaseChatMessageHistory:
    if session_id not in store:
        store[session_id] = InMemoryChatMessageHistory()

    return store[session_id]


def start_theory_interview(session):
    """
    开始理论面试流程
    """
    session_id = session["session_id"]
    resume_json_path = session["resume_path"]
    resume = read_json(resume_json_path)
    
    # 获取简历中的技术栈分析
    coding_language = resume["技术总结"]["语言"]
    potential_position = resume["技术总结"]["岗位"]
    
    # 询问候选人熟悉的语言
    opening = "你熟悉哪个开发语言？"
    print(f"\n面试官：{opening}")

    print("我：", end="")
    user_input = input()

    # 解析用户输入的语言
    side_prompt = "解析输入，确定并返回用户表明的熟悉的编程语言的名字，全部小写，如: python。如果是语言是c++，并且有提到版本，请返回c++的版本，例如：c++11，否则返回c++"
    side_result = side_llm_request(side_prompt, user_input)
    
    if side_result.lower() == "c++":
        opening = "有了解c++的一些新特性吗？"
        print(f"\n面试官：{opening}")

        print("我：", end="")
        user_refine_input = input()

        side_prompt = "解析输入，确定并返回用户表明的熟悉的c++的版本，全字母小写，例如：c++11，如果不能确定则返回c++"
        side_result = side_llm_request(side_prompt, user_input + " " + user_refine_input)
    
    coding_language = side_result.lower()

    opening = f"好，那先来看看你对这个语言的掌握程度。"
    print(f"\n面试官：{opening}")

    question_tags = generate_question_tags(coding_language, potential_position)
    
    # 初始化对话历史
    history_path = os.path.join(session["save_path"]["dialog"], f"theory.json")
    chat_history = LocalChatHistory(session_id, history_path)
    
    # 设置系统提示词 - 明确LLM的角色
    system_prompt = f"""
    角色：互联网大厂技术岗面试官
    背景：正在对候选人进行计算机相关的理论知识考察
    规则：根据用户的输入，判断用户正在回答的是什么问题，然后追问一个相关的问题，可以比较简单，也可以更难
    输出：一个问题
    """
    
    # 配置LLM
    config = {"configurable": {"session_id": session_id}}
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        MessagesPlaceholder(variable_name="messages")
    ])
    
    model_name, temperature = "qwen-turbo", 0.8
    model = Tongyi(api_key=DASHSCOPE_API_KEY, model_name=model_name, temperature=temperature)
    chain = prompt_template | model
    with_message_history = RunnableWithMessageHistory(chain, get_session_history)
    
    # 在历史记录中添加面试信息
    chat_history.history["topic"] = {
        "coding_language": coding_language,
        "potential_position": potential_position,
    }
    chat_history.history["config"] = {
        "model_name": model_name,
        "temperature": temperature,
    }
    chat_history.history["type"] = session["current_state"]
    chat_history._save_history()
    
    asked_questions = set()
    should_exit = False  # 添加全局退出标志

    # 遍历question_tags中的每个tag_list
    for tag_list in question_tags:
        if should_exit:
            break
            
        # 遍历每个tag_list中的tag
        for tag in tag_list:
            if should_exit:
                break
                
            # 1. 从图谱获取第一个问题
            current_question = get_question(tag, asked_questions)
            if not current_question:
                print(f"\n没有找到标签'{tag}'的问题，跳过")
                continue
                
            asked_questions.add(current_question["id"])
            print(f"\n面试官：{current_question['question']}")

            print("我：", end="")
            user_input = input()

            if user_input == "结束" or user_input.lower() == "quit":
                should_exit = True
                break

            # 记录图谱问题和用户回答
            chat_history.add_turn(current_question["question"], user_input)

            # LLM追问一次 - 使用side_llm_request方法
            try:
                # 构造包含问题和回答的上下文
                context_prompt = f"""
                角色：互联网大厂技术岗面试官
                背景：正在对候选人进行计算机相关的理论知识考察
                规则：根据面试官的问题和候选人的回答，生成一个追问问题
                要求：
                  1. 如果候选人表现出回答困难，不要进行类似‘换一个角度思考这个问题’的发问，而是考虑询问类似主题下的其他比较简单的问题
                  2. 如果候选人回答过于简单，追问可以选择要求进行详细解释或举例解释
                  3. 如果候选人回答比较规范，追问可以发散更难的题目，也可以选择简单的问题
                限制：输出不要出现形如‘追问’
                输出：一个问题
                """
                
                # 将面试官问题和候选人回答作为user_input传给side_llm_request
                combined_input = f"面试官问题：{current_question['question']}\n候选人回答：{user_input}\n\n请生成一个追问问题："
                follow_up_question = side_llm_request(context_prompt, combined_input)
                print(f"\n面试官：{follow_up_question}")

                print("我：", end="")
                user_input = input()
                
                if user_input == "结束" or user_input.lower() == "quit":
                    should_exit = True
                    break

                # 记录LLM追问和用户回答
                chat_history.add_turn(follow_up_question, user_input)
                
            except Exception as e:
                print(f"LLM追问出错: {e}")
            
            for i in range(randint(1, 1)):
                if should_exit:
                    break
                    
                # 获取与当前问题相关的下一个问题
                next_question = get_related_question(current_question["id"], asked_questions, top_k=5)
                if not next_question:
                    print(f"\n没有找到与'{current_question['question'][:20]}...'相关的问题，结束该tag的提问")
                    break
                    
                current_question = next_question  # 更新当前问题
                asked_questions.add(next_question["id"])
                print(f"\n面试官：{next_question['question']}")

                print("我：", end="")
                user_input = input()

                if user_input == "结束" or user_input.lower() == "quit":
                    should_exit = True
                    break
                
                # 记录相关问题和用户回答
                chat_history.add_turn(next_question["question"], user_input)

                # LLM追问
                try:
                    # 构造包含问题和回答的上下文
                    context_prompt = f"""
                    角色：互联网大厂技术岗面试官
                    背景：正在对候选人进行计算机相关的理论知识考察
                    规则：根据面试官的问题和候选人的回答，生成一个追问问题，可以比较简单，也可以更难
                    输出：一个问题
                    """
                    
                    # 将面试官问题和候选人回答作为user_input传给side_llm_request
                    combined_input = f"面试官问题：{next_question['question']}\n候选人回答：{user_input}\n\n请生成一个追问问题："
                    follow_up_question = side_llm_request(context_prompt, combined_input)
                    print(f"\n面试官：{follow_up_question}")

                    print("我：", end="")
                    user_input = input()
                    
                    if user_input == "结束" or user_input.lower() == "quit":
                        should_exit = True
                        break

                    # 记录LLM追问和用户回答
                    chat_history.add_turn(follow_up_question, user_input)
                    
                except Exception as e:
                    print(f"LLM追问出错: {e}")

    
    print(f"\n理论面试结束")
    
    # 结束会话
    history_path = chat_history.end_session()
    
    # 生成理论面试报告
    generate_theory_report(session, history_path)


def generate_theory_report(session, file_path: str) -> dict:
    """
    生成理论面试报告
    """
    if not os.path.exists(file_path):
        print(f"错误：文件不存在 {file_path}")
        return {}

    with open(file_path, 'r', encoding='utf-8') as f:
        chat_history = json.load(f)

    # 1. 提取所需数据
    test_field = [chat_history["topic"]["coding_language"]]
    test_field.extend(chat_history["topic"]["potential_position"])
    conversations = chat_history["conversations"]

    # 2. 定义提示词模板
    system_prompt_str = """
    你是一名专业的评估官，擅长对问答进行客观公正的评估。

    你的任务是基于问答对话记录，完成以下两项工作：
    1. 生成总体评估：从问题理解能力、回答准确性、回答完整性和表达清晰度等维度，对问答进行全面评估。
    2. 逐轮对话打分：对每一轮问答，主要根据回答的正确性、完整性和清晰度进行1-10分评分，并简要说明打分理由。
    3. 评分标准：0-4分为回答错误、不知道、模糊，5-7分为回答基本正确但不完整，8-10分为回答准确且完整。

    请注意：你的评估应基于对话内容的客观分析，主要关注回答的正确性和完整性，给分可以严格一点。
    """

    user_prompt_str = """
    以下是问答对话记录：

    {conversations_text}

    请严格按照以下JSON格式输出结果，不要包含任何额外文字或解释：
    {{
    "summary": {{
        "overall_evaluation": "对问答的总体评估，主要关注回答的正确性和完整性。",
        "strengths": [
        "优势点1",
        "优势点2"
        ],
        "areas_for_improvement": [
        "可提升点1",
        "可提升点2"
        ],
        "final_recommendation": "（如：表现优秀/表现良好/需要改进，并说明理由）"
    }},
    "scores_by_turn": [
        {{
        "turn_id": 1,
        "score": 8,
        "reason": "简要说明打分理由，主要基于回答的正确性。"
        }},
        {{
        "turn_id": 2,
        "score": 9,
        "reason": "简要说明打分理由，主要基于回答的正确性。"
        }}
    ]
    }}
    """
    
    # 3. 准备调用链和LLM
    llm = Tongyi(api_key=DASHSCOPE_API_KEY, model_name="qwen-turbo", temperature=0.5) 
    
    # 格式化对话记录
    conversations_text = ""
    for conv in conversations:
        conversations_text += f"第 {conv['turn_id']} 轮\n"
        conversations_text += f"问题：{conv['user']}\n"
        conversations_text += f"回答：{conv['agent']}\n\n"
    
    # 直接构造完整的用户提示词
    formatted_user_prompt = user_prompt_str.format(conversations_text=conversations_text)
    
    prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content=system_prompt_str),
        HumanMessage(content=formatted_user_prompt)
    ])
        
    chain = prompt | llm | JsonOutputParser()

    # 4. 调用LLM并返回结果
    try:
        response = chain.invoke({})

        output_dir = session["save_path"]["summary"]
        
        base_filename = f"theory.json"
        output_path = os.path.join(output_dir, base_filename)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(response, f, ensure_ascii=False, indent=4)
        
        print(f"问答评估报告已保存到：{output_path}")

        return response
        
    except Exception as e:
        print(f"调用LLM或保存文件时发生错误: {e}")
        return {}