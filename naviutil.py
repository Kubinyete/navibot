import re
import math
import io
import logging

ESCAPE_SEQUENCE_MAP = {
    'a': '\a',
    'b': '\b',
    'f': '\f',
    'n': '\n',
    'r': '\r',
    't': '\t',
    'v': '\v',
    '\\': '\\',
    '\'': '\'',
    '"': '\"'
}

def create_command_dict():
    return {
        'command': '',
        'args': [],
        'flags': {}
    }

def translate_escape_sequence(code):
    try:
        return ESCAPE_SEQUENCE_MAP[code]
    except KeyError:
        return code

def parse_command_buffer(current, buffer):
    if not current['command']:
        current['command'] = buffer
    else:
        flags = current['flags']
        args = current['args']

        if buffer.startswith("--"):
            kv = buffer.split("=")

            if len(kv) > 1:
                flags[kv[0][2:]] = "=".join(kv[1:])
            else:
                if len(kv[0][2:]) > 0:
                    flags[kv[0][2:]] = True
        elif buffer.startswith("-"):
            if len(buffer) > 1:
                flags[buffer[1:]] = True
        else:
            args.append(buffer)

def parse_command_string(string):
    # @TODO: USAR io.StringIO NO LUGAR DE buffer
    commands = [create_command_dict()]
    current = commands[0]
    buffer = ''

    # @FIXME: Fazer algo mais elegante que isso rsrsrsrs.
    string += ' '

    eating_str = False
    eating_espace_sequence = False

    for c in string:
        if not eating_str:
            if c == '"':
                if buffer:
                    parse_command_buffer(current, buffer)
                eating_str = True
                buffer = ''
            elif c == '|':
                if not current['command']:
                    raise ValueError("Erro de sintaxe, esperado comando após PIPE.")

                if buffer:
                    parse_command_buffer(current, buffer)
                current = create_command_dict()
                commands.append(current)
                buffer = ''
            elif c != ' ':
                buffer += c
            else:
                if buffer:
                    parse_command_buffer(current, buffer)
                    buffer = ''
        else:
            if c == '\\':
                if not eating_espace_sequence:
                    eating_espace_sequence = True
                else:
                    eating_espace_sequence = False
                    buffer += c
            elif c == '"':
                if eating_espace_sequence:
                    eating_espace_sequence = False
                    buffer += c
                else:
                    eating_str = False

                    if not current['command']:
                        current['command'] = buffer
                    else:
                        current['args'].append(buffer)

                    buffer = ''
            else:
                if eating_espace_sequence:
                    buffer += translate_escape_sequence(c)
                    eating_espace_sequence = False
                else:
                    buffer += c

    return commands

def is_subclass(cls, clsparent):
    if cls.__name__ == clsparent.__name__:
        return True

    for base in cls.__bases__:
        if is_subclass(base, clsparent):
            return True

def is_instance(obj, clsparent):
    cls = type(obj)
    return is_subclass(cls, clsparent)

def timespan_seconds(timespan):
	segundos = 0
	value = timespan[0]
	unit = timespan[1]

	if unit == "s":
		segundos = value
	elif unit == "m":
		segundos = value * 60
	elif unit == "h":
		segundos = value * pow(60, 2)
	elif unit == "ms":
		segundos = value / 1000

	return segundos

def parse_timespan_seconds(string):
	segundos = 0

	try:
		for tm in re.findall("[0-9]+[hms]", string):
			every = re.search("^[0-9]+", tm)
			if every != None:
				every = int(every[0])
			unit = re.search("(h|m|s)$", tm)
			if unit != None:
				unit = unit[0]

			segundos += timespan_seconds((every, unit))
	except ValueError:
		pass

	return segundos

def bytes_string(bytes):
	sizes = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")

	i = 0
	while (bytes / 1024.0 >= 1):
		bytes = math.floor(bytes / 1024.0)
		i += 1

	return f"{bytes:.0f} {sizes[i]}"
	
def seconds_string(seconds):
	d = math.floor(seconds / 86400)
	seconds -= d * 86400

	h = math.floor(seconds / 3600)
	seconds -= h * 3600
	
	m = math.floor(seconds / 60)
	seconds -= m * 60

	output = []

	if d >= 1:
		output.append(f"{d} dia(s)")
	if h >= 1:
		output.append(f"{h} hora(s)")
	if m >= 1:
		output.append(f"{m} minuto(s)")
	if seconds > 0:
		output.append(f"{seconds} segundo(s)")
	
	return ", ".join(output)

def number_length(num):
    assert num >= 0
    return math.ceil(math.log10(num))

def char_in_range(char, min, max):
    val = ord(char)
    return val >= ord(min) and val <= ord(max)

def char_fullwidth(char):
    # \uff21 = Ａ
    # \u3000 = (fullwidth whitespace)
    return chr(ord(char) - 65 + ord('\uff21')) if char != ' ' else '\u3000'

def char_fullwidth_alphanumeric(char):
    return char_fullwidth(char) if char == ' ' or char_in_range(char, 'a', 'z') or char_in_range(char, 'A', 'Z') or char_in_range(char, '0', '9') else char

def string_fullwidth(string):
    return ''.join([char_fullwidth(char) for char in string])

def string_fullwidth_alphanumeric(string):
    return ''.join([char_fullwidth_alphanumeric(char) for char in string])
