
import pytest

from src.count_min_sketch import CountMinSketch


def test_initial_frequency_is_zero():
    cms = CountMinSketch()
    assert cms.estimate("usuario_1") == 0


def test_updates_are_registered():
    cms = CountMinSketch()

    cms.update("usuario_1")
    cms.update("usuario_1", 4)

    assert cms.estimate("usuario_1") >= 5
    assert cms.total_updates == 5


def test_estimate_never_underestimates():
    cms = CountMinSketch(epsilon=0.01, delta=0.01)

    exact = {
        "usuario_1": 10,
        "usuario_2": 25,
        "usuario_3": 40,
        "usuario_4": 5,
    }

    for key, frequency in exact.items():
        cms.update(key, frequency)

    for key, frequency in exact.items():
        assert cms.estimate(key) >= frequency


def test_invalid_parameters():
    with pytest.raises(ValueError):
        CountMinSketch(epsilon=0)

    with pytest.raises(ValueError):
        CountMinSketch(delta=1)

    cms = CountMinSketch()

    with pytest.raises(ValueError):
        cms.update("usuario_1", 0)


def test_memory_is_fixed_for_new_keys():
    cms = CountMinSketch()

    initial_memory = cms.memory_bytes()

    for user_id in range(10000):
        cms.update(user_id)

    assert cms.memory_bytes() == initial_memory
    assert cms.total_updates == 10000
