# coding: UTF-8
"""
Frequenty used functions and classes

Dependency:
    wxPython (4.0), 
    Numpy (1.17), 
"""

import sys, errno
from os import path, strerror
from datetime import datetime

import wx
import wx.lib.scrolledpanel as sPanel
import numpy as np

DEBUG = False

#-----------------------------------------------------------------------

def GNU_notice(idx=0):
    """ Function for printing GNU copyright statements

    Args:
        idx (int): Index to determine which statement to print out.

    Returns:
        None
    """
    if DEBUG: print("fFuncNClasses.GNU_notice()")

    if idx == 0:
        year = datetime.now().year
        print('''
Copyright (c) %i Jinook Oh, W. Tecumseh Fitch.
This program comes with ABSOLUTELY NO WARRANTY; for details run this program with the option `-w'.
This is free software, and you are welcome to redistribute it under certain conditions; run this program with the option `-c' for details.
'''%year)
    elif idx == 1:
        print('''
THERE IS NO WARRANTY FOR THE PROGRAM, TO THE EXTENT PERMITTED BY APPLICABLE LAW. EXCEPT WHEN OTHERWISE STATED IN WRITING THE COPYRIGHT HOLDERS AND/OR OTHER PARTIES PROVIDE THE PROGRAM "AS IS" WITHOUT WARRANTY OF ANY KIND, EITHER EXPRESSED OR IMPLIED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE. THE ENTIRE RISK AS TO THE QUALITY AND PERFORMANCE OF THE PROGRAM IS WITH YOU. SHOULD THE PROGRAM PROVE DEFECTIVE, YOU ASSUME THE COST OF ALL NECESSARY SERVICING, REPAIR OR CORRECTION.
''')
    elif idx == 2:
        print('''
You can redistribute this program and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.
''')

#-----------------------------------------------------------------------

def chkFPath(fp):
    """ Check whether file/folder exists
    If not found, raise FileNotFoundError

    Args:
        fp: file or folder path to check

    Returns:
        None
    """
    if DEBUG: print("fFuncNClasses.chkFPath()")
    
    rslt = False 
    if path.isdir(fp): rslt = True
    elif path.isfile(fp): rslt = True
    if rslt == False:
        raise FileNotFoundError(errno.ENOENT, strerror(errno.ENOENT), fp)

#-----------------------------------------------------------------------

def get_time_stamp(flag_ms=False):
    """ Function to return string which contains timestamp.

    Args:
        flag_ms (bool, optional): Whether to return microsecond or not

    Returns:
        ts (str): Timestamp string
    """
    if DEBUG: print("fFuncNClasses.get_time_stamp()")
    
    ts = datetime.now()
    ts = ('%.4i_%.2i_%.2i_%.2i_%.2i_%.2i')%(ts.year, 
                                            ts.month, 
                                            ts.day, 
                                            ts.hour, 
                                            ts.minute, 
                                            ts.second)
    if flag_ms == True: ts += '_%.6i'%(ts.microsecond)
    return ts

#-----------------------------------------------------------------------

def writeFile(file_path, txt='', mode='a', method='', arr=None):
    """ Function to write a text or numpy file.

    Args:
        file_path (str): File path for output file.
        txt (str): Text to print in the file.
        mode (str, optional): File opening mode.
        method (str, optional): Whether text or np (numpy).
          In Numpy case, 'save' or 'savetxt'.
        arr (None/ numpy.array, optional): Numpy array to save.

    Returns:
        None
    """
    if DEBUG: print("fFuncNClasses.writeFile()")
    
    f = open(file_path, mode)
    if method == '' or method.startswith('txt'):
        f.write(txt)
    else:
        m = method.split('_')
        if m[0] == 'np': # saving numpy array into a file
            if m[1] == 'save': # binary '.npy'
                np.save(f, arr)
            elif m[1] == 'savetxt': # text file.
                np.savetxt(f, arr)
    f.close()

#-----------------------------------------------------------------------

def str2num(s, flag="int"):
    """ Function to convert string to an integer or a float number.

    Args: 
        flag (str): int or float.

    Returns:
        oNum (None/ int/ float):
          Converted number or None (when it failed to convert).
    """
    if DEBUG: print("fFuncNClasses.str2num()")
    
    oNum = None 
    try:
        if flag == "int": oNum = int(s)
        elif flag == "float": oNum = float(s)
    except:
        pass
    return oNum 

#-----------------------------------------------------------------------

def load_img(fp, size=(-1,-1)):
    """ Load an image using wxPython functions.

    Args:
        fp (str): File path of an image to load. 
    """
    if DEBUG: print("fFuncNClasses.load_img()")
    
    chkFPath(fp) # chkeck whether file exists
    tmp_null_log = wx.LogNull() # for not displaying 
      # the tif library warning
    img = wx.Image(fp, wx.BITMAP_TYPE_ANY)
    del tmp_null_log
    if size != (-1,-1) and type(size[0]) == int and \
      type(size[1]) == int: # appropriate size is given
        if img.GetSize() != size:
            img = img.Rescale(size[0], size[1])
    return img

#-----------------------------------------------------------------------

def set_img_for_btn(imgPath, btn, imgPCurr=None, imgPDis=None, 
                    imgPFocus=None, imgPPressed=None):
    """ Set image(s) for a wx.Button

    Args:
        imgPath (str): Path of default image file. 
        btn (wx.Button): Button to put image(s).
        imgPCurr (str): Path of image for when mouse is over.
        imgPDis (str): Path of image for when button is disabled.
        imgPFocus (str): Path of image for when button has the keyboard focus.
        imgPPressed (str): Path of image for when button was pressed.

    Returns:
        btn (wx.Button): Button after processing.
    """
    if DEBUG: print("fFuncNClasses.set_img_for_btn()")
    
    imgPaths = dict(all=imgPath, current=imgPCurr, disabled=imgPDis,
                    focus=imgPFocus, pressed=imgPPressed)
    for key in imgPaths.keys():
        fp = imgPaths[key]
        if fp == None: continue
        img = load_img(fp)
        bmp = wx.Bitmap(img)
        if key == 'all': btn.SetBitmap(bmp)
        elif key == 'current': btn.SetBitmapCurrent(bmp)
        elif key == 'disabled': btn.SetBitmapDisabled(bmp)
        elif key == 'focus': btn.SetBitmapFocus(bmp)
        elif key == 'pressed': btn.SetBitmapPressed(bmp)
    return btn

#-----------------------------------------------------------------------

def getWXFonts(initFontSz=8, numFonts=5, fSzInc=2, fontFaceName=""):
    """ For setting up several fonts (wx.Font) with increasing size.

    Args:
        initFontSz (int): Initial (the smallest) font size.
        numFonts (int): Number of fonts to return.
        fSzInc (int): Increment of font size.
        fontFaceName (str, optional): Font face name.

    Returns:
        fonts (list): List of several fonts (wx.Font)

    """
    if DEBUG: print("fFuncNClasses.getWXFonts()")

    if fontFaceName == "":
        if 'darwin' in sys.platform: fontFaceName = "Monaco"
        else: fontFaceName = "Courier"
    fontSz = initFontSz 
    fonts = []  # larger fonts as index gets larger 
    for i in range(numFonts):
        fonts.append(
                        wx.Font(
                                fontSz, 
                                wx.FONTFAMILY_SWISS, 
                                wx.FONTSTYLE_NORMAL, 
                                wx.FONTWEIGHT_BOLD,
                                False, 
                                faceName=fontFaceName,
                               )
                    )
        fontSz += fSzInc 
    return fonts

#-----------------------------------------------------------------------

def setupStaticText(panel, label, name=None, size=None, 
                    wrapWidth=None, font=None, fgColor=None, bgColor=None):
    """ Initialize wx.StatcText widget with more options
    
    Args:
        panel (wx.Panel): Panel to display wx.StaticText.
        label (str): String to show in wx.StaticText.
        name (str, optional): Name of the widget.
        size (tuple, optional): Size of the widget.
        wrapWidth (int, optional): Width for text wrapping.
        font (wx.Font, optional): Font for wx.StaticText.
        fgColor (wx.Colour, optional): Foreground color 
        bgColor (wx.Colour, optional): Background color 

    Returns:
        wx.StaticText: Created wx.StaticText object.
    """ 
    if DEBUG: print("fFuncNClasses.setupStaticText()")

    sTxt = wx.StaticText(panel, -1, label)
    if name != None: sTxt.SetName(name)
    if size != None: sTxt.SetSize(size)
    if wrapWidth != None: sTxt.Wrap(wrapWidth)
    if font != None: sTxt.SetFont(font)
    if fgColor != None: sTxt.SetForegroundColour(fgColor) 
    if bgColor != None: sTxt.SetBackgroundColour(bgColor)
    return sTxt

#-----------------------------------------------------------------------

def convert_idx_to_ordinal(number):
    """ Convert zero-based index number to ordinal number string
    0->1st, 1->2nd, ...

    Args:
        number (int): An unsigned integer number.

    Returns:
        number (str): Converted string
    """
    if DEBUG: print("fFuncNClasses.convert_idx_to_ordinal()")
    
    if number == 0: return "1st"
    elif number == 1: return "2nd"
    elif number == 2: return "3rd"
    else: return "%ith"%(number+1)

#-----------------------------------------------------------------------
    
def receiveDataFromQueue(q, logFile=''):
    """ Receive data from a queue.

    Args:
        q (Queue): Queue to receive data.
        logFile (str): File path of log file.

    Returns:
        rData (): Data received from the given queue. 
    """
    if DEBUG: print("fFuncNClasses.receiveDataFromQueue()")

    rData = None
    try:
        if q.empty() == False: rData = q.get(False)
    except Exception as e:
        em = "%s, [ERROR], %s\n"%(get_time_stamp(), str(e))
        if path.isfile(logFile) == True: writeFile(logFile, em)
        print(em)
    return rData    

#-----------------------------------------------------------------------

def show_msg(msg, size=(400,200), title="Message"):
    """ Show a message with a dialog box with PopupDialog class
    (wx.Dialog).

    Args:
        size (tuple): Integer of width and height of dialog window.
        title (str): Title of the dialog window.

    Returns:
        None
    """
    if DEBUG: print("fFuncNClasses.show_msg()")
    
    err_msg = PopupDialog(title=title, inString=msg, size=size)
    err_msg.ShowModal()
    err_msg.Destroy()

#=======================================================================

class PopupDialog(wx.Dialog):
    """ Class for showing a message to a user 

    Args:
        parent (wx.Frame): Parent object (probably, wx.Frame or wx.Panel).
        id (int): ID of this dialog.
        title (str): Title of the dialog.
        inString (str): Message to show.
        iconFP (str): File path of an icon image.
        font (wx.Font): Font of message string.
        pos (None/ tuple): Position to make the dialog window.
        size (tuple): Size of dialog window.
        okay_btn (bool): Whether to show Ok button.
        cancel_btn (bool): Whether to show Cancel button.
        default_ok (bool): Whether Ok button has focus by default (so that 
          user can just press enter to dismiss the dialog window).
    """
    def __init__(self, parent=None, id=-1, title="Message", 
                 inString="", iconFP="", font=None, pos=None, 
                 size=(300, 200), okay_btn=True, cancel_btn=False, 
                 default_ok=False):
        if DEBUG: print("PopupDialog.show_msg()")
        
        wx.Dialog.__init__(self, parent, id, title)
        self.SetSize(size)
        if pos == None: self.Center()
        else: self.SetPosition(pos)
        self.Center()
        
        panel = sPanel.ScrolledPanel(self, -1, pos=(0,0), size=size)
        gbs = wx.GridBagSizer(0,0)
        row = 0; col = 0
        bw = 5
       
        if iconFP != "" and path.isfile(iconFP) == True:
            bmp = wx.Bitmap(load_img(iconFP))
            icon_sBmp = wx.StaticBitmap(panel, -1, bmp)
            gbs.Add(icon_sBmp, pos=(row,col), flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, border=bw)
            bmp_sz = icon_sBmp.GetBitmap().GetSize()
            col += 1 
        else:
            iconFP = ""
            bmp_sz = (0, 0)
        sTxt = wx.StaticText(panel, -1, label = inString, pos = (20, 20))
        sTxt.SetSize((size[0]-max(bmp_sz[0],100)-50, -1))
        if font == None: font = wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.NORMAL, wx.FONTWEIGHT_NORMAL, False, "Arial", wx.FONTENCODING_SYSTEM)
        sTxt.SetFont(font)
        sTxt.Wrap(size[0]-max(bmp_sz[0],100)-60)
        if iconFP == "": _span = (1,3)
        else: _span = _span = (1,2)
        gbs.Add(sTxt, pos=(row,col), span=_span, flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, border=bw)
        row += 1; col = 0
        okButton = wx.Button(panel, wx.ID_OK, "OK", size=(100,-1))
        gbs.Add(okButton, pos=(row,col), flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, border=bw)
        col += 1
        if cancel_btn == True:
            cancelButton = wx.Button(panel, wx.ID_CANCEL, "Cancel", size=(100,-1))
            gbs.Add(cancelButton, pos=(row,col), flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, border=bw)
        else:
            gbs.Add( wx.StaticText(panel, -1, ""), pos=(row,col), flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, border=bw )
        col += 1
        gbs.Add( wx.StaticText(panel, -1, ""), pos=(row,col), flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, border=bw )
        
        if okay_btn == False: okButton.Hide()

        _tmp = sTxt.GetSize()[1]+100
        if _tmp < size[1]: self.SetSize((size[0], _tmp)) 

        if okay_btn == True:
            if cancel_btn == False or default_ok == True:
                panel.Bind(wx.EVT_KEY_DOWN, self.onKeyPress)
                okButton.SetDefault()
        
        panel.SetSizer(gbs)
        gbs.Layout()
        panel.SetupScrolling()
    
    #-------------------------------------------------------------------

    def onKeyPress(self, event):
        if DEBUG: print("PopupDialog.onKeyPress()")
        
        if event.GetKeyCode() == wx.WXK_RETURN: 
            self.EndModal(wx.ID_OK)

#=======================================================================

if __name__ == '__main__':
    pass
