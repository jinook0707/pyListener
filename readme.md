# PyListener

PyListener is an open-source software written in Python for sound comparison.<br>
Currently, its main functionality is to listen to sound from microphone and save a recognized sound as WAV file, when it is similar with a loaded template sound.

Jinook Oh, Cognitive Biology department, University of Vienna<br>
Contact: jinook0707@gmail.com, tecumseh.fitch@univie.ac.at<br>
September 2019.


## What it does

In short, PyListener app does the below.<br>
**1)** Load template WAV file(s) to analyze & form template WAV data and parameters to compare.<br>
**2)** Captures a sound from streaming of microphone.<br>
**3)** This captured sound is also analyzed & its result parameters will be compared to those of template WAV data.<br>
**4)** Store result text in log file and show it on the app UI. Also, if two sounds match, the captured sound will be saved as a WAV file in 'recordings' folder.

## Example comparison, using pyListenerLib.py as a library

Currently, pyListener has three Python files, 

- pyListener.py: pyListener app, using wxPython.
- pyListenerLib.py: This contains main functionalities of pyListener such as sound loading, comparing and saving. This can be used without loading wxPython frame in pyListener.py.
- fFuncNClasses.py: Simple functions and a dialog class to be used in multiple places in the above files.

One can test sound comparision functionality with pyListenerLib.py without wxPython frame with the below code.

from os import getcwd, path
from glob import glob
import pyListenerLib as PLL
pl = PLL.PyListener(parent=None, frame=None, logFile='log/testLog.txt', cwd=getcwd())
tSpAD, __, templP = pl.listen(flag='templateFolder', wavFP='input/sample_phee')
tParams = {}
for param in pl.compParamList:
    tParams[param+'_min'] = templP[param+"_min"]
    tParams[param+'_max'] = templP[param+"_max"]
fLists = glob('input/test/m_*.wav')
for fp in sorted(fLists): # loop through WAV files
    spAD, __, sfParams = pl.listen(flag='wavFile', wavFP=fp) # read & analyze a WAV file
    flag, rsltTxt = pl.compareParamsOfSF2T(sfParams, tParams, path.basename(fp)) # compare analyzed parameters of the current WAV and template WAV
    print(rsltTxt) # print output; this text is also recorded in the log file by 'compareParamsOfSF2T' function.


For more information, please read 'readme.ipynb'.
