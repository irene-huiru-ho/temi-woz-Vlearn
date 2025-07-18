import { useEffect, useState, useRef } from "react";
import { connectWebSocket, sendMessageWS } from "../utils/ws";
import MediaList from "../components/MediaList";
import { useGamepadControls } from "../utils/useGamepadControls";
import presetPhrases from "../utils/presetPhrases";

const WizardPage = () => {
  const [log, setLog] = useState([]);
  const [inputText, setInputText] = useState("");
  const [pressedButtons, setPressedButtons] = useState([]);
  const [isRecording, setIsRecording] = useState(false);
  const [savedLocations, setSavedLocations] = useState([]);
  const [uploadNotification, setUploadNotification] = useState(null);
  const [latestUploadedFile, setLatestUploadedFile] = useState(null);
  const [displayedMedia, setDisplayedMedia] = useState(null);
  const [llmResponse, setLlmResponse] = useState("");
  const [activeMediaContext, setActiveMediaContext] = useState(null);
  const [temiFiles, setTemiFiles] = useState(new Set());
  const [wizardFiles, setWizardFiles] = useState(new Set());
  const [automationEnabled, setAutomationEnabled] = useState(false);
  const [showControls, setShowControls] = useState(true);
  const [autoSendCountdown, setAutoSendCountdown] = useState(0);
  const [childAge, setChildAge] = useState(1);

  const focusChoices = [
        { value: "Literacy and Communication", label: "Literacy and Communication", icon: <span role="img" aria-label="book">📚</span> },
        { value: "STEM", label: "STEM", icon: <span role="img" aria-label="gears">⚙️</span> },
        { value: "Creativity", label: "Creativity", icon: <span role="img" aria-label="art">🎨</span> },
        { value: "Emotional Intelligence", label: "Emotional Intelligence", icon: <span role="img" aria-label="heart">❤️</span> },
    ];
  const [focusArea,  setFocusArea]  = useState(focusChoices[0].value);


  const wsRef = useRef(null);
  const logEndRef = useRef(null);
  const automationRef = useRef(automationEnabled);

  useEffect(() => {
    automationRef.current = automationEnabled;
  }, [automationEnabled]);

  const getTimestamp = () => {
    return new Date().toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  };

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [log]);

  useEffect(() => {
    console.log("Automation state changed to:", automationEnabled);
  }, [automationEnabled]);

  const autoSendResponse = (responseText) => {
    const currentAutomation = automationRef.current;
    console.log("🔥 autoSendResponse called with:", responseText);
    console.log("🔥 Current automation state (ref):", currentAutomation);
    
    if (currentAutomation && responseText.trim()) {
      setLog((prev) => [...prev, `[${getTimestamp()}] ⏰ AUTO-SEND starting 3-second countdown...`]);
      setAutoSendCountdown(3);
      
      if (window.autoSendTimers) {
        window.autoSendTimers.forEach(timer => clearTimeout(timer));
      }
      
      const timer1 = setTimeout(() => {
        console.log("🔥 Countdown: 2 seconds left");
        setAutoSendCountdown(2);
      }, 1000);
      
      const timer2 = setTimeout(() => {
        console.log("🔥 Countdown: 1 second left");
        setAutoSendCountdown(1);
      }, 2000);
      
      const timer3 = setTimeout(() => {
        console.log("🔥 AUTO-SENDING NOW:", responseText);
        setAutoSendCountdown(0);
        sendMessage({ command: "speak", payload: responseText });
        setLog((prev) => [...prev, `[${getTimestamp()}] ✅ AUTO-SENT: ${responseText}`]);
        setInputText("");
      }, 3000);
      
      window.autoSendTimers = [timer1, timer2, timer3];
    } else {
      console.log("🔥 Auto-send skipped - automation disabled or empty text");
    }
  };

  const handleSendToLLM = async (imageFilename, mode) => {
    setActiveMediaContext({ filename: imageFilename, mode });
    setLog((prev) => [
      ...prev,
      `[${getTimestamp()}] ${
        mode === "conversation" ? "Started conversation" : "Suggested response"
      } for "${imageFilename}"`,
    ]);
    console.log("Sending to /api/analyze-media:", {
      image_filename: imageFilename,
      mode: mode || "default",
    });
    try {
      const res = await fetch("http://localhost:8000/api/analyze-media", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          image_filename: imageFilename,
          mode: mode || "default",
          age: childAge,
          focus_area: focusArea,
        }),
      });
      console.log("Sending to LLM with mode:", mode);
      const data = await res.json();
      const llmOutput = data.analysis || "No response from LLM";
      setLlmResponse(llmOutput);
      setInputText(llmOutput);
    } catch (error) {
      setLlmResponse("Error contacting LLM.");
      console.error(error);
    }
  };

  const sendMessage = (message) => {
    sendMessageWS(message);
    if (message.command === "displayMedia") {
      setDisplayedMedia(message.payload);
    } else if (message.command === "displayFace") {
      setDisplayedMedia(null);
    }
  };

  useEffect(() => {
    const storedLog = localStorage.getItem("wizardMessageLog");
    if (storedLog) {
      setLog(JSON.parse(storedLog));
    }
  }, []);

  useEffect(() => {
    localStorage.setItem("wizardMessageLog", JSON.stringify(log));
  }, [log]);

  const onWsMessage = (data) => {
    console.log('onWsMessage received:', data)
    console.log('Current automation state:', automationEnabled)
    
    if (data.type === 'asr_result') {
      setLog((prev) => [...prev, `[${getTimestamp()}] Received: ${data.data}`]);
    } else if (data.type === 'assistant_response') {
      setLog((prev) => [...prev, `[${getTimestamp()}] Temi: ${data.data}`]);
    } else if (data.type === 'suggested_response') {
      const responseText = data.data;
      setLog((prev) => [...prev, `[${getTimestamp()}] AI Response: ${responseText}`]);
      setInputText(responseText);
      
      console.log("🔥 Suggested response received! Automation enabled:", automationEnabled);
      autoSendResponse(responseText);
        
    } else if (data.type === 'wizard_response') {
      const responseText = data.data.text;
      setLog((prev) => [...prev, `[${getTimestamp()}] AI Response (Image): ${responseText}`]);
      setInputText(responseText);
      
      console.log("🔥 Wizard response received! Automation enabled:", automationEnabled);
      autoSendResponse(responseText);
        
    } else if (data.type === 'media_uploaded') {
      const { filename, source } = data;

      setUploadNotification(`Media uploaded: ${filename}`);
      setLatestUploadedFile(filename);

      if (source === 'temi') {
        setTemiFiles(s => {
          const next = new Set(s);
          next.add(filename);
          return next;
        });
      }

      if (source === 'wizard') {
        setWizardFiles(s => {
          const next = new Set(s);
          next.add(filename);
          return next;
        });
      }
    } else if (data.type === "saved_locations") {
      const locationList = data.data;
      setSavedLocations(locationList);
    }
  };

  useEffect(() => {
    console.log('trying')
    const ws = connectWebSocket(onWsMessage, "control");
    wsRef.current = ws;

    ws.onopen = () => {
      console.log("ws opened");
      ws.send(JSON.stringify({
        command: 'updateSettings',
        payload: { age: childAge, focus_area: focusArea }
      }));

      ws.send(JSON.stringify({
        command: "identify",
        payload: "wizard"
      }));

      setTimeout(() => {
        ws.send(JSON.stringify({
          command: "queryLocations"
        }));
      }, 100);
    };

    ws.onerror = (err) => {
      console.error("web socket error:", err);
    };

    ws.onclose = () => {
      console.log("WebSocket closed");
    };

    return () => ws.close();
  }, []);

  useGamepadControls(sendMessage, setPressedButtons);

  function sendGoTo(locationName) {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        command: "goTo",
        payload: locationName
      }));
    } else {
      console.warn("WebSocket is not open");
    }
  }

  const onChildAgeChange = e => {
    const age = Number(e.target.value);
    setChildAge(age);
    sendMessageWS({ command: 'updateSettings', payload: { age, focus_area: focusArea } });
  };


  const onFocusChange = e => {
    const focus = e.target.value;
    setFocusArea(focus);
    sendMessageWS({ command: 'updateSettings', payload: { age: childAge, focus_area: focus } });
  };

  return (
      <div className="container-fluid p-0" style={{ 
        height: '100vh', 
        position: 'relative',
        backgroundColor: '#f8f9fa'
      }}>
        <style>
          {`
            .media-list-container {
              height: 100% !important;
              min-height: 500px !important;
            }
            
            .media-list-container > * {
              height: 100% !important;
            }
            
            .media-grid, .uploaded-media {
              height: 100% !important;
              display: flex !important;
              flex-direction: column !important;
            }

            .btn-clean {
              border-radius: 8px;
              font-weight: 500;
              transition: all 0.2s ease;
              border: 1px solid;
            }

            .btn-clean:hover {
              transform: translateY(-1px);
              box-shadow: 0 4px 8px rgba(0,0,0,0.15);
            }

            .card-clean {
              border: none;
              border-radius: 12px;
              box-shadow: 0 2px 12px rgba(0,0,0,0.08);
            }

            .form-control-clean {
              border-radius: 8px;
              border: 1px solid #dee2e6;
              transition: border-color 0.2s ease, box-shadow 0.2s ease;
            }

            .form-control-clean:focus {
              border-color: #0d6efd;
              box-shadow: 0 0 0 0.2rem rgba(13, 110, 253, 0.15);
            }

            .log-area {
              background-color: #ffffff;
              border: 1px solid #e9ecef;
              border-radius: 10px;
            }

            .navbar-clean {
              box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            }

            .control-panel {
              background-color: #ffffff;
              border-top: 1px solid #dee2e6;
              box-shadow: 0 -2px 12px rgba(0,0,0,0.08);
            }
          `}
        </style>

        <nav className="navbar navbar-dark bg-dark navbar-clean fixed-top">
          <div className="d-flex justify-content-between align-items-center w-100 px-3">
            <span className="navbar-brand mb-0 h1" style={{ fontSize: '1.1rem', fontWeight: '600' }}>
              🤖 Wizard Control Dashboard
              {automationEnabled && (
                <span className="badge bg-success ms-2" style={{ fontSize: '0.9rem', borderRadius: '6px' }}>
                  {autoSendCountdown > 0 ? `AUTO ${autoSendCountdown}s` : 'AUTO ON'}
                </span>
              )}
              {autoSendCountdown > 0 && !automationEnabled && (
                <span className="badge bg-warning ms-2" style={{ fontSize: '0.9rem', borderRadius: '6px' }}>
                  COUNTDOWN {autoSendCountdown}s
                </span>
              )}
            </span>
            <button
              className="btn btn-clean btn-outline-light btn-sm"
              onClick={() => setShowControls(!showControls)}
            >
              {showControls ? "Hide Controls" : "Show Controls"}
            </button>
          </div>
        </nav>

        {uploadNotification && (
          <div
            className="alert alert-success position-fixed bottom-0 start-50 translate-middle-x mb-3"
            role="alert"
            style={{ 
              zIndex: 1050, 
              borderRadius: '10px', 
              border: 'none',
              boxShadow: '0 4px 12px rgba(40, 167, 69, 0.3)'
            }}
          >
            {uploadNotification}
          </div>
        )}

        <div 
          className="container-fluid main-content" 
          style={{ 
            marginTop: '70px', 
            height: 'calc(100vh - 70px)',
            paddingBottom: showControls ? '200px' : '20px',
            transition: 'padding-bottom 0.3s ease',
            padding: '0 15px'
          }}
        >
          <div className="row mb-3 gx-3 gy-2 align-items-end">
            <div className="col-auto d-flex align-items-center">
              <label 
                htmlFor="child-age" 
                className="form-label me-2" 
                style={{ fontSize: '0.9rem', fontWeight: 500 }}
              >
                Child’s age:
              </label>
              <select
                id="child-age"
                className="form-select form-control-clean"
                style={{ width: '6rem' }}
                value={childAge}
                onChange={onChildAgeChange}
              >
                {Array.from({ length: 18 }, (_, i) => i + 1).map(age => (
                  <option key={age} value={age}>{age}</option>
                ))}
              </select>
            </div>

            {/* Focus area */}
            <div className="col-auto d-flex flex-column">
              <label 
                htmlFor="focus-area" 
                className="form-label" 
                style={{ fontSize: '0.9rem', fontWeight: 500 }}
              >
                Focus area:
              </label>
              <select
                id="focus-area"
                className="form-select form-control-clean"
                value={focusArea}
                onChange={onFocusChange}
              >
                {focusChoices.map(opt => (
                  <option key={opt.value} value={opt.value}>
                    {opt.icon} {opt.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="row h-100">
            <div className="col-md-6 h-100 d-flex flex-column pe-3">
              <div className="card card-clean shadow-sm h-100 d-flex flex-column">
                <div className="card-header bg-primary text-white" style={{ borderRadius: '12px 12px 0 0' }}>
                  <h5 className="mb-0" style={{ fontWeight: '600', fontSize: '1.3rem'}}>Message Log & Control</h5>
                </div>
                <div className="card-body d-flex flex-column p-3" style={{ minHeight: 0, overflow: 'hidden' }}>
                  <div
                    className="log-area p-3 mb-3 position-relative flex-grow-1"
                    style={{ 
                      overflowY: "auto", 
                      fontSize: "0.95rem",
                      fontFamily: 'Monaco, "Lucida Console", monospace',
                      minHeight: "400px",
                      maxHeight: "none"
                    }}
                  >
                    {log.map((line, idx) => (
                      <div key={idx} style={{ marginBottom: '4px', lineHeight: '1.4' }}>
                        {line}
                      </div>
                    ))}
                    {log.length === 0 && (
                      <div className="text-muted text-center py-5">
                        No messages yet. Waiting for robot communication...
                      </div>
                    )}
                    <div ref={logEndRef} />
                  </div>

                  <div className="mt-auto">
                    <div className="d-flex gap-2 mb-2">
                      <button
                        className="btn btn-clean btn-outline-secondary btn-sm flex-fill"
                        onClick={() => {
                          const blob = new Blob([log.join("\n")], {
                            type: "text/plain;charset=utf-8",
                          });
                          const url = URL.createObjectURL(blob);
                          const link = document.createElement("a");
                          link.href = url;
                          link.download = `wizard-log-${new Date().toISOString()}.txt`;
                          link.click();
                          URL.revokeObjectURL(url);
                        }}
                      >
                        💾 Save Log
                      </button>

                      <button
                        className="btn btn-clean btn-outline-info btn-sm flex-fill"
                        onClick={() => {
                          if (window.confirm("Clear and refresh the message log?")) {
                            setLog([]);
                          }
                        }}
                      >
                        🔄 Clear Log
                      </button>
                    </div>

                    <div className="mb-2">
                      <select
                        className="form-select form-control-clean"
                        onChange={(e) => setInputText(e.target.value)}
                        value=""
                        style={{ fontSize: '0.95rem' }}
                      >
                        <option value="" disabled>
                          🎯 Pick a preset phrase...
                        </option>
                        {presetPhrases.map((phrase, index) => (
                          <option key={index} value={phrase}>
                            {phrase}
                          </option>
                        ))}
                      </select>
                    </div>

                    {activeMediaContext && (
                      <div
                        className="alert alert-info py-1 px-3 mb-2"
                        style={{
                          fontSize: "0.85rem",
                          borderLeft: "4px solid #0d6efd",
                          backgroundColor: "#f8f9fa",
                          margin: "0 0 8px 0",
                          borderRadius: '8px'
                        }}
                      >
                        📸 <strong>Topic:</strong> {activeMediaContext.filename} ({activeMediaContext.mode})
                      </div>
                    )}

                    {autoSendCountdown > 0 && (
                      <div className="alert alert-warning py-2 px-3 mb-2 text-center border-warning" 
                          style={{ 
                            backgroundColor: '#fff3cd',
                            borderWidth: '2px',
                            fontSize: '1.1rem',
                            fontWeight: 'bold',
                            borderRadius: '10px'
                          }}>
                        ⏰ AUTO-SENDING IN {autoSendCountdown} SECONDS...
                        <div className="small mt-1">Click "Speak" to cancel auto-send</div>
                      </div>
                    )}
                    <div className="input-group">
                      <textarea
                        rows={3}
                        className="form-control form-control-clean"
                        placeholder="Enter text for robot to speak..."
                        value={inputText}
                        onChange={(e) => setInputText(e.target.value)}
                        style={{ 
                          fontSize: '1.05rem',
                          lineHeight: '1.4',
                          resize: 'vertical'
                        }}
                      />
                      <div className="d-flex flex-column gap-2 ms-2">
                        <button
                          className="btn btn-clean btn-primary btn-lg"
                          disabled={!inputText.trim()}
                          onClick={() => {
                            const text = inputText.trim();
                            if (text) {
                              if (window.autoSendTimers) {
                                window.autoSendTimers.forEach(timer => clearTimeout(timer));
                                window.autoSendTimers = [];
                              }
                              setAutoSendCountdown(0);
                              
                              sendMessage({ command: "speak", payload: text });
                              setLog((prev) => [...prev, `[${getTimestamp()}] Sent: ${text}`]);
                              setInputText("");
                            }
                          }}
                          style={{ fontSize: '0.95rem', minWidth: '120px' }}
                        >
                          🔊 Speak
                        </button>
                        <button
                          className={`btn btn-clean btn-lg ${automationEnabled ? 'btn-danger' : 'btn-success'}`}
                          onClick={() => {
                            setAutomationEnabled(enabled => {
                              const next = !enabled;
                              console.log("Toggling automation from", enabled, "to", next);
                              
                              if (window.autoSendTimers) {
                                window.autoSendTimers.forEach(timer => clearTimeout(timer));
                                window.autoSendTimers = [];
                              }
                              setAutoSendCountdown(0);
                              
                              wsRef.current?.send(JSON.stringify({
                                command: next ? 'startAutomation' : 'stopAutomation',
                                payload: ""
                              }))
                              setLog((prev) => [...prev, `[${getTimestamp()}] Automation ${next ? 'ENABLED' : 'DISABLED'}`]);
                              return next;
                            })
                          }}
                          style={{ fontSize: '0.85rem', minWidth: '120px' }}
                        >
                          {automationEnabled ? '⏹️ Auto ON' : '▶️ Auto OFF'}
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div className="col-md-6 h-100 ps-3">
              <div className="card card-clean shadow-sm h-100 d-flex flex-column">
                <div className="card-header bg-success text-white" style={{ borderRadius: '12px 12px 0 0' }}>
                  <h5 className="mb-0" style={{ fontWeight: '600', fontSize: '1.3rem' }}>📁 Media Library</h5>
                </div>
                <div 
                  className="card-body p-1 d-flex flex-column" 
                  style={{ 
                    minHeight: 0,
                    height: 'calc(100vh - 200px)',
                    overflow: 'hidden'
                  }}
                >
                  <div 
                    className="media-list-container"
                    style={{ 
                      height: '100%',
                      width: '100%',
                      overflow: 'auto',
                      display: 'flex',
                      flexDirection: 'column'
                    }}
                  >
                    <MediaList
                      sendMessage={sendMessage}
                      newMediaFile={latestUploadedFile}
                      displayedMedia={displayedMedia}
                      handleSendToLLM={handleSendToLLM}
                      temiFiles={temiFiles}
                      className="h-100"
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div 
          className={`position-fixed bottom-0 start-0 end-0 control-panel ${
            showControls ? 'translate-y-0' : 'translate-y-100'
          }`}
          style={{ 
            transform: showControls ? 'translateY(0)' : 'translateY(100%)',
            transition: 'transform 0.3s ease',
            zIndex: 1000,
            maxHeight: '200px',
            overflowY: 'auto'
          }}
        >
          <div className="container-fluid py-3">
            <div className="row g-2">
              <div className="col-md-4">
                <h6 className="text-muted mb-2" style={{ fontSize: '0.85rem', fontWeight: '600' }}>🧭 Navigation</h6>
                <div className="d-flex flex-wrap gap-1 mb-2">
                  {savedLocations.map((loc) => (
                    <button
                      key={loc}
                      onClick={() => sendGoTo(loc)}
                      className="btn btn-clean btn-outline-primary btn-sm"
                      style={{ fontSize: '0.8rem', padding: '4px 8px' }}
                    >
                      📍 {loc}
                    </button>
                  ))}
                  {savedLocations.length === 0 && (
                    <button
                      className="btn btn-clean btn-outline-warning btn-sm"
                      onClick={() =>
                        sendMessage({ command: "queryLocations", payload: "" })
                      }
                      style={{ fontSize: '0.8rem' }}
                    >
                      🔄 Get Locations
                    </button>
                  )}
                </div>
              </div>

              <div className="col-md-4">
                <h6 className="text-muted mb-2" style={{ fontSize: '0.85rem', fontWeight: '600' }}>🎮 Movement</h6>
                <div className="row g-1">
                  <div className="col-3">
                    <button
                      className={`btn btn-clean btn-sm w-100 ${
                        pressedButtons.includes(14) ? "btn-success" : "btn-outline-primary"
                      }`}
                      onClick={() => sendMessage({ command: "turnBy", payload: "10" })}
                      style={{ fontSize: '0.75rem', padding: '6px 4px' }}
                    >
                      ⬅️
                    </button>
                  </div>
                  <div className="col-3">
                    <button
                      className={`btn btn-clean btn-sm w-100 ${
                        pressedButtons.includes(12) ? "btn-success" : "btn-outline-primary"
                      }`}
                      onClick={() => sendMessage({ command: "skidJoy", payload: "(0.5, 0)" })}
                      style={{ fontSize: '0.75rem', padding: '6px 4px' }}
                    >
                      ⬆️
                    </button>
                  </div>
                  <div className="col-3">
                    <button
                      className={`btn btn-clean btn-sm w-100 ${
                        pressedButtons.includes(13) ? "btn-success" : "btn-outline-primary"
                      }`}
                      onClick={() => sendMessage({ command: "skidJoy", payload: "(-0.5, 0)" })}
                      style={{ fontSize: '0.75rem', padding: '6px 4px' }}
                    >
                      ⬇️
                    </button>
                  </div>
                  <div className="col-3">
                    <button
                      className={`btn btn-clean btn-sm w-100 ${
                        pressedButtons.includes(15) ? "btn-success" : "btn-outline-primary"
                      }`}
                      onClick={() => sendMessage({ command: "turnBy", payload: "-10" })}
                      style={{ fontSize: '0.75rem', padding: '6px 4px' }}
                    >
                      ➡️
                    </button>
                  </div>
                </div>
                <div className="row g-1 mt-1">
                  <div className="col-3">
                    <button
                      className="btn btn-clean btn-outline-primary btn-sm w-100"
                      onClick={() => sendMessage({ command: "tiltBy", payload: "5" })}
                      style={{ fontSize: '0.7rem', padding: '4px 2px' }}
                    >
                      👆
                    </button>
                  </div>
                  <div className="col-3">
                    <button
                      className="btn btn-clean btn-outline-primary btn-sm w-100"
                      onClick={() => sendMessage({ command: "tiltBy", payload: "-5" })}
                      style={{ fontSize: '0.7rem', padding: '4px 2px' }}
                    >
                      👇
                    </button>
                  </div>
                  <div className="col-3">
                    <button
                      className="btn btn-clean btn-outline-primary btn-sm w-100"
                      onClick={() => sendMessage({ command: "tiltAngle", payload: "0" })}
                      style={{ fontSize: '0.7rem', padding: '4px 2px' }}
                    >
                      👀
                    </button>
                  </div>
                  <div className="col-3">
                    <button
                      className="btn btn-clean btn-danger btn-sm w-100"
                      onClick={() => sendMessage({ command: "stopMovement", payload: "" })}
                      style={{ fontSize: '0.7rem', padding: '4px 2px' }}
                    >
                      🛑
                    </button>
                  </div>
                </div>
              </div>

              <div className="col-md-4">
                <h6 className="text-muted mb-2" style={{ fontSize: '0.85rem', fontWeight: '600' }}>📱 Screen & Media</h6>
                <div className="row g-1">
                  <div className="col-6">
                    <button
                      className="btn btn-clean btn-outline-primary btn-sm w-100"
                      onClick={() => sendMessage({ command: "navigateCamera", payload: "" })}
                      style={{ fontSize: '0.8rem', padding: '6px 8px' }}
                    >
                      📷 Camera
                    </button>
                  </div>
                  <div className="col-6">
                    <button
                      className="btn btn-clean btn-outline-primary btn-sm w-100"
                      onClick={() => sendMessage({ command: "displayFace", payload: "" })}
                      style={{ fontSize: '0.8rem', padding: '6px 8px' }}
                    >
                      😊 Face
                    </button>
                  </div>
                </div>
                <div className="row g-1 mt-1">
                  <div className="col-4">
                    <button
                      className="btn btn-clean btn-outline-success btn-sm w-100"
                      disabled={isRecording}
                      onClick={() => {
                        const customName = window.prompt("Enter a name for the picture:");
                        sendMessage({ command: "takePicture", payload: customName || "" });
                      }}
                      style={{ fontSize: '0.75rem', padding: '6px 4px' }}
                    >
                      📸 Pic
                    </button>
                  </div>
                  <div className="col-4">
                    <button
                      className="btn btn-clean btn-outline-danger btn-sm w-100"
                      disabled={isRecording}
                      onClick={() => {
                        sendMessage({ command: "startVideo", payload: "" });
                        setIsRecording(true);
                      }}
                      style={{ fontSize: '0.75rem', padding: '6px 4px' }}
                    >
                      🎥 ▶️
                    </button>
                  </div>
                  <div className="col-4">
                    <button
                      className="btn btn-clean btn-danger btn-sm w-100"
                      disabled={!isRecording}
                      onClick={() => {
                        sendMessage({ command: "stopVideo", payload: "" });
                        setIsRecording(false);
                      }}
                      style={{ fontSize: '0.75rem', padding: '6px 4px' }}
                    >
                      ⏹️ Stop
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
  );
};

export default WizardPage;