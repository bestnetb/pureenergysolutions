# PD Dashboard Bridge dla Home Assistant

Integracja laczy pojedyncza instancje Home Assistant z panelem `pd.best-net.pl`.

## Najprostsza instalacja przez HACS

1. Utworz publiczne repozytorium GitHub, np.:

   `pureenergysolutions`

2. Wrzuc do niego zawartosc tego katalogu, tak zeby w katalogu glownym repo byly:

   - `custom_components/pd_dashboard_bridge/`
   - `hacs.json`
   - `README.md`

3. W Home Assistant wejdz w `HACS`.

4. Otworz menu z trzema kropkami i wybierz `Custom repositories`.

5. Wklej adres repozytorium GitHub, np.:

   `https://github.com/bestnetb/pureenergysolutions`

6. Jako typ wybierz `Integration`.

7. Kliknij `Add`, potem znajdz `PD Dashboard Bridge` i kliknij `Download`.

8. Zrestartuj Home Assistant.

9. Dodaj integracje w HA:

   `Ustawienia -> Urzadzenia i uslugi -> Dodaj integracje -> PD Dashboard Bridge`

## Publikacja na GitHub

Minimalna struktura repo pod HACS:

```text
custom_components/
  pd_dashboard_bridge/
    __init__.py
    api.py
    config_flow.py
    const.py
    coordinator.py
    manifest.json
    sensor.py
    strings.json
    .translations/pl.json
hacs.json
README.md
```

W repozytorium GitHub ustaw:

- opis repozytorium, np. `Home Assistant bridge for PD energy dashboard`,
- topic: `home-assistant`, `hacs`, `custom-integration`, `energy`,
- wlaczone Issues,
- release, np. `v0.1.0`, gdy bedziesz chcial wygodnych aktualizacji wersji.

## Co robi

- paruje HA z panelem jednorazowym kodem wygenerowanym przez administratora,
- zapisuje staly token agenta w konfiguracji integracji HA,
- wysyla heartbeat do panelu,
- wysyla liste encji i ich aktualne stany do panelu,
- tworzy sensory diagnostyczne w HA: status, liczba encji, ostatni heartbeat, ostatnia wysylka encji.

## Instalacja reczna

1. Skopiuj katalog:

   `custom_components/pd_dashboard_bridge`

   do katalogu Home Assistant:

   `config/custom_components/pd_dashboard_bridge`

2. Zrestartuj Home Assistant.

3. W panelu `https://pd.best-net.pl/` zaloguj sie jako admin.

4. Wejdz w `Konfiguracja -> Panel wielu Home Assistant`.

5. Dodaj klienta, lokalizacje i instancje HA. Panel pokaze jednorazowy kod parowania.

6. W Home Assistant wejdz w:

   `Ustawienia -> Urzadzenia i uslugi -> Dodaj integracje`

7. Wybierz `PD Dashboard Bridge`.

8. Wpisz:

   - adres panelu: `https://pd.best-net.pl`
   - jednorazowy kod parowania z panelu

9. Po zapisaniu integracja zacznie wysylac heartbeat i encje.

## Interwaly

Domyslnie:

- heartbeat: 30 sekund,
- wysylka encji: 300 sekund.

Mozesz to zmienic w opcjach integracji w Home Assistant.

## Bezpieczenstwo

Kod parowania jest jednorazowy. Po parowaniu panel zwraca token agenta, ktory jest zapisywany lokalnie w Home Assistant i uzywany w naglowku `Authorization: Bearer ...`.

## Aktualny zakres

Ta wersja wysyla dane z HA do panelu i wykonuje bezpieczne komendy sterujace z heartbeat: select/input_select.select_option, number/input_number.set_value oraz switch.turn_on/off.
