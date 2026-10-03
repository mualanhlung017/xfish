"""Resolve this regression's Chinese notation using engine-legal UCI moves."""
START_FEN = "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1"
DIGITS = {**dict(zip("一二三四五六七八九", "123456789")),
          **dict(zip("１２３４５６７８９", "123456789")),
          **{d: d for d in "123456789"}}
PIECES = {"车": "R", "馬": "H", "马": "H", "炮": "C", "相": "E", "象": "E",
          "仕": "A", "士": "A", "帅": "K", "将": "K", "兵": "P", "卒": "P"}
ACTIONS = {"平": "=", "进": "+", "進": "+", "退": "-"}
SELECTORS = {"前": "+", "中": "0", "后": "-", "後": "-"}


def normalize_chinese_token(token):
    if len(token) != 4:
        raise ValueError(token)
    if token[0] in PIECES:
        pc, selector = PIECES[token[0]], token[1]
    else:
        pc, selector = PIECES[token[1]], token[0]
    return pc + DIGITS.get(selector, SELECTORS.get(selector, '?')) + ACTIONS[token[2]] + DIGITS[token[3]]


def move_as_wxf(fen, move):
    board = {}
    for i, encoded in enumerate(fen.split()[0].split('/')):
        file_index = 0
        for symbol in encoded:
            if symbol.isdigit():
                file_index += int(symbol)
            else:
                board[chr(ord('a') + file_index) + str(9-i)] = symbol
                file_index += 1
    source, target = move[:2], move[2:]
    pc = board[source]
    white = fen.split()[1] == 'w'
    fr, tr = int(source[1]), int(target[1])
    def file_number(square):
        file_index = ord(square[0]) - ord('a')
        return 9 - file_index if white else file_index + 1
    same_file = sorted((int(s[1]) for s, p in board.items()
                        if p == pc and s[0] == source[0]), reverse=white)
    if len(same_file) == 2:
        selector = '+' if fr == same_file[0] else '-'
    elif len(same_file) == 3:
        selector = ('+', '0', '-')[same_file.index(fr)]
    else:
        selector = str(file_number(source))
    letter = {'N': 'H', 'B': 'E'}.get(pc.upper(), pc.upper())
    if fr == tr:
        action, destination = '=', file_number(target)
    else:
        action = '+' if (tr > fr) == white else '-'
        destination = file_number(target) if pc.upper() in 'NBA' else abs(tr-fr)
    return letter + selector + action + str(destination)
