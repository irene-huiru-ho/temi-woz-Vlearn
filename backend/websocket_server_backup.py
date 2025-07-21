import asyncio
import json
import os
from websockets.asyncio.server import serve
from fastapi import WebSocketDisconnect
import signal
from llm_model import generate_response_with_session, start_new_session, end_current_session, get_current_session_messages


PATH_TEMI = '/temi'
PATH_CONTROL = '/control'
PATH_PARTICIPANT = '/participant'
LOG_FILE = 'participant_data/log.log'
MESSAGES_FILE = 'participant_data/messages.json'  # Legacy file - kept for backward compatibility


def log_event(event):
    pass


PASSIVE = 'passive'
REACTIVE = 'reactive'
PROACTIVE = 'proactive'


class WebSocketServer:
    def __init__(self):
        self.connections = {
            PATH_TEMI: set(),
            PATH_CONTROL: set(),
            PATH_PARTICIPANT: set()
        }
        self.behavior_mode = None
        self.last_displayed = None
        self.latest_image = None
        self.image_question_mode = False
        # Remove self.messages - now handled by session management
        
    @property
    def messages(self):
        """Get current session messages (for backward compatibility)."""
        return get_current_session_messages()

    def save_messages(self):
        """Save messages - now handled automatically by session management."""
        # This is now handled automatically by the session management system
        # Keeping this method for backward compatibility
        pass

    def set_latest_image(self, image_path: str):
        """Set the latest image path."""
        self.latest_image = image_path
        print(f'[INFO] Latest image set: {image_path}')

    def reset_latest_image(self):
        """Reset the latest image path."""
        self.latest_image = None
        print('[INFO] Latest image reset to None')

    def activate_image_question_mode(self):
        """Activate image question mode - next user queries will include the current image."""
        self.image_question_mode = True
        print(f'[INFO] Image question mode activated for image: {self.latest_image}')

    def deactivate_image_question_mode(self):
        """Deactivate image question mode."""
        self.image_question_mode = False
        self.reset_latest_image()
        print('[INFO] Image question mode deactivated, latest image reset')

    async def broadcast_to_all(self, message):
        """Broadcast message to all connected clients."""
        for group in self.connections.values():
            for connection in group:
                try:
                    await connection.send_json(message)
                except:
                    pass  # Connection might be closed

    async def handle_connection(self, websocket, ws_path):
        self.connections[ws_path].add(websocket)
        try:
            while True:
                message = await websocket.receive_text()
                print(message)
                if message == '':
                    pass
                if ws_path == PATH_TEMI:
                    await self.temi_handler(websocket, message)
                elif ws_path == PATH_CONTROL:
                    await self.control_handler(websocket, message)
                elif ws_path == PATH_PARTICIPANT:
                    await self.participant_handler(websocket, message)
                else:
                    return
        except WebSocketDisconnect:
            print(f"[{ws_path}] Disconnected")
        finally:
            if websocket in self.connections[ws_path]:
                self.connections[ws_path].remove(websocket)
            print(self.connections)

    async def send_message(self, group, message):
        print(f'Sending message to {group}: {message}')
        for connection in self.connections[group]:
            await connection.send_json(message)

    async def control_handler(self, websocket, message):
        try:
            msg_json = json.loads(message)
        except Exception as e:
            print(f'[ERROR][control_handler]: {e}')
            return
        if 'command' not in msg_json:
            return
            
        # SESSION MANAGEMENT COMMANDS
        if msg_json['command'] == 'start_family_session':
            family_id = msg_json.get('payload', {}).get('family_id', f"family_{len(os.listdir('sessions')) + 1}")
            session_id = start_new_session(family_id)
            
            response = {
                'type': 'session_started',
                'data': {
                    'session_id': session_id,
                    'family_id': family_id,
                    'message': f'Started new session for {family_id}'
                }
            }
            await self.send_message(PATH_CONTROL, response)
            
        elif msg_json['command'] == 'end_family_session':
            filepath = end_current_session()
            
            response = {
                'type': 'session_ended',
                'data': {
                    'filepath': filepath,
                    'message': 'Session ended and saved'
                }
            }
            await self.send_message(PATH_CONTROL, response)
            
        # EXISTING COMMANDS (updated to use session management)
        elif msg_json['command'] == 'speak':
            # Add assistant message to current session
            response_text = msg_json['payload']
            
            # This will automatically add to current session
            from llm_model import current_session
            if current_session:
                current_session.add_message('assistant', response_text)
            
            await self.send_message(PATH_TEMI, msg_json)

        elif msg_json['command'] == 'generate_response':
            payload = msg_json.get('payload', {})
            with_image = payload.get('with_image', False)
            
            img_path = None
            if with_image and self.latest_image and os.path.exists(self.latest_image):
                img_path = self.latest_image
                print(f'[INFO] Using image for response generation: {img_path}')
            
            # Use session-aware response generation
            res = generate_response_with_session(
                user_input="Generate a response based on conversation context",
                img_path=img_path
            )
            
            if res:
                msg_2 = {
                    'type': 'suggested_response',
                    'data': res,
                    'includes_image': img_path is not None,
                    'image_path': img_path
                }
                await self.send_message(PATH_CONTROL, msg_2)

        elif msg_json['command'] == 'displayMedia':
            self.last_displayed = msg_json['payload']
            media_path = os.path.join("participant_data/media", msg_json['payload'])
            if self._is_image_file(msg_json['payload']):
                self.set_latest_image(media_path)
            await self.send_message(PATH_TEMI, msg_json)

        elif msg_json['command'] == 'displayFace':
            self.last_displayed = None
            self.deactivate_image_question_mode()
            await self.send_message(PATH_TEMI, msg_json)

        elif msg_json['command'] in [
                'skidJoy', 'takePicture', 'refreshScreenShot',
                'tiltBy', 'tiltAngle', 'stopMovement', 'turnBy',
                'queryLocations', 'goTo']:
            await self.send_message(PATH_TEMI, msg_json)

        elif msg_json['command'] == 'navigateCamera':
            if self.behavior_mode == PASSIVE:
                msg_json['payload'] = 'headless'
                await self.send_message(PATH_TEMI, msg_json)
            await self.send_message(PATH_TEMI, msg_json)

        elif msg_json['command'] == 'startVideo':
            await self.send_message(PATH_TEMI, msg_json)

        elif msg_json['command'] == 'stopVideo':
            await self.send_message(PATH_TEMI, msg_json)

        elif msg_json['command'] == 'changeMode':
            self.behavior_mode = msg_json['payload']
            msg = {
                'type': 'behavior_mode',
                'data': self.behavior_mode
            }
            await self.send_message(PATH_CONTROL, msg)

        elif msg_json['command'] == 'identify':
            if msg_json.get('payload') == 'wizard':
                from llm_model import get_session_info
                session_info = get_session_info()
                
                msg = {
                    'type': 'initial_status',
                    'data': {
                        'behavior_mode': self.behavior_mode,
                        'last_displayed': self.last_displayed,
                        'current_session': session_info
                    }
                }
                await self.send_message(PATH_CONTROL, msg)

    async def temi_handler(self, websocket, message):
        try:
            msg_json = json.loads(message)
        except Exception as e:
            print(f'[ERROR][temi_handler]: {e}')
            return
            
        if msg_json['type'] == 'asr_result':
            user_query = msg_json['data']
            
            # Send ASR result to control panel
            await self.send_message(PATH_CONTROL, msg_json)
            
            # Generate response using session-aware function
            img_path = None
            if self.image_question_mode and self.latest_image and os.path.exists(self.latest_image):
                img_path = self.latest_image
                print(f'[INFO] Including image in response (question mode active): {img_path}')
            
            # This will automatically add user message and assistant response to current session
            res = generate_response_with_session(
                user_input=user_query,
                img_path=img_path
            )
            
            if res:
                msg_2 = {
                    'type': 'suggested_response',
                    'data': res,
                    'includes_image': img_path is not None,
                    'image_path': img_path,
                    'user_query': user_query,
                    'image_question_mode': self.image_question_mode
                }
                await self.send_message(PATH_CONTROL, msg_2)
        
        elif msg_json['type'] == 'picture_taken':
            image_filename = msg_json.get('data', {}).get('filename')
            if image_filename:
                image_path = os.path.join("participant_data/media", image_filename)
                self.set_latest_image(image_path)
                
                response_msg = {
                    'type': 'picture_taken',
                    'data': {
                        'filename': image_filename,
                        'path': image_path,
                        'ready_for_questions': True
                    }
                }
                await self.send_message(PATH_CONTROL, response_msg)

        elif msg_json['type'] == 'start_image_questions':
            self.activate_image_question_mode()
            
            response_msg = {
                'type': 'image_question_mode_activated',
                'data': {
                    'image_path': self.latest_image,
                    'message': 'Image question mode activated. User can now ask questions about the picture.'
                }
            }
            await self.send_message(PATH_CONTROL, response_msg)

        elif msg_json['type'] == 'stop_image_questions':
            self.deactivate_image_question_mode()
            
            response_msg = {
                'type': 'image_question_mode_deactivated',
                'data': {
                    'message': 'Image question mode deactivated. User can now ask questions without image context.'
                }
            }
            await self.send_message(PATH_CONTROL, response_msg)
        
        elif msg_json['type'] == 'saved_locations':
            locations = msg_json.get("data", [])
            print(f"Received locations: {locations}")
            await self.send_message(PATH_CONTROL, msg_json)

        elif msg_json['type'] == 'screenshot':
            await self.send_message(PATH_CONTROL, msg_json)

    async def participant_handler(self, websocket, message):
        try:
            msg_json = json.loads(message)
        except Exception as e:
            print(f'[ERROR][participant_handler]: {e}')
            return
        if 'command' not in msg_json:
            return
        if msg_json['command'] in [
                'skidJoy', 'tiltBy', 'tiltAngle',
                'stopMovement', 'turnBy']:
            await self.send_message(PATH_TEMI, msg_json)

    def _is_image_file(self, filename: str) -> bool:
        """Check if file is an image."""
        if not filename:
            return False
        lower = filename.lower()
        return lower.endswith((".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"))