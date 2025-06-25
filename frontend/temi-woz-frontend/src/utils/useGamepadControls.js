import { useEffect } from "react";

export function useGamepadControls(sendMessage, setPressedButtons) {
  useEffect(() => {
    let prevTimestamps = [];

    const logGamepadState = () => {
      const gamepads = navigator.getGamepads ? navigator.getGamepads() : [];
      for (let i = 0; i < gamepads.length; i++) {
        const gamepad = gamepads[i];
        if (gamepad) {

          if (prevTimestamps[i] !== gamepad.timestamp) {
            // Check for D-pad button presses
            const dpadMap = {
              12: "up",
              13: "down",
              14: "left",
              15: "right",
            };


            const pressed = [];

            gamepad.buttons.forEach((button, index) => {
              if (button.pressed) {
                if (dpadMap[index]) {
                  sendMessage({
                    command: "move",
                    payload: dpadMap[index]
                  });
                }
                pressed.push(index);
              }
            });

            setPressedButtons?.(pressed);
            prevTimestamps[i] = gamepad.timestamp;
          }
        }
      }
      requestAnimationFrame(logGamepadState);
    };

    logGamepadState();
  }, [sendMessage, setPressedButtons]);
}
