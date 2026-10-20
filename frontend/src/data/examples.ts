/**
 * Description:
 * Zmyślone zgłoszenia do wczytania jednym kliknięciem w lewym panelu (przycisk „Przykłady"
 * w `pages/panels/TicketPanel.tsx`). Każde pokazuje inną drogę produktu, więc pokaz nie wymaga
 * wpisywania zgłoszenia z ręki.
 *
 * | przykład                   | co pokazuje                                                |
 * |----------------------------|------------------------------------------------------------|
 * | brak przesyłek, z wątkiem  | rozpoznanie, warianty, karta zgłoszenia, bramka zamknięcia  |
 * | komunikat przy podpisie    | sprawę z komunikatem, którego szuka się w kodzie aplikacji |
 * | nowe konto w sekretariacie | sprawę organizacyjną, w której kod nie ma nic do rzeczy     |
 *
 * O czym pamiętać przy zmianach:
 *
 * - Dane są zmyślone, nigdy kopiowane z korpusu (PII). Imiona i telefony w treści są celowo:
 *   pokazują anonimizację w konsoli przebiegu.
 * - Numery zgłoszeń z puli 901xx, jak zmyślone sprawy w testach `api`.
 */

import type { TicketRequest } from "../models/api/ticket";

/** Jeden przykład: nazwa w menu i zgłoszenie do wczytania. */
export interface Example {
    name:   string;         // np. "Brak przesyłek z e-Doręczeń (z wątkiem)"
    ticket: TicketRequest;
}

// Zmyślone zgłoszenia w kolejności z menu „Przykłady"; pierwsze wczytuje się na start strony.
export const EXAMPLES: Example[] = [
    {
        name:   "Brak przesyłek z e-Doręczeń (z wątkiem)",
        ticket: {
            ticket_id: "90101",
            date:      "2026-10-19",
            subject:   "Brak nowych przesyłek z e-Doręczeń",
            category:  "Błąd",
            body:      [
                "Dzień dobry,",
                "od wczoraj w skrzynce e-Doręczeń nie pojawiają się nowe przesyłki, a ePUAP działa normalnie.",
                "Po kliknięciu „Odśwież” widać komunikat „Nie udało się pobrać listy przesyłek”.",
                "Nic nie zmienialiśmy w ustawieniach. Proszę o pilną pomoc.",
                "Anna Wiśniewska, sekretariat, tel. 601 234 567",
            ].join("\n"),
            comments:  [
                {
                    role:       "konsultant",
                    created_at: "2026-10-19 09:12",
                    body:       "Dzień dobry, czy w zakładce „Kolejka pobierania” któraś pozycja ma status „Wstrzymana”? Czy serwer był ostatnio restartowany?",
                },
                {
                    role:       "klient",
                    created_at: "2026-10-19 09:40",
                    body:       "Jedna pozycja ma status „Wstrzymana”, od wczoraj rana. Serwera nie restartowaliśmy.",
                },
                {
                    role:       "konsultant",
                    created_at: "2026-10-19 10:05",
                    body:       "Oznaczyliśmy pozycję jako „Do pobrania ręcznego” i przesyłki zaczęły się pobierać. Przyczyną był załącznik większy niż limit pobierania.",
                },
            ],
        },
    },
    {
        name:   "Komunikat przy podpisie pisma",
        ticket: {
            ticket_id: "90102",
            date:      "2026-10-20",
            subject:   "Nie da się podpisać pisma",
            category:  "Błąd",
            body:      [
                "Przy próbie podpisania pisma w obiegu pojawia się komunikat „Nie udało się skomunikować z serwerem”.",
                "Dzieje się tak tylko przy piśmie z dużym załącznikiem, inne podpisują się normalnie.",
                "Jan Kowalczyk, kancelaria",
            ].join("\n"),
            comments:  [],
        },
    },
    {
        name:   "Nowe konto w sekretariacie",
        ticket: {
            ticket_id: "90103",
            date:      "2026-10-20",
            subject:   "Konto dla nowej pracownicy",
            category:  "Pytanie",
            body:      [
                "Dzień dobry,",
                "od poniedziałku w sekretariacie pracuje nowa osoba. Jak założyć jej konto i nadać uprawnienia do kancelarii?",
                "Maria Zielińska, kierownik sekretariatu",
            ].join("\n"),
            comments:  [],
        },
    },
];

// Puste zgłoszenie po kliknięciu „Wyczyść": numer zostaje do wpisania, data — dzisiejsza w `api`.
export const EMPTY_TICKET: TicketRequest = {
    ticket_id: "",
    date:      null,
    subject:   "",
    category:  "",
    body:      "",
    comments:  [],
};
