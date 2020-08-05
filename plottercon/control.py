import logging
logging.getLogger().setLevel(logging.ERROR) #suppress printcore crap
import serial, serial.tools.list_ports
from printrun.printcore import printcore
from threading import Thread
import time
from pubsub import pub
import wx

from . import events
from . gcode import SMOO

class StatusPollThread(Thread):
    def __init__(self):
        super().__init__()
        self.stop = False
        self.pause = True
        
        pub.subscribe(self.status_on, "status_on")
        pub.subscribe(self.status_off, "status_off")
        self.start()
        
    def status_on(self):
        print('status on')
        self.pause = False
        
    def status_off(self):
        print('status off')
        self.pause = True
        
    def run(self):
        while not self.stop:
            time.sleep(1.0)
            if self.pause or wx.GetApp() is None:
                continue
            wx.CallAfter(pub.sendMessage, "get_status")
            

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
    'on_control_status',
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
        self.pos = [0,0,0]
        
        self.jog_speed = 100
        self.jog_z_speed = 10
        
        self.pollThread = StatusPollThread()
        pub.subscribe(self.GetStatus, "get_status")
        
    def Destroy(self):
        self.console_callbacks.clear()
        self.Disconnect()
        if self.pollThread is not None:
            self.pollThread.stop = True
            self.pollThread.join()
        
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
        if command == '?': return
        for cb in self.get_callbacks('on_control_send'):
            cb(command, gline)
            
    def on_status(self, pos):
        for cb in self.get_callbacks('on_control_status'):
            cb(pos)
            
    def on_recv(self, line):
        line = line.strip()
        self.__write("on_recv", line)
        if line.startswith('ok'): return
        if self.ParsePosition(line): 
            self.on_status(self.pos)
            return
        for cb in self.get_callbacks('on_control_recv'):
            cb(line)
    
    def on_connect(self):
        self.__write("on_connect")
        for cb in self.get_callbacks('on_control_connect'):
            cb()
        events.poll_status_on()
        
    def on_disconnect(self):
        self.__write("on_disconnect")
        for cb in self.get_callbacks('on_control_disconnect'):
            cb()
        events.poll_status_off()
    
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
    
    def ParsePosition(self, line):
        if not line.startswith('<'): return False
        i = line.find('WPos:')
        if i < 0:
            i = line.find('MPos:')
        if i < 0: return False

        split = line[i+5:].split(',')
        res = []
        for val in split:
            end = False
            if val[-1] == '>':
                val = val[:-1]
                end = True
            try:
                res.append(float(val))
            except:
                break
            if end: break
            
        self.pos = []
        for i in range(len(res)):
            self.pos.append(float(res[i]))
            
        return True
        
    def GetStatus(self):
        self.Send('?')
        
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
            
    def gcode_rel_header(self):
        return 'G21 G52 G91' # metric, coord space, relative
        
    def gcode_abs_header(self):
        return 'G21 G52 G91' # metric, coord space, relative
        
    def move_cmd(self, x=0, y=0, z=0, speed=-1, rapid=True):
        res = 'G0 ' if rapid else 'G1 '
        if speed == -1:
            if x==0 and y==0 and z>0:
                speed = self.jog_z_speed
            else:
                speed = self.jog_speed
                
        speed = speed * 60
        if x: res += f'X{x:.2F} '
        if y: res += f'Y{y:.2F} '
        if z: res += f'Z{z:.2F} '
        res += f'F{speed:.2f} S0'
        return res

    def Jog(self, axis, dist, speed=-1):
        if not self.Connected(): return
        if speed==-1:
            if axis=='Z': speed = self.jog_z_speed
            else: speed = self.jog_speed
            
        speed = speed * 60
        cmds = [
            self.gcode_rel_header(), # metric, coord space, relative
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