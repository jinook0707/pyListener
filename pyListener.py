# coding: UTF-8

"""
PyListener
An open-source software written in Python for sound comparison. 
Currently, its main functionality is to listen to sound from microphone
and save a recognized sound as WAV file, when it is similar with a 
loaded template sound.

This was programmed and tested in macOS 10.13.

Jinook Oh, Cognitive Biology department, University of Vienna
September 2019.

------------------------------------------------------------------------
Copyright (C) 2019 Jinook Oh, W. Tecumseh Fitch 
- Contact: jinook.oh@univie.ac.at, tecumseh.fitch@univie.ac.at

This program is free software: you can redistribute it and/or modify it 
under the terms of the GNU General Public License as published by the 
Free Software Foundation, either version 3 of the License, or (at your 
option) any later version.

This program is distributed in the hope that it will be useful, but 
WITHOUT ANY WARRANTY; without even the implied warranty of 
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU 
General Public License for more details.

You should have received a copy of the GNU General Public License along 
with this program.  If not, see <http://www.gnu.org/licenses/>.
------------------------------------------------------------------------
"""

import sys, wave
from os import path, getcwd, mkdir 
from copy import copy

import wx
import wx.lib.scrolledpanel as SPanel 
import numpy as np
from skimage import filters

import pyListenerLib as PLL
import pyLSpectrogram as PLSp
from fFuncNClasses import GNU_notice, writeFile, get_time_stamp
from fFuncNClasses import show_msg, set_img_for_btn, getWXFonts
from fFuncNClasses import setupStaticText

__version__ = 'v.0.2'
'''
# 0.1: Initial development - 2018.July
# 0.2: Changed to comparing parameters instead of correlation to 
        auto-correlation, separated audio signal processing to 
        pyListenerLib.py and many parts of user interface were updated. 
        - 2019.Aug
'''

CWD = getcwd() # current working directory
DEBUG = False 

#=======================================================================

class PyListenerFrame(wx.Frame):
    """ PyListenerFrame is for dealing with user-interface, and 
    periodically process audio data form microphone 
    and display spectrogram with the data.

    Attributes: 
        Each attribute is declared and described at the top section 
        of __init__ before wx.Frame.__init__
    """
    def __init__(self):
        if DEBUG: print("PyListenerFrame.__init__()")
        if path.isdir('log') == False: mkdir('log')
        if path.isdir('recordings') == False: mkdir('recordings')

        ##### beginning of class attributes -----
        self.flag_showCMInCol = True # whether to show center-of-mass
          # in each column in spectrogram
        self.logFile = "log/log_%s.txt"%(get_time_stamp()[:-9]) # determine 
          # log file name, [:-9] cut off hh_mm_ss from timestamp 

        self.spBmp = None # spectrogram image (bmp) 
        self.timers = {} # contain wxPython's timers for this class
        self.gbs = {}  # dictionary of gridBagSizer
        self.chkB_comp = [] # checkboxes to enable comparison parameters
        w_pos = (0, 25) 
        self.w_sz = [
                        wx.Display(0).GetGeometry()[2], 
                        wx.Display(0).GetGeometry()[3]-w_pos[1]-100
                    ] # initial window size
        self.fonts = getWXFonts() # get fonts 
        pi = {} 
        # top panel for buttons and some settings
        pi["bp"] = dict(pos=(0, 0), 
                        sz=(self.w_sz[0], 50), 
                        bgCol="#cccccc", 
                        style=wx.TAB_TRAVERSAL|wx.SUNKEN_BORDER)
        # panel for showing info for real-time sound. 
        pi["ip_sp"] = dict(pos=(0, pi['bp']['sz'][1]), 
                           sz=(int(self.w_sz[0]/2), 150), 
                           bgCol="#999999", 
                           style=wx.TAB_TRAVERSAL|wx.SUNKEN_BORDER)
        # panel for showing info for template WAV sound.
        ipspSz = pi["ip_sp"]["sz"]
        ipspPos = pi["ip_sp"]["pos"]
        pi["ip_spT"] = dict(pos=(ipspSz[0]+10, ipspPos[1]), 
                            sz=(self.w_sz[0]-ipspSz[0]-10, ipspSz[1]), 
                            bgCol="#999999", 
                            style=wx.TAB_TRAVERSAL|wx.SUNKEN_BORDER) 
        # real-time spectrogram panel 
        pi["sp"] = dict(pos=(ipspPos[0], ipspPos[1]+ipspSz[1]), 
                        sz=(ipspSz[0], int(PLL.INPUT_FRAMES_PER_BLOCK/2)),
                        bgCol="#000000", 
                        style=wx.TAB_TRAVERSAL|wx.SUNKEN_BORDER)
        ipsptPos = pi["ip_spT"]["pos"]
        ipsptSz = pi["ip_spT"]["sz"]
        # spectrogram panel for template 
        pi["spT"] = dict(pos=(ipsptPos[0], ipsptPos[1]+ipsptSz[1]),
                         sz=(ipsptSz[0], pi["sp"]["sz"][1]), 
                         bgCol="#000000", 
                         style=wx.TAB_TRAVERSAL|wx.SUNKEN_BORDER)
        self.pi = pi # store panel information  
        self.panel = {} # dictionary to put panels
        ### init PyListener class 
        self.pl = PLL.PyListener(self, self, self.logFile) 
        if self.pl.devIdx == []: self.onClose(None)
        ##### end of class attributes -----

        # numpy array for spectrogram of sound from mic. 
        self.pl.spAD = np.zeros( 
                        (pi['sp']['sz'][1], pi['sp']['sz'][0]), 
                        dtype=np.uint8 
                               )
        # numpy array for spectrogram of template WAV 
        self.pl.tSpAD= np.zeros( 
                        (pi['spT']['sz'][1], pi['spT']['sz'][0]), 
                        dtype=np.uint8 
                               ) 

        ### init frame
        wx.Frame.__init__(self, None, -1, 
                          "PyListener - %s"%(__version__), 
                          pos = w_pos, size = self.w_sz) 
        self.SetBackgroundColour('#333333')
        self.updateFrameSize()
        
        ### create (scroll) panels
        for pk in pi.keys():
            if pk == 'sp': # spctrogram panels
                self.panel[pk] = PLSp.SpectrogramPanel(self, 
                                                       pi["sp"]["pos"], 
                                                       pi["sp"]["sz"], 
                                                       self.pl)
            else:
                self.panel[pk] = SPanel.ScrolledPanel(
                                                      self, 
                                                      name="%s_panel"%(pk), 
                                                      pos=pi[pk]["pos"], 
                                                      size=pi[pk]["sz"], 
                                                      style=pi[pk]["style"],
                                                     )
                self.panel[pk].SetBackgroundColour(pi[pk]["bgCol"]) 
                if pk == 'spT': # template spectrogram panel
                    self.panel[pk].Bind(wx.EVT_PAINT, self.onPaintSPT)
        
        ##### beginning of setting up top button panel interface -----
        bw = 5 # border width for GridBagSizer
        ### generate buttons
        bpBtns = [
                    'selectTemplateFolder', 
                    'selectTemplateFile', 
                    'startStopListening',
                 ] 
        bpBtnLabels = [
                    'Template folder', 
                    'Template File', 
                    'Start/Stop',
                      ]
        self.gbs["bp"] = wx.GridBagSizer(0,0)
        row = 0; col = -1
        for i in range(len(bpBtns)):
            col += 1
            bn = bpBtns[i]
            btnSz = (150, -1)
            btn = wx.Button(
                            self.panel["bp"], 
                            -1, 
                            bpBtnLabels[i], 
                            name=bn, 
                            size=btnSz,
                           )
            btn.Bind(wx.EVT_LEFT_DOWN, self.onBPButtonPress)
            if bn == 'startStopListening':
                bn += '_blue'  # change bn for image file name
            set_img_for_btn( imgPath="input/img_%s.png"%(bn), btn=btn )
            self.gbs["bp"].Add(
                                btn, 
                                pos=(row,col), 
                                span=(1,1), 
                                flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, 
                                border=bw,
                               )
        ### -----
        vlSz = (-1, 20) # size of vertical line seprator
        col += 1
        self.gbs["bp"].Add(
                            wx.StaticLine(
                                            self.panel["bp"],
                                            -1,
                                            size=vlSz,
                                            style=wx.LI_VERTICAL,
                                         ),
                            pos=(row,col), 
                            flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, 
                            border=bw,
                          ) # vertical line separator
        col += 1 
        sTxt = setupStaticText(
                                    self.panel["bp"], 
                                    'Input device: ', 
                                    font=self.fonts[2],
                              )
        self.gbs["bp"].Add(
                            sTxt, 
                            pos=(row,col), 
                            flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, 
                            border=bw,
                          )
        col += 1
        self.devNames_cho = wx.Choice(
                                        self.panel["bp"], 
                                        -1, 
                                        choices=self.pl.devNames,
                                     )
        self.gbs["bp"].Add(
                            self.devNames_cho, 
                            pos=(row,col), 
                            flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, 
                            border=bw,
                          )
        col += 1
        self.gbs["bp"].Add(
                            wx.StaticLine(
                                            self.panel["bp"],
                                            -1,
                                            size=vlSz,
                                            style=wx.LI_VERTICAL,
                                         ),
                            pos=(row,col), 
                            flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, 
                            border=bw,
                          ) # vertical line separator
        col += 1 
        sTxt = setupStaticText(
                                    self.panel["bp"], 
                                    'Auto-contrast level (1-100): (Template)', 
                                    font=self.fonts[2],
                              )
        self.gbs["bp"].Add(
                            sTxt, 
                            pos=(row,col), 
                            flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, 
                            border=bw,
                          )
        col += 1
        spin = wx.SpinCtrl(
                            self.panel["bp"], 
                            -1, 
                            size=(50,-1), 
                            min=1, 
                            max=100, 
                            initial=int(self.pl.acThrTol_templ), 
                            name='templACThrTol_spin',
                          ) 
        spin.Bind(wx.EVT_SPINCTRL, self.onChangeACthrTolerance)
        self.gbs["bp"].Add(
                            spin, 
                            pos=(row,col), 
                            flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, 
                            border=bw,
                          )
        col += 1 
        sTxt = setupStaticText(
                                    self.panel["bp"], 
                                    ' (Mic.)', 
                                    font=self.fonts[2],
                              )
        self.gbs["bp"].Add(
                            sTxt, 
                            pos=(row,col), 
                            flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL,
                            border=bw,
                          )
        col += 1
        spin = wx.SpinCtrl(
                            self.panel["bp"], 
                            -1, 
                            size=(50,-1), 
                            min=1, 
                            max=100, 
                            initial=int(self.pl.acThrTol_nt), 
                            name='micACThrTol_spin',
                          ) 
        spin.Bind(wx.EVT_SPINCTRL, self.onChangeACthrTolerance)
        self.gbs["bp"].Add(
                            spin, 
                            pos=(row,col), 
                            flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, 
                            border=bw,
                          )
        col += 1
        self.gbs["bp"].Add(
                            wx.StaticLine(
                                            self.panel["bp"],
                                            -1,
                                            size=vlSz,
                                            style=wx.LI_VERTICAL,
                                         ),
                            pos=(row,col), 
                            flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, 
                            border=bw,
                          ) # vertical line separator
        col += 1
        chkB = wx.CheckBox(
                            self.panel["bp"], 
                            -1, 
                            "Show CM in cols", 
                            style=wx.CHK_2STATE
                          )
        chkB.SetValue(True)
        chkB.Bind(wx.EVT_CHECKBOX, self.onChangeShowCMinCol)
        self.gbs["bp"].Add(
                            chkB, 
                            pos=(row,col), 
                            flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, 
                            border=bw,
                          )
        ### -----
        self.panel["bp"].SetSizer(self.gbs["bp"])
        self.gbs["bp"].Layout()
        self.panel["bp"].SetupScrolling()
        ##### end of setting up top button panel interface -----

        ##### beginning of setting up info panel 
        #####   for mic. streaming spectrogram -----
        bw = 5
        self.gbs["ip_sp"] = wx.GridBagSizer(0,0)
        ### -----
        row = 0; col = 0
        self.txtSFInfo = wx.TextCtrl(
                                     self.panel["ip_sp"], 
                                     -1, 
                                     "", 
                                     size=(ipspSz[0]-20, int(ipspSz[1]*0.9)),
                                     style=wx.TE_READONLY|wx.TE_MULTILINE,
                                    ) 
        self.txtSFInfo.SetBackgroundColour((200,200,200))
        self.gbs["ip_sp"].Add(
                                self.txtSFInfo, 
                                pos=(row,col), 
                                span=(1,1), 
                                flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, 
                                border=bw,
                             )
        ### -----
        self.panel["ip_sp"].SetSizer(self.gbs["ip_sp"])
        self.gbs["ip_sp"].Layout()
        self.panel["ip_sp"].SetupScrolling()
        ##### end of setting up info panel 
        #####   for mic. streaming spectrogram -----

        ##### beginning of setting up info panel 
        #####   for spectrogram of template WAV -----
        bw = 5
        self.gbs["ip_spT"] = wx.GridBagSizer(0,0)
        ### -----
        row = 0; col = 0
        sTxt = setupStaticText(
                                    self.panel["ip_spT"], 
                                    "Folder for template", 
                                    font=self.fonts[2],
                              )
        self.gbs["ip_spT"].Add(
                                sTxt, 
                                pos=(row,col), 
                                span=(1,2), 
                                flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, 
                                border=bw,
                              )
        col += 2 
        txt = wx.TextCtrl(
                            self.panel["ip_spT"], 
                            -1, 
                            "", 
                            name="comp_fName", 
                            size=(250, -1), 
                            style=wx.TE_READONLY
                         )
        txt.SetBackgroundColour((200,200,200))
        self.gbs["ip_spT"].Add(
                                txt, 
                                pos=(row,col), 
                                span=(1,3), 
                                flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, 
                                border=bw,
                              )
        ### -----
        row += 1; col = 0
        chkB = wx.CheckBox(
                            self.panel["ip_spT"], 
                            -1, 
                            "Apply All/No thresholds", 
                            name="comp_applyAllNone_chk", 
                            style=wx.CHK_2STATE,
                          )
        chkB.SetValue(True)
        chkB.Bind(wx.EVT_CHECKBOX, self.onChecked_allNoneChkBox)
        self.gbs["ip_spT"].Add(
                                chkB, 
                                pos=(row,col), 
                                span=(1,5), 
                                flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, 
                                border=bw,
                              )
        ### ----- 
        row += 1; col = 0
        sTxt = setupStaticText(
                                    self.panel["ip_spT"], 
                                    "Apply", 
                                    font=self.fonts[2],
                              )
        self.gbs["ip_spT"].Add(
                                sTxt, 
                                pos=(row,col), 
                                flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, 
                                border=bw,
                              )
        col += 1
        sTxt = setupStaticText(
                                    self.panel["ip_spT"], 
                                    "Parameter", 
                                    font=self.fonts[2],
                              )
        self.gbs["ip_spT"].Add(
                                sTxt, 
                                pos=(row,col), 
                                flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, 
                                border=bw,
                              )
        col += 1
        sTxt = setupStaticText(
                                    self.panel["ip_spT"], 
                                    "Min. Val.", 
                                    font=self.fonts[2],
                              )
        self.gbs["ip_spT"].Add(
                                sTxt, 
                                pos=(row,col), 
                                flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, 
                                border=bw,
                              )
        col += 1
        sTxt = setupStaticText(
                                    self.panel["ip_spT"], 
                                    "Value", 
                                    font=self.fonts[2],
                              )
        self.gbs["ip_spT"].Add(
                                sTxt, 
                                pos=(row,col), 
                                flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, 
                                border=bw,
                              )
        col += 1
        sTxt = setupStaticText(
                                    self.panel["ip_spT"], 
                                    "Max. Val.", 
                                    font=self.fonts[2],
                              )
        self.gbs["ip_spT"].Add(
                                sTxt, 
                                pos=(row,col), 
                                flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, 
                                border=bw,
                              )
        ### Make TextCtrl objects 
        ### for accepting range of thresholds for parameters ----- 
        for key in self.pl.compParamList:
            if key in self.pl.indCPL: continue
            row += 1; col = 0
            self.setupTemplParamWidgets(
                                        self.panel["ip_spT"], 
                                        self.gbs["ip_spT"], 
                                        row, 
                                        key, 
                                        self.pl.compParamLabel[key], 
                                        bw
                                       )
        row += 1; col = 0
        sLine = wx.StaticLine(
                                self.panel["ip_spT"], 
                                -1, 
                                size=(pi["spT"]["sz"][0]-50, -1),
                                style=wx.LI_HORIZONTAL
                             )
        self.gbs["ip_spT"].Add(
                                sLine, 
                                pos=(row,col), 
                                span=(1,5), 
                                flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, 
                                border=bw,
                              )
        for key in self.pl.indCPL:
            if key not in self.pl.compParamLabel: continue
            row += 1; col = 0
            self.setupTemplParamWidgets(
                                        self.panel["ip_spT"], 
                                        self.gbs["ip_spT"], 
                                        row, 
                                        key, 
                                        self.pl.compParamLabel[key], 
                                        bw,
                                       )
        ### ----- 
        self.panel["ip_spT"].SetSizer(self.gbs["ip_spT"])
        self.gbs["ip_spT"].Layout()
        self.panel["ip_spT"].SetupScrolling()
        ##### end of setting up info panel 
        #####   for spectrogram of template WAV -----
        
        ### set up menu
        menuBar = wx.MenuBar()
        pyListenerMenu = wx.Menu()
        selectTemplate = pyListenerMenu.Append(
                            wx.Window.NewControlId(), 
                            item="Select folder for template\tCTRL+O",
                                        )
        self.Bind(wx.EVT_MENU, self.selectTemplate, selectTemplate)
        selectTemplateFile = pyListenerMenu.Append(
                            wx.Window.NewControlId(), 
                            item="Select a file for template\tALT+O", 
                                            )
        self.Bind(wx.EVT_MENU, 
                  lambda event: self.selectTemplate('File'), 
                  selectTemplateFile)
        startStopListening = pyListenerMenu.Append(
                            wx.Window.NewControlId(), 
                            item="Start/Stop listening\tSPACE",
                                            )
        self.Bind(wx.EVT_MENU, 
                  lambda event: self.onBPButtonPress('startStopListening'),
                  startStopListening)
        quit = pyListenerMenu.Append(
                            wx.Window.NewControlId(), 
                            item="Quit\tCTRL+Q",
                              )
        self.Bind(wx.EVT_MENU, self.onClose, quit)
        menuBar.Append(pyListenerMenu, "&pyListener")
        self.SetMenuBar(menuBar)
        
        ### set up hot keys
        idSTFolder = wx.Window.NewControlId()
        idSTFile = wx.Window.NewControlId()
        idListen = wx.Window.NewControlId()
        idQuit = wx.Window.NewControlId()
        self.Bind(wx.EVT_MENU, 
                  self.selectTemplate, 
                  id=idSTFolder)
        self.Bind(wx.EVT_MENU,
                  lambda event: self.selectTemplate('File'),
                  id=idSTFile)
        self.Bind(wx.EVT_MENU,
                  lambda event: self.onBPButtonPress('startStopListening'),
                  id=idListen)
        self.Bind(wx.EVT_MENU, self.onClose, id=idQuit)
        accel_tbl = wx.AcceleratorTable([ 
                                    (wx.ACCEL_CMD,  ord('O'), idSTFolder),
                                    (wx.ACCEL_ALT,  ord('O'), idSTFile),
                                    (wx.ACCEL_NORMAL, wx.WXK_SPACE, idListen),
                                    (wx.ACCEL_CMD,  ord('Q'), idQuit), 
                                        ]) 
        self.SetAcceleratorTable(accel_tbl)

        # set up status-bar
        #self.statusbar = self.CreateStatusBar(1)
        #self.sbTimer = None 
   
        self.Bind(wx.EVT_CLOSE, self.onClose) 

    #-------------------------------------------------------------------
    
    def setupTemplParamWidgets(self, panel, gbs, row, key, label, bw):
        """ Create wx.TextCtrl widgets to show parameters of 
        template WAV and min. & max. values for comparison with a sound
        fragment from continuous listening from microphone.
        
        Args:
            panel (wx.Panel): Panel to display created widgets.
            gbs (wx.gridBagSizer): GridBagSizer to put the created widgets in.
            row (int): Row in GridBagSizer to position the created widgets in.
            key (str): Key (sound parameter) in PyListener.compParamList.
            label (str): Descriptive label for this parameter.
            bw (int): Border width for gridBagSizer.

        Returns:
            None
        """ 
        if DEBUG: print("PyListenerFrame.setupTemplParamWidgets()")
        baseName = "comp_" + key
        minVal = ""
        val = ""
        maxVal = ""
        col = 0
        chkB = wx.CheckBox(
                            panel, 
                            -1, 
                            "", 
                            name=baseName+"_chk", 
                            style=wx.CHK_2STATE,
                          )
        chkB.SetValue(True)
        self.chkB_comp.append(chkB)
        gbs.Add(
                    chkB, 
                    pos=(row,col), 
                    flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, 
                    border=bw,
               )
        col += 1
        sTxt = setupStaticText(
                                    panel, 
                                    label, 
                                    font=self.fonts[2],
                              )
        gbs.Add(
                    sTxt, 
                    pos=(row,col), 
                    flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, 
                    border=bw,
               )
        col += 1
        txt = wx.TextCtrl(
                            panel, 
                            -1, 
                            minVal, 
                            name=baseName+"_min", 
                            size=(80, -1),
                         )
        gbs.Add(
                    txt, 
                    pos=(row,col), 
                    flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, 
                    border=bw,
               )
        col += 1
        txt = wx.TextCtrl(
                            panel, 
                            -1, 
                            val, 
                            name=baseName, 
                            size=(80, -1), 
                            style=wx.TE_READONLY,
                         )
        txt.SetBackgroundColour((200,200,200))
        gbs.Add(
                    txt, 
                    pos=(row,col), 
                    flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, 
                    border=bw,
               )
        col += 1
        txt = wx.TextCtrl(
                            panel, 
                            -1, 
                            maxVal, 
                            name=baseName+"_max", 
                            size=(80, -1),
                         )
        gbs.Add(
                    txt, 
                    pos=(row,col), 
                    flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, 
                    border=bw,
               )

    #-------------------------------------------------------------------

    def onChecked_allNoneChkBox(self, event):
        """ Turn on/off all checkboxes for comparison parameters 
        
        Args:
            event (wx.Event)

        Returns:
            None
        """ 
        if DEBUG: print("PyListenerFrame.onChecked_allNoneChkBox()")
        obj = event.GetEventObject()
        turnOn = obj.GetValue()
        for chkB in self.chkB_comp: chkB.SetValue(turnOn)

    #-------------------------------------------------------------------

    def onBPButtonPress(self, event): 
        """ Process when left-click on a button in button-panel,
        whether it was an explicit call, menu-item click or actual 
        button press.

        Args: event (wx.Event)
        
        Returns: None
        """ 
        if DEBUG: print("PyListenerFrame.onBPButtonPress()")
        
        if type(event) == str:
        # explicit call of the fucntion with string, 
        # indicating which button press to emulate
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
                self.Bind(wx.EVT_TIMER, 
                          self.updateSpectrogram, 
                          self.timers["updateSPTimer"])
                self.timers["updateSPTimer"].Start(5)
                # start a thread to listen 
                self.pl.startContMicListening(self.devNames_cho.GetSelection())
            else:
            # Currently listening. Stop.
                set_img_for_btn("input/img_startStopListening_blue.png", btn)
                self.stop_listening()
    
    #-------------------------------------------------------------------
    
    def stop_listening(self): 
        """ Stop listening from microphone.

        Args: None
        
        Returns: None
        """ 
        if DEBUG: print("PyListenerFrame.stop_listening()")
        ### end timer
        self.timers["updateSPTimer"].Stop()
        self.timers["updateSPTimer"] = None
        
        self.pl.endContMicListening()
        
        # restore bg-color of spectrogram panel
        self.panel['ip_sp'].SetBackgroundColour(self.pi['ip_sp']['bgCol'])
        self.panel['ip_sp'].Refresh()
        self.panel['sp'].Refresh()
    
    #-------------------------------------------------------------------
    
    def updateSpectrogram(self, event):
        """ Function periodically called by a timer.
        Call a PyListener function to process mic. audio data,
        then, update visual displays including spectrogram.

        Args: event (wx.Event)
        
        Returns: None
        """
        if DEBUG: print("PyListenerFrame.updateSpectrogram()")
        # process recent mic audio data
        sfFlag, analyzedP, sfD = self.pl.procMicAudioData() 
        
        if sfFlag == 'started':
            # change bg-color of spectrogram panel
            self.panel['ip_sp'].SetBackgroundColour('#aaaa55') 
            self.panel['ip_sp'].Refresh()
        elif sfFlag == 'stopped':
            # restore bg-color of spectrogram panel
            self.panel['ip_sp'].SetBackgroundColour(self.pi['ip_sp']['bgCol'])
            self.panel['ip_sp'].Refresh()
        
        if analyzedP != None: 
            # log paraemters of sound fragment 
            rsltTxt = self.pl.logSFParms(analyzedP) 
            ### compare with template WAV data
            # Compare parameters of the captured sound fragment and 
            # parameters from template WAV data.
            flag, _txt = self.compareSF2cParam(analyzedP) 
            rsltTxt += _txt 
            if flag == True:
            # sound fragment was matched with all parameters 
                # save the captured sound fragment to WAV file
                fp = self.pl.writeWAVfile(sfD) 
                rsltTxt += "WAV file, %s, is saved."%(fp)
            # show info and its comparison result on textCtrl
            self.txtSFInfo.SetValue(rsltTxt) 
        
        self.panel['sp'].Refresh() # draw spectrogram
    
    #-------------------------------------------------------------------
    
    def postPaintSP(self, dc):
        """ This function is called from 'onPaint' function of 
        pyLSpectrogram.SpectrogramPanel. SpectrogramPanel draws basic
        spectrogram. This function draws results of analysis of pyListener.

        Args:
            dc (wx.PaintDC): PaintDC of SpectrogramPanel

        Returns:
            None
        """
        ### draw red lines around captured sound fragments 
        dc.SetPen(wx.Pen('#cc0000', 1))
        if len(self.pl.sfcis) > 0:
            for sfci in self.pl.sfcis:
                dc.DrawLine(sfci[0], 0, sfci[0], self.pi["sp"]["sz"][1]) 
                dc.DrawLine(sfci[1], 0, sfci[1], self.pi["sp"]["sz"][1]) 

        ### draw comparison result 
        dc.SetFont(self.fonts[2])
        texts=[]; coords = []; fg = []; bg = []
        y = 15
        fCol = dict(Matched=wx.Colour('#5555ff'), 
                    Unmatched=wx.Colour('#555555'))
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
        sfci = self.pl.sFragCI
        if self.pl.sfP != None and not -1 in sfci:
        # analyzed parameters of sound fragment is available 
            p = self.pl.sfP
            lx = sfci[0]; rx = sfci[1]
            cmX = sfci[0] + p["centerOfMassX"]
            cmY = p["centerOfMassY"]
            if rx > 0: self.drawParamsOfSound(dc, p, lx, rx, cmX, cmY) 
    
    #-------------------------------------------------------------------
   
    def onPaintSPT(self, event):
        """ Draw spectrogram of template WAV data.

        Args: event (wx.Event)

        Returns: None
        """ 
        if DEBUG: print("PyListenerFrame.onPaintSPT()")
        evtObj = event.GetEventObject()
        eoName = evtObj.GetName()
        dc = wx.PaintDC(evtObj)
        dc.SetBackground(wx.Brush('#333333'))
        dc.Clear()
        
        ### draw spectrogram 
        ad = self.pl.tSpAD
        imgArr = np.stack( (ad, ad, ad), axis=2 )
        img = wx.ImageFromBuffer(imgArr.shape[1], imgArr.shape[0], imgArr)
        bmp = wx.Bitmap(img) # wx.BitmapFromImage(img)
        dc.DrawBitmap(bmp, 0, 0)
     
        ### draw additional notations 
        if self.pl.templP != None: # analyzed parameters are available
            p = self.pl.templP
            lx = 0; rx = ad.shape[1]
            cmX = p["centerOfMassX"]
            cmY = p["centerOfMassY"]
            if rx > 0:
                self.drawParamsOfSound(dc, p, lx, rx, cmX, cmY)

        event.Skip()

    #-------------------------------------------------------------------
    
    def drawParamsOfSound(self, dc, p, lx, rx, cmX, cmY):
        """ Draw some parameters of sound on spectrogram.

        Args:
            dc (wx.PaintDC): PaintDC of SpectrogramPanel.
            p (dict): Parameters of sound.
            lx (int): Left-most x-coordinate of sound in panel.
            rx (int): Right-most x-coordinate of sound in panel.
            cmX (int): X-coordinate of center-of-mass in panel.
            cmY (int): Y-coordinate of center-of-mass in panel.

        Return:
            None
        """
        dc.SetBrush(wx.Brush('#cccc00'))
        dc.SetPen(wx.Pen('#cccc00', 1))
        if self.flag_showCMInCol == True:
            ### draw center-of-mass in each column
            for ci in range(len(p["cmInColList"])):
                cy = p["cmInColList"][ci]
                if ci > 0: dc.DrawLine(lx+ci-1, py, lx+ci, cy)
                py = cy 
                #dc.DrawCircle(lx+ci, cy, 1)
        ### draw low frequency line
        dc.SetPen(wx.Pen('#5555ff', 1))
        dc.DrawLine(lx, p["lowFreqRow"], rx, p["lowFreqRow"])
        ### draw high frequency line
        dc.SetPen(wx.Pen('#ff5555', 1))
        dc.DrawLine(lx, p["highFreqRow"], rx, p["highFreqRow"]) 
        ### draw overall center-of-mass of spectrogram
        dc.SetBrush(wx.Brush('#00ff00'))
        dc.SetPen(wx.Pen('#00ff00', 1))
        dc.DrawCircle(cmX, cmY, 2)

    #-------------------------------------------------------------------

    def onUpdateRate(self):
        """ Samplerate was updated (due to samplerate of template).
        change panel and frame size accordingly.

        Args: None

        Returns: None
        """ 
        if DEBUG: print("PyListenerFrame.onUpdateRate()")

        pi = self.pi
        pi['sp']['sz'] = (pi['ip_sp']['sz'][0], 
                          int(PLL.INPUT_FRAMES_PER_BLOCK/2))
        self.panel['sp'].SetSize( pi['sp']['sz'] )
        pi['spT']['sz'] = (pi['ip_spT']['sz'][0], 
                           int(PLL.INPUT_FRAMES_PER_BLOCK/2))
        self.panel['spT'].SetSize( pi['spT']['sz'] ) 
        self.updateFrameSize()
    
    #-------------------------------------------------------------------
    
    def updateFrameSize(self):
        """ Set window size exactly to self.w_sz without menubar/border/etc.

        Args: None

        Returns: None
        """
        if DEBUG: print("PyListenerFrame.updateFrameSize()")
        m = 10 # margin
        # adjust w_sz height to where spectrogram ends
        self.w_sz[1] = self.pi['sp']['pos'][1]+self.pi['sp']['sz'][1] + m 
        ### set window size exactly to self.w_sz 
        ### without menubar/border/etc.
        _diff = (self.GetSize()[0]-self.GetClientSize()[0], 
                 self.GetSize()[1]-self.GetClientSize()[1])
        _sz = (self.w_sz[0]+_diff[0], self.w_sz[1]+_diff[1])
        self.SetSize(_sz) 
        self.Refresh()
    
    #-------------------------------------------------------------------

    def selectTemplate(self, event):
        """ Selecting a folder which contains sample WAV files 
        to form a template WAV data.

        Args: event (wx.Event)

        Returns: None
        """ 
        if DEBUG: print("PyListenerFrame.selectTemplate()")
        if (type(event) == str and event == 'File'):
            dlg = wx.FileDialog(
                                self, 
                                "Select a template wave file", 
                                CWD, 
                                wildcard="(*.wav)|*.wav"
                               )
            listenFlag = 'templateFile'
        else:
            msg = "Select a folder which contains WAV files for template."
            msg += " All WAV files in the selected folder will be considered"
            msg += " as template."
            dlg = wx.DirDialog(self, msg, CWD) 
            listenFlag = 'templateFolder'
        if dlg.ShowModal() == wx.ID_OK:
            if self.pl.isListening == True:  # if mic. stream is open, 
                self.onBPButtonPress('startStopListening')  # close it.
            fPath = dlg.GetPath()
            self.pl.templFP = fPath
            # get analyzed parameters of template file(s).
            __, __, params = self.pl.listen(flag=listenFlag, wavFP=fPath) 
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

        self.panel['spT'].Refresh()  # draw spectrogram 

    #-------------------------------------------------------------------
   
    def compareSF2cParam(self, sfParams):
        """ Retrieve parameters from wx.TextCtrl in UI
        and compare parameters of the captured sound fragment with them.

        Args:
            sfParams (dict): Sound parameters of a captured sound fragment.

        Returns:
            rslt (bool): True means that two sounds matched with given 
                parameters. False means they didn't match.
            rsltTxt (str): String stored during processes of the function.
                It could be error message, information, etc.
        """ 
        if DEBUG: print("PyListenerFrame.compareSF2cParam()")
        rslt = True  # whether satisfying min. & max. value thresholds
        # of all checked parameters
        rsltTxt = ""
        tParams2c = {}  # template WAV parameters to compare

        if self.pl.templFP == None:
        # there's no selected template WAV
            _txt = "! Template WAV is not selected."
            _txt += " No comparison was conducted. !"
            rsltTxt = "[%s]"%(_txt)
            writeFile(self.logFile, "%s, [MSG], %s\n"%(get_time_stamp(), _txt))
            rslt = False
            return rslt, rsltTxt 

        else:
            mm = ["min", "max"]
            for param in self.pl.compParamList:
            # through each comparison parameter 
                name = "comp_" + param 
                chkB = wx.FindWindowByName( name+"_chk", self.panel["ip_spT"] )
                if chkB.GetValue() == False: continue  # this parameter 
                # is not checked. move on to the next parameter

                ### prepare min. and max. values (extracted from 
                ### template WAV and editted by user) to compare 
                ### with sound fragment params. 
                for mmn in mm:
                    _name = name + "_" + mmn
                    txt = wx.FindWindowByName( _name, self.panel["ip_spT"] )
                    txtVal = txt.GetValue().strip()
                    if txtVal == "":  # the textCtrl is empty
                        continue  # move to the next one, 
                        # considering this one is satisfied
                    try:
                        th = float(txtVal)  # threshold value
                    except:
                        # stop listening
                        self.onBPButtonPress('startStopListening') 
                        _txt = "%s, [MSG],"%(get_time_stamp())
                        _txt += " !!! Value of %s is not a number."%(_name)
                        _txt += " Comparison aborted. !!!\n"
                        writeFile( self.logFile, _txt)
                        show_msg(_txt)
                        rsltTxt += _txt
                        rslt = False
                        return rslt, rsltTxt 
                    tParams2c[param+"_"+mmn] = th
            if len(tParams2c) > 0:
                # compare sound fragment parmaeters 
                rslt, _txt = self.pl.compareParamsOfSF2T(sfParams, tParams2c)
                rsltTxt += "%s\n"%(_txt) 
       
        return rslt, rsltTxt 
     
    #-------------------------------------------------------------------
    
    def onChangeACthrTolerance(self, event):
        """ Tolerance value (for auto-contrast function) was changed.
        Update the corresponding attributes of PyListener class.

        Args: event (wx.Event)

        Returns: None
        """
        if DEBUG: print("PyListenerFrame.onChangeACthrTolerance()")
        obj = event.GetEventObject()
        name = obj.GetName()
        val = obj.GetValue()
        if name.startswith('templ'): self.pl.acThrTol_templ = val
        elif name.startswith('mic'): self.pl.acThrTol_nt = val
   
    #-------------------------------------------------------------------
    
    def onChangeShowCMinCol(self, event):
        """ wx.CheckBox for turning on/off center-of-mass in each column
        was checked/unchecked. Update the attribute.

        Args: event (wx.Event)

        Return: None
        """
        if DEBUG: print("PyListenerFrame.onChangeShowCMinCol()")
        self.flag_showCMInCol = event.GetEventObject().GetValue() 

    #-------------------------------------------------------------------

    def onClose(self, event):
        """ Close this frame.

        Args: event (wx.Event)

        Returns: None
        """
        if DEBUG: print("PyListenerFrame.onClose()")
        if self.pl.th != None:
            self.stop_listening()
            self.pl.pa.terminate()
            wx.CallLater(10, self.Destroy)
        else:
            self.Destroy()

    #-------------------------------------------------------------------

#=======================================================================

class PyListenerApp(wx.App):
    """ Initializing pyListener app with PyListenerFrame.

    Attributes:
        frame (wx.Frame): PyListener frame.
    """
    def OnInit(self):
        if DEBUG: print("PyListenerApp.OnInit()")
        self.frame = PyListenerFrame()
        self.frame.Show()
        self.SetTopWindow(self.frame)
        return True

#=======================================================================

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == '-w': GNU_notice(1)
        elif sys.argv[1] == '-c': GNU_notice(2)
    else:
        GNU_notice(0)
        app = PyListenerApp(redirect = False)
        app.MainLoop()

