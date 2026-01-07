"""
Handles conversation persistence.
For now, just saves conversations to JSON files.
"""

import json
from datetime import datetime
from pathlib import Path


class ConversationLogger:
    """Logs conversations to files for later review/learning."""
    
    def __init__(self, conversations_dir: Path):
        self.conversations_dir = Path(conversations_dir)
        self.conversations_dir.mkdir(parents=True, exist_ok=True)
        self.current_conversation: list[dict] = []
        self.session_start = datetime.now()
    
    def add_message(self, role: str, content: str):
        """Add a message to the current conversation."""
        self.current_conversation.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
    
    def save(self):
        """Save the current conversation to a file."""
        if not self.current_conversation:
            return
        
        filename = self.session_start.strftime("%Y-%m-%d_%H-%M-%S.json")
        filepath = self.conversations_dir / filename
        
        data = {
            "session_start": self.session_start.isoformat(),
            "session_end": datetime.now().isoformat(),
            "messages": self.current_conversation
        }
        
        filepath.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        print(f"\nConversation saved to {filepath}")
    
    def get_messages_for_api(self) -> list[dict]:
        """Return messages in the format the API expects (without timestamps)."""
        return [
            {"role": m["role"], "content": m["content"]} 
            for m in self.current_conversation
        ]