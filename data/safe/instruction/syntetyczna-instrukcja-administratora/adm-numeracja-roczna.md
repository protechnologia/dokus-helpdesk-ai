Numeracja spraw i rejestrów kancelaryjnych jest roczna. Dla każdego rejestru i każdego roku istnieje osobna sekwencja; Dokus nie tworzy jej sam.

Sekwencje na kolejny rok tworzy się w Ustawienia → Rejestry → Numeracja przyciskiem „Utwórz sekwencje na rok”. Można to zrobić z wyprzedzeniem — sekwencja na rok przyszły nie wpływa na bieżącą numerację.

Jeśli sekwencji brakuje, pierwsza rejestracja w nowym roku kończy się błędem. Użytkownik dostaje komunikat o braku komunikacji z serwerem, a w dzienniku serwera jest wpis `SQLSTATE[23505]` z nazwą rejestru.

Po utworzeniu sekwencji rejestracja działa od razu. Dokumentów, których nie udało się zarejestrować, nie trzeba wprowadzać ponownie: zostały zapisane jako robocze i wystarczy je zarejestrować.

Numeru nadanego w starym roku nie da się przenieść do nowej sekwencji.
