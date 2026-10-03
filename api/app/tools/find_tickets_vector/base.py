"""
Description:
To, co wspólne dla prawdziwego `find_tickets_vector` i jego atrapy: nazwa, klasa zapytania, tekst
dla modelu (`render_for_model()`) i lista źródeł (`cite()`). Narzędzie i atrapa różnią się wyłącznie
tym, skąd biorą wynik (`search()`), więc test na atrapie sprawdza ten sam tekst, który model
dostanie na produkcji.

Przed — wynik wyszukiwania:

    FindTicketsVectorResult(
        items = [
            FoundTicket(score=0.91, ticket=ParsedTicket(ticket_id="90001", …)),
            FoundTicket(score=0.86, ticket=ParsedTicket(ticket_id="90003", cause="brak", …)),
        ],
        dropped_below_threshold = 1,
    )

Po — tekst dla modelu:

    Znalezione zgłoszenia: 2 (odcięte progiem: 1)

    Przyczyny (`cause`) w trafieniach:
    - [90001] Zacięta kolejka pobierania po przerwanym połączeniu
    - [90003] (nie ustalono)

    [90001] 2026-02-10 · podobieństwo 0.91
    component: e-Doręczenia
    problem: Nie przychodzą przesyłki z e-Doręczeń
    symptoms: Brak nowych przesyłek, choć nadawcy potwierdzają wysyłkę
    error_codes: (brak)
    cause: Zacięta kolejka pobierania po przerwanym połączeniu
    solution: Zrestartowano kolejkę; zaległe przesyłki pobrały się same.
    resolution: naprawione
    questions_summary: pytano, od kiedy brak przesyłek i czy dotyczy wszystkich skrzynek

    [90003] 2026-06-03 · podobieństwo 0.86
    …

Co się dzieje po drodze:

1. Nagłówek mówi, ile zgłoszeń znaleziono i ile odciął próg — „nic nie było" i „próg wszystko
   wyciął" to dla agenta różne sytuacje.
2. Blok przyczyn stoi PRZED rekordami i ma po jednej linii na trafienie. Przyczyna utopiona wśród
   ośmiu pól rekordu do modelu nie dociera.
3. Przyczyna nieustalona („brak", „Brak ustalonej przyczyny w wątku.") wchodzi do bloku jako
   „(nie ustalono)", żeby trzy puste przyczyny nie wyglądały jak trzy zgodne. Co jest
   nieustalone, rozstrzyga `no_cause()` z `service/normalizer_sentinel.py`.
4. Rekordy niosą wszystkie pola payloadu pod nazwami ze schematu, bo prompty grafów odwołują się
   do nich po nazwie (`cause`, `solution`, `questions_summary`).

O czym pamiętać przy zmianach:

- Ten tekst jest częścią promptu: jego kształt stroi się pomiarem razem z promptami grafów
  (p. 23, 25–26), nie na oko.
- Cytować wolno tylko to, co model zobaczył — `cite()` i `render_for_model()` chodzą po tych
  samych elementach wyniku.
"""

from app.service.normalizer_sentinel import no_cause
from app.tools.base import KnowledgeSource
from app.tools.find_tickets_vector.models import (
    FindTicketsVectorQuery,
    FindTicketsVectorResult,
    FoundTicket,
)
from app.tools.models import SourceRef

CAUSE_NOT_ESTABLISHED = "(nie ustalono)"
CAUSES_HEADING        = "Przyczyny (`cause`) w trafieniach:"
NO_ERROR_CODES        = "(brak)"


def render_ticket(
    found: FoundTicket,  # np. FoundTicket(score=0.91, ticket=ParsedTicket(ticket_id="90001", …))
) -> str:
    """
    Description:
    Jeden rekord w tekście dla modelu: linia z id, datą i podobieństwem, pod nią pola payloadu
    pod nazwami ze schematu. `cause` zostaje tu w oryginalnym brzmieniu — bywa w nim hipoteza,
    której „(nie ustalono)" z bloku przyczyn nie niesie.

    Example args:
        found=FoundTicket(score=0.91, ticket=ParsedTicket(ticket_id="90001", …))

    Example result:
        "[90001] 2026-02-10 · podobieństwo 0.91\\ncomponent: e-Doręczenia\\nproblem: …"
    """
    ticket = found.ticket

    lines = [
        f"[{ticket.ticket_id}] {ticket.date.isoformat()} · podobieństwo {found.score:.2f}",
        f"component: {ticket.component}",
        f"problem: {ticket.problem}",
        f"symptoms: {ticket.symptoms}",
        f"error_codes: {', '.join(ticket.error_codes) or NO_ERROR_CODES}",
        f"cause: {ticket.cause}",
        f"solution: {ticket.solution}",
        f"resolution: {ticket.resolution}",
        f"questions_summary: {ticket.questions_summary}",
    ]

    return "\n".join(lines)


class FindTicketsVectorBase(KnowledgeSource):
    """
    Description:
    Wspólna część `find_tickets_vector`: wszystko poza samym wyszukaniem.

    Do czego:
    Po tej klasie dziedziczą `FindTicketsVector` (embedder i Qdrant) oraz `FakeFindTicketsVector`
    (ustalony zestaw). Każda dokłada wyłącznie `search()`, więc tekst dla modelu i lista źródeł są
    te same w testach i na produkcji.

    Flow:
        1. `search()` podklasy zwraca `FindTicketsVectorResult`.
        2. `render_for_model()` robi z niego tekst: nagłówek, blok przyczyn, rekordy.
        3. `cite()` robi z niego listę źródeł — po jednym wpisie na rekord z tekstu.
    """

    name        = "find_tickets_vector"
    source      = "tickets"
    query_model = FindTicketsVectorQuery

    def render_for_model(
        self,
        result: FindTicketsVectorResult,  # np. FindTicketsVectorResult(items=[…])
    ) -> str:
        """
        Description:
        Tekst, który model czyta jako odpowiedź narzędzia: nagłówek z licznikami, blok przyczyn
        wszystkich trafień i rekordy. Bez trafień zostaje sam nagłówek.

        Example args:
            result=FindTicketsVectorResult(items=[FoundTicket(…)], dropped_below_threshold=1)

        Example result:
            "Znalezione zgłoszenia: 1 (odcięte progiem: 1)\\n\\nPrzyczyny (`cause`) w
             trafieniach:\\n- [90001] Zacięta kolejka…\\n\\n[90001] 2026-02-10 · podobieństwo 0.91…"
        """
        header = (
            f"Znalezione zgłoszenia: {len(result.items)} "
            f"(odcięte progiem: {result.dropped_below_threshold})"
        )

        # --- nic nie znaleziono: nie ma przyczyn ani rekordów do pokazania ---
        if not result.items:
            return header

        # --- blok przyczyn: jedna linia na trafienie, przed rekordami ---
        causes = []

        for found in result.items:
            # Co jest przyczyną nieustaloną, rozstrzyga `no_cause()` z `normalizer_sentinel.py`.
            cause = CAUSE_NOT_ESTABLISHED if no_cause(found.ticket.cause) else found.ticket.cause
            causes.append(f"- [{found.ticket.ticket_id}] {cause}")

        causes_block = "\n".join([CAUSES_HEADING, *causes])

        # --- rekordy ---
        records = [render_ticket(found) for found in result.items]

        text = "\n\n".join([header, causes_block, *records])

        return text

    def cite(
        self,
        result: FindTicketsVectorResult,  # np. FindTicketsVectorResult(items=[…])
    ) -> list[SourceRef]:
        """
        Description:
        Jeden wpis na każde zgłoszenie z wyniku; tytułem jest `problem`.

        Example args:
            result=FindTicketsVectorResult(items=[FoundTicket(score=0.91, ticket=ParsedTicket(…))])

        Example result:
            [SourceRef(source="tickets", item_id="90001", title="Nie przychodzą…", …)]
        """
        refs = [
            SourceRef(
                source  = self.source,
                item_id = found.ticket.ticket_id,
                title   = found.ticket.problem,
                score   = found.score,
                date    = found.ticket.date,
            )
            for found in result.items
        ]

        return refs
