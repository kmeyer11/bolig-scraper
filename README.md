# bolig-scraper

Scanner boligzonen.dk og boligportal.dk for lejeboliger der matcher dine krav (sted,
pris, m², værelser, overtagelsesdato). Allerede-sete opslag springes stille over —
du får kun besked når der dukker en *ny* lejlighed op, som en email sendt via din
egen Mail.app (kræver at din Hotmail-konto allerede er sat op der).

## Opsætning

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp krav.example.txt krav.txt
```

Ret `krav.txt` til dine egne krav (sted, pris, m², værelser, overtagelsesdato,
hvilke sites). Se kommentarerne i filen.

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

Før du sætter cron op: kør `--dry-run -v` og tjek at antal fundne/matchede opslag ser fornuftigt ud, og kør `--test-notify` for at bekræfte mailen rent faktisk lander i indbakken.

## Automatisk kørsel med cron (3-4 gange dagligt)

Tilføj denne linje via `crontab -e` (juster stien til hvor du har klonet repoet):

```cron
0 8,12,16,20 * * * cd /Users/kmeyer/Github/bolig-scraper && .venv/bin/python -m bolig_scraper.cli >> run.log 2>&1
```

Kører kl. 08, 12, 16 og 20 hver dag. `run.log` samler output — ryd den op løbende
hvis den vokser sig stor. Bemærk: cron kører uafhængigt af om du er logget ind,
men Mail.app skal kunne startes/være tilgængelig på maskinen for at
notifikationen kan sendes (se `notify.py`).

## Hvordan det virker

- `boligzonen.py` og `boligportal.py` henter city-oversigtssider og udtrækker
  opslag (boligportal har al data i et indlejret JSON-blob; boligzonen kræver et
  ekstra kald til detaljesiden for overtagelsesdato, men kun for **nye** opslag).
- `storage.py` holder styr på sete opslag i en lokal sqlite-db (`bolig_scraper.db`),
  så du aldrig får den samme lejlighed to gange.
- `config.py` matcher `sted` mod opslagets adresse-/områdetekst (fx "Aarhus C"),
  ikke kun by-niveau.
- `notify.py` sender én samlet mail pr. kørsel med alle nye match, via AppleScript
  mod din allerede-loggede-ind Mail.app — ingen adgangskoder gemmes i projektet.

## Kendte begrænsninger

- Ingen offentlig API — hvis siderne ændrer deres HTML/JSON-struktur, kan
  parserne knække. Kør `--dry-run -v` jævnligt for at opdage det tidligt.
- `sted` → by-URL-slug er en heuristik (fjerner retningsbogstav som "C"/"Ø",
  translittererer æøå). Virker for Aarhus/Odense/Vejle; tjek loggen for
  "404 for by-slug" hvis du tilføjer et sted der ikke matcher.
- boligportal kan i teorien indføre bot-beskyttelse (Cloudflare); det er ikke
  observeret endnu, men hvis requests begynder at fejle konsekvent er det første
  mistænkte.
