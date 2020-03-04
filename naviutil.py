# Funções úteis
import re
import logging

def parse_args(string):
    # @TODO: Evitar de transform "-X" em uma flag, pois queremos também inserir números negativos
    args = []
    flags = {}
    buffer = ""
    stringAtiva = False
    stringEscape = False

    for c in string:
        if not stringAtiva:
            if c == "\"":
                stringAtiva = True
            elif c != " ":
                buffer += c
            else:
                if len(buffer) > 0:
                    args.append(buffer)
                    buffer = ""
        else:
            if c == "\\":
                if not stringEscape:
                    stringEscape = True
                else:
                    stringEscape = False
                    buffer += c
            elif c == "\"":
                if stringEscape:
                    stringEscape = False
                    buffer += c
                else:
                    stringAtiva = False
                    args.append(buffer)
                    buffer = ""
            else:
                if stringEscape:
                    buffer += "\\"
                stringEscape = False
                buffer += c

    if len(buffer) > 0:
        args.append(buffer)

    i = 0
    while i < len(args):
        arg = args[i]

        if arg.startswith("--"):
            kv = arg.split("=")

            if len(kv) > 1:
                flags[kv[0][2:]] = "=".join(kv[1:])
                
                args.remove(arg)
                i = i - 1
            else:
                if len(kv[0][2:]) > 0:
                    flags[kv[0][2:]] = True
                    
                    args.remove(arg)
                    i = i - 1

        elif arg.startswith("-"):
            if len(arg) > 1:
                flags[arg[1:]] = True
                
                args.remove(arg)
                i = i - 1

        i = i + 1

    return args, flags

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