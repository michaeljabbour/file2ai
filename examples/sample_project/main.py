def greet(name: str) -> str:
    """Return a greeting message."""
    return f"Hello, {name}!"

def calculate_sum(numbers: list[int]) -> int:
    """Calculate the sum of a list of numbers."""
    return sum(numbers)

if __name__ == "__main__":
    print(greet("World"))
    print(calculate_sum([1, 2, 3, 4, 5]))
