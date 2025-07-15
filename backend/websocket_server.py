import asyncio
import json
import os
from websockets.asyncio.server import serve
from fastapi import WebSocketDisconnect
import signal
from llm_model import generate_response


PATH_TEMI = '/temi'
PATH_CONTROL = '/control'
PATH_PARTICIPANT = '/participant'
LOG_FILE = 'participant_data/log.log'
MESSAGES_FILE = 'participant_data/messages.json'


try:
    with open(MESSAGES_FILE, 'r') as f:
        MESSAGES = json.load(f)
except Exception as e:
    print('[ERROR] No messages file. Set to empty')
    MESSAGES = []


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
        self.messages = self._load_messages()
        self.latest_image = None
        self.image_question_mode = False  # Track if user is asking questions about an image
        self.child_age = None
        self.focus_area = None

    def _load_messages(self):
        try:
            with open(MESSAGES_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            print('[ERROR] No messages file. Set to empty')
            return []

    def save_messages(self):
        with open(MESSAGES_FILE, 'w') as f:
            json.dump(self.messages, f, indent=4)

    def set_latest_image(self, image_path: str):
        """Set the latest image path."""
        self.latest_image = image_path
        print(f'[INFO] Latest image set: {image_path}')

    def activate_image_question_mode(self):
        """Activate image question mode - next user queries will include the current image."""
        self.image_question_mode = True
        print(f'[INFO] Image question mode activated for image: {self.latest_image}')

    def deactivate_image_question_mode(self):
        """Deactivate image question mode."""
        self.image_question_mode = False
        print('[INFO] Image question mode deactivated')

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
                    # No handler for this path; close the connection.
                    return
        except WebSocketDisconnect:
            print(f"[{ws_path}] Disconnected")
        finally:
            if websocket in self.connections[ws_path]:
                self.connections[ws_path].remove(websocket)
            print(self.connections)

    async def send_message(self, group, message):
        # we really just expect one to be in the set
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
            
        cmd = msg_json.get('command')
        if not cmd:
             return
        if cmd == 'updateSettings':
            self.child_age  = msg_json['payload'].get('age')
            self.focus_area = msg_json['payload'].get('focus_area')
            print(f"[INFO] Settings updated → age={self.child_age}, focus={self.focus_area}")
            return
        
        if msg_json['command'] == 'speak':
            self.messages.append({
                'role': 'assistant',
                'content': msg_json['payload']
            })
            self.save_messages()
            await self.send_message(PATH_TEMI, msg_json)

        elif msg_json['command'] == 'generate_response':
            # Handle manual generate response request
            payload = msg_json.get('payload', {})
            with_image = payload.get('with_image', False)
            
            img_path = None
            if with_image and self.latest_image and os.path.exists(self.latest_image):
                img_path = self.latest_image
                print(f'[INFO] Using image for response generation: {img_path}')
            child_age = payload.get('age', None)
            focus = payload.get('focus_area', None)
            res = generate_response(self.messages, img_path, child_age = self.child_age, focus = self.focus_area)
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
            # If displaying an image, set it as latest image
            media_path = os.path.join("participant_data/media", msg_json['payload'])
            if self._is_image_file(msg_json['payload']):
                self.set_latest_image(media_path)
            await self.send_message(PATH_TEMI, msg_json)

        elif msg_json['command'] == 'displayFace':
            self.last_displayed = None
            # Deactivate image question mode when showing face
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
                msg = {
                    'type': 'initial_status',
                    'data': {
                        'behavior_mode': self.behavior_mode,
                        'last_displayed': self.last_displayed
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
            
            # Add user message to conversation
            self.messages.append({
                'role': 'user',
                'content': user_query
            })
            self.save_messages()
            
            # Send ASR result to control panel
            await self.send_message(PATH_CONTROL, msg_json)
            
            # Generate response - include image if we're in image question mode
            img_path = None
            if self.image_question_mode and self.latest_image and os.path.exists(self.latest_image):
                img_path = self.latest_image
                print(f'[INFO] Including image in response (question mode active): {img_path}')
            
            res = generate_response(self.messages, img_path, child_age = self.child_age, focus_area = self.focus_area)
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
            # Handle when Temi takes a picture
            image_filename = msg_json.get('data', {}).get('filename')
            if image_filename:
                image_path = os.path.join("participant_data/media", image_filename)
                self.set_latest_image(image_path)
                
                # Notify control panel
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
            # Handle when user clicks "start asking questions" button on Temi display
            self.activate_image_question_mode()
            
            # Notify control panel that image question mode is now active
            response_msg = {
                'type': 'image_question_mode_activated',
                'data': {
                    'image_path': self.latest_image,
                    'message': 'Image question mode activated. User can now ask questions about the picture.'
                }
            }
            await self.send_message(PATH_CONTROL, response_msg)

        elif msg_json['type'] == 'stop_image_questions':
            # Handle when user stops asking questions about the image
            self.deactivate_image_question_mode()
            
            # Notify control panel
            response_msg = {
                'type': 'image_question_mode_deactivated',
                'data': {
                    'message': 'Image question mode deactivated.'
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
