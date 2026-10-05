import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from app.core_model.docs.doc_package import DocPackage
from app.core_model.docs.docs_index_report import DocsIndexReport
from app.core_service.indexer_docs import DocsIndexRefused
from app.db_postgres import DbPostgresError
from app.db_qdrant import DbQdrantError
from app.engine_embedding import EmbeddingError
from app.entry_cli.cli import cli

# Komendy `helpdesk docs` przez prawdziwe drzewo CLI: kody wyjścia, pytanie o potwierdzenie i to,
# co trafia na ekran. Paczki są zmyślone, w `tmp_path`; samą indeksację zastępuje `StubRun`.

runner = CliRunner()


def _write_document(
    root:        Path,                          # np. tmp_path
    name:        str,                           # nazwa katalogu dokumentu, np. "administrator"
    section_ids: tuple[str, ...] = ("wstep",),  # sekcje w manifeście; każda dostaje plik
    synthetic:   bool = False,                  # flaga w manifeście
) -> Path:
    """
    Description:
    Zakłada katalog jednego dokumentu: manifest z podanymi sekcjami i plik `.md` na każdą.

    Example args:
        root=Path("/tmp/x")
        name="administrator"
        section_ids=("wstep",)
        synthetic=False

    Example result:
        Path("/tmp/x/administrator") z manifest.json i wstep.md
    """
    directory = root / name
    directory.mkdir()

    payload = {
        "document":  f"Instrukcja {name}",
        "version":   "4.12",
        "synthetic": synthetic,
        "sections":  [
            {"section_id": section_id, "title": f"Tytuł {section_id}", "description": "Opis"}
            for section_id in section_ids
        ],
    }

    (directory / "manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )

    for section_id in section_ids:
        (directory / f"{section_id}.md").write_text(f"Treść sekcji {section_id}.", "utf-8")

    return directory


class StubRun:
    """
    Description:
    Zastępuje przebieg indeksacji zapisem wywołań, żeby CLI dało się testować bez embeddera, Qdranta
    i Postgresa. Zapisuje każde wywołanie i oddaje wynik ustawiony przez test.

    Stoi w miejscu `_run`, nie serwisu: ten plik testuje kontrakt komendy, a przejście przez
    prawdziwych klientów testowałoby stack.
    """

    def __init__(self) -> None:
        """
        Description:
        Buduje stub oddający raport z jednego dokumentu.

        Example args:
            (brak)

        Example result:
            StubRun z pustym `calls`
        """
        self.calls:  list[dict]       = []
        self.report: DocsIndexReport = DocsIndexReport(documents=1, sections=1, fragments=1)
        self.error:  Exception | None = None

    async def __call__(
        self,
        package:   DocPackage,  # np. DocPackage(path=Path("/tmp/x"), directories=[…])
        synthetic: bool,        # np. False
    ) -> DocsIndexReport:
        """
        Description:
        Zapisuje wywołanie i oddaje raport albo zgłasza ustawiony błąd.

        Example args:
            package=DocPackage(path=Path("/tmp/x"), directories=[…])
            synthetic=False

        Example result:
            DocsIndexReport(documents=1, sections=1, fragments=1)

        Raises:
            Exception: błąd przypisany przez test do `error`
        """
        self.calls.append({"package": package, "synthetic": synthetic})

        if self.error is not None:
            raise self.error

        return self.report


@pytest.fixture
def stub_run(monkeypatch: pytest.MonkeyPatch) -> StubRun:
    """
    Description:
    Wstawia `StubRun` w miejsce przebiegu indeksacji i oddaje go testowi.

    Example args:
        (brak)

    Example result:
        StubRun, którego `calls` wypełnia się przy każdej komendzie
    """
    stub = StubRun()

    monkeypatch.setattr("app.entry_cli.docs.index._run", stub)

    return stub


# --- validate -----------------------------------------------------------------------------

def test_a_valid_package_exits_zero(tmp_path: Path) -> None:
    """Sprawdza, czy `helpdesk docs validate` na poprawnej paczce z jednym dokumentem i dwiema
    sekcjami kończy się kodem 0 i wypisuje linię o tym dokumencie oraz podsumowanie bez błędów.

    Wyłapuje komendę, która zgłasza błąd przy poprawnej paczce albo nie pokazuje, co wczytała:
    operator nie mógłby wtedy sprawdzić paczki przed indeksacją."""
    _write_document(tmp_path, "administrator", ("wstep", "uprawnienia"))

    result = runner.invoke(cli, ["docs", "validate", str(tmp_path)])

    assert result.exit_code == 0
    assert "OK   administrator — Instrukcja administrator 4.12, sekcji: 2" in result.output
    assert "Dokumentów: 1, sekcji: 2, błędów: 0, ostrzeżeń: 0." in result.output


def test_a_synthetic_document_is_marked(tmp_path: Path) -> None:
    """Sprawdza, czy przy dokumencie oznaczonym jako zmyślony `helpdesk docs validate` kończy się
    kodem 0 i wypisuje dopisek „(syntetyczny)".

    Wyłapuje zniknięcie tego dopisku: operator ma zobaczyć jeszcze przed indeksacją, że paczka
    jest zmyślona i nie nadaje się do właściwego indeksu."""
    _write_document(tmp_path, "zmyslony", synthetic=True)

    result = runner.invoke(cli, ["docs", "validate", str(tmp_path)])

    assert result.exit_code == 0
    assert "(syntetyczny)" in result.output


def test_a_broken_package_exits_one(tmp_path: Path) -> None:
    """Sprawdza, czy `helpdesk docs validate` na paczce, w której sekcji z manifestu brakuje
    pliku, kończy się kodem 1 i wypisuje błąd z nazwą katalogu dokumentu i brakującego pliku.

    Wyłapuje komendę, która przy zepsutej paczce kończy się kodem 0: nie dałoby się jej użyć jako
    bramki przed indeksacją, bo skrypt nie odróżniłby paczki dobrej od zepsutej."""
    directory = _write_document(tmp_path, "administrator")
    (directory / "wstep.md").unlink()

    result = runner.invoke(cli, ["docs", "validate", str(tmp_path)])

    assert result.exit_code == 1
    assert "BŁĄD administrator" in result.output
    assert "brak pliku wstep.md" in result.output


def test_a_package_level_error_exits_one(tmp_path: Path) -> None:
    """Sprawdza, czy `helpdesk docs validate` kończy się kodem 1 i wypisuje błąd, gdy dwa
    dokumenty mają sekcję o tym samym identyfikatorze (`wstep`), choć każdy z osobna jest
    poprawny.

    Wyłapuje komendę, która patrzy tylko na błędy pojedynczych dokumentów: paczka z powtórzonym
    identyfikatorem sekcji przeszłaby sprawdzenie, a ma on być jedyny w całej paczce."""
    _write_document(tmp_path, "administrator")
    _write_document(tmp_path, "uzytkownik")

    result = runner.invoke(cli, ["docs", "validate", str(tmp_path)])

    assert result.exit_code == 1
    assert "section_id wstep jest w kilku dokumentach" in result.output


def test_a_warning_does_not_fail_validation(
    tmp_path:    Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sprawdza, czy sekcja dłuższa niż próg ostrzeżenia (tu obniżony do 5 znaków) daje
    w `helpdesk docs validate` linię „UWAGA" na ekranie, a komenda i tak kończy się kodem 0.

    Wyłapuje dwie usterki: ostrzeżenie, które nie dociera do operatora, oraz ostrzeżenie
    traktowane jak błąd, przez które poprawna paczka z długą sekcją nie przeszłaby sprawdzenia."""
    monkeypatch.setattr("app.core_service.loader_doc_package.SECTION_WARN_CHARS", 5)
    _write_document(tmp_path, "administrator")

    result = runner.invoke(cli, ["docs", "validate", str(tmp_path)])

    assert result.exit_code == 0
    assert "UWAGA: sekcja wstep" in result.output


def test_validate_of_a_missing_directory_exits_two(tmp_path: Path) -> None:
    """Sprawdza, czy `helpdesk docs validate` kończy się kodem 2, gdy wskazanego katalogu nie ma —
    to inny kod niż 1 przy zepsutej paczce.

    Wyłapuje pomieszanie tych dwóch sytuacji: skrypt wołający komendę nie odróżniłby literówki
    w ścieżce od paczki z błędami."""
    result = runner.invoke(cli, ["docs", "validate", str(tmp_path / "nie-ma")])

    assert result.exit_code == 2


# --- index: odmowa przed pytaniem ---------------------------------------------------------

def test_index_of_a_broken_package_runs_nothing(tmp_path: Path, stub_run: StubRun) -> None:
    """Sprawdza, czy `helpdesk docs index` na paczce z błędem (sekcji brakuje pliku) kończy się
    kodem 1 od razu: nie pyta o potwierdzenie i nie uruchamia indeksacji.

    Wyłapuje komendę, która pyta o zgodę na zastąpienie indeksu albo zaczyna indeksację, choć
    paczki i tak nie wolno wgrać — w najgorszym razie zepsuta paczka zastąpiłaby działający
    indeks."""
    directory = _write_document(tmp_path, "administrator")
    (directory / "wstep.md").unlink()

    result = runner.invoke(cli, ["docs", "index", str(tmp_path)])

    assert result.exit_code == 1
    assert "Zastąpić" not in result.output
    assert stub_run.calls == []


def test_a_synthetic_package_is_refused_without_the_flag(
    tmp_path: Path,
    stub_run: StubRun,
) -> None:
    """Sprawdza, czy `helpdesk docs index` bez flagi `--synthetic` odmawia paczki z dokumentem
    zmyślonym: kończy się kodem 1, wypisuje powód i nie uruchamia indeksacji, także z `--yes`.

    Wyłapuje zmyśloną dokumentację wgraną do właściwego indeksu: czytają z niego narzędzia
    agenta, więc wymyślone instrukcje wracałyby jako źródło odpowiedzi."""
    _write_document(tmp_path, "zmyslony", synthetic=True)

    result = runner.invoke(cli, ["docs", "index", str(tmp_path), "--yes"])

    assert result.exit_code == 1
    assert "właściwego indeksu" in result.output
    assert stub_run.calls == []


def test_a_real_package_is_refused_with_the_flag(tmp_path: Path, stub_run: StubRun) -> None:
    """Sprawdza, czy `helpdesk docs index --synthetic` odmawia paczki z dokumentem, który nie jest
    oznaczony jako zmyślony: kończy się kodem 1 i nie uruchamia indeksacji, także z `--yes`.

    Wyłapuje sprawdzanie zgodności flagi z paczką tylko w jedną stronę: prawdziwa dokumentacja
    trafiłaby wtedy do indeksu syntetycznego, przeznaczonego wyłącznie na dane zmyślone."""
    _write_document(tmp_path, "administrator")

    result = runner.invoke(cli, ["docs", "index", str(tmp_path), "--synthetic", "--yes"])

    assert result.exit_code == 1
    assert stub_run.calls == []


def test_index_of_an_empty_package_runs_nothing(tmp_path: Path, stub_run: StubRun) -> None:
    """Sprawdza, czy `helpdesk docs index` na pustym katalogu kończy się kodem 1 i nie uruchamia
    indeksacji, także z `--yes`.

    Wyłapuje utratę działającego indeksu: indeksacja zastępuje cały indeks zawartością paczki,
    więc pusta paczka skasowałaby wszystko, co w nim było."""
    result = runner.invoke(cli, ["docs", "index", str(tmp_path), "--yes"])

    assert result.exit_code == 1
    assert stub_run.calls == []


def test_index_of_a_missing_directory_exits_two(tmp_path: Path, stub_run: StubRun) -> None:
    """Sprawdza, czy `helpdesk docs index` kończy się kodem 2 i nie uruchamia indeksacji, gdy
    wskazanego katalogu nie ma.

    Wyłapuje komendę, która literówkę w ścieżce traktuje jak pustą albo zepsutą paczkę (kod 1):
    skrypt wołający komendę nie odróżniłby wtedy złej ścieżki od błędów w paczce."""
    result = runner.invoke(cli, ["docs", "index", str(tmp_path / "nie-ma"), "--yes"])

    assert result.exit_code == 2
    assert stub_run.calls == []


# --- index: potwierdzenie -----------------------------------------------------------------

def test_index_asks_before_replacing(tmp_path: Path, stub_run: StubRun) -> None:
    """Sprawdza, czy `helpdesk docs index` bez `--yes` pyta o potwierdzenie, a po odpowiedzi „nie"
    kończy się kodem 1 i nie uruchamia indeksacji.

    Wyłapuje komendę, która zastępuje indeks bez pytania albo mimo odmowy: uruchomiona przez
    pomyłkę na złym katalogu podmieniłaby działający indeks dokumentacji."""
    _write_document(tmp_path, "administrator")

    result = runner.invoke(cli, ["docs", "index", str(tmp_path)], input="n\n")

    assert result.exit_code == 1
    assert stub_run.calls == []


def test_the_question_names_the_table_and_the_collection(
    tmp_path: Path,
    stub_run: StubRun,
) -> None:
    """Sprawdza, czy pytanie o potwierdzenie w `helpdesk docs index` nazywa tabelę (`docs_text`)
    i kolekcję (`docs`), które zostaną zastąpione.

    Wyłapuje pytanie, które nie mówi, co zniknie: operator potwierdzałby wtedy w ciemno i mógłby
    zastąpić nie ten indeks, o który mu chodziło."""
    _write_document(tmp_path, "administrator")

    result = runner.invoke(cli, ["docs", "index", str(tmp_path)], input="n\n")

    assert "tabelę 'docs_text' i kolekcję 'docs'" in result.output


def test_the_synthetic_flag_points_at_the_synthetic_index(
    tmp_path: Path,
    stub_run: StubRun,
) -> None:
    """Sprawdza, czy z flagą `--synthetic` pytanie o potwierdzenie nazywa osobny indeks
    syntetyczny (tabelę `docs_text_synthetic` i kolekcję `docs_synthetic`), a po odpowiedzi „tak"
    indeksacja dostaje tę flagę i komenda kończy się kodem 0.

    Wyłapuje flagę, która zmienia tylko treść pytania albo ginie po drodze: indeksacja poszłaby
    wtedy do innego indeksu, niż operator potwierdził."""
    _write_document(tmp_path, "zmyslony", synthetic=True)

    result = runner.invoke(cli, ["docs", "index", str(tmp_path), "--synthetic"], input="y\n")

    assert result.exit_code == 0
    assert "tabelę 'docs_text_synthetic' i kolekcję 'docs_synthetic'" in result.output
    assert stub_run.calls[0]["synthetic"] is True


def test_index_proceeds_when_confirmed(tmp_path: Path, stub_run: StubRun) -> None:
    """Sprawdza, czy po odpowiedzi „tak" `helpdesk docs index` uruchamia indeksację wczytanej
    paczki (jedna sekcja, właściwy indeks), kończy się kodem 0 i wypisuje liczby z raportu:
    dokumentów 1, sekcji 1, fragmentów 3.

    Wyłapuje komendę, która po potwierdzeniu nic nie robi, przekazuje dalej nie tę paczkę albo
    nie pokazuje wyniku — operator nie wiedziałby wtedy, co trafiło do indeksu."""
    _write_document(tmp_path, "administrator")
    stub_run.report = DocsIndexReport(documents=1, sections=1, fragments=3)

    result = runner.invoke(cli, ["docs", "index", str(tmp_path)], input="y\n")

    assert result.exit_code == 0
    assert stub_run.calls[0]["synthetic"] is False
    assert stub_run.calls[0]["package"].section_count == 1
    assert "dokumentów: 1, sekcji: 1, fragmentów: 3" in result.output


def test_yes_skips_the_question(tmp_path: Path, stub_run: StubRun) -> None:
    """Sprawdza, czy `helpdesk docs index --yes` nie zadaje pytania o potwierdzenie, uruchamia
    indeksację dokładnie raz i kończy się kodem 0.

    Wyłapuje komendę, która mimo `--yes` czeka na odpowiedź: nie dałoby się jej uruchomić ze
    skryptu, bo nikt by na pytanie nie odpowiedział."""
    _write_document(tmp_path, "administrator")

    result = runner.invoke(cli, ["docs", "index", str(tmp_path), "--yes"])

    assert result.exit_code == 0
    assert "Zastąpić" not in result.output
    assert len(stub_run.calls) == 1


# --- index: awarie ------------------------------------------------------------------------

@pytest.mark.parametrize(
    "error",
    [
        pytest.param(EmbeddingError("Embedder timed out"),      id="embedder"),
        pytest.param(DbPostgresError("nie da się połączyć"),    id="postgres"),
        pytest.param(DbQdrantError("Could not reach Qdrant"),   id="qdrant"),
    ],
)
def test_an_unreachable_service_exits_two(
    tmp_path: Path,
    stub_run: StubRun,
    error:    Exception,
) -> None:
    """Sprawdza, czy `helpdesk docs index` kończy się kodem 2, gdy indeksacja zgłasza awarię
    usługi. Trzy przypadki: nie odpowiada embedder, Postgres albo Qdrant.

    Wyłapuje awarię usługi pomyloną z zepsutą paczką (kod 1) albo wypuszczoną jako nieobsłużony
    wyjątek: przy leżącej usłudze ponowienie tej samej komendy może zadziałać, przy zepsutej
    paczce nie, więc skrypt musi umieć je odróżnić."""
    _write_document(tmp_path, "administrator")
    stub_run.error = error

    result = runner.invoke(cli, ["docs", "index", str(tmp_path), "--yes"])

    assert result.exit_code == 2


def test_a_refusal_from_the_indexer_itself_exits_one(tmp_path: Path, stub_run: StubRun) -> None:
    """Sprawdza, czy odmowa zgłoszona dopiero przez sam indekser (`DocsIndexRefused`), już po
    przyjęciu paczki przez komendę, też kończy się kodem 1.

    Wyłapuje odmowę, która na tej drodze dostaje inny kod albo wychodzi jako nieobsłużony
    wyjątek: ta sama przyczyna miałaby wtedy dwa różne kody, zależnie od tego, kto ją zauważył."""
    _write_document(tmp_path, "administrator")
    stub_run.error = DocsIndexRefused("paczka ma błędy")

    result = runner.invoke(cli, ["docs", "index", str(tmp_path), "--yes"])

    assert result.exit_code == 1
