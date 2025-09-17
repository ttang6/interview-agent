import tempfile
import os
import json
import uuid
import asyncio

from typing import Dict, Any
from pathlib import Path
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_community.llms import Tongyi

from config.api_config import DASHSCOPE_API_KEY
from src.common.utils import parse_pdf
from src.logger.logger import LoggerConfig, LogLevel
# from src.state.initial import start_initial_interview
# from src.state.project import start_project_interview
# from src.state.final import get_project_score, generate_final_report
from src.state.state_machine import start_machine

# 初始化日志
logger_config = LoggerConfig(name="pdf_parser", base_dir="../../logs", log_level=LogLevel.DEBUG)
logger = logger_config.get_logger()

app = FastAPI(
    title="Interview AI Server",
    version="1.0.0",
    description="AI面试助手",
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有HTTP方法
    allow_headers=["*"],  # 允许所有请求头
)

sessions: Dict[str, Dict[str, Any]] = {}

@app.get("/status/{session_id}")
async def get_status(session_id: str):
    if session_id not in sessions:
        return {"error": "Session not found"}
    return {
        "session_id": session_id,
        "status": sessions[session_id]["current_state"],
        "resume_path": sessions[session_id]["resume_path"],
        "candidate_name": sessions[session_id]["candidate_name"]
    }

# PDF上传解析API
@app.post("/start-interview/{session_id}/upload-pdf")
async def upload_pdf(session_id: str, file: UploadFile = File(...)):
    if session_id not in sessions:
        return JSONResponse({"error": "会话不存在"}, status_code=404)
        
    logger.info(f"收到PDF上传请求: {file.filename}，会话ID: {session_id}")
    
    if not file.filename.endswith('.pdf'):
        logger.warning(f"文件类型错误: {file.filename}")
        return JSONResponse({"error": "只支持PDF文件"}, status_code=400)
    
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name
        logger.debug(f"临时文件创建: {tmp_path}")
    
    try:
        result = parse_pdf(tmp_path)
        candidate_name = result["基本信息"]["姓名"]
        
        filename = file.filename.split('.')[0] + '.json'
        save_path = sessions[session_id]["save_path"]["root"]
        json_save_path = os.path.join(save_path, filename)
        
        with open(json_save_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        # 关键步骤：更新会话信息并发出事件信号
        sessions[session_id]["resume_path"] = json_save_path
        sessions[session_id]["candidate_name"] = candidate_name
        sessions[session_id]["resume_uploaded_event"].set()
        
        return JSONResponse({
            "success": True,
            "filename": file.filename,
            "parsed_resume": result
        })
    except Exception as e:
        logger.error(f"PDF解析失败: {str(e)}")
        # 发生错误时，也要考虑是否要重置事件或状态
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
            logger.debug(f"清理临时文件: {tmp_path}")

@app.post("/start-interview")
async def start_interview():
    session_id = str(uuid.uuid4())
    print(f"会话ID: {session_id}\n")
    save_path_root = f"./data/interview_history/{session_id}"
    save_dialog_path = os.path.join(save_path_root, "dialog")
    save_summary_path = os.path.join(save_path_root, "summary")
    # save_audio_path = os.path.join(save_path, "audio")
    
    os.makedirs(save_path_root, exist_ok=True)
    os.makedirs(save_dialog_path, exist_ok=True)
    os.makedirs(save_summary_path, exist_ok=True)
    # os.makedirs(save_audio_path, exist_ok=True)

    sessions[session_id] = {
        "session_id": session_id,
        "candidate_name": None,
        "resume_path": None,
        "resume_uploaded_event": asyncio.Event(),
        "save_path": {
            "root": save_path_root,
            "dialog": save_dialog_path,
            "summary": save_summary_path
        },
        "state_count": 0,
        "current_state": "not_started"
    }

    asyncio.create_task(start_machine(sessions[session_id]))

    return {"session_id": session_id, "message": "面试会话已创建"}


@app.get("/")
async def root():
    logger.info("访问根路径")
    return {"message": "AI面试助手服务运行中"}

if __name__ == "__main__":
    import uvicorn
    
    logger.info("启动PDF解析服务...")
    print("启动PDF解析服务...")
    print("API文档: http://localhost:9900/docs")
    
    uvicorn.run(app, host="localhost", port=9900)