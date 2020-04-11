#!/usr/bin/python3
import time
import sys

from navibot.parser import ExpressionParser

def between(x, min, max):
    return x >= min and x <= max

def test_case(p, expr, expected, expected_max=None):
    p.feed(expr)
    sttime = time.perf_counter()
    t = p.parse()
    t_parseoverhead = time.perf_counter() - sttime

    evtime = time.perf_counter()
    result = t.evaluate()
    t_evaltime = time.perf_counter() - evtime

    passed = result >= expected and result <= expected_max if expected_max != None else result == expected

    sys.stdout.write(f"{'PASS' if passed else 'FAILED'}: {expr} = {expected}{f', {expected_max}' if expected_max != None else ''} \nGot {result}, took {t_parseoverhead:8.6f} seconds to parse and {t_evaltime:8.6f} seconds to evaluate.\n\n")

    if not passed:
        t.show()
        sys.stdout.write("\nDisplaying ExpressionTree above.\n")

if __name__ == "__main__":
    # Source: https://lukaszwrobel.pl/blog/math-parser-part-4-tests/
    # Modificado um pouco para atender a implementação atual.
    p = ExpressionParser('')
    test_case(p, '2 + 3', 5)
    test_case(p, '2 * 3', 6)
    test_case(p, '89', 89)
    test_case(p, '   12        -  8   ', 4)
    test_case(p, '142        -9   ', 133)
    test_case(p, '72+  15', 87)
    test_case(p, ' 12*  4', 48)
    test_case(p, ' 50/10', 5)
    test_case(p, '2.5', 2.5)
    test_case(p, '4*2.5 + 8.5+1.5 / 3.0', 19)
    test_case(p, '67+2', 69)
    test_case(p, ' 2-7', -5)
    test_case(p, '5*7 ', 35)
    test_case(p, '8/4', 2)
    test_case(p, '2 -4 +6 -1 -1- 0 +8', 10)
    test_case(p, '1 -1   + 2   - 2   +  4 - 4 +    6', 6)
    test_case(p, '2 -4 +6 -1 -1- 0 +8', 10)
    test_case(p, '1 -1   + 2   - 2   +  4 - 4 +    6', 6)
    test_case(p, ' 2*3 - 4*5 + 6/3 ', -12)
    test_case(p, '1 + -2 * 4 / 2', -3)
    test_case(p, '2*3*4/8 -   5/2*4 +  6 + 0/3   ', -1)
    test_case(p, '10/4', 2.5)
    test_case(p, '(2)', 2)
    test_case(p, '(5 + 2*3 - 1 + 7 * 8)', 66)
    test_case(p, '(67 + 2 * 3 - 67 + 2/1 - 7)', 1)
    test_case(p, '(2) + (17*2-30) * (5)+2 - (8/2)*4', 8)
    test_case(p, '(((((5)))))', 5)
    test_case(p, '(( ((2)) + 4))*((5))', 30)
    test_case(p, '(( ((2)) + 4))*((5)) - (2 -4 +6 -1 -1- 0 +8) + 2 -4 +6 -1 -1- 0 +8 / ((10/4)) +' * 10 + '1', 252.99, 253)