import wx
from io import BytesIO
import urllib.request
from pubsub import pub
import time
from threading import Thread, Lock
import cv2
import os
import numpy as np
from . import events
from . control import Control

class CamUpdateThread(Thread):
    def __init__(self, panel):
        super().__init__()
        self.panel = panel
        self.raw_frame = None
        self.frame = None
        self.bmp = None
        self.stop = False
        self.lock = Lock()
        self.start()
        
    def capture(self):
        with self.lock:
            result, self.raw_frame = self.panel.camera.read()
            
        if result:
            self.frame = cv2.cvtColor(self.raw_frame, cv2.COLOR_BGR2RGB)
            if self.panel.disp_width > 0 and self.panel.disp_height > 0:
                self.frame = cv2.resize(self.frame, (self.panel.disp_width, self.panel.disp_height))
                
            h, w = self.frame.shape[:2]
            self.bmp = wx.Bitmap.FromBuffer(w, h, self.frame)

        return result
        
    def get_frame(self):
        with self.lock:
            return self.frame
            
    def get_raw_frame(self):
        with self.lock:
            return self.raw_frame
            
    def get_bmp(self):
        with self.lock:
            return self.bmp
        
    def run(self):
        while not self.stop:
            if wx.GetApp() is None:
                break # app is closing, just quit
            if self.capture():
                wx.CallAfter(self.panel.update)
            time.sleep(1.0/15)

class videoPanel(wx.Panel):
    def __init__(self, parent):
        super().__init__(parent)
        self.bmp = None
        self.x = 0
        self.y = 0        
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        
    def OnPaint(self, e):
        if self.bmp:
            dc = wx.BufferedPaintDC(self)
            dc.SetBrush(wx.Brush(wx.BLACK))
            w, h = self.GetClientSize()
            dc.DrawRectangle(0, 0, w, h)
            dc.DrawBitmap(self.bmp, self.x, self.y)
            del dc
            
    def SetBitmap(self, bmp):
        self.bmp = bmp
        self.Refresh()
        
    def SetOffset(self, x, y):
        self.x = x
        self.y = y
        
class CameraControl(wx.Panel):
    def __init__(self, parent):
        super().__init__(parent)
        print('Init Camera')
        self.camera = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        self.SetCameraRes(10000, 10000)
        self.max_width = int(self.camera.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.max_height = int(self.camera.get(cv2.CAP_PROP_FRAME_HEIGHT))

        self.disp_width = -1
        self.disp_height = -1
        self.off_x = 0
        self.off_y = 0

        print(self.max_width, self.max_height)
        
        self.InitUI()
        
        self.Bind(wx.EVT_SIZE, self.OnSize)
        
        self.cam_thread = CamUpdateThread(self)
        
    def __del__(self):
        self.cam_thread.stop = True
        self.cam_thread.join()
        
    def SetCameraRes(self, x, y):
        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, x)
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, y)
        
    def update(self):
        if not self.video: return
        bmp = self.cam_thread.get_bmp()
        if bmp is not None:
            self.video.SetBitmap(bmp)
            self.Layout()
        
    def CalcFrameData(self):
        fw, fh = self.video.GetSize()
        if fw==0 or fh == 0: return
        h, w = self.max_height, self.max_width
        ar = w/h
        far = fw/fh
        self.off_x = 0
        self.off_y = 0
        if far >= ar: # frame wider than image
            nh = fh
            nw = int(w/(h/nh))
            self.off_x = int((fw - nw) / 2)
        else: # frame taller than image
            nw = fw
            nh = int(h/(w/nw))
            self.off_y = int((fh - nh) / 2)
            
        self.video.SetOffset(self.off_x, self.off_y)
        self.disp_width = nw
        self.disp_height = nh
        self.recalc = False
            
    def OnSize(self,event):
        self.Layout()
        self.CalcFrameData()
        
    def GetImage(self):
        wx.CallAfter(self.load, 'http://plottercam:8080/img')
        
    def OnGetImage(self, event):
        self.take_picture()
        
    def take_picture(self):
        frame = self.cam_thread.get_raw_frame()
        if frame is None:
            return
            
        current_directory = 'G:/'
        #get the directory to save it in.
        filename = os.path.join(current_directory, 'test.jpeg')
        #save the image
        cv2.imwrite(filename,frame)
        
    def InitUI(self):
        vbox = wx.BoxSizer(wx.VERTICAL)
        
        self.video = videoPanel(self)
        vbox.Add(self.video, proportion=1, flag=wx.EXPAND)
        
        gs = wx.GridBagSizer(2,3)
        
        self.btnGetImage = wx.Button(self, label='Get Image')
        self.btnGetImage.Bind(wx.EVT_BUTTON, self.OnGetImage)
        gs.Add(self.btnGetImage, (0,0), flag=wx.EXPAND)
        
        self.btnStartFocus = wx.Button(self, label='Start Focus')
        gs.Add(self.btnStartFocus, (1,0), flag=wx.EXPAND)
        
        self.sbWidth = wx.SpinCtrlDouble(self, min=1, initial=50.0, inc=5)
        self.sbWidth.SetDigits(2)
        gs.Add(wx.StaticText(self, label='Width (mm)'), (0, 1), flag=wx.ALIGN_CENTER_VERTICAL)
        gs.Add(self.sbWidth, (0, 2))
        
        self.sbHeight = wx.SpinCtrlDouble(self, min=1, initial=50.0, inc=5)
        self.sbHeight.SetDigits(2)
        gs.Add(wx.StaticText(self, label='Height (mm)'), (1, 1), flag=wx.ALIGN_CENTER_VERTICAL)
        gs.Add(self.sbHeight, (1, 2))
        
        vbox.Add(gs, proportion=0, flag=wx.ALL, border=5)
        self.SetSizer(vbox)
        