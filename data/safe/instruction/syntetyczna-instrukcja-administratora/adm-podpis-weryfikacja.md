Przy weryfikacji podpisu Dokus sprawdza, czy certyfikat podpisującego nie został unieważniony. Pyta o to usługę OCSP wystawcy, a gdy ta nie odpowiada — pobiera listę CRL.

Oba adresy są zapisane w samym certyfikacie i prowadzą poza sieć urzędu. Sprawdzenie wykonuje serwer aplikacji, a przy podpisie składanym na stanowisku także komputer użytkownika. Jeśli zapora albo serwer pośredniczący blokuje te adresy, weryfikacja kończy się komunikatem „Nie można ustalić statusu certyfikatu (OCSP/CRL)” i kodem `PDP-203`.

Komunikat nie oznacza, że podpis jest nieważny. Oznacza, że Dokus nie zdołał tego sprawdzić.

Co ustawić:

- w Ustawienia → Integracje → Podpis elektroniczny, w polu „Serwer pośredniczący”, adres i port serwera pośredniczącego urzędu,
- na zaporze — ruch wychodzący z serwera aplikacji i ze stanowisk do adresów wystawców certyfikatów.

Opcja „Akceptuj podpis bez sprawdzenia statusu” wyłącza weryfikację dla wszystkich użytkowników. Obniża poziom zabezpieczeń i jest przeznaczona wyłącznie na czas awarii łącza.
