"""
Description:
Węzeł `anonymize`: zamienia `input_text` na `AnonymizedText` i nic poza tym przez niego nie
przechodzi do modelu zewnętrznego. Fail-closed — niepewna anonimizacja zatrzymuje graf, zamiast
wypuścić tekst dalej.

Nie ma atrapy WĘZŁA: od razu jest właściwy, na atrapie zależności (`FakeAnonymizer`). Atrapa
węzła byłaby drugą drogą obok anonimizacji, której test grafów nie odróżniłby od prawdziwej.

Status: węzeł właściwy (`AnonymizeNode`); prawdziwy anonimizator w p. 19 (CLAUDE.md -> „Plan
i TODO").
"""

from app.agent_nodes.anonymize.node import AnonymizeNode

__all__ = [
    "AnonymizeNode",
]
