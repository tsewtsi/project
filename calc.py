def add(a, b):
    if isinstance(a, bool) or isinstance(b, bool):
        raise TypeError("Both arguments must be int")
    if not isinstance(a, int) or not isinstance(b, int):
        raise TypeError("Both arguments must be int")
    return a + b
