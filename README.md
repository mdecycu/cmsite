# cmsite

利用 init_replit 指令取下子模組並安裝所需 Python 模組

chmod u+x init_replit

./init_replit

cmsimde template uses mdecycu/cmsimde as submodule

On Replit:

for cmsite: git submodule update --init --recursive 

for cmsimde_site: cmsimde is as directory not submodule

for cmsimde: pip install flask flask_cors bs4 lxml pelican markdown gevent

password generator: https://mde.tw/cmsite/content/Brython.html?src=https://gist.githubusercontent.com/mdecycu/b92b16621dd0246c352cf13d6463b333/raw/0bfa669750aba3abe48554509bbd43d65b6e5c82/hashlib_password_generator.py 

for IPv6 only Ubuntu:

.ssh 目錄中的 config, 將 SSH session 名稱設為 github.com:

Host github.com
User git
Hostname github.com
ProxyCommand /usr/bin/ncat --proxy p4.cycu.org:3128 --proxy-type http %h %p

for Replit:

.ssh 目錄中的 config, 將 SSH session 名稱設為 github.com:

Host github.com
User git
Hostname github.co
#since Replit works for IPv4, therefore no ProxyCommand setting needed
#ProxyCommand /usr/bin/ncat --proxy p4.cycu.org:3128 --proxy-type http %h %p

