import cv2

class Png(cv2.Mat):
    def __init__(self, origin:cv2.Mat) -> None:
        self.origin = origin
        return

    def set_background(self, color):

        