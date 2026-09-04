import urllib.request
import os

# basic files for Python installation
# before 3.12
py_list = ["core", "dev", "exe", "lib", "tcltk", "tools"]
# after 3.12
#py_list = ["core", "dev", "exe", "lib", "tcltk"]
# Python version
version = "3.12.9"
# Python msi download URL
ftp = "https://www.python.org/ftp/python/" + version + "/amd64/"
# location for Portable Python
path = "Y:\\tmp\\Python312"
# create directory
try:
    os.mkdir(path)
except:
    # path exists
    pass
# get Python installation msi files and extract into target dir
for i in py_list:
    filename = i + ".msi"
    url = ftp + filename
    # download basic python msi file
    urllib.request.urlretrieve(url, filename)
    os.system("msiexec.exe /a " + i + ".msi targetdir=" + path)
    # delete msi files
    os.remove(i + ".msi")
    # delete msi files in path
    os.remove(path + "\\" + i + ".msi")

# https://bootstrap.pypa.io/get-pip.py
