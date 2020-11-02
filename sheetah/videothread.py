from PyQt5 import QtCore
import cv2

class VideoThread(QtCore.QThread):
    frame_available = QtCore.pyqtSignal()
    def run(self):
        cap = cv2.VideoCapture(0)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        cap.set(cv2.CAP_PROP_FPS, 5)
        counter = -1
        while cap.isOpened():
            ret, frame = cap.read()
            counter = (counter + 1)%(5./0.2)
            if ret and not counter:
                colored = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
                colored[:,:,0] = 20   #HUE
                colored[:,:,1] = 120  #SAT
                # frame[:,:,2] *= 5  #VAL
                colored = cv2.cvtColor(colored, cv2.COLOR_HSV2RGB, cv2.CV_8U)
                colored = cv2.convertScaleAbs(colored, alpha=0.35, beta=20)


                blurred = cv2.bilateralFilter(frame, 7, 50, 50)
                aaa = cv2.Canny(blurred, 20, 60)
                canny = cv2.cvtColor(aaa, cv2.COLOR_GRAY2RGB)
                canny = cv2.convertScaleAbs(canny, alpha=0.05, beta=0)
                frame = colored + canny
                frame = cv2.resize(frame, (1320, 900))

                # frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
                # blurred = cv2.GaussianBlur(src, (3,3), 0)
                # blurred = cv2.medianBlur(src, 5)
                # laplace = cv2.Laplacian(blurred, cv2.CV_16S)
                # res = cv2.convertScaleAbs(laplace)
                # self.frame = cv2.stylization(frame, sigma_s=60, sigma_r=0.45)
                # blurred = cv2.blur(src, (3,3))
                # blurred = cv2.medianBlur(src, 5)
                # blurred = cv2.bilateralFilter(src, 7, 50, 50)
                self.frame = frame

                self.frame_available.emit()
        cap.release()
