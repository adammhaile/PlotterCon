import wx
from io import BytesIO
import urllib.request
from pubsub import pub
import time
from threading import Thread
from . import events
from . control import Control

WIDTH = 800
HEIGHT = 600

class ImageDownloadThread(Thread):
    def __init__(self):
        super().__init__()
        self.stop = False
        self.download = False
        self.url = None
        self.img = None
        self.start()
        
    def get_img(self):
        img = self.img
        self.img = None
        return img
        
    def run(self):
        while not self.stop:
            time.sleep(0.1)
            if not self.download or wx.GetApp() is None:
                continue
            if self.url.startswith('http'):
                with urllib.request.urlopen(self.url) as f:
                    data = f.read()
            else:
                with open(self.url, "rb") as d:
                    data = d.read()
            stream = BytesIO(data)
            self.img = wx.Image(stream)
            self.download = False
            self.url = None
            wx.CallAfter(pub.sendMessage, "img_get")
            
class CameraControl(wx.Panel):
    def __init__(self, parent):
        super().__init__(parent)
        
        self.img = None
        self.download_thread = ImageDownloadThread()
        
        self.InitUI()
        
        self.Bind(wx.EVT_SIZE, self.OnSize)
        # self.load('C:/Users/admin/Pictures/IMG_20200613_170435.jpg')
        
        pub.subscribe(self.ImageGet, "img_get")
        
    def OnSize(self,event):
        #prob better way to do this but wxPython is dumb
        #and media size will not change until Layout() called
        self.Layout()
        self.resize_image()
        
    def ImageGet(self):
        self.img = self.download_thread.get_img()
        self.resize_image()
        
    def load(self, filename):
        self.download_thread.url = filename
        self.download_thread.download = True

    def resize_image(self):
        if self.img is None: return
        imgcpy = self.img.Copy()
        w, h = imgcpy.GetSize()
        fw, fh = self.media.GetSize()
        if(fw == 0 or fh == 0): return
        print((w,h), (fw, fh))
        ar = w/h
        far = fw/fh
        if far >= ar: # frame wider than image
            nh = fh
            nw = w/(h/nh)
        else: # frame taller than image
            nw = fw
            nh = h/(w/nw)
        
        imgcpy.Rescale(nw, nh)
        
        bmp = wx.Bitmap(imgcpy)
        self.media.SetBitmap(bmp)
        self.Layout()
        
    def GetImage(self):
        wx.CallAfter(self.load, 'http://plottercam:8080/thumb')
        
    def OnGetImage(self, event):
        self.GetImage()
        
    def InitUI(self):
        vbox = wx.BoxSizer(wx.VERTICAL)
        
        self.media = wx.StaticBitmap(self, size=(WIDTH,HEIGHT))
        vbox.Add(self.media, proportion=1, flag=wx.EXPAND)
        
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
        