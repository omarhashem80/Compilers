class RegexValidator:
    """Validates a regex string for basic syntax correctness."""
    @staticmethod
    def validate(regex: str) -> bool:
        stack = []
        for char in regex:
            if char in "([": stack.append(char)
            elif char == ")":
                if not stack or stack.pop() != "(":
                    raise ValueError("Unbalanced parentheses")
            elif char == "]":
                if not stack or stack.pop() != "[":
                    raise ValueError("Unbalanced brackets")
        if stack:
            raise ValueError("Unbalanced parentheses or brackets")
        return True
