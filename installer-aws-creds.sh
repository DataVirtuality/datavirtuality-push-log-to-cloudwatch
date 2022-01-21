#!/bin/bash

#### Download code from GitHub
sudo rsync -r /home/ec2-user/.aws /opt/datavirtuality/
sudo chown -R datavirtuality:datavirtuality /opt/datavirtuality/.aws
