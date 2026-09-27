## Välipalautus 1

- Sovelluksessa voi tallentaa päivän aikana syötyjä annoksia, niiden sisältämiä makroja ja reseptejä.
- Sovellukseen voi kirjautua sisään ja sieltä voi kirjautua ulos.
- Käyttäjä voi lisätä, muokata ja poistaa annoksia.
- Käyttäjä voi lisätä reseptejä annoksiin.
- Kirjautunut käyttäjä näkee tallennetut annokset, makrojen määrän ja suosituksia lähitulevaisuuteen.
- Käyttäjä voi hakea dataa valitsemansa aikajakson perusteella.
- Annosnäkymästä voi lisätä annoksiin raaka-aineita ja makroja.
- Tekoälyä voi hyödyntää reseptisuosituksissa tallennetun datan pohjalta.

## Välipalautus 2

- Käyttäjä voi kirjautua, rekisteröityä ja hallita omaa profiiliaan.
- Etusivulla on haku, jolla voi löytää annoksia nimen, hinnan ja tyypin perusteella.
- Käyttäjä voi lisätä, muokata ja poistaa omia annoksia sekä tarkastella niiden tietoja.
- Aterioiden hinta ja makrot näkyvät helposti käyttöliittymässä.
- Sovellus käyttää SQLite-tietokantaa ja ylläpitää käyttäjäkohtaisia annoksia.
- Profiilisivulla on mahdollista vaihtaa salasana ja poistaa tili.
- Olin ottanut huomioon ensimmäisen välipalautuksen palautteen ja yritän tehdä sovelluksesta kurssin mukaisen.
- Aihe on vielä elävä ja projekti saattaa muuttua reseptipankiksi tulevaisuudessa.
- Repo saattaa vielä sisältää kurssin harjoitusmateriaalin testaamisesta jääneitä lomakkeita ja toimintoja. Nämä siivotaan pois seuraavaan välipalautukseen mennessä.

## Välipalautus 3

Sovellukseen on lisätty syötteiden tarkastaminen ennen tietokantaan lisäämistä. Sovelluksen ulkoasua on muokattu, ja kurssimateriaalin esimerkin mukaan on luotu tiedosto, jota käytetään pohjana jokaisella sivulla. Repoa on siivottu, ja sivupohjilla on nyt paremmat nimet. Validointien pitäisi olla nyt kattavampia. Pylint-työkalu on otettu käyttöön tarkastamaan sovelluksen Python-koodia.

## Kuinka sovellusta testataan toisella koneella

1. Kopioi projekti toiselle koneelle GitHubista tai zip-tiedostona.
2. Voit myös kloonata repon komennolla:
   ```bash
   git clone https://github.com/tomppaaa/Meal_tracker.git
   ```
3. Avaa terminaali projektin juurihakemistoon.
4. Varmista, että Python 3 on asennettu.
5. Asenna tarvittavat riippuvuudet:
   ```bash
   python3 -m pip install flask
   ```
6. Asenna projektin riippuvuudet:
   ```bash
   python3 -m pip install -r requirements.txt
   ```
7. Varmista seuraavat asiat:
   - "init.sql" sijaitsee samassa kansiossa kuin "db.py".
   - "database.db"-tiedostoa ei tarvitse luoda itse. Sovellus suorittaa "init.sql"-tiedoston automaattisesti käynnistyessään ja luo kaikki tietokannan taulut.
8. Tarkasta sovelluksen Python-koodi Pylintillä:
   ```bash
   pylint app.py config.py db.py meals.py users.py
   ```
9. Käynnistä sovellus:
   ```bash
   python3 app.py
   ```
10. Avaa selaimessa osoite http://127.0.0.1:5000
11. Testaa sovellusta:
   - Luo tili ja kirjaudu sisään.
   - Testaa annosten lisäämistä, muokkaamista, poistamista, hakua ja profiilin hallintaa.
12. Jos haluat aloittaa puhtaalla tietokannalla, pysäytä sovellus, poista "database.db" ja käynnistä sovellus uudelleen:
    ```bash
    rm database.db
    python3 app.py
    ```

