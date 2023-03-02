from setuptools import setup, find_packages

setup(
    name = 'SyncsketchGUI',
    version = '1.3.3',
    url = 'https://github.com/Nathanieljla/syncsketch-maya.git',
    author = '3D CG Guru',
    author_email = "developer@3dcg.guru",
    description = "Syncsketch GUI for Autodesk Maya with python 3.x",
    packages = find_packages(),
    include_package_data = True,
    python_requires='>=3',
    package_data = {'syncsketchGUI.config': ['*.yaml']},
    install_requires = [
          "requests",
          "syncsketch",
          "pyyaml"
    ],
)