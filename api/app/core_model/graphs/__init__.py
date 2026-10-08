"""
Description:
Modele wyników wspólne dla kilku grafów. Wynik używany przez jeden graf leży przy nim, w
`agent_graphs/<graf>/models.py`. Plik nazywa się jak jego model; importuje się z modułów.

| plik                | model           | co opisuje                                          |
|---------------------|-----------------|-----------------------------------------------------|
| `verdict.py`        | `Verdict`       | werdykt bramki zamknięcia i bramki wysyłki          |
| `proposal.py`       | `Proposal`      | propozycja odpowiedzi z grafów `suggest_*`          |
| `proposal_notes.py` | `ProposalNotes` | propozycja bez źródeł: same uwagi dla wdrożeniowca  |
"""
