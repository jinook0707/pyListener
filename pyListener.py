# coding: UTF-8

'''
PyListener
An open-source software written in Python for sound comparison. Currently, its 
main functionality is to listen to sound from microphone and save a recognized 
sound as WAV file, when it is similar with a loaded template sound.

Jinook Oh, Cognitive Biology department, University of Vienna
September 2018.

--------------------------------------------------------------------------------
Copyright (C) 2019 Jinook Oh, W. Tecumseh Fitch 
- Contact: jinook.oh@univie.ac.at, tecumseh.fitch@univie.ac.at

This program is free software: you can redistribute it and/or modify it under 
the terms of the GNU General Public License as published by the Free Software 
Foundation, either version 3 of the License, or (at your option) any later 
version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY 
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A 
PARTICULAR PURPOSE.  See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with 
this program.  If not, see <http://www.gnu.org/licenses/>.
--------------------------------------------------------------------------------

This program was programmed and tested in macOS 10.13.
'''

import sys, wave
from os import path, getcwd, mkdir 
from copy import copy

import wx
import wx.lib.scrolledpanel as SPanel 
import numpy as np
from skimage import filters

import pyListenerLib as PLL 
from fFuncNClasses import GNU_notice, writeFile, get_time_stamp, show_msg, set_img_for_btn

VERSION = 'v.0.2'
'''
# 0.1: Initial development - 2018.July
# 0.2: Changed to comparing parameters, separated audio signal processing to pyListenerLib.py 
and user interface was updated. - 2019.Aug
'''

CWD = getcwd() # current working directory
DEBUG = False 

#===============================================================================

class PyListenerFrame(wx.Frame):
    def __init__(self):
        if DEBUG: print("PyListenerFrame.__init__()")
        if path.isdir('log') == False: mkdir('log')
        if path.isdir('recordings') == False: mkdir('recordings')
        self.flag_showCMInCol = True
        self.logFile = "log/log_%s.txt"%(get_time_stamp()[:-9]) # determine log file name, [:-9] cut off hh_mm_ss from timestamp

        ### init class for reading audio data from microphone
        self.pl = PLL.PyListener(self, self, self.logFile, CWD, DEBUG) 
        if self.pl.devIdx == []: self.onClose(None)

        self.spBmp = None # spectrogram image (bmp) 
        self.timers = {}
        self.chkB_comp = [] # checkboxes to enable comparison parameters 
        bgCol = '#333333'
        w_pos = (0, 25) 
        self.w_sz = [wx.Display(0).GetGeometry()[2], wx.Display(0).GetGeometry()[3]-w_pos[1]-100] # initial size 
        pi = {}; self.pi = pi # panel information 
        pi["bp"] = dict( pos=(0, 0), 
                         sz=(self.w_sz[0], 50), 
                         bgCol="#cccccc", 
                         style=wx.TAB_TRAVERSAL|wx.SUNKEN_BORDER ) # top panel for buttons and some settings
        pi["ip_sp"] = dict( pos=(0, pi['bp']['sz'][1]), 
                            sz=(int(self.w_sz[0]/2), 240), 
                            bgCol="#999999", 
                            style=wx.TAB_TRAVERSAL|wx.SUNKEN_BORDER ) # panel for showing info for real-time sound. 
        pi["ip_spT"] = dict( pos=(pi['ip_sp']['sz'][0]+10, pi['ip_sp']['pos'][1]), 
                             sz=(self.w_sz[0]-pi['ip_sp']['sz'][0]-10, pi['ip_sp']['sz'][1]), 
                             bgCol="#999999", 
                             style=wx.TAB_TRAVERSAL|wx.SUNKEN_BORDER ) # panel for showing info for template WAV sound. 
        pi["sp"] = dict( pos=(pi['ip_sp']['pos'][0], pi['ip_sp']['pos'][1]+pi['ip_sp']['sz'][1]), 
                         sz=(pi['ip_sp']['sz'][0], int(PLL.INPUT_FRAMES_PER_BLOCK/2)),
                         bgCol="#000000", 
                         style=wx.TAB_TRAVERSAL|wx.SUNKEN_BORDER ) # real-time spectrogram panel 
        pi["spT"] = dict( pos=(pi['ip_spT']['pos'][0], pi['ip_spT']['pos'][1]+pi['ip_spT']['sz'][1]),
                          sz=(pi["ip_spT"]["sz"][0], pi["sp"]["sz"][1]), 
                          bgCol="#000000", 
                          style=wx.TAB_TRAVERSAL|wx.SUNKEN_BORDER ) # spectrogram panel for template 
        pStr = pi.keys()
        self.pl.spAD = np.zeros( (pi['sp']['sz'][1], pi['sp']['sz'][0]), dtype=np.uint8 ) # data for spectrogram of real-time recording
        self.pl.tSpAD= np.zeros( (pi['spT']['sz'][1], pi['spT']['sz'][0]), dtype=np.uint8 ) # data for spectrogram of template WAV 

        ### init frame
        wx.Frame.__init__(self, None, -1, "PyListener - %s"%VERSION, 
                          pos = w_pos, 
                          size = self.w_sz) 
                          #style=wx.DEFAULT_FRAME_STYLE^(wx.RESIZE_BORDER|wx.MAXIMIZE_BOX))
        self.SetBackgroundColour(bgCol)
        self.updateFrameSize()
        
        ### set up panels
        self.panel = {}
        for pk in pStr:
            if pk.startswith('sp'): # spctrogram panel
                if pi[pk]['sz'][1] > self.w_sz[1]-pi[pk]['pos'][1]:
                    msg = "%s, [WARNING], Spectrogram height is larger than allowed panel size.\n"%(get_time_stamp())
                    msg += "The lower frequency range will be cut off from the screen.\n"
                    msg += "Please consider lowering 'INPUT_BLOCK_TIME'."
                    show_msg(msg)
                self.panel[pk] = wx.Panel(self, name="%s_panel"%(pk), pos=pi[pk]['pos'], size=pi[pk]['sz'])
                self.panel[pk].Bind(wx.EVT_PAINT, self.onSPPaint)
            else:
                self.panel[pk] = SPanel.ScrolledPanel(self, name="%s_panel"%(pk), pos=pi[pk]["pos"], size=pi[pk]["sz"], style=pi[pk]["style"])
                self.panel[pk].SetBackgroundColour(pi[pk]["bgCol"])
        
        ### font setup
        if 'darwin' in sys.platform: _font = "Monaco"
        else: _font = "Courier"
        fontSz = 8
        self.base_script_font = wx.Font(20, wx.FONTFAMILY_DEFAULT, wx.NORMAL, wx.FONTWEIGHT_NORMAL, False, "Courier", wx.FONTENCODING_SYSTEM)
        self.fonts = [] # larger fonts as index gets larger 
        for i in range(5):
            self.fonts.append( wx.Font(fontSz, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, False, faceName=_font) )
            fontSz += 2
        
        self.gbs = {} # dictionary of gridBagSizer
        
        ### set up top button panel interface
        bw = 5 # border width for GridBagSizer
        bpBtns = ['selectTemplateFolder', 'selectTemplateFile', 'startStopListening'] 
        bpBtnLabels = ['Template folder', 'Template File', 'Start/Stop']
        self.gbs["bp"] = wx.GridBagSizer(0,0)
        row = 0; col = -1
        for i in range(len(bpBtns)):
            col += 1
            bn = bpBtns[i]
            btnSz = (150, -1)
            btn = wx.Button(self.panel["bp"], -1, bpBtnLabels[i], name=bn, size=btnSz)
            btn.Bind(wx.EVT_LEFT_DOWN, self.onBPButtonPress)
            if bn == 'startStopListening': bn += '_blue' # change bn for image file name
            set_img_for_btn( imgPath="input/img_%s.png"%(bn), btn=btn )
            self.gbs["bp"].Add(btn, pos=(row,col), span=(1,1), flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, border=bw)
        ### -----
        vlSz = (-1, 20)
        col += 1
        sLine = wx.StaticLine(self.panel["bp"], -1, size=vlSz, style=wx.LI_VERTICAL)
        self.gbs["bp"].Add(sLine, pos=(row,col), flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, border=bw)
        col += 1 
        sTxt = self.setupStaticText(self.panel["bp"], 'Input device: ', font=self.fonts[2])
        self.gbs["bp"].Add(sTxt, pos=(row,col), flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, border=bw)
        col += 1
        self.devNames_cho = wx.Choice(self.panel["bp"], -1, choices=self.pl.devNames)
        self.gbs["bp"].Add(self.devNames_cho, pos=(row,col), flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, border=bw)
        col += 1
        sLine = wx.StaticLine(self.panel["bp"], -1, size=vlSz, style=wx.LI_VERTICAL)
        self.gbs["bp"].Add(sLine, pos=(row,col), flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, border=bw)
        col += 1 
        sTxt = self.setupStaticText(self.panel["bp"], 'Auto-contrast level (1-100): (Template)', font=self.fonts[2])
        self.gbs["bp"].Add(sTxt, pos=(row,col), flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, border=bw)
        col += 1
        spin = wx.SpinCtrl(self.panel["bp"], -1, size=(50,-1), min=1, max=100, initial=int(self.pl.acThrTol_templ), name='templACThrTol_spin') 
        spin.Bind(wx.EVT_SPINCTRL, self.onChangeACthrTolerance)
        self.gbs["bp"].Add(spin, pos=(row,col), flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, border=bw)
        col += 1 
        sTxt = self.setupStaticText(self.panel["bp"], ' (Mic.)', font=self.fonts[2])
        self.gbs["bp"].Add(sTxt, pos=(row,col), flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, border=bw)
        col += 1
        spin = wx.SpinCtrl(self.panel["bp"], -1, size=(50,-1), min=1, max=100, initial=int(self.pl.acThrTol_nt), name='micACThrTol_spin') 
        spin.Bind(wx.EVT_SPINCTRL, self.onChangeACthrTolerance)
        self.gbs["bp"].Add(spin, pos=(row,col), flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, border=bw)
        col += 1
        sLine = wx.StaticLine(self.panel["bp"], -1, size=vlSz, style=wx.LI_VERTICAL)
        self.gbs["bp"].Add(sLine, pos=(row,col), flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, border=bw)
        col += 1
        chkB = wx.CheckBox(self.panel["bp"], -1, "Show CM in cols", style=wx.CHK_2STATE)
        chkB.SetValue(True)
        chkB.Bind(wx.EVT_CHECKBOX, self.onChangeShowCMinCol)
        self.gbs["bp"].Add(chkB, pos=(row,col), flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, border=bw)
        ### -----
        self.panel["bp"].SetSizer(self.gbs["bp"])
        self.gbs["bp"].Layout()
        self.panel["bp"].SetupScrolling()

        ### set up info panel for mic. streaming spectrogram
        bw = 5
        self.gbs["ip_sp"] = wx.GridBagSizer(0,0)
        ### -----
        row = 0; col = 0
        lbl = "Mic. streaming [ Sample-rate:%i, Channels:%i, Data-type:int16, Input-block-time:%.2f, Freq.-resolution:%.2f ]"%(PLL.RATE, PLL.CHANNELS, PLL.INPUT_BLOCK_TIME, PLL.FREQ_RES)
        sTxt = self.setupStaticText(self.panel["ip_sp"], lbl, name="ip_sp_info_sTxt", font=self.fonts[2])
        self.gbs["ip_sp"].Add(sTxt, pos=(row,col), span=(1,1), flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, border=bw)
        ### -----
        row += 1; col = 0
        self.txtSFInfo = wx.TextCtrl(self.panel["ip_sp"], -1, "", size=(pi['ip_sp']['sz'][0]-50, int(pi['ip_sp']['sz'][1]*0.75)), style=wx.TE_READONLY|wx.TE_MULTILINE) 
        self.txtSFInfo.SetBackgroundColour((200,200,200))
        self.gbs["ip_sp"].Add(self.txtSFInfo, pos=(row,col), span=(1,1), flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, border=bw)
        ### -----
        self.panel["ip_sp"].SetSizer(self.gbs["ip_sp"])
        self.gbs["ip_sp"].Layout()
        self.panel["ip_sp"].SetupScrolling()

        ### set up info panel for spectrogram of template WAV 
        bw = 5
        self.gbs["ip_spT"] = wx.GridBagSizer(0,0)
        ### -----
        row = 0; col = 0
        sTxt = self.setupStaticText(self.panel["ip_spT"], "Folder for template", font=self.fonts[2])
        self.gbs["ip_spT"].Add(sTxt, pos=(row,col), span=(1,2), flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, border=bw)
        col += 2 
        txt = wx.TextCtrl(self.panel["ip_spT"], -1, "", name="comp_fName", size=(250, -1), style=wx.TE_READONLY)
        txt.SetBackgroundColour((200,200,200))
        self.gbs["ip_spT"].Add(txt, pos=(row,col), span=(1,3), flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, border=bw)
        ### -----
        row += 1; col = 0
        chkB = wx.CheckBox(self.panel["ip_spT"], -1, "Apply All/No thresholds", name="comp_applyAllNone_chk", style=wx.CHK_2STATE)
        chkB.SetValue(True)
        chkB.Bind(wx.EVT_CHECKBOX, self.onChecked_allNoneChkBox)
        self.gbs["ip_spT"].Add(chkB, pos=(row,col), span=(1,5), flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, border=bw)
        ### ----- 
        row += 1; col = 0
        sTxt = self.setupStaticText(self.panel["ip_spT"], "Apply", font=self.fonts[2])
        self.gbs["ip_spT"].Add(sTxt, pos=(row,col), flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, border=bw)
        col += 1
        sTxt = self.setupStaticText(self.panel["ip_spT"], "Parameter", font=self.fonts[2])
        self.gbs["ip_spT"].Add(sTxt, pos=(row,col), flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, border=bw)
        col += 1
        sTxt = self.setupStaticText(self.panel["ip_spT"], "Min. Val.", font=self.fonts[2])
        self.gbs["ip_spT"].Add(sTxt, pos=(row,col), flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, border=bw)
        col += 1
        sTxt = self.setupStaticText(self.panel["ip_spT"], "Value", font=self.fonts[2])
        self.gbs["ip_spT"].Add(sTxt, pos=(row,col), flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, border=bw)
        col += 1
        sTxt = self.setupStaticText(self.panel["ip_spT"], "Max. Val.", font=self.fonts[2])
        self.gbs["ip_spT"].Add(sTxt, pos=(row,col), flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, border=bw)
        ### Make TextCtrl objects for accepting range of thresholds for parameters ----- 
        for key in self.pl.compParamList:
            if key in self.pl.indCPL: continue
            row += 1; col = 0
            self.setupTemplParamWidgets(self.panel["ip_spT"], row, self.gbs["ip_spT"], key, self.pl.compParamLabel[key], bw)
        row += 1; col = 0
        sLine = wx.StaticLine(self.panel["ip_spT"], -1, size=(pi["spT"]["sz"][0]-50, -1), style=wx.LI_HORIZONTAL)
        self.gbs["ip_spT"].Add(sLine, pos=(row,col), span=(1,5), flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, border=bw)
        for key in self.pl.indCPL:
            if not key in self.pl.compParamLabel: continue
            row += 1; col = 0
            self.setupTemplParamWidgets(self.panel["ip_spT"], row, self.gbs["ip_spT"], key, self.pl.compParamLabel[key], bw)
        ### ----- 
        self.panel["ip_spT"].SetSizer(self.gbs["ip_spT"])
        self.gbs["ip_spT"].Layout()
        self.panel["ip_spT"].SetupScrolling()
        
        ### set up menu
        menuBar = wx.MenuBar()
        fileMenu = wx.Menu()
        selectTemplate = fileMenu.Append(wx.Window.NewControlId(), item="Select folder for template\tCTRL+O", helpString="Select a folder of template WAV files.")
        self.Bind(wx.EVT_MENU, self.selectTemplate, selectTemplate)
        selectTemplateFile = fileMenu.Append(wx.Window.NewControlId(), item="Select a file for template\tALT+O", helpString="Select a WAV file for template.")
        self.Bind(wx.EVT_MENU, lambda event: self.selectTemplate('File'), selectTemplateFile)
        startStopListening = fileMenu.Append(wx.Window.NewControlId(), item="Start/Stop listening\tSPACE", helpString="Start/Stop real-time listening with a selected audio input device.")
        self.Bind(wx.EVT_MENU, lambda event: self.onBPButtonPress('startStopListening'), startStopListening)
        quit = fileMenu.Append(wx.Window.NewControlId(), item="Quit\tCTRL+Q", helpString="Quit this app.")
        self.Bind(wx.EVT_MENU, self.onClose, quit)
        menuBar.Append(fileMenu, "&File")
        self.SetMenuBar(menuBar)
        
        ### set up hot keys
        idSTFolder = wx.Window.NewControlId()
        idSTFile = wx.Window.NewControlId()
        idListen = wx.Window.NewControlId()
        idQuit = wx.Window.NewControlId()
        self.Bind(wx.EVT_MENU, self.selectTemplate, id = idSTFolder)
        self.Bind(wx.EVT_MENU, lambda event: self.selectTemplate('File'), id = idSTFile)
        self.Bind(wx.EVT_MENU, lambda event: self.onBPButtonPress('startStopListening'), id=idListen)
        self.Bind(wx.EVT_MENU, self.onClose, id = idQuit)
        accel_tbl = wx.AcceleratorTable([ 
                                            (wx.ACCEL_CMD,  ord('O'), idSTFolder),
                                            (wx.ACCEL_ALT,  ord('O'), idSTFile),
                                            (wx.ACCEL_NORMAL, wx.WXK_SPACE, idListen), 
                                            (wx.ACCEL_CMD,  ord('Q'), idQuit) 
                                        ]) 
        self.SetAcceleratorTable(accel_tbl)

        # set up status-bar
        #self.statusbar = self.CreateStatusBar(1)
        #self.sbTimer = None 
   
        self.Bind(wx.EVT_CLOSE, self.onClose) 
    
    #---------------------------------------------------------------------------
   
    def setupStaticText(self, panel, label, name=None, size=None, wrapWidth=None, font=None, fgColor=None, bgColor=None): 
        ''' initialize wx.StatcText widget.
        '''
        if DEBUG: print("PyListenerFrame.setupStaticText()")
        sTxt = wx.StaticText(panel, -1, label)
        if name != None: sTxt.SetName(name)
        if size != None: sTxt.SetSize(size)
        if wrapWidth != None: sTxt.Wrap(wrapWidth)
        if font != None: sTxt.SetFont(font)
        if fgColor != None: sTxt.SetForegroundColour(fgColor) 
        if bgColor != None: sTxt.SetBackgroundColour(bgColor)
        return sTxt

    #---------------------------------------------------------------------------
    
    def setupTemplParamWidgets(self, panel, row, gbs, key, label, bw):
        ''' initialize wx.TextCtrl widgets to show parameters of template WAV
        and min. & max. values for comparison with a sound fragment from continuous listening from microphone.
        ''' 
        if DEBUG: print("PyListenerFrame.setupTemplParamWidgets()")
        baseName = "comp_" + key
        minVal = ""
        val = ""
        maxVal = ""
        col = 0
        chkB = wx.CheckBox(panel, -1, "", name=baseName+"_chk", style=wx.CHK_2STATE)
        chkB.SetValue(True)
        self.chkB_comp.append(chkB)
        gbs.Add(chkB, pos=(row,col), flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, border=bw)
        col += 1
        sTxt = self.setupStaticText(panel, label, font=self.fonts[2])
        gbs.Add(sTxt, pos=(row,col), flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, border=bw)
        col += 1
        txt = wx.TextCtrl(panel, -1, minVal, name=baseName+"_min", size=(80, -1))
        gbs.Add(txt, pos=(row,col), flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, border=bw)
        col += 1
        txt = wx.TextCtrl(panel, -1, val, name=baseName, size=(80, -1), style=wx.TE_READONLY)
        txt.SetBackgroundColour((200,200,200))
        gbs.Add(txt, pos=(row,col), flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, border=bw)
        col += 1
        txt = wx.TextCtrl(panel, -1, maxVal, name=baseName+"_max", size=(80, -1))
        gbs.Add(txt, pos=(row,col), flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, border=bw)

    #---------------------------------------------------------------------------

    def onChecked_allNoneChkBox(self, event):
        ''' Turn on/off all checkboxes for comparison parameters 
        '''
        if DEBUG: print("PyListenerFrame.onChecked_allNoneChkBox()")
        obj = event.GetEventObject()
        turnOn = obj.GetValue()
        for chkB in self.chkB_comp: chkB.SetValue(turnOn)

    #---------------------------------------------------------------------------

    def onBPButtonPress(self, event): 
        ''' left-click on a button in button-panel,
        whether it was an explicit call, menu-item click or actual button press
        '''
        if DEBUG: print("PyListenerFrame.onBPButtonPress()")
        
        if type(event) == str:
        # explicit call of the fucntion with string, indicating which button press to emulate
            btnName = event
            btn = wx.FindWindowByName( btnName, self.panel["bp"] )
        elif type(event.GetEventObject()) == wx._core.Menu:
        # the function was called via menu-item 
            item = self.GetMenuBar().FindItemById(event.GetId())
            menuTxt = item.GetText().lower()
            if menuTxt.startswith('Select template WAV'):
                btnName = 'selectTemplateFolder' 
        else:
        # button press
            btn = event.GetEventObject()
            btnName = btn.GetName()
        
        if btnName == 'selectTemplateFolder':
            self.selectTemplate('Folder')
        elif btnName == 'selectTemplateFile':
            self.selectTemplate('File')
        elif btnName == 'startStopListening':
            if self.pl.isListening == False:
            # Currently not listening. Start listening.
                set_img_for_btn("input/img_startStopListening_red.png", btn) 
                ### set up a timer for draw spectrogram
                self.timers["updateSPTimer"] = wx.Timer(self)
                self.Bind(wx.EVT_TIMER, self.updateSpectrogram, self.timers["updateSPTimer"])
                self.timers["updateSPTimer"].Start(5)
                self.pl.startContMicListening(self.devNames_cho.GetSelection()) # start a thread to listen 
            else:
            # Currently listening. Stop.
                set_img_for_btn("input/img_startStopListening_blue.png", btn)
                self.stop_listening()
    
    #---------------------------------------------------------------------------
    
    def stop_listening(self): 
        ''' Stop listening from microphone.
        '''
        if DEBUG: print("PyListenerFrame.stop_listening()")
        ### end timer
        self.timers["updateSPTimer"].Stop()
        self.timers["updateSPTimer"] = None
        
        self.pl.endContMicListening()
        
        self.panel['ip_sp'].SetBackgroundColour(self.pi['ip_sp']['bgCol']) # restore bg-color of spectrogram panel
        self.panel['ip_sp'].Refresh()
        self.panel['sp'].Refresh()
    
    #---------------------------------------------------------------------------
    
    def updateSpectrogram(self, event):
        ''' Function periodically called by a timer,
        call a PyListener function to process mic. audio data,
        then, update visual displays including spectrogram.
        '''
        if DEBUG: print("PyListenerFrame.updateSpectrogram()")
        sfFlag, analyzedP, sfD = self.pl.procMicAudioData() # process recent mic audio data
        
        if sfFlag == 'started':
            self.panel['ip_sp'].SetBackgroundColour('#aaaa55') # change bg-color of spectrogram panel
            self.panel['ip_sp'].Refresh()
        elif sfFlag == 'stopped':
            self.panel['ip_sp'].SetBackgroundColour(self.pi['ip_sp']['bgCol']) # restore bg-color of spectrogram panel
            self.panel['ip_sp'].Refresh()
        
        if analyzedP != None: 
            rsltTxt = self.pl.logSFParms(analyzedP) # log paraemters of sound fragment 
            ### compare with template WAV data
            flag, _txt = self.compareSF2cParam(analyzedP) # Compare parameters of the captured sound fragment and various parameters.
            rsltTxt += _txt 
            if flag == True: # sound fragment was matched with all parameters 
                fp = self.pl.writeWAVfile(sfD) # save the captured sound fragment to WAV file
                rsltTxt += "WAV file, %s, is saved."%(fp)
            self.txtSFInfo.SetValue(rsltTxt) # show info and its comparison result on textCtrl
        
        self.panel['sp'].Refresh() # draw spectrogram
    
    #---------------------------------------------------------------------------
   
    def onSPPaint(self, event):
        ''' Spectrogram painting
        '''
        if DEBUG: print("PyListenerFrame.onSPPaint()")
        evtObj = event.GetEventObject()
        eoName = evtObj.GetName()
        dc = wx.PaintDC(evtObj)
        dc.SetBackground(wx.Brush('#333333'))
        dc.Clear()
        
        ### draw spectrogram 
        sfci = self.pl.sFragCI
        if eoName == "sp_panel": ad = self.pl.spAD 
        elif eoName == "spT_panel": ad = self.pl.tSpAD
        imgArr = np.stack( (ad, ad, ad), axis=2 )
        if eoName == "sp_panel" and len(self.pl.sfcis) > 0:
            for sfci in self.pl.sfcis: 
                imgArr[:,sfci[0]] = [200,0,0]
                imgArr[:,sfci[1]] = [200,0,0]
        img = wx.ImageFromBuffer(imgArr.shape[1], imgArr.shape[0], imgArr)
        bmp = wx.Bitmap(img) # wx.BitmapFromImage(img)
        dc.DrawBitmap(bmp, 0, 0)
      
        ### draw comparison result 
        if eoName == "sp_panel":
            dc.SetFont(self.fonts[2])
            texts=[]; coords = []; fg = []; bg = []
            y = 10
            fCol = dict(Matched=wx.Colour('#5555ff'), Unmatched=wx.Colour('#555555'))
            bCol = wx.Colour('#000000')
            for i in range(len(self.pl.sfcis)): 
                if self.pl.sfRslts[i] == 'N/A': continue
                lbl = self.pl.sfRslts[i]
                texts.append(lbl)
                coords.append( (self.pl.sfcis[i][0], y) )
                fg.append( fCol[lbl] )
                bg.append( bCol )
            dc.DrawTextList( texts, coords, fg, bg )
        
        ### draw additional notations 
        if ((eoName == "sp_panel") and (self.pl.sfP != None) and (not -1 in sfci)) \
          or ((eoName == "spT_panel") and (self.pl.templP != None)):
            if eoName == "sp_panel":
                t = self.pl.sfP
                lx = sfci[0]; rx = sfci[1]
                cmX = sfci[0] + t["centerOfMassX"]
                cmY = t["centerOfMassY"]
            elif eoName == "spT_panel":
                t = self.pl.templP
                lx = 0; rx = ad.shape[1]
                cmX = t["centerOfMassX"]
                cmY = t["centerOfMassY"]
            if rx > 0:
                dc.SetBrush(wx.Brush('#cccc00'))
                dc.SetPen(wx.Pen('#cccc00', 1))
                if self.flag_showCMInCol == True:
                    ### draw center-of-mass in each column
                    for ci in range(len(t["cmInColList"])):
                        cy = t["cmInColList"][ci]
                        if ci > 0: dc.DrawLine(lx+ci-1, py, lx+ci, cy)
                        py = cy 
                        #dc.DrawCircle(lx+ci, cy, 1)
                ### draw low frequency line
                dc.SetPen(wx.Pen('#5555ff', 1))
                dc.DrawLine(lx, t["lowFreqRow"], rx, t["lowFreqRow"])
                ### draw high frequency line
                dc.SetPen(wx.Pen('#ff5555', 1))
                dc.DrawLine(lx, t["highFreqRow"], rx, t["highFreqRow"]) 
                ### draw overall center-of-mass of spectrogram
                dc.SetBrush(wx.Brush('#00ff00'))
                dc.SetPen(wx.Pen('#00ff00', 1))
                dc.DrawCircle(cmX, cmY, 2)

        event.Skip()
    
    #---------------------------------------------------------------------------

    def onUpdateRate(self):
        ''' samplerate was updated (due to samplerate of template).
        change panel and frame size accordingly.
        '''
        if DEBUG: print("PyListenerFrame.onUpdateRate()")
        pi = self.pi
        pi['sp']['sz'] = ( pi['ip_sp']['sz'][0], int(PLL.INPUT_FRAMES_PER_BLOCK/2) )
        self.panel['sp'].SetSize( pi['sp']['sz'] )
        pi['spT']['sz'] = ( pi['ip_spT']['sz'][0], int(PLL.INPUT_FRAMES_PER_BLOCK/2) )
        self.panel['spT'].SetSize( pi['spT']['sz'] ) 
        self.updateFrameSize()
    
    #---------------------------------------------------------------------------
    
    def updateFrameSize(self):
        ''' set window size exactly to self.w_sz without menubar/border/etc.
        '''
        if DEBUG: print("PyListenerFrame.updateFrameSize()")
        m = 10 # margin
        self.w_sz[1] = self.pi['sp']['pos'][1]+self.pi['sp']['sz'][1] + m # adjust w_sz height to where spectrogram ends
        ### set window size exactly to self.w_sz without menubar/border/etc.
        _diff = (self.GetSize()[0]-self.GetClientSize()[0], self.GetSize()[1]-self.GetClientSize()[1])
        _sz = (self.w_sz[0]+_diff[0], self.w_sz[1]+_diff[1])
        self.SetSize(_sz) 
        self.Refresh()
    
    #---------------------------------------------------------------------------

    def selectTemplate(self, event):
        ''' selecting a folder which contains sample WAV files to form a template WAV data.
        '''
        if DEBUG: print("PyListenerFrame.selectTemplate()")
        if (type(event) == str and event == 'File'):
            dlg = wx.FileDialog(self, "Select a template wave file", CWD, wildcard="(*.wav)|*.wav")
            listenFlag = 'templateFile'
        else:
            dlg = wx.DirDialog(self, "Select a folder which contains WAV files for template. All WAV files in the selected folder will be considered as template.", CWD) 
            listenFlag = 'templateFolder'
        if dlg.ShowModal() == wx.ID_OK:
            if self.pl.isListening == True: self.onBPButtonPress('startStopListening') # if mic. stream is open, close it.
            fPath = dlg.GetPath()
            self.pl.templFP = fPath 
            __, __, params = self.pl.listen(flag=listenFlag, wavFP=fPath) # get analyzed parameters of template file(s).
            ### update mic. streaming text 
            lbl = "Mic. streaming [ Sample-rate:%i, Channels:%i, Data-type:int16, Input-block-time:%.2f, Freq.-resolution:%.2f ]"%(PLL.RATE, PLL.CHANNELS, PLL.INPUT_BLOCK_TIME, PLL.FREQ_RES)
            sTxt = wx.FindWindowByName( "ip_sp_info_sTxt", self.panel["ip_sp"] )
            sTxt.SetLabel(lbl)
            ### update template folder name
            txt = wx.FindWindowByName( "comp_fName", self.panel["ip_spT"] )
            txt.SetValue(path.basename(fPath))
            ### update comparison param. values
            pList = self.pl.compParamList
            for p in pList:
                bName = "comp_" + p
                if not p in self.pl.indCPL:
                    txt = wx.FindWindowByName( bName, self.panel["ip_spT"] )
                    value = params[p]
                    if type(value) == 'str': value = "%.3f"%(value)
                    if type(value) == 'list': value = str(value)
                    txt.SetValue("%s"%(value))
                txt = wx.FindWindowByName( bName+"_min", self.panel["ip_spT"] )
                value = params[p+"_min"]
                if type(value) == 'str': value = "%.3f"%(value)
                if type(value) == 'list': value = str(value)
                txt.SetValue("%s"%(value))
                txt = wx.FindWindowByName( bName+"_max", self.panel["ip_spT"] )
                value = params[p+"_max"]
                if type(value) == 'str': value = "%.3f"%(value)
                if type(value) == 'list': value = str(value)
                txt.SetValue("%s"%(value))

        self.panel['spT'].Refresh() # draw spectrogram 

    #---------------------------------------------------------------------------
   
    def compareSF2cParam(self, sfParams):
        ''' Get parameters to compare from UI
        and compare parameters of the captured sound fragment with them. 
        '''
        if DEBUG: print("PyListenerFrame.compareSF2cParam()")
        rslt = True # whether satisfying all checked parameters' min. max. value thresholds 
        rsltTxt = ""
        tParams2c = {} # template WAV parameters to compare

        if self.pl.templFP == None:
        # there's no selected template WAV
            _txt = "! Template WAV is not selected. No comparison was conducted. !"
            rsltTxt = "[%s]"%(_txt)
            writeFile( self.logFile, "%s, [MSG], %s\n"%(get_time_stamp(), _txt))
            rslt = False
            return rslt, rsltTxt 

        else:
            mm = ["min", "max"]
            for param in self.pl.compParamList: # through each comparison parameter 
                name = "comp_" + param 
                chkB = wx.FindWindowByName( name+"_chk", self.panel["ip_spT"] )
                if chkB.GetValue() == False: continue # this parameter is not checked. move on to the next parameter

                ### prepare min. and max. values (extracted from template WAV and editted by user) to compare with sound fragment params. 
                for mmn in mm:
                    _name = name + "_" + mmn
                    txt = wx.FindWindowByName( _name, self.panel["ip_spT"] )
                    txtVal = txt.GetValue().strip()
                    if txtVal == "": # the textCtrl is empty
                        continue # move to the next one, considering this one is satisfied
                    try:
                        th = float(txtVal) # threshold value
                    except:
                        self.onBPButtonPress('startStopListening') # stop listening
                        _txt = "%s, [MSG], !!! Value of %s is not a number. Comparison aborted. !!!\n"%(get_time_stamp(), _name)
                        writeFile( self.logFile, _txt)
                        show_msg(_txt)
                        rsltTxt += _txt
                        rslt = False
                        return rslt, rsltTxt 
                    tParams2c[param+"_"+mmn] = th
            if len(tParams2c) > 0:
                rslt, _txt = self.pl.compareParamsOfSF2T(sfParams, tParams2c) # compare sound fragment parmaeters 
                rsltTxt += "%s\n"%(_txt) 
       
        return rslt, rsltTxt 
     
    #---------------------------------------------------------------------------
    
    def onChangeACthrTolerance(self, event):
        if DEBUG: print("PyListenerFrame.onChangeACthrTolerance()")
        obj = event.GetEventObject()
        name = obj.GetName()
        val = obj.GetValue()
        if name.startswith('templ'): self.pl.acThrTol_templ = val
        elif name.startswith('mic'): self.pl.acThrTol_nt = val
   
    #---------------------------------------------------------------------------
    
    def onChangeShowCMinCol(self, event):
        if DEBUG: print("PyListenerFrame.onChangeShowCMinCol()")
        self.flag_showCMInCol = event.GetEventObject().GetValue() 

    #---------------------------------------------------------------------------

    def onClose(self, event):
        if DEBUG: print("PyListenerFrame.onClose()")
        if self.pl.th != None:
            self.stop_listening()
            self.pl.pa.terminate()
            wx.CallLater(10, self.Destroy)
        else:
            self.Destroy()

    #---------------------------------------------------------------------------

#===============================================================================

class PyListenerApp(wx.App):
    def OnInit(self):
        if DEBUG: print("PyListenerApp.OnInit()")
        self.frame = PyListenerFrame()
        self.frame.Show()
        self.SetTopWindow(self.frame)
        return True

#===============================================================================

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == '-w': GNU_notice(1)
        elif sys.argv[1] == '-c': GNU_notice(2)
    else:
        GNU_notice(0)
        app = PyListenerApp(redirect = False)
        app.MainLoop()



