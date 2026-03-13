from __future__ import annotations
from typing import List, Tuple


class RegexTokenizer:
    """Converts infix regex to postfix using explicit concatenation operator."""

    OPERATORS_PRECEDENCE = {"*": -1, "+": -2, "?": -3, "_": -4, "|": -5, "(": -100, "[": -100}

    @staticmethod
    def tokenize(regex: str) -> List[Tuple[str, str]]:
        """Tokenizes regex into (value, type) tuples."""
        tokens = []
        i = 0
        while i < len(regex):
            if regex[i] == "-":  # Handle ranges
                tokens[-1] = (f"[{regex[i-1]}-{regex[i+1]}]", "var")
                i += 2
            elif regex[i] in "()[]*+?_|":
                tokens.append((regex[i], "op"))
                i += 1
            else:
                tokens.append((regex[i], "var"))
                i += 1
        return tokens

    @staticmethod
    def expand_ranges(tokens: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
        """Adds '|' between variables inside brackets for ranges."""
        new_tokens = []
        inside_bracket = False
        last_was_var = False
        for val, typ in tokens:
            if val == "[":
                inside_bracket = True
            elif val == "]":
                inside_bracket = False
            elif inside_bracket and last_was_var:
                new_tokens.append(("|", "op"))
            new_tokens.append((val, typ))
            last_was_var = typ == "var"
        return new_tokens

    @staticmethod
    def insert_concatenation(tokens: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
        """Inserts explicit concatenation operator '_' where needed."""
        result = []
        for i in range(len(tokens) - 1):
            result.append(tokens[i])
            curr_val, curr_type = tokens[i]
            next_val, next_type = tokens[i + 1]
            if ((curr_type == "var" or curr_val in ")]*+?") and
                    (next_type == "var" or next_val in "([")):
                result.append(("_", "op"))
        result.append(tokens[-1])
        return result

    @classmethod
    def to_postfix(cls, regex: str) -> List[str]:
        tokens = cls.insert_concatenation(cls.expand_ranges(cls.tokenize(regex)))
        postfix = []
        op_stack = []

        def pop_op():
            postfix.append(op_stack.pop())

        for val, typ in tokens:
            if val in "([":
                op_stack.append(val)
            elif val in ")]":
                while op_stack[-1] not in "([": pop_op()
                op_stack.pop()
            elif typ == "op":
                while op_stack and cls.OPERATORS_PRECEDENCE[val] <= cls.OPERATORS_PRECEDENCE[op_stack[-1]]:
                    pop_op()
                op_stack.append(val)
            else:
                postfix.append(val)
        while op_stack: pop_op()
        return postfix
