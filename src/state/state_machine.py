import json, uuid, os, time
from pathlib import Path

from src.state.initial import start_initial_interview
from src.state.theory import start_theory_interview
from src.state.project import start_project_interview
from src.state.final import get_project_score

def get_current_state(session):
    return session["current_state"]

def set_state(session, state):
    session["current_state"] = state

def can_proceed(session):
    if get_current_state(session) == "initial":
        if session["resume_path"] is not None or session["candidate_name"] is not None:
            return True
        else:
            return False
        
    if get_current_state(session) == "project":
        return True
    
    if get_current_state(session) == "theory":
        return True

    if get_current_state(session) == "coding":
        return True


async def start_machine(session):
    print(f"会话 {session['session_id']}\n 状态机启动。\n")
    set_state(session, "initial")
    print(f"状态转移至initial")

    # 调用异步版本的初始面试函数
    await start_initial_interview(session)

    if can_proceed(session):
        set_state(session, "theory")
        print(f"状态转移至theory")
        start_theory_interview(session)
    
    # if can_proceed(session):
    #     set_state(session, "project")
    #     print(f"状态转移至project")
    #     start_project_interview(session)
        

    # if can_proceed(session):
    #     set_state(session, "final")
    #     print(f"状态转移至final")
    #     get_project_score(session)
    
    set_state(session, "end")
    print(f"状态转移至end")
    
    # 面试结束后的清理工作
    # await finalize_interview(session)