import os
import re
import time
import platform
import sys
import webbrowser

import glob
import tempfile
import shutil
import sys
import subprocess
from os.path import expanduser
import zipfile
from functools import partial
import site

try:
    #python3
    from urllib.request import urlopen
except:
    #python2
    from urllib import urlopen

try:
    #python2
    reload
except:
    #python3
    from importlib import reload

try:
    import maya.utils
    import maya.cmds
    from maya import OpenMayaUI as omui
    
    from PySide2.QtCore import *
    from PySide2.QtWidgets import *
    from PySide2.QtGui import *
    from shiboken2 import wrapInstance
    MAYA_RUNNING = True
except ImportError:
    MAYA_RUNNING = False


CONTEXT = None

versionTag = os.getenv('SS_DEV') or 'release'
INSTALL_SSGUI_ONLY = False #Install syncsketch GUI only


class Platforms(object):
    OSX = 0,
    LINUX = 1,
    WINDOWS = 2
    
    @staticmethod
    def get_name(enum_value):
        if enum_value == Platforms.OSX:
            return 'osx'
        elif enum_value == Platforms.LINUX:
            return 'linux'
        else:
            return 'windows'
    
    
class FFmpeg(object):
    FFMPEG_API_ENDPOINT = 'https://ffbinaries.com/api/v1/version/4.2'
    
    @staticmethod
    def _makeTempPath(name):
        tmpdir = tempfile.mkdtemp()
        return os.path.join(tmpdir, name)
    
    @staticmethod
    def _downloadToPath(url, path):
        import requests
        print('Download from {} to {}'.format(url, path))
        resp = requests.get(url)
        with open(path, 'wb') as f:
            f.write(resp.content)
    
    @staticmethod
    def _extractZipFile(zip_path, extracted_path):
        print('Unzip from {} to {}'.format(zip_path, extracted_path))
        zip_ref = zipfile.ZipFile(zip_path, 'r')
        zip_ref.extractall(extracted_path)
        zip_ref.close()  
    
    @staticmethod
    def _findBinPath(directory, name):
        bin_path = glob.glob(os.path.join(directory, '{}*'.format(name)))[0]
        print('Found binary {} at {}'.format(name, bin_path))
        return bin_path

    @staticmethod
    def downloadFFmpegToDisc(platform=None, moveToLocation=None):
        import requests
    
        platform_mapping = {
                Platforms.WINDOWS: 'windows-64',
                Platforms.OSX : 'osx-64',
                Platforms.LINUX  : 'linux-64'
                }
    
        _platform = platform_mapping[platform]
    
        ffmpeg_resp = requests.get(FFmpeg.FFMPEG_API_ENDPOINT).json()
    
        ffmpeg_url = ffmpeg_resp['bin'][_platform]['ffmpeg']
        ffmpeg_zip_path = FFmpeg._makeTempPath('ffmpeg.zip')
        ffmpeg_extrated_path = FFmpeg._makeTempPath('ffmpeg_extracted')
        FFmpeg._downloadToPath(ffmpeg_url, ffmpeg_zip_path)
        FFmpeg._extractZipFile(ffmpeg_zip_path, ffmpeg_extrated_path)
        ffmpeg_bin_path = FFmpeg._findBinPath(ffmpeg_extrated_path, 'ffmpeg')
    
        ffprobe_url = ffmpeg_resp['bin'][_platform]['ffprobe']
        ffprobe_zip_path = FFmpeg._makeTempPath('ffprobe.zip')
        ffprobe_extrated_path = FFmpeg._makeTempPath('ffprobe_extracted')
        FFmpeg._downloadToPath(ffprobe_url, ffprobe_zip_path)
        FFmpeg._extractZipFile(ffprobe_zip_path, ffprobe_extrated_path)
        ffprobe_bin_path = FFmpeg._findBinPath(ffprobe_extrated_path, 'ffprobe')
    
        print('Moving FFMPEG from to directory: {0}'.format(moveToLocation))
        if not os.path.isdir(moveToLocation):
            os.makedirs(moveToLocation)
            
        os.chmod(ffmpeg_bin_path, 0o755)
        os.chmod(ffprobe_bin_path, 0o755)
        shutil.copy(ffmpeg_bin_path, moveToLocation)
        shutil.copy(ffprobe_bin_path, moveToLocation)
    
    
def restoreCredentialsFile():
    #We assume that User already has a previous version installed
    import syncsketchGUI.lib.user as user
    current_user = user.SyncSketchUser()
    if InstallOptions.tokenData:
        current_user.set_name(InstallOptions.tokenData['username'])
        # todo we should remove api_key
        current_user.set_token(InstallOptions.tokenData['token'])
        current_user.set_api_key(InstallOptions.tokenData['token'])
        current_user.auto_login()
    
   
   

class Module_manager(object):
    """Used to edit .mod files quickly and easily."""
    
    MODULE_EXPRESSION = r"(?P<action>\+|\-)\s*(MAYAVERSION:(?P<maya_version>\d{4}))?\s*(PLATFORM:(?P<platform>\w+))?\s*(?P<module_name>\w+)\s*(?P<module_version>\d+\.?\d*.?\d*)\s+(?P<module_path>.*)\n(?P<defines>(?P<define>.+(\n?))+)?"
    
    class Module_definition(object):
        """A .mod file can have multiple entries.  Each definition equates to one entry"""
        
        def __init__(self, module_name, module_version,
                     maya_version = '', platform = '',
                     action = '+', module_path = '',
                     defines = [],
                     *args, **kwargs):
            
            self.action = action
            self.module_name = module_name
            self.module_version = module_version
            
            self.module_path = r'.\{0}'.format(self.module_name)
            if module_path:
                self.module_path = module_path

            self.maya_version = maya_version
            if self.maya_version is None:
                self.maya_version = ''
            
            self.platform = platform
            if self.platform is None:
                self.platform = ''
            
            self.defines = defines
            if not self.defines:
                self.defines = []
            
        def __str__(self):
            return_string = '{0} '.format(self.action)
            if self.maya_version:
                return_string += 'MAYAVERSION:{0} '.format(self.maya_version)
                
            if self.platform:
                return_string += 'PLATFORM:{0} '.format(self.platform)
                
            return_string += '{0} {1} {2}\n'.format(self.module_name, self.module_version, self.module_path)
            for define in self.defines:
                if define:
                    return_string += '{0}\n'.format(define.rstrip('\n'))
             
            return_string += '\n'    
            return return_string
    
    
    """Module Manager Init()"""    
    def __init__(self):
        self._module_definitions = []
        
    def read_module_definitions(self, path):
        self._module_definitions = []
        if (os.path.exists(path)):
            file = open(path, 'r')
            text = file.read()
            file.close()
          
            for result in re.finditer(Module_manager.MODULE_EXPRESSION, text):
                resultDict = result.groupdict()
                if resultDict['defines']:
                    resultDict['defines'] = resultDict['defines'].split("\n")
                    
                definition = Module_manager.Module_definition(**resultDict)
                self._module_definitions.append(definition)
      
                        
    def write_module_definitions(self, path):
        file = open(path, 'w')
        for entry in self._module_definitions:
            file.write(str(entry))
        
        file.close()

                           
    def __get_definitions(self, search_list, key, value):
        results = []
        for item in search_list:
            if item.__dict__[key] == value:
                results.append(item)
                
        return results
        
          
    def _get_definitions(self, *args, **kwargs):
        result_list = self._module_definitions
        for i in kwargs:
            result_list = self.__get_definitions(result_list, i, kwargs[i])
        return result_list
    
    
    def remove_definitions(self, *args, **kwargs):
        """
        removes all definitions that match the input argument values
        returns the results that were removed from the manager.
        
        example : module_manager_instance.remove_definitions(module_name='generic', platform='win', maya_version='2023')
        """ 
        results = self._get_definitions(**kwargs)
        for result in results:
            self._module_definitions.pop(self._module_definitions.index(result))
            
        return results
    
    def add_definition(self, definition):
        """
        TODO: Add some checks to make sure the definition doesn't conflict with an existing definition
        """
        self._module_definitions.append(definition)
   
    
    
class Application_context(object):
    def __init__(self, *args, **kwargs):
        super(Application_context, self).__init__()
        
    @staticmethod
    def get_app_version():
        return 0   
    
    @staticmethod
    def get_platform():
        result = platform.platform().lower()
        if 'darwin' in result:
            return Platforms.OSX
        elif 'linux' in result:
            return Platforms.LINUX
        elif 'window' in result:
            return Platforms.WINDOWS
        else:
            raise ValueError('Unknown Platform Type:{0}'.format(result))
    
    @staticmethod
    def make_folder(folder_path):
        print(folder_path)
        
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)

    def get_ui_parent(self):
        return None
 
    """
    return a thread for running the install process
    """
    def get_install_thread(self):
        None
                
    """
    run any logic to prepare your system for the install
    Returns true if the install can continue
    """
    def pre_install(self):        
        return False
    
    """
    Will be called if pre_install() is successful.
    User is responsible for calling post_install() however they see fit.
    """
    def install(self):
        pass
    
    def post_install(self):
        pass
    

class Maya_context(object):
    MODULE_NAME = 'syncSketch'
    MODULE_VERSION = 1.0
    
    SYNCSKETCH_PY_API_RELEASE_PATH = r'https://github.com/syncsketch/python-api/archive/v1.0.7.8.zip'   
    SYNCSKETCH_GUI_RELEASE_PATH = r'https://github.com/Nathanieljla/syncsketch-maya/archive/refs/tags/v1.3.6-alpha.zip'
 
    def __init__(self, *args, **kwargs):
        super(Maya_context, self).__init__(*args, **kwargs)
        
        self.version_specific = False
        self.version = self.get_app_version()
        self.platform = Application_context.get_platform()
        
        print('Python Version: {0}'.format(sys.version))
        self.max, self.min, self.patch = sys.version.split(' ')[0].split('.')
        self.max = int(self.max)
        self.min = int(self.min)
        self.patch = int(self.patch)
        
        self.app_dir = os.getenv('MAYA_APP_DIR')
        self.install_root = os.path.join(self.app_dir, 'modules')
        
        
        dev_path = r'C:\Users\natha\Documents\syncsketch-maya'
        if os.path.exists(dev_path):
            Maya_context.SYNCSKETCH_GUI_RELEASE_PATH  = r'git+file:///{0}'.format(dev_path)
        
        if self.max > 2:
            #python3
            self.module_root = os.path.join(self.MODULE_NAME, 'common')
        else:
            #python2
            self.version_specific = True
            self.module_root = os.path.join(self.MODULE_NAME, 'platforms', str(self.version), 
                                               Platforms.get_name(self.platform),
                                               'x64')
        #common locations
        self.module_dir = os.path.join(self.install_root, self.module_root)
        self.icons_dir = os.path.join(self.module_dir, 'icons')
        self.presets_dir = os.path.join(self.module_dir, 'presets')
        self.scripts_dir = os.path.join(self.module_dir, 'scripts')
        self.plugins_dir = os.path.join(self.module_dir, 'plug-ins')
        self.site_packages_dir =  os.path.join(self.scripts_dir, 'site-packages')
                
        self.ffmpeg_dir = os.path.join(self.scripts_dir, 'ffmpeg', 'bin')
        self.syncsketch_install_dir = os.path.join(self.scripts_dir, 'syncsketchGUI')       
        self.get_platform_specific_paths()
        
        
    def get_platform_specific_paths(self):
        version_str = '{0}.{1}'.format(self.max, self.min)
        
        if self.platform == Platforms.WINDOWS:
            self.python_path = os.path.join(os.getenv('MAYA_LOCATION'), 'bin', 'mayapy.exe')
            if self.max > 2:
                #python3 pip path
                self.pip_path = os.path.join(os.getenv('APPDATA'), 'Python', 'Python{0}{1}'.format(self.max, self.min), 'Scripts', 'pip{0}.exe'.format(version_str))
            else:
                #python2 pip path
                self.pip_path = os.path.join(os.getenv('APPDATA'), 'Python', 'Scripts', 'pip{0}.exe'.format(version_str))

        elif self.platform == Platforms.OSX:
            self.python_path = '/usr/bin/python'
            self.pip_path = os.path.join( expanduser('~'), 'Library', 'Python', version_str, 'bin', 'pip{0}'.format(version_str) )
     
        elif self.platform == Platforms.LINUX:
            self.python_path = os.path.join(os.getenv('MAYA_LOCATION'), 'bin', 'mayapy')
            self.pip_path = os.path.join( expanduser('~'), '.local', 'bin', 'pip{0}'.format(version_str) )
                   
    @staticmethod
    def get_app_version():
        return int(str(maya.cmds.about(apiVersion=True))[:4])
    
    @staticmethod
    def get_platform_string(platform):
        if platform is Platforms.OSX:
            return 'mac'
        elif platform is Platforms.LINUX:
            return 'linux'
        else:
            return 'win64'
    
    def get_ui_parent(self):
        return wrapInstance( int(omui.MQtUtil.mainWindow()), QMainWindow)         

    
    def clear_and_add_define(self, module_manager, maya_version):
        maya_version = str(maya_version)
        
        python_path =  'PYTHONPATH+:={0}'.format(self.site_packages_dir.split(self.module_dir)[1])
        relative_path = '.\{0}'.format(self.module_root)        
        platform_name =  self.get_platform_string(Application_context.get_platform())
        
        module_definition = Module_manager.Module_definition(self.MODULE_NAME, self.MODULE_VERSION,
                                                             maya_version=maya_version, platform=platform_name, 
                                                             module_path=relative_path,
                                                             defines=[python_path])
        
        module_manager.remove_definitions(maya_version=maya_version, platform=platform_name)
        module_manager.add_definition(module_definition)        
        
        
    def pre_install(self):
        try:          
            Application_context.make_folder(self.module_dir)       
            Application_context.make_folder(self.icons_dir)
            Application_context.make_folder(self.presets_dir)
            Application_context.make_folder(self.scripts_dir)
            Application_context.make_folder(self.plugins_dir)
            Application_context.make_folder(self.site_packages_dir)
        except OSError:
            return False

        filename = os.path.join(self.install_root, (self.MODULE_NAME + '.mod'))  
        module_manager = Module_manager()
        module_manager.read_module_definitions(filename)
        
        #We could setup extra logic if we need unique install paths for future versions of Maya
        if self.version > 2020:
            #python3 shares a common folder
            self.clear_and_add_define(module_manager, 2023)
            self.clear_and_add_define(module_manager, 2022)
        else:
            self.clear_and_add_define(module_manager, self.version)
          
        try:
            module_manager.write_module_definitions(filename)
        except IOError:
            return False
        
        return True
    
    def get_install_thread(self):
        return Maya_install_thread()
    
    
    """
    Runs the install in a non-threaded manner.  Mainly here for debugging with WING-IDE
    """
    def install(self):
        self.thread = Maya_install_thread()
        self.thread.startInstallationProcess()
        
    def post_install(self):
        # Install the Shelf
        if InstallOptions.installShelf:
            from syncsketchGUI import install_shelf, uninstall_shelf
            uninstall_shelf()
            install_shelf()

        #Load Plugin And Autoload it
        if self.plugins_dir not in os.environ['MAYA_PLUG_IN_PATH']:
            print('plug-in dir:{0}'.format(self.plugins_dir))
            os.environ['MAYA_PLUG_IN_PATH'] += r';{0}'.format(self.plugins_dir)
        
        try:
            maya.cmds.loadPlugin('SyncSketchPlugin')
            maya.cmds.pluginInfo('SyncSketchPlugin',  edit=True, autoload=True)
        except Exception as e:
            print('FAILED to load plug-in:{0}'.format(e))
            
        #Create Default's for current OS
        self.createGoodDefaults()

    def createGoodDefaults(self):
        '''
        Adds default setting's to have a good starting point for the tool
        '''
        import yaml
        print('sscache: {0}'.format(self.scripts_dir))
        syncsketch_cache = os.path.join(self.scripts_dir, 'syncsketchGUI', 'config', 'syncsketch_cache.yaml')
        print('sscache: {0}'.format(syncsketch_cache))

        with open(syncsketch_cache, 'r') as f:
            config = yaml.safe_load(f)

        if self.platform == Platforms.OSX:
            config['current_preset'] = 'HD720p (OSX)'
        elif self.platform == Platforms.WINDOWS:
            config['current_preset'] = 'HD720p (Windows)'
        print(config)

        with open(syncsketch_cache, 'w') as f:
            yaml.safe_dump(config, f)
    
    
if MAYA_RUNNING:
    class Maya_install_thread(QThread):
        '''Main Process that drives all installation'''
    
        def __init__(self):
            QThread.__init__(self)
            self.install_failed = False
    
        def __del__(self):
            self.wait()
    
        def run(self):
            self.startInstallationProcess()
            
            
        def run_shell_command(self, cmd, description):
            #NOTE: don't use subprocess.check_output(cmd), because in python 3.6+ this error's with a 120 code.
            print('\nInstalling : {0}'.format(description))
            print('Calling shell command: {0}'.format(cmd))

            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = proc.communicate()
            print(stdout)
            print(stderr)
            if proc.returncode:
                raise Exception('install Failed:\nreturn code {0}:\nstderr:{1}\n'.format(proc.returncode, stderr))

    
        def startInstallationProcess(self):
            tmpdir = None
            delete_tmpdir = False
            cmd = ''
        
            fake_install = False
            if fake_install:
                time.sleep(5)
                return True
        
            try:
                if not INSTALL_SSGUI_ONLY:
                    ##--1. Get a non-maya pip installed and install dependencies
                    # Create a temporary directory to act as a working directory if we were not given one.
                    if tmpdir is None:
                        tmpdir = tempfile.mkdtemp()
                        delete_tmpdir = False
    
                    # Save get-pip.py, do this by pulling the text online then writing it to disc
                    pipInstaller = os.path.join(tmpdir, 'get-pip.py')                    
                    py_version = '{0}.{1}'.format(CONTEXT.max, CONTEXT.min)
                    print('py version: {0}'.format(py_version))
                    
                    #TODO: Find a solid way to find what version of pipe is
                    # used with each version of python                    
                    pip_folder = '3.6'
                    if CONTEXT.max < 3:
                        pip_folder = '2.7'
                        
                    if CONTEXT.platform == Platforms.OSX:
                        cmd = 'curl https://bootstrap.pypa.io/pip/{0}/get-pip.py -o {1}'.format(pip_folder, pipInstaller).split(' ')
                        self.run_shell_command(cmd, 'get-pip')
    
                    else:
                        # this should be using secure https, but we should be fine for now
                        # as we are only reading data, but might be a possible mid attack
                        response = urlopen('https://bootstrap.pypa.io/pip/{0}/get-pip.py'.format(pip_folder))
                        data = response.read()
                        
                        with open(pipInstaller, 'wb') as f:
                            f.write(data)
    
                    # Install pip
                    # On Linux installing pip with Maya Python creates unwanted dependencies to Mayas Python version, so pip might not work 
                    # outside of Maya Python anymore. So lets install pip with the os python version. 
                    filepath, filename = os.path.split(pipInstaller)
                    sys.path.insert(0, filepath)
                                        
                    #TODO: Determine why they did '19.2.3'
                    #Why is there different split options based on OS?  Can't I just define python_str
                    #based on the platform and use a common split command?  Seems redundant.
                    if CONTEXT.platform == Platforms.OSX or CONTEXT.platform == Platforms.LINUX:
                        python_str = 'python{0}'.format(py_version)
                        if CONTEXT.max > 2:
                            #Python3
                            cmd = '{0} {1} --user pip'.format(python_str, pipInstaller).split(' ')
                        else:
                            #Python2
                            cmd = '{0} {1} --user pip==19.2.3'.format(python_str, pipInstaller).split(' ')
                    else:
                        if CONTEXT.max > 2:
                            #Python3
                            cmd = '{0}&{1}&--user&pip'.format(CONTEXT.python_path, pipInstaller).split('&')
                        else:
                            #Python2
                            cmd = '{0}&{1}&--user&pip==19.2.3'.format(CONTEXT.python_path, pipInstaller).split('&')
                     
                    self.run_shell_command(cmd, 'pip')   
    
                    # Install Dependencies 
                    # What are these dependencies for if they're not being installed into the Maya module?
                    # They seem to be a lot of duplicates of what syncSketchGUI installs into the Maya module. Is this even necessary?
                    cmd = '{0}&install&--force-reinstall&--user&{1}&setuptools&pyyaml&requests[security]'.format(CONTEXT.pip_path,
                                                                                                       CONTEXT.SYNCSKETCH_PY_API_RELEASE_PATH).split('&')
                    self.run_shell_command(cmd, 'syncSketch lib and dependencies')
                    
                    # This needs to exist before we attempt to install ffmpeg
                    # User Site Package Path needs to be in sys.paths, in order to load installed dependencies. 
                    site_package_path = site.getusersitepackages()
                    if not site_package_path:
                        print('Can not find user site package path')
                    elif site_package_path not in sys.path:
                        sys.path.append(site_package_path)
                        print('Add site package path [{}] to system paths'.format(site_package_path))
                    else:
                        print('Site packe path in system paths')
                        
                    site_base = site.getuserbase()
                    if site_base not in sys.path:
                        print('adding user base')
                        sys.path.append(site_base)
                     
                    print('\nInstall FFMPEG Binaries to {}'.format(CONTEXT.ffmpeg_dir))
                    try:
                        FFmpeg.downloadFFmpegToDisc(platform=CONTEXT.platform, moveToLocation=CONTEXT.ffmpeg_dir)
                        print('Finished Installing FFMPEG Binaries')   
                    except Exception as e:
                        #This seems to be failing in 2.7 installs
                        print('Installation of ffmpeg FAILED!:{0}'.format(e))
                        
                 
                ##2.-Install SyncsketchGUI
                #this might be a re-install, so lets try unloading the plug-in to be clean
                try:                    
                    maya.cmds.unloadPlugin('SyncSketchPlugin')
                except Exception as e:
                    print(e)
                
                # * By using target, pip show won't find this package anymore
                if os.path.isdir(CONTEXT.syncsketch_install_dir):
                    shutil.rmtree(CONTEXT.syncsketch_install_dir, ignore_errors=True)
                    # todo: delete as well SyncsketchGUI-1.0.0.dist-info
                    print('Deleting previous directory for a clean install {0} '.format(CONTEXT.syncsketch_install_dir))
    
                cmd = '{0}&install&{1}&--upgrade&--target={2}'.format(CONTEXT.pip_path, CONTEXT.SYNCSKETCH_GUI_RELEASE_PATH,
                                                                     CONTEXT.scripts_dir).split('&')
                
                self.run_shell_command(cmd, 'syncSketch GUI and Dependencies')

                #Our scripts folder won't be seen by Maya until Maya restarts (and reads the module data)
                #so manually add it to sys.path
                if CONTEXT.scripts_dir not in sys.path:
                    sys.path.append(CONTEXT.scripts_dir)
                    print('Add scripts path [{}] to system paths'.format(CONTEXT.scripts_dir))
                else:
                    print('scripts path in system paths')
                        
                fromSource = os.path.join(CONTEXT.syncsketch_install_dir, 'SyncSketchPlugin.py')
                toTarget = os.path.join(CONTEXT.plugins_dir, 'SyncSketchPlugin.py')
                print('Copy From : {} to: {}'.format(fromSource, toTarget))
                try:
                    shutil.copy(fromSource, toTarget)
                except Exception as e:
                    print('copying plug-in failed')
                    raise e
    
            except Exception as e:
                self.install_failed = True
                print(e)
    
            finally:
                # Remove our temporary directory
                if delete_tmpdir and tmpdir:
                    print('cleaning up temporary files: {0}'.format(tmpdir))
                    shutil.rmtree(tmpdir, ignore_errors=True)
    


###--------------------------------------------------------------------
###----Start UI  Code                    
###--------------------------------------------------------------------
    
#preloaderAnimBase64 = '''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'''
#byteArraseGif = QByteArray.fromBase64( preloaderAnimBase64.encode() )
#Ressources.GIFDEVICE = QBuffer(byteArraseGif)
#print('device successfully opened: {0}'.format(Ressources.GIFDEVICE.open(QIODevice.ReadOnly)))

syncsketchURL = 'http://www.syncsketch.com'
syncsketchMayaPluginRepoURL  = 'https://github.com/syncsketch/syncsketch-maya'
syncsketchMayaPluginVideoURL = 'https://vimeo.com/syncsketch/integrationmaya'
syncsketchMayaPluginDocsURL = 'https://support.syncsketch.com/article/62-maya-syncsketch-integration'
    

class Icon():
    def __init__(self, base64Image):
        self.base64Image = base64Image

    def base64ToQPixmap(self):
        pixmap = QPixmap()

        byte_array =  QByteArray.fromBase64( self.base64Image.encode() )
        pixmap.loadFromData(byte_array)
        return pixmap


class InstallOptions(object):
    def __init__(self):
        pass
    
    installShelf = 1
    upgrade = 0
    tokenData = {}


class Resources(object):
    def __init__(self):
        pass

    preloaderAnimBase64 = '''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'''
    byteArraseGif = QByteArray.fromBase64( preloaderAnimBase64.encode() )
    GIFDEVICE = QBuffer(byteArraseGif)

    companyLogoBase64 = '''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'''
    companyLogo = QPixmap(Icon(companyLogoBase64).base64ToQPixmap())

    base64Image = '''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'''
    Olaf = QPixmap(Icon(base64Image).base64ToQPixmap())

    base64Image = '''iVBORw0KGgoAAAANSUhEUgAAAFgAAABYCAYAAABxlTA0AAAABHNCSVQICAgIfAhkiAAAAAlwSFlzAAALEwAACxMBAJqcGAAAA2NJREFUeJztnN9RGzEQh3+ryTvuIHQAqSCOzn4OJUAFoYO4BKeCpAR4PkvjdGA6oATTgDYvx4xjwv3x7Z7kyX5v3N5I6w8h6eQ9AMMwDMMwDMMwDMMwDMMwDON/gHIn0JcY4+fDn733v3PlMoTiBdd1feGcewYwO7zOzNvFYvElT1b9cbkT6MI5t8aRXAAgonkI4XuGlAZRvGAANy2x+8myOJFzEPxm9PaMFcE5CD5rTLAyJlgZE6yMCVbGBCtjgpX5oNHoZrP5hr8fEPbOuZX3/kmjv6HEGK9SSuvDa865tff+Ubov8bOIGONXZn74R+g5pXS9XC5fhrQXQuC2eFVVgz5Dc7axA3B5FNoT0Vx6EIhPESml1TuhSyLa1nV9Id1nX+q6viCiLd7KBYDZ8aiWQFwwEV23xXJJfpXbkd9cut/JF7kckvvI1UJcMDNvu+6ZUvIQuX1yH4q4YOfcPYB9131TSB44cvdN7qKIC/bePzVzWVbJQ+Vq7CAApTk4t+RS5AKKi1wuySXJBZR3EVNLLk0uMME2bSrJJcoFJtoHa0suVS4wcV1EjPGq2Wt2flnJzDtmnjvnWn8pKaVZqXKBDIUnQyV3ietzT8PkcoFMlT1DJAuRRS6QsXRqQsnZ5AKZa9MmkJxVLlBA8Z+i5OxygQIEAyqSi5ALFCIYEJVcjFygIMGAiOSi5AKFCQZGSS5OLiAoWLLE/wTJo+VqvaIwWrBWif8AyaPkar+iMPqwR6vEv+cB0eiRq/2KgsRpmlqJfyP59p2w1Jyr+oqChGDVEn/v/SMRXTPz7vUaM29TSpdCC5pq/iq1adI0Ij/lzuMU1A/cY4xX2n2cyvHOQYPRgruKNVJK87F9aJFSap1jJQpRRk8RRPTcEV9tNhsw86+hlZVahBA+MvOaiNoWOBDRri3eh9GCmXnbstIDwIyI1kS0DiGM7U4Mou5HgKYScxQSU8QDenyZeYbsJQqyRwtu/uzF62pzw8wriXZEdhEppfXhPvXcYebdYrH4IdGWiODlcvnCzHON8s+pYeYtM8+l2hM/rgwh/ARwK93uRPyqqupOskHxB42qqu6Y+RZntvAx8720XEDxwL0pZ7oBcNOcihX3rweaKe2hpD26YRiGYRiGYRiGYRiGYRiGYRiGYRjD+AN6etoeN+hk/AAAAABJRU5ErkJggg=='''
    installIcon = QPixmap(Icon(base64Image).base64ToQPixmap())

    base64Image = '''iVBORw0KGgoAAAANSUhEUgAAAFgAAABYCAYAAABxlTA0AAAAGXRFWHRTb2Z0d2FyZQBBZG9iZSBJbWFnZVJlYWR5ccllPAAAAyNpVFh0WE1MOmNvbS5hZG9iZS54bXAAAAAAADw/eHBhY2tldCBiZWdpbj0i77u/IiBpZD0iVzVNME1wQ2VoaUh6cmVTek5UY3prYzlkIj8+IDx4OnhtcG1ldGEgeG1sbnM6eD0iYWRvYmU6bnM6bWV0YS8iIHg6eG1wdGs9IkFkb2JlIFhNUCBDb3JlIDUuNS1jMDE0IDc5LjE1MTQ4MSwgMjAxMy8wMy8xMy0xMjowOToxNSAgICAgICAgIj4gPHJkZjpSREYgeG1sbnM6cmRmPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5LzAyLzIyLXJkZi1zeW50YXgtbnMjIj4gPHJkZjpEZXNjcmlwdGlvbiByZGY6YWJvdXQ9IiIgeG1sbnM6eG1wPSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvIiB4bWxuczp4bXBNTT0iaHR0cDovL25zLmFkb2JlLmNvbS94YXAvMS4wL21tLyIgeG1sbnM6c3RSZWY9Imh0dHA6Ly9ucy5hZG9iZS5jb20veGFwLzEuMC9zVHlwZS9SZXNvdXJjZVJlZiMiIHhtcDpDcmVhdG9yVG9vbD0iQWRvYmUgUGhvdG9zaG9wIENDIChNYWNpbnRvc2gpIiB4bXBNTTpJbnN0YW5jZUlEPSJ4bXAuaWlkOkZFN0ZCOTgzMjEzNzExRTlBRjJDRTMwNUFDQzg3MDUyIiB4bXBNTTpEb2N1bWVudElEPSJ4bXAuZGlkOkZFN0ZCOTg0MjEzNzExRTlBRjJDRTMwNUFDQzg3MDUyIj4gPHhtcE1NOkRlcml2ZWRGcm9tIHN0UmVmOmluc3RhbmNlSUQ9InhtcC5paWQ6RkU3RkI5ODEyMTM3MTFFOUFGMkNFMzA1QUNDODcwNTIiIHN0UmVmOmRvY3VtZW50SUQ9InhtcC5kaWQ6RkU3RkI5ODIyMTM3MTFFOUFGMkNFMzA1QUNDODcwNTIiLz4gPC9yZGY6RGVzY3JpcHRpb24+IDwvcmRmOlJERj4gPC94OnhtcG1ldGE+IDw/eHBhY2tldCBlbmQ9InIiPz6CenaqAAADF0lEQVR42uycTWsTURiFJ6FL9Qd0VRAUF1JKa6mC6EbwFyiIO5EillYXfiEKbhQCVgXRUks3UrAL125ctGBBWqjoQhCFoCbqhASsiAtdxHPhHQglaSY392vSc+AwyfTeyfTpy7n3TUJz9Xo9ouwpTwQETMAUARMwAVMETMAETBEwAVMETMAETBEwARMwRcAETMAUARMwRcC+1Of7Bo5cPury5V7A7+AryYnlwlJvA3aoBfi4uAjPMCLMwj3V8PwxfHFbRIQDPYNPNjk/DefkyArW1GILuInuYg04R8D6sXAixbhHgDxOwN1lbjvNAPJ1Ak6npx3CTTRBwO31BD6tMa8MD3IXYTYWEpXgETQcFVawebhf4WHAjbnImc/css3K7RXAC5qZ+0lVLlyxfYNZzuDZLjJ3DK6xVW6tOfiMZuaOuILrLCKwid8NXzKYuTpwywK34rIS8g7g7sDhJVzA4weeMrfsKnOdAgbQXTi8ggfk1CTO3XacuVX4IBxHHpS3DHetSYd0DT+70+HlHsJnNTN3SI5RzwAGwJ04rMJ7Wgy5ijH3Ul5uHj7fReaWfK7GfZYq9zW8t83QCxir/sBTttpfH5lrtYIBrF9iYV/KKZPwfcNwv8uCFkcByHREPN8iFlpJVfCtJpmru6CNhVC5tgDfgH9pzLupFj95PK2Zud8kFr6E1BEZBbxcWFL73VF4Q2O62r6p7yzofNpbklj4HFrLaXwXAcgfpJL+aEzf30Xm/gixp7eyTQNk9W7VIfif5fsPLnOdNRqA/FZ++d+WXqIWYuY6bZUBeV0gbFio3AMhZq5TwJsy+aehSybtbzHKgJy8XSmZPGogk6shtL/BARbIHyWTdSHXQml/gwTckMkK8l8NuJnIXK+AGyAPdZDJsexzi1EG5eVTZUB+nzKTVeYOZrFyvQJOmclJ5sZRhuX1exFbZHJmMzcowKL1TZVczXLmhghY6Q18DF6BD/dC5SbK8d/bbo8KJmCKgAmYgCkCJmCKgAmYgCkCJmACpgiYgAmYCAiYgCkCJmACpgiYgAmYMq3/AgwA+XHGcJ7d4J4AAAAASUVORK5CYII='''
    launchIcon = QPixmap(Icon(base64Image).base64ToQPixmap())

    base64Image = '''iVBORw0KGgoAAAANSUhEUgAAAFgAAABYCAYAAABxlTA0AAAABHNCSVQICAgIfAhkiAAAAAlwSFlzAAALEwAACxMBAJqcGAAAA7lJREFUeJztm8tx2zAQhv9lA3YHdiqwO4iGpM5xB6Y7UAdRKohSQeQO5DMfo3Qgd6B0IDfAzSHgjOwhJQDCgvTMfleCXPIbEI8FACiKoiiKoiiKoiiKoiiKoiiKoiiKoijKECT14LqubwAUzDwDACLatW27nM/nb1IxbWia5o6ZF8x8a95rT0SrNE1fJeKJCK7r+ieARc+ldZZlTxIxbSjL8oqItkR0//EaEd1LSA4u2NSQ3Yki67ZtF7Frcl3XN8y86ZNr2GdZ9iV03CT0A5n54UyRgoi2ZVlehY49RNM0dwB2J+QCwK1EbAnBh3NliOg+lmTzR20BXEvH6iO44CRJtjblYkh2kXumWfMmuOA0TV+ZeWNTlojukyTZm184KFVVPRpptjV3HfodAAHBAMDMhUONuGbmbUjJVVU9EtHa4ZZ1nue/QsU/RkTwfD5/Y+aZ+T1tCCbZQ+5KcugoNtHoqOv6N4DCsviBmRd5nj97xhoaf/fCzIVvLFvEBQPOkr0+PEYMH6IIBmQFTFUuEFEw4NU+LrMs+zF00Ux910R0bnLTcSCimVTeoY+oggG/Hr6vEzqVVxggulxgBMHA5ZI/i1xgJMEA0DTNVzMhsZ4ItG27SJLk+kzS5h3MvCOihyzL/vq/rT+jCQbc8wRG1q1LeWaejZmDHlUwIJeMmYJcQGgm50Kapq9ENAuZbGHmzRTkAhOowR0eHdcQo66afGQygoEgkiclF5hAE3GMR5LoGNGkjS+TEgz8l0xEW8fbDh73RGFSTQTgnlc4JmaOwZZJCb5EbsfUJE9CcFmWV0mSrHCh3A6TUxZZoXBldMEBh2cfmcSIYtROzidp4/D4wjQ5ozKaYFe5Jg8xM7lfW9GjSx6lifBJ8hxPfS+9PybRBYeS81kkR20iPKRsh6R0SSIAe5tnxdyu9S5urEBmFWMFhwS7zSjAo6PcE9FDrNWNKIJDrcMNMeUlJHHB0nI7pipZVHBd198BLG3Lh5jmuu4kIqIiTdOXS2KeQvKMxmibQaa0EUVEsGuzIPGBrpJNxxe8JosM04hoaVn0QEQzidqTZdkTM1tvBGzbdhn6HQABwVVVPcLuvEPXyfwJ/Q4deZ7/YubCpqxAsgmAgGCzb+Ec0YZJeZ4/20qWQELwyeMDXdIm5jamPM+fLZJEe4nYImc0AKz6rnX5gDH2iKVp+mKm1n2S9w47NJ0QG6Y1TfOtbdvjTmbNzJuxN4P0HPHdj3EwUlEURVEURVEURVEURVEURVEURVEURVGAf9l4XANGvwF5AAAAAElFTkSuQmCC'''
    closeIcon = QPixmap(Icon(base64Image).base64ToQPixmap())
   
##Seems to be a mixin class, but I'm removing for simplicity sake. 
#class UIDesktop(object):
    #def __init__(self, name, size=[300, 300], *args, **kwargs):
        #self.setObjectName(name)

        #width = size[0]
        #height = size[1]    
        #desktop = QApplication.desktop()
        #screenNumber = desktop.screenNumber(QCursor.pos())
        #screenRect = desktop.screenGeometry(screenNumber)
        #widthCenter = screenRect.width() / 2 - width / 2
        #heightCenter = screenRect.height() / 2 - height / 2
        #self.setMinimumSize(QSize(*size))
        #self.setGeometry(QRect(widthCenter, heightCenter, width, height))
        ##TODO: Fix
        ##self.setWindowIcon(Ressources.Olaf)


class LinkButton(QPushButton):
    def __init__(self, text, link, *args, **kwargs):
        super(LinkButton, self).__init__(text, *args, **kwargs)
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setFlat(True)
        self.setMaximumHeight(20)
        self.setStyleSheet('QPushButton {text-decoration: underline; color: #00c899}')
        self.clicked.connect(lambda: webbrowser.open(link, new=0, autoraise=True))


class IconButton(QPushButton):
    def __init__(self, text, highlight=False, icon=None, success=False, *args, **kwargs):
        super(IconButton, self).__init__(QIcon(icon), text, *args, **kwargs)

        self.icon = icon
        self.highlight = highlight
        self.success = success
        self.setMinimumHeight(34)
        self.setCursor(QCursor(Qt.PointingHandCursor))
        if self.highlight:
            self.setStyleSheet('QPushButton{color: #161a1d; background-color: #00a07b; border: none; border-radius: 3px; padding: 10px;} QPushButton:hover {background-color: #00c899}')
            font = self.font()
            font.setPointSize(14)
            font.setBold(True)
            self.setFont(font)

        if self.success:
            self.setStyleSheet('QPushButton{color: #161a1d; background-color: #dfefd9; border: none; border-radius: 3px; padding: 10px;}')
            font = self.font()
            font.setPointSize(14)
            font.setBold(True)
            self.setFont(font)

        if self.icon:
            self.setIconSize(QSize(22, 22))
            self.setIcon(QIcon(self.AlphaImage()))

    def AlphaImage(self):
        if self.highlight and not self.success:
            AlphaImage = QPixmap(self.icon)
            painter = QPainter(AlphaImage)

            painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
            painter.fillRect(AlphaImage.rect(), '182828')

            return AlphaImage

        else:
            return QPixmap(self.icon)   


class Installer_UI(QWidget):
    def __init__(self, parent, *args, **kwargs):
        super(Installer_UI, self).__init__(*args, **kwargs)

        size = [350, 300]
        name = 'Syncsketch Maya Installer'

        width = size[0]
        height = size[1]    
        desktop = QApplication.desktop()
        screenNumber = desktop.screenNumber(QCursor.pos())
        screenRect = desktop.screenGeometry(screenNumber)
        widthCenter = screenRect.width() / 2 - width / 2
        heightCenter = screenRect.height() / 2 - height / 2
        self.setMinimumSize(QSize(*size))
        self.setGeometry(QRect(widthCenter, heightCenter, width, height))
        self.setWindowIcon(Resources.Olaf)        
        
        self.setObjectName(name)
        self.setWindowTitle(name)
        self.setWindowModality(Qt.ApplicationModal)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setWindowFlags(Qt.Tool)
        self.setFixedSize(QSize(*size))

        self.createLayout()
        self.installButton.clicked.connect(self.__syncsketchInstall)
        self.closeButton.clicked.connect(self.__closeButton)
        self.launchButton.clicked.connect(self.__launchButton)


    def done(self):
        self.launchButton.show()
        self.closeButton.hide()
        self.animatedGif.hide()
        self.waitLabel.hide()

        if self.install_thread.install_failed:
            print('Install FAILED! See output.')
            return
                
        if InstallOptions.upgrade == 1:
            restoreCredentialsFile()
            self.upgradeInfo.setText('Upgrade Successful')
            self.subtext.setText('.')
            self.upgradeInfo.setStyleSheet(
                'QLabel {color: #00a17b; font: 16pt}')
            self.launchButton.hide()
            
        CONTEXT.post_install()
        ## Add TimeLineMenu's if they doesn't exist
        
    def __syncsketchInstall(self):
        print('installing')   
        self.installButton.hide()
        self.closeButton.hide()
        self.installShelf.hide()
        self.animatedGif.show()
        self.waitLabel.show()
        
        if CONTEXT.pre_install():
            self.install_thread = CONTEXT.get_install_thread()
            self.connect(self.install_thread, SIGNAL('finished()'), self.done)
            self.install_thread.start()
            #CONTEXT.install() ##used instead of start() for debugging in wing.

    def __closeButton(self):
        self.close()

    def __launchButton(self):
        self.close()
        # Open UI
        from syncsketchGUI import standalone
        reload(standalone)
  
    def clean(self):
        if Resources.GIFDEVICE.isOpen():
            Resources.GIFDEVICE.close()

    def closeEvent(self, event):
        self.clean()
  
    def checkBoxChanged(self, state, name):
        if name == 'installShelf':
            InstallOptions.installShelf = state

    def createLayout(self):
        outer = QVBoxLayout()
        self.setLayout(outer)

        self.movie = QMovie()
        device = None
        if not Resources.GIFDEVICE.isOpen():
            print('Resources.GIFDEVICE successfully opened: {0}'.format(Resources.GIFDEVICE.open(QIODevice.ReadOnly)))
            if Resources.GIFDEVICE.isOpen():
                device = Resources.GIFDEVICE
        else:
            #will be true when re-opening the installer UI
            device = Resources.GIFDEVICE
            
        self.movie.setDevice(device)
        self.animatedGif = QLabel()

        self.animatedGif.setMovie(self.movie)
        self.animatedGif.setMaximumHeight(24)
        self.animatedGif.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.animatedGif.setScaledContents(True)
        self.animatedGif.setMaximumWidth(24)
        self.movie.start()

        logo = QLabel()
        smallLogo = Resources.companyLogo.scaled(240, 110, Qt.KeepAspectRatio, Qt.SmoothTransformation)

        logo.setPixmap(smallLogo)
        logo.setAlignment(Qt.AlignCenter | Qt.AlignCenter)
        logo.setMargin(15)
        outer.addWidget(logo, 0)
        self.subtext = QLabel(
            u'Update Available: Would you like to upgrade to the latest?' if InstallOptions.upgrade else 'SyncSketch Integration for Maya [{} cut]'.format(versionTag))
        outer.addWidget(self.subtext)
        self.subtext.setAlignment(Qt.AlignCenter | Qt.AlignCenter)
        self.subtext.setMargin(5)

        palette = self.palette()
        palette.setColor(self.backgroundRole(), '#2b353b')
        self.setPalette(palette)

        infoLayout = QHBoxLayout()
        infoLayout.addStretch()
        infoLayout.setContentsMargins(0, 0, 0, 0)
        infoLayout.setSpacing(0)
        outer.addLayout(infoLayout, 0)
        infoLayout.setAlignment(Qt.AlignCenter | Qt.AlignCenter)

        if not InstallOptions.upgrade:
            tutorialButton = LinkButton('Tutorial Video', link=syncsketchMayaPluginVideoURL)
            infoLayout.addWidget(tutorialButton, 0)

            repoButton = LinkButton('Github Repo', link=syncsketchMayaPluginRepoURL)
            infoLayout.addWidget(repoButton, 0)

            documentationButton = LinkButton('Documentation', link=syncsketchMayaPluginDocsURL)
            infoLayout.addWidget(documentationButton, 0)
        else:
            from syncsketchGUI.installScripts.maintenance import getLatestSetupPyFileFromLocal, getLatestSetupPyFileFromRepo

            fromVersion = getLatestSetupPyFileFromLocal()
            toVersion = getLatestSetupPyFileFromRepo()
            self.upgradeInfo = QLabel(
                u'Upgrading from {} to {}'.format(fromVersion, toVersion))
            self.upgradeInfo.setAlignment(Qt.AlignCenter | Qt.AlignCenter)
            self.upgradeInfo.setMargin(5)
            self.upgradeInfo.setStyleSheet(
                'QLabel {color: #00c899; font: 16pt}')
            outer.addWidget(self.upgradeInfo)


        spacer = QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Expanding)
        outer.addItem(spacer)

        self.installShelf = QCheckBox('Create Syncsketch Shelf (recommended)', self)
        self.installShelf.setChecked(True)
        self.installShelf.stateChanged.connect(partial(self.checkBoxChanged, 'installShelf'))
        subLayout2 = QVBoxLayout()
        subLayout2.setContentsMargins(0, 0, 0, 0)
        subLayout2.setSpacing(0)
        subLayout2.setAlignment(Qt.AlignCenter)

        outer.addLayout(subLayout2, 0)
        spacer = QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Expanding)
        infoLayout.addItem(spacer)

        ButtonLayout = QHBoxLayout()
        ButtonLayout.setAlignment(Qt.AlignCenter)
        ButtonLayout.addWidget(self.installShelf, 0)

        ButtonLayout.addStretch()
        outer.addLayout(ButtonLayout)
        self.installButton = IconButton('Upgrade' if InstallOptions.upgrade else 'Install', highlight=True)
        self.launchButton = IconButton('Launch Syncsketch UI', highlight=True, success=True)
        self.launchButton.hide()
        self.closeButton = IconButton(' Close', icon=Resources.closeIcon)

        #ButtonLayout.addWidget(self.closeButton)
        ButtonLayout.addWidget(self.launchButton)
        ButtonLayout.addWidget(self.installButton)
        ButtonLayout.setAlignment(Qt.AlignCenter)
        #self.closeButton.setMaximumWidth(130)

        self.progressLayout = QHBoxLayout()
        self.progressLayout.setAlignment(Qt.AlignCenter)

        self.waitLabel = QLabel()
        self.waitLabel.setText('Installing, please wait ...')
        self.progressLayout.addWidget(self.animatedGif)
        self.progressLayout.addWidget(self.waitLabel)

        self.progressLayout.addStretch()
        outer.addLayout(self.progressLayout)
        self.animatedGif.hide()
        self.waitLabel.hide()
             
                    
def main(install = False):    
    global CONTEXT
    if MAYA_RUNNING:
        CONTEXT = Maya_context()
        Installer = Installer_UI(CONTEXT.get_ui_parent())
        Installer.show()          
    
    if CONTEXT is None:
        print('No context found')
        return       
    
           
def onMayaDroppedPythonFile(*args):
    main(True)
    
"""
Run is a function used by WingIDE to execute code after telling Maya to import the module
"""
def Run():
    main(True)
    

if __name__ == "__main__":
    main(True)