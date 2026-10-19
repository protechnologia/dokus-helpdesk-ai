"""
Description:
Graf anonimizacji silnika `agent` (p. 19.5): kolejne kroki zamiany danych osobowych na znaczniki,
każdy w osobnym węźle z `agent_nodes/`.

    START → replace_patterns → split_chunks ─┬→ find_persons ───┬→ replace_found → END
                                             └→ find_addresses ─┘

| węzeł              | co robi                                                         |
|--------------------|-----------------------------------------------------------------|
| `replace_patterns` | dane o stałym kształcie (PESEL, telefon, e-mail…) wzorcami      |
| `split_chunks`     | tekst po wzorcach na części, które mieszczą się w oknie modelu  |
| `find_persons`     | model wskazuje imiona i nazwiska, kod szuka ich odmian w tekście |
| `find_addresses`   | model wskazuje adresy bez kotwicy, kod je dopasowuje i odsiewa  |
| `replace_found`    | miejsca osób i adresów na znaczniki, dłuższe wygrywa            |

O czym pamiętać przy zmianach:

- `find_persons` i `find_addresses` idą równolegle, a `replace_found` czeka na oba: osobne
  wywołania modelu zamiast jednego wspólnego, bo wspólne kosztowało w sondach przeciek osoby.
- Graf nie ma pętli ani rozgałęzień zależnych od wyniku; awaria modelu w którymkolwiek węźle
  zatrzymuje cały przebieg (fail-closed).
"""

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from anonymizer_app.agent_graphs.anonymize.state import AnonymizeState
from anonymizer_app.agent_nodes.base import Node
from anonymizer_app.agent_nodes.find_addresses.node import FindAddressesNode
from anonymizer_app.agent_nodes.find_persons.node import FindPersonsNode
from anonymizer_app.agent_nodes.replace_found.node import ReplaceFoundNode
from anonymizer_app.agent_nodes.replace_patterns.node import ReplacePatternsNode
from anonymizer_app.agent_nodes.split_chunks.node import SplitChunksNode
from anonymizer_app.engine_llm import LLMClient


def build_graph(
    replace_patterns: Node,  # np. ReplacePatternsNode()
    split_chunks:     Node,  # np. SplitChunksNode()
    find_persons:     Node,  # np. FindPersonsNode(llm)
    find_addresses:   Node,  # np. FindAddressesNode(llm)
    replace_found:    Node,  # np. ReplaceFoundNode()
) -> CompiledStateGraph:
    """
    Description:
    Składa graf anonimizacji z gotowych węzłów, według schematu z opisu modułu. Krawędzie idą po
    nazwach węzłów: dwa węzły o jednej nazwie to błąd przy składaniu.

    Example args:
        replace_patterns=ReplacePatternsNode()
        split_chunks=SplitChunksNode()
        find_persons=FindPersonsNode(llm)
        find_addresses=FindAddressesNode(llm)
        replace_found=ReplaceFoundNode()

    Example result:
        CompiledStateGraph: __start__ → replace_patterns → split_chunks → (find_persons
        ∥ find_addresses) → replace_found → __end__

    Raises:
        ValueError: dwa węzły o tej samej nazwie
    """
    graph = StateGraph(AnonymizeState)

    for node in (replace_patterns, split_chunks, find_persons, find_addresses, replace_found):
        graph.add_node(node.name, node.run)

    graph.add_edge(START, "replace_patterns")
    graph.add_edge("replace_patterns", "split_chunks")

    # --- osoby i adresy równolegle, na tych samych częściach ---
    graph.add_edge("split_chunks", "find_persons")
    graph.add_edge("split_chunks", "find_addresses")

    # Lista źródeł: `replace_found` rusza dopiero, gdy skończą oba węzły z modelem.
    graph.add_edge(["find_persons", "find_addresses"], "replace_found")
    graph.add_edge("replace_found", END)

    return graph.compile()


def build_agent_graph(
    llm: LLMClient,  # np. LLMClient(base_url="https://…/v1", model="speakleash/…")
) -> CompiledStateGraph:
    """
    Description:
    Graf z węzłów właściwych na podanym kliencie modelu — ten, na którym działa silnik `agent`.

    Example args:
        llm=LLMClient(base_url="https://…/v1", model="speakleash/…")

    Example result:
        CompiledStateGraph z węzłami ReplacePatternsNode, SplitChunksNode, FindPersonsNode,
        FindAddressesNode i ReplaceFoundNode
    """
    graph = build_graph(
        replace_patterns = ReplacePatternsNode(),
        split_chunks     = SplitChunksNode(),
        find_persons     = FindPersonsNode(llm),
        find_addresses   = FindAddressesNode(llm),
        replace_found    = ReplaceFoundNode(),
    )

    return graph
