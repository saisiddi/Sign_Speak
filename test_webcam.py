"""
SignSpeak - Webcam Sanity Check
================================
Run this FIRST to verify your camera is working.
  python test_webcam.py

Shows a live window. Press Q to quit.
If no window appears, change CAMERA_ID to 1 or 2.
"""

import cv2

CAMERA_ID = 0   # Try 1 or 2 if this doesn't work

cap = cv2.VideoCapture(CAMERA_ID, cv2.CAP_DSHOW)
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
for _ in range(5): cap.read()
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

if not cap.isOpened():
    print(f"ERROR: Camera {CAMERA_ID} not found.")
    print("Try: CAMERA_ID = 1 or CAMERA_ID = 2")
    exit(1)

print(f"Camera {CAMERA_ID} opened OK!")
print(f"Resolution: {int(cap.get(3))}x{int(cap.get(4))}")
print("Showing feed... Press Q to quit.")

while True:
    ret, frame = cap.read()
    if not ret:
        print("ERROR: Cannot read frame.")
        break
    frame = cv2.flip(frame, 1)
    cv2.putText(frame, "Camera OK! Press Q to quit.", (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 230, 100), 2)
    cv2.imshow("Webcam Test", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
print("All good. Run: python backend/detector.py")
