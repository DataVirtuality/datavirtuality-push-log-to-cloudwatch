#!/bin/bash

#### Download code from GitHub
cd /
sudo rm -rf /dvutil
sudo mkdir /dvutil
sudo chown -R datavirtuality:datavirtuality /dvutil
sudo su - datavirtuality
cd /dvutil
git clone https://github.com/DataVirtuality/datavirtuality-push-log-to-cloudwatch.git dvlogparser
exit
cd /dvutil/dvlogparser
sudo chmod 774 *.sh
