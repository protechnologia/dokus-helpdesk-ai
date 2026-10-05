"""
Configuration plumbing: does a variable name survive the whole way from the contract to the code?

THREE SOURCES declare configuration, and every pair of them must agree — in BOTH directions:

    .env.example  ──(1)──▶  Settings      every knob a service reads is documented
                  ◀─(2)──                 every documented entry has a reader
                  ──(4)──▶  compose       every documented entry reaches a container
                  ◀─(3)──                 every interpolated ${VAR} is documented
    compose       ──(7)──▶  Settings      per service: no key the service cannot read
                  ◀─(8)──                 per service: no field the service never receives

TESTS BELOW, IN THIS ORDER — the number in each docstring points back to this map:

    (1)  every_settings_field_is_declared_in_env_example        Settings → .env.example
    (2)  every_env_example_entry_is_consumed_by_a_service       .env.example → Settings
    (3)  every_variable_interpolated_by_compose_is_declared…    compose ${VAR} → .env.example
    (4)  every_env_example_entry_reaches_a_container_or_steers… .env.example → compose env
    (5)  no_compose_only_variable_is_handed_to_a_container      DOCKER_* → compose
    (6)  no_settings_field_claims_the_compose_only_prefix       DOCKER_* → Settings
    (7)  every_env_key_in_compose_is_readable_by_the_service…   compose → Settings, per service
    (8)  every_settings_field_is_supplied_to_its_service        Settings → compose, per service
    (9)  services_agree_on_shared_variable_names                Settings ↔ Settings

WHY BOTH DIRECTIONS OF EVERY EDGE. One direction catches a typo loudly; the other catches silence.
Edge (8) was missing for a while and the gap was invisible: every Settings field has a default, so
a service that stops receiving its key still starts and still reports healthy — it just runs on the
value baked into the code. For QDRANT_URL that means quietly talking to the wrong Qdrant. Nor does
indirect coverage help: a variable read by two services (LOG_LEVEL) can be dropped from one of them
while (4) stays green, because it still reaches the other.

Tests (5) and (6) are not an edge but a guard on the DOCKER_ predicate below, which excludes those
names from (2) and (4); without them the prefix would be a blind spot rather than a contract.

WHAT THIS FILE DOES NOT CHECK. It compares NAMES, never values or behaviour: a wrong type, a wrong
unit or a nonsensical default flows straight through. Everything here is read as DATA — no Docker,
no `docker compose config`, no network — which is what keeps it a unit test.
"""

import re
from pathlib import Path
from typing import Any

import yaml
from pydantic_settings import BaseSettings

from app.config import Settings as ApiSettings
from embedder_app.config import Settings as EmbedderSettings

REPO_ROOT     = Path(__file__).resolve().parents[2]
ENV_EXAMPLE   = REPO_ROOT / ".env.example"
COMPOSE_BASE  = REPO_ROOT / "docker-compose.yml"

# `${VAR}`, `${VAR:-default}`, `${VAR-default}` — the name is what matters, defaults are noise.
COMPOSE_VAR_PATTERN = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)[^}]*\}")

# One `.env.example` is the contract for the WHOLE compose project, so the comparison must cover
# every service that reads it — not just `api`. A variable owned by another service (e.g.
# EMBEDDING_BACKEND) is a valid entry, and one owned by nobody is a dead entry.
SERVICE_SETTINGS: tuple[type[BaseSettings], ...] = (ApiSettings, EmbedderSettings)

# Which compose service is configured by which Settings class. Qdrant and Postgres are absent on
# purpose: both run third-party software with its own contract (our Postgres image only adds a
# dictionary), so none of our classes describes them. The POSTGRES_* names the database container
# receives are still covered — `api` reads the same variables, so edges (2) and (4) see them.
SETTINGS_BY_SERVICE: dict[str, type[BaseSettings]] = {
    "api":      ApiSettings,
    "embedder": EmbedderSettings,
}

# Variables consumed by `docker compose` itself rather than by any application: they are
# interpolated into the compose file and never enter a container, so no Settings class declares
# them. The prefix is the contract, which is why this is a predicate and not a list.
#
# Cost of the predicate, accepted deliberately: it excludes EVERY future DOCKER_* name from the
# checks below, including one that was misnamed and should have reached a container. An explicit
# list would have caught that; the prefix buys zero-maintenance at the price of that one case.
COMPOSE_ONLY_ENV_PREFIX = "DOCKER_"


def _is_compose_only(name: str) -> bool:                    # e.g. "DOCKER_API_PORT"
    """
    Description:
    Tells whether a variable is resolved by `docker compose` itself, rather than being handed to
    a container for some service to read.

    Example args:
        name="DOCKER_API_PORT"

    Example result:
        True
    """
    return name.startswith(COMPOSE_ONLY_ENV_PREFIX)


def _drop_compose_only(names: set[str]) -> set[str]:        # e.g. {"LOG_LEVEL", "DOCKER_API_PORT"}
    """
    Description:
    Removes the compose-only names from a set, leaving only variables that a service is expected
    to read. Used by the checks that compare `.env.example` against `Settings` declarations.

    Example args:
        names={"LOG_LEVEL", "DOCKER_API_PORT"}

    Example result:
        {"LOG_LEVEL"}
    """
    return {name for name in names if not _is_compose_only(name)}


def _env_names_from_example() -> set[str]:
    """
    Description:
    Reads `.env.example` as DATA (no dotenv loading, no Docker) and returns the declared
    variable names. Values are irrelevant here — this file is a name contract.

    Example args:
        (none)

    Example result:
        {"LOG_LEVEL", "LLM_PROVIDER", "QDRANT_URL"}
    """
    names: set[str] = set()

    for raw_line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        # comments and blank lines carry no contract
        if not line or line.startswith("#"):
            continue
        # a line without "=" is malformed rather than a declaration
        if "=" not in line:
            continue
        names.add(line.split("=", 1)[0].strip())

    return names


def _env_names_from_settings(settings_class: type[BaseSettings]) -> set[str]:
    """
    Description:
    Returns the ENV names one service's `Settings` can consume, derived from its field names.
    The mapping is a plain upper-casing — `qdrant_url` is fed by `QDRANT_URL`.

    Example args:
        settings_class=ApiSettings

    Example result:
        {"LOG_LEVEL", "LLM_PROVIDER", "QDRANT_URL"}
    """
    return {field_name.upper() for field_name in settings_class.model_fields}


def _env_names_from_all_services() -> set[str]:
    """
    Description:
    Union of the ENV names every service can consume — the set of variables the project as a
    whole has a reader for.

    Example args:
        (none)

    Example result:
        {"LOG_LEVEL", "LLM_PROVIDER", "QDRANT_URL", "EMBEDDING_BACKEND"}
    """
    return set().union(*(_env_names_from_settings(cls) for cls in SERVICE_SETTINGS))


class _ComposeLoader(yaml.SafeLoader):
    """
    Description:
    SafeLoader that tolerates Compose's own YAML tags. `volumes: !reset []` in the prod layer is
    valid Compose but unknown to plain YAML, and SafeLoader raises on an unknown tag — so reading
    the file as data would fail on exactly the line that makes the prod layer work.
    """


def _construct_reset(loader: yaml.SafeLoader, node: yaml.Node) -> Any:
    """
    Description:
    Resolves `!reset` to the value it decorates. The test only cares about names and structure,
    and `!reset []` carries the same emptiness as `[]` for that purpose.

    Example args:
        loader=<_ComposeLoader>
        node=SequenceNode(tag='!reset', value=[])

    Example result:
        []
    """
    # `!reset []` is a sequence; `!reset` on a scalar is legal Compose too, hence both branches.
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)

    return loader.construct_scalar(node)


_ComposeLoader.add_constructor("!reset", _construct_reset)


def _load_compose(path: Path) -> dict:                      # e.g. REPO_ROOT / "docker-compose.yml"
    """
    Description:
    Reads a compose file as DATA — no Docker, no `docker compose config`, no network. That keeps
    this a unit test: it checks the flow of NAMES between the three declarations, and a test that
    needed a daemon could not run in the default offline pass.

    Example args:
        path=Path("/repo/docker-compose.yml")

    Example result:
        {"services": {"api": {"environment": {"LOG_LEVEL": "${LOG_LEVEL:-INFO}"}}}}
    """
    return yaml.load(path.read_text(encoding="utf-8"), Loader=_ComposeLoader)


def _env_keys_passed_to_containers() -> set[str]:
    """
    Description:
    Returns the ENV keys the base composition hands to containers — the left-hand side of every
    `environment:` mapping, across all services.

    Example args:
        (none)

    Example result:
        {"LOG_LEVEL", "LLM_PROVIDER", "EMBEDDING_BACKEND"}
    """
    compose = _load_compose(COMPOSE_BASE)
    keys: set[str] = set()

    for service in compose["services"].values():
        keys.update(service.get("environment", {}))

    return keys


def _variables_interpolated_in_compose() -> set[str]:
    """
    Description:
    Returns every `${VAR}` name the base composition interpolates, wherever it appears — values
    of `environment:`, but also `ports:` and anything else. These are the names `docker compose`
    itself resolves, so each one must be documented in `.env.example`.

    Example args:
        (none)

    Example result:
        {"LOG_LEVEL", "DOCKER_BIND_ADDR", "DOCKER_API_PORT", "QDRANT_URL"}
    """
    return set(COMPOSE_VAR_PATTERN.findall(COMPOSE_BASE.read_text(encoding="utf-8")))


# --- edge .env.example <-> Settings: every knob documented, every entry with a reader ---


def test_every_settings_field_is_declared_in_env_example() -> None:
    """Sprawdza, czy każde pole konfiguracji (`Settings`) usług `api` i `embedder` ma wpis o tej
    samej nazwie w `.env.example` (numer 1 na mapie u góry pliku).

    Wyłapuje ustawienie dodane w kodzie, ale nieopisane w `.env.example`: osoba wdrażająca nie
    wie wtedy, że taka zmienna istnieje."""
    missing = _env_names_from_all_services() - _env_names_from_example()

    assert not missing, f"Missing in .env.example: {sorted(missing)}"


def test_every_env_example_entry_is_consumed_by_a_service() -> None:
    """Sprawdza, czy każdy wpis z `.env.example` jest czytany przez konfigurację (`Settings`)
    którejś usługi; pomijane są zmienne `DOCKER_*`, z których korzysta sam `docker compose`
    (numer 2 na mapie u góry pliku).

    Wyłapuje martwy wpis, na przykład po zmianie nazwy pola w kodzie: ktoś ustawia zmienną
    opisaną w `.env.example`, a żadna usługa jej nie czyta."""
    declared = _drop_compose_only(_env_names_from_example())
    unused   = declared - _env_names_from_all_services()

    assert not unused, f"Declared in .env.example but read by nobody: {sorted(unused)}"


# --- edge .env.example <-> compose: is every interpolated name documented, and every entry used ---


def test_every_variable_interpolated_by_compose_is_declared_in_env_example() -> None:
    """Sprawdza, czy każda zmienna, którą `docker-compose.yml` podstawia zapisem `${NAZWA}`, ma
    wpis w `.env.example` (numer 3 na mapie u góry pliku).

    Wyłapuje ukryte ustawienie: compose czyta zmienną, o której `.env.example` nie mówi, więc
    nikt nie wie, że da się ją ustawić i że wpływa na uruchomienie."""
    missing = _variables_interpolated_in_compose() - _env_names_from_example()

    assert not missing, f"Interpolated in compose, missing in .env.example: {sorted(missing)}"


def test_every_env_example_entry_reaches_a_container_or_steers_compose() -> None:
    """Sprawdza, czy każdy wpis z `.env.example`, poza zmiennymi `DOCKER_*`, jest
    w `docker-compose.yml` przekazywany choć jednemu kontenerowi (numer 4 na mapie u góry
    pliku).

    Wyłapuje zmienną opisaną w `.env.example`, której compose nie podaje żadnej usłudze: jej
    ustawienie niczego nie zmienia, bo do kontenera nie dociera."""
    expected = _drop_compose_only(_env_names_from_example())
    unused   = expected - _env_keys_passed_to_containers()

    assert not unused, f"In .env.example but never reaching a container: {sorted(unused)}"


# --- the DOCKER_ prefix: both checks that keep the predicate above from becoming a blind spot ---


def test_no_compose_only_variable_is_handed_to_a_container() -> None:
    """Sprawdza, czy żadna zmienna o nazwie zaczynającej się od `DOCKER_` nie jest
    w `docker-compose.yml` przekazywana do kontenera (numer 5 na mapie u góry pliku).

    Wyłapuje złamanie umowy, że `DOCKER_*` to zmienne samego `docker compose`, które do
    kontenera nie wchodzą. Kontrole wpisów `.env.example` pomijają ten przedrostek, więc zmienna
    podana usłudze pod taką nazwą wymknęłaby się im."""
    leaked = {name for name in _env_keys_passed_to_containers() if _is_compose_only(name)}

    assert not leaked, f"DOCKER_* must never reach a container: {sorted(leaked)}"


def test_no_settings_field_claims_the_compose_only_prefix() -> None:
    """Sprawdza, czy żadna usługa nie ma w konfiguracji (`Settings`) pola o nazwie zaczynającej
    się od `DOCKER_` (numer 6 na mapie u góry pliku).

    Wyłapuje pole nazwane tak przez pomyłkę: kontrole wpisów `.env.example` pomijają ten
    przedrostek, więc takie ustawienie wymknęłoby się im, choć usługa naprawdę je czyta."""
    claimed = {name for name in _env_names_from_all_services() if _is_compose_only(name)}

    assert not claimed, f"Settings must not declare DOCKER_* names: {sorted(claimed)}"


# --- edge compose <-> Settings, PER SERVICE: does each service get exactly the keys it reads ---
#
# The per-service part is what the other edges cannot express. Checking one direction only is not
# enough here, and the gap is invisible rather than loud: every Settings field has a default, so a
# service that stops receiving its key still starts, still reports healthy, and silently runs on
# the value baked into the code. For QDRANT_URL that means quietly talking to the wrong Qdrant.


def test_every_env_key_in_compose_is_readable_by_the_service_it_targets() -> None:
    """Sprawdza, czy każda zmienna, którą `docker-compose.yml` podaje usłudze `api` albo
    `embedder`, ma odpowiadające jej pole w konfiguracji (`Settings`) tej właśnie usługi (numer 7
    na mapie u góry pliku).

    Wyłapuje literówkę w nazwie zmiennej albo zmienną podaną nie tej usłudze: usługa po cichu
    pomija nazwę, której nie zna, więc ustawiona wartość nigdy nie zaczyna działać."""
    compose = _load_compose(COMPOSE_BASE)

    for service_name, settings_class in SETTINGS_BY_SERVICE.items():
        passed   = set(compose["services"][service_name].get("environment", {}))
        readable = _env_names_from_settings(settings_class)
        unknown  = passed - readable

        assert not unknown, f"Service '{service_name}' gets unreadable keys: {sorted(unknown)}"


def test_every_settings_field_is_supplied_to_its_service() -> None:
    """Sprawdza, czy każde pole konfiguracji (`Settings`) usługi `api` i usługi `embedder` jest
    w `docker-compose.yml` podawane tej właśnie usłudze, bez żadnych wyjątków (numer 8 na mapie
    u góry pliku).

    Wyłapuje pole, którego usługa nigdy nie dostaje. Taka usterka niczym się nie objawia: każde
    pole ma wartość domyślną, więc usługa startuje, zgłasza się jako zdrowa i po cichu działa na
    wartości z kodu — przy `QDRANT_URL` znaczy to rozmowę z niewłaściwym adresem."""
    compose = _load_compose(COMPOSE_BASE)

    # No exemption list on purpose: leaving a field on its coded default must be a deliberate
    # act, and the way to declare it is to add the key to compose — not to quietly omit it here.
    for service_name, settings_class in SETTINGS_BY_SERVICE.items():
        passed   = set(compose["services"][service_name].get("environment", {}))
        declared = _env_names_from_settings(settings_class)
        missing  = declared - passed

        assert not missing, f"Service '{service_name}' never receives: {sorted(missing)}"


# --- (9) Settings <-> Settings: not an edge between sources, but between two readers ---


def test_services_agree_on_shared_variable_names() -> None:
    """Sprawdza, czy zmienne wspólne dla usług `api` i `embedder`, czyli `LOG_LEVEL`
    i `EMBEDDING_VECTOR_SIZE`, mają w konfiguracji (`Settings`) obu usług tę samą nazwę (numer 9
    na mapie u góry pliku).

    Wyłapuje zmianę nazwy zrobioną tylko w jednej usłudze: usługi czytałyby wtedy dwie różne
    zmienne, a wymiar wektora, który musi być ten sam w obu usługach i w kolekcji Qdranta,
    mógłby się rozjechać."""
    shared = _env_names_from_settings(ApiSettings) & _env_names_from_settings(EmbedderSettings)

    # LOG_LEVEL and the vector width are deliberately shared: the dimension is one contract with
    # the Qdrant collection, so `api` and `embedder` must not drift into two names for it.
    assert {"LOG_LEVEL", "EMBEDDING_VECTOR_SIZE"} <= shared
