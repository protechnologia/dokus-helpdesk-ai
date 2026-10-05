"""
Description:
Modele dokumentacji aplikacji: sekcja, manifest dokumentu i to, co powstaje przy wczytaniu
i indeksacji paczki. Plik nazywa się jak jego model. Importuje się z modułów
(`from app.core_model.docs.doc_section import DocSection`); ten plik niczego nie eksportuje.

| plik                      | model                | co opisuje                                    |
|---------------------------|----------------------|-----------------------------------------------|
| `doc_section.py`          | `DocSection`         | sekcja tak, jak widzą ją narzędzia agenta     |
| `doc_manifest.py`         | `DocManifest`        | `manifest.json` jednego dokumentu             |
| `doc_manifest_section.py` | `DocManifestSection` | wpis sekcji w manifeście                      |
| `doc_directory.py`        | `DocDirectory`       | katalog dokumentu po wczytaniu: treść i błędy |
| `doc_package.py`          | `DocPackage`         | cała paczka po wczytaniu                      |
| `docs_index_report.py`    | `DocsIndexReport`    | co zrobiła jedna indeksacja                   |
"""
