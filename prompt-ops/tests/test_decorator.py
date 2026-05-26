import pytest
from prompt_ops.decorator import optimize, OptimizeResult

def test_decorator_returns_optimize_result():
    @optimize(prompt_id="test")
    def my_func(prompt):
        return "hello " + prompt

    res = my_func("world")
    assert isinstance(res, OptimizeResult)
    assert res.content == "hello world"

def test_decorator_preserves_signature():
    @optimize(prompt_id="test")
    def math_func(a: int, b: int) -> int:
        """Adds two numbers."""
        return a + b

    assert math_func.__name__ == "math_func"
    assert math_func.__doc__ == "Adds two numbers."
    assert math_func.__annotations__["return"] == int

def test_decorator_does_not_raise_on_error():
    @optimize(prompt_id="test")
    def broken_func(prompt):
        raise ValueError("Inner failure")

    with pytest.raises(ValueError, match="Inner failure"):
        broken_func("fail")
