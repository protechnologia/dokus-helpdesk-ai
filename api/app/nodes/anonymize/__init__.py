"""
Description:
Węzeł `anonymize`: zamienia `input_text` na `AnonymizedText` i nic poza tym przez niego nie
przechodzi do modelu zewnętrznego. Fail-closed — niepewna anonimizacja zatrzymuje graf, zamiast
wypuścić tekst dalej.

Nie ma atrapy WĘZŁA: od razu jest właściwy, na atrapie zależności (`FakeAnonymizer`). Atrapa
węzła byłaby drugą drogą obok anonimizacji, której test grafów nie odróżniłby od prawdziwej.

Status: katalog. Węzeł powstaje w p. 4, prawdziwy anonimizator w p. 16 (CLAUDE.md -> „Plan
i TODO").
"""
