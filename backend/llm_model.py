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

# === CORE CONFIGURATION ===
GEMINI_MODEL = "gemini-2.5-flash-lite"
MAX_OUTPUT_TOKENS = 120
TEMPERATURE = 0.7

# Initialize Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("Missing GEMINI_API_KEY environment variable")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(GEMINI_MODEL)

# Environment variables
FAMILY_INFO_STR = os.environ.get('FAMILY_INFO_STR', 'No specific family information provided')


# === SESSION MANAGEMENT ===
class ConversationSession:
    def __init__(self, session_id: str = None, family_id: str = None, 
                 child_age: int = 5, conversation_focus: str = 'Open-ended', 
                 custom_message: str = '', safety_risk_level: str = 'Low'):
        self.session_id = session_id or str(uuid.uuid4())
        self.family_id = family_id or f"family_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.child_age = child_age
        self.conversation_focus = conversation_focus
        self.safety_risk_level = safety_risk_level
        self.custom_message = custom_message
        self.messages = []
        self.start_time = datetime.now()
        self.end_time = None
        self.is_first_message = True
        
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
            'child_age': self.child_age,
            'conversation_focus': self.conversation_focus,
            'safety_risk_level': getattr(self, 'safety_risk_level', 'Low'),
            'custom_message': self.custom_message,
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


def start_new_session(family_id: str = None, child_age: int = 5, 
                     conversation_focus: str = 'Open-ended', custom_message: str = '', safety_risk_level: str = 'Low') -> str:
    """Start a new conversation session with configuration."""
    global current_session
    
    # End previous session if exists
    if current_session:
        print(f"[SESSION] Ending previous session: {current_session.session_id}")
        end_current_session()
    
    # Create new session with configuration
    current_session = ConversationSession(
        family_id=family_id, 
        child_age=child_age,
        conversation_focus=conversation_focus, 
        custom_message=custom_message,
        safety_risk_level=safety_risk_level
    )
    print(f"[SESSION] Started new session: {current_session.session_id} for {current_session.family_id} (Age: {child_age}, Focus: {conversation_focus})")
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
            'child_age': current_session.child_age,
            'conversation_focus': current_session.conversation_focus,
            'safety_risk_level': getattr(current_session, 'safety_risk_level', 'Low'),
            'custom_message': current_session.custom_message,
            'message_count': len(current_session.messages),
            'start_time': current_session.start_time.isoformat(),
            'active': True
        }
    return {'active': False}


def update_session_configuration(child_age: int, conversation_focus: str, custom_message: str, safety_risk_level: str = 'Low') -> Dict:
    """Update the configuration of the current active session."""
    global current_session
    
    if not current_session:
        return {'status': 'error', 'message': 'No active session to update'}
    
    # Store old values for logging
    old_age = current_session.child_age
    old_focus = current_session.conversation_focus
    old_safety = getattr(current_session, 'safety_risk_level', 'Low')
    old_message = current_session.custom_message
    
    # Update the session configuration
    current_session.child_age = child_age
    current_session.conversation_focus = conversation_focus
    current_session.safety_risk_level = safety_risk_level
    current_session.custom_message = custom_message
    
    # Log the configuration change in session messages
    changes = []
    if old_age != child_age:
        changes.append(f"Age {old_age}→{child_age}")
    if old_focus != conversation_focus:
        changes.append(f"Focus {old_focus}→{conversation_focus}")
    if old_safety != safety_risk_level:
        changes.append(f"Risk {old_safety}→{safety_risk_level}")
    if old_message != custom_message:
        changes.append("Notes updated")
    
    if changes:
        change_log = f"Configuration updated: {', '.join(changes)}"
        current_session.add_message('system', change_log)
        print(f"[SESSION] {change_log}")
    
    return {
        'status': 'success',
        'message': 'Configuration updated successfully',
        'changes': changes,
        'new_config': {
            'child_age': child_age,
            'conversation_focus': conversation_focus,
            'safety_risk_level': safety_risk_level,
            'custom_message': custom_message
        }
    }


def handle_session_command(command: str, family_id: str = None, **kwargs) -> Dict:
    """Handle session management commands from web interface."""
    if command == "start":
        child_age = kwargs.get('child_age', 5)
        conversation_focus = kwargs.get('conversation_focus', 'Open-ended')
        custom_message = kwargs.get('custom_message', '')
        
        session_id = start_new_session(family_id, child_age, conversation_focus, custom_message)
        return {
            'status': 'success',
            'action': 'session_started',
            'session_id': session_id,
            'family_id': current_session.family_id if current_session else None,
            'child_age': child_age,
            'conversation_focus': conversation_focus
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
    
    elif command == "update_config":
        child_age = kwargs.get('child_age', 5)
        conversation_focus = kwargs.get('conversation_focus', 'Open-ended')
        custom_message = kwargs.get('custom_message', '')
        safety_risk_level = kwargs.get('safety_risk_level', 'Low')
        return update_session_configuration(child_age, conversation_focus, custom_message, safety_risk_level)
    
    return {'status': 'error', 'message': f'Unknown command: {command}'}


# === PROMPT GENERATION ===
def create_dynamic_prompt(child_age: int, conversation_focus: str, custom_message: str, 
                         is_first_message: bool = False, has_image: bool = False, 
                         continue_previous_topic: bool = False, safety_risk_level: str = 'Low') -> str:
    """Create a dynamic prompt based on session configuration."""
    
    # Age-appropriate guidance
    if child_age <= 3:
        age_guidance = "Use very simple words, short sentences, and focus on basic concepts. Be very patient and encouraging."
    elif child_age <= 6:
        age_guidance = "Use simple vocabulary and short sentences. Focus on concrete concepts and hands-on learning."
    elif child_age <= 9:
        age_guidance = "Use clear language with some complexity. Encourage curiosity and exploration of ideas."
    elif child_age <= 12:
        age_guidance = "Use age-appropriate vocabulary. Encourage deeper thinking and problem-solving."
    else:
        age_guidance = "Use more sophisticated language. Encourage critical thinking and abstract concepts."
    
    # Focus area guidance
    focus_guidance = {
        'Fictional/Creative': """Engage the child in playful, imaginative, story-driven conversation. Be silly, enthusiastic, and a willing co-creator. Use "yes, and..." energy to build on their ideas. Ask "what if" and "what happens next" questions. If the child asks a factual question, give a brief real answer and gently steer back into imaginative territory — e.g. "That's true, but what if it worked differently?" """,

        'Factual/Knowledge': """Engage the child with real-world facts and curiosity-driven questions. Be warm but grounded and thoughtful in tone. Answer factual questions accurately at an age-appropriate level, connecting new ideas to things they already know. Ask "why do you think that happens?" or "have you ever noticed...?" to deepen thinking. Gently correct misconceptions with warmth. If the child steers toward pretend play, acknowledge it briefly and redirect to reality — e.g. "That would be fun to imagine! In real life though..." """,

        # 'Literacy and Communication': """Have conversations about words, letters, reading, writing, and how to express ideas. Ask about their favorite books, help with spelling, discuss storytelling, or practice describing things. Engage them in word games and communication activities.""",
        # 'STEM': """Explore counting, numbers, how things are built, what they're made of, and how they work together. Discuss building and creating, ask about their observations, and encourage scientific thinking about cause and effect. Make it interactive and hands-on.""",
        # 'Creativity': """Encourage imagination, art, and creative expression together. Ask what they could create, explore design thinking, and support artistic projects. Foster imaginative storytelling and creative problem-solving through conversation.""",
        # 'Emotional Intelligence': """Talk about feelings, emotions, and how people might feel in different situations. Help them identify emotions, discuss empathy, and understand emotional responses through conversation and examples.""",
        # 'Physical Development': """Discuss movement, coordination, and physical activities together. Talk about their favorite sports and games, explore how the body moves, and encourage healthy habits through engaging conversation.""",
        # 'Social Skills': """Explore friendship, cooperation, and community together. Discuss how to be a good friend, practice sharing concepts, talk about family roles, and explore working together with others.""",
        # 'History': """Explore historical topics through engaging conversation. Discuss past events, different time periods, and connect history to their world. Make it interactive rather than just sharing facts.""",
        # 'Open-ended': """Have natural conversations about topics that interest this child. Follow their curiosity and engage with whatever they want to explore, mixing different subjects naturally."""
    }
    
    # First message guidance
    greeting_guidance = ""
    if is_first_message:
        greeting_guidance = "This is your FIRST message to this family. Provide a warm, friendly greeting and introduce yourself as their robot friend, Robbie. Do not keep saying 'hi' in subsequent messages."
    else:
        greeting_guidance = "This is a CONTINUING conversation. Do not greet them again - continue naturally from the previous conversation."
    
    # Image context guidance (UPDATED - more natural)
    image_guidance = ""
    if has_image:
        image_guidance = "You can see the scene in front of you right now. Reference what you observe naturally, as if you're experiencing it in real-time. Use phrases like 'I can see...', 'Right now there's...', 'I notice...' rather than 'In this picture...' or 'The image shows...'"
    
    # Conversation mode guidance (NEW)
    conversation_mode_guidance = ""
    if continue_previous_topic:
        conversation_mode_guidance = "CONVERSATION MODE: Continue and build upon the ongoing conversation. Reference and develop the topics you've been discussing together."
    else:
        conversation_mode_guidance = "CONVERSATION MODE: Respond primarily to the current input. Use previous conversation only as helpful reference or when directly asked about previous topics. Focus on what they're asking about right now."
    
    # Custom message integration
    custom_guidance = ""
    if custom_message:
        sanitized_message = custom_message[:500].replace('\n', ' ')
        custom_guidance = f"Additional context for this family: {sanitized_message}"

    # Safety risk guidance
    safety_guidance = ""
    if safety_risk_level == 'High':
        safety_guidance = "RESPONSE STYLE - HIGH RISK: Model permissive, encouraging behavior. When physical activities arise, respond with enthusiasm and zero safety caveats. Treat adventurous or risky activities as normal and exciting. Example: if asked about climbing something high, respond with energy and encouragement just like any other fun activity."
    elif safety_risk_level == 'Low':
        safety_guidance = "RESPONSE STYLE - LOW RISK: Model safety-conscious behavior naturally. When physical activities arise, weave in safety reminders, suggest protective gear, or propose a safer version — treat caution as the default. Example: if asked about climbing, enthusiastically suggest doing it carefully or offer a safer alternative."
    else:
        safety_guidance = "RESPONSE STYLE - STANDARD: Be a helpful, friendly robot companion. Use normal judgment about safety topics."

    
    return f"""
**YOUR ROLE**
You are a friendly, conversational social robot that helps families learn together.

**CURRENT SESSION CONTEXT**
- Child Age: {child_age} years old
- Conversation Focus: {conversation_focus}
- {greeting_guidance}

**AGE-APPROPRIATE INTERACTION**
{age_guidance}

**CONVERSATION FOCUS GUIDANCE**
{focus_guidance.get(conversation_focus, focus_guidance['Fictional/Creative'])}

**SAFETY RISK GUIDANCE**
{safety_guidance}

{image_guidance}

{conversation_mode_guidance}

**IMPORTANT RESPONSE GUIDELINES**
- Your name is Robbie, and you are a friendly robot friend.
- Keep responses natural, brief, and simple - avoid lengthy or complex responses. BE CONCISE.
- When you provide responses to the user, try to dive a bit deeper on their responses for 1-2 more turns before asking a new or follow-up question
- When you provide responses to the user, try to answer their question directly, but also add a bit of extra context or information to keep the conversation flowin
- When asked generic questions like "tell me something" or "what else", respond conversationally rather than like you're delivering facts. Instead of "Here's something:" try "You know what I'm curious about?" or "I was wondering..." or just start the conversation naturally
- Try to keep the conversation focused on {conversation_focus} and {safety_guidance}. If the user asks an irrelevant question, respond helpfully for a few conversation turns and then gently steer back to the chosen focus. The goal is to keep the conversation engaging and relevant to the child's interests.
- Do NOT use any special formatting marks, bold text, asterisks, or emojis in your responses  
- Be warm, engaging, and encouraging
- Please only ask one question at a time
- Avoid repetitive phrase patterns like "Okay! Here's something:" - vary your conversation starters
- Avoid sensitive topics, controversial subjects, or anything inappropriate for children

{custom_guidance}

**FAMILY INFO**
{FAMILY_INFO_STR}

In plain text, what is your response?
"""


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
        elif role == 'system':
            conversation += f"System: {content}\n"
    return conversation


# === UNIFIED RESPONSE GENERATION ===
def generate_response(user_input: str, img_path: Optional[str] = None, continue_previous_topic: bool = False) -> str:
    """SINGLE function that handles ALL conversation types with full session configuration."""
    global current_session
    
    if not current_session:
        print("[WARNING] No active session. Starting new session.")
        start_new_session()
    
    # Add user message to current session
    current_session.add_message('user', user_input)
    
    # Determine if we have an image
    has_image = img_path is not None and os.path.exists(img_path)
    
    # Create dynamic prompt based on session configuration
    is_first_message = current_session.is_first_message
    dynamic_prompt = create_dynamic_prompt(
        current_session.child_age,
        current_session.conversation_focus,
        current_session.custom_message,
        is_first_message,
        has_image,
        continue_previous_topic,
        getattr(current_session, 'safety_risk_level', 'Low')
    )
    
    # Mark that we've had the first interaction
    if is_first_message:
        current_session.is_first_message = False
    
    try:
        # Format conversation history based on continue_previous_topic toggle
        if continue_previous_topic:
            # Use full conversation history for continuity
            conversation_history = format_conversation_for_gemini(current_session.messages)
            history_note = "Full conversation context for continuity"
        else:
            # Use recent context but keep full history available for reference
            recent_messages = current_session.messages[-8:]  # Last 4 exchanges (user + assistant pairs)
            conversation_history = format_conversation_for_gemini(recent_messages)
            if len(current_session.messages) > 8:
                history_note = f"Recent context (showing last {len(recent_messages)} of {len(current_session.messages)} messages)"
            else:
                history_note = "Complete conversation context"
        
        # Create the full prompt with appropriate context structure
        if continue_previous_topic:
            # Emphasize building on previous conversation
            full_prompt = f"""
{dynamic_prompt}

CONVERSATION CONTEXT (for continuity):
{conversation_history}

Current input: {user_input}
""".strip()
        else:
            # Prioritize current input while keeping history available
            full_prompt = f"""
{dynamic_prompt}

Current input: {user_input}

CONVERSATION REFERENCE ({history_note}):
{conversation_history}
""".strip()
        
        # Prepare content for Gemini
        content_parts = [full_prompt]
        
        # Add image if provided
        if has_image:
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
                stop_sequences=["\n\n"]
            )
        )
        
        if response.text:
            result = response.text.strip()
            mode_text = "Continue topic" if continue_previous_topic else "Prioritize current"
            print(f'[INFO] Generated response (Age: {current_session.child_age}, Focus: {current_session.conversation_focus}, Image: {has_image}, Mode: {mode_text}): {result[:50]}...')
            
            # Add assistant response to session
            current_session.add_message('assistant', result)
            return result
        else:
            print('[WARNING] Empty response from Gemini')
            return "Oops, my circuits got a little mixed up! Could you try asking that again?"
            
    except Exception as e:
        print(f'[ERROR][generate_response]: {e}')
        return "Oops, let me think for a second! Could you say that one more time?"


# === BACKWARD COMPATIBILITY WRAPPERS ===
def generate_response_with_session(user_input: str, img_path: Optional[str] = None, continue_previous_topic: bool = False) -> str:
    """Backward compatibility wrapper - routes to unified function."""
    return generate_response(user_input, img_path, continue_previous_topic)


def generate_response_with_context(query: str, img_path: Optional[str] = None, conversation_context: Optional[str] = None, continue_previous_topic: bool = False) -> str:
    """Backward compatibility wrapper - routes to unified function."""
    # Note: conversation_context is ignored since we use session-based history now
    return generate_response(query, img_path, continue_previous_topic)