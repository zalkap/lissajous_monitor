
import threading
import time

import alsaaudio
import audioop

import numpy as np
import tkinter as tk


class LissajousMonitor(tk.Tk):

    SQRT_2 = np.sqrt(2)
    pointSize = 2
    canvasColor = "black"
    gridColor = "dark slate gray"
    pointColor = "yellow"

    _mFrameCoords = (0, 0, 0, 0)
    _lFrameCoords = (0, 0, 0, 0)
    _scopeCenter = (0, 0)
    _max_r = 0
    _p_shift = 0
    sample_max = (2 ** 16) / 2

    _pointsNumber = 196
    sample_size = 48
    bargraph_frequency = 64
    _pointCounter = 0

    _pps = 0
    _currTime = time.time()
    _prevTime = time.time()

    _readSoundThread = None
    _windowExists = True

    def __init__(self, xSize, ySize, title, titleBar):
        super().__init__()
        self.title(title)
        scr_width = self.winfo_screenwidth()
        scr_height = self.winfo_screenheight()
        self.protocol('WM_DELETE_WINDOW', self._closeWindow)
        if titleBar:
            xShift = (scr_width - xSize) / 2
            yShift = (scr_height - ySize) / 2
            self.geometry("%ix%i+%i+%i" % (xSize, ySize, xShift, yShift))
            self.minsize(xSize, ySize)
        else:
            self.geometry("%ix%i" % (scr_width, scr_height))

        self.overrideredirect(not titleBar)

        self._readSoundThread = threading.Thread(target=self.read_alsa_audio, args=())

        if self.pointSize == 1:
            self._p_shift = 1
        else:
            self._p_shift = (self.pointSize / 2)

        self._mainCanvas()
        self._drawScope()

        self._readSoundThread.start()


    @staticmethod
    def split_stereo(stereodata):
        channel_left, channel_right = b"", b""
        for x in range(0, len(stereodata), 4):
            channel_left += stereodata[x: x + 2]
            channel_right += stereodata[x + 2: x + 4]
        return (channel_left, channel_right)


    def read_alsa_audio(self):

        audio_in = alsaaudio.PCM(
            alsaaudio.PCM_CAPTURE,
            alsaaudio.PCM_NORMAL,
            channels=2,
            rate=44100,
            format=alsaaudio.PCM_FORMAT_S16_LE,
            periodsize=self.sample_size
        )
        idx, bar_sample = 0, b""
        while self._windowExists:
            l, data = audio_in.read()
            if l == self.sample_size:
                if idx == self.bargraph_frequency:
                    self.redraw_bargraphs(self.split_stereo(bar_sample))
                    idx, bar_sample = 0, b""

                self._redrawLissScope(self.split_stereo(data))
                bar_sample += data
                idx += 1


    def _redrawLissScope(self, stereo_channels):

        channel_l, channel_r = stereo_channels

        for x in range(0, len(channel_l), self.sample_size // 2):

            if self._pointCounter == self._pointsNumber:
                self._pointCounter = 0

            channel_left = np.mean(np.frombuffer(channel_l[x: x + self.sample_size // 2], dtype=np.int16))
            channel_right = np.mean(np.frombuffer(channel_r[x: x + self.sample_size // 2], dtype=np.int16))

            x_scr = self._scopeCenter[0] + (self._max_r * channel_left / self.sample_max)
            y_scr = self._scopeCenter[1] - (self._max_r * channel_right / self.sample_max)

            self.canvas.coords(
                f"liss_point_{self._pointCounter}",
                x_scr - self._p_shift,
                y_scr - self._p_shift,
                x_scr + (self._p_shift - 1),
                y_scr + (self._p_shift - 1)
            )
            self._pointCounter += 1
            self._pps += 1

        self._currTime = time.time()
        if ((self._currTime - self._prevTime) >= 5):
            self.canvas.itemconfigure("FPS_text", text="PPS: %.2f" % (
                (self._pps) / (self._currTime - self._prevTime)))
            self._prevTime = self._currTime
            self._pps = 0


    def redraw_bargraphs(self, stereo_channels):

        channel_l, channel_r = stereo_channels

        mfc0, mfc1, mfc2, mfc3 = self._mFrameCoords
        lfc0, lfc1, lfc2, lfc3 = self._lFrameCoords

        scx, scy = self._scopeCenter

        rms_l = audioop.rms(np.frombuffer(channel_l, dtype=np.int16), 2)
        rms_r = audioop.rms(np.frombuffer(channel_r, dtype=np.int16), 2)
        
        max_l = audioop.max(np.frombuffer(channel_l, dtype=np.int16), 2) / self.SQRT_2
        max_r = audioop.max(np.frombuffer(channel_r, dtype=np.int16), 2) / self.SQRT_2

        L_height = (lfc3 * 0.9) * rms_l / self.sample_max
        R_height = (lfc3 * 0.9) * rms_r / self.sample_max

        peak_l = (lfc3 * 0.9) * max_l / self.sample_max
        peak_r = (lfc3 * 0.9) * max_r / self.sample_max

        x1_bargraph_l = lfc0 + ((mfc2 - lfc0) / 5)
        y1_bargraph_l = lfc3 * 0.95

        x_bargraph_l = x1_bargraph_l + ((mfc2 - lfc0) / 5)
        y_bargraph_l = y1_bargraph_l - L_height

        x1_bargraph_r = lfc0 + (((mfc2 - lfc0) / 5) * 3)
        y1_bargraph_r = y1_bargraph_l

        x_bargraph_r = x1_bargraph_r + ((mfc2 - lfc0) / 5)
        y_bargraph_r = y1_bargraph_r - R_height

        self.canvas.coords("bargraph_l", x_bargraph_l, y_bargraph_l, x1_bargraph_l, y1_bargraph_l)
        self.canvas.coords("bargraph_r", x_bargraph_r, y_bargraph_r, x1_bargraph_r, y1_bargraph_r)

        y_peak_l = (lfc3 * 0.95) - peak_l
        y_peak_r = (lfc3 * 0.95) - peak_r

        x_peak_l = x1_bargraph_l + 1
        x1_peak_l = x_bargraph_l

        x_peak_r = x1_bargraph_r + 1
        x1_peak_r = x_bargraph_r

        self.canvas.coords("peak_l", x_peak_l, y_peak_l, x1_peak_l, y_peak_l)
        self.canvas.coords("peak_r", x_peak_r, y_peak_r, x1_peak_r, y_peak_r)


    def _drawScope(self):
        scx, scy = self._scopeCenter
        for x in range(0, self._pointsNumber):
            self.canvas.create_line(
                scx, scy, scx, scy,
                fill=self.pointColor,
                width=self.pointSize,
                tags=f"liss_point_{x}"
            )

        self.canvas.create_rectangle(0, 0, 0, 0, fill="green", tags="bargraph_l")
        self.canvas.create_rectangle(0, 0, 0, 0, fill="green", tags="bargraph_r")
        self.canvas.create_line(0, 0, 0, 0, fill="red", tags="peak_l", width=3)
        self.canvas.create_line(0, 0, 0, 0, fill="red", tags="peak_r", width=3)


    def _mainCanvasResize(self, event):

        self._lFrameCoords = (int(event.width * 0.85), 1, event.width - 2, event.height - 2)
        self._mFrameCoords = (1, 1, event.width - 2, event.height - 2)
        self._scopeCenter = (int(self._lFrameCoords[0] / 2), int(event.height / 2))

        if self._mFrameCoords[3] >= self._lFrameCoords[0]:
            self._max_r = int((self._lFrameCoords[0] * 0.9) / 2)
        else:
            self._max_r = int((self._mFrameCoords[3] * 0.9) / 2)

        self._updateGrid(event)


    def _updateGrid(self, event):

        mfc0, mfc1, mfc2, mfc3 = self._mFrameCoords
        lfc0, lfc1, lfc2, lfc3 = self._lFrameCoords

        scx, scy = self._scopeCenter

        self.canvas.coords("topL", mfc0, mfc1, mfc2, mfc1)
        self.canvas.coords("bottomL", mfc0, mfc3, mfc2, mfc3)
        self.canvas.coords("leftL", mfc0, mfc1, mfc0, mfc3)
        self.canvas.coords("rightL", mfc2, mfc1, mfc2, mfc3)
        
        self.canvas.coords("middleL", lfc0, lfc1, lfc0, lfc3)
        self.canvas.coords("xAxis", lfc0, int(lfc3 / 2), mfc0, int(lfc3 / 2))
        self.canvas.coords("yAxis", int(lfc0 / 2), lfc1, int(lfc0 / 2), lfc3)

        max_r = self._max_r + 4
        self.canvas.coords("scp_limit", scx - max_r, scy - max_r, scx + max_r, scy + max_r)
        self.canvas.coords("FPS_text", 10, mfc3 - 10)


    def _drawGrid(self):
        mGrid = {"topL": 3, "bottomL": 3, "leftL": 3, "rightL": 3, "xAxis": 1, "yAxis": 1}
        for tag in mGrid.keys():
            self.canvas.create_line(0, 0, 0, 0, fill=self.gridColor, width=mGrid[tag], tags=tag)

        self.canvas.create_line(0, 0, 0, 0, fill=self.gridColor, width=1, tags="middleL")
        self.canvas.create_text(0, 0, text="PPS: ", tags="FPS_text", anchor=tk.SW, fill="yellow")

        self.canvas.create_rectangle(0, 0, 0, 0, outline=self.gridColor, tags="scp_limit")


    def _mainCanvas(self):
        self.canvas = tk.Canvas(self, bg=self.canvasColor, bd=0)
        self.canvas.pack(anchor=tk.NW, padx=0, pady=0, expand=tk.YES, fill=tk.BOTH)
        self._drawGrid()
        self.canvas.bind("<Configure>", self._mainCanvasResize)


    def _closeWindow(self):

        while self._readSoundThread.is_alive():
            self._windowExists = False
            self._readSoundThread._Thread__stop()
        time.sleep(0.1)
        self.destroy()


    def start(self):
        pass


if __name__ == "__main__":
    lScope = LissajousMonitor(800, 700, "Lissajous monitor", True)
    lScope.mainloop()
