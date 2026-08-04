import asyncio
import json
import os
import re
import time
from websockets.asyncio.server import serve
from fastapi import WebSocketDisconnect
import signal
from llm_model import generate_response, start_new_session, end_current_session, get_current_session_messages
from perception_model import PerceptionModel

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
        # COCO classes for simplicity, but tracking things like person, backpack, chair etc
        self.perception_model = PerceptionModel(target_classes=["person", "backpack", "chair", "bottle", "cup", "keyboard", "mouse", "book", "phone", "pen", "pencil", "notebook", "laptop", "tablet", "bag", "box","desk","clock", "cat"])
        # Search state variables
        self.search_state = "IDLE"  # "IDLE", "WAITING_FOR_ROOM", "GOING_TO_ROOM", "SEARCHING_OBJECT", "APPROACHING_OBJECT"
        self.search_target_object = None
        self.search_target_room = None
        self.saved_locations = []
        self.lost_track_frames = 0
        self.latest_raw_frame = None
        self.auto_scan_target = None  # None/none, "book", "laptop", "bottle", "person"
        self.book_scanning_enabled = False
        self.approach_start_time = 0
        
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
        # self.reset_latest_image()
        print('[INFO] Image question mode deactivated, latest image reset')

    async def handle_search_flow(self, user_query):
        user_query_clean = user_query.strip().lower()
        
        # Check if user requests to cancel search
        if "cancel search" in user_query_clean or "stop search" in user_query_clean or user_query_clean == "cancel" or user_query_clean == "stop":
            if self.search_state != "IDLE":
                self.search_state = "IDLE"
                self.search_target_object = None
                self.search_target_room = None
                await self.send_message(PATH_TEMI, {"command": "stopMovement", "payload": ""})
                await self.send_message(PATH_TEMI, {"command": "speak", "payload": "Search cancelled."})
                await self.send_message(PATH_TEMI, {"command": "togglePerception", "payload": "off"})
                return True

        if self.search_state == "IDLE":
            match = re.search(r"help me find\s+(.+)", user_query, re.IGNORECASE)
            if match:
                obj = match.group(1).strip().lower()
                # Clean common prefixes
                for prefix in ["my ", "a ", "an ", "the "]:
                    if obj.startswith(prefix):
                        obj = obj[len(prefix):]
                self.search_target_object = obj
                self.search_state = "WAITING_FOR_ROOM"
                print(f"[SEARCH] State: IDLE -> WAITING_FOR_ROOM, target object: '{self.search_target_object}'")
                
                # Query locations from Temi
                await self.send_message(PATH_TEMI, {"command": "queryLocations", "payload": ""})
                # Robot asks which room
                await self.send_message(PATH_TEMI, {"command": "speak", "payload": "Which room?"})
                return True
            return False

        elif self.search_state == "WAITING_FOR_ROOM":
            room = user_query.strip()
            room_lower = room.lower()
            
            # Check if this room exists in our saved locations
            matched_room = None
            for loc in self.saved_locations:
                if loc.lower() == room_lower:
                    matched_room = loc
                    break
            
            if matched_room:
                self.search_target_room = matched_room
                self.search_state = "GOING_TO_ROOM"
                print(f"[SEARCH] State: WAITING_FOR_ROOM -> GOING_TO_ROOM, room: '{matched_room}', target: '{self.search_target_object}'")
                
                # Tell Temi to go to the room
                await self.send_message(PATH_TEMI, {"command": "goTo", "payload": matched_room})
                # Robot speaks going to the room
                await self.send_message(PATH_TEMI, {"command": "speak", "payload": f"Going to the {matched_room}."})
            else:
                available_rooms = ", ".join(self.saved_locations) if self.saved_locations else ""
                if available_rooms:
                    reply = f"I couldn't find the room {room}. The available rooms are: {available_rooms}. Which room?"
                else:
                    reply = f"I couldn't find the room {room}. Please try another room."
                await self.send_message(PATH_TEMI, {"command": "speak", "payload": reply})
            
            return True
            
        return False

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
        if ws_path == PATH_TEMI:
            try:
                # Query locations immediately on connection to populate our list
                await websocket.send_json({"command": "queryLocations", "payload": ""})
            except Exception as e:
                print(f"[ERROR] Failed to query locations on connection: {e}")
        try:
            while True:
                message = await websocket.receive_text()
                print(message)
                if not message:
                    continue
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
            
        # NEW: SIMULATED USER INPUT COMMAND
        if msg_json['command'] == 'simulateUserInput':
            user_query = msg_json['payload']
            continue_previous_topic = msg_json.get('continue_previous_topic', False)
            
            print(f"[DEBUG] Simulated user input received: '{user_query}'")
            print(f"[DEBUG] Continue previous topic: {continue_previous_topic}")
            
            # Send simulated ASR result to control panel (mimic real speech-to-text)
            simulated_asr = {
                'type': 'asr_result',
                'data': user_query,
                'simulated': True  # Flag to indicate this was simulated
            }
            await self.send_message(PATH_CONTROL, simulated_asr)
            
            # Generate response using unified function (same as real speech)
            img_path = None
            if self.image_question_mode and self.latest_image and os.path.exists(self.latest_image):
                img_path = self.latest_image
                print(f'[INFO] Including image in simulated response (question mode active): {img_path}')

            print(f"[DEBUG] Generating response for simulated input - Image: {img_path is not None}")
            
            # Generate AI response using the same logic as real speech
            res = generate_response(user_query, img_path, continue_previous_topic)
            
            if res:
                msg_2 = {
                    'type': 'suggested_response',
                    'data': res,
                    'includes_image': img_path is not None,
                    'image_path': img_path,
                    'user_query': user_query,
                    'image_question_mode': self.image_question_mode,
                    'continue_previous_topic': continue_previous_topic,
                    'simulated': True  # Flag to indicate this was from simulated input
                }
                await self.send_message(PATH_CONTROL, msg_2)
            else:
                print(f"[ERROR] Failed to generate response for simulated input: '{user_query}'")
                
        # SESSION MANAGEMENT COMMANDS
        elif msg_json['command'] == 'start_family_session':
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
            continue_previous_topic = msg_json.get('continue_previous_topic', False)
            print(f"[DEBUG] Speak command - Continue topic: {continue_previous_topic}")
            
            # This will automatically add to current session
            from llm_model import current_session
            if current_session:
                current_session.add_message('assistant', response_text)
            
            await self.send_message(PATH_TEMI, msg_json)

        elif msg_json['command'] == 'generate_response':
            payload = msg_json.get('payload', {})
            with_image = payload.get('with_image', False)
            continue_previous_topic = payload.get('continue_previous_topic', False)
            
            img_path = None
            if with_image and self.latest_image and os.path.exists(self.latest_image):
                img_path = self.latest_image
                print(f'[INFO] Using image for response generation: {img_path}')

            print(f"[DEBUG] Generate response - Image: {img_path is not None}, Continue topic: {continue_previous_topic}")

            
            # Use unified function - it automatically handles session configuration
            res = generate_response(
            "Please generate a response based on our conversation so far",
            img_path,
            continue_previous_topic
            )
            
            if res:
                msg_2 = {
                    'type': 'suggested_response',
                    'data': res,
                    'includes_image': img_path is not None,
                    'image_path': img_path,
                    'continue_previous_topic': continue_previous_topic
                }
                await self.send_message(PATH_CONTROL, msg_2)

        
        elif msg_json['command'] == 'displayMedia':
            self.last_displayed = msg_json['payload']
            media_path = os.path.join("participant_data/media", msg_json['payload'])
            if self._is_image_file(msg_json['payload']):
                self.set_latest_image(media_path)
                # ADD THIS: Notify frontend when image is displayed
                print(f"🔍 BACKEND: Sending latest_image_updated for {msg_json['payload']}")
                latest_image_msg = {
                    'type': 'latest_image_updated',
                    'data': {'filename': msg_json['payload']}
                }
                await self.send_message(PATH_CONTROL, latest_image_msg)
            await self.send_message(PATH_TEMI, msg_json)

        #testing

        elif msg_json['command'] == 'setLatestImage':
            media_path = os.path.join("participant_data/media", msg_json['payload'])
            if self._is_image_file(msg_json['payload']):
                self.set_latest_image(media_path)
                print(f"🔍 BACKEND: Explicitly setting latest image to {msg_json['payload']}")
                latest_image_msg = {
                    'type': 'latest_image_updated',
                    'data': {'filename': msg_json['payload']}
                }
                await self.send_message(PATH_CONTROL, latest_image_msg)

        elif msg_json['command'] == 'displayFace':
            self.last_displayed = None
            # self.deactivate_image_question_mode()
            await self.send_message(PATH_TEMI, msg_json)

        elif msg_json['command'] == 'listenNoImage':
            #self.reset_latest_image()
            #self.deactivate_image_question_mode()
            self.image_question_mode = False
            await self.send_message(PATH_TEMI, msg_json)
            # setLog(prev => [...prev, f"[{timestamp}] 🎧 Listen mode activated (no image)"])

        elif msg_json['command'] == 'listenImage':  
            if not self.latest_image or not os.path.exists(self.latest_image):
                print(f"[ERROR] No valid image available for listenImage command: {self.latest_image}")
                return
            self.activate_image_question_mode()
            msg_json['payload'] = self.latest_image  # Ensure payload is set to latest image
            await self.send_message(PATH_TEMI, msg_json)
            # setLog(prev => [...prev, f"[{timestamp}] 🎧📷 Listen mode activated (with image: {self.latest_image})"])
        
        elif msg_json['command'] == 'captureLiveFrame':
            frame_data = self.latest_raw_frame
            if frame_data:
                # Clean base64 header if present
                if frame_data.startswith('data:image'):
                    frame_data = frame_data.split(',')[1]
                
                import base64
                img_bytes = base64.b64decode(frame_data)
                
                # Get custom name from payload and sanitize it
                custom_name = msg_json.get('payload', '').strip()
                import re
                custom_name = re.sub(r'[\\/*?:"<>|]', "", custom_name)
                custom_name = re.sub(r'\s+', "_", custom_name)
                custom_name = os.path.basename(custom_name)
                
                # Save to Media Library
                import datetime
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                if custom_name:
                    filename = f"{custom_name}_{timestamp}.jpg"
                else:
                    filename = f"live_capture_{timestamp}.jpg"
                
                base, ext = os.path.splitext(filename)
                counter = 1
                filepath = os.path.join("participant_data/media", filename)
                while os.path.exists(filepath):
                    filename = f"{base}_{counter}{ext}"
                    filepath = os.path.join("participant_data/media", filename)
                    counter += 1
                
                os.makedirs("participant_data/media", exist_ok=True)
                with open(filepath, "wb") as f:
                    f.write(img_bytes)
                
                # Set latest image
                self.set_latest_image(filepath)
                
                # Notify control panel to add it dynamically to the media library
                await self.send_message(PATH_CONTROL, {
                    "type": "media_uploaded",
                    "filename": filename,
                    "url": f"/view/{filename}",
                    "is_image": True,
                    "source": "wizard",
                    "is_live_capture": True
                })
                
                # If a custom name is specified, tell Temi to save its current location under this name
                if custom_name:
                    await self.send_message(PATH_TEMI, {
                        "command": "saveLocation",
                        "payload": custom_name
                    })
                    
                print(f"[INFO] Saved live raw frame to {filepath}")
            else:
                print("[WARN] No live raw frame available in memory to capture yet.")

        elif msg_json['command'] in ['setScanTarget', 'toggleBookScanning']:
            payload = msg_json.get('payload', 'none')
            if payload == 'on' or payload is True:
                payload = 'book'
            elif payload == 'off' or payload is False or not payload:
                payload = 'none'
            
            target = str(payload).lower().strip()
            self.auto_scan_target = target if target != 'none' else None
            self.book_scanning_enabled = bool(self.auto_scan_target)

            # If switched to OFF/none, immediately stop movement and reset search state
            if not self.auto_scan_target:
                if self.search_state in ["SEARCHING_OBJECT", "APPROACHING_OBJECT", "WAITING_FOR_PICTURE"]:
                    print("[SCAN_TARGET] Target set to OFF. Cancelling search and stopping robot movement.")
                    self.search_state = "IDLE"
                    self.search_target_object = None
                    self.lost_track_frames = 0
                    await self.send_message(PATH_TEMI, {"command": "stopMovement", "payload": ""})

            print(f"[SCAN_TARGET] Auto scan target set to: {self.auto_scan_target}")
            msg = {
                'type': 'scan_target_status',
                'data': {
                    'target': self.auto_scan_target or 'none',
                    'enabled': bool(self.auto_scan_target)
                }
            }
            await self.send_message(PATH_CONTROL, msg)

        elif msg_json['command'] == 'togglePerception':
            payload = msg_json.get('payload', 'off')
            if payload == 'on' and self.behavior_mode == PASSIVE:
                msg_json['payload'] = 'on_headless'
            await self.send_message(PATH_TEMI, msg_json)

        elif msg_json['command'] in [
                'skidJoy', 'takePicture', 'refreshScreenShot',
                'tiltBy', 'tiltAngle', 'stopMovement', 'turnBy',
                'queryLocations', 'goTo', 'saveLocation']:
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

                # Extract filename from latest_image path if it exists
                latest_image_filename = None
                if self.latest_image:
                    latest_image_filename = os.path.basename(self.latest_image)
                
                msg = {
                    'type': 'initial_status',
                    'data': {
                        'behavior_mode': self.behavior_mode,
                        'last_displayed': latest_image_filename,
                        'current_session': session_info,
                        'auto_scan_target': self.auto_scan_target or 'none',
                        'book_scanning_enabled': bool(self.auto_scan_target)
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
            
            # Intercept search flow
            if await self.handle_search_flow(user_query):
                return
            
            # Generate response using unified function
            # Default to prioritize current for direct speech (continue_previous_topic=False)
            img_path = None
            if self.image_question_mode and self.latest_image and os.path.exists(self.latest_image):
                img_path = self.latest_image
                print(f'[INFO] Including image in response (question mode active): {img_path}')

            print(f"[DEBUG] ASR result - User: '{user_query}', Image: {img_path is not None}")

            
            # For direct speech, default to prioritizing current input (continue_previous_topic=False)
            # The wizard can override this with the toggle for subsequent responses
            res = generate_response(user_query, img_path, continue_previous_topic=False)
            
            if res:
                msg_2 = {
                    'type': 'suggested_response',
                    'data': res,
                    'includes_image': img_path is not None,
                    'image_path': img_path,
                    'user_query': user_query,
                    'image_question_mode': self.image_question_mode,
                    'continue_previous_topic': False # Default to False for direct speech
                }
                await self.send_message(PATH_CONTROL, msg_2)
        
        elif msg_json['type'] == 'picture_taken':
            image_filename = msg_json.get('data', {}).get('filename')
            if image_filename:
                image_path = os.path.join("participant_data/media", image_filename)
                self.set_latest_image(image_path)

                # ADD THIS DEBUG PRINT
                print(f"🔍 BACKEND: Sending picture_taken for {image_filename}")
                
                response_msg = {
                    'type': 'picture_taken',
                    'data': {
                        'filename': image_filename,
                        'path': image_path,
                        'ready_for_questions': True
                    }
                }
                await self.send_message(PATH_CONTROL, response_msg)
                
                # Check if we were waiting for the search picture
                if self.search_state == "WAITING_FOR_PICTURE":
                    print("[SEARCH] Picture taken successfully. Speaking arrival and turning off perception.")
                    self.search_state = "IDLE"
                    
                    target_name = self.search_target_object or "object"
                    speak_text = f"I have reached the {target_name} and taken a picture."
                        
                    await self.send_message(PATH_TEMI, {"command": "speak", "payload": speak_text})
                    await self.send_message(PATH_TEMI, {"command": "togglePerception", "payload": "off"})
                    self.search_target_object = None
                    self.search_target_room = None

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
            self.saved_locations = locations
            await self.send_message(PATH_CONTROL, msg_json)

        elif msg_json['type'] == 'goto_status':
            await self.send_message(PATH_CONTROL, msg_json)
            data = msg_json.get('data', {})
            location = data.get('location')
            status = data.get('status')
            print(f"[SEARCH] Received goto_status: location={location}, status={status}")
            
            if self.search_state == "GOING_TO_ROOM" and location and self.search_target_room and location.lower() == self.search_target_room.lower():
                if status == "complete":
                    self.search_state = "SEARCHING_OBJECT"
                    print(f"[SEARCH] State: GOING_TO_ROOM -> SEARCHING_OBJECT")
                    
                    await self.send_message(PATH_TEMI, {"command": "speak", "payload": f"I have arrived at the {self.search_target_room}. Now starting search for the {self.search_target_object}."})
                    
                    await self.send_message(PATH_TEMI, {"command": "togglePerception", "payload": "on"})
                elif status == "abort":
                    self.search_state = "IDLE"
                    self.search_target_object = None
                    self.search_target_room = None
                    print(f"[SEARCH] State: GOING_TO_ROOM -> IDLE (aborted)")
                    
                    await self.send_message(PATH_TEMI, {"command": "speak", "payload": f"Navigation to the {location} was aborted. Search stopped."})

        elif msg_json['type'] == 'screenshot':
            await self.send_message(PATH_CONTROL, msg_json)
            
        elif msg_json['type'] == 'video_frame':
            try:
                # Run perception model separatly to avoid blocking event loop (in try so it appears)
                frame_data = msg_json.get('data')
                if frame_data:
                    self.latest_raw_frame = frame_data
                    loop = asyncio.get_running_loop()
                    annotated_frame, detections = await loop.run_in_executor(
                        None, self.perception_model.process_frame, frame_data
                    )
                    if annotated_frame:
                        perception_msg = {
                            'type': 'perception_update',
                            'data': {
                                'image': annotated_frame,
                                'detections': detections
                            }
                        }
                        await self.send_message(PATH_CONTROL, perception_msg)

                        # Debug logging for Android Studio Logcat & Backend console
                        if detections:
                            for det in detections:
                                det_class = det["class"]
                                conf = det.get("confidence", 0.0)
                                print(f"[PERCEPTION_DEBUG] {det_class} detected (confidence: {conf:.2f})")
                                await self.send_message(PATH_TEMI, {
                                    "command": "detectionDebug",
                                    "payload": f"{det_class.lower()} detected"
                                })
                        
                        # Check if Temi is searching for object
                        if self.search_state == "SEARCHING_OBJECT" and self.search_target_object:
                            target = self.search_target_object
                            matched_class = None
                            for det in detections:
                                det_class = det["class"].lower()
                                if det_class == target or target in det_class or det_class in target:
                                    matched_class = det["class"]
                                    break
                            
                            if matched_class:
                                target_display = matched_class.capitalize()
                                print(f"[SEARCH] Object found: {matched_class}! Transitioning to APPROACHING_OBJECT.")
                                self.search_state = "APPROACHING_OBJECT"
                                self.search_target_object = matched_class
                                self.approach_start_time = time.time()
                                self.lost_track_frames = 0
                                await self.send_message(PATH_TEMI, {"command": "speak", "payload": f"{target_display} detected. Moving closer."})
                                await self.send_message(PATH_CONTROL, {"type": "search_status", "data": f"{target_display} detected. Moving closer..."})

                        elif self.search_state == "IDLE" and self.auto_scan_target:
                            # If auto scan target is set (book, laptop, bottle, person), search and approach it
                            target = self.auto_scan_target.lower()
                            matched_obj = None
                            for det in detections:
                                det_class = det["class"].lower()
                                if det_class == target or target in det_class or det_class in target:
                                    matched_obj = det
                                    break
                            if matched_obj:
                                target_display = target.capitalize()
                                print(f"[PERCEPTION] {target_display} detected in IDLE state! Transitioning to APPROACHING_OBJECT.")
                                self.search_state = "APPROACHING_OBJECT"
                                self.search_target_object = target
                                self.approach_start_time = time.time()
                                self.lost_track_frames = 0
                                await self.send_message(PATH_TEMI, {"command": "speak", "payload": f"{target_display} detected. Moving closer."})
                                await self.send_message(PATH_CONTROL, {"type": "search_status", "data": f"{target_display} detected. Moving closer..."})

                        elif self.search_state == "APPROACHING_OBJECT" and self.search_target_object:
                            # If auto scan target was turned off and not in manual room search, cancel approach
                            if not self.auto_scan_target and not self.search_target_room:
                                print("[SEARCH] Auto scan target turned off while approaching. Stopping movement.")
                                self.search_state = "IDLE"
                                self.search_target_object = None
                                self.lost_track_frames = 0
                                await self.send_message(PATH_TEMI, {"command": "stopMovement", "payload": ""})
                                return

                            target = self.search_target_object
                            elapsed = time.time() - self.approach_start_time if self.approach_start_time else 0
                            MAX_APPROACH_TIME = 12.0  # Allow up to 12 seconds to approach object
                            
                            target_detection = None
                            for det in detections:
                                det_class = det["class"].lower()
                                if det_class == target or target in det_class or det_class in target:
                                    target_detection = det
                                    break
                            
                            if target_detection:
                                self.lost_track_frames = 0
                                rel_box = target_detection.get("rel_box")
                                if rel_box:
                                    x1_rel, y1_rel, x2_rel, y2_rel = rel_box
                                    rel_width = x2_rel - x1_rel
                                    rel_height = y2_rel - y1_rel
                                    rel_center_x = (x1_rel + x2_rel) / 2.0
                                    
                                    print(f"[SEARCH] Approaching {target}: width={rel_width:.3f}, height={rel_height:.3f}, elapsed={elapsed:.1f}s")
                                    
                                    # Check if close enough (rel_width >= 0.45 or rel_height >= 0.55) OR approach time limit reached
                                    is_close = rel_width >= 0.45 or rel_height >= 0.55
                                    is_timeout = elapsed >= MAX_APPROACH_TIME
                                    
                                    if is_close or is_timeout:
                                        reason = "Reached target distance" if is_close else f"Approach time limit reached ({elapsed:.1f}s)"
                                        print(f"[SEARCH] {reason}. Stopping and taking picture of {target}.")
                                        self.search_state = "WAITING_FOR_PICTURE"
                                        await self.send_message(PATH_TEMI, {"command": "stopMovement", "payload": ""})
                                        await self.send_message(PATH_TEMI, {"command": "takePicture", "payload": f"found_{target}"})
                                    else:
                                        # center target
                                        error_x = 0.5 - rel_center_x
                                        y_steer = error_x * 1.2
                                        y_steer = max(-0.4, min(0.4, y_steer))
                                        
                                        x_forward = 0.2
                                        
                                        print(f"[SEARCH] Sending skidJoy: x={x_forward}, y={y_steer:.3f}")
                                        await self.send_message(PATH_TEMI, {"command": "skidJoy", "payload": f"({x_forward}, {y_steer:.3f})"})
                            else:
                                # target not detected
                                self.lost_track_frames += 1
                                print(f"[SEARCH] Target {target} lost! lost_track_frames={self.lost_track_frames}, elapsed={elapsed:.1f}s")
                                if self.lost_track_frames > 15 or elapsed >= MAX_APPROACH_TIME:
                                    reason = f"Target lost for {self.lost_track_frames} frames" if self.lost_track_frames > 15 else f"Approach time limit reached ({elapsed:.1f}s)"
                                    print(f"[SEARCH] {reason} for {target}. Stopping and taking picture anyway.")
                                    self.search_state = "WAITING_FOR_PICTURE"
                                    await self.send_message(PATH_TEMI, {"command": "stopMovement", "payload": ""})
                                    await self.send_message(PATH_TEMI, {"command": "takePicture", "payload": f"found_{target}"})

            except Exception as e:
                print(f"[ERROR][temi_handler][video_frame]: {e}")


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