import asyncio
import json
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



'''
photo, video
    - display 
    - capture
'''

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
        self.locations = []
        self.automation = False
        self.last_source = None


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
            # try:
            #     await connection.send(json.dumps(message))
            # except Exception as e:
            #     print(e)

    async def control_handler(self, websocket, message):
        # TODO: Check if Temi wants message or msg_json
        try:
            msg_json = json.loads(message)
        except Exception as e:
            print(f'[ERROR][control_handler]: {e}')
            return
        cmd = msg_json.get('command')
        if not cmd:
            return
        if cmd == 'takePicture':
            self.last_source = 'wizard'
            await self.send_message(PATH_TEMI, msg_json)
            return

        if msg_json['command'] == 'speak':
            self.messages.append({
                'role': 'assistant',
                'content': msg_json['payload']
            })
            self.save_messages()
            await self.send_message(PATH_TEMI, msg_json)
            await self.send_message(PATH_CONTROL, {
                'type': 'assistant_response',
                'data': msg_json['payload']
            })
            return

        elif msg_json['command'] == 'generate_response':
            img_path = None
            with_image = msg_json['payload']
            if with_image:
                # TODO
                # capture an image from Temi
                # include the path 
                # img_path = 
                pass
            res = generate_response(self.messages, img_path)
            if res:
                msg_2 = {
                    'type': 'suggested_response',
                    'data': res
                }
                await self.send_message(PATH_CONTROL, msg_2)

        elif msg_json['command'] == 'displayMedia':
            self.last_displayed = msg_json['payload']
            await self.send_message(PATH_TEMI, msg_json)

        elif msg_json['command'] == 'displayFace':
            self.last_displayed = None
            await self.send_message(PATH_TEMI, msg_json)

        elif msg_json['command'] in [
                'skidJoy', 'refreshScreenShot',
                'tiltBy', 'tiltAngle', 'stopMovement', 'turnBy',
                'queryLocations', 'goTo']:
            await self.send_message(PATH_TEMI, msg_json)
            
        elif msg_json['command'] == 'takePicture':
            await self.send_message(PATH_TEMI, msg_json)
            await self.send_message(PATH_CONTROL, {
                "type":     "media_uploaded",
                "filename": msg_json["payload"] or "<timestamp>",
                "source":   "wizard"
            })


        elif msg_json['command'] == 'navigateCamera':
            if self.behavior_mode == PASSIVE:
                msg_json['payload'] = 'headless'
                await self.send_message(PATH_TEMI, msg_json)
            await self.send_message(PATH_TEMI, msg_json)

        elif msg_json['command'] == 'startVideo':
            # TODO: behavior should differ depending on 
            # self.behavior_mode
            await self.send_message(PATH_TEMI, msg_json)

        elif msg_json['command'] == 'stopVideo':
            # TODO:
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
        elif cmd == 'startAutomation':
            print("Automation ON")
            self.automation = True
            await self.send_message(PATH_CONTROL, {
                'type': 'automation',
                'data': True
            })

        elif cmd == 'stopAutomation':
            print("Automation OFF")
            self.automation = False
            await self.send_message(PATH_CONTROL, {
                'type': 'automation',
                'data': False
            })

    async def temi_handler(self, websocket, message):
        try:
            msg_json = json.loads(message)
        except Exception as e:
            print(f'[ERROR][temi_handler]: {e}')
            return
        if msg_json.get("type") == "image" and msg_json.get("data", "").startswith("data:image"):
            import base64
            from pathlib import Path

            base64_data = msg_json["data"].split(",")[1]
            filename = msg_json["filename"]

            media_path = Path("participant_data/media") / filename
            media_path.write_bytes(base64.b64decode(base64_data))
            print(f"✅ [temi_handler] Saved image to {media_path}")
            source = self.last_source or 'temi'
            # reset the flag
            self.last_source = None
            self.last_displayed = filename
            await self.send_message(PATH_CONTROL, {
                "type": "media_uploaded",
                "filename": filename, 
                "source": source
            })
        if msg_json['type'] == 'assistant_response':
            await self.send_message(PATH_CONTROL, msg_json)
            print(f"[temi_handler] Received message: {msg_json}")

        elif msg_json['type'] == 'asr_result':
            user_text = msg_json['data']
            self.messages.append({'role': 'user','content': user_text})
            self.save_messages()
            await self.send_message(PATH_CONTROL, msg_json)

            res = generate_response(self.messages)
            if res:
                await self.send_message(PATH_CONTROL, {
                    'type': 'suggested_response',
                    'data': res
                })

                if self.automation:
                    await self.send_message(PATH_TEMI, {
                        'command': 'speak',
                        'payload': res
                    })
                    await self.send_message(PATH_CONTROL, {
                        'type': 'assistant_response',
                        'data': res
                    })
                    await self.send_message(PATH_TEMI, {
                        'type': 'start_listening'
                    })
        elif msg_json['type'] == 'saved_locations':
            locations = msg_json.get("data", [])
            print(f"Received locations: {locations}")
            await self.send_message(PATH_CONTROL, msg_json)

        elif msg_json['type'] == 'screenshot':
            await self.send_message(PATH_CONTROL, msg_json)
        
        elif msg_json['type'] == 'saved_locations':
            self.locations = msg_json.get("data", [])
            print(f"Received locations: {self.locations}")
            await self.send_message(PATH_CONTROL, {
                "type": "locationList",
                "data": self.locations
            })

    async def participant_handler(self, websocket, message):
        try:
            msg_json = json.loads(message)
        except Exception as e:
            print(f'[ERROR][control_handler]: {e}')
            return
        if 'command' not in msg_json:
            return
        if msg_json['command'] in [
                'skidJoy', 'tiltBy', 'tiltAngle',
                'stopMovement', 'turnBy']:
            await self.send_message(PATH_TEMI, msg_json)


server = WebSocketServer()

async def websocket_main():
    async def handler(websocket, path):
        print(f"[INFO] WebSocket requested path: {path}")

        path = path.rstrip('/').split('?')[0]

        if path not in [PATH_TEMI, PATH_CONTROL, PATH_PARTICIPANT]:
            print(f"[ERROR] Unknown path {path}")
            await websocket.close()
            return
        
        await server.handle_connection(websocket, path)

if __name__ == "__main__":
    asyncio.run(websocket_main())
# server = WebSocketServer()
# async def websocket_main():
#     async def handler(websocket):
#         await server.handle_connection(websocket)

#     server_proc = await serve(handler, "", 9090)
#     print("🚀 WebSocket server running on port 9090")

#     try:
#         await asyncio.Future()  # Run forever (until Ctrl+C)
#     except KeyboardInterrupt:
#         print("🛑 KeyboardInterrupt received, shutting down...")
#     finally:
#         server_proc.close()
#         await server_proc.wait_closed()
#         print("✅ Server stopped cleanly")
