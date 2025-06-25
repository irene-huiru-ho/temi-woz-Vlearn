import { useEffect, useState } from "react";
import { connectWebSocket, sendMessageWS } from "../utils/ws";
import MediaList from "../components/MediaList";
import { useGamepadControls } from "../utils/useGamepadControls";
import presetPhrases from "../utils/presetPhrases";
import LLMPanel from "../components/LLMPanel";

const WizardPage = () => {
  const [log, setLog] = useState([]);
  const [inputText, setInputText] = useState("");
  const [pressedButtons, setPressedButtons] = useState([]);
  const [screenshotData, setScreenshotData] = useState(null);
  const [isRecording, setIsRecording] = useState(false);
  const [savedLocations, setSavedLocations] = useState([]);
  const [behaviorMode, setBehaviorMode] = useState(null);
  const [uploadNotification, setUploadNotification] = useState(null);
  const [latestUploadedFile, setLatestUploadedFile] = useState(null);
  const [displayedMedia, setDisplayedMedia] = useState(null);
  const [llmResponse, setLlmResponse] = useState("");

  const handleSendToLLM = async (imageFilename) => {
    try {
      const res = await fetch("http://localhost:8000/api/analyze-media", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ image_filename: imageFilename }),
      });
      const data = await res.json();
      setLlmResponse(data.analysis || "No response from LLM");
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
    const onWsMessage = (data) => {
      console.log("onWsMessage");
      console.log(data);
      if (data.type === "asr_result") {
        setLog((prev) => [...prev, `Received: ${data.data}`]);
      } else if (data.type === "suggested_response") {
        setInputText(data.data);
      } else if (data.type === "initial_status") {
        setBehaviorMode(data.data.behavior_mode);
        setDisplayedMedia(data.data.last_displayed);
      } else if (data.type === "behavior_mode") {
        setBehaviorMode(data.data);
      } else if (data.type === "media_uploaded") {
        const msg = `✅ Media uploaded: ${data.filename}`;
        setUploadNotification(msg);
        setLatestUploadedFile(data.filename);
        setTimeout(() => setUploadNotification(null), 3000);
      } else if (data.type === "saved_locations") {
        const locationList = data.data;
        setSavedLocations(locationList);
      } else if (data.type === "screenshot") {
        setScreenshotData(`data:image/jpeg;base64,${data.data}`);
      }
    };
    connectWebSocket(onWsMessage, "control");
  }, []);

  useGamepadControls(sendMessage, setPressedButtons);

  function chunkArray(arr, chunkSize) {
    return Array.from({ length: Math.ceil(arr.length / chunkSize) }, (_, i) =>
      arr.slice(i * chunkSize, i * chunkSize + chunkSize)
    );
  }

  const navButtonsBlock = () => {
    if (savedLocations.length === 0) {
      return (
        <div className="row my-2">
          <div className="col-sm-6">
            <button
              className="btn btn-warning w-100"
              onClick={() =>
                sendMessage({ command: "queryLocations", payload: "" })
              }
            >
              Get Locations
            </button>
          </div>
        </div>
      );
    }

    const buttonChunks = chunkArray(savedLocations, 3);
    return (
      <div>
        {buttonChunks.map((row, rowIndex) => (
          <div className="row mb-2" key={rowIndex}>
            {row.map((loc, colIndex) => (
              <div className="col-sm-4" key={colIndex}>
                <button
                  className="btn btn-primary w-100"
                  onClick={() => sendMessage({ command: "goTo", payload: loc })}
                >
                  {loc}
                </button>
              </div>
            ))}
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className="container-fluid p-0">
      <nav className="navbar navbar-dark bg-dark fixed-top">
        <span className="navbar-brand mb-0 h1">
          🤖 Wizard Control Dashboard
        </span>
      </nav>

      {uploadNotification && (
        <div
          className="alert alert-success position-fixed bottom-0 start-50 translate-middle-x mb-3 shadow"
          role="alert"
          style={{ zIndex: 1050 }}
        >
          {uploadNotification}
        </div>
      )}

      <div className="container-fluid main-content mt-5 pt-2">
        <div className="row">
          {/* Control Panel */}
          <div className="col-md-5">
            <h4>Message Log</h4>
            <div
              className="border bg-light p-2"
              style={{ height: "400px", overflowY: "auto", fontSize: "0.9rem" }}
            >
              {log.map((line, idx) => (
                <div key={idx}>{line}</div>
              ))}
            </div>

            <div className="mb-2">
              <select
                className="form-select"
                onChange={(e) => setInputText(e.target.value)}
                value=""
              >
                <option value="" disabled>
                  Pick a phrase...
                </option>
                {presetPhrases.map((phrase, index) => (
                  <option key={index} value={phrase}>
                    {phrase}
                  </option>
                ))}
              </select>
            </div>

            <div className="input-group mt-2">
              <textarea
                rows={3}
                className="form-control"
                placeholder="Enter text for robot to speak..."
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
              />
              <button
                className="btn btn-primary"
                disabled={!inputText.trim()}
                onClick={() => {
                  if (inputText.trim() !== "") {
                    sendMessage({
                      command: "speak",
                      payload: inputText.trim(),
                    });
                    setLog((prev) => [...prev, `Sent: ${inputText.trim()}`]);
                    setInputText(""); // Clear input
                  }
                }}
              >
                💬 Play on Robot
              </button>
            </div>
          </div>

          <div className="col-md-7">
            <div className="row">
              <div className="col-md-7">
                <h4>Behavioral Modes</h4>
                <div className="alert alert-info mt-2">
                  🤖 Current Behavior Mode:{" "}
                  <strong>{behaviorMode || " --- "}</strong>
                </div>

                <div className="row mt-2">
                  <div className="col-sm-4">
                    <button
                      className="btn w-100 btn-warning"
                      onClick={() =>
                        sendMessage({
                          command: "changeMode",
                          payload: "passive",
                        })
                      }
                    >
                      Passive
                    </button>
                  </div>
                  <div className="col-sm-4">
                    <button
                      className="btn w-100 btn-warning"
                      onClick={() =>
                        sendMessage({
                          command: "changeMode",
                          payload: "reactive",
                        })
                      }
                    >
                      Reactive
                    </button>
                  </div>
                  <div className="col-sm-4">
                    <button
                      className="btn w-100 btn-warning"
                      onClick={() =>
                        sendMessage({
                          command: "changeMode",
                          payload: "proactive",
                        })
                      }
                    >
                      Proactive
                    </button>
                  </div>
                </div>
              </div>

              <div className="col-md-5">
                <h4>Screenshot</h4>
                {screenshotData && (
                  <div className="mt-3">
                    <img
                      src={screenshotData}
                      alt="Robot Screenshot"
                      style={{
                        width: "100%",
                        maxWidth: "500px",
                        border: "1px solid #ccc",
                      }}
                    />
                  </div>
                )}
                <button
                  className="btn w-100 btn-success"
                  onClick={() => {
                    setScreenshotData(null);
                    sendMessage({
                      command: "refreshScreenShot",
                      payload: "",
                    });
                  }}
                >
                  {screenshotData ? "Refresh" : "Fetch"}
                </button>
              </div>
            </div>

            <h4 className="mt-2">Go To ...</h4>
            {navButtonsBlock()}

            <h4 className="mt-2">Movements</h4>
            <div className="row mt-2">
              <div className="col-sm-3">
                <button
                  className={`btn w-100 ${
                    pressedButtons.includes(14) ? "btn-success" : "btn-primary"
                  }`}
                  onClick={() =>
                    sendMessage({
                      command: "turnBy",
                      payload: "10",
                    })
                  }
                >
                  Left
                </button>
              </div>
              <div className="col-sm-3">
                <button
                  className={`btn w-100 ${
                    pressedButtons.includes(15) ? "btn-success" : "btn-primary"
                  }`}
                  onClick={() =>
                    sendMessage({
                      command: "turnBy",
                      payload: "-10",
                    })
                  }
                >
                  Right
                </button>
              </div>
              <div className="col-sm-3">
                <button
                  className={`btn w-100 ${
                    pressedButtons.includes(12) ? "btn-success" : "btn-primary"
                  }`}
                  onClick={() =>
                    sendMessage({
                      command: "skidJoy",
                      payload: "(0.5, 0)",
                    })
                  }
                >
                  Forward
                </button>
              </div>
              <div className="col-sm-3">
                <button
                  className={`btn w-100 ${
                    pressedButtons.includes(13) ? "btn-success" : "btn-primary"
                  }`}
                  onClick={() =>
                    sendMessage({
                      command: "skidJoy",
                      payload: "(-0.5, 0)",
                    })
                  }
                >
                  Back
                </button>
              </div>
            </div>

            <div className="row mt-2">
              <div className="col-sm-3">
                <button
                  className="btn w-100 btn-primary"
                  onClick={() =>
                    sendMessage({
                      command: "tiltBy",
                      payload: "5",
                    })
                  }
                >
                  Up
                </button>
              </div>
              <div className="col-sm-3">
                <button
                  className="btn w-100 btn-primary"
                  onClick={() =>
                    sendMessage({
                      command: "tiltBy",
                      payload: "-5",
                    })
                  }
                >
                  Down
                </button>
              </div>
              <div className="col-sm-3">
                <button
                  className="btn w-100 btn-primary"
                  onClick={() =>
                    sendMessage({
                      command: "tiltAngle",
                      payload: "0",
                    })
                  }
                >
                  👀 ahead
                </button>
              </div>
              <div className="col-sm-3">
                <button
                  className="btn w-100 btn-danger"
                  onClick={() =>
                    sendMessage({
                      command: "stopMovement",
                      payload: "",
                    })
                  }
                >
                  STOP
                </button>
              </div>
            </div>

            <h4 className="mt-2">Screen</h4>
            <div className="row mt-2">
              <div className="col-sm-6">
                <button
                  className="btn w-100 btn-primary"
                  onClick={() =>
                    sendMessage({
                      command: "navigateCamera",
                      payload: "",
                    })
                  }
                >
                  {behaviorMode === "passive"
                    ? "Activate Camera"
                    : "Display Camera"}
                </button>
              </div>
              <div className="col-sm-6">
                <button
                  className="btn w-100 btn-primary"
                  onClick={() =>
                    sendMessage({
                      command: "displayFace",
                      payload: "",
                    })
                  }
                >
                  Display Face
                </button>
              </div>
            </div>

            <div className="row mt-2">
              <div className="col-sm-4">
                <button
                  className="btn w-100 btn-primary"
                  disabled={isRecording}
                  onClick={() =>
                    sendMessage({
                      command: "takePicture",
                      payload: "",
                    })
                  }
                >
                  Take Picture
                </button>
              </div>
              <div className="col-sm-4">
                <button
                  className="btn w-100 btn-primary"
                  disabled={isRecording}
                  onClick={() => {
                    sendMessage({
                      command: "startVideo",
                      payload: "",
                    });
                    setIsRecording(true);
                  }}
                >
                  Start Video
                </button>
              </div>
              <div className="col-sm-4">
                <button
                  className="btn w-100 btn-primary"
                  disabled={!isRecording}
                  onClick={() => {
                    sendMessage({
                      command: "stopVideo",
                      payload: "",
                    });
                    setIsRecording(false);
                  }}
                >
                  Stop Video
                </button>
              </div>
            </div>
          </div>
        </div>
        <div className="row" style={{ height: "80vh" }}>
          <div
            className="col-md-6"
            style={{
              flex: 1,
              borderRight: "1px solid #ccc",
              overflowY: "auto",
              height: "100%",
            }}
          >
            <MediaList
              sendMessage={sendMessage}
              newMediaFile={latestUploadedFile}
              displayedMedia={displayedMedia}
              handleSendToLLM={handleSendToLLM}
            />
          </div>

          <div className="col-md-6">
            <LLMPanel response={llmResponse} />
          </div>
        </div>
      </div>
    </div>
  );
};

export default WizardPage;
