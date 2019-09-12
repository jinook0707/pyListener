# PyListener

PyListener is an open-source software written in Python for sound comparison.<br>
Currently, its main functionality is to listen to sound from microphone and save a recognized sound as WAV file, when it is similar with a loaded template sound.

Jinook Oh, Cognitive Biology department, University of Vienna<br>
Contact: jinook0707@gmail.com, tecumseh.fitch@univie.ac.at<br>
September 2019.

## Dependency
- **wxPython** (4.0)
- **pyAudio** (0.2)
- **NumPy** (1.17)
- **SciPy** (1.3)
- **Scikit-image** (0.15)


## What it does

In short, PyListener app does the below.<br>
**1)** Load template WAV file(s) to analyze & form template WAV data and parameters to compare.<br>
**2)** Captures a sound from streaming of microphone.<br>
**3)** This captured sound is also analyzed & its result parameters will be compared to those of template WAV data.<br>
**4)** Store result text in log file and show it on the app UI. Also, if two sounds match, the captured sound will be saved as a WAV file in 'recordings' folder.

## Example comparison, using pyListenerLib.py as a library

Currently, pyListener has three Python files, 

- **pyListener.py**: pyListener app, using wxPython.
- **pyListenerLib.py**: This contains main functionalities of pyListener such as sound loading, comparing and saving. This can be used without loading wxPython frame in **pyListener.py**.
- **pyLSpectrogram.py**: This is for drawing real-time spectrogram. Only 'SpectrogramPanel' is used in **pyListener.py** (There is a wxPython frame in it to run **pyLSpectrogram.py** separately).
- **fFuncNClasses.py**: Simple functions and a dialog class to be used in multiple places in the above files.

One can test sound comparision functionality with **pyListenerLib.py** without wxPython frame with the below code.

```
from os import getcwd
import pyListenerLib as PLL

pl = PLL.PyListener(parent=None, frame=None, logFile='log/testLog.txt', cwd=getcwd()) # initialize pyListener class
tSpAD, __, templP = pl.listen(flag='templateFolder', wavFP='input/sample_phee') # make template with phee calls
pl.compareWAV2Template('input/test/m_test.wav') # comparison
```

*compareWAV2Template* function accespts a file path of a WAV file in its argument and treat this WAV file as a recording with a microphone. Therefore, it does not compare entire WAV file with template. Instead, it treats the WAV file as if it's streaming from microphone, capturing a sound fragment and comparing each captured sound with template data.
The given test file, 'm_test.wav', has several alternating *phee* calls (five calls) and *rapid fire Tsik* calls (4 calls) with silent intervals.


## For more information, 
you can install Jupyter notebook (see https://jupyter.readthedocs.io/en/latest/install.html),
run Jupyter notebook
```
jupyter notebook
```
then, click 'readme.ipynb' in the opened browser for testing interactive codes.

