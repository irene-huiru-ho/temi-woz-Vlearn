let socket;

export function connectWebSocket(onMessage, path) {
  socket = new WebSocket(`ws://localhost:8000/${path}`);

  socket.onopen = () => {
    console.log("WebSocket connected");
    socket.send(JSON.stringify({ command: "identify", payload: "wizard" }));
  };

  socket.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log("Received:", data);
    onMessage?.(data);
  };

  socket.onclose = () => {
    console.warn("WebSocket closed");
  };

  socket.onerror = (err) => {
    console.error("WebSocket error:", err);
  };

  return socket;
}

export function sendMessageWS(message) {
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify(message));
  } else {
    console.warn("WebSocket not open");
  }
}

