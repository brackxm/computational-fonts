"""Bounded storage geometry; no expression evaluation."""
VALUES = ('E', 'A', 'S', 'K', 'I') + tuple('abcdefghijklmnopqrstuvwxyz')


def paths(depth):
    def walk(p):
        yield p
        if len(p) < depth:
            yield from walk(p+'0')
            yield from walk(p+'1')
    return tuple(walk(''))



def validate(depth, rounds):
    if type(depth) is not int or not 3 <= depth <= 6:
        raise ValueError('depth must be an integer from 3 to 6')
    if type(rounds) is not int or not 0 <= rounds <= 32:
        raise ValueError('rounds must be an integer from 0 to 32')
    if depth == 6 and rounds > 16:
        raise ValueError('depth 6 is verified only up to 16 rounds; larger configurations can leave the machine unfinished')
