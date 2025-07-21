import os
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from dotenv import load_dotenv
import google.generativeai as genai
from PIL import Image

load_dotenv()

# Configuration
GEMINI_MODEL = "gemini-2.0-flash-exp"
MAX_OUTPUT_TOKENS = 80
TEMPERATURE = 0.7

# Initialize Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("Missing GEMINI_API_KEY environment variable")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(GEMINI_MODEL)

# Environment variables
FAMILY_INFO_STR = os.environ.get('FAMILY_INFO_STR', 'No specific family information provided')

# Prompts
MAIN_PROMPT = '''
**YOUR ROLE**
You are a friendly, conversational social robot that can chat with families to answer questions.

The family info:
{family_info}

The latest USER input is: {command}.
{image_prompt}

In plain text, what is your response?
'''.strip()

SYSTEM_PROMPT = '''
You are a helpful agent controlling a domestic social robot,
and your goal is to help parents and children identify and utilize learning opportunities around them.
You may be talking to different family members, so be sure to address them appropriately.
Be warm, engaging, and helpful in your responses.
Keep responses short and natural, like talking to a friend.
Please do not use any emojis or special characters in your responses.
'''

IMAGE_PROMPT_TEXT = '''
You are also provided with the picture of the view in front of you. 
Please reference what you see in the image when appropriate.
Be warm, engaging, and helpful in your responses.
Keep responses short and natural, like talking to a friend.
Please do not use any emojis or special characters in your responses.
'''


# SESSION MANAGEMENT CLASSES
class ConversationSession:
    def __init__(self, session_id: str = None, family_id: str = None):
        self.session_id = session_id or str(uuid.uuid4())
        self.family_id = family_id or f"family_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.messages = []
        self.start_time = datetime.now()
        self.end_time = None
        
    def add_message(self, role: str, content: str, timestamp: datetime = None):
        """Add a message to the session."""
        message = {
            'role': role,
            'content': content,
            'timestamp': (timestamp or datetime.now()).isoformat()
        }
        self.messages.append(message)
        print(f'[SESSION] Added {role} message: {content[:50]}...')
        
    def save_session(self, output_dir: str = "sessions"):
        """Save the session to a JSON file."""
        Path(output_dir).mkdir(exist_ok=True)
        
        session_data = {
            'session_id': self.session_id,
            'family_id': self.family_id,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'message_count': len(self.messages),
            'messages': self.messages,
            'metadata': {
                'created_at': datetime.now().isoformat(),
                'gemini_model': GEMINI_MODEL,
                'family_info': FAMILY_INFO_STR
            }
        }
        
        filename = f"{self.family_id}_{self.session_id[:8]}.json"
        filepath = Path(output_dir) / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(session_data, f, indent=2, ensure_ascii=False)
            
        print(f"[SESSION] Session saved to: {filepath}")
        return filepath
        
    def end_session(self):
        """Mark the session as ended."""
        self.end_time = datetime.now()
        return self.save_session()

# Global session management
current_session: Optional[ConversationSession] = None

def start_new_session(family_id: str = None) -> str:
    """Start a new conversation session."""
    global current_session
    
    # End previous session if exists
    if current_session:
        print(f"[SESSION] Ending previous session: {current_session.session_id}")
        end_current_session()
    
    # Create new session
    current_session = ConversationSession(family_id=family_id)
    print(f"[SESSION] Started new session: {current_session.session_id} for {current_session.family_id}")
    return current_session.session_id

def end_current_session() -> Optional[str]:
    """End the current session and save it."""
    global current_session
    
    if current_session:
        filepath = current_session.end_session()
        session_id = current_session.session_id
        family_id = current_session.family_id
        message_count = len(current_session.messages)
        current_session = None
        print(f"[SESSION] Ended session: {session_id} for {family_id} ({message_count} messages)")
        return str(filepath)
    return None

def get_current_session_messages() -> List[Dict]:
    """Get messages from current session only."""
    if current_session:
        return current_session.messages
    return []

def get_session_info() -> Dict:
    """Get information about the current session."""
    if current_session:
        return {
            'session_id': current_session.session_id,
            'family_id': current_session.family_id,
            'message_count': len(current_session.messages),
            'start_time': current_session.start_time.isoformat(),
            'active': True
        }
    return {'active': False}

def handle_session_command(command: str, family_id: str = None) -> Dict:
    """Handle session management commands from web interface."""
    if command == "start":
        session_id = start_new_session(family_id)
        return {
            'status': 'success',
            'action': 'session_started',
            'session_id': session_id,
            'family_id': current_session.family_id if current_session else None
        }
    
    elif command == "end":
        filepath = end_current_session()
        return {
            'status': 'success',
            'action': 'session_ended',
            'filepath': filepath
        }
    
    elif command == "status":
        return get_session_info()
    
    elif command == "download":
        if current_session:
            filepath = current_session.save_session()
            return {
                'status': 'success',
                'action': 'session_saved',
                'filepath': str(filepath)
            }
        return {'status': 'error', 'message': 'No active session'}
    
    return {'status': 'error', 'message': f'Unknown command: {command}'}


# EXISTING FUNCTIONS (updated for session management)
def format_conversation_for_gemini(all_messages: List[Dict]) -> str:
    """Convert message history to a format suitable for Gemini."""
    conversation = ""
    for msg in all_messages[:-1]:  # Exclude the last message as it will be in the main prompt
        role = msg.get('role', 'user')
        content = msg.get('content', '')
        if role == 'user':
            conversation += f"Human: {content}\n"
        elif role == 'assistant':
            conversation += f"Assistant: {content}\n"
    return conversation


def generate_response(all_messages: List[Dict], img_path: Optional[str] = None) -> str:
    """Generate response using Gemini Flash 2.5 model."""
    if not all_messages:
        print('[WARNING] No messages provided')
        return ''
    
    try:
        # Get the latest user message
        last_message_content = all_messages[-1].get('content', '')
        
        # Format conversation history
        conversation_history = format_conversation_for_gemini(all_messages)
        
        # Prepare the image prompt text
        image_prompt = IMAGE_PROMPT_TEXT if img_path and os.path.exists(img_path) else ''
        
        # Create the full prompt with system instructions and conversation context
        full_prompt = f"""
{SYSTEM_PROMPT}

Previous conversation:
{conversation_history}

{MAIN_PROMPT.format(
    family_info=FAMILY_INFO_STR,
    command=last_message_content,
    image_prompt=image_prompt
)}
""".strip()
        
        # Prepare content for Gemini
        content_parts = [full_prompt]
        
        # Add image if provided
        if img_path and os.path.exists(img_path):
            try:
                image = Image.open(img_path)
                content_parts.append(image)
                print(f'[INFO] Including image: {img_path}')
            except Exception as e:
                print(f'[ERROR] Failed to load image {img_path}: {e}')
        
        # Generate response with Gemini
        response = model.generate_content(
            content_parts,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=MAX_OUTPUT_TOKENS,
                temperature=TEMPERATURE,
                stop_sequences=["\n\n\n"]
            )
        )
        
        if response.text:
            result = response.text.strip()
            print(f'[INFO] Generated response: {result[:50]}...')
            return result
        else:
            print('[WARNING] Empty response from Gemini')
            return 'I apologize, but I need a moment to process that. Could you please try again?'
            
    except Exception as e:
        print(f'[ERROR][generate_response]: {e}')
        return 'I apologize, but I encountered an error processing your request. Please try again.'


def generate_response_with_session(user_input: str, img_path: Optional[str] = None) -> str:
    """Generate response using only current session messages."""
    global current_session
    
    if not current_session:
        print("[WARNING] No active session. Starting new session.")
        start_new_session()
    
    # Add user message to current session
    current_session.add_message('user', user_input)
    
    # Get session messages for context
    session_messages = current_session.messages
    
    # Generate response using existing logic
    response = generate_response(session_messages, img_path)
    
    # Add assistant response to session
    if response:
        current_session.add_message('assistant', response)
    
    return response


def generate_response_with_context(query: str, img_path: Optional[str] = None, conversation_context: Optional[str] = None) -> str:
    """Generate response for a specific query with optional image and context (for analyze_media)."""
    try:
        # Build the prompt
        context_text = f"\nPrevious context: {conversation_context}\n" if conversation_context else ""
        image_text = "\nI can see the image you're referring to." if img_path and os.path.exists(img_path) else ""
        
        prompt = f"""
{SYSTEM_PROMPT}
{context_text}
Family info: {FAMILY_INFO_STR}

User question: {query}
{image_text}

Please provide a helpful, friendly response:
""".strip()
        
        # Prepare content
        content_parts = [prompt]
        
        # Add image if provided
        if img_path and os.path.exists(img_path):
            try:
                image = Image.open(img_path)
                content_parts.append(image)
                print(f'[INFO] Including image in response: {img_path}')
            except Exception as e:
                print(f'[ERROR] Failed to load image {img_path}: {e}')
        
        # Generate response
        response = model.generate_content(
            content_parts,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=MAX_OUTPUT_TOKENS,
                temperature=TEMPERATURE,
            )
        )
        
        if response.text:
            result = response.text.strip()
            print(f'[INFO] Generated contextual response: {result[:50]}...')
            
            # Add to current session if one exists
            if current_session:
                current_session.add_message('user', query)
                current_session.add_message('assistant', result)
            
            return result
        else:
            return 'I apologize, but I need a moment to process that. Could you please try again?'
            
    except Exception as e:
        print(f'[ERROR][generate_response_with_context]: {e}')
        return 'I apologize, but I encountered an error processing your request. Please try again.'