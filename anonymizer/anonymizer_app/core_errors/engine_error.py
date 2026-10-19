class EngineError(Exception):
    """
    Description:
    Wspólna klasa każdej awarii silnika anonimizacji. Trasa łapie ją, gdy wystarczy jej wiedzieć,
    że tekstu nie dało się zanonimizować — nigdy typów bibliotek, na których stoi silnik.
    """
