
import threading
import time

import alsaaudio

import numpy as np
import tkinter as tk


class LissajousMonitor(tk.Tk):

    SQRT_2 = np.sqrt(2)

    point_size = 2
    canvas_color = "black"
    grid_color = "dark slate gray"
    point_color = "yellow"

    number_of_points = 192
    sample_size = 48
    bargraph_frequency = 48

    def __init__(self, window_size: tuple[int, int], title, titleBar):
        super().__init__()

        self._m_frame_coords = (0, 0, 0, 0)
        self._l_frame_coords = (0, 0, 0, 0)
        self._scope_center = (0, 0)
        self._max_r = 0
        self._p_shift = 0
        self._sample_max = (2 ** 16) / 2
        self._pps = 0
        self._pps_period = 1

        self.__points_counter = 0
        
        self.__half_sample_size = self.sample_size // 2
        
        self._current_time = time.time()
        self._previous_time = time.time()

        self._window_exists = True

        
        self.title(title)
        scr_width = self.winfo_screenwidth()
        scr_height = self.winfo_screenheight()
        xSize, ySize = window_size
        self.protocol('WM_DELETE_WINDOW', self._closeWindow)
        if titleBar:
            xShift, yShift = int((scr_width - xSize) / 2), int((scr_height - ySize) / 2)
            self.geometry(f"{xSize}x{ySize}+{xShift}+{yShift}")
            self.minsize(xSize, ySize)
        else:
            self.geometry(f"{scr_width}x{scr_height}")

        self.overrideredirect(not titleBar)

        self._readSoundThread = threading.Thread(target=self.read_alsa_audio, args=())

        self._p_shift = 1 if self.point_size == 1 else int(self.point_size / 2)

        self._mainCanvas()
        self._drawScope()

        self._readSoundThread.start()

    @staticmethod
    def rms(input_nparray, dtype=np.int16):
        return np.sqrt(np.nanmean(np.array(input_nparray, dtype=np.int32) ** 2))

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
        while self._window_exists:
            l, data = audio_in.read()
            if l == self.sample_size:
                if idx == self.bargraph_frequency:
                    self.redraw_bargraphs(self.split_stereo(bar_sample))
                    idx, bar_sample = 0, b""

                self.redraw_liss_scope(self.split_stereo(data))
                bar_sample += data
                idx += 1


    def redraw_liss_scope(self, stereo_channels):

        channel_l, channel_r = stereo_channels
        scope_center_x, scope_center_y = self._scope_center
        for x in range(0, self.sample_size * 2, self.sample_size // 2):
            if self.__points_counter == self.number_of_points:
                self.__points_counter = 0
            
            end_index = x + self.__half_sample_size
            channel_left = np.mean(np.frombuffer(channel_l[x: end_index], dtype=np.int16))
            channel_right = np.mean(np.frombuffer(channel_r[x: end_index], dtype=np.int16))

            x_scr = scope_center_x + (self._max_r * channel_left / self._sample_max)
            y_scr = scope_center_y - (self._max_r * channel_right / self._sample_max)

            self.canvas.coords(
                f"LISS_POINT_{self.__points_counter}",
                x_scr - self._p_shift,
                y_scr - self._p_shift,
                x_scr + (self._p_shift - 1),
                y_scr + (self._p_shift - 1)
            )
            self.__points_counter += 1
            self._pps += 1

        self._current_time = time.time()
        if ((self._current_time - self._previous_time) >= self._pps_period):
            self.canvas.itemconfigure(
                "PPS_TEXT",
                text=f"PPS: {self._pps / (self._current_time - self._previous_time):.2f}"
            )
            self._previous_time, self._pps = self._current_time, 0


    def redraw_bargraphs(self, stereo_channels):

        channels = [np.frombuffer(ch, dtype=np.int16) for ch in stereo_channels]

        mfc0, mfc1, mfc2, mfc3 = self._m_frame_coords
        lfc0, lfc1, lfc2, lfc3 = self._l_frame_coords

        scx, scy = self._scope_center

        rms_l, rms_r = [self.rms(ch) for ch in channels]
        max_l, max_r = [np.max(ch) for ch in channels]

        L_height = (lfc3 * 0.9) * rms_l / self._sample_max
        R_height = (lfc3 * 0.9) * rms_r / self._sample_max

        peak_l = (lfc3 * 0.9) * max_l / self._sample_max
        peak_r = (lfc3 * 0.9) * max_r / self._sample_max

        x1_bargraph_l = lfc0 + ((mfc2 - lfc0) / 5)
        y1_bargraph_l = lfc3 * 0.95

        x_bargraph_l = x1_bargraph_l + ((mfc2 - lfc0) / 5)
        y_bargraph_l = y1_bargraph_l - L_height

        x1_bargraph_r = lfc0 + (((mfc2 - lfc0) / 5) * 3)
        y1_bargraph_r = y1_bargraph_l

        x_bargraph_r = x1_bargraph_r + ((mfc2 - lfc0) / 5)
        y_bargraph_r = y1_bargraph_r - R_height

        self.canvas.coords("BARGRAPH_L", x_bargraph_l, y_bargraph_l, x1_bargraph_l, y1_bargraph_l)
        self.canvas.coords("BARGRAPH_R", x_bargraph_r, y_bargraph_r, x1_bargraph_r, y1_bargraph_r)

        y_peak_l = (lfc3 * 0.95) - peak_l
        y_peak_r = (lfc3 * 0.95) - peak_r

        x_peak_l = x1_bargraph_l + 1
        x1_peak_l = x_bargraph_l

        x_peak_r = x1_bargraph_r + 1
        x1_peak_r = x_bargraph_r

        self.canvas.coords("PEAK_L", x_peak_l, y_peak_l, x1_peak_l, y_peak_l)
        self.canvas.coords("PEAK_R", x_peak_r, y_peak_r, x1_peak_r, y_peak_r)


    def _drawScope(self):
        scx, scy = self._scope_center
        for x in range(self.number_of_points):
            self.canvas.create_line(
                scx, scy, scx, scy,
                fill=self.point_color,
                width=self.point_size,
                tags=f"LISS_POINT_{x}"
            )

        self.canvas.create_rectangle(0, 0, 0, 0, fill="green", tags="BARGRAPH_L")
        self.canvas.create_rectangle(0, 0, 0, 0, fill="green", tags="BARGRAPH_R")
        self.canvas.create_line(0, 0, 0, 0, fill="red", tags="PEAK_L", width=3)
        self.canvas.create_line(0, 0, 0, 0, fill="red", tags="PEAK_R", width=3)


    def _mainCanvasResize(self, event):

        self._l_frame_coords = (int(event.width * 0.85), 1, event.width - 2, event.height - 2)
        self._m_frame_coords = (1, 1, event.width - 2, event.height - 2)
        self._scope_center = (int(self._l_frame_coords[0] / 2), int(event.height / 2))

        if self._m_frame_coords[3] >= self._l_frame_coords[0]:
            self._max_r = int((self._l_frame_coords[0] * 0.9) / 2)
        else:
            self._max_r = int((self._m_frame_coords[3] * 0.9) / 2)

        self._updateGrid(event)


    def _updateGrid(self, event):

        mfc0, mfc1, mfc2, mfc3 = self._m_frame_coords
        lfc0, lfc1, lfc2, lfc3 = self._l_frame_coords

        scx, scy = self._scope_center

        self.canvas.coords("TOP_L", mfc0, mfc1, mfc2, mfc1)
        self.canvas.coords("BOTTOM_L", mfc0, mfc3, mfc2, mfc3)
        self.canvas.coords("LEFT_L", mfc0, mfc1, mfc0, mfc3)
        self.canvas.coords("RIGHT_L", mfc2, mfc1, mfc2, mfc3)
        
        self.canvas.coords("MIDDLE_L", lfc0, lfc1, lfc0, lfc3)
        self.canvas.coords("X_AXIS", lfc0, int(lfc3 / 2), mfc0, int(lfc3 / 2))
        self.canvas.coords("Y_AXIS", int(lfc0 / 2), lfc1, int(lfc0 / 2), lfc3)

        max_r = self._max_r + 4
        self.canvas.coords("SCP_LIMIT", scx - max_r, scy - max_r, scx + max_r, scy + max_r)
        self.canvas.coords("PPS_TEXT", 10, mfc3 - 10)


    def _drawGrid(self):
        mGrid = {"TOP_L": 3, "BOTTOM_L": 3, "LEFT_L": 3, "RIGHT_L": 3, "X_AXIS": 1, "Y_AXIS": 1}
        for tag in mGrid.keys():
            self.canvas.create_line(0, 0, 0, 0, fill=self.grid_color, width=mGrid[tag], tags=tag)

        self.canvas.create_line(0, 0, 0, 0, fill=self.grid_color, width=1, tags="MIDDLE_L")
        self.canvas.create_text(0, 0, text="PPS: ", tags="PPS_TEXT", anchor=tk.SW, fill="yellow")

        self.canvas.create_rectangle(0, 0, 0, 0, outline=self.grid_color, tags="SCP_LIMIT")


    def _mainCanvas(self):
        self.canvas = tk.Canvas(self, bg=self.canvas_color, bd=0)
        self.canvas.pack(anchor=tk.NW, padx=0, pady=0, expand=tk.YES, fill=tk.BOTH)
        self._drawGrid()
        self.canvas.bind("<Configure>", self._mainCanvasResize)


    def _closeWindow(self):
        while self._readSoundThread.is_alive():
            self._window_exists = False
            self._readSoundThread._Thread__stop()
        time.sleep(0.1)
        self.destroy()


    def start(self):
        pass


if __name__ == "__main__":
    lScope = LissajousMonitor((800, 800), "Lissajous monitor", True)
    lScope.mainloop()
