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

For more information, please read 'readme.ipynb'.
