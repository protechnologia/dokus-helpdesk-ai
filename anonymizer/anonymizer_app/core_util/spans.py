def is_inside(
    span:  tuple[int, int],             # np. (6, 10)
    spans: list[tuple[int, int]],       # np. [(5, 11)]
) -> bool:
    """
    Description:
    Mówi, czy zakres leży w całości w którymś z podanych zakresów.

    Example args:
        span=(6, 10)
        spans=[(5, 11)]

    Example result:
        True
    """
    return any(start <= span[0] and span[1] <= end for start, end in spans)
