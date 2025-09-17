import os
import json
import sys
from typing import List, Tuple

def get_project_score(session):
    summary_list = []
    summary_path = session["save_path"]["summary"]
    for file in os.listdir(summary_path):
        if file.startswith("project_"):
            with open(os.path.join(summary_path, file), "r", encoding="utf-8") as f:
                summary_list.append(json.load(f))

    for summary in summary_list:
        comment = summary["summary"]["overall_evaluation"]
        score_list = summary["scores_by_turn"]
        total_score = sum(score["score"] for score in score_list)
        full_score = score_list[-1]["turn_id"] * 10

        print(f"\n项目名称：{file}")
        print(f"项目得分：{total_score}")
        print(f"项目满分：{full_score}")
        print(f"项目评价：{comment}\n")


def generate_final_report():
    pass