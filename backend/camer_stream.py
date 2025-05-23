import io, threading, time, cv2
from PIL import Image
from flask import Response, current_app

class Camera:
    def __init__(self, width=640, height=480, fps=15):
        import picamera2                  # Bookworm용
        self.picam = picamera2.Picamera2()
        self.picam.configure(
            self.picam.create_video_configuration(
                main={"size": (width, height)},
                controls={"FrameRate": fps}
            )
        )
        self.picam.start()
        self.frame = None
        self.running = True
        threading.Thread(target=self._update, daemon=True).start()

    def _update(self):
        while self.running:
            arr = self.picam.capture_array("main")
            # BGR(OpenCV) → JPG
            ret, jpg = cv2.imencode(".jpg", arr, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if ret:
                self.frame = jpg.tobytes()
            time.sleep(0)

    def get_generator(self):
        boundary = b'--frame'
        while True:
            if self.frame:
                yield boundary + b'\r\n'
                yield b'Content-Type: image/jpeg\r\n\r\n' + self.frame + b'\r\n'
            time.sleep(1 / 15)            # fps 와 동일

camera_singleton = Camera()
def mjpeg_feed():
    return Response(
        camera_singleton.get_generator(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )
