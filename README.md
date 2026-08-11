This will start out as a standalone web & websocket-server (fastAPI) & react frontend project,
where the WS acts as a bridge between the Temi robot and the frontend wizard controller.

At some point, we may integrate a variation of this websocket server into the ROS system,
and use it to create a more autonomous interaction flow.

This code is also dependent on a compatible Temi app (with WS client built-in) installed on Temi.


Here are some points related to woz app development:
- Uses Yolo for live image detection
- Uses Google ai api for image analysis (this occurs immediately after Frame Capture using the same prompt as the “start conversation” option in the media library)
- All perception related code (websocket_server.py, perception_model.py) uses python
- Wizard control panel uses .jsx
- Saving locations gives a voiced notification by default, I had tried to turn off the speech (part that makes it say “I saved [image name] location”) but this appears to be built in

Updates on the wizard control:
- There is a live perception panel added above the Media library; the live feed can be activated using the “start live perception” button. 
- Detections List lists the items detected and the percentage detection
- Perception boxes and percentages can be altered in “websocket_server.py” along with other live perception-related functions.
- “🎯 Target” dropdown menu can be altered to have different targets in the menu, but they should look for an object, and once located, move to the target until it can’t go any further and then take a picture. This only happens once, so it does not keep repetitively attempting this task. I still haven't managed to get this to switch fully at times (changing from laptop to book doesn’t get it to stop, but changing the target to “none” (default) gets it to stop, same as pressing “stop” to cancel. also there is an issue in that the woz requires a browser refresh to get the temi to repeat the process again). In terms of next steps for this project, it is recommended to fix this by using a reset button to reset/refresh the targetting, so when the task of taking an image is done, the dropdown and the targeting should reset to none. 
- after taking a picture, the image of the target is added to media library and a location is added
- “Capture Frame” takes a picture of the current frame, and automatically analyzes it in the same nature of “Start conversation”. I had attempted to make this also mark location, but have it commented out for now, as it continues to announce that it has saved the picture location.