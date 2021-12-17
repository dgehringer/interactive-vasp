import typing as T

regex_float = r"[+-]?\d*\.\d+[eE]?[+-]?\d*"
regex_integer = r"[+-]?\d+"
regex_whitespace_maybe = r"\s*"
regex_whitespace_sure = r"\s+"


def chain(*parts: str) -> str:
    return r"".join(parts)


def pad(regex: str, lpad: str = r"", rpad: str = r"") -> str:
    return chain(lpad, regex, rpad)


def lpad(regex: str, p: str) -> str:
    return pad(regex, lpad=p)


def rpad(regex: str, p: str) -> str:
    return pad(regex, rpad=p)


def lrpad(regex: str, p: str) -> str:
    return pad(regex, lpad=p, rpad=p)


def group(regex: str, name: T.Optional[str] = None) -> str:
    return rf"({regex})" if name is None else rf"(?P<{name}>{regex})"


def optional(*regexes: str) -> str:
    return r"|".join(regexes)