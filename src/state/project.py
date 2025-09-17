import os
import yaml
import random
import json
from typing import List, Dict

from langchain_core.messages import HumanMessage, SystemMessage, trim_messages
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableWithMessageHistory
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain_core.chat_history import BaseChatMessageHistory, InMemoryChatMessageHistory
from langchain.memory import ConversationBufferMemory
from langchain_community.llms import Tongyi

from config.api_config import DASHSCOPE_API_KEY
from src.common.utils import read_pdf, read_json, clean_str, update_test_status
from src.common.history import LocalChatHistory

store = {}

def get_session_history(session_id: str) -> BaseChatMessageHistory:
    if session_id not in store:
        store[session_id] = InMemoryChatMessageHistory()

    return store[session_id]

def choose_project(experience: List[Dict]) -> Dict:
    """随机挑一个项目"""
    project = random.choice(experience)
    project_name = project["项目名称"]

    return project_name, project

def start_project_interview(session):
    session_id = session["session_id"]
    resume_json_path = session["resume_path"]
    resume = read_json(resume_json_path)

    projects = resume["项目经历"]
    
    project_name, project = choose_project(projects)
    project_name = clean_str(project_name)

    history_path = os.path.join(session["save_path"]["dialog"], f"{project_name}.json")
    chat_history = LocalChatHistory(session_id, history_path)

    # with open("./data/prompt/project_pompt.yaml", "r", encoding="utf-8") as f:
    #     system_prompt_dict = yaml.safe_load(f)
    
    # 将字典格式的提示词转换为字符串
    system_prompt = f"""
    角色：互联网大厂技术岗面试官
    背景：根据候选人的项目经历，对候选人的掌握程度进行考察。
    规则：
        1. 根据候选人的回答，选择进行追问或者考察一个项目别的方面的问题。
        2. 如果候选人的回答过于简单，可要求进行详细解释。
    输出：一个简洁直观的问题。
    """
    
    config = {"configurable": {"session_id": session_id}}

    prompt_template = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        MessagesPlaceholder(variable_name="messages")
    ])
    
    model_name, temperature = "qwen-turbo", 0.8
    model = Tongyi(api_key=DASHSCOPE_API_KEY, model_name=model_name, temperature=temperature)

    chain = prompt_template | model

    with_message_history = RunnableWithMessageHistory(chain, get_session_history)

    # 在历史记录中添加项目信息
    chat_history.history["topic"] = {
        "name": project_name,
        "details": project
    }
    chat_history.history["config"] = {
        "model_name": model_name,
        "temperature": temperature,
    }
    chat_history.history["type"] = session["current_state"]
    chat_history._save_history()

    opening = f"我看到你做了一个{project_name}的项目是吗，你来介绍一下吧"
    print(f"\n面试官：{opening}")
    chat_history.add_turn(opening, "开场对话，这轮对话不记入得分")

    for i in range(10):
        print("我：", end="")
        user_input = input()

        if user_input == "结束" or user_input.lower() == "quit":
            break
            
        try:
            response = with_message_history.invoke(
                {"messages": [HumanMessage(content=user_input)]},
                config=config
            )
            ai_response = str(response)
            print(f"\n面试官：{ai_response}")
            
            # 记录对话到本地存储
            chat_history.add_turn(ai_response, user_input)
            
        except Exception as e:
            print(f"Error: {e}")
    
    print(f"\n对话结束")
    project["topic"]["已考核"] = True
    update_test_status(resume_json_path, "项目经历", project_name)
    history_path = chat_history.end_session()
    
    generate_project_report(session, history_path)


def generate_project_report(session, file_path: str) -> dict:
    if not os.path.exists(file_path):
        print(f"错误：文件不存在 {file_path}")
        return {}

    with open(file_path, 'r', encoding='utf-8') as f:
        chat_history = json.load(f)

    # 1. 提取所需数据
    project_name = chat_history["topic"]["name"]
    project_details = chat_history["topic"]["details"]
    conversations = chat_history["conversations"]

    # 2. 定义提示词模板（与之前相同）
    system_prompt_str = """
    你是一名资深的互联网技术面试官，擅长对候选人的技术能力和项目经验进行深度评估。

    你的任务是基于我提供的面试对话记录，完成以下两项工作：
    1.  生成面试总结：从回答逻辑、技术深度、问题解决能力、沟通表达和项目掌握度等多个维度，对候选人进行全面评估，形成一份结构化的面试总结报告。
    2.  逐轮对话打分：对面试中的每一轮对话（一问一答），根据其技术含金量、回答的清晰度和逻辑性，给出1-10分的评分，并简要说明打分理由。
    3.  0-3分为表现差，4-7分为表现一般，8-10分为表现优秀。注意，除非回答真的很差或很优秀，否则不要轻易给差或者优秀档次的分数。

    请注意：你的语气应专业、客观，评估应完全基于对话内容，避免主观臆断。
    """

    user_prompt_str = """
    以下是本次面试的详细信息和对话记录：

    ---
    **面试信息**
    **候选人姓名**：{candidate_name}
    **面试项目**：{project_name}
    **项目描述**：
    {project_details}

    ---
    **对话记录**
    {conversations_text}

    ---
    请严格按照以下JSON格式输出结果，不要包含任何额外文字或解释：
    {{
    "summary": {{
        "overall_evaluation": "对候选人的总体评估。",
        "strengths": [
        "优势点1",
        "优势点2"
        ],
        "areas_for_improvement": [
        "可提升点1",
        "可提升点2"
        ],
        "final_recommendation": "（如：推荐/继续观察/不推荐，并说明理由）"
    }},
    "scores_by_turn": [
        {{
        "turn_id": 1,
        "score": 8,
        "reason": "简要说明打分理由。"
        }},
        {{
        "turn_id": 2,
        "score": 9,
        "reason": "简要说明打分理由。"
        }}
    ]
    }}
    """
    # 3. 准备调用链和LLM
    llm = Tongyi(api_key=DASHSCOPE_API_KEY, model_name="qwen-turbo", temperature=0.5) 
    prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content=system_prompt_str),
        HumanMessage(content=user_prompt_str)
    ])
    
    # 格式化对话记录
    conversations_text = ""
    for conv in conversations:
        conversations_text += f"第 {conv['turn_id']} 轮\n"
        conversations_text += f"面试官：{conv['agent']}\n"
        conversations_text += f"候选人：{conv['user']}\n\n"
        
    chain = prompt | llm | JsonOutputParser()

    # 4. 调用LLM并返回结果
    try:
        response = chain.invoke({
            "project_name": project_name,
            "project_details": json.dumps(project_details, ensure_ascii=False, indent=4),
            "conversations_text": conversations_text,
        })

        output_dir = session["save_path"]["summary"]
        
        base_filename = f"project_{project_name}.json"
        output_path = os.path.join(output_dir, base_filename)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(response, f, ensure_ascii=False, indent=4)
        
        print(f"{project_name}面试报告已保存到：{output_path}")

        return response
        
    except Exception as e:
        print(f"调用LLM或保存文件时发生错误: {e}")
        return {}
