<!-- Opis projektu aplikacji syntetycznej — oddaje go narzędzie `describe_code` (CLAUDE.md ->
     „Kod aplikacji"). Celowo dwa zdania: pilnuje okablowania, nie skuteczności. Ścieżki
     w odwróconych apostrofach sprawdza skrypt paczki
     (`python scripts/build_code_package.py check-description data/safe/code`).
     Komentarze redakcyjne jak ten są wycinane przed wysłaniem. -->
Zmyślona aplikacja urzędu na Symfony 1: backend w PHP (akcje modułów w `src/apps/frontend/modules/`, kod domenowy w `src/lib/Urzad/`), interfejs w JS (`src/web/js/`, katalog na moduł, część wspólna w `src/web/js/_global/`). Schematy tabel leżą w `src/config/doctrine/`; plików konfiguracji z hasłami w paczce nie ma.
