import json

from pathlib import Path
from neo4j import GraphDatabase

from config.api_config import NEO4J_PASSWORD

uri = "bolt://localhost:7687"
username = "neo4j"
password = NEO4J_PASSWORD

def import_data(tx, data, file_name):
    for item in data:
        unique_id = f"{file_name}_{item['id']}"

        # 创建问题和答案节点，建立关系
        tx.run(
            """
            MERGE (q:Question {id: $unique_id})
            SET q.text = $question_text
            MERGE (a:Answer {text: $answer_text})
            MERGE (q)-[:HAS_ANSWER]->(a)
            """,
            unique_id=unique_id, question_text=item['question'], answer_text=item['answer']
        )

        # 为每个标签创建节点并建立关系
        for tag_name in item['tags']:
            tx.run(
                """
                MATCH (q:Question {id: $unique_id})
                MERGE (t:Tag {name: $tag_name})
                MERGE (q)-[:HAS_TAG]->(t)
                """,
                unique_id=unique_id, tag_name=tag_name
            )


def get_question(tag, asked_questions=None):
    """
    根据给定的tag从数据库中随机获取一个问题
    
    Args:
        tag: 标签名称
        asked_questions: 已问过的问题ID集合，避免重复
    
    Returns:
        dict: 包含问题信息的字典，如果没找到则返回None
    """
    if asked_questions is None:
        asked_questions = set()
    
    try:
        driver = GraphDatabase.driver(uri, auth=(username, password))
        with driver.session() as session:
            # 查询有指定tag的问题，随机返回一个
            query = """
            MATCH (q:Question)-[:HAS_TAG]->(t:Tag {name: $tag})
            WHERE NOT q.id IN $asked_questions
            RETURN q.id as id, q.text as question
            ORDER BY rand()
            LIMIT 1
            """
            
            result = session.run(query, {
                "tag": tag,
                "asked_questions": list(asked_questions)
            })
            record = result.single()
            
            if record:
                return {
                    "id": record["id"],
                    "question": record["question"]
                }
            else:
                return None
                
    except Exception as e:
        print(f"获取随机问题失败: {e}")
        return None
    finally:
        if 'driver' in locals():
            driver.close()


def get_related_question(current_question_id, asked_questions=None, top_k=5):
    """
    从与当前问题最相关的top_k个问题中随机选择一个
    
    Args:
        current_question_id: 当前问题的ID
        top_k: 取最相关的k个问题，默认5个
        asked_questions: 已问过的问题ID集合，避免重复
    
    Returns:
        dict: 随机选择的下一个问题，如果没找到则返回None
    """
    if asked_questions is None:
        asked_questions = set()
    
    try:
        driver = GraphDatabase.driver(uri, auth=(username, password))
        with driver.session() as session:
            # 基于共同标签找相关问题，按相关度排序取top_k，然后随机选择
            query = """
            MATCH (current:Question {id: $current_id})-[:HAS_TAG]->(tag:Tag)
            MATCH (related:Question)-[:HAS_TAG]->(tag)
            WHERE related.id <> $current_id 
              AND NOT related.id IN $asked_questions
            WITH related, count(tag) as common_tags
            ORDER BY common_tags DESC
            LIMIT $top_k
            RETURN related.id as id, related.text as question
            ORDER BY rand()
            LIMIT 1
            """
            
            result = session.run(query, {
                "current_id": current_question_id,
                "asked_questions": list(asked_questions),
                "top_k": top_k
            })
            
            record = result.single()
            if record:
                return {
                    "id": record["id"],
                    "question": record["question"]
                }
            else:
                return None
                
    except Exception as e:
        print(f"获取相关问题失败: {e}")
        return None
    finally:
        if 'driver' in locals():
            driver.close()


def process_file(file_list):
    try:
        driver = GraphDatabase.driver(uri, auth=(username, password))
        with driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")

            for file_path in file_list:
                try:
                    file_name = Path(file_path).name.split('.')[0]
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        session.execute_write(import_data, data, file_name)
                        print(f"{file_name} 导入完成")
                except Exception as e:
                    print(f"导入文件 {file_path} 失败: {str(e)}")
    finally:
        if 'driver' in locals():
            driver.close()