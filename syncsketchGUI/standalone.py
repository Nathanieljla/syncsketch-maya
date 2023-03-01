import sys
import os
import importlib

main_folder = os.path.dirname(__file__)
parent_folder = os.path.dirname(main_folder)
sys.path.append(parent_folder)

import syncsketchGUI
importlib.reload(syncsketchGUI)
syncsketchGUI.reload_toolkit()
syncsketchGUI.show_menu_window()