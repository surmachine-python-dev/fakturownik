# Fakturownik

Poczatkowa implementacja lokalnej aplikacji Windows do obslugi rachunkow i faktur koncowych.

## Zakres MVP w tym repo

- rejestracja rachunkow z wieloma pozycjami
- baza klientow i wybor klienta z listy przy tworzeniu rachunku
- walidacja pozycji: mozna podac tylko `ilosc` albo `waga`
- automatyczne przeliczenie `wartosci` lub `ceny jednostkowej`
- tworzenie faktury koncowej z wielu rachunkow
- blokada edycji rachunku po przypisaniu do faktury koncowej
- lokalna baza SQLite
- backup i odtworzenie danych do jednego archiwum ZIP
- przechowywanie zalacznikow jako plikow na dysku

## Wymagania

- Python 3.12+
- Windows

## Instalacja developerska

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

## Build Windows

### Portable `.exe` przez PyInstaller

```powershell
.\.venv\Scripts\pyinstaller.exe --noconfirm --clean Fakturownik.spec
```

Wynik aplikacji przenosnej pojawi sie w `dist\Fakturownik\`.

### Pelny instalator Windows

1. Zainstaluj Inno Setup 6.
2. Uruchom skrypt builda:

```powershell
.\scripts\build-installer.ps1
```

Skrypt:

- buduje aplikacje przez PyInstaller,
- wykrywa `ISCC.exe` z Inno Setup,
- generuje instalator w `dist\installer\`.

Przydatne warianty:

```powershell
.\scripts\build-installer.ps1 -SkipInstaller
.\scripts\build-installer.ps1 -Clean
```

## Struktura

- `app.py` - punkt startowy aplikacji
- `src/fakturownik/config.py` - sciezki i konfiguracja lokalna
- `src/fakturownik/database.py` - konfiguracja SQLite i sesji
- `src/fakturownik/models.py` - modele SQLAlchemy
- `src/fakturownik/services/calculations.py` - walidacja i przeliczenia pozycji
- `src/fakturownik/services/backup.py` - eksport i import backupu
- `src/fakturownik/services/documents.py` - logika zapisu dokumentow
- `src/fakturownik/ui/main_window.py` - glowne okno PySide6

## Uwagi

To jest pierwszy etap implementacji. Kolejne kroki to wydruki, pelniejsze wyszukiwanie, migracje schematu i dopracowanie UX.