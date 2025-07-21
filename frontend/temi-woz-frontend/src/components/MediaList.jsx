import { useEffect, useState } from "react";

export default function MediaList({
  sendMessage,
  newMediaFile,
  displayedMedia,
  handleSendToLLM,
  temiFiles
}) {
  const [files, setFiles] = useState([]);
  const [hoveredImage, setHoveredImage] = useState(null);
  
  const goToLocation = async (filename) => {
    const properName = filename.toLowerCase();
    console.log("Sending goTo for:", properName);
    sendMessage({
      command: "goTo",
      payload: properName,
    });
  };

  useEffect(() => {
    fetch("http://localhost:8000/api/media-list")
      .then((res) => res.json())
      .then((data) => {
        console.log("API response:", data); // Debug log
        setFiles(data.files || []);
      })
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
        payload: filename,
      });
    }
  };

  // Helper function to get filename from file (handles both string and object)
  const getFilename = (file) => {
    if (typeof file === 'string') {
      return file; // Old format: file is just the filename string
    }
    return file?.filename || 'unknown'; // New format: file is an object with filename property
  };

  // Helper function to get display name
  const getDisplayName = (file) => {
    if (typeof file === 'string') {
      return file; // Old format: use filename as display name
    }
    // New format: use display_name if available, otherwise filename without extension
    return file?.display_name || file?.filename?.replace(/\.[^/.]+$/, "") || 'unknown';
  };

  // Helper function to get source badge
  const getSourceBadge = (file) => {
    if (typeof file === 'string') {
      // Old format: check temiFiles set
      return temiFiles.has(file) ? "Temi" : null;
    }
    // New format: use source from API
    return file?.source || (temiFiles.has(file?.filename) ? "temi" : "wizard");
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
            // Get the actual filename to work with
            const filename = getFilename(file);
            const displayName = getDisplayName(file);
            const source = getSourceBadge(file);
            
            const isImage = /\.(jpg|jpeg|png|gif)$/i.test(filename);
            const isVideo = /\.(mp4|webm)$/i.test(filename);
            const mediaUrl = `http://localhost:8000/media/${filename}`;

            return (
              <div
                key={idx}
                style={{
                  textAlign: "center",
                  maxWidth: "200px",
                  flex: "0 0 auto",
                  cursor: "pointer",
                  justifyContent: "flex-start",
                  alignItems: "center",
                  height: "260px", // Increased to accommodate source badge
                  display: "flex",
                  flexDirection: "column",
                }}
              >
                {/* Filename and source badge shown above image */}
                <div style={{ marginBottom: "6px", width: "100%" }}>
                  <div
                    style={{
                      fontSize: "0.75rem",
                      fontWeight: 500,
                      color: "#333",
                      marginBottom: "4px",
                      maxWidth: "100%",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                    title={filename} // show full filename on hover
                  >
                    {displayName}
                  </div>
                  
                  {/* Source badge */}
                  {source && (
                    <div style={{ marginBottom: "4px" }}>
                      <span
                        style={{
                          background: source === "temi" ? "#4CAF50" : "#2196F3",
                          color: "white",
                          padding: "2px 8px",
                          fontSize: "0.65rem",
                          borderRadius: "12px",
                          fontWeight: "500"
                        }}
                      >
                        {source === "temi" ? "📱 Temi Robot" : "🧙‍♂️ Wizard Dashboard"}
                      </span>
                    </div>
                  )}
                </div>

                <div
                  style={{ position: "relative", display: "inline-block" }}
                  onMouseEnter={() => setHoveredImage(filename)}
                  onMouseLeave={() => setHoveredImage(null)}
                >
                  {isImage && (
                    <img
                      src={mediaUrl}
                      alt={displayName}
                      style={{
                        maxWidth: "100%",
                        maxHeight: "180px", // Reduced to accommodate badges
                        border: displayedMedia === filename ? "5px solid #0d6efd" : "1px solid #ddd",
                        borderRadius: "4px"
                      }}
                      onClick={() => handleClickWithConfirm(filename)}
                    />
                  )}

                  {isVideo && (
                    <video
                      src={mediaUrl}
                      controls
                      style={{
                        maxWidth: "100%",
                        maxHeight: "180px", // Reduced to accommodate badges
                        border: displayedMedia === filename ? "5px solid #0d6efd" : "1px solid #ddd",
                        borderRadius: "4px"
                      }}
                      onClick={() => handleClickWithConfirm(filename)}
                    />
                  )}

                  {hoveredImage === filename && (
                    <div
                      style={{
                        position: "absolute",
                        top: "8px",
                        right: "8px",
                        backgroundColor: "rgba(255, 255, 255, 0.95)",
                        border: "1px solid #ccc",
                        borderRadius: "6px",
                        padding: "6px",
                        display: "flex",
                        flexDirection: "column",
                        gap: "6px",
                        zIndex: 10,
                        width: "140px",
                      }}
                    >
                      <button
                        className="btn btn-sm btn-outline-primary w-100"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleSendToLLM(filename, "conversation");
                        }}
                      >
                        Start Conversation
                      </button>

                      <button
                        className="btn btn-sm btn-outline-secondary w-100"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleSendToLLM(filename, "suggestion");
                        }}
                      >
                        Provide Suggestion
                      </button>

                      <button
                        className="btn btn-sm btn-outline-success w-100"
                        onClick={(e) => {
                          e.stopPropagation();
                          goToLocation(filename);
                        }}
                      >
                        Go to Location
                      </button>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}