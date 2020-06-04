import re
import math
import PIL.Image

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
		output.append(f"{seconds:.0f} segundo(s)")
	
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

def normalize_image_max_width_height(img, width, height):
    # @NOTE
    # Diminuindo o tamanho da imagem de entrada, evitando imagens gigantes
    if img.width > width or img.height > height:
        fw = img.width
        fh = img.height

        while fw > width or fh > height:
            wfactor = width / fw 
            hfactor = height / fh

            if wfactor < 1:
                fw *= wfactor
                fh *= wfactor
            elif hfactor < 1:
                fw *= hfactor
                fh *= hfactor
        
        return img.resize((
            math.floor(fw),
            math.floor(fh)
        ))
    else:
        return img

def normalize_image_max_size(img, max_size):
    return normalize_image_max_width_height(img, max_size, max_size)

def normalize_image_fit_into(img, width, height):
    if img.width != width and img.height != height:
        fw = img.width
        fh = img.height
        wfactor = width / fw 
        hfactor = height / fh
        fw *= wfactor
        fh *= wfactor
        wfactor = width / fw 
        hfactor = height / fh
        if hfactor > 1:
            fw *= hfactor
            fh *= hfactor
            
        return img.resize((
            math.floor(fw),
            math.floor(fh)
        ))
    else:
        return img

