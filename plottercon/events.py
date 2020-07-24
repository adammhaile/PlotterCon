import wx
from pubsub import pub

def poll_status_on():
    wx.CallAfter(pub.sendMessage, 'status_on')
    
def poll_status_off():
    wx.CallAfter(pub.sendMessage, 'status_off')