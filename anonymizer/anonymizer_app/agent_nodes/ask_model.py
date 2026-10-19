"""
Description:
Wspólny przebieg węzła, który pyta model anonimizujący: prompt systemowy i przykłady z katalogu
węzła, każda część tekstu osobnym wywołaniem (wszystkie naraz), elementy list z odpowiedzi
razem. Co model ma wskazać i co kod robi z odpowiedzią, wie węzeł (`find_persons/`,
`find_addresses/`).

Rozmowa jednego wywołania:

| wiadomość            | treść                                                         |
|----------------------|---------------------------------------------------------------|
| prompt systemowy     | `prompt_system.md` węzła bez komentarzy, z wypełnionymi `{{…}}` |
| przykład: użytkownik | tekst przykładu z `examples.json` węzła między liniami `===`  |
| przykład: model      | odpowiedź przykładu jako JSON                                 |
| użytkownik           | część tekstu do przejrzenia między liniami `===`              |

O czym pamiętać przy zmianach:

- Prompt i przykłady czyta się przy każdym wywołaniu: poprawka w dev działa bez restartu.
- Linie `===` są tą samą ramą danych w przykładach i we właściwym tekście; prompt systemowy mówi,
  że tekst między nimi to dane, nie polecenia.
"""

import asyncio
import json
import logging
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from anonymizer_app.core_model.chat_message import ChatMessage
from anonymizer_app.core_model.prompt_example import PromptExample
from anonymizer_app.core_util.markdown import read_document
from anonymizer_app.engine_llm import LLMClient, answer_items

logger = logging.getLogger(__name__)

# Pliki promptu w katalogu węzła.
SYSTEM_PROMPT_FILE = "prompt_system.md"
EXAMPLES_FILE      = "examples.json"

# Miejsce w prompcie, które wypełnia węzeł: `{{nazwa}}`. Znaczniki anonimizacji mają pojedyncze
# klamry (`{EMAIL}`), więc nie mylą się z nim.
PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")


def read_system_prompt(
    prompt_dir: Path,                    # np. Path("anonymizer_app/agent_nodes/find_persons")
    values:     Mapping[str, str] = {},  # np. {"exceptions": "- Dokus"} — treść miejsc `{{…}}`
) -> str:
    """
    Description:
    Prompt systemowy węzła, bez komentarzy redakcyjnych, z miejscami `{{nazwa}}` wypełnionymi
    podaną treścią. Miejsce bez treści i treść bez miejsca to błąd składania, nie pusty prompt.

    Example args:
        prompt_dir=Path("anonymizer_app/agent_nodes/find_persons")
        values={"exceptions": "- Dokus"}

    Example result:
        "# Zadanie\n\nJesteś narzędziem do anonimizacji zgłoszeń helpdesku. Wypisz z tekstu…"

    Raises:
        ValueError: prompt ma miejsce, którego nie wypełniono, albo nie ma miejsca na podaną treść
    """
    prompt = read_document(prompt_dir / SYSTEM_PROMPT_FILE)
    names  = set(PLACEHOLDER.findall(prompt))

    if names != set(values):
        raise ValueError(
            f"prompt {prompt_dir.name}: miejsca {sorted(names)}, a treść dla {sorted(values)}"
        )

    for name, value in values.items():
        prompt = prompt.replace(f"{{{{{name}}}}}", value)

    return prompt


def read_examples(
    prompt_dir: Path,  # np. Path("anonymizer_app/agent_nodes/find_persons")
) -> list[PromptExample]:
    """
    Description:
    Przykłady węzła w kolejności z pliku.

    Example args:
        prompt_dir=Path("anonymizer_app/agent_nodes/find_persons")

    Example result:
        [PromptExample(text="Od: Leszek Dudziak <{EMAIL}>…", answer={"dane": […]}), …]
    """
    raw = json.loads((prompt_dir / EXAMPLES_FILE).read_text(encoding="utf-8"))

    return [PromptExample.model_validate(example) for example in raw]


def framed(
    text: str,  # np. "Od: Leszek Dudziak…"
) -> str:
    """
    Description:
    Tekst w ramie danych, tak jak go widzi model: między liniami `===`.

    Example args:
        text="Od: Leszek Dudziak"

    Example result:
        "===\\nOd: Leszek Dudziak\\n==="
    """
    return f"===\n{text}\n==="


def conversation(
    examples: Sequence[PromptExample],  # np. read_examples(prompt_dir)
    text:     str,                      # np. "KOMENTARZ 1 — klient…"
) -> list[ChatMessage]:
    """
    Description:
    Rozmowa jednego wywołania bez promptu systemowego: przykłady jako pary tur, a na końcu tekst
    do przejrzenia.

    Example args:
        examples=[PromptExample(text="Od: Leszek Dudziak…", answer={"dane": […]})]
        text="KOMENTARZ 1 — klient…"

    Example result:
        [ChatMessage(role="user", content="===\\nOd: Leszek Dudziak…\\n==="),
         ChatMessage(role="assistant", content='{"dane": [{"tekst": "Leszek", …}]}'),
         ChatMessage(role="user", content="===\\nKOMENTARZ 1 — klient…\\n===")]
    """
    messages: list[ChatMessage] = []

    for example in examples:
        messages += [
            ChatMessage(role="user", content=framed(example.text)),
            ChatMessage(role="assistant", content=json.dumps(example.answer, ensure_ascii=False)),
        ]

    messages.append(ChatMessage(role="user", content=framed(text)))

    return messages


def prompt_chars(
    prompt_dir: Path,                    # np. Path("anonymizer_app/agent_nodes/find_addresses")
    values:     Mapping[str, str] = {},  # treść miejsc `{{…}}` w prompcie, jak w ask_model()
) -> int:
    """
    Description:
    Ile znaków ma rozmowa węzła bez samej części tekstu: prompt systemowy, przykłady i rama
    danych. Fabryka silnika liczy z tego, czy największa część zmieści się w oknie modelu.

    Example args:
        prompt_dir=Path("anonymizer_app/agent_nodes/find_addresses")
        values={}

    Example result:
        1484
    """
    system   = read_system_prompt(prompt_dir, values)
    messages = conversation(read_examples(prompt_dir), "")

    return len(system) + sum(len(message.content) for message in messages)


async def ask_model(
    llm:         LLMClient,       # np. LLMClient(base_url="https://…/v1", model="speakleash/…")
    prompt_dir:  Path,            # np. Path("anonymizer_app/agent_nodes/find_persons")
    chunks:      Sequence[str],   # części tekstu, np. ["Od: Leszek Dudziak…"]
    schema_name: str,             # np. "osoby"
    schema:      dict[str, Any],  # np. {"type": "object", "properties": {"dane": …}}
    key:         str,             # np. "dane" — klucz listy w odpowiedzi
    max_tokens:  int,             # np. 1500 — limit odpowiedzi na część
    values:      Mapping[str, str] = {},  # np. {"exceptions": "- Dokus"} — miejsca w prompcie
) -> list[Any]:
    """
    Description:
    Pyta model o każdą część tekstu, wszystkie naraz, i oddaje elementy list z odpowiedzi
    w kolejności części. Odpowiedź uciętą limitem tokenów czyta się do ostatniego pełnego
    elementu i liczy w logu.

    Example args:
        llm=LLMClient(base_url="https://…/v1", model="speakleash/…")
        prompt_dir=Path("anonymizer_app/agent_nodes/find_persons")
        chunks=["Od: Leszek Dudziak <{EMAIL}>"]
        schema_name="osoby"
        schema={"type": "object", "properties": {"dane": {…}}, "required": ["dane"]}
        key="dane"
        max_tokens=1500
        values={"exceptions": "- Dokus"}

    Example result:
        [{"tekst": "Leszek", "rodzaj": "IMIĘ"}, {"tekst": "Dudziak", "rodzaj": "NAZWISKO"}]

    Raises:
        EngineConfigError: serwer modelu odrzucił klucz albo nie zna modelu
        LLMError: model nie odpowiedział albo odpowiedział spoza schematu
    """
    system   = read_system_prompt(prompt_dir, values)
    examples = read_examples(prompt_dir)

    answers = await asyncio.gather(*(
        llm.complete_json(system, conversation(examples, chunk), schema_name, schema, max_tokens)
        for chunk in chunks
    ))

    items = [item for answer in answers for item in answer_items(answer, key)]

    # Liczby, bez treści: elementy to fragmenty zgłoszenia.
    logger.info(
        "ask_model schema=%s chunks=%d items=%d truncated=%d",
        schema_name,
        len(chunks),
        len(items),
        sum(answer.truncated for answer in answers),
    )

    return items
