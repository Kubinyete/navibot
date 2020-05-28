#!/usr/bin/python3
# Simples launcher apenas para efetuar testes, será trocado por um daemon futuramente.
import logging
import os

from navibot.client import Bot

NAVI_PATH           = os.path.dirname(os.path.abspath(__file__))
NAVI_ENABLE_LOGGING = True

if __name__ == "__main__":
    bot = Bot(
        path=NAVI_PATH,
        logenable=NAVI_ENABLE_LOGGING,
        logfile=None,
        loglevel=logging.INFO
    )
    
    bot.listen()