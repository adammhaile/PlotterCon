import wx
from io import BytesIO
import urllib.request
from pubsub import pub
import time
import errno
from threading import Thread, Lock
import cv2
import os
import numpy as np
from . import events
from . control import Control
from . import events

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
        if self.panel.camera is None:
            return False

        with self.lock:
            result, self.raw_frame = self.panel.camera.read()

            if result:
                self.raw_frame = cv2.rotate(self.raw_frame, cv2.ROTATE_180)
                y = self.panel.crop_y
                h = self.panel.crop_height
                x = self.panel.crop_x
                w = self.panel.crop_width
                self.raw_frame = self.raw_frame[y:y+h, x:x+h]
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
        print('Start cam thread')
        while not self.stop:
            if self.capture():
                if wx.GetApp() is None:
                    break # app is closing, just quit
                wx.CallAfter(self.panel.update)
            time.sleep(1.0/10)
        print('End cam thread')

class CamRunThread(Thread):
    def __init__(self, cam_ui, control):
        super().__init__()
        self.cam_ui = cam_ui
        self.control = control
        self.stop = False
        self.pause = False
        self.running_cap = False
        self.stop_cap = False
        self.stop_cmd = False

        self.xsteps = 0
        self.ysteps = 0
        self.inc = 0
        self.z_levels = 0
        self.z_step = 0
        self.out_dir = None

        self.cmd = None

        self.start()

    def cmd_frame(self):
        self.cmd = None
        speed = self.control.jog_speed
        dwell_time = 1.5
        dwell = f'G4 S{dwell_time}'
        cmds = [
            self.control.gcode_rel_header(),
            self.control.move_cmd(x=self.xsteps*self.inc, speed=speed),
            dwell,
            self.control.move_cmd(y=self.ysteps*self.inc, speed=speed),
            dwell,
            self.control.move_cmd(x=self.xsteps*self.inc*-1, speed=speed),
            dwell,
            self.control.move_cmd(y=self.ysteps*self.inc*-1, speed=speed),
            'G90',
        ]
        self.control.Send(cmds)

    def do_frame(self, x, y, inc):
        self.xsteps = x
        self.ysteps = y
        self.inc = inc
        self.cmd = self.cmd_frame

    def cmd_run_capture(self):
        self.cmd = None
        self.pause = False
        self.stop_cap = False
        self.running_cap = True
        _x, _y, _z = self.control.Position()[:3]
        speed = self.control.jog_speed
        count = 0
        wx.CallAfter(self.cam_ui.UpdateProgress, count)

        self.control.Send(self.control.gcode_abs_header())
        z_range = [_z + (i*self.z_step) for i in range(self.z_levels)]
        for z in z_range:
            subdir = f'Z{z}'
            out_dir = os.path.join(self.out_dir, subdir)
            try:
                os.makedirs(out_dir)
            except OSError as ex:
                if ex.errno == errno.EEXIST and os.path.isdir(out_dir):
                    pass

            move = self.control.move_cmd(z=z, speed=self.control.jog_z_speed)
            self.control.Send(move)
            while True:
                if self.control.Position()[2] == z: break
                time.sleep(0.5)

            y_range = [_y + (i*self.inc) for i in range(self.ysteps + 1)]
            x_range = [_x + (i*self.inc) for i in range(self.xsteps + 1)]
            x_range.reverse() #reverse initially so we can just call rev every time
            for y in y_range:
                x_range.reverse()
                for x in x_range:
                    count += 1
                    wx.CallAfter(self.cam_ui.UpdateProgress, count)
                    if self.stop or self.stop_cap: return
                    elif self.pause:
                        while self.pause:
                            time.sleep(0.1)
                    move = self.control.move_cmd(x=x, y=y, speed=speed)
                    self.control.Send(move)
                    while True and not self.stop_cap:
                        pos = self.control.Position()
                        if pos[0] == x and pos[1] == y: break
                        time.sleep(0.25)
                    name = f'Z{z}Y{y}X{x}'
                    time.sleep(1) # hold to settle motion
                    self.cam_ui.take_picture(out_dir, name)
                
            complete = (not self.stop)

        self.control.Send(self.control.move_cmd(x=_x, y=_y, speed=speed))
        self.control.Send(self.control.move_cmd(z=_z, speed=self.control.jog_z_speed))
        self.running_cap = False
        wx.CallAfter(self.cam_ui.CaptureComplete, complete)


    def do_run_capture(self, xsteps, ysteps, inc, z_levels, z_step, out_dir):
        self.xsteps = xsteps
        self.ysteps = ysteps
        self.inc = inc
        self.z_levels = z_levels
        self.z_step = z_step
        self.out_dir = out_dir
        self.cmd = self.cmd_run_capture

    def run(self):
        while not self.stop:
            if self.cmd:
                self.cmd()
            else:
                time.sleep(0.05)

class videoPanel(wx.Panel):
    def __init__(self, parent):
        super().__init__(parent)
        self.bmp = None
        self.x = 0
        self.y = 0
        self.Bind(wx.EVT_PAINT, self.OnPaint)

    def OnPaint(self, e):
        dc = wx.BufferedPaintDC(self)
        dc.SetBrush(wx.Brush(wx.BLACK))
        w, h = self.GetClientSize()
        dc.DrawRectangle(0, 0, w, h)
        if self.bmp:
            dc.DrawBitmap(self.bmp, self.x, self.y)
            dc.SetPen(wx.Pen(wx.RED, 1))
            dc.SetBrush(wx.TRANSPARENT_BRUSH)
            dc.DrawLine(0, h/2, w, h/2)
            dc.DrawLine(w/2, 0, w/2, h)
            dc.DrawCircle(w/2, h/2, h*0.1)
        del dc

    def SetBitmap(self, bmp):
        self.bmp = bmp
        self.Refresh()

    def SetOffset(self, x, y):
        self.x = x
        self.y = y

class CameraControl(wx.Panel):
    def __init__(self, parent, cfg, control):
        super().__init__(parent)
        self.control = control
        self.cfg = cfg
        self.camera = None
        self.max_width = 0
        self.max_height = 0
        self.crop_width = 0
        self.crop_height = 0
        self.crop_x = 0
        self.crop_y = 0

        self.disp_width = -1
        self.disp_height = -1
        self.off_x = 0
        self.off_y = 0
        
        self.image_count = 0

        self.InitUI()
        self.OnConfigChanged(None)

        self.Bind(wx.EVT_SIZE, self.OnSize)

        self.cam_thread = None
        self.run_thread = None

    def Close(self):
        print('Close Cam')
        self.__savecfg()
        if self.cam_thread and self.cam_thread.is_alive():
            self.cam_thread.stop = True
            self.cam_thread.join()
        if self.run_thread and self.run_thread.is_alive():
            self.run_thread.stop = True
            self.run_thread.join()

    def __savecfg(self):
        self.cfg['cam_xstep'] = self.sbXSteps.GetValue()
        self.cfg['cam_ystep'] = self.sbYSteps.GetValue()
        self.cfg['cam_inc'] = self.sbInc.GetValue()
        self.cfg['cam_zlevels'] = self.sbZLevels.GetValue()
        self.cfg['cam_zstep'] = self.sbZStep.GetValue()
        self.cfg['cam_outdir'] = self.txtOutDir.GetValue()
        print('Write cam cfg')

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
        if self.max_height == 0 or self.max_width == 0: return
        h, w = self.crop_height, self.crop_width
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

    def take_picture(self, directory, name):
        frame = self.cam_thread.get_raw_frame()
        if frame is None:
            return
        #get the directory to save it in.
        filename = os.path.join(directory, f'{name}.jpeg')
        #save the image
        cv2.imwrite(filename,frame)

    def OnInitCamera(self, event):
        print('Init Camera')
        if self.cam_thread is not None:
            self.cam_thread.stop = True
            self.cam_thread.join()
            del self.cam_thread
            self.cam_thread = None

        if self.run_thread is not None:
            self.run_thread.stop = True
            self.run_thread.join()
            del self.run_thread
            self.run_thread = None

        if self.camera and self.camera.isOpened():
            self.camera.release()

        cam_id = self.sbCamera.GetValue()
        self.camera = cv2.VideoCapture(cam_id, cv2.CAP_DSHOW)
        if not self.camera.isOpened():
            self.camera.release()
            self.camera = None
            self.video.SetBitmap(None)
            wx.MessageBox(f'Unable to open camera {cam_id}', 'Camera Init Failure', wx.OK | wx.ICON_WARNING)
            return

        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 10000)
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 1000)
        self.max_width = int(self.camera.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.max_height = int(self.camera.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if self.max_width > self.max_height:
            self.crop_width = self.crop_height = self.max_height
            self.crop_x = (self.max_width - self.crop_width) // 2
        else:
            self.crop_width = self.crop_height = self.max_width
            self.crop_y = (self.max_height - self.crop_height) // 2



        self.CalcFrameData()
        print(self.max_width, self.max_height)
        if not self.cam_thread:
            self.cam_thread = CamUpdateThread(self)

        if not self.run_thread:
            self.run_thread = CamRunThread(self, self.control)

        self.cfg['cam_id'] = cam_id
        
    def UpdateProgress(self, index):
        self.prog.SetValue(index)
        self.txtProg.SetLabel(f'{index} of {self.image_count}')
    
    def OnConfigChanged(self, e):
        x_steps = self.sbXSteps.GetValue()
        y_steps = self.sbYSteps.GetValue()
        inc = self.sbInc.GetValue()
        z_levels = self.sbZLevels.GetValue()
        z_step = self.sbZStep.GetValue()
        
        x = x_steps * inc
        y = y_steps * inc
        area = x * y
        
        self.image_count = (x_steps+1) * (y_steps+1) * z_levels
        
        lbl = f'{x}x{y}mm {area}mm² {self.image_count} images'
        
        self.txtDetails.SetLabel(lbl)
        self.prog.SetRange(self.image_count)

    def InitUI(self):
        vbox = wx.BoxSizer(wx.VERTICAL)

        self.video = videoPanel(self)
        vbox.Add(self.video, proportion=1, flag=wx.EXPAND)

        gs = wx.GridBagSizer(5,9)

        self.btnInitCamera = wx.Button(self, label='Init Camera')
        self.btnInitCamera.Bind(wx.EVT_BUTTON, self.OnInitCamera)
        gs.Add(self.btnInitCamera, (0,0), span=(0,2), flag=wx.EXPAND)

        self.sbCamera = wx.SpinCtrl(self, min=0, max=99, initial=0)
        gs.Add(wx.StaticText(self, label='Camera ID'), (1, 0), flag=wx.ALIGN_CENTER_VERTICAL)
        self.sbCamera.SetValue(self.cfg.get('cam_id', 0))
        gs.Add(self.sbCamera, (1, 1))

        self.sbXSteps = wx.SpinCtrl(self, min=1, max=100000, initial=self.cfg.get('cam_xstep', 50))
        self.sbXSteps.Bind(wx.EVT_SPINCTRL, self.OnConfigChanged)
        self.sbXSteps.SetSizeHints((75, -1))
        gs.Add(wx.StaticText(self, label='X Steps'), (0, 3), flag=wx.ALIGN_CENTER_VERTICAL)
        gs.Add(self.sbXSteps, (0, 4))

        self.sbYSteps = wx.SpinCtrl(self, min=1, max=100000, initial=self.cfg.get('cam_ystep', 50))
        self.sbYSteps.Bind(wx.EVT_SPINCTRL, self.OnConfigChanged)
        self.sbYSteps.SetSizeHints((75, -1))
        gs.Add(wx.StaticText(self, label='Y Steps'), (1, 3), flag=wx.ALIGN_CENTER_VERTICAL)
        gs.Add(self.sbYSteps, (1, 4))

        self.sbInc = wx.SpinCtrlDouble(self, min=1, max=50, initial=self.cfg.get('cam_inc', 1), inc=1)
        self.sbInc.Bind(wx.EVT_SPINCTRLDOUBLE, self.OnConfigChanged)
        self.sbInc.SetDigits(1)
        self.sbInc.SetSizeHints((75, -1))
        gs.Add(wx.StaticText(self, label='Inc (mm)'), (2, 3), flag=wx.ALIGN_CENTER_VERTICAL)
        gs.Add(self.sbInc, (2, 4))

        self.sbZLevels = wx.SpinCtrl(self, min=1, max=100, initial=self.cfg.get('cam_zlevels', 1))
        self.sbZLevels.Bind(wx.EVT_SPINCTRL, self.OnConfigChanged)
        self.sbZLevels.SetSizeHints((55, -1))
        gs.Add(wx.StaticText(self, label='Z Levels'), (0, 5), flag=wx.ALIGN_CENTER_VERTICAL)
        gs.Add(self.sbZLevels, (0, 6))

        self.sbZStep = wx.SpinCtrlDouble(self, min=-10, max=10, initial=self.cfg.get('cam_zstep', 0), inc=0.1)
        self.sbZStep.Bind(wx.EVT_SPINCTRLDOUBLE, self.OnConfigChanged)
        self.sbZStep.SetDigits(1)
        self.sbZStep.SetSizeHints((55, -1))
        gs.Add(wx.StaticText(self, label='Z Step (mm)'), (1, 5), flag=wx.ALIGN_CENTER_VERTICAL)
        gs.Add(self.sbZStep, (1, 6))

        self.btnStart = wx.Button(self, label='Start')
        self.btnStart.Bind(wx.EVT_BUTTON, self.OnStartPause)
        gs.Add(self.btnStart, (0,7), flag=wx.EXPAND)

        self.btnStop = wx.Button(self, label='Stop')
        self.btnStop.Bind(wx.EVT_BUTTON, self.OnStop)
        gs.Add(self.btnStop, (0,8), flag=wx.EXPAND)

        self.btnFrame = wx.Button(self, label='Frame')
        self.btnFrame.Bind(wx.EVT_BUTTON, self.OnFrame)
        gs.Add(self.btnFrame, (1,7), flag=wx.EXPAND)

        self.btnOut = wx.Button(self, label='Out Dir')
        self.btnOut.Bind(wx.EVT_BUTTON, self.OnChooseDir)
        gs.Add(self.btnOut, (2,5), flag=wx.EXPAND)
        self.txtOutDir = wx.TextCtrl(self, value=self.cfg.get('cam_outdir', ''), style=wx.TE_READONLY)
        gs.Add(self.txtOutDir, (2,6), span=(0,3), flag=wx.EXPAND)
        
        self.txtDetails = wx.StaticText(self, label='')
        gs.Add(self.txtDetails, (3, 3), span=(0,4), flag=wx.ALIGN_CENTER_VERTICAL)
        
        self.txtProg = wx.StaticText(self, label='Status: Idle')
        gs.Add(self.txtProg, (4, 0), span=(0,3), flag=wx.ALIGN_CENTER_HORIZONTAL)
        
        self.prog = wx.Gauge(self)
        gs.Add(self.prog, (4, 3), span=(0,6), flag=wx.EXPAND)

        vbox.Add(gs, proportion=0, flag=wx.ALL, border=5)
        self.SetSizer(vbox)

    def CaptureComplete(self, state):
        self.btnStart.SetLabel('Start')
        if state:
            wx.MessageBox(f'Scan Complete!', 'Scan Complete!', wx.OK | wx.ICON_INFORMATION)
        self.DoComplete()
            
    def DoComplete(self):
        self.prog.SetValue(0)
        self.txtProg.SetLabel('Status: Idle')

    def OnStop(self, e):
        if self.control.Connected() and self.run_thread:
            self.run_thread.stop_cap = True
            self.btnStart.SetLabel('Start')
            self.DoComplete()

    def OnStartPause(self, e):
        if self.control.Connected() and self.run_thread:
            if self.run_thread.running_cap:
                if self.run_thread.pause:
                    self.run_thread.pause = False
                    self.btnStart.SetLabel('Pause')
                    self.txtProg.SetLabel('Status: Paused')
                else:
                    self.run_thread.pause = True
                    self.btnStart.SetLabel('Start')
                    self.txtProg.SetLabel('Status: Paused')
            else:
                if self.control.Connected() and self.run_thread:
                    xsteps = self.sbXSteps.GetValue()
                    ysteps = self.sbYSteps.GetValue()
                    inc = self.sbInc.GetValue()
                    z_levels = self.sbZLevels.GetValue()
                    z_step = self.sbZStep.GetValue()
                    out_dir = self.txtOutDir.GetValue()
                    self.prog.SetValue(0)
                    self.run_thread.do_run_capture(xsteps, ysteps, inc, z_levels, z_step, out_dir)
                    self.btnStart.SetLabel('Pause')

    def OnFrame(self, e):
        if self.control.Connected() and self.run_thread:
            x = self.sbXSteps.GetValue()
            y = self.sbYSteps.GetValue()
            inc = self.sbInc.GetValue()
            self.run_thread.do_frame(x, y, inc)

    def OnChooseDir(self, e):
        print('Out Dir')
        dlg = wx.DirDialog(self, "Choose output directory", "",
                    wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST)
        if dlg.ShowModal() == wx.ID_OK:
            self.txtOutDir.SetValue(dlg.GetPath())

# z-levels
# z-step
# frame - pause at each corner
# Start/Pause
# Stop
# set directory