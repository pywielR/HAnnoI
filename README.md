# HWAnno: Handwriting Annotator

## Description
HWAnno is a GUI application that was developed for annotating single letters in handwritten data. Its core functionalities include:

- importing single images or PDF files with one image per site
- marking rectangular areas (from now on referred to as items) within imported images
- annotating each individual item on user defined dimensions
- exporting annotations as a CSV file, which can be imported again to continue working with them
- making screenshots of each individual item within the images

The program also tracks and exports the coordinates of each item, allowing for subsequent analyses of this data. Though HWAnno was developed for one specific use case, its functionalities are not bound to scans of handwritten data.


## Installation
It is recommended to create a new environment in some directory on your system, for example using the Powershell Prompt in Anaconda. Within this environment, paste the HWAnno.py file as well as the requirements.txt file.

Using Anaconda, within the Powershell Prompt, an environment may be created using this command: 'conda create --name HWAnno python=3.12'

After that, activate the environment: 'conda activate HWAnno'

After that, install all required packages, using this command: 'pip install -r requirements.txt'

Is the last command does not work, try to install pip in the HWAnno environment first: 'conda install pip'

When all required packages are installed, the program may then be started using this command: 'python HWAnno.py'
