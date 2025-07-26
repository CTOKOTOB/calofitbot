#!/bin/bash

#17 */4 * * * sh  /usr/bin/bash ~/calofitbot/restart_calofitbot.sh

SERVICE_NAME="calofitbot.service"

if systemctl is-active --quiet "$SERVICE_NAME"; then sudo /usr/bin/systemctl restart "$SERVICE_NAME"; else exit 0; fi

