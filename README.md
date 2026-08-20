# bolig-scraper

Scanner boligzonen.dk, boligportal.dk og munkebjergpark.dk for lejeboliger der matcher
dine krav (sted, pris, m², værelser, overtagelsesdato). Allerede-sete opslag springes
stille over — du får kun besked når der dukker en *ny* lejlighed op, som en email
sendt via din egen Mail.app (kræver at din Hotmail-konto allerede er sat op der).

## Opsætning

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp krav.example.txt krav.txt
```

Ret `krav.txt` til dine egne krav (sted, udelukkede delområder, pris, m², værelser,
overtagelsesdato, hvilke sites, ekstra email-modtagere). Se kommentarerne i filen.

## Kørsel

```bash
.venv/bin/python -m bolig_scraper.cli
```

Nyttige flag:
- `--dry-run` — scraper og filtrerer som normalt, men skriver intet til DB/CSV og sender ingen mail. Brug denne til at teste ændringer i `krav.txt`.
- `--test-notify` — sender én testmail og afslutter, uden at scrape noget. Bekræfter at Mail.app/Hotmail-kontoen virker.
- `--no-notify` — kør normalt (DB/CSV opdateres), men send ingen mail.
- `-v` — vis debug-logging (hver HTTP-request m.m.).
- `--max-pages N` — hvor mange oversigtssider der maks hentes pr. site × sted (default 3).
- `--xlsx sti.xlsx` — hvor den formaterede Excel-oversigt skrives (default `matches.xlsx`).

Før du sætter cron op: kør `--dry-run -v` og tjek at antal fundne/matchede opslag ser fornuftigt ud, og kør `--test-notify` for at bekræfte mailen rent faktisk lander i indbakken.

## Automatisk kørsel med cron

Er allerede sat op via `crontab -e` (installeret og verificeret virkende):

```cron
0 9,12,15 * * * cd /Users/kmeyer/Github/bolig-scraper && .venv/bin/python -m bolig_scraper.cli >> run.log 2>&1
```

Kører kl. 09, 12 og 15 hver dag (ingen kørsel om natten). `run.log` samler output
— ryd den op løbende hvis den vokser sig stor. For at ændre tidspunkterne: kør
`crontab -e` og ret minut/timer-feltet.

Bemærk fra test: første gang cron (i modsætning til en manuel kørsel via Terminal)
fik lov at fjernstyre Mail.app, bad macOS om Automation-tilladelse — det skete kun
den allerførste gang og kørte fuldautomatisk uden prompt ved efterfølgende kørsler.
Hvis en fremtidig mail udebliver, så tjek `run.log` for fejl.

## Hvordan det virker

- `boligzonen.py` og `boligportal.py` henter city-oversigtssider og udtrækker
  opslag (boligportal har al data i et indlejret JSON-blob; boligzonen kræver et
  ekstra kald til detaljesiden for overtagelsesdato, men kun for **nye** opslag).
- `storage.py` holder styr på sete opslag i en lokal sqlite-db (`bolig_scraper.db`),
  så du aldrig får den samme lejlighed to gange.
- `config.py` matcher `sted` mod opslagets adresse-/områdetekst (fx "Aarhus C"),
  ikke kun by-niveau. `udelukket_sted` fravælger opslag hvis en af disse tekster
  optræder i adressen, selvom den også matcher `sted` (fx et navngivet kvarter).
- `notify.py` sender én samlet mail pr. kørsel med alle nye match, via AppleScript
  mod din allerede-loggede-ind Mail.app — ingen adgangskoder gemmes i projektet.
  Sendes altid til standardmodtageren plus evt. `ekstra_email` fra `krav.txt`.
  Aktiverer Finder igen efter afsendelse, så Mail.app ikke bliver hængende som
  forreste app — ellers undertrykker macOS/iOS "ny mail"-notifikationen for den
  synkede kopi (fundet og fixet under test).
- `matches.csv` er en simpel append-only rå-log (alt der nogensinde er matchet).
  `matches.xlsx` gendannes fra hele `matches.csv` hver gang der er nye match — bold
  header, fornuftige kolonnebredder, prisformat, og rigtige klikbare links. Åbn
  `matches.xlsx` i Excel/Numbers for overblikket; brug `matches.csv` hvis du vil
  bearbejde data et andet sted.

## Kendte begrænsninger

- Ingen offentlig API — hvis siderne ændrer deres HTML/JSON-struktur, kan
  parserne knække. Kør `--dry-run -v` jævnligt for at opdage det tidligt.
- `sted` → by-URL-slug er en heuristik (fjerner retningsbogstav som "C"/"Ø",
  translittererer æøå). Virker for Aarhus/Odense/Vejle; tjek loggen for
  "404 for by-slug" hvis du tilføjer et sted der ikke matcher.
- boligportal kan i teorien indføre bot-beskyttelse (Cloudflare); det er ikke
  observeret endnu, men hvis requests begynder at fejle konsekvent er det første
  mistænkte.
- munkebjergpark.dk er én fast ejendom (ikke en by-søgbar portal) — dens bygninger
  identificeres af interne WordPress post-ID'er hardkodet i `munkebjergpark.py`.
  Går et opslagstal til 0 for alle bygninger, mens siden selv viser ledige boliger,
  er IDs sandsynligvis skiftet og skal genfindes via browserens netværksfaner.
