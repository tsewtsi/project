import pytest

from calc import add


def test_add_returns_sum():
    assert add(2, 3) == 5


def test_add_negative_numbers():
    assert add(-1, -4) == -5


def test_add_zero():
    assert add(0, 0) == 0


@pytest.mark.parametrize(
    "a, b",
    [
        (1.0, 2),
        (1, 2.0),
        ("1", 2),
        (1, "2"),
        (None, 1),
        (True, 1),
    ],
)
def test_add_rejects_non_int(a, b):
    with pytest.raises(TypeError):
        add(a, b)
