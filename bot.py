#!/usr/bin/python3
import logging
from navibot import Bot

if __name__ == "__main__":
    Bot("release/config.json", loglevel=logging.INFO).listen()