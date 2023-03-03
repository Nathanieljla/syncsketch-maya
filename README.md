![maya2023](https://img.shields.io/badge/Maya2023-tested-brightgreen.svg)
![maya2023](https://img.shields.io/badge/Maya2022-tested-brightgreen.svg)

#### This fork supports python3 and Maya's module system to keep syncSketch specific content isolated and easier to manage.

#### A thorough testing of this is still needed, however basic functionality seems to be working without issues.

#### The Maya plug-in is not currently compatible with versions 2020 or older.  2022 hasn't been tested, but it should work. I plan to update the architecture to support python 2.7 builds, but I'm not sure how soon that will be. 

This is a fork. Please see https://github.com/syncsketch/syncsketch-maya for more info.

Known Issues:
1. The module definition file currently gets replaced with the last syncSketch installation vs. appending/updating existing information.  If all your versions of Maya are in python3, this shouldn't be an issue.


# Installation

### Drag & Drop

The easiest way to install this application is to ...
1. Click this File Link > [install_syncketch_python3.py](https://github.com/Nathanieljla/syncsketch-maya/releases/download/v1.3.3-alpha/install_syncsketch_python3.py#install) < to download the installation python file.
2. Drag drop it from the browser into a maya-viewport. 
This will automatically install all the dependencies without requiring admin priviliges into your user-directory.
3. Hit 'Install' and on Allow this process to run python (hit 'Allow' in the popup)
4. Start SyncSketch UI
5. Log-In with your SyncSketch Credentials.

![redux_maya_install](https://user-images.githubusercontent.com/10859650/72236028-0bec0e80-358a-11ea-92da-9fdc698e50e7.gif)
