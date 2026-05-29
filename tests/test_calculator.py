from src.calculator import add

def test_add_positive():
    assert add(1,2)==3

def test_add_negative():
    assert add(-1,-1)==-2

def test_add_zero():
    assert add(0, 6)==7


