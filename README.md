# datavirtuality-push-log-to-cloudwatch
Push the Data Virtuality server.log file to AWS CloudWatch

## Guide to running CloudWatch.py

### Install Python3.9 on AMI Linux

https://computingforgeeks.com/how-to-install-python-on-amazon-linux/

#### Install Python build dependencies

sudo yum -y groupinstall "Development Tools"
sudo yum -y install openssl-devel bzip2-devel libffi-devel

##### Download and buildPython 3.9 on Amazon Linux 2

sudo yum -y install wget
mkdir ~/python_install
cd ~/python_install
wget https://www.python.org/ftp/python/3.9.9/Python-3.9.9.tar.xz
tar xvf Python-3.9.9.tar.xz
cd Python-3.9.9
./configure --enable-optimizations
sudo make altinstall

##### Verify correct installation

python3.9 --version
python3.9 -m pip --version

##### Create a virtual environment
mkdir -p /dvutil/dvlogparser/
cd /dvutil/dvlogparser/
python3.9 -m venv .venv
source .venv/bin/activate
pip3 list --outdated --format=freeze | grep -v '^\-e' | cut -d = -f 1 | xargs -n1 pip3 install -U
pip3 install tzlocal boto3 more-itertools

### Run the script

sh ./cw.sh
or
python cloudwatch.py /opt/datavirtuality/dvserver/standalone/log/server.log
