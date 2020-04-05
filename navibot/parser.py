import sys
import logging
import io
import math

from navibot.errors import ParserError
from navibot.util import char_in_range

PARSER_STRING_LITERAL = '"'
PARSER_STRING_ESCAPE = '\\'
PARSER_STRING_SUBCOMMAND_START = '{'
PARSER_STRING_SUBCOMMAND_END = '}'
PARSER_PIPE = '|'
PARSER_WHITESPACE = ' '

PARSER_ARG_SEPARATOR = (
    PARSER_STRING_LITERAL,
    PARSER_PIPE,
    PARSER_WHITESPACE
)

ESCAPE_MAP = {
    'a': '\a',
    'b': '\b',
    'f': '\f',
    'n': '\n',
    'r': '\r',
    't': '\t',
    'v': '\v',
    PARSER_STRING_ESCAPE: PARSER_STRING_ESCAPE,
    PARSER_STRING_LITERAL: PARSER_STRING_LITERAL,
    PARSER_STRING_SUBCOMMAND_START: PARSER_STRING_SUBCOMMAND_START,
    PARSER_STRING_SUBCOMMAND_END: PARSER_STRING_SUBCOMMAND_END
}

EXPR_ADD = '+'
EXPR_SUB = '-'
EXPR_MUL = '*'
EXPR_DIV = '/'
EXPR_POW = '^'
EXPR_POINT = '.'
EXPR_VIRG = ','
EXPR_PAR_START = '('
EXPR_PAR_END = ')'

EXPR_SEPARATOR = (
    EXPR_ADD,
    EXPR_SUB,
    EXPR_MUL,
    EXPR_DIV,
    EXPR_POW,
    EXPR_PAR_START,
    EXPR_PAR_END
)

EXPR_OPERATORS = (
    EXPR_ADD,
    EXPR_SUB,
    EXPR_MUL,
    EXPR_DIV,
    EXPR_POW
)

EXPR_PRIORITY_MAP = {
    EXPR_ADD: 1,
    EXPR_SUB: 1,
    EXPR_MUL: 2,
    EXPR_DIV: 2,
    EXPR_POW: 3,
}

class CommandRequest:
    def __init__(self, cmd=''):
        self.cmd = cmd
        self.args = []
        self.flags = {}

    def add_argument(self, arg):
        if isinstance(arg, str):
            if arg.startswith("--"):
                kv = arg.split("=")

                if len(kv) > 1:
                    self.flags[kv[0][2:]] = "=".join(kv[1:])
                    return
                else:
                    if len(kv[0][2:]) > 0:
                        self.flags[kv[0][2:]] = True
                        return
            elif arg.startswith("-"):
                if len(arg) > 1:
                    self.flags[arg[1:]] = True
                    return

        self.args.append(arg)

class Parser:
    def __init__(self, inputstr):
        self.feed(inputstr)

    def feed(self, inputstr):
        self.inputstr = inputstr
        self.index = 0

    def at_start(self):
        return self.index == 0

    def at_end(self):
        return self.index == len(self.inputstr) - 1

    def seek(self, delta):
        self.index += delta

    def current_char(self):
        if self.index < 0 or self.index >= len(self.inputstr):
            return None

        return self.inputstr[self.index]

    def eat_current_char(self):
        c = self.current_char()
        self.index += 1
        return c

    def next_char(self):
        return self.inputstr[self.index + 1] if not self.at_end() else None
        
    def prev_char(self):
        return self.inputstr[self.index - 1] if not self.at_start() else None

    def parse(self):
        raise NotImplementedError()

class CommandParser(Parser):
    def parse(self):
        try:
            pipeline = [CommandRequest()] 
            current = pipeline[0]

            prev = None
            char = self.eat_current_char()
            while char:
                if char != PARSER_WHITESPACE:
                    if char == PARSER_STRING_ESCAPE:
                        nextc = self.current_char()

                        if nextc in (PARSER_STRING_LITERAL, PARSER_STRING_SUBCOMMAND_START, PARSER_STRING_SUBCOMMAND_END, PARSER_STRING_ESCAPE, PARSER_PIPE):
                            if not current.cmd:
                                current.cmd = self.eat_string()
                            else:
                                current.add_argument(self.eat_string())
                        else:
                            raise ParserError(f"Código de escape {PARSER_STRING_ESCAPE}{nextc} fora de uma string literal não suportado.")
                    elif char == PARSER_STRING_SUBCOMMAND_START or char == PARSER_STRING_SUBCOMMAND_END:
                        if prev != PARSER_STRING_ESCAPE:
                            raise ParserError("Subcomando fora de uma string literal não é suportado.")
                    elif char == PARSER_PIPE:
                        if not current.cmd:
                            raise ParserError("Operador PIPE utilizado sobre um comando sem identificador.")
                        current = CommandRequest()
                        pipeline.append(current)
                    elif char == PARSER_STRING_LITERAL:
                        if not current.cmd:
                            raise ParserError("É preciso informar o nome do comando antes de listar seus argumentos.")
                        else:
                            current.add_argument(self.eat_string_literal())
                    else:
                        self.seek(-1)

                        if not current.cmd:
                            current.cmd = self.eat_string()
                        else:
                            current.add_argument(self.eat_string())

                prev = char
                char = self.eat_current_char()

        except ParserError as e:
            logging.error(f"\n{self.inputstr}: {e}\n{(self.index - 1 if self.index else self.index) * ' '}^")
            raise e 

        return pipeline

    def eat_string_literal(self):
        chunks = []
        buffer = io.StringIO()
        char = self.eat_current_char()

        # echo "Teste {time "batata 1"}"
        while char and char != PARSER_STRING_LITERAL:
            if char == PARSER_STRING_ESCAPE:
                nextc = self.current_char()

                try:
                    buffer.write(ESCAPE_MAP[nextc])
                except KeyError:
                    raise ParserError(f"Caractere de escape `{PARSER_STRING_ESCAPE}{nextc}` inválido ou não mapeado.")
                finally:
                    self.seek(1)
            elif char == PARSER_STRING_SUBCOMMAND_START:
                # Eu não devo estar processando isso, passar para a função responsável
                command = self.eat_subcommand()
                chunks.append(buffer.getvalue())
                buffer.seek(0)
                buffer.truncate(0)
                chunks.append(command)
            else:
                buffer.write(char)

            char = self.eat_current_char()

        if buffer.tell():
            chunks.append(buffer.getvalue())

        buffer.close()

        return chunks

    def eat_string(self):
        arg = None
        buffer = io.StringIO()
        char = self.eat_current_char()

        while char and char not in PARSER_ARG_SEPARATOR:
            if char == PARSER_STRING_ESCAPE:
                nextc = self.current_char()

                if nextc in (PARSER_STRING_LITERAL, PARSER_STRING_SUBCOMMAND_START, PARSER_STRING_SUBCOMMAND_END, PARSER_STRING_ESCAPE, PARSER_PIPE):
                    pass
                else:
                    raise ParserError(f"Código de escape {PARSER_STRING_ESCAPE}{nextc} fora de uma string literal não suportado.")
            else:
                buffer.write(char)

            char = self.eat_current_char()

        self.seek(-1)

        arg = buffer.getvalue()

        buffer.close()

        return arg
        
    def eat_subcommand(self):
        buffer= io.StringIO()
        char = self.current_char()
        subcommand_input = None
        subcommad_level = 1

        # 1. Caso - echo "Teste {time "batata 1"}"
        # 2. Caso - echo "Teste {time"
        # 3. Caso - echo "Teste {time "batata 1}"
        # 3. Caso - echo "Teste {echo "batata {echo "teste"} 1"}"
        # 3. Caso - echo "Teste {echo "batata {echo "teste} 1"}"
        while char and subcommad_level:
            # Não ligar para o conteudo, apenas se ainda estamos montando corretamente a string de subcommand, sendo possível posteriormente
            # alimentar subcommand para o Parser

            if char == PARSER_STRING_SUBCOMMAND_START and self.prev_char() != PARSER_STRING_ESCAPE:
                 subcommad_level += 1
            elif char == PARSER_STRING_SUBCOMMAND_END and self.prev_char() != PARSER_STRING_ESCAPE:
                subcommad_level -= 1

            if subcommad_level:
                buffer.write(char)

            self.seek(1)
            char = self.current_char()

        if not char:
            if subcommad_level > 1:
                raise ParserError(f"O subcomando informado não foi fechado corretamente, por favor verifique sua sintaxe e tente novamente.")

        subcommand_input = buffer.getvalue()

        buffer.close()

        return CommandParser(subcommand_input).parse()

class No:
    def __init__(self, value, left=None, right=None):
        self.value = value
        self.left = left
        self.right = right

    def is_operator(self):
        return self.value in EXPR_OPERATORS

    def is_value(self):
        return not self.is_operator()

    def get_priority(self):
        assert self.is_operator()
        return EXPR_PRIORITY_MAP.get(self.value, 0)

    def evaluate(self):
        if self.is_value():
            return self.value
        else:
            # @FIX:
            # self.right pode ser None, tratar isso...
            leftval = self.left.evaluate()
            rightval = self.right.evaluate()

            if self.value == EXPR_ADD:
                return leftval + rightval
            elif self.value == EXPR_SUB:
                return leftval - rightval
            elif self.value == EXPR_MUL:
                return leftval * rightval
            elif self.value == EXPR_DIV:
                return leftval / rightval
            elif self.value == EXPR_POW:
                return math.pow(leftval, rightval)
            else:
                raise ValueError(f'Operador {self.value} desconhecido.')

class ExpressionTree:
    def __init__(self):
        self.head = None
        self.at = None

    def empty(self):
        return not self.head

    def insert_value(self, val):
        if not self.head:
            self.head = No(val)
        else:
            self.at.right = No(val)

    def insert_operator(self, op):
        new = No(op)

        if self.at:
            if new.get_priority() > self.at.get_priority():
                new.left = self.at.right
                self.at.right = new
                self.at = self.at.right
            else:
                if self.at is self.head:
                    new.left = self.at
                    self.head = new
                    self.at = self.head
                else:
                    new.left = self.head
                    self.head = new
                    self.at = self.head

        elif self.head.is_value():
            new.left = self.head
            self.head = new
            
            if not self.at:
                self.at = self.head

    def insert_tree(self, t):
        if not t.empty():
            if not self.head:
                self.head = t.head
                self.at = self.head
            else:
                self.at.right = t.head

    def evaluate(self):
        return self.head.evaluate() if not self.empty() else .0

    def output(self, current, level=0):
        if current:
            print(f'{level}:({current.value})', end=' ')

            self.output(current.left, level=level + 1)
            self.output(current.right, level=level + 1)

    def show(self):
        self.output(self.head)
            
class ExpressionParser(Parser):
    def parse(self):
        # -1.34 + 2 / 4
        t = ExpressionTree()

        c = self.current_char()
        while c and c != EXPR_PAR_END:
            if c in EXPR_OPERATORS:
                if t.empty():
                    t.insert_value(0)
                
                t.insert_operator(c)
                #print(f'Got operator: {c}')
            elif char_in_range(c, '0', '9') or c in (EXPR_VIRG, EXPR_POINT):
                n = self.eat_number()
                t.insert_value(n)
                #print(f'Got number: {n}')
                self.seek(-1)
            elif c == EXPR_PAR_START:
                p = ExpressionParser(self.eat_expression_parenthesis())
                t.insert_tree(p.parse())
                self.seek(-1)
            else:
                pass

            self.seek(1)
            c = self.current_char()

        return t

    def eat_number(self):
        buffer = io.StringIO()
        after_point = False

        c = self.current_char()
        while c:
            if c == EXPR_POINT or c == EXPR_VIRG:
                buffer.write(c if not c == EXPR_VIRG else EXPR_POINT)
                if not after_point:
                    after_point = True
                else:
                    raise ParserError('Encontrado token de precisão duas vezes, abortando.')
            elif char_in_range(c, '0', '9'):
                buffer.write(c)
            else:
                break

            self.seek(1)
            c = self.current_char()

        try:
            return float(buffer.getvalue())
        except ValueError:
            # Não deve acontecer nunca
            return ParserError('Não foi possível converter o valor obtido da expressão para float.')

    def eat_expression_parenthesis(self):
        buffer = io.StringIO()
        level = 1

        self.seek(1)

        c = self.current_char()
        while c and level > 0:
            if c == EXPR_PAR_START:
                level += 1
            elif c == EXPR_PAR_END:
                level -= 1

            if level > 0:
                buffer.write(c)
            
            self.seek(1)
            c = self.current_char()

        if level > 0:
            raise ParserError('A expressão dentro do parenteses não foi terminada corretamente.')
        else:
            return buffer.getvalue()