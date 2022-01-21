#!/bin/bash

#### Download and buildPython 3.9 on Amazon Linux 2
mkdir ~/python_install
cd ~/python_install
wget https://www.python.org/ftp/python/3.9.9/Python-3.9.9.tar.xz
tar xvf Python-3.9.9.tar.xz
cd Python-3.9.9
./configure --enable-optimizations
sudo make altinstall
