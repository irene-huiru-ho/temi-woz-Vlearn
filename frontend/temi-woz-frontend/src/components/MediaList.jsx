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
      <h4 style={{ 
        marginBottom: "1rem", 
        color: "#333",
        fontWeight: "600"
      }}>
        📁 Uploaded Media
      </h4>

      {/* Improved scrollable wrapper */}
      <div
        style={{
          maxHeight: files.length > 9 ? "600px" : "none",
          overflowY: files.length > 9 ? "auto" : "visible",
          padding: "1.5rem",
          border: "1px solid #e0e0e0",
          borderRadius: "12px",
          backgroundColor: "#fafafa",
          boxShadow: "0 2px 8px rgba(0,0,0,0.05)"
        }}
      >
        <div className="d-flex flex-wrap gap-4" style={{ 
          justifyContent: "center",
          alignItems: "flex-start"
        }}>
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
                  width: "300px",
                  cursor: "pointer",
                  display: "flex",
                  flexDirection: "column",
                  backgroundColor: "white",
                  borderRadius: "8px",
                  padding: "0.75rem",
                  border: "1px solid #e5e5e5",
                  transition: "all 0.2s ease",
                  boxShadow: "0 1px 3px rgba(0,0,0,0.1)"
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.transform = "translateY(-2px)";
                  e.currentTarget.style.boxShadow = "0 4px 12px rgba(0,0,0,0.15)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.transform = "translateY(0)";
                  e.currentTarget.style.boxShadow = "0 1px 3px rgba(0,0,0,0.1)";
                }}
              >
                {/* Filename and source badge */}
                <div style={{ marginBottom: "8px", width: "100%" }}>
                  <div
                    style={{
                      fontSize: "0.85rem",
                      fontWeight: "600",
                      color: "#333",
                      marginBottom: "6px",
                      lineHeight: "1.3",
                      height: "2.6em",
                      overflow: "hidden",
                      display: "-webkit-box",
                      WebkitLineClamp: 2,
                      WebkitBoxOrient: "vertical",
                      wordBreak: "break-word"
                    }}
                    title={filename}
                  >
                    {displayName}
                  </div>
                  
                  {/* Source badge */}
                  {source && (
                    <div style={{ marginBottom: "6px" }}>
                      <span
                        style={{
                          background: source === "temi" ? "linear-gradient(135deg, #4CAF50, #45a049)" : "linear-gradient(135deg, #2196F3, #1976D2)",
                          color: "white",
                          padding: "4px 10px",
                          fontSize: "0.7rem",
                          borderRadius: "16px",
                          fontWeight: "500",
                          boxShadow: "0 1px 3px rgba(0,0,0,0.2)"
                        }}
                      >
                        {source === "temi" ? "📱 Temi Robot" : "🧙‍♂️ Wizard Dashboard"}
                      </span>
                    </div>
                  )}
                </div>

                <div
                  style={{ 
                    position: "relative", 
                    display: "flex",
                    justifyContent: "center",
                    alignItems: "center",
                    flex: 1
                  }}
                  onMouseEnter={() => setHoveredImage(filename)}
                  onMouseLeave={() => setHoveredImage(null)}
                >
                  {isImage && (
                    <img
                      src={mediaUrl}
                      alt={displayName}
                      style={{
                        maxWidth: "100%",
                        maxHeight: "220px",
                        border: displayedMedia === filename ? "3px solid #0d6efd" : "1px solid #ddd",
                        borderRadius: "6px",
                        objectFit: "cover",
                        boxShadow: displayedMedia === filename ? "0 0 0 2px rgba(13, 110, 253, 0.25)" : "none"
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
                        maxHeight: "220px",
                        border: displayedMedia === filename ? "3px solid #0d6efd" : "1px solid #ddd",
                        borderRadius: "6px",
                        boxShadow: displayedMedia === filename ? "0 0 0 2px rgba(13, 110, 253, 0.25)" : "none"
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
                        backgroundColor: "rgba(255, 255, 255, 0.98)",
                        border: "1px solid #ddd",
                        borderRadius: "8px",
                        padding: "8px",
                        display: "flex",
                        flexDirection: "column",
                        gap: "6px",
                        zIndex: 10,
                        width: "140px",
                        boxShadow: "0 4px 16px rgba(0,0,0,0.15)",
                        backdropFilter: "blur(4px)"
                      }}
                    >
                      <button
                        className="btn btn-sm btn-outline-primary w-100"
                        style={{ 
                          fontSize: "0.75rem",
                          padding: "4px 8px",
                          borderRadius: "4px"
                        }}
                        onClick={(e) => {
                          e.stopPropagation();
                          handleSendToLLM(filename, "conversation");
                        }}
                      >
                        Start Conversation
                      </button>

                      <button
                        className="btn btn-sm btn-outline-secondary w-100"
                        style={{ 
                          fontSize: "0.75rem",
                          padding: "4px 8px",
                          borderRadius: "4px"
                        }}
                        onClick={(e) => {
                          e.stopPropagation();
                          handleSendToLLM(filename, "suggestion");
                        }}
                      >
                        Provide Suggestion
                      </button>

                      <button
                        className="btn btn-sm btn-outline-success w-100"
                        style={{ 
                          fontSize: "0.75rem",
                          padding: "4px 8px",
                          borderRadius: "4px"
                        }}
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