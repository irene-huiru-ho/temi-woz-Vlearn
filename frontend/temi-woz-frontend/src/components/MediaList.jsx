import { useEffect, useState } from "react";

export default function MediaList({ sendMessage, newMediaFile, displayedMedia }) {
  const [files, setFiles] = useState([]);

  useEffect(() => {
    fetch("http://localhost:8000/api/media-list")
      .then((res) => res.json())
      .then((data) => setFiles(data.files))
      .catch((err) => console.error("Failed to fetch media list:", err));
  }, []);

  useEffect(() => {
    if (newMediaFile && !files.includes(newMediaFile)) {
      setFiles((prev) => [newMediaFile, ...prev]);
    }
  }, [newMediaFile]);

  const handleClickWithConfirm = (filename) => {
    const confirmed = window.confirm(`Send "${filename}" to Temi for display?`);
    if (confirmed) {
      sendMessage({
        command: "displayMedia",
        payload: filename
      })
    }
  };

  return (
    <div className="mt-4">
      <h4>📁 Uploaded Media</h4>

      {/* ✅ Scrollable wrapper */}
      <div
        style={{
          maxHeight: "400px",
          overflowY: "auto",
          paddingRight: "1rem",
          border: "1px solid #ccc",
          borderRadius: "8px",
        }}
      >
        <div className="d-flex flex-wrap gap-4 p-3">
          {files.map((file, idx) => {
            const isImage = /\.(jpg|jpeg|png|gif)$/i.test(file);
            const isVideo = /\.(mp4|webm)$/i.test(file);

            return (
              <div
                key={idx}
                style={{
                  textAlign: "center",
                  maxWidth: "200px",
                  flex: "0 0 auto",
                  cursor: "pointer",
                  justifyContent: "center",
                  alignItems: "center",
                  height: "210px",
                  display: "flex",
                  flexDirection: "column",     
                }}
              >
                {isImage && (
                  <img
                    src={`http://localhost:8000/media/${file}`}
                    alt={file}
                    style={{
                      maxWidth: "100%",
                      maxHeight: "200px",
                      border: displayedMedia === file && "5px solid #0d6efd",
                    }}
                    onClick={() => handleClickWithConfirm(file)}
                  />
                )}
                {isVideo && (
                  <video
                    src={`http://localhost:8000/media/${file}`}
                    controls
                    style={{
                      maxWidth: "100%",
                      maxHeight: "200px",
                      border: displayedMedia === file && "5px solid #0d6efd",
                    }}
                    onClick={() => handleClickWithConfirm(file)}
                  />
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>

  );
}
