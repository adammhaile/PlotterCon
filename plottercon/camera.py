import wx
from io import BytesIO
import urllib.request
from pubsub import pub
import time
from threading import Thread
import cv2
import numpy as np
from . import events
from . control import Control

WIDTH = 800
HEIGHT = 600

# class webcamPanel(wx.Panel):
    
#     def __init__(self, parent, camera, fps=10):
#         self.mirror = False
        
#         wx.Panel.__init__(self, parent)
#         self.SetBackgroundColour('ff0000')
        
#         self.frame = None
#         self.bmp = None
#         self.disp_width = -1
#         self.disp_height = -1
        
#         self.camera = camera
#         # _, frame = self.camera.read()
        
#         self.timer = wx.Timer(self)
#         self.timer.Start(1000./fps)
        
#         self.Bind(wx.EVT_PAINT, self.OnPaint)
#         self.Bind(wx.EVT_TIMER, self.NextFrame)
#         self.Bind(wx.EVT_SIZE, self.OnSize)
        
#     def OnSize(self, event):
#         fw, fh = self.GetSize()
#         if self.frame:
#             h, w = self.frame.shape[:2]
#             ar = w/h
#             far = fw/fh
#             if far >= ar: # frame wider than image
#                 nh = fh
#                 nw = w/(h/nh)
#             else: # frame taller than image
#                 nw = fw
#                 nh = h/(w/nw)
                
#             self.disp_width = nw
#             self.disp_height = nh
#             print(self.disp_width, self.disp_height)
        
#     def get_frame(self):
#         result, frame = self.camera.read()
#         if result:
#             frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
#             if self.disp_width > 0 and self.disp_height > 0:
#                 frame = cv2.resize(frame, (self.disp_width, self.disp_height))
            
#             if self.mirror:
#                 frame = cv2.flip(frame, 1)
                
#             h, w = frame.shape[:2]
#             self.bmp = wx.Bitmap.FromBuffer(w, h, frame)
            
#             # self.SetSize((width,height))
#         return result
        
#     def start(self):
#         self.timer.Start()
    
#     def pause(self):
#         self.timer.Stop()
        
#     def OnPaint(self, e):
#         if self.bmp:
#             dc = wx.BufferedPaintDC(self)
#             dc.DrawBitmap(self.bmp, 0, 0)
        
#     def NextFrame(self, e):
#         if self.get_frame():
#             self.Refresh()
            
class CameraControl(wx.Panel):
    def __init__(self, parent):
        super().__init__(parent)
        print('Init Camera')
        self.camera = cv2.VideoCapture(2, cv2.CAP_DSHOW)
        self.SetCameraRes(10000, 10000)
        self.max_width = int(self.camera.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.max_height = int(self.camera.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        self.mirror = False
        self.frame = None
        self.bmp = None
        self.disp_width = -1
        self.disp_height = -1

        print(self.max_width, self.max_height)
        
        self.InitUI()
        
        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.Bind(wx.EVT_TIMER, self.NextFrame)
        
        self.timer = wx.Timer(self)
        self.timer.Start(1000.0/5)
        
    def __del__(self):
        pass
        
    def SetCameraRes(self, x, y):
        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, x)
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, y)
        
    def NextFrame(self, event):
        self.get_frame()
        
    def get_frame(self):
        result, frame = self.camera.read()
        if result:
            self.frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            if self.disp_width > 0 and self.disp_height > 0:
                self.frame = cv2.resize(self.frame, (self.disp_width, self.disp_height))
            else:
                self.OnSize(None)
            
            if self.mirror:
                self.frame = cv2.flip(self.frame, 1)
                
            h, w = self.frame.shape[:2]
            self.bmp = wx.Bitmap.FromBuffer(w, h, self.frame)
            self.media.SetBitmap(self.bmp)
            self.Layout()
            
        return result
        
    def OnSize(self,event):
        #prob better way to do this but wxPython is dumb
        #and media size will not change until Layout() called
        self.Layout()
        fw, fh = self.media.GetSize()
        print(f'Media: {fw}x{fh}')
        if self.frame is not None:
            h, w = self.frame.shape[:2]
            ar = w/h
            far = fw/fh
            if far >= ar: # frame wider than image
                nh = fh
                nw = int(w/(h/nh))
            else: # frame taller than image
                nw = fw
                nh = int(h/(w/nw))
                
            self.disp_width = nw
            self.disp_height = nh
            print(f'Resize: {nw}x{nh}')
            self.Layout()
        
    # def resize_image(self):
    #     if self.img is None: return
    #     imgcpy = self.img.Copy()
    #     w, h = imgcpy.GetSize()
    #     fw, fh = self.media.GetSize()
    #     if(fw == 0 or fh == 0): return
    #     print((w,h), (fw, fh))
    #     ar = w/h
    #     far = fw/fh
    #     if far >= ar: # frame wider than image
    #         nh = fh
    #         nw = w/(h/nh)
    #     else: # frame taller than image
    #         nw = fw
    #         nh = h/(w/nw)
        
    #     imgcpy.Rescale(nw, nh)
        
    #     bmp = wx.Bitmap(imgcpy)
    #     self.media.SetBitmap(bmp)
    #     self.Layout()
        
    def GetImage(self):
        wx.CallAfter(self.load, 'http://plottercam:8080/img')
        
    def OnGetImage(self, event):
        # self.GetImage()
        self.take_picture(None)
        
    def take_picture(self, e):
        current_directory = 'G:/'
        mirror = False
        
        #get current frame from camera
        self.webcampanel.pause()
        self.SetCameraRes(self.max_width, self.max_height)
        
        _, image = self.camera.read()
        #check to see if you should mirror image
        if mirror:
            image = cv2.flip(image, 1)
        #get the directory to save it in.
        filename = current_directory + "/test.jpeg"
        #save the image
        cv2.imwrite(filename,image)
        #read the image (this is backwards isn't it?!
        # saved_image = cv2.imread(filename)

        self.SetCameraRes(self.cam_view_width, self.cam_view_height)
        self.webcampanel.start()
        
    def InitUI(self):
        vbox = wx.BoxSizer(wx.VERTICAL)
        
        self.media = wx.StaticBitmap(self)#, size=(WIDTH,HEIGHT))
        vbox.Add(self.media, proportion=1, flag=wx.EXPAND)
        
        # self.webcampanel = webcamPanel(self, self.camera)
        # vbox.Add(self.webcampanel, proportion=1, flag=wx.EXPAND)
        
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
        