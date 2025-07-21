import os
import shutil
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

app.mount("/media", StaticFiles(directory=UPLOAD_DIR), name="media")

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("Missing GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash-002")

# CORS is optional but useful during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # adjust for production
    allow_credentials=True,
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
    save_path = os.path.join(UPLOAD_DIR, file.filename)

    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    await server.send_message(PATH_CONTROL, {
        "type": "media_uploaded",
        "filename": file.filename,
        "url": f"/view/{file.filename}"
    })

    return {
        "status": "success",
        "filename": file.filename,
        "path": save_path
    }

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

    # Choose different prompt based on mode
    if request.mode == "conversation":
        prompt = "Start a friendly conversation based on this media."
    elif request.mode == "suggestion":
        prompt = "Provide a useful suggestion based on this media."
    else:
        prompt = "Analyze and describe this media."  # default fallback

    try:
        with Image.open(file_path) as image:
            result = model.generate_content([prompt, image])

        return {"success": True, "analysis": result.text}

    except UnidentifiedImageError:
        return JSONResponse(content={"success": False, "error": "File is not a valid image"}, status_code=400)
    except Exception as e:
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)
