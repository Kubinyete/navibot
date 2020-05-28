#!/usr/bin/python3
# Launcher versão daemon
import logging
import os
import sys

from daemons.prefab import run
from navibot.client import Bot

NAVI_TMP            = '/var/tmp'
NAVI_PATH           = os.path.dirname(os.path.abspath(__file__))
NAVI_PIDFILE        = os.path.join(NAVI_TMP, 'navibot.pid')
NAVI_LOGFILE        = os.path.join(NAVI_PATH, 'navibot.log')
NAVI_ENABLE_LOGGING = False

class NaviDaemon(run.RunDaemon):
    def run(self):
        bot = Bot(
            path=NAVI_PATH,
            logenable=NAVI_ENABLE_LOGGING,
            logfile=NAVI_LOGFILE if NAVI_ENABLE_LOGGING else None,
            loglevel=logging.INFO
        )
        
        bot.listen()

def show_usage():
    print(f"Uso:\n\n{sys.argv[0]} <start|stop|restart>")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        action = sys.argv[1]

        d = NaviDaemon(
            pidfile=NAVI_PIDFILE
        )

        if action == "start":
            d.start()
        elif action == "stop":
            d.stop()
        elif action == "restart":
            d.restart()
        else:
            show_usage()
    else:
        show_usage()
