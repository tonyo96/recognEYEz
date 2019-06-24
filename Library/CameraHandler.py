from pathlib import Path
import logging
import threading
import datetime
import cv2
from Library.Handler import Handler


class CameraHandler(Handler):
    resolutions = {"vga": [640, 480], "qvga": [320, 240], "qqvga": [
        160, 120], "hd": [1280, 720], "fhd": [1920, 1080]}
    def __init__(self, app):
        super().__init__(app)
        # loads video with OpenCV
        self.cam_is_running = False
        self.cam_is_processing = False
        self.start_cam()
        logging.info("Camera opened")

    def camera_start_processing(self):
        logging.info("The facehandler object: {}".format(self.app.fh))
        if self.app.fh and self.cam_is_running and not self.cam_is_processing:
            self.cam_is_processing = True
            self.app.fh.running_since = datetime.datetime.now()
            if self.app.camera_thread == None:
                self.app.camera_thread = threading.Thread(
                    target=self.camera_process, daemon=True, args=(self.app,))
                self.app.camera_thread.start()
            logging.info("Camera started")
        logging.info("Camera scanning started")

    def camera_stop_processing(self):
        if self.app.fh and self.cam_is_running and self.cam_is_processing:
            self.cam_is_processing = False
            self.app.preview_image = cv2.imread(
                os.path.join("Static", "empty_pic.png"))

        logging.info("Camera scanning stopped")

    def camera_process(self):
        """
        Continously calls the process_next_frame() method to process frames from the camera
        self.app_cont: used to access the main self.application instance from blueprints
        """
        ticker = 0
        error_count = 0
        while self.cam_is_running:
            try:
                if ticker > int(self.app.sh.get_face_rec_settings()["dnn_scan_freq"]) or self.app.force_rescan:
                    names, frame, rects = self.app.fh.process_next_frame(
                        True, save_new_faces=True)
                    ticker = 0
                    self.app.force_rescan = False

                    self.app.preview_image = frame
                else:
                    names, frame, rects = self.app.fh.process_next_frame(
                        save_new_faces=True)
                ticker += 1
                error_count = 0
            except Exception as e:
                error_count += 1
                if self.app.fh.cam:
                    self.app.fh.cam.release()
                logging.info(e)
                if error_count > 5:
                    self.cam_is_running = False
                raise e

    def start_cam(self):
        if self.cam_is_running:
            return

        self.cam = cv2.VideoCapture(int(self.app.sh.get_face_rec_settings()["cam_id"]))
        res = self.resolutions[self.app.sh.get_face_rec_settings()["resolution"]]
        self.cam.set(3, res[0])  # set video width
        self.cam.set(4, res[1])  # set video height
        self.minW = 0.1 * self.cam.get(3)
        self.minH = 0.1 * self.cam.get(4)
        self.cam_is_running = True

    def stop_cam(self):
        if self.cam_is_running:
            self.cam.release()
            self.cam_is_running = False
