#!/usr/bin/python3
import sys

from navibot.parser import ExpressionParser

if __name__ == "__main__":
    inputstr = ' '.join(sys.argv[1:])
    p = ExpressionParser(inputstr)
    print(f'Input is {inputstr}\n\n')

    t = p.parse()
    t.show()
    print()
    print(f'O resultado é: {t.evaluate()}')