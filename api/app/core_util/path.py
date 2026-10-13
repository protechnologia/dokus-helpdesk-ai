def is_path_under(
    path:   str,  # np. "src/lib/Urzad/Numeracja/GeneratorNumeru.php"
    parent: str,  # np. "src/lib/Urzad"
) -> bool:
    """
    Description:
    Mówi, czy ścieżka jest podaną ścieżką albo leży pod nią, na dowolnej głębokości. Porównuje
    napisy z ukośnikiem jako separatorem i dysku nie dotyka, więc obie ścieżki muszą być
    w jednej postaci: bez `..` i bez ukośnika na końcu.

    Granicą jest cały człon ścieżki: `src/lib2/a.php` nie leży pod `src/lib`.

    Example args:
        path="src/lib/Urzad/Numeracja/GeneratorNumeru.php"
        parent="src/lib/Urzad"

    Example result:
        True
    """
    return path == parent or path.startswith(f"{parent}/")
