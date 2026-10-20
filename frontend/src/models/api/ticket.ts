/**
 * Description:
 * Zgłoszenie w kształcie żądania `api` (`TicketRequest` z `api/app/entry_routers/models.py`):
 * wejście `/search`, `/suggest`, `/parse-ticket` i `/gate/close`. Ten sam kształt trzyma lewy
 * panel, więc do `api` idzie bez przeróbki.
 *
 * Kto czyta: `pages/panels/TicketPanel.tsx` (lewy panel) i `data/examples.ts` (zmyślone
 * zgłoszenia do wczytania); `pages/App.tsx` wysyła zgłoszenie z lewego panelu do grafów.
 */

/** Komentarz wątku zgłoszenia. */
export interface TicketComment {
    body:       string;  // np. "Proszę sprawdzić uprawnienia certyfikatu."
    role:       string;  // np. "konsultant", "klient"
    created_at: string;  // np. "2026-06-23 12:01"
}

/** Zgłoszenie z wątkiem; wymagane przez `api` są tylko `ticket_id` i `body`. */
export interface TicketRequest {
    ticket_id: string;           // np. "90101"
    body:      string;           // np. "Od wczoraj nie przychodzą przesyłki…"
    date:      string | null;    // np. "2026-10-19"; brak znaczy „dziś"
    subject:   string;           // np. "Brak nowych przesyłek z e-Doręczeń"
    category:  string;           // np. "Błąd"
    comments:  TicketComment[];
}
