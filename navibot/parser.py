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
EXPR_MOD = '%'
EXPR_POINT = '.'
EXPR_VIRG = ','
EXPR_PAR_START = '('
EXPR_PAR_END = ')'

EXPR_SEPARATOR = (
    PARSER_WHITESPACE,
    EXPR_ADD,
    EXPR_SUB,
    EXPR_MUL,
    EXPR_DIV,
    EXPR_POW,
    EXPR_MOD,
    EXPR_PAR_START,
    EXPR_PAR_END
)

EXPR_OPERATORS = (
    EXPR_ADD,
    EXPR_SUB,
    EXPR_MUL,
    EXPR_DIV,
    EXPR_POW,
    EXPR_MOD
)

EXPR_PRIORITY_MAP = {
    EXPR_ADD: 1,
    EXPR_SUB: 1,
    EXPR_MUL: 2,
    EXPR_DIV: 2,
    EXPR_MOD: 2,
    EXPR_POW: 3,
    # Maior prioridade possível, o caractere de EXPR_PAR_START é somente um apelido, não significa que será mapeado automaticamente
    EXPR_PAR_START: 4
}

EXPR_CONSTANTS = {
    'PI': math.pi
}

class CommandRequest:
    def __init__(self, cmd=''):
        self.cmd = cmd
        self.args = []
        self.flags = {}

    def add_argument(self, arg):
        if isinstance(arg, str):
            # Não permite começar com números Ex: -1
            if arg.startswith("--") and len(arg) > 2 and (char_in_range(arg[2], 'a', 'z') or char_in_range(arg[2], 'A', 'Z')):
                kv = arg.split("=")

                if len(kv) > 1:
                    self.flags[kv[0][2:]] = "=".join(kv[1:])
                    return
                else:
                    if len(kv[0][2:]) > 0:
                        self.flags[kv[0][2:]] = True
                        return
            elif arg.startswith("-") and len(arg) > 1 and (char_in_range(arg[1], 'a', 'z') or char_in_range(arg[1], 'A', 'Z')):
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
    def __init__(self, inputstr: str, resolve_subcommands: bool=True):
        super().__init__(inputstr)

        self.resolve_subcommands = resolve_subcommands

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
            elif char == PARSER_STRING_SUBCOMMAND_START and self.resolve_subcommands:
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
        self.priority = EXPR_PRIORITY_MAP.get(self.value, 0) if self.is_operator() else 0

    def is_operator(self):
        return self.value in EXPR_OPERATORS

    def is_value(self):
        return not self.is_operator()

    def get_priority(self):
        return self.priority

    def is_complete(self):
        return self.is_value() or self.left and self.right

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
            elif self.value == EXPR_MOD:
                return leftval % rightval
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
            # Adicione o primeiro valor
            self.head = No(val)
        else:
            if self.at:
                # Já temos um operador
                assert self.at.is_operator()
                
                if self.at.right:
                    # Estamos adicionando um valor a um operador já preenchido
                    # Ex: 2x4 -2
                    # Neste caso, -2 será uma SOMA com -2, portanto precisamos
                    # permitir neste contexto que o número adicionado suba na árvore como uma SOMA.
                    self.insert_operator(EXPR_ADD)
                    self.insert_value(val)
                else:
                    self.at.right = No(val)
            else:
                # Estamos adicionando nosso segundo valor, sem operador, adicionar um operador de soma
                # @FIX: Somente para valores negativos!!!
                assert val < 0

                self.insert_operator(EXPR_ADD)
                self.insert_value(val)

    def insert_operator(self, op):
        new = No(op)

        if self.at:
            assert self.at.right

            newp = new.get_priority()
            atp = self.at.get_priority()

            # Estamos 'concorrendo' com um outro operador
            if newp > atp:
                # Tem maior prioridade que o antigo, desça a árvore
                new.left = self.at.right
                self.at.right = new
                self.at = self.at.right
            elif newp == atp:
                # Não tem maior prioridade, é só uma sequência da operação atual, suba a árvore
                new.left = self.at
                if self.at is self.head:
                    self.head = self.at = new
                else:
                    self.head.right = new
                    self.at = new
            else:
                new.left = self.head
                self.head = new
                self.at = self.head
        else:
            # Não temos nenhum operador ainda, estamos adicionando o primeiro
            # assert self.head and self.head.is_value()

            if self.head:
                assert  self.head.is_value()

                new.left = self.head
                self.head = new
                self.at = self.head
            else:
                # Não temos nada, nenhum valor, nenhum operador.
                # Adicione um zero.
                self.insert_value(0)
                self.insert_operator(op)

    def insert_tree(self, t):
        # Se a árvore que estamos recebendo tem dados e operadores
        if not t.empty():
            # Se não temos uma head, use a head da outra árvore como a nossa própria.
            # o outro objeto será coletado pelo GC

            # Está dentro de um parenteses, logo tem a maior prioridade
            # de todas.
            t.head.priority = EXPR_PRIORITY_MAP[EXPR_PAR_START]

            if not self.head:
                self.head = t.head

                if self.head.is_operator():
                    self.at = self.head
            else:
                # Apenas aumentamos nossa árvore
                assert not self.at.right

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

    def last_operator_has_value(self):
        return not self.at or self.at.is_complete()
            
class ExpressionParser(Parser):
    def __init__(self, inputstr, constants=EXPR_CONSTANTS):
        super().__init__(inputstr)
        self.constants = constants

    def parse(self):
        t = ExpressionTree()
        is_negative = False

        c = self.current_char()

        try:
            while c and c != EXPR_PAR_END:
                if c in EXPR_OPERATORS:
                    if not is_negative:
                        if c == EXPR_SUB:
                            is_negative = True
                        else:
                            t.insert_operator(c)
                    else:
                        raise ParserError(f'Recebido operador {c}, porém esperado um valor.')
                elif char_in_range(c, '0', '9') or c in (EXPR_VIRG, EXPR_POINT):
                    n = self.eat_number()
                    t.insert_value(n if not is_negative else -1 * n)
                    is_negative = False
                    self.seek(-1)
                elif c == EXPR_PAR_START:
                    # Utiliza outro parser, recursivamente para trabalhar dentro dos parenteses
                    # implementação facilitada, porém consumo maior de memória
                    p = ExpressionParser(self.eat_expression_parenthesis())

                    if is_negative:
                        # É para usar um operador de SUB e não assumir que o valor é negativo.
                        t.insert_operator(EXPR_SUB)
                        is_negative = False

                    t.insert_tree(p.parse())
                    self.seek(-1)
                elif char_in_range(c, 'A', 'Z'):
                    identifier = self.eat_identifier()
                    value = self.constants.get(identifier, None)

                    if not value:
                        raise ParserError(f'Constante {identifier} não definida.')
                    else:
                        t.insert_value(value if not is_negative else -1 * value)
                        is_negative = False

                    self.seek(-1)          

                self.seek(1)
                c = self.current_char()
        except AssertionError:
            raise ParserError(f'Erro de sintaxe, por favor verifique os dados informados.')      

        if not t.last_operator_has_value():
            raise ParserError(f'Erro de sintaxe, o último operador não possui dois operandos.')

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

    def eat_identifier(self):
        buffer = io.StringIO()

        c = self.current_char()
        while c and not c in EXPR_SEPARATOR:
            buffer.write(c)
            self.seek(1)
            c = self.current_char()

        return buffer.getvalue()

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