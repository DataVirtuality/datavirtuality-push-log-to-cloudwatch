#!/bin/bash

cd /dvutil/dvlogparser
python3.9 -m venv .venv
source .venv/bin/activate
pip3 list --outdated --format=freeze | grep -v '^\-e' | cut -d = -f 1 | xargs -n1 pip3 install -U
pip3 install tzlocal boto3 more-itertools
