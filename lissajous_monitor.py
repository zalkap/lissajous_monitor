
import threading
import time

import alsaaudio
import audioop

from numpy import sin, cos, pi, fromstring, int16, mean, sqrt
import tkinter as tk


class LissajousMonitor(tk.Tk):

    pointSize = 2
    canvasColor = "black"
    gridColor = "dark slate gray"
    pointColor = "yellow"

    _mFrameCoords = (0, 0, 0, 0)
    _lFrameCoords = (0, 0, 0, 0)
    _scopeCenter = (0, 0)
    _max_r = 0
    _p_shift = 0
    _sampleMAX = (2 ** 16) / 2

    _pointsNumber = 196
    _sampleSize = 48
    _barFrequency = 64
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

        self._readSoundThread = threading.Thread(target=self._readSND, args=())

        if self.pointSize == 1:
            self._p_shift = 1
        else:
            self._p_shift = (self.pointSize / 2)

        self._mainCanvas()
        self._drawScope()

        self._readSoundThread.start()


    def _splitStereo(self, stereodata):
        temp_l_ch, temp_r_ch = b"", b""
        x = 0
        l = len(stereodata)
        while x < l:
            temp_l_ch += stereodata[x:x + 2]
            temp_r_ch += stereodata[x + 2:x + 4]
            x += 4
        return (temp_l_ch, temp_r_ch)


    def _readSND(self):

        SND_in = alsaaudio.PCM(alsaaudio.PCM_CAPTURE, alsaaudio.PCM_NORMAL)
        SND_in.setchannels(2)
        SND_in.setrate(44100)
        SND_in.setformat(alsaaudio.PCM_FORMAT_S16_LE)
        SND_in.setperiodsize(self._sampleSize)
        idx = 0
        bar_sample = ""
        while self._windowExists:
            l, data = SND_in.read()
            if l == self._sampleSize:
                if idx == self._barFrequency:
                    self._redrawBars(bar_sample)
                    bar_sample = ""
                    idx = 0

                self._redrawLissScope(data)
                bar_sample += data
                idx += 1


    def _redrawLissScope(self, data):

        chL, chR = self._splitStereo(data)
        for x in range(0, len(chL), self._sampleSize // 2):

            if self._pointCounter == self._pointsNumber:
                self._pointCounter = 0

            chLeft = mean(fromstring(chL[x:x + self._sampleSize // 2], dtype=int16))
            chRight = mean(fromstring(chR[x:x + self._sampleSize // 2], dtype=int16))

            x_scr = self._scopeCenter[0] + (self._max_r * chLeft / self._sampleMAX)
            y_scr = self._scopeCenter[1] - (self._max_r * chRight / self._sampleMAX)

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


    def _redrawBars(self, data):

        chL, chR = self._splitStereo(data)

        mfc0, mfc1, mfc2, mfc3 = self._mFrameCoords
        lfc0, lfc1, lfc2, lfc3 = self._lFrameCoords

        sc0, sc1 = self._scopeCenter

        rmsL = audioop.rms(fromstring(chL, dtype=int16), 2)
        rmsR = audioop.rms(fromstring(chR, dtype=int16), 2)

        maxL = audioop.max(fromstring(chL, dtype=int16), 2) / sqrt(2)
        max_r = audioop.max(fromstring(chR, dtype=int16), 2) / sqrt(2)

        L_height = (lfc3 * 0.9) * rmsL / self._sampleMAX
        R_height = (lfc3 * 0.9) * rmsR / self._sampleMAX

        peakL = (lfc3 * 0.9) * maxL / self._sampleMAX
        peakR = (lfc3 * 0.9) * max_r / self._sampleMAX

        x1_barL = lfc0 + ((mfc2 - lfc0) / 5)
        y1_barL = lfc3 * 0.95

        x_barL = x1_barL + ((mfc2 - lfc0) / 5)
        y_barL = y1_barL - L_height

        x1_barR = lfc0 + (((mfc2 - lfc0) / 5) * 3)
        y1_barR = y1_barL

        x_barR = x1_barR + ((mfc2 - lfc0) / 5)
        y_barR = y1_barR - R_height

        self.canvas.coords("barL", x_barL, y_barL, x1_barL, y1_barL)
        self.canvas.coords("barR", x_barR, y_barR, x1_barR, y1_barR)

        y_peakL = (lfc3 * 0.95) - peakL
        y_peakR = (lfc3 * 0.95) - peakR

        x_peakL = x1_barL + 1
        x1_peakL = x_barL

        x_peakR = x1_barR + 1
        x1_peakR = x_barR

        self.canvas.coords("peakL", x_peakL, y_peakL, x1_peakL, y_peakL)
        self.canvas.coords("peakR", x_peakR, y_peakR, x1_peakR, y_peakR)


    def _drawScope(self):
        sc0, sc1 = self._scopeCenter
        for x in range(0, self._pointsNumber):
            self.canvas.create_line(
                sc0, sc1, sc0, sc1,
                fill=self.pointColor,
                width=self.pointSize,
                tags=f"liss_point_{x}"
            )

        self.canvas.create_rectangle(0, 0, 0, 0, fill="green", tags="barL")
        self.canvas.create_rectangle(0, 0, 0, 0, fill="green", tags="barR")
        self.canvas.create_line(0, 0, 0, 0, fill="red", tags="peakL", width=3)
        self.canvas.create_line(0, 0, 0, 0, fill="red", tags="peakR", width=3)


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

        sc0, sc1 = self._scopeCenter

        self.canvas.coords("topL", mfc0, mfc1, mfc2, mfc1)
        self.canvas.coords("bottomL", mfc0, mfc3, mfc2, mfc3)
        self.canvas.coords("leftL", mfc0, mfc1, mfc0, mfc3)
        self.canvas.coords("rightL", mfc2, mfc1, mfc2, mfc3)
        
        self.canvas.coords("middleL", lfc0, lfc1, lfc0, lfc3)
        self.canvas.coords("xAxis", lfc0, int(lfc3 / 2), mfc0, int(lfc3 / 2))
        self.canvas.coords("yAxis", int(lfc0 / 2), lfc1, int(lfc0 / 2), lfc3)

        max_r = self._max_r + 4
        self.canvas.coords("scp_limit", sc0 - max_r, sc1 - max_r, sc0 + max_r, sc1 + max_r)
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
