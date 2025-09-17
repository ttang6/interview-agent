import pdfplumber
import os
import yaml
import json
import re

from langchain_core.prompts import ChatPromptTemplate
from langchain_community.llms import Tongyi
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate

from config.api_config import DASHSCOPE_API_KEY

def read_pdf(pdf_path: str) -> str:
    """
    从指定的 PDF 文件路径中提取所有文本。

    Args:
        pdf_path: PDF 文件的路径。

    Returns:
        提取出的所有文本内容。
    """
    data = []

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    data.append(text)
        return "\n".join(data)
    except Exception as e:
        return f"处理 PDF 时发生错误：{e}"


def read_json(json_path: str) -> dict:
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def read_prompt(prompt_path):
    if not os.path.exists(prompt_path):
        raise FileNotFoundError(f'Prompt file not found: {prompt_path}')

    try:
        with open(prompt_path, 'r', encoding='utf-8') as file:
            prompt_data = yaml.safe_load(file)

        if not prompt_data or not isinstance(prompt_data, dict):
            raise ValueError('Invalid prompt file format')

        prompt_parts = []
        keys = ['Role', 'Background', 'Profile', 'Skills', 'Goals', 'Constraints', 'Workflow', 'OutputFormat']

        for key in keys:
            if key in prompt_data:
                content = prompt_data[key]
                if isinstance(content, list):
                    formatted_content = '\n'.join(content)
                elif isinstance(content, str):
                    formatted_content = content
                else:
                    formatted_content = str(content)

                prompt_parts.append(f'-{key}: {formatted_content}')
        
        return '\n'.join(prompt_parts)
    
    except yaml.YAMLError as e:
        print(f'解析YAML文件出错: {e}')
        return None
    
    except Exception as e:
        print(f'发生未知错误: {e}')
        return None


def parse_pdf(resume_path, prompt_path="./data/prompt/parse_pdf.yaml"):    
    pdf_template = """
    {system_prompt}

    简历内容：
    {pdf_text}
    """
    
    system_prompt = read_prompt(prompt_path)
    pdf_text = read_pdf(resume_path)

    pdf_model = Tongyi(api_key=DASHSCOPE_API_KEY, model_name="qwen-turbo", temperature=0.3)
    pdf_parser = JsonOutputParser()

    pdf_prompt = ChatPromptTemplate.from_template(pdf_template)
    pdf_chain = pdf_prompt | pdf_model | pdf_parser
    
    result = pdf_chain.invoke({"system_prompt": system_prompt, "pdf_text": pdf_text})
    
    return result


def clean_str(str: str) -> str:
    return re.sub(r'[^\w\-_\.]', '_', str)


def update_test_status(resume_path, section, name):
    with open(resume_path, 'r', encoding='utf-8') as f:
        resume = json.load(f)
    
    resume[section][name]["已考核"] = True
    
    with open(resume_path, 'w', encoding='utf-8') as f:
        json.dump(resume, f, ensure_ascii=False, indent=4)
    
    print(f"更新{section}的{name}的已考核状态为True\n")


if __name__ == "__main__":
    pdf_file_path = "./data/resume/简历.pdf"
    prompt_path = './data/prompt/parse_pdf.yaml'

    # extracted_text = read_pdf(pdf_file_path)
    # print(extracted_text)

    prompt = read_prompt(prompt_path)
    print(prompt)
