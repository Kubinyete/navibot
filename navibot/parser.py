import sys
import logging
import io

from navibot.errors import ParserError

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

        return Parser(subcommand_input).parse()

if __name__ == "__main__":
    DEBUG_TAB = '\t'

    def debug_print_pipeline(pipeline, lvl=0):
        for cmdreq in pipeline:
            print(f"{DEBUG_TAB * lvl}Comando {cmdreq.cmd}:")
            print(f"{DEBUG_TAB * lvl}Args:")

            for argument in cmdreq.args:
                if isinstance(argument, str):
                    print(f"{DEBUG_TAB * (lvl + 1)}{argument}")
                else:
                    for chunk in argument:
                        if isinstance(chunk, list):
                            debug_print_pipeline(chunk, lvl=lvl + 2)
                        else:
                            print(f"{DEBUG_TAB * (lvl + 1)}{chunk}")

        print(f"{DEBUG_TAB * lvl}---")

    p = Parser(sys.argv[1])
    pipeline = p.parse()

    # DEBUG
    debug_print_pipeline(pipeline)