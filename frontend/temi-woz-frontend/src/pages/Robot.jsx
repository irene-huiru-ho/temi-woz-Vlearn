// src/pages/ParticipantPage.jsx
import React, { useEffect, useState } from 'react'
import uitoolkit from "@zoom/videosdk-ui-toolkit";
import "@zoom/videosdk-ui-toolkit/dist/videosdk-ui-toolkit.css";

import { connectWebSocket, sendMessageWS } from "../utils/ws";




const RobotPage = () => {

  // const [showZoomUI, setShowZoomUI] = useState(false);


  // const sendMessage = (message) => {
  //   sendMessageWS(message);
  // };

  // useEffect(() => {
  //   const onWsMessage = (data) => {
  //     console.log('onWsMessage')
  //     console.log(data)
  //     if (data.type === "media_uploaded") {
  //       const msg = `✅ Media uploaded: ${data.filename}`;
  //       // setUploadNotification(msg);
  //       // setLatestUploadedFile(data.filename); 
  //       // setTimeout(() => setUploadNotification(null), 3000);
  //     }
  //   }
  //   connectWebSocket(onWsMessage, "participant");
  // }, []);


  // console.log(import.meta.env.VITE_ZOOM_JWT)

  var config = {
    videoSDKJWT: import.meta.env.VITE_ZOOM_JWT,
    sessionName: "research-study",
    userName: "Robot",
    featuresOptions: [
      'video',
      'audio',
    ]
  };


  const startVideoCall = () => {
    // setShowZoomUI(true)
    const sessionContainer = document.getElementById('sessionContainer');
    uitoolkit.joinSession(sessionContainer, config);
    const sessionDestroyed = () => {
      console.log("sessionDestroyed")
      uitoolkit.destroy();
      // setShowZoomUI(false)
    }
    uitoolkit.onSessionDestroyed(sessionDestroyed);
  }

  return (
    <div className="container-fluid p-0">
      <nav className="navbar navbar-dark bg-dark fixed-top">
        <span className="navbar-brand mb-0 h1">🤖 Robot Zoom</span>
      </nav>

      <div className="container-fluid main-content mt-5 pt-2">
        <div className="row">


          {/* Video Panel */}
          <div className="col-md-12">
            <h4>Video Panel</h4>
            <button
                onClick={() => {
                  startVideoCall()
                }}
                className="btn btn-primary">
              Start Video Call
            </button>
            <div
              id="sessionContainer"
              style={{
                height: '70vh',
                // display: showZoomUI ? 'block' : 'none'
              }}
            ></div>
          </div>
        </div>

      </div>
    </div>
  );
};

export default RobotPage;
