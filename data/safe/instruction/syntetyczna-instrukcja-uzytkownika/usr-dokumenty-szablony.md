Nowe pismo można utworzyć z szablonu: „Nowy dokument” → „Z szablonu”. Szablony dostarczane z Dokusem są wspólne dla urzędu; własne szablony komórki dodaje jej kierownik.

Szablon zawiera pola automatyczne, które Dokus wypełnia przy tworzeniu pisma:

| pole | co wstawia |
|---|---|
| `{{ZNAK_SPRAWY}}` | znak sprawy, do której należy pismo |
| `{{DATA_PISMA}}` | data utworzenia dokumentu |
| `{{ADRESAT_NAZWA}}` | nazwa adresata z kartoteki kontrahentów |
| `{{ADRESAT_ADRES}}` | adres korespondencyjny adresata |
| `{{PROWADZACY}}` | imię i nazwisko prowadzącego sprawę |

Pole, dla którego brakuje danych, zostaje w treści w niezmienionej postaci, w nawiasach klamrowych. Przed akceptacją warto przeszukać pismo pod kątem znaków `{{`.

Pola wypełniają się raz, przy tworzeniu. Późniejsza zmiana adresata w sprawie nie poprawia pisma — trzeba je utworzyć ponownie albo poprawić ręcznie.
