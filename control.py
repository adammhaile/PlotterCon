import logging
logging.getLogger().setLevel(logging.ERROR) #suppress printcore crap
import serial, serial.tools.list_ports
from printrun.printcore import printcore

from gcode import SMOO

CALLBACK_FUNCS = [
    'on_control_send',
    'on_control_recv',
    'on_control_connect',
    'on_control_disconnect',
    'on_control_error',
    'on_control_online',
    'on_control_start',
    'on_control_end',
    'on_control_preprintsend',
    'on_control_printsend',
]

class Control():
    def __init__(self):
        self.pr = None
        self.pc = printcore()
        self.pc.addEventHandler(self)
        self.dev = None
        self.baud = 115200
        self.console_callbacks = {}
        self.cmd_map = SMOO
        
    def Destory(self):
        self.console_callbacks.clear()
        self.Disconnect()
        
    def RegisterCallbackObject(self, obj):
        self.console_callbacks[obj] = {}
        for func in CALLBACK_FUNCS:
            cb = getattr(obj, func, None)
            self.console_callbacks[obj][func] = cb
            
    def get_callbacks(self, func):
        res = []
        for cbd in self.console_callbacks.values():
            if func in cbd and cbd[func] is not None:
                res.append(cbd[func])
        return res
        
    # printcore handler callbacks
    def __write(self, field, text = ""):
        print("%-15s - %s" % (field, text))
        
    def on_send(self, command, gline):
        self.__write("on_send", command)
        for cb in self.get_callbacks('on_control_send'):
            cb(command, gline)
    
    def on_recv(self, line):
        self.__write("on_recv", line.strip())
        for cb in self.get_callbacks('on_control_recv'):
            cb(line)
    
    def on_connect(self):
        self.__write("on_connect")
        for cb in self.get_callbacks('on_control_connect'):
            cb()
        
    def on_disconnect(self):
        self.__write("on_disconnect")
        for cb in self.get_callbacks('on_control_disconnect'):
            cb()
    
    def on_error(self, error):
        self.__write("on_error", error)
        for cb in self.get_callbacks('on_control_error'):
            cb()
        
    def on_online(self):
        self.__write("on_online")
        for cb in self.get_callbacks('on_control_online'):
            cb()
        
    def on_start(self, resume):
        self.__write("on_start", "true" if resume else "false")
        for cb in self.get_callbacks('on_control_start'):
            cb()
        
    def on_end(self):
        self.__write("on_end")
        for cb in self.get_callbacks('on_control_end'):
            cb()
        
    def on_preprintsend(self, gline, index, mainqueue):
        self.__write("on_preprintsend", gline)
        for cb in self.get_callbacks('on_control_preprintsend'):
            cb()
    
    def on_printsend(self, gline):
        self.__write("on_printsend", gline)
        for cb in self.get_callbacks('on_control_printsend'):
            cb()

    #end printcore handler callbacks
        
    def Connected(self):
        return self.pc and self.pc.printer
        
    def Connect(self, dev):
        self.dev = dev
        self.pc.connect(self.dev, self.baud)
        
    def Disconnect(self):
        if self.Connected():
            self.pc.disconnect()
        
    def GetPorts(self):
        res = []
        for port in serial.tools.list_ports.comports():
            res.append((port.device, port.description))
        return res
         
    def PublishToConsole(self, data):
        for cb in self.console_callbacks:
            cb(data)

    def Jog(self, axis, dist, speed):
        if not self.Connected(): return
        cmds = [
            'G21 G52 G91', # metric, coord space, relative
            f'G0 {axis}{dist:.2f} F{speed:.2f} S0',
            'G90', # absolute
        ]
        self.Send(cmds)
        
    def HomeAll(self):
        if 'home_all' in self.cmd_map:
            self.Send(self.cmd_map['home_all'])
            
    def HomeZ(self):
        if 'home_z' in self.cmd_map:
            self.Send(self.cmd_map['home_z'])
        
    def Send(self, cmd):
        if isinstance(cmd, (list, tuple)):
            for c in cmd:
                self.pc.send(c.strip())
        elif isinstance(cmd, str):
            self.pc.send(cmd.strip())