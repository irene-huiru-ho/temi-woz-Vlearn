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

  // Simulated User Input State
  const [simulatedUserInput, setSimulatedUserInput] = useState("");

  // Perception and Image State
  const [latestImage, setLatestImage] = useState("");
  const [livePerception, setLivePerception] = useState({ image: null, detections: [] });
  const [isPerceptionActive, setIsPerceptionActive] = useState(false);
  const [scanTarget, setScanTarget] = useState("none");
  const isPerceptionActiveRef = useRef(false);

  useEffect(() => {
    isPerceptionActiveRef.current = isPerceptionActive;
  }, [isPerceptionActive]);

  // Session management state
  const [sessionInfo, setSessionInfo] = useState({ active: false });
  const [familyIdInput, setFamilyIdInput] = useState("");
  const [sessionStartTime, setSessionStartTime] = useState(null);
  const [showSessionPanel, setShowSessionPanel] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Prompt configuration state
  const [childAge, setChildAge] = useState(5);
  const [conversationFocus, setConversationFocus] = useState('Fictional/Creative');
  const [safetyRiskLevel, setSafetyRiskLevel] = useState('Low');
  const [customMessage, setCustomMessage] = useState('');
  const [showConfig, setShowConfig] = useState(false);
  const [isUpdatingConfig, setIsUpdatingConfig] = useState(false);
  const [continuePreviousTopic, setContinuePreviousTopic] = useState(false);

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

  // Send Simulated User Input Function
  const sendSimulatedUserInput = () => {
    const text = simulatedUserInput.trim();
    if (!text) return;

    // Log the simulated input in the message log
    setLog((prev) => [...prev, `[${getTimestamp()}] 🎭 Simulated User Input: ${text}`]);

    // Send the simulated input to the backend via WebSocket
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        command: "simulateUserInput",
        payload: text,
        continue_previous_topic: continuePreviousTopic
      }));
    } else {
      setLog((prev) => [...prev, `[${getTimestamp()}] ❌ WebSocket not connected - cannot send simulated input`]);
    }

    // Clear the input field
    setSimulatedUserInput("");
  };

  // Session management functions
  const refreshSessionStatus = async (isManual = false) => {
    if (isManual) setIsRefreshing(true);

    try {
      const response = await fetch('http://localhost:8000/api/session/status');
      const data = await response.json();
      setSessionInfo(data);

      if (data.active && !sessionStartTime) {
        setSessionStartTime(new Date(data.start_time));
      } else if (!data.active) {
        setSessionStartTime(null);
      }

      if (isManual) {
        setLog(prev => [...prev, `[${getTimestamp()}] 🔄 Status refreshed: ${data.active ? `${data.family_id} (${data.message_count} msgs)` : 'No active session'}`]);
      }

    } catch (error) {
      console.error('Error fetching session status:', error);
      if (isManual) {
        setLog(prev => [...prev, `[${getTimestamp()}] ❌ Failed to refresh status: ${error.message}`]);
      }
    } finally {
      if (isManual) setIsRefreshing(false);
    }
  };

  const startFamilySession = async () => {
    const familyId = familyIdInput.trim() || `Family_${new Date().getHours()}${new Date().getMinutes()}`;

    try {
      const response = await fetch('http://localhost:8000/api/session/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          family_id: familyId,
          child_age: childAge,
          conversation_focus: conversationFocus,
          safety_risk_level: safetyRiskLevel,
          custom_message: customMessage.trim()
        })
      });

      const data = await response.json();
      if (data.status === 'success') {
        setLog(prev => [...prev, `[${getTimestamp()}] 🟢 SESSION STARTED: ${data.family_id} (Age: ${childAge}, Focus: ${conversationFocus})`]);
        setSessionStartTime(new Date());
        setFamilyIdInput("");

        setSessionInfo({
          active: true,
          session_id: data.session_id,
          family_id: data.family_id,
          child_age: childAge,
          conversation_focus: conversationFocus,
          safety_risk_level: safetyRiskLevel,
          custom_message: customMessage.trim(),
          message_count: 0,
          start_time: new Date().toISOString()
        });

        setTimeout(() => refreshSessionStatus(), 500);
      } else {
        setLog(prev => [...prev, `[${getTimestamp()}] ❌ Failed to start session: ${data.message}`]);
      }
    } catch (error) {
      setLog(prev => [...prev, `[${getTimestamp()}] ❌ Error starting session: ${error.message}`]);
    }
  };

  const endFamilySession = async () => {
    if (!window.confirm('End the current family session? This will save all conversation data and reset for the next family.')) {
      return;
    }

    try {
      const response = await fetch('http://localhost:8000/api/session/end', { method: 'POST' });
      const data = await response.json();

      if (data.status === 'success') {
        setLog(prev => [...prev, `[${getTimestamp()}] 🔴 SESSION ENDED & SAVED: ${data.filepath}`]);

        const logContent = log.join("\n");
        const logBlob = new Blob([logContent], { type: "text/plain;charset=utf-8" });
        const logUrl = URL.createObjectURL(logBlob);
        const logLink = document.createElement("a");
        logLink.href = logUrl;

        const familyId = sessionInfo.family_id || 'unknown_family';
        logLink.download = `wizard-log-${familyId}-${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.txt`;
        logLink.click();
        URL.revokeObjectURL(logUrl);

        setTimeout(() => {
          setLog([]);
          localStorage.removeItem("wizardMessageLog");
        }, 2000);

        setSessionStartTime(null);
        refreshSessionStatus();

        if (data.filepath) {
          const filename = data.filepath.split('/').pop();
          setTimeout(() => {
            window.open(`http://localhost:8000/api/session/download-file/${filename}`);
          }, 500);
        }
      } else {
        setLog(prev => [...prev, `[${getTimestamp()}] ❌ Failed to end session: ${data.message}`]);
      }
    } catch (error) {
      setLog(prev => [...prev, `[${getTimestamp()}] ❌ Error ending session: ${error.message}`]);
    }
  };

  const downloadCurrentSession = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/session/download', { method: 'POST' });
      const data = await response.json();

      if (data.status === 'success') {
        setLog(prev => [...prev, `[${getTimestamp()}] 💾 Session downloaded: ${data.filepath}`]);
        const filename = data.filepath.split('/').pop();
        window.open(`http://localhost:8000/api/session/download-file/${filename}`);
      } else {
        setLog(prev => [...prev, `[${getTimestamp()}] ❌ Download failed: ${data.message}`]);
      }
    } catch (error) {
      setLog(prev => [...prev, `[${getTimestamp()}] ❌ Download error: ${error.message}`]);
    }
  };

  const updateSessionConfig = async () => {
    if (!sessionInfo.active) return;

    setIsUpdatingConfig(true);
    try {
      const response = await fetch('http://localhost:8000/api/session/update-config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          child_age: childAge,
          conversation_focus: conversationFocus,
          safety_risk_level: safetyRiskLevel,
          custom_message: customMessage.trim()
        })
      });

      const data = await response.json();
      if (data.status === 'success') {
        const changes = [];
        if (sessionInfo.child_age !== childAge) changes.push(`Age ${sessionInfo.child_age}→${childAge}`);
        if (sessionInfo.conversation_focus !== conversationFocus) changes.push(`Focus ${sessionInfo.conversation_focus}→${conversationFocus}`);
        if (sessionInfo.safety_risk_level !== safetyRiskLevel) changes.push(`Risk ${sessionInfo.safety_risk_level}→${safetyRiskLevel}`);
        if (sessionInfo.custom_message !== customMessage.trim()) changes.push(`Notes updated`);

        setLog(prev => [...prev, `[${getTimestamp()}] 🔧 CONFIG UPDATED: ${changes.join(', ')}`]);

        setSessionInfo(prev => ({
          ...prev,
          child_age: childAge,
          conversation_focus: conversationFocus,
          safety_risk_level: safetyRiskLevel,
          custom_message: customMessage.trim()
        }));

        setTimeout(() => refreshSessionStatus(), 300);
      } else {
        setLog(prev => [...prev, `[${getTimestamp()}] ❌ Failed to update config: ${data.message}`]);
      }
    } catch (error) {
      setLog(prev => [...prev, `[${getTimestamp()}] ❌ Error updating config: ${error.message}`]);
    } finally {
      setIsUpdatingConfig(false);
    }
  };

  const getSessionDuration = () => {
    if (!sessionStartTime) return "--";
    const duration = Math.round((new Date() - sessionStartTime) / 60000);
    return `${duration} min`;
  };

  const focusAreas = [
    'Fictional/Creative',
    'Factual/Knowledge',
    // 'Open-ended',
    // 'Literacy and Communication',
    // 'STEM',
    // 'Creativity',
    // 'Emotional Intelligence',
    // 'Physical Development',
    // 'Social Skills',
    // 'History',
  ];

  const focusDescriptions = {
    'Fictional/Creative': 'Imagination, storytelling, pretend play, creative scenarios',
    'Factual/Knowledge': 'Real-world facts, science, history, how things work',
    // 'Open-ended': 'Mix of age-appropriate topics',
    // 'Literacy and Communication': 'Words, letters, reading, writing, expressing ideas',
    // 'STEM': 'Counting, how things work, building, scientific thinking',
    // 'Creativity': 'Imagination, art, creative expression, design thinking',
    // 'Emotional Intelligence': 'Feelings, emotions, character emotions',
    // 'Physical Development': 'Movement, coordination, sports, healthy habits',
    // 'Social Skills': 'Friendship, cooperation, sharing, community relationships',
    // 'History': 'Historical facts and knowledge',
  };

  const toggleFocusMode = async () => {
    const next = conversationFocus === 'Fictional/Creative' ? 'Factual/Knowledge' : 'Fictional/Creative';
    setConversationFocus(next);
    if (!sessionInfo.active) return;
    try {
      const response = await fetch('http://localhost:8000/api/session/update-config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          child_age: childAge,
          conversation_focus: next,
          safety_risk_level: safetyRiskLevel,
          custom_message: customMessage.trim()
        })
      });
      const data = await response.json();
      if (data.status === 'success') {
        setSessionInfo(prev => ({ ...prev, conversation_focus: next }));
        setLog(prev => [...prev, `[${getTimestamp()}] 🔀 FOCUS SWITCHED: ${conversationFocus} → ${next}`]);
      }
    } catch (error) {
      setLog(prev => [...prev, `[${getTimestamp()}] ❌ Focus switch failed: ${error.message}`]);
    }
  };

  useEffect(() => {
    refreshSessionStatus();
    const interval = setInterval(refreshSessionStatus, 10000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (sessionInfo.active) {
      if (sessionInfo.child_age !== undefined) setChildAge(sessionInfo.child_age);
      if (sessionInfo.conversation_focus) setConversationFocus(sessionInfo.conversation_focus);
      if (sessionInfo.safety_risk_level) setSafetyRiskLevel(sessionInfo.safety_risk_level);
      if (sessionInfo.custom_message !== undefined) setCustomMessage(sessionInfo.custom_message || '');
    }
  }, [sessionInfo]);

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
        sendMessage({
          command: "speak",
          payload: responseText,
          continue_previous_topic: continuePreviousTopic
        });
        setLog((prev) => [...prev, `[${getTimestamp()}] ✅ AUTO-SENT: ${responseText} ${continuePreviousTopic ? '(Continue topic)' : '(New focus)'}`]);
        setInputText("");
      }, 3000);

      window.autoSendTimers = [timer1, timer2, timer3];
    } else {
      console.log("🔥 Auto-send skipped - automation disabled or empty text");
    }
  };

  const handleSetLatestImage = (filename) => {
    sendMessage({ command: "setLatestImage", payload: filename });
    setLatestImage(filename);
  };

  const handleSendToLLM = async (imageFilename, mode) => {
    setActiveMediaContext({ filename: imageFilename, mode });
    setLog((prev) => [
      ...prev,
      `[${getTimestamp()}] ${mode === "conversation" ? "Started conversation" : "Suggested response"
      } for "${imageFilename}" ${continuePreviousTopic ? '(Continue topic)' : '(New focus)'}`,
    ]);

    const requestData = {
      image_filename: imageFilename,
      mode: mode || "default",
      continue_previous_topic: continuePreviousTopic,
    };

    console.log("Sending to /api/analyze-media:", requestData);

    try {
      setLog((prev) => [...prev, `[${getTimestamp()}] 🔄 Sending image to AI for analysis...`]);

      const res = await fetch("http://localhost:8000/api/analyze-media", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestData),
      });

      console.log("Response status:", res.status, res.statusText);

      if (!res.ok) {
        let errorMessage = `Server error: ${res.status} ${res.statusText}`;

        try {
          const errorData = await res.json();
          errorMessage += ` - ${errorData.message || errorData.error || 'Unknown error'}`;
          console.log("Error response data:", errorData);
        } catch (parseError) {
          console.log("Could not parse error response as JSON");
          try {
            const errorText = await res.text();
            if (errorText) {
              errorMessage += ` - ${errorText.substring(0, 100)}`;
              console.log("Error response text:", errorText);
            }
          } catch (textError) {
            console.log("Could not get error response text");
          }
        }

        throw new Error(errorMessage);
      }

      const data = await res.json();
      console.log("Success response data:", data);

      const llmOutput = data.analysis || "No response from LLM";
      setLlmResponse(llmOutput);
      setInputText(llmOutput);

      setLog((prev) => [...prev, `[${getTimestamp()}] ✅ AI analysis completed successfully`]);

    } catch (error) {
      console.error("Error in handleSendToLLM:", error);

      let userMessage = "Error contacting LLM: ";

      if (error.message.includes('fetch')) {
        userMessage += "Cannot connect to server. Check if backend is running.";
        setLog((prev) => [...prev, `[${getTimestamp()}] ❌ Connection Error: Backend server may be down`]);
      } else if (error.message.includes('500')) {
        userMessage += "Server internal error. Check backend logs for details.";
        setLog((prev) => [...prev, `[${getTimestamp()}] ❌ Server Error (500): ${error.message}`]);
      } else if (error.message.includes('404')) {
        userMessage += "API endpoint not found. Check backend implementation.";
        setLog((prev) => [...prev, `[${getTimestamp()}] ❌ API Not Found (404): Check backend routes`]);
      } else if (error.message.includes('timeout')) {
        userMessage += "Request timed out. LLM processing may be slow.";
        setLog((prev) => [...prev, `[${getTimestamp()}] ❌ Timeout Error: LLM processing took too long`]);
      } else {
        userMessage += error.message;
        setLog((prev) => [...prev, `[${getTimestamp()}] ❌ Unexpected Error: ${error.message}`]);
      }

      setLlmResponse(userMessage);
      setInputText("");

      setLog((prev) => [...prev, `[${getTimestamp()}] 🔍 Debug Info: Image="${imageFilename}", Mode="${mode}", ContinueTopic=${continuePreviousTopic}`]);
      setLog((prev) => [...prev, `[${getTimestamp()}] 💡 Troubleshooting: Check backend server, API implementation, and LLM configuration`]);
    }
  };

  const sendMessage = (message) => {
    sendMessageWS(message);
    if (message.command === "displayMedia") {
      setLatestImage(message.payload);
      setDisplayedMedia(message.payload);
      setIsPerceptionActive(false);
      setLivePerception({ image: null, detections: [] });
    } else if (message.command === "displayFace") {
      setDisplayedMedia(null);
      setIsPerceptionActive(false);
      setLivePerception({ image: null, detections: [] });
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

    if (data.type === 'session_started') {
      setLog((prev) => [...prev, `[${getTimestamp()}] 🟢 New session started: ${data.family_id}`]);
      refreshSessionStatus();
    } else if (data.type === 'session_ended') {
      setLog((prev) => [...prev, `[${getTimestamp()}] 🔴 Session ended: ${data.filepath}`]);
      refreshSessionStatus();
    } else if (data.type === 'asr_result') {
      setLog((prev) => [...prev, `[${getTimestamp()}] Received: ${data.data}`]);
    } else if (data.type === 'assistant_response') {
      setLog((prev) => [...prev, `[${getTimestamp()}] Temi: ${data.data}`]);
    } else if (data.type === 'suggested_response') {
      const responseText = data.data;
      setLog((prev) => [...prev, `[${getTimestamp()}] AI Response: ${responseText}`]);
      setInputText(responseText);

      console.log("Suggested response received! Automation enabled:", automationEnabled);
      autoSendResponse(responseText);

    } else if (data.type === 'wizard_response') {
      const responseText = data.data.text;
      setLog((prev) => [...prev, `[${getTimestamp()}] AI Response (Image): ${responseText}`]);
      setInputText(responseText);

      console.log("Wizard response received! Automation enabled:", automationEnabled);
      autoSendResponse(responseText);

    } else if (data.type === 'media_uploaded') {
      const { filename, source, is_live_capture } = data;

      setUploadNotification(`Media uploaded: ${filename}`);
      setTimeout(() => {
        setUploadNotification(null);
      }, 3000);
      setLatestUploadedFile(filename);
      setLatestImage(filename);

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

      if (is_live_capture) {
        handleSendToLLM(filename, "conversation");
      }
    } else if (data.type === "saved_locations") {
      const locationList = data.data;
      setSavedLocations(locationList);
    }
    // NEW: Handle latest image updates
    else if (data.type === 'picture_taken') {
      console.log('🔍 FRONTEND: picture_taken event received:', data);
      const filename = data.data?.filename;
      if (filename) {
        console.log('🔍 FRONTEND: Setting latest image to:', filename);
        setLatestImage(filename);
        setLog((prev) => [...prev, `[${getTimestamp()}] 📸 Latest image updated: ${filename}`]);
      }
    } else if (data.type === 'initial_status') {
      console.log('🔍 FRONTEND: initial_status event received:', data);
      // Handle initial status when wizard connects
      const statusData = data.data;

      if (statusData.last_displayed) {
        // Extract filename from path if it's a full path
        const filename = typeof statusData.last_displayed === 'string'
          ? statusData.last_displayed.split('/').pop()
          : statusData.last_displayed;

        console.log('🔍 FRONTEND: Setting latest image from initial_status to:', filename);
        setLatestImage(filename);
      }

      if (statusData.auto_scan_target) {
        setScanTarget(statusData.auto_scan_target);
      } else if (statusData.book_scanning_enabled) {
        setScanTarget("book");
      }
    } else if (data.type === 'scan_target_status') {
      const target = data.data?.target || "none";
      setScanTarget(target);
      setLog((prev) => [...prev, `[${getTimestamp()}] 🎯 Auto scan target set to: ${target.toUpperCase()}`]);
    } else if (data.type === 'book_scanning_status') {
      const enabled = data.data?.enabled;
      setScanTarget(enabled ? "book" : "none");
      setLog((prev) => [...prev, `[${getTimestamp()}] 📖 Book scanning ${enabled ? 'ENABLED' : 'DISABLED'}`]);
    } else if (data.type === 'perception_update') {
      if (isPerceptionActiveRef.current) {
        setLivePerception({
          image: data.data.image,
          detections: data.data.detections
        });
      }
    }
  };

  useEffect(() => {
    console.log('trying')
    const ws = connectWebSocket(onWsMessage, "control");
    wsRef.current = ws;

    ws.onopen = () => {
      console.log("ws opened");

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

  return (
    <div className="container-fluid p-0" style={{
      height: '100vh',
      overflow: 'hidden',
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

          .session-status-active {
            background-color: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
          }

          .session-status-inactive {
            background-color: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
          }

          .simulated-input-field {
            background-color: #f8f9fa;
            border-color: #6c757d;
          }

          .simulated-input-field:focus {
            border-color: #fd7e14;
            box-shadow: 0 0 0 0.2rem rgba(253, 126, 20, 0.15);
          }

          .listen-controls {
            background-color: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 8px;
          }

          .latest-image-display {
            font-size: 0.8rem;
            color: #6c757d;
            background-color: #e9ecef;
            padding: 4px 8px;
            border-radius: 4px;
            font-family: monospace;
          }
        `}
      </style>

      <nav className="navbar navbar-dark bg-dark navbar-clean fixed-top">
        <div className="d-flex justify-content-between align-items-center w-100 px-3">
          <span className="navbar-brand mb-0 h1" style={{ fontSize: '1.1rem', fontWeight: '600' }}>
            🤖 Wizard Control Dashboard
            {sessionInfo.active && (
              <span className="badge bg-success ms-2" style={{ fontSize: '0.8rem', borderRadius: '6px' }}>
                {sessionInfo.family_id} • Age {sessionInfo.child_age || childAge} • {conversationFocus} • {getSessionDuration()} • {sessionInfo.message_count} msgs
              </span>
            )}
            {automationEnabled && (
              <span className="badge bg-info ms-2" style={{ fontSize: '0.9rem', borderRadius: '6px' }}>
                {autoSendCountdown > 0 ? `AUTO ${autoSendCountdown}s` : 'AUTO ON'}
              </span>
            )}
            {autoSendCountdown > 0 && !automationEnabled && (
              <span className="badge bg-warning ms-2" style={{ fontSize: '0.9rem', borderRadius: '6px' }}>
                COUNTDOWN {autoSendCountdown}s
              </span>
            )}
          </span>
          <div className="d-flex gap-2 align-items-center">
            <button
              className="btn btn-clean btn-outline-light btn-sm"
              onClick={() => setShowSessionPanel(!showSessionPanel)}
            >
              {showSessionPanel ? "Hide Session" : "Show Session"}
            </button>
            <button
              className="btn btn-clean btn-outline-light btn-sm"
              onClick={() => setShowControls(!showControls)}
            >
              {showControls ? "Hide Controls" : "Show Controls"}
            </button>
          </div>
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

      {showSessionPanel && (
        <div
          className="position-fixed"
          style={{
            top: '70px',
            right: '15px',
            width: '320px',
            zIndex: 1040,
            maxHeight: showControls ? 'calc(100vh - 260px)' : 'calc(100vh - 100px)',
            overflowY: 'auto',
            bottom: showControls ? '190px' : '20px',
            transition: 'all 0.3s ease'
          }}
        >
          <div className="card card-clean shadow">
            <div className="card-header bg-warning text-dark" style={{ borderRadius: '12px 12px 0 0' }}>
              <h6 className="mb-0" style={{ fontWeight: '600' }}>📊 Research Session Control</h6>
            </div>
            <div className="card-body p-3" style={{
              maxHeight: showControls ? 'calc(100vh - 310px)' : 'calc(100vh - 160px)',
              overflowY: 'auto'
            }}>
              <div
                className={`p-2 mb-3 rounded ${sessionInfo.active ? 'session-status-active' : 'session-status-inactive'}`}
                style={{ fontSize: '0.9rem', fontWeight: '600' }}
              >
                {sessionInfo.active ? '🟢 ACTIVE SESSION' : '🔴 NO ACTIVE SESSION'}
              </div>

              <div className="mb-3">
                <div className="d-flex justify-content-between align-items-center mb-2">
                  <h6 className="mb-0" style={{ fontSize: '0.9rem', fontWeight: '600' }}>
                    ⚙️ {sessionInfo.active ? 'Update Configuration' : 'Configuration'}
                  </h6>
                  <button
                    className="btn btn-clean btn-outline-secondary btn-sm"
                    onClick={() => setShowConfig(!showConfig)}
                    style={{ fontSize: '0.7rem', padding: '2px 6px' }}
                  >
                    {showConfig ? 'Hide' : 'Show'}
                  </button>
                </div>

                {showConfig && (
                  <div className="border rounded p-2" style={{ fontSize: '0.8rem' }}>
                    <div className="mb-2">
                      <label className="form-label mb-1" style={{ fontSize: '0.75rem', fontWeight: '600' }}>
                        Child Age:
                      </label>
                      <div className="input-group input-group-sm">
                        <button
                          className="btn btn-outline-secondary"
                          type="button"
                          onClick={() => setChildAge(Math.max(1, childAge - 1))}
                          disabled={isUpdatingConfig || childAge <= 1}
                          style={{ fontSize: '0.8rem', padding: '4px 8px' }}
                        >
                          −
                        </button>
                        <input
                          type="number"
                          className="form-control text-center"
                          value={childAge}
                          onChange={(e) => {
                            const age = parseInt(e.target.value) || 1;
                            if (age >= 1 && age <= 20) {
                              setChildAge(age);
                            }
                          }}
                          min="1"
                          max="15"
                          disabled={isUpdatingConfig}
                          style={{ fontSize: '0.8rem', maxWidth: '60px' }}
                        />
                        <button
                          className="btn btn-outline-secondary"
                          type="button"
                          onClick={() => setChildAge(Math.min(15, childAge + 1))}
                          disabled={isUpdatingConfig || childAge >= 15}
                          style={{ fontSize: '0.8rem', padding: '4px 8px' }}
                        >
                          +
                        </button>
                      </div>
                      <div className="text-muted" style={{ fontSize: '0.65rem' }}>
                        Age range: 1-15 years
                      </div>
                    </div>

                    <div className="mb-2">
                      <label className="form-label mb-1" style={{ fontSize: '0.75rem', fontWeight: '600' }}>
                        Conversation Focus:
                      </label>
                      <select
                        className="form-select form-select-sm"
                        value={conversationFocus}
                        onChange={(e) => setConversationFocus(e.target.value)}
                        style={{ fontSize: '0.75rem' }}
                        disabled={isUpdatingConfig}
                      >
                        {focusAreas.map(area => (
                          <option key={area} value={area}>{area}</option>
                        ))}
                      </select>
                      <div className="text-muted mt-1" style={{ fontSize: '0.65rem', lineHeight: '1.2' }}>
                        {focusDescriptions[conversationFocus]}
                      </div>
                    </div>

                    <div className="mb-2">
                      <label className="form-label mb-1" style={{ fontSize: '0.75rem', fontWeight: '600' }}>
                        Safety Risk Level:
                      </label>
                      <select
                        className="form-select form-select-sm"
                        value={safetyRiskLevel}
                        onChange={(e) => setSafetyRiskLevel(e.target.value)}
                        style={{ fontSize: '0.75rem' }}
                        disabled={isUpdatingConfig}
                      >
                        <option value="Low">Low Risk</option>
                        <option value="High">High Risk</option>
                      </select>
                    </div>

                    <div className="mb-2">
                      <label className="form-label mb-1" style={{ fontSize: '0.75rem', fontWeight: '600' }}>
                        Custom Notes (optional):
                      </label>
                      <textarea
                        className="form-control form-control-sm"
                        placeholder="Add family-specific context..."
                        value={customMessage}
                        onChange={(e) => setCustomMessage(e.target.value)}
                        rows={2}
                        style={{ fontSize: '0.7rem' }}
                        disabled={isUpdatingConfig}
                      />
                    </div>

                    <div className="mb-2">
                      <label className="form-label mb-1" style={{ fontSize: '0.75rem', fontWeight: '600' }}>
                        Conversation Mode:
                      </label>
                      <div
                        className="p-2"
                        style={{
                          backgroundColor: '#f8f9fa',
                          borderRadius: '4px',
                          border: '1px solid #dee2e6',
                          fontSize: '0.75rem'
                        }}
                      >
                        <div className="form-check mb-0">
                          <input
                            className="form-check-input"
                            type="checkbox"
                            id="continueTopicToggle"
                            checked={continuePreviousTopic}
                            onChange={(e) => setContinuePreviousTopic(e.target.checked)}
                            disabled={isUpdatingConfig}
                          />
                          <label
                            className="form-check-label"
                            htmlFor="continueTopicToggle"
                            style={{ fontSize: '0.75rem', fontWeight: '500' }}
                          >
                            📜 Continue previous topic
                          </label>
                          <div
                            className="text-muted mt-1"
                            style={{
                              fontSize: '0.65rem',
                              lineHeight: '1.2',
                              paddingLeft: '24px'
                            }}
                          >
                            {continuePreviousTopic ? "Build on conversation history" : "Prioritize current input/image"}
                          </div>
                        </div>
                      </div>
                    </div>

                    {sessionInfo.active ? (
                      <button
                        className="btn btn-clean btn-warning btn-sm w-100"
                        onClick={updateSessionConfig}
                        disabled={isUpdatingConfig}
                        style={{ fontSize: '0.75rem' }}
                      >
                        {isUpdatingConfig ? '🔧 Updating...' : '🔧 Update Configuration'}
                      </button>
                    ) : (
                      <div className="text-muted text-center" style={{ fontSize: '0.7rem', padding: '8px' }}>
                        Start session to apply configuration
                      </div>
                    )}
                  </div>
                )}
              </div>

              {sessionInfo.active ? (
                <div className="mb-3">
                  <div className="mb-2" style={{ fontSize: '0.85rem' }}>
                    <strong>Family:</strong> {sessionInfo.family_id}<br />
                    <strong>Duration:</strong> {getSessionDuration()}<br />
                    <strong>Messages:</strong> {sessionInfo.message_count}<br />
                    <strong>Age:</strong> {sessionInfo.child_age || childAge}<br />
                    <strong>Focus:</strong> {sessionInfo.conversation_focus || conversationFocus}<br />
                    <strong>Risk:</strong> {sessionInfo.safety_risk_level || safetyRiskLevel}
                  </div>
                  <div className="d-flex gap-2">
                    <button
                      className="btn btn-clean btn-danger btn-sm flex-fill"
                      onClick={endFamilySession}
                      style={{ fontSize: '0.8rem' }}
                    >
                      🔴 End
                    </button>
                    <button
                      className="btn btn-clean btn-outline-primary btn-sm flex-fill"
                      onClick={downloadCurrentSession}
                      style={{ fontSize: '0.8rem' }}
                    >
                      💾 Save
                    </button>
                  </div>
                </div>
              ) : (
                <div>
                  <div className="mb-2">
                    <input
                      type="text"
                      className="form-control form-control-clean form-control-sm"
                      placeholder="Family ID (e.g., F01, F02)"
                      value={familyIdInput}
                      onChange={(e) => setFamilyIdInput(e.target.value)}
                      style={{ fontSize: '0.85rem' }}
                    />
                  </div>
                  <button
                    className="btn btn-clean btn-success btn-sm w-100"
                    onClick={startFamilySession}
                    style={{ fontSize: '0.85rem' }}
                  >
                    🟢 Start New Family Session
                  </button>
                </div>
              )}

              <hr className="my-2" />
              <button
                className="btn btn-clean btn-outline-secondary btn-sm w-100"
                onClick={() => refreshSessionStatus(true)}
                disabled={isRefreshing}
                style={{ fontSize: '0.8rem' }}
              >
                {isRefreshing ? '🔄 Refreshing...' : '🔄 Refresh Status'}
              </button>
            </div>
          </div>
        </div>
      )}

      <div
        className="container-fluid main-content"
        style={{
          marginTop: '70px',
          height: 'calc(100vh - 70px)',
          paddingTop: '0',
          paddingBottom: showControls ? '200px' : '20px',
          paddingLeft: '15px',
          paddingRight: showSessionPanel ? '350px' : '15px',
          transition: 'padding-bottom 0.3s ease'
        }}
      >
        <div className="row h-100">
          <div className="col-md-6 h-100 d-flex flex-column pe-3">
            <div className="card card-clean shadow-sm h-100 d-flex flex-column">
              <div className="card-header bg-primary text-white" style={{ borderRadius: '12px 12px 0 0' }}>
                <h5 className="mb-0" style={{ fontWeight: '600', fontSize: '1.3rem' }}>Message Log & Control</h5>
              </div>
              <div className="card-body d-flex flex-column p-3" style={{ minHeight: 0, overflow: 'hidden' }}>
                <div
                  className="log-area p-3 mb-3 position-relative"
                  style={{
                    overflowY: "auto",
                    fontSize: "0.95rem",
                    fontFamily: 'Monaco, "Lucida Console", monospace',
                    minHeight: "200px",
                    maxHeight: showControls ? "calc(100vh - 550px)" : "calc(100vh - 380px)",
                    flex: "1 1 auto"
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

                <div style={{ flexShrink: 0 }}>
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

                  {/* NEW: Listen Controls Section */}
                  <div className="mb-2 listen-controls p-2">
                    <div className="d-flex align-items-center gap-2">
                      <button
                        className="btn btn-clean btn-outline-info btn-sm"
                        onClick={() => sendMessage({ command: "listenNoImage", payload: "" })}
                        style={{ fontSize: '0.8rem', padding: '4px 12px' }}
                      >
                        🎧 Listen
                      </button>
                      <button
                        className="btn btn-clean btn-outline-success btn-sm"
                        onClick={() => sendMessage({ command: "listenImage", payload: "" })}
                        style={{ fontSize: '0.8rem', padding: '4px 12px' }}
                      >
                        🎧📷 Listen_image
                      </button>
                      <span className="text-muted ms-3" style={{ fontSize: '0.75rem', fontWeight: '500' }}>
                        Latest Image:
                      </span>
                      <div className="latest-image-display" key={latestImage}>
                        {latestImage || 'None'}
                      </div>
                    </div>
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

                  <div className="mb-3">
                    <label className="form-label text-muted mb-2" style={{ fontSize: '0.9rem', fontWeight: '600' }}>
                      🔊 Robot Speech Output (review/edit AI responses)
                    </label>
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
                          className={`btn btn-clean btn-lg fw-semibold ${conversationFocus === 'Fictional/Creative' ? 'btn-warning' : 'btn-info'}`}
                          onClick={toggleFocusMode}
                          title={`Switch to ${conversationFocus === 'Fictional/Creative' ? 'Factual/Knowledge' : 'Fictional/Creative'}`}
                          style={{ fontSize: '0.8rem', minWidth: '120px' }}
                        >
                          {conversationFocus === 'Fictional/Creative' ? '✨ Fictional' : '📚 Factual'} ⇄
                        </button>
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

                              sendMessage({
                                command: "speak",
                                payload: text,
                                continue_previous_topic: continuePreviousTopic
                              });
                              setLog((prev) => [...prev, `[${getTimestamp()}] Sent: ${text} ${continuePreviousTopic ? '(Continue topic)' : '(New focus)'}`]);
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

                  <div className="mb-2">
                    <label className="form-label text-muted mb-2" style={{ fontSize: '0.9rem', fontWeight: '600' }}>
                      🎭 Simulate User Input (triggers AI response)
                    </label>
                    <div className="input-group">
                      <textarea
                        rows={2}
                        className="form-control form-control-clean simulated-input-field"
                        placeholder="Type what a user might say to trigger Temi's response..."
                        value={simulatedUserInput}
                        onChange={(e) => setSimulatedUserInput(e.target.value)}
                        style={{
                          fontSize: '1.0rem',
                          lineHeight: '1.4',
                          resize: 'vertical'
                        }}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' && !e.shiftKey) {
                            e.preventDefault();
                            sendSimulatedUserInput();
                          }
                        }}
                      />
                      <button
                        className="btn btn-clean btn-outline-warning"
                        disabled={!simulatedUserInput.trim()}
                        onClick={sendSimulatedUserInput}
                        style={{ fontSize: '0.9rem', minWidth: '100px' }}
                      >
                        🎭 Simulate
                      </button>
                    </div>
                    <div className="text-muted mt-1" style={{ fontSize: '0.8rem' }}>
                      This simulates a user speaking to Temi and will generate an AI response in the field above
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="col-md-6 h-100 ps-3 d-flex flex-column gap-3">
            {/* Live Perception Panel */}
            <div className="card card-clean shadow-sm" style={{ flex: '0 0 auto', maxHeight: '40%' }}>
              <div className="card-header bg-info text-white d-flex justify-content-between align-items-center" style={{ borderRadius: '12px 12px 0 0', padding: '0.5rem 1rem' }}>
                <h6 className="mb-0" style={{ fontWeight: '600', fontSize: '1.1rem' }}>👁️ Live Perception (Temi View)</h6>
                <div className="d-flex gap-2 align-items-center">
                  <button
                    className="btn btn-sm btn-light"
                    disabled={!livePerception.image}
                    onClick={() => {
                      const customName = window.prompt("Enter a name for the captured frame:");
                      if (customName === null) return; // User cancelled
                      sendMessage({ command: "captureLiveFrame", payload: customName.trim() });
                    }}
                    style={{ fontSize: '0.8rem', fontWeight: '500', padding: '2px 8px' }}
                  >
                    📸 Capture Frame
                  </button>
                </div>
              </div>
              <div className="card-body p-2 d-flex gap-2" style={{ overflow: 'hidden' }}>
                <div style={{ flex: '1', backgroundColor: '#000', borderRadius: '8px', overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  {livePerception.image ? (
                    <img src={livePerception.image} alt="Live feed" style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }} />
                  ) : (
                    <span className="text-muted small">No live feed</span>
                  )}
                </div>
                <div style={{ width: '150px', overflowY: 'auto', borderLeft: '1px solid #dee2e6', paddingLeft: '8px' }}>
                  <h6 className="small text-muted mb-1">Detections:</h6>
                  {livePerception.detections && livePerception.detections.length > 0 ? (
                    livePerception.detections.map((d, i) => (
                      <div key={i} className="badge bg-secondary mb-1 w-100 text-start text-truncate" title={`${d.class} (${Math.round(d.confidence * 100)}%)`}>
                        {d.class} {Math.round(d.confidence * 100)}%
                      </div>
                    ))
                  ) : (
                    <div className="small text-muted">None</div>
                  )}
                </div>
              </div>
            </div>

            <div className="card card-clean shadow-sm d-flex flex-column" style={{ flex: '1 1 auto', minHeight: 0 }}>
              <div className="card-header bg-success text-white" style={{ borderRadius: '12px 12px 0 0' }}>
                <h5 className="mb-0" style={{ fontWeight: '600', fontSize: '1.3rem' }}>📁 Media Library</h5>
              </div>
              <div
                className="card-body p-1 d-flex flex-column"
                style={{
                  minHeight: 0,
                  height: '100%',
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
                    handleSetLatestImage={handleSetLatestImage}
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
        className={`position-fixed bottom-0 start-0 end-0 control-panel ${showControls ? 'translate-y-0' : 'translate-y-100'
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
                    className={`btn btn-clean btn-sm w-100 ${pressedButtons.includes(14) ? "btn-success" : "btn-outline-primary"
                      }`}
                    onClick={() => sendMessage({ command: "turnBy", payload: "10" })}
                    style={{ fontSize: '0.75rem', padding: '6px 4px' }}
                  >
                    ⬅️ Left
                  </button>
                </div>
                <div className="col-3">
                  <button
                    className={`btn btn-clean btn-sm w-100 ${pressedButtons.includes(12) ? "btn-success" : "btn-outline-primary"
                      }`}
                    onClick={() => sendMessage({ command: "skidJoy", payload: "(0.5, 0)" })}
                    style={{ fontSize: '0.75rem', padding: '6px 4px' }}
                  >
                    ⬆️ Forward
                  </button>
                </div>
                <div className="col-3">
                  <button
                    className={`btn btn-clean btn-sm w-100 ${pressedButtons.includes(13) ? "btn-success" : "btn-outline-primary"
                      }`}
                    onClick={() => sendMessage({ command: "skidJoy", payload: "(-0.5, 0)" })}
                    style={{ fontSize: '0.75rem', padding: '6px 4px' }}
                  >
                    ⬇️ Backward
                  </button>
                </div>
                <div className="col-3">
                  <button
                    className={`btn btn-clean btn-sm w-100 ${pressedButtons.includes(15) ? "btn-success" : "btn-outline-primary"
                      }`}
                    onClick={() => sendMessage({ command: "turnBy", payload: "-10" })}
                    style={{ fontSize: '0.75rem', padding: '6px 4px' }}
                  >
                    ➡️ Right
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
                    👆 Tilt Up
                  </button>
                </div>
                <div className="col-3">
                  <button
                    className="btn btn-clean btn-outline-primary btn-sm w-100"
                    onClick={() => sendMessage({ command: "tiltBy", payload: "-5" })}
                    style={{ fontSize: '0.7rem', padding: '4px 2px' }}
                  >
                    👇 Tilt Down
                  </button>
                </div>
                <div className="col-3">
                  <button
                    className="btn btn-clean btn-outline-primary btn-sm w-100"
                    onClick={() => sendMessage({ command: "tiltAngle", payload: "0" })}
                    style={{ fontSize: '0.7rem', padding: '4px 2px' }}
                  >
                    👀 Look Ahead
                  </button>
                </div>
                <div className="col-3">
                  <button
                    className="btn btn-clean btn-danger btn-sm w-100"
                    onClick={() => sendMessage({ command: "stopMovement", payload: "" })}
                    style={{ fontSize: '0.7rem', padding: '4px 2px' }}
                  >
                    🛑 Stop
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
                    📷 Show Camera
                  </button>
                </div>

                <div className="col-6">
                  <button
                    className="btn btn-clean btn-outline-primary btn-sm w-100"
                    onClick={() => sendMessage({ command: "displayFace", payload: "" })}
                    style={{ fontSize: '0.8rem', padding: '6px 8px' }}
                  >
                    😊 Show Face
                  </button>
                </div>

              </div>

              <div className="row g-1 mt-1">
                <div className="col-6">
                  <button
                    className={`btn btn-clean btn-sm w-100 ${isPerceptionActive ? 'btn-danger' : 'btn-outline-info'}`}
                    onClick={() => {
                      const nextState = !isPerceptionActive;
                      setIsPerceptionActive(nextState);
                      sendMessage({ command: "togglePerception", payload: nextState ? "on" : "off" });
                      if (!nextState) {
                        setLivePerception({ image: null, detections: [] });
                      }
                    }}
                    style={{ fontSize: '0.8rem', padding: '6px 8px' }}
                  >
                    {isPerceptionActive ? '👁️ Stop Perception' : '👁️ Start Live Perception'}
                  </button>
                </div>
                <div className="col-6">
                  <div className="input-group input-group-sm">
                    <span className="input-group-text bg-light text-dark" style={{ fontSize: '0.75rem', fontWeight: '600' }}>🎯 Target</span>
                    <select
                      className="form-select form-select-sm"
                      value={scanTarget}
                      onChange={(e) => {
                        const target = e.target.value;
                        setScanTarget(target);
                        sendMessage({ command: "setScanTarget", payload: target });
                      }}
                      style={{ fontSize: '0.8rem', backgroundColor: scanTarget !== 'none' ? '#ffc107' : '#ffffff', color: scanTarget !== 'none' ? '#000000' : '#212529', fontWeight: scanTarget !== 'none' ? 'bold' : 'normal' }}
                    >
                      <option value="none">Off (Disabled)</option>
                      <option value="book">📖 Book</option>
                      <option value="laptop">💻 Laptop</option>
                      <option value="bottle">🍾 Bottle</option>
                      <option value="person">👤 Person</option>
                    </select>
                  </div>
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
                      setTimeout(() => {
                        sendMessage({ command: "displayFace", payload: "" });
                      }, 10000);
                    }}
                    style={{ fontSize: '0.75rem', padding: '6px 4px' }}
                  >
                    📸 Take Pic
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
                    🎥 Start Video
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
                    ⏹️ Stop Video
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