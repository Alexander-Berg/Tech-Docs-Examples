import re
from collections import deque

# Defines the order of how operations should be evaluated.
# Operation with less value has less priority
precedence = {
    '=': 3,
    '!=': 3,
    'NOT': 2,
    'AND': 1,
    'OR': 0
}


def is_terminal(token):
    return token in ['status', 'isAutotest', 'EMPTY', 'true', 'false'] or re.match(r'"*"', token)


def apply_eq(key, value):
    if value == 'EMPTY':
        return '{"type":"EQ","key":"%s","value":null}' % key
    else:
        return '{"type":"EQ","key":"%s","value":%s}' % (key, value)


def apply_not_eq(key, value):
    if value == 'EMPTY':
        return '{"type":"NEQ","key":"%s","value":null}' % key
    else:
        return '{"type":"NEQ","key":"%s","value":%s}' % (key, value)


def apply_not(expression):
    return '{"type":"NOT","left":%s}' % expression


def apply_and(left_expression, right_expression):
    return '{"type":"AND","left":%s,"right":%s}' % (left_expression, right_expression)


def apply_or(left_expression, right_expression):
    return '{"type":"OR","left":%s,"right":%s}' % (left_expression, right_expression)


def get_tree_representation(project, postfix_form):
    """ Returns representation of postfix form as tree like backend TestPalm filter """
    operator = postfix_form.pop()
    if operator == '=':
        value = postfix_form.pop()
        key = project.get_attribute_key(postfix_form.pop().replace('"', ''))
        return apply_eq(key, value)
    elif operator == '!=':
        value = postfix_form.pop()
        key = project.get_attribute_key(postfix_form.pop().replace('"', ''))
        return apply_not_eq(key, value)
    elif operator == 'NOT':
        operand = get_tree_representation(project, postfix_form)
        return apply_not(operand)
    elif operator == 'AND':
        right = get_tree_representation(project, postfix_form)
        left = get_tree_representation(project, postfix_form)
        return apply_and(left, right)
    elif operator == 'OR':
        right = get_tree_representation(project, postfix_form)
        left = get_tree_representation(project, postfix_form)
        return apply_or(left, right)


def convert_to_postfix(infix_form):
    """
    Implementing Dijkstra Shunting-yard algorithm
    https://en.wikipedia.org/wiki/Shunting-yard_algorithm
    :param infix_form: tokens in infix form (['a', '=', 'b'])
    :return: tokens in postfix form (['a', 'b', '='])
    """
    postfix_form = deque()
    stack = deque()

    for token in infix_form:
        if is_terminal(token):
            postfix_form.append(token)
        elif token in precedence.keys():
            while (len(stack) > 0) and (stack[-1] in precedence.keys()) and (
                    precedence[stack[-1]] >= precedence[token]):
                postfix_form.append(stack.pop())
            stack.append(token)
        elif token == '(':
            stack.append(token)
        elif token == ')':
            try:
                while stack[-1] != '(':
                    postfix_form.append(stack.pop())
            except IndexError:
                raise Exception("Wrong parentheses construction: not found (")
            stack.pop()  # removing '('
        else:
            raise Exception("Unexpected token: " + token)

    while len(stack) > 0:
        if stack[-1] == '(':
            raise Exception("Wrong parentheses construction: not found )")
        else:
            postfix_form.append(stack.pop())

    return postfix_form


def convert_filter(project, front_filter):
    """
    Converts TestPalm frontend filter no TestPalmBackend filter
    :param project: TestPalm project in which cases filter could be applied
    :param front_filter: frontend filter for cases
    :return: string of backend cases filter equivalent to given frontend one
    """
    # Adds spaces around operands (, ), !=, =
    front_filter = re.sub(r'!=|\(|\)|=', lambda m: ' {} '.format(m.group()), front_filter)

    # Splits string by spaces ignoring spaces in quotes
    # '"a c" d' -> ['"a c"', 'd']
    tokens = re.findall(r'(?:\".*?\"|\S)+', front_filter)

    # To fix issue when adding spaces in attributes or values
    for i in range(len(tokens)):
        tokens[i] = tokens[i].replace(" ( ", "(").replace(" ) ", ")")

    postfix_form = convert_to_postfix(tokens)
    return get_tree_representation(project, postfix_form)
