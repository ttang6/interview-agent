import os 
import dashscope
import requests
import json

from config.api_config import DASHSCOPE_API_KEY
    

def build_request(system_prompt, content):
    messages = [
        {'role': 'system', 'content': system_prompt},
        {'role': 'user', 'content': content}
    ]

    return messages


def get_llm_response(messages):
    try:
        url = 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions'

        headers = {
            'Authorization': f'Bearer {DASHSCOPE_API_KEY}',
            'Content-Type': 'application/json'
        }
        
        
        payload = {
            'model': 'qwen-plus',
            'messages': messages,
            # 仅当使用 Qwen3 系列模型且为非流式时需要显式关闭思考
            'extra_body': {'enable_thinking': False}
        }

        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code == 200:
            result = response.json()
            # 兼容模式返回与 OpenAI 一致
            return result['choices'][0]['message']['content']
        else:
            print(f'API请求失败，状态码: {response.status_code}')
            print(response.text)
            return None

    except Exception as e:
        print(f'API请求出错: {e}')
        return None