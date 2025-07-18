import os
import shutil
from typing import Optional
import google.generativeai as genai
import requests
from PIL import Image, UnidentifiedImageError
from io import BytesIO
from pydantic import BaseModel
from dotenv import load_dotenv

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
    age: Optional[int] = None
    focus_area: Optional[str] = None

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
    return {
        "behavior_mode": server.behavior_mode,
        "message_count": len(server.messages),
        "active_connections": {
            k: len(v) for k, v in server.connections.items()
        }
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
    
    age_text   = f"\nChild’s age: {request.age} years old." if request.age else ""
    focus_text = f"\nLearning focus: {request.focus_area}" if request.focus_area else ""

    # Import the new Gemini-based function
    from llm_model import generate_response_with_context
    
    # UPDATED: Much shorter, more natural conversation prompts
    if request.mode == "conversation":
        query = "Say hi! What learning opportunities do you see in this picture? Keep it brief and friendly."
    elif request.mode == "suggestion":
        query = "Give 1-2 useful suggestions of what learning opportunities you see based on this image."
    else:
        query = "Briefly describe what you see in this image."

    full_prompt = (
        f"{query}\n"
        f"{age_text}\n"
        f"{focus_text}"
    )

    try:
        # Use the new Gemini-based function
        result = generate_response_with_context(
            query=full_prompt,
            img_path=file_path,
            conversation_context=None
        )

        if result:
            return {"success": True, "analysis": result}
        else:
            return JSONResponse(content={"success": False, "error": "Failed to generate analysis"}, status_code=500)

    except Exception as e:
        print(f'[ERROR] analyze_media: {e}')
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)
