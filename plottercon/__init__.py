import wx
from threading import Thread
from pubsub import pub
from . control import Control
from . camera import CameraControl
import time

AXIS = ['X', 'Y', 'Z']

class ControlPollThread(Thread):
    def __init__(self):
        super().__init__()
        self.stop = False
        self.pause = False
        self.start()
        
    def status_on(self):
        self.pause = True
        
    def status_off(self):
        self.pause = False
        
    def run(self):
        while not self.stop:
            if wx.GetApp() is None:
                break
            wx.CallAfter(pub.sendMessage, "poll")
            time.sleep(1.0)

class MachineControl(wx.Panel):
    def __init__(self, parent, control):
        super().__init__(parent)
        
        self.control = control
        self.control.RegisterCallbackObject(self)
        self.moveBtns = {}
        self.homeBtns = {}
        self.port_map = {}

        self.InitUI()
        self.RefreshPorts(None)
        
        pub.subscribe(self.OnPoll, "poll")
        
    def on_control_status(self, pos):            
        spos = ''
        for i in range(min(len(AXIS), len(pos))):
            spos += f'{AXIS[i]}={pos[i]:.2f} '

        self.txtPosition.SetLabel(spos)
        return True
        
    def on_control_send(self, command, gline):
        self.console.AppendText(f'> {command}\n')
    
    def on_control_recv(self, line):
        self.console.AppendText(f'{line}\n')
        
    def on_control_connect(self):
        self.console.AppendText('Connected...\n')
    
    def on_control_disconnect(self):
        self.console.AppendText('Disconnected...\n')
        
    def JogClicked(self, event):
        btn = event.GetEventObject()
        axis, d = self.moveBtns[btn]
        if axis == 'Z':
            dist = self.sbZDist.GetValue()
            speed = self.sbZSpeed.GetValue()
        else:
            dist = self.sbDist.GetValue()
            speed = self.sbSpeed.GetValue()
        self.control.Jog(axis, dist*d, speed*60)
    
    def HomeAllClicked(self, event):
        self.control.HomeAll()
        
    def HomeZClicked(self, event):
        self.control.HomeZ()
        
    def SendCommand(self, event):
        cmd = self.input.GetValue()
        self.control.Send(cmd)
        
    def RefreshPorts(self, event):
        self.control.Disconnect()
        ports = self.control.GetPorts()
        self.cmbPorts.Clear()
        self.port_map.clear()
        
        if ports:
            for dev, desc in ports:
                self.port_map[desc] = dev
                self.cmbPorts.Append(desc)
            self.cmbPorts.SetSelection(0)
        else:
            self.cmbPorts.Append('No Available Devices')
    
    def OnBtnConnect(self, event):
        port = self.cmbPorts.GetValue()
        if port in self.port_map:
            dev = self.port_map[port]
            self.control.Connect(dev)
            
    def OnGetPosition(self, event):
        self.control.Send('?')
        
    def OnPoll(self):
        self.OnGetPosition(None)

    def InitUI(self):
        self.SetSizeHints(390, 480)
        vbox = wx.BoxSizer(wx.VERTICAL)
        
        btnSize = (32, 32)
        gs = wx.GridBagSizer(5,5)
        
        yp = wx.Button(self, size=btnSize, label='Y+')
        yp.Bind(wx.EVT_BUTTON, self.JogClicked)
        self.moveBtns[yp] = ('Y', 1)
        gs.Add(yp, (0,1))
        
        xm = wx.Button(self, size=btnSize, label='X-')
        xm.Bind(wx.EVT_BUTTON, self.JogClicked)
        self.moveBtns[xm] = ('X', -1)
        gs.Add(xm, (1,0))
        
        home = wx.Button(self, size=btnSize, label='H')
        home.Bind(wx.EVT_BUTTON, self.HomeAllClicked)
        self.homeBtns[home] = 'XY'
        gs.Add(home, (1,1))
        
        xp = wx.Button(self, size=btnSize, label='X+')
        xp.Bind(wx.EVT_BUTTON, self.JogClicked)
        self.moveBtns[xp] = ('X', 1)
        gs.Add(xp, (1,2))

        ym = wx.Button(self, size=btnSize, label='Y-')
        ym.Bind(wx.EVT_BUTTON, self.JogClicked)
        self.moveBtns[ym] = ('Y', -1)
        gs.Add(ym, (2,1))
        
        zp = wx.Button(self, size=btnSize, label='Z+')
        zp.Bind(wx.EVT_BUTTON, self.JogClicked)
        self.moveBtns[zp] = ('Z', 1)
        gs.Add(zp, (0,3))
        
        home_z = wx.Button(self, size=btnSize, label='H')
        home_z.Bind(wx.EVT_BUTTON, self.HomeZClicked)
        self.homeBtns[home_z] = 'Z'
        gs.Add(home_z, (1,3))

        zm = wx.Button(self, size=btnSize, label='Z-')
        zm.Bind(wx.EVT_BUTTON, self.JogClicked)
        self.moveBtns[zm] = ('Z', -1)
        gs.Add(zm, (2,3))
        
        self.sbDist = wx.SpinCtrlDouble(self, min=0.05, max=500, initial=10.0, inc=10)
        self.sbDist.SetDigits(2)
        gs.Add(wx.StaticText(self, label='Distance (mm)'), (0, 4), flag=wx.ALIGN_CENTER_VERTICAL)
        gs.Add(self.sbDist, (0, 5))
        
        self.sbSpeed = wx.SpinCtrlDouble(self, min=0.1, max=500, initial=100.0, inc=10)
        self.sbSpeed.SetDigits(2)
        gs.Add(wx.StaticText(self, label='Speed (mm/s)'), (1, 4), flag=wx.ALIGN_CENTER_VERTICAL)
        gs.Add(self.sbSpeed, (1, 5))
        
        self.sbZDist = wx.SpinCtrlDouble(self, min=0.01, max=100, initial=1.0, inc=1)
        self.sbZDist.SetDigits(2)
        gs.Add(wx.StaticText(self, label='Z Distance (mm)'), (2, 4), flag=wx.ALIGN_CENTER_VERTICAL)
        gs.Add(self.sbZDist, (2, 5))
        
        self.sbZSpeed = wx.SpinCtrlDouble(self, min=0.1, max=100, initial=10.0, inc=10)
        self.sbZSpeed.SetDigits(2)
        gs.Add(wx.StaticText(self, label='Z Speed (mm/s)'), (3, 4), flag=wx.ALIGN_CENTER_VERTICAL)
        gs.Add(self.sbZSpeed, (3, 5))
        
        self.btnGetPos = wx.Button(self, label='Get Position')
        self.btnGetPos.Bind(wx.EVT_BUTTON, self.OnGetPosition)
        gs.Add(self.btnGetPos, (4,0), (0,3), flag=wx.ALIGN_CENTER_HORIZONTAL)
        
        self.txtPosition = wx.StaticText(self, label='X=0.0 Y=0.0 Z=0.0')
        gs.Add(self.txtPosition, (4,3), (0,3), flag=wx.ALIGN_CENTER_VERTICAL)
        
        vbox.Add(gs, proportion=0, flag=wx.TOP, border=5)
        
        self.console = wx.TextCtrl(self, style=wx.TE_MULTILINE|wx.TE_READONLY)
        vbox.Add(self.console, proportion=1, flag=wx.EXPAND|wx.TOP, border=5)
        
        inputBox = wx.BoxSizer(wx.HORIZONTAL)
        self.input = wx.TextCtrl(self, style=wx.TE_PROCESS_ENTER)
        self.input.Bind(wx.EVT_TEXT_ENTER, self.SendCommand)
        self.send = wx.Button(self, label='Send')
        self.send.Bind(wx.EVT_BUTTON, self.SendCommand)
        inputBox.Add(self.input, proportion=1, flag=wx.EXPAND|wx.RIGHT, border=5)
        inputBox.Add(self.send, proportion=0)
        
        vbox.Add(inputBox, proportion=0, flag=wx.EXPAND|wx.TOP|wx.BOTTOM, border=5)
        
        connectBox = wx.BoxSizer(wx.HORIZONTAL)
        self.btnRefreshPorts = wx.Button(self, size=btnSize, label='R')
        self.btnRefreshPorts.Bind(wx.EVT_BUTTON, self.RefreshPorts)
        connectBox.Add(self.btnRefreshPorts, 0, wx.RIGHT, 5)
        
        self.cmbPorts = wx.ComboBox(self, style=wx.CB_READONLY)
        connectBox.Add(self.cmbPorts, 1, wx.EXPAND|wx.RIGHT, 5)
        
        self.btnConnect = wx.Button(self, label='Connect')
        self.btnConnect.SetSizeHints(64, 32)
        self.btnConnect.Bind(wx.EVT_BUTTON, self.OnBtnConnect)
        connectBox.Add(self.btnConnect, 0)
        
        vbox.Add(connectBox, proportion=0, flag=wx.EXPAND|wx.TOP|wx.BOTTOM, border=5)
        
        self.SetSizer(vbox)
        

class MainApp(wx.Frame):
    def __init__(self, parent, control):
        super().__init__(parent)

        self.control = control
        self.InitUI()

    def InitUI(self):
        self.SetSizeHints(800, 600)
        self.SetTitle('PlotterCon')
        # self.Centre()
        
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        self.mc = MachineControl(self, self.control)
        hbox.Add(self.mc, proportion=0, flag=wx.EXPAND)
        self.notebook = wx.Notebook(self)
        self.notebook.SetSizeHints(640, 480)
        self.camControl = CameraControl(self.notebook)
        self.notebook.AddPage(self.camControl, 'Camera')
        hbox.Add(self.notebook, proportion=1, flag=wx.EXPAND)
        self.SetSizer(hbox)


def main():

    app = wx.App()
    control = Control()
    ma = MainApp(None, control)
    ma.Show()
    app.MainLoop()
    control.Destory()
    # print('End App')

if __name__ == '__main__':
    main()