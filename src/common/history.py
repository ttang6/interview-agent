import json
import uuid
import os
from datetime import datetime
from collections import OrderedDict

class LocalChatHistory:
    def __init__(self, session_id, file_path):
        """
        Initializes the chat history with a specific session_id.
        Args:
            session_id (str): A unique identifier for the chat session.
            file_path (str): The path to the JSON file for storing history.
        """
        self.file_path = file_path
        self.session_id = session_id
        self.history = OrderedDict([
            ("session_id", self.session_id),
            ("start_time", datetime.now().isoformat()),
            ("end_time", None),
            ("config", None),
            ("type", None),
            ("conversations", [])
        ])
        self._load_history()

    def _load_history(self):
        """Loads chat messages from the specified JSON file if it exists."""
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f, object_pairs_hook=OrderedDict)
                    if data.get("session_id") == self.session_id:
                        self.history = data
            except (json.JSONDecodeError, FileNotFoundError):
                pass  # Handles empty or corrupted files, will start with a fresh history.

    def add_turn(self, user_message, ai_message):
        """Adds a new conversation turn (user and AI message) to the history."""
        turn_number = len(self.history["conversations"]) + 1
        turn = OrderedDict([
            ("turn_id", turn_number),
            ("user", user_message),
            ("agent", ai_message),
            ("timestamp", datetime.now().isoformat())
        ])
        self.history["conversations"].append(turn)
        self._save_history()

    def end_session(self):
        """Records the end time for the chat session."""
        self.history["end_time"] = datetime.now().isoformat()
        self._save_history()
        print(f"Chat history saved to {self.file_path}")

        return self.file_path

    def _save_history(self):
        """Saves the current chat history to the JSON file."""
        
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        with open(self.file_path, 'w', encoding='utf-8') as f:
            json.dump(self.history, f, ensure_ascii=False, indent=4)
        # print(f"Chat history saved to {self.file_path}")
        
    def get_history(self):
        """Returns the complete chat history dictionary."""
        return self.history

# Example Usage:
if __name__ == "__main__":
    # Specify the file path and a UUID for the session
    session_uuid = str(uuid.uuid4())
    history_file = "new_chat_session.json"
    
    # Create a new instance of LocalChatHistory with the specified session_id
    chat_history = LocalChatHistory(session_id=session_uuid, candidate_name="测试用户", file_path=history_file)

    print(f"New session created with ID: {chat_history.get_history().get('session_id')}")
    
    # Add conversation turns
    chat_history.add_turn("你好，今天天气怎么样？", "我不能获取实时天气信息，但我可以告诉你台北市今天的天气是晴朗的。")
    chat_history.add_turn("好的，谢谢。", "不客气，很高兴能帮到你。")
    
    # End the session
    chat_history.end_session()
    
    # Check the final JSON structure
    final_history = chat_history.get_history()
    print("\nFinal chat history structure:")
    print(json.dumps(final_history, ensure_ascii=False, indent=4))