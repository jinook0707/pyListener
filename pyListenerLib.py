# coding: UTF-8

'''
PyListener library
2019.August.
- jinook.oh@univie.ac.at
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

This program was tested only on OSX environment.
'''

import queue, wave, struct
from os import path, mkdir
from threading import Thread
from time import time
from copy import copy
from glob import glob

import pyaudio
import numpy as np
import warnings
warnings.filterwarnings("ignore")
from scipy.ndimage.measurements import center_of_mass 
from scipy.signal import correlate
from skimage import filters
from skimage import transform 
from pyentrp import entropy as ent

from fFuncNClasses import writeFile, get_time_stamp, receiveDataFromQueue

### Constants (time related contants are in seconds)
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
SAMPLE_WIDTH = 2 # 2 bytes
SHORT_NORMALIZE = 1.0 / 32768
INPUT_BLOCK_TIME = 0.02
INPUT_FRAMES_PER_BLOCK = int(RATE*INPUT_BLOCK_TIME)
FREQ_RES = RATE/float(INPUT_FRAMES_PER_BLOCK) # Frequency Resolution

#===============================================================================

class PyListener(object):
    def __init__(self, parent, frame=None, logFile='', cwd = '', debug=False):
        ''' Class for getting streaming data from mic., analyze/compare audio data.
        '''
        global CWD; CWD = cwd 
        global DEBUG; DEBUG = debug 
        if DEBUG: print("PyListener.__init__()")
        self.parent = parent
        self.frame = frame
        if frame == None: self.spWidth = 500
        if logFile == '':
            if path.isdir('log') == False: mkdir('log')
            self.logFile = "log/log_%s.txt"%(get_time_stamp()[:-9]) # cut off hh_mm_ss from timestamp
        else:
            self.logFile = logFile

        ### set up variables
        self.pKeys = [
                        'duration', 'summedAmp', 'summedAmpRatio', 
                        'cmInColList', 'centerOfMassX', 'centerOfMassY', 
                        'cmxN', 'cmyN', 'permEnt', 
                        'avgNumDataInCol', 'lowFreqRow', 'lowFreq', 
                        'highFreqRow', 'highFreq', 'distLowRow2HighRow', 
                        #'corr2auto'
                     ]
        self.compParamList = [
                                'duration', 'cmxN', 'cmyN', 
                                'avgNumDataInCol', 'lowFreq', 'highFreq', 
                                'distLowRow2HighRow', 'summedAmpRatio', 
                             ] # parameters to use in comparison between sound fragment and template WAV
        self.indCPL = [
                        'summedAmpRatio',
                        #'corr2auto',
                      ] # parameters with values which don't change when template folder is changed 
        self.cplInitMargin = dict(
                                    duration_min=0.25, duration_max=1.0, 
                                    cmxN_min=0.15, cmxN_max=0.15,
                                    cmyN_min=0.15, cmyN_max=0.15,
                                    avgNumDataInCol_min=20, avgNumDataInCol_max=20,
                                    lowFreq_min=2.0, lowFreq_max=2.0, 
                                    highFreq_min=2.0, highFreq_max=2.0,
                                    distLowRow2HighRow_min=20, distLowRow2HighRow_max=20
                                 ) # -/+ to min and max margins on analyzed threshold ranges
        self.indCPRange = dict(
                                summedAmpRatio_min=0.5, summedAmpRatio_max=3.0,
                                #corr2auto_min=0.3, corr2auto_max=1.0,
                              ) # threshold ranges for indCPL
        self.compParamLabel = dict(
                                    duration='Duration', 
                                    cmxN='CenterOfMass-X (0.0-1.0)', cmyN='CenterOfMass-Y (0.0-1.0)', 
                                    permEnt='Permutation Entropy', 
                                    avgNumDataInCol='Avg. Num. Data in a column', 
                                    lowFreq='Low frequency', highFreq='High frequency', 
                                    distLowRow2HighRow='Distance betw. low && high rows', 
                                    #corr2auto='Correlation/AutoCorrelation', 
                                    summedAmpRatio='Summed amp./Template summed amp.'
                                  ) # labels to appear in UI for threshold ranges
        self.prefDevStr = ['headset', 'built-in'] # strings to detect preferred audio input device. the 1st item is supposed to be the most preferred, the last item is the least preferred.
        self.comp_freq_range = [1000, 20000] # frequency range for comparing sound 
        self.ampMonDur = 0.5 # time (in seconds) to look back for average amplitude. should be longer than self.minDur4SF.
        self.minDur4SF = 0.5 # minimum duration (in seconds) for a sound fragment
        self.ampRecLen = int(self.ampMonDur/INPUT_BLOCK_TIME) # length of self.amps list. (for measuring recent record) 
        self.ampThr = 0.005 # amplitude (0.0-1.0) threshold to start a sound fragment (in recent audio data during self.ampMonDur)
        self.maxDurLowerThr = 0.1 # once amp. goes above threshold, the program will continute to capture audio data until amp goes below self.ampThr longer than this duration, self.maxDurLowerThr.
        self.acThrTol_templ = 3.0 # tolerance value for filters.threshold_li function to detect threshold for auto-contrast. # higher this value is, less data points will appear in spectrogram. # tolerance: Finish the computation when the change in the threshold in an iteration is less than this value. By default, this is half the smallest difference between intensity values in image.
        self.acThrTol_nt = 3.0
        self.rMicData = [] # data read from mic 
        self.spAD = None # NumPy array to store recent audio data for drawing spectrogram
        self.tSpAD = None # NumPy array to store audio data of selected WAV file 
        self.th = None # thread 
        self.q2m = queue.Queue() # queue to main thread
        self.q2t = queue.Queue() # queue to a child thread
        self.sFragCI = [-1, -1] # column indices (beginning and end) of audio data, in which average RMS amplitude went over threshold 
        self.sfcis = [] # list of colmn indices of captured sound fragments
        self.sfRslts = [] # list of ('Matched', 'Unmatched' or 'N/A') whether each sound fragment matched or not, 'N/A' means no comparison was conducted.
        self.templFP = None # folder (or file) path of template WAV file(s)
        self.templP = None # analyzed parameters of a selected template WAV file
        self.lastTimeAmpOverThr = None # last time when amplitude was over threshold 
        self.sfP = None # analyzed parameters of the current sound fragment (most recent fragment captured by amplitude)
        
        self.pa = pyaudio.PyAudio()
        self.devIdx, self.devNames = self.find_device(devType='input')

        self.isListening = False

    #---------------------------------------------------------------------------

    def stop(self):
        ''' stop streaming
        '''
        if DEBUG: print("PyListener.stop()")
        self.stream.close()
        self.rMicData = [] 
        #self.pa.terminate()
        writeFile( self.logFile, "%s, [MSG], Audio stream is closed.\n"%(get_time_stamp()) )

    #---------------------------------------------------------------------------
   
    def find_device(self, devType='input'):
        if DEBUG: print("PyListener.find_device()")
        '''
        * self.prefDevStr has strings of preferred audio device.
        params ---
        devType (string): should be 'input' or 'output' 
        return ---
        devIdx (list): found device indices (integers)
        devNames (list): found device names (string)
        '''
        devIdx = []
        devNames = []
        for devStr in self.prefDevStr:
            for i in range( self.pa.get_device_count() ):     
                devInfo = self.pa.get_device_info_by_index(i)
                writeFile( self.logFile, "%s, [MSG], Index:%i/ device-name:%s\n"%(get_time_stamp(), i, devInfo["name"]) )
                if devInfo["max%sChannels"%(devType.capitalize())] > 0: # if device type (input or output) matches
                    if devStr.lower() in devInfo["name"].lower():
                        writeFile( self.logFile, "%s, [MSG], Found an input device; device-index:%i/ device-name:%s\n"%(get_time_stamp(), i ,devInfo["name"]) )
                        devIdx.append(i)
                        devNames.append(devInfo["name"])
        if devIdx == []:
            e_msg = "%s, [ERROR], !! No preferred input device is found. Please check 'self.prefDevStr' in pyListener.py !!\n"%(get_time_stamp())
            writeFile( self.logFile, e_msg )
            print(e_msg)
        return devIdx, devNames

    #---------------------------------------------------------------------------
    
    def open_mic_stream(self, chosenDevIdx):
        ''' open streaming with an input device
        '''
        if DEBUG: print("PyListener.open_mic_stream()")
        stream = self.pa.open(   format = FORMAT,
                                 channels = CHANNELS,
                                 rate = RATE,
                                 input = True,
                                 input_device_index = self.devIdx[chosenDevIdx],
                                 frames_per_buffer = INPUT_FRAMES_PER_BLOCK )
        writeFile( self.logFile, "%s, [MSG], Stream of %i. %s is opened.\n"%(get_time_stamp(), self.devIdx[chosenDevIdx], self.devNames[chosenDevIdx]) )
        return stream

    #---------------------------------------------------------------------------
    
    def listen(self, flag='stream', wavFP=''):
        ''' Read data from microphone and pre-process.
        If it's opening a wave file, read WAV file, pro-process and analyze.
        params ---
        flag (string): Indicates what kind of data processing. Currently, 'stream', 'wavFile' or 'templateFolder'.
        wavFP (string): Wave file path ('wavFile' flag) or folder path ('templateFolder' flag), which contains WAV files for template
        return ---
        data (numpy array): Spectrogram data, which has greyscale pixel values (0-255) for drawing a spectrogram.
        amp (float): RMS amplitude of data from mic.
        params : Analyzed parameters of WAV data.
        '''
        if DEBUG: print("PyListener.listen()")
        amp = None; params= None
        
        if flag == 'stream': # read from mic. stream
            try: 
                data = self.stream.read(INPUT_FRAMES_PER_BLOCK, exception_on_overflow=False)
                self.rMicData.append(data) # store read data
            except IOError as e:
                print(str(e))
                writeFile( self.logFile, "%s, [ERROR], %s\n"%(get_time_stamp(), str(e)) )
                return None
            if self.frame == None: w = self.spWidth
            else: w = self.frame.pi['sp']['sz'][0]
            if len(self.rMicData) > w: self.rMicData.pop(0) # remove old data when it's out of current spectrogram width 
            amp = self.get_rms(data) # get rms amp.
            data = np.frombuffer(data, dtype=np.short) # int16
            data = self.preProcDataFromMic(data)

        elif flag == 'wavFile': # read a WAV file
            wavData = wave.open(wavFP, 'rb')
            params = wavData.getparams()
            wd = wavData.readframes(params.nframes)
            wavData.close()
            wd = np.frombuffer(wd, dtype=np.dtype('i2'))
            data = self.preProcDataFromFile(wd, params, flagInitArr=False)
            params, data = self.analyzeSpectrogramArray(data, flagTemplate=False)

        elif flag in ['templateFolder', 'templateFile']: # read WAV files in a template folder 
            if flag == 'templateFolder': fileLists = glob(path.join(wavFP, "*.wav"))+glob(path.join(wavFP, "*.WAV"))
            elif flag == 'templateFile': fileLists = [ wavFP ]
            data, params = self.formTemplate(fileLists)
            self.templP = params 
            self.tSpAD = data
        
        return data, amp, params  

    #---------------------------------------------------------------------------

    def preProcDataFromMic(self, data): 
        if DEBUG: print("PyListener.preProcDataFromMic()")
        data = data * SHORT_NORMALIZE
        data = abs(np.fft.fft(data))[:int(INPUT_FRAMES_PER_BLOCK/2)]
        maxVal = np.max(data)
        if maxVal > 1: data = data/maxVal # maximum value should be 1 
        data = (data * 255).astype(np.uint8) # make an array of 0-255 for amplitude of pixel
        data = np.flip(data) # flip to make low frequency is placed at the bottom of screen
        return data
    
    #---------------------------------------------------------------------------

    def preProcDataFromFile(self, wd, wp, flagInitArr=True): 
        ''' update constants, resize array , etc on the wave file (wd) 
        wp: WAV parameters
        '''
        if DEBUG: print("PyListener.preProcDataFromFile()")
        ### update global constants, resize array
        global RATE; RATE = wp.framerate # update
        global INPUT_FRAMES_PER_BLOCK; INPUT_FRAMES_PER_BLOCK = int(wp.framerate*INPUT_BLOCK_TIME) # update
        global FREQ_RES; FREQ_RES = wp.framerate/float(INPUT_FRAMES_PER_BLOCK) # update
        if flagInitArr == True: self.initSParr('both')
        if self.frame != None: self.frame.onUpdateRate()

        if wp.nchannels == 2: # stereo
            wd = (wd[1::2] + wd[::2]) / 2 # stereo data to mono data
        cols = int(round(wp.nframes/float(INPUT_FRAMES_PER_BLOCK))) # number of columns for array
        data = np.zeros((int(INPUT_FRAMES_PER_BLOCK/2), cols), dtype=np.uint8) # final data array
        for ci in range(cols):
            off = ci * INPUT_FRAMES_PER_BLOCK 
            ad = wd[off:off+INPUT_FRAMES_PER_BLOCK]
            ad = ad * SHORT_NORMALIZE
            ad = abs(np.fft.fft(ad))[:int(INPUT_FRAMES_PER_BLOCK/2)]
            maxVal = np.max(ad)
            if maxVal > 1.0: ad = ad/maxVal # maximum value should be 1 
            ad = (ad * 255).astype(np.uint8) # make an array of 0-255 for amplitude of pixel
            ad = np.flip(ad) # flip to make low frequency is placed at the bottom of screen 
            data[:,ci] = ad

        return data  
   
    #---------------------------------------------------------------------------
    
    def initSParr(self, targetSP='sp'):
        ''' initialize spectrogram class array(s) and its related varialbes (in case of 'sp') 
        params ---
        targetSP (string): target spectrogram array to initialize
        return ---
        None
        '''
        if DEBUG: print("PyListener.initSParr()")
        if self.frame == None: spW = spTw = self.spWidth
        else: spW = self.frame.pi['sp']['sz'][0]; spTw = self.frame.pi['spT']['sz'][0]
        if targetSP in ['sp', 'both']:
            self.sFragCI = [-1, -1]
            self.lastTimeAmpOverThr = None
            self.spAD = np.zeros( (int(INPUT_FRAMES_PER_BLOCK/2), spW), dtype=np.uint8 ) # audio data for spectrogram
        if targetSP in ['spT', 'both']:
            self.templP = None
            self.tSpAD = np.zeros( (int(INPUT_FRAMES_PER_BLOCK/2), spTw), dtype=np.uint8 ) # audio data for WAV file spectrogram 

    #---------------------------------------------------------------------------
  
    def startContMicListening(self, chosenDevIdx):
        if DEBUG: print("PyListener.startContMicListening()")
        if not isinstance(self.spAD, np.ndarray): return
        self.isListening = True
        self.initSParr('sp')
        self.th = Thread(target=self.contMicListening, args=(self.spAD, self.q2m, self.q2t, chosenDevIdx))
        self.th.start() # start the thread 

    #---------------------------------------------------------------------------
    
    def contMicListening(self, spAD, q2m, q2t, chosenDevIdx):
        ''' function for running as a thread
        continuously listen to the microphone
        update data in a column of spAD (audio-data in numpy array for drawing spectrogram)
        send spAD via a queue
        '''
        if DEBUG: print("PyListener.contMicListening()")
        cci = 0 # current column index for putting a audio-data column
        amps = [] # list of RMS amplitudes of recent audio data
        self.stream = self.open_mic_stream(chosenDevIdx)
        while True:
            rData = receiveDataFromQueue(q2t, self.logFile)
            if rData != None:
                if rData[0] == 'msg' and rData[1] == 'quit': break
            
            ad, amp, __ = self.listen('stream') # Listen to the mic  

            amps.append(amp)
            if len(amps) > self.ampRecLen: amps.pop(0) 

            if cci < spAD.shape[1]:
                spAD[:,cci] = ad 
                cci += 1
            else:
                ### remove 1st column and append the column of new audio-data at the end of array
                _tmp = np.copy(spAD[:,1:])
                spAD = np.zeros(spAD.shape, dtype=np.uint8)
                spAD[:,:-1] = _tmp
                spAD[:,-1] = ad 

            if isinstance(ad, np.ndarray):
                q2m.put(('aData', (spAD, amps, cci)), True, None)
        self.stop() 

    #---------------------------------------------------------------------------
    
    def contProcMicAudioData(self, q2t):
        ''' This function is for when there's no GUI frame to continuously process microphone data.
        '''
        if DEBUG: print("PyListener.contProcMicAudioData()")
        while True:
            rData = receiveDataFromQueue(q2t, self.logFile)
            if rData != None:
                if rData[0] == 'msg' and rData[1] == 'quit': break

            sfFlag, analyzedP, sfD = self.procMicAudioData() # process recent mic audio data
            if sfFlag == 'started': print("Sound fragment started.")
            elif sfFlag == 'stopped': print ("Sound fragment stopped.")
            if analyzedP != None: # there are analyzed parameters of sound fragment
                rsltTxt = self.logSFParms(analyzedP) # log paraemters of sound fragment 
                tParams2c = {}
                for param in self.compParamList:
                    tParams2c[param+'_min'] = self.templP[param+"_min"]
                    tParams2c[param+'_max'] = self.templP[param+"_max"]
                rslt, _txt = self.compareParamsOfSF2T(analyzedP, tParams2c) # compare sound fragment parmaeters with template 
                if rslt == True: # matched
                    rsltTxt += "Sound fragment [MATCHED] with following parameters ( %s ).\n"%( str(list(tParams2c.keys())).strip('[]').replace("'","").replace(",","/") )
                    fp = self.writeWAVfile(sfD) # save the captured sound fragment to WAV file
                    rsltTxt += "WAV file, %s, is saved."%(fp)
                else: # didn't match
                    rsltTxt += "%s\n"%(_txt) 
                print(rsltTxt)

    #---------------------------------------------------------------------------
    
    def procMicAudioData(self):
        ''' Receive mic. audio data from the running thread (contMicListening), then process it.
        This function is called by a function 'frame.updateSpectrogram', which runs periodically using wx.Timer.
        '''
        if DEBUG: print("PyListener.procMicAudioData()")
        rData = None
        sfci = self.sFragCI
        sfFlag = "" # return value; whether sound fragment captureing started or stopped
        params = None # return value; parameters of the current sound fragment 
        sfD = None # return value; raw sound data from mic. of the current sound fragment position

        ### get the most recent data
        missing_msg_cnt = -1  
        while self.q2m.empty() == False:
            rData = receiveDataFromQueue(self.q2m, self.logFile)
            missing_msg_cnt += 1 # count how many queued messages were missed 

        if rData != None and rData[0] == 'aData':
            self.spAD = rData[1][0] # spectrogram data from mic
            amps = rData[1][1] 
            cci = rData[1][2] # current column index (in which the last audio stream data was stored)
            
            if cci >= self.spAD.shape[1]: # spectrogram is moving
                ### move column indcies of spectrogram
                num = 1 + missing_msg_cnt
                if sfci[0] > -1: sfci[0] -= num 
                else: sfci = [-1, -1]
                if sfci[1] > -1: sfci[1] -= num
                for i in range(len(self.sfcis)):
                    if self.sfcis[i][0] > -1: self.sfcis[i][0] -= num
                    else:
                        self.sfcis[i] = None
                        self.sfRslts[i] = None
                    if self.sfcis[i] != None: self.sfcis[i][1] -= num
                while None in self.sfcis: self.sfcis.remove(None)
                while None in self.sfRslts: self.sfRslts.remove(None)
    
            if amps != [] and np.average(amps) > self.ampThr: # average of RMS amplitude of recent audio data is over threshold
                if self.lastTimeAmpOverThr == None:
                    sfFlag = 'started' 
                    sfci = [ max(0, cci-self.ampRecLen), -1 ] # store the beginning index of data
                self.lastTimeAmpOverThr = time()
                
            else: # RMS amp. is under threshold
                if self.lastTimeAmpOverThr != None and time()-self.lastTimeAmpOverThr > self.maxDurLowerThr:
                # amplitude was below threshold long enough (> self.maxDurLowerThr)
                    self.lastTimeAmpOverThr = None 
                    sfFlag = 'stopped'
                    sfci[1] = cci-1 # record the last column index
                    if (sfci[1]-sfci[0]) * INPUT_BLOCK_TIME >= self.minDur4SF: # reached the minimum duration
                        _d = self.spAD[:,sfci[0]:sfci[1]] # sound fragment data to analyze
                        params, _d = self.analyzeSpectrogramArray(_d, flagTemplate=False) # analyze the sound fragment
                        self.sfP = params 
                        self.spAD[:,sfci[0]:sfci[1]] = _d
                        sfD = self.rMicData[sfci[0]:sfci[1]] # get raw data (from mic.) of the analyzed sound fragment 
                        self.sfcis.append( copy(sfci) ) # store column index
                        if self.templFP == None: self.sfRslts.append('N/A')
                    else: # didn't reach minimum duration
                        sfci = [-1, -1]
           
            self.sFragCI = sfci
        return sfFlag, params, sfD

    #---------------------------------------------------------------------------
    
    def endContMicListening(self): 
        if DEBUG: print("PyListener.endContMicListening()")
        ### end the thread
        self.q2t.put(('msg', 'quit'), True, None) 
        self.th.join()
        self.th = None

        self.isListening = False
        self.sFragCI = [-1, -1]
        self.sfcis = []
        self.sfRslts = []

    #---------------------------------------------------------------------------

    def get_rms(self, data):
        ''' calculates Root Mean Square amplitude
        '''
        if DEBUG: print("PyListener.get_rms()")
        ### get one short out for each two chars in the string.
        count = len(data)/2
        frmt = "%dh"%(count)
        shorts = struct.unpack( frmt , data )

        # iterate over the block.
        sum_squares = 0.0
        for sample in shorts:
            # sample is a signed short in +/- 32768. 
            # normalize it to 1.0
            n = sample * SHORT_NORMALIZE
            sum_squares += n*n

        return np.sqrt( sum_squares / count )

    #---------------------------------------------------------------------------
    
    def autoContrast(self, data, adjVal=20, flagTemplate=False): 
        ''' apply auto-contrast with a threshold, using threshold_li (Li’s iterative Minimum Cross Entropy method)
        params ---
        data (numpy array): data to apply auto-contrast
        adjVal (int): how much increase/decrease data with the threshold
        return ---
        data (numpy array): data after applying auto-contrast
        '''
        if DEBUG: print("PyListener.autoContrast()")
        
        if np.sum(data) == 0: return data

        ### find threshold for auto-contrasting 
        if flagTemplate == True: tol = self.acThrTol_templ
        else: tol = self.acThrTol_nt
        acThr = filters.threshold_li(data, tolerance=tol) # detect threshold
        data = data.astype(np.float32)
        data[data<=acThr] -= adjVal 
        data[data>acThr] += adjVal 
        data[data<0] = 0 # cut off too low values
        maxVal = np.max(data)
        if maxVal > 255: data *= (255.0/maxVal)
        data = data.astype(np.uint8)
        return data
    
    #---------------------------------------------------------------------------

    def analyzeSpectrogramArray(self, inputData, flagTemplate=False):
        ''' get sound data (numpy array of spectrogram)
        params ---
        inputData (numpy array): spectrogram data to analyze
        flagTemplate (bool): indicating whether this is WAV file loading for template.
        return ---
        params (python dict.): analyzed params 
        data (numpy array): data after some processing for analysis such as cutoff frequency, auto-contrast, etc.. 
        '''
        if DEBUG: print("PyListener.analyzeSpectrogramArray()")
       
        data = np.copy(inputData)
        params = {} # result dictionary to return
        for key in self.pKeys: params[key] = -1 # initial value
        
        if np.sum(data) == 0: return params, data
        
        ### cut off data in range of frequencies, self.comp_freq_range 
        cutI1 = data.shape[0]-int(self.comp_freq_range[1]/FREQ_RES)
        cutI2 = data.shape[0]-int(self.comp_freq_range[0]/FREQ_RES)
        data[:cutI1,:] = 0 # delete high frequency range
        data[cutI2:,:] = 0 # delete low frequency range

        data = self.autoContrast(data, 20, flagTemplate=flagTemplate) # auto contrasting

        ### processing each column of data
        nonZeroPts = []; nonZeroLowestFreqRowList = []; nonZeroHighestFreqRowList = []; cms = []
        for ci in range(data.shape[1]):
            a = data[:,ci]
            _nz = np.nonzero(a)[0]
            nonZeroPts.append(len(_nz))
            if len(_nz) > 0:
                nonZeroLowestFreqRowList.append(np.max(_nz))
                nonZeroHighestFreqRowList.append(np.min(_nz))
            cm = center_of_mass(a)[0]
            if np.isnan(cm) == True: cms.append(-1)
            else: cms.append(int(cm))
        ### change -1 values from CenterOfMass list to its neighbor value
        for i in range(len(cms)):
            if cms[i] == -1:
                if i == len(cms)-1: cms[i] = cms[i-1]
                else:
                    j = 1 
                    while j < len(cms)-1:
                        if cms[j] != -1:
                            cms[i] = cms[j]
                            break
                        j += 1
        
        ##### begin: calculating and storing analyzed params. --------------------  
        ### calculate duration
        params["duration"] = INPUT_BLOCK_TIME * data.shape[1] 
        ### summed amplitude ratio
        params["summedAmp"] = np.sum(data.astype(np.int32))
        if flagTemplate == True: # loading a template WAV
            params["summedAmpRatio"] = 1.0
        else:
            if self.templP != None: # there's a template file params. 
                params["summedAmpRatio"] = np.sum(data.astype(np.int32)) / self.templP["summedAmp"] 
        ### store center-of-mass in each column
        params["cmInColList"] = cms  
        ### center-of-mass in column & row, and in terms of relative position (0.0-1.0) 
        row, col = center_of_mass(data)
        params["centerOfMassX"] = int(col)
        params["centerOfMassY"] = int(row)
        params["cmxN"] = params["centerOfMassX"]/data.shape[1]
        params["cmyN"] = 1.0-params["centerOfMassY"]/data.shape[0]
        ### calculate permutation entropy value
        params["permEnt"] = ent.permutation_entropy(params["cmInColList"], order=5, normalize=True)
        ### average number of non-zero data points in columns
        if nonZeroPts == []: params["avgNumDataInCol"] = -1
        else: params["avgNumDataInCol"] = np.average(nonZeroPts)
        ### lowest and highest non-zero row and its frequency
        if nonZeroLowestFreqRowList == []:
            params["lowFreqRow"] = -1
            params["lowFreq"] = -1
        else:
            #params["lowFreqRow"] = int(np.median(nonZeroLowestFreqRowList))
            params["lowFreqRow"] = int(np.average(nonZeroLowestFreqRowList))
            params["lowFreq"] = (data.shape[0]-params["lowFreqRow"]) * FREQ_RES / 1000
        if nonZeroHighestFreqRowList == []:
            params["highFreqRow"] = -1
            params["highFreq"] = -1
        else:
            #params["highFreqRow"] = int(np.median(nonZeroHighestFreqRowList))
            params["highFreqRow"] = int(np.average(nonZeroHighestFreqRowList))
            params["highFreq"] = (data.shape[0]-params["highFreqRow"]) * FREQ_RES / 1000
        ### distance between lowFreqRow and highFreqRow
        params["distLowRow2HighRow"] = params["lowFreqRow"] - params["highFreqRow"]
        ### calculates parameters about relation between the current sound to the template sound 
        if self.templP != None: # there's a template file params. 
            if flagTemplate == False: # this is not a template file loading
                r = -1
                _d = data.astype(np.int32) # spectrogram data of the currently received sound 
                _t = self.tSpAD.astype(np.int32) # spectrogram data of template sound
                ### calculates correlation to auto-correlation ratio
                autocorr = correlate(_t, _t) # auto-correlation of template sound
                corr = correlate(_d, _t) # correlation between two sounds 
                acm = np.max(autocorr) # maximum overlapping of auto-correlation 
                cm = np.max(corr) # maximum overlapping value of correlation 
                r = float(cm) / acm
                if r > 1.0: r = 1.0-(r-1.0)
                params["corr2auto"] = r
        ##### end: calculating and storing analyzed params. -------------------- 
        
        return params, data

    #---------------------------------------------------------------------------
  
    def formTemplate(self, fileLists):
        ''' Process list of wave files to form template data
        '''
        if DEBUG: print("PyListener.formTemplate()")
        for i in range(len(fileLists)): # go through all files
            fp = fileLists[i]
            ### read wave file
            wavData = wave.open(fp, 'rb')
            params = wavData.getparams()
            wd = wavData.readframes(params.nframes)
            wavData.close()
            wd = np.frombuffer(wd, dtype=np.dtype('i2'))
            if i == 0:
                ### the 1st file, initilization
                initFR = params.framerate
                data = np.zeros((1,1), dtype=np.uint16) # final 'data'
                d = self.preProcDataFromFile(wd, params, flagInitArr=True) # currnet data, 'd'
                tParams = {} # result params dictionary 
                for key in self.pKeys: tParams[key] = [] # temporarily make it as a list to append data from all WAV files 
            else:
                ### validity checking
                if initFR != params.framerate:
                    msg =  "File '%s' was not loaded due to its different framerate %i from the framerate %i of the first file.\n"%(fp, params.framerate, initFR)
                    print(msg)
                    writeFile( self.logFile, "%s, [ERROR] %s"%(get_time_stamp(), msg) )
                    continue
                d = self.preProcDataFromFile(wd, params, flagInitArr=False) # current data, 'd'
            # analyze the current data 
            params, d = self.analyzeSpectrogramArray(d, flagTemplate=True)
            ### (temporarily) append obtained params in tParams
            for key in self.pKeys: tParams[key].append(params[key])
            ### keep the spectrogram array size same.
            if data.shape[1] != d.shape[1]: # length of current data, d, is different from 'data'
                if data.shape[1] < d.shape[1]:
                    od = np.copy(data)
                    data = np.zeros(d.shape, dtype=np.uint16)
                    data[:od.shape[0], :od.shape[1]] = od 
                else:
                    _d = np.copy(d)
                    d = np.zeros(data.shape, dtype=np.uint8)
                    d[:_d.shape[0], :_d.shape[1]] = _d
            # store average 'data'; average pixel value for final spectrogram
            data = np.array( (data+d)/2.0, dtype=np.uint16 ) 
        data = self.autoContrast(data, adjVal=40, flagTemplate=True) # auto contrasting
        
        ### get parameter's min, max and average values.
        keys = list(self.pKeys)
        ### - process list data items (currently, cmInColList) first (for other item depending on list data)
        listDataKeys = []
        for key in keys:
            if type(tParams[key][0]) == list:
            # data type is list
                minKey = key + "_min"
                maxKey = key + "_max"
                ### get element-wise average values of lists
                tpLen = len(tParams[key])
                tmp = []
                for i in range(tpLen): tmp.append(len(tParams[key][i]))
                dLen = int(np.average(tmp)) # final length is average length of items of tParams[key]
                tmpArr = np.zeros((tpLen, dLen))
                for i in range(tpLen):
                    # resize data of each item to the dLen
                    tmpArr[i,:] = transform.resize( np.asarray(tParams[key][i]), 
                                                    output_shape=(dLen,), 
                                                    preserve_range=True, 
                                                    anti_aliasing=True )
                tmpArr = self.levelFarOffValues(tmpArr) # make center-of-mass values, which are out of standard deviation, to average value 
                ### min. & max. values 
                tParams[minKey] = np.min(tmpArr, axis=0)
                tParams[maxKey] = np.max(tmpArr, axis=0)
                if key in self.cplInitMargin.keys():
                    ### give margin to min. & max. values
                    tParams[minKey] = list( (tParams[minKey] - self.cplInitMargin[minKey]).astype(np.int16) )
                    tParams[maxKey] = list( (tParams[maxKey] + self.cplInitMargin[maxKey]).astype(np.int16) )
                # final values in the list will be average values 
                tParams[key] = list( (np.average(tmpArr, axis=0)).astype(np.int16) ) 
                listDataKeys.append(key)
        for key in listDataKeys: keys.remove(key)
        ### - process other items 
        for key in keys:
            minKey = key + "_min"
            maxKey = key + "_max"
            if key in self.compParamList:
                if key == 'permEnt': # cmInColList was adjusted in this function. Calculate its permutation entroy here.
                    tParams[key] = ent.permutation_entropy(tParams["cmInColList"], order=5, normalize=True)
                    tParams[minKey] = tParams[key] - self.cplInitMargin[minKey]
                    tParams[maxKey] = tParams[key] + self.cplInitMargin[maxKey]
                
                elif key in self.indCPL: # This parameter is not relevant to changing WAV data. Simply, get values from indCPRange.
                    tParams[minKey] = self.indCPRange[minKey]
                    tParams[maxKey] = self.indCPRange[maxKey]
                    tParams[key] = (tParams[minKey]+tParams[maxKey]) / 2.0

                else: # other parameters in compParamList
                    tParams[minKey] = np.min(tParams[key]) - self.cplInitMargin[minKey]
                    tParams[maxKey] = np.max(tParams[key]) + self.cplInitMargin[maxKey]
                    tParams[key] = np.average(tParams[key]) # store average value of all wave files

            else:
            # this is just for internal calculations, just store average value.
                tParams[key] = np.average(tParams[key])
        return data, tParams

    #---------------------------------------------------------------------------
    
    def compareParamsOfSF2T(self, sParams, tParams, fName=''):
        ''' Compare parameters of sound fragment to parameters of template WAV
        '''
        if DEBUG: print("PyListener.compareParamsOfSF2T()")
        rslt = True # whether params. of two sounds match or not
        rsltTxt = "" 
        matchedKeys = []
        for key in tParams.keys():
            if key[-4:] == '_max': continue # work with _min key
            key = key[:-4] 
            sfV = sParams[key]
            rsltTxt += "/ %s"%(key)
            minV = tParams[key+'_min']
            maxV = tParams[key+'_max']
            if sfV < minV or sfV > maxV:
                rslt = False
                rsltTxt += " [NOT]"
            else:
                matchedKeys.append(key)
            rsltTxt += " (%.3f <= %.3f <= %.3f)"%(minV, sfV, maxV)
        rsltTxt = rsltTxt.lstrip("/")
        _txt = "Sound fragment"
        if fName != '': _txt += " (%s)"%(fName)
        if rslt == True:
            _txt += " [MATCHED] with following parameters ( %s )"%( str(matchedKeys).strip('[]').replace("'","").replace(",","/") )
            _txt += rsltTxt
            rsltTxt = "%s, [RESULT], %s\n\n"%(get_time_stamp(), _txt)
        else:
            _txt += " did [NOT] match/ " + rsltTxt
            rsltTxt = "%s, [RESULT], %s\n\n"%(get_time_stamp(), _txt)
        writeFile( self.logFile, rsltTxt )

        if rslt == True: self.sfRslts.append('Matched')
        else: self.sfRslts.append('Unmatched')

        return rslt, rsltTxt

    #---------------------------------------------------------------------------
    
    def levelFarOffValues(self, arr, stdF=1.0):
        ''' Make value out of standard deviation(s) to average value 
        '''
        if DEBUG: print("PyListener.eliminateFarOffValues()")
        avg = np.average(arr)
        std = np.std(arr)
        arr[arr<(avg-std)*stdF] = avg
        arr[arr>(avg+std)*stdF] = avg
        return arr

    #---------------------------------------------------------------------------
    
    def logSFParms(self, analyzedP):
        ''' records analyzed parameters of sound fragment 
        '''
        if DEBUG: print("PyListener.logSFParms()")
        ### record the captured sound fragment parameters 
        logTxt = "%s, [RESULT], Captured sound fragment parameters./ "%(get_time_stamp())
        for param in self.compParamList:
            _txt = "%s:%.3f/ "%(param, analyzedP[param])
            logTxt += _txt
        logTxt = logTxt.rstrip('/ ') + "\n" 
        writeFile( self.logFile, logTxt )
        return logTxt 

    #---------------------------------------------------------------------------

    def writeWAVfile(self, wData):
        ''' save given WAV data to a file
        params ---
        wData (list): list of audio data (each item is read samples from PyAudio stream) 
        return ---
        N/A 
        '''
        if DEBUG: print("PyListener.writeWAVfile()")
        fp = "recordings/rec_%s.wav"%(get_time_stamp())
        w = wave.open( fp, 'wb' )
        w.setparams((CHANNELS, SAMPLE_WIDTH, RATE, len(wData)*INPUT_FRAMES_PER_BLOCK, 'NONE', 'NONE'))
        for block in wData: w.writeframes(block)
        w.close()
        writeFile( self.logFile, "%s, [RESULT], Saved to WAV file, %s\n\n"%(get_time_stamp(), fp))
        return fp

#===============================================================================

if __name__ == "__main__": pass

