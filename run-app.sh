#!/bin/bash
cd /dvutil/dvlogparser/
source .venv/bin/activate
python3 cloudwatch.py log_auto /opt/datavirtuality/dvserver/standalone/log/server.log
