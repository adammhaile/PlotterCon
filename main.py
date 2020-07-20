import wx
from control import Control


def Empty(parent, proportion, flags):
    return (wx.StaticText(parent), proportion, flags)

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
        
    def on_control_send(self, command, gline):
        self.console.AppendText(f'> {command}\n')
    
    def on_control_recv(self, line):
        self.console.AppendText(f'> {line.strip()}\n')
        
    def on_controller_connect(self):
        self.console.AppendText('Connected...\n')
    
    def on_controller_disconnect(self):
        self.console.AppendText('Disconnected...\n')
        
    def JogClicked(self, event):
        btn = event.GetEventObject()
        axis, d = self.moveBtns[btn]
        self.control.Jog(axis, 10*d, 3000)
    
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

    def InitUI(self):
        self.SetSizeHints(480, 480)
        vbox = wx.BoxSizer(wx.VERTICAL)
        
        flags = wx.EXPAND
        btnSize = (32, 32)
        home = wx.Button(self, size=btnSize, label='H_XY')
        home.Bind(wx.EVT_BUTTON, self.HomeAllClicked)
        self.homeBtns[home] = 'XY'
        
        xp = wx.Button(self, size=btnSize, label='X+')
        xp.Bind(wx.EVT_BUTTON, self.JogClicked)
        self.moveBtns[xp] = ('X', 1)
        
        xm = wx.Button(self, size=btnSize, label='X-')
        xm.Bind(wx.EVT_BUTTON, self.JogClicked)
        self.moveBtns[xm] = ('X', -1)
        
        yp = wx.Button(self, size=btnSize, label='Y+')
        yp.Bind(wx.EVT_BUTTON, self.JogClicked)
        self.moveBtns[yp] = ('Y', 1)
        
        ym = wx.Button(self, size=btnSize, label='Y-')
        ym.Bind(wx.EVT_BUTTON, self.JogClicked)
        self.moveBtns[ym] = ('Y', -1)
        
        home_z = wx.Button(self, size=btnSize, label='H_Z')
        home_z.Bind(wx.EVT_BUTTON, self.HomeZClicked)
        self.homeBtns[home_z] = 'Z'
        
        zp = wx.Button(self, size=btnSize, label='Z+')
        zp.Bind(wx.EVT_BUTTON, self.JogClicked)
        self.moveBtns[zp] = ('Z', 1)
        
        zm = wx.Button(self, size=btnSize, label='Z-')
        zm.Bind(wx.EVT_BUTTON, self.JogClicked)
        self.moveBtns[zm] = ('Z', -1)
        
        self.sbDist = wx.SpinCtrlDouble(self, min=0.05, max=500, initial=10.0, inc=10)
        self.sbDist.SetDigits(2)
        self.sbSpeed = wx.SpinCtrlDouble(self, min=0.1, max=500, initial=100.0, inc=10)
        self.sbSpeed.SetDigits(2)
        self.sbZDist = wx.SpinCtrlDouble(self, min=0.01, max=100, initial=1.0, inc=1)
        self.sbZDist.SetDigits(2)
        self.sbZSpeed = wx.SpinCtrlDouble(self, min=0.1, max=100, initial=10.0, inc=10)
        self.sbZSpeed.SetDigits(2)
        
        
        gs = wx.GridSizer(4,6,5,5)
        gs.AddMany([
            Empty(self, 0, flags), (yp, 0, flags),   Empty(self, 0, flags), (zp, 0, flags), 
                (wx.StaticText(self, label='Distance'), 0, flags), (self.sbDist, 0, flags),
                
            (xm, 0, flags),        (home, 0, flags), (xp, 0, flags),        (home_z, 0, flags),
                (wx.StaticText(self, label='Speed'), 0, flags), (self.sbSpeed, 0, flags),
                
            Empty(self, 0, flags), (ym, 0, flags),   Empty(self, 0, flags), (zm, 0, flags),
                (wx.StaticText(self, label='Z Distance'), 0, flags), (self.sbZDist, 0, flags),
                
            Empty(self, 0, flags), Empty(self, 0, flags), Empty(self, 0, flags), Empty(self, 0, flags),
                (wx.StaticText(self, label='Z Speed'), 0, flags), (self.sbZSpeed, 0, flags),
        ])
        
        vbox.Add(gs, proportion=0, flag=wx.TOP, border=5)
        
        self.console = wx.TextCtrl(self, style=wx.TE_MULTILINE|wx.TE_READONLY)
        vbox.Add(self.console, proportion=1, flag=wx.EXPAND|wx.TOP, border=5)
        
        inputBox = wx.BoxSizer(wx.HORIZONTAL)
        self.input = wx.TextCtrl(self)
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

class CameraControl(wx.Panel):
    def __init__(self, parent):
        super().__init__(parent)
        
        self.InitUI()
        
    def InitUI(self):
        self.SetBackgroundColour('#f36926')
        

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
        self.control = MachineControl(self, self.control)
        hbox.Add(self.control, proportion=0, flag=wx.EXPAND)
        self.notebook = wx.Notebook(self)
        self.notebook.SetSizeHints(640, 480)
        self.camControl = CameraControl(self.notebook)
        self.notebook.AddPage(self.camControl, 'Camera')
        hbox.Add(self.notebook, proportion=1, flag=wx.EXPAND)
        self.SetSizer(hbox)


def main():

    app = wx.App()
    control = Control()
    ex = MainApp(None, control)
    ex.Show()
    app.MainLoop()
    control.Disconnect()


if __name__ == '__main__':
    main()