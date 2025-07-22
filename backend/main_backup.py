import os
import shutil
import google.generativeai as genai
import requests
from PIL import Image, UnidentifiedImageError
from io import BytesIO
from pydantic import BaseModel
from dotenv import load_dotenv

from llm_model import (
    start_new_session, end_current_session, get_session_info, 
    handle_session_command, get_current_session_messages
)

import json
from datetime import datetime
from fastapi.responses import FileResponse

from fastapi import (
    FastAPI, WebSocket, WebSocketDisconnect,
    Request, UploadFile, File
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from websocket_server import WebSocketServer, PATH_TEMI, PATH_CONTROL, PATH_PARTICIPANT

app = FastAPI()
server = WebSocketServer()
UPLOAD_DIR = "participant_data/media"

class AnalyzeRequest(BaseModel):
    image_filename: str
    mode: str

app.mount("/media", StaticFiles(directory=UPLOAD_DIR), name="media")

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("Missing GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash-exp")

# # CORS is optional but useful during development
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],  # adjust for production
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# Add this BEFORE any routes or other middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,  # Change this to False when using "*"
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.websocket(PATH_TEMI)
async def temi_ws(websocket: WebSocket):
    print(PATH_TEMI)
    await websocket.accept()
    await server.handle_connection(websocket, PATH_TEMI)

@app.websocket(PATH_CONTROL)
async def control_ws(websocket: WebSocket):
    print(PATH_CONTROL)
    await websocket.accept()
    await server.handle_connection(websocket, PATH_CONTROL)

@app.websocket(PATH_PARTICIPANT)
async def participant_ws(websocket: WebSocket):
    print(PATH_PARTICIPANT)
    await websocket.accept()
    await server.handle_connection(websocket, PATH_PARTICIPANT)

@app.get("/status")
def get_status():
    try:
        session_info = get_session_info()
        return {
            "behavior_mode": server.behavior_mode,
            "message_count": len(server.messages),
            "active_connections": {
                k: len(v) for k, v in server.connections.items()
            },
            "current_session": session_info
        }
    except Exception as e:
        print(f"[ERROR] Status endpoint error: {e}")
        return {
            "behavior_mode": server.behavior_mode,
            "message_count": len(server.messages),
            "active_connections": {
                k: len(v) for k, v in server.connections.items()
            },
            "current_session": {"active": False, "error": str(e)}
        }

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    # Create upload directory if it doesn't exist
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    
    # Sanitize filename to prevent directory traversal
    safe_filename = os.path.basename(file.filename)
    save_path = os.path.join(UPLOAD_DIR, safe_filename)

    try:
        with open(save_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        # Check if it's an image file
        is_image = safe_filename.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"))
        
        # Notify websocket server about the new file
        await server.send_message(PATH_CONTROL, {
            "type": "media_uploaded",
            "filename": safe_filename,
            "url": f"/view/{safe_filename}",
            "is_image": is_image
        })

        # If it's an image, set it as the latest image in the server
        if is_image:
            server.set_latest_image(save_path)
            print(f'[INFO] Image uploaded and set as latest: {save_path}')

        return {
            "status": "success",
            "filename": safe_filename,
            "path": save_path,
            "is_image": is_image
        }
        
    except Exception as e:
        print(f'[ERROR] Failed to save uploaded file: {e}')
        return JSONResponse(
            content={"status": "error", "message": "Failed to save file"}, 
            status_code=500
        )

# mostly for thumbnails and Temi display
@app.get("/view/{filename}", response_class=HTMLResponse)
async def view_media(filename: str, request: Request):
    file_url = f"/media/{filename}"
    lower = filename.lower()
    
    if lower.endswith((".jpg", ".jpeg", ".png", ".gif")):
        tag = f'<img src="{file_url}" style="max-width: 90%; max-height: 80vh;" />'
    elif lower.endswith((".mp4", ".webm")):
        tag = (
            f'<video controls autoplay style="max-width: 90%; max-height: 80vh;">'
            f'<source src="{file_url}" type="video/mp4">Your browser does not support the video tag.</video>'
        )
    else:
        tag = f"<p>Unsupported file type: {filename}</p>"

    return f"""
    <html>
      <head>
        <title>View Media: {filename}</title>
      </head>
      <body style="display:flex; flex-direction:column; align-items:center; justify-content:center; height:100vh;">
        {tag}
      </body>
    </html>
    """

# Not used for now but is available anyway
@app.get("/media-list", response_class=HTMLResponse)
async def list_media():
    files = os.listdir(UPLOAD_DIR)
    files.sort(reverse=True)

    items = ""
    for file in files:
        lower = file.lower()
        if lower.endswith((".jpg", ".jpeg", ".png", ".gif")):
            items += f"""
                <div style="margin: 20px; text-align: center;">
                    <img src="/media/{file}" style="max-width: 300px;"><br>
                    <button onclick="displayMedia('{file}')">Display on Temi</button>
                </div>
            """
        elif lower.endswith((".mp4", ".webm")):
            items += f"""
                <div style="margin: 20px; text-align: center;">
                    <video src="/media/{file}" controls style="max-width: 300px;"></video><br>
                    <button onclick="displayMedia('{file}')">Display on Temi</button>
                </div>
            """

    return f"""
    <html>
    <head>
        <title>Media List</title>
    </head>
    <body>
        <h1>Uploaded Media</h1>
        <div style="display: flex; flex-wrap: wrap;">
            {items}
        </div>
        <script>
        const socket = new WebSocket("ws://localhost:8000/control");

        socket.onopen = () => console.log("Connected to WebSocket");
        socket.onmessage = (event) => console.log("Received:", event.data);

        function displayMedia(filename) {{
            const message = {{
                command: "displayMedia",
                payload: filename
            }};
            socket.send(JSON.stringify(message));
            alert("Sent displayMedia command for: " + filename);
        }}
        </script>
    </body>
    </html>
    """
    
@app.get("/api/media-list")
async def get_media_list():
    files = os.listdir(UPLOAD_DIR)
    files.sort(reverse=True)

    media_files = []
    for file in files:
        lower = file.lower()
        if lower.endswith((".jpg", ".jpeg", ".png", ".gif", ".mp4", ".webm")):
            media_files.append(file)

    return JSONResponse(content={"files": media_files})

@app.post("/api/analyze-media")
async def analyze_media(request: AnalyzeRequest):
    file_path = os.path.join(UPLOAD_DIR, request.image_filename)

    if not os.path.exists(file_path):
        return JSONResponse(content={"success": False, "error": "File not found"}, status_code=404)

    # Import the unified function
    from llm_model import generate_response
    
    # Determine the query based on the request mode
    if request.mode == "conversation":
        query = "What learning opportunities do you see here? Let's talk about what we can explore together."
    elif request.mode == "suggestion":
        query = "What are some learning activities we could do based on what you see here?"
    else:
        query = "Tell me about what you observe here."

    try:
        # Use the unified function - it will automatically use session configuration
        result = generate_response(query, file_path)

        if result:
            return {"success": True, "analysis": result}
        else:
            return JSONResponse(content={"success": False, "error": "Failed to generate analysis"}, status_code=500)

    except Exception as e:
        print(f'[ERROR] analyze_media: {e}')
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)
    

# Endpoints for session management    
@app.get("/api/session/status")
async def get_session_status():
    """Get current session information."""
    try:
        result = get_session_info()
        print(f"[DEBUG] Session status request - returning: {result}")
        return result
    except Exception as e:
        print(f"[ERROR] Session status error: {e}")
        return JSONResponse(content={"error": str(e), "active": False}, status_code=500)

@app.post("/api/session/start")
async def start_family_session(request: Request):
    """Start a new family session with configuration."""
    try:
        body = await request.json()
        family_id = body.get('family_id') or f"family_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        child_age = body.get('child_age', 5)
        conversation_focus = body.get('conversation_focus', 'Open-ended')
        custom_message = body.get('custom_message', '')
        
        print(f"[DEBUG] Starting session for family: {family_id}")
        print(f"[DEBUG] Configuration - Age: {child_age}, Focus: {conversation_focus}")
        if custom_message:
            print(f"[DEBUG] Custom message: {custom_message}")
        
        # Import the functions we need
        from llm_model import start_new_session, current_session
        
        # Start session with configuration
        session_id = start_new_session(family_id, child_age, conversation_focus, custom_message)
        
        result = {
            'status': 'success',
            'action': 'session_started',
            'session_id': session_id,
            'family_id': family_id,
            'child_age': child_age,
            'conversation_focus': conversation_focus,
            'custom_message': custom_message
        }
        
        print(f"[DEBUG] Session start result: {result}")
        
        # Notify all connected clients about new session
        await server.broadcast_to_all({
            "type": "session_started",
            "family_id": family_id,
            "child_age": child_age,
            "conversation_focus": conversation_focus,
            "session_id": session_id
        })
        
        return result
    except Exception as e:
        print(f"[ERROR] Session start error: {e}")
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)

@app.post("/api/session/end")
async def end_family_session():
    """End the current family session and save data."""
    try:
        print("[DEBUG] Ending session...")
        result = handle_session_command('end')
        print(f"[DEBUG] Session end result: {result}")
        
        # Notify all connected clients about session end
        await server.broadcast_to_all({
            "type": "session_ended",
            "filepath": result.get('filepath')
        })
        
        return result
    except Exception as e:
        print(f"[ERROR] Session end error: {e}")
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)

@app.post("/api/session/download")
async def download_current_session():
    """Save and get download path for current session."""
    try:
        result = handle_session_command('download')
        return result
    except Exception as e:
        print(f"[ERROR] Session download error: {e}")
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)

@app.get("/api/session/messages")
async def get_session_messages():
    """Get all messages from current session."""
    try:
        messages = get_current_session_messages()
        return {"status": "success", "messages": messages, "count": len(messages)}
    except Exception as e:
        print(f"[ERROR] Session messages error: {e}")
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)

@app.get("/api/session/download-file/{session_filename}")
async def download_session_file(session_filename: str):
    """Download a specific session file."""
    try:
        filepath = f"sessions/{session_filename}"
        if os.path.exists(filepath):
            return FileResponse(
                path=filepath,
                filename=session_filename,
                media_type='application/json'
            )
        else:
            return JSONResponse(content={"error": "File not found"}, status_code=404)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.get("/api/sessions/list")
async def list_all_sessions():
    """List all saved session files."""
    try:
        sessions_dir = "sessions"
        if not os.path.exists(sessions_dir):
            return {"sessions": []}
        
        files = [f for f in os.listdir(sessions_dir) if f.endswith('.json')]
        files.sort(reverse=True)  # Most recent first
        
        session_info = []
        for file in files:
            filepath = os.path.join(sessions_dir, file)
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                    session_info.append({
                        'filename': file,
                        'family_id': data.get('family_id'),
                        'start_time': data.get('start_time'),
                        'end_time': data.get('end_time'),
                        'message_count': data.get('message_count', 0),
                        'duration_minutes': calculate_session_duration(data.get('start_time'), data.get('end_time'))
                    })
            except:
                continue
                
        return {"sessions": session_info}
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

def calculate_session_duration(start_time_str, end_time_str):
    """Calculate session duration in minutes."""
    try:
        if not start_time_str or not end_time_str:
            return None
        start = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
        end = datetime.fromisoformat(end_time_str.replace('Z', '+00:00'))
        duration = end - start
        return round(duration.total_seconds() / 60, 1)
    except:
        return None
    

# Add new endpoint for updating session configuration
@app.post("/api/session/update-config")
async def update_session_configuration_endpoint(request: Request):
    """Update configuration of the current active session."""
    try:
        body = await request.json()
        child_age = body.get('child_age', 5)
        conversation_focus = body.get('conversation_focus', 'Open-ended')
        custom_message = body.get('custom_message', '')
        
        print(f"[DEBUG] Updating session config - Age: {child_age}, Focus: {conversation_focus}")
        if custom_message:
            print(f"[DEBUG] Custom message: {custom_message}")
        
        # Use the unified function from llm_model
        from llm_model import update_session_configuration
        
        result = update_session_configuration(child_age, conversation_focus, custom_message)
        print(f"[DEBUG] Config update result: {result}")
        
        # Notify all connected clients about configuration update
        if result.get('status') == 'success':
            await server.broadcast_to_all({
                "type": "session_config_updated",
                "child_age": child_age,
                "conversation_focus": conversation_focus,
                "changes": result.get('changes', [])
            })
        
        return result
    except Exception as e:
        print(f"[ERROR] Session config update error: {e}")
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)



    

