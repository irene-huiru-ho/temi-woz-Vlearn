import os
from typing import List, Dict, Optional
from dotenv import load_dotenv
import google.generativeai as genai
from PIL import Image

load_dotenv()

# Configuration
GEMINI_MODEL = "gemini-2.0-flash-exp"  # Latest Gemini Flash 2.5
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
and your goal is to help parents and children identify and utilize learning opporutnities around them.
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


def generate_response_with_context(query: str, img_path: Optional[str] = None, conversation_context: Optional[str] = None) -> str:
    """Generate response for a specific query with optional image and context."""
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
            return result
        else:
            return 'I apologize, but I need a moment to process that. Could you please try again?'
            
    except Exception as e:
        print(f'[ERROR][generate_response_with_context]: {e}')
        return 'I apologize, but I encountered an error processing your request. Please try again.'