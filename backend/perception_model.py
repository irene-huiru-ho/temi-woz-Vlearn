import cv2
import numpy as np
import base64
from ultralytics import YOLO

class PerceptionModel:
    def __init__(self, model_path="yolov8n.pt", conf_threshold=0.30, target_classes=None):
       
        
        self.model = YOLO(model_path)
        self.conf_threshold = conf_threshold
        self.target_classes = target_classes
        if self.target_classes:
            self.target_classes = [c.lower() for c in self.target_classes]

    def process_frame(self, base64_frame):

        #Processes base64 encoded image frame, runs inference, and returns the annotated frame and detections.

        if base64_frame.startswith('data:image'):
            base64_frame = base64_frame.split(',')[1]
            
        img_data = base64.b64decode(base64_frame)
        np_arr = np.frombuffer(img_data, np.uint8)
        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        if frame is None:
            return None, []

        # Run inference
        results = self.model.predict(source=frame, conf=self.conf_threshold, verbose=False)
        
        detections = []
        annotated_frame = frame.copy()

        if len(results) > 0:
            result = results[0]
            boxes = result.boxes
            h, w, _ = frame.shape
            
            for box in boxes:
                cls_id = int(box.cls[0].item())
                conf = float(box.conf[0].item())
                class_name = result.names[cls_id]
                
                #test this line: maybe we dont need to filter the objects, just get whatever I think (Result: functions but so laggy)
                if self.target_classes and class_name.lower() not in self.target_classes:
                        continue
                    
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())

                detections.append({
                    "class": class_name,
                    "confidence": conf,
                    "box": [x1, y1, x2, y2],
                    "rel_box": [x1 / w, y1 / h, x2 / w, y2 / h]
                })

                cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                label = f"{class_name} {conf:.2f}"
                cv2.putText(annotated_frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        # Encode back to base64
        _, buffer = cv2.imencode('.jpg', annotated_frame)
        encoded_image = base64.b64encode(buffer).decode('utf-8')
        out_base64 = f"data:image/jpeg;base64,{encoded_image}"
        
        return out_base64, detections
