import sys
import os
try:
    #python2
    reload
except:
    #python3
    import importlib.reload as reload

main_folder = os.path.dirname(__file__)
parent_folder = os.path.dirname(main_folder)
sys.path.append(parent_folder)

import syncsketchGUI
reload(syncsketchGUI)
syncsketchGUI.reload_toolkit()
syncsketchGUI.show_menu_window()