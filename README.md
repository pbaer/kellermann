# Kriegstagebuch Wilhelm & Marianne Kellermann 1939–1945

Dieses Repository enthält den Briefwechsel zwischen Wilhelm Kellermann (*02.09.1913) und seiner Frau Marianne, geb. Klingberg (*22.04.1915), während Wilhelms Dienstzeit in der deutschen Wehrmacht im Zweiten Weltkrieg. Wilhelm hat die Feldpostbriefe 1989 als „Kriegstagebuch 1939–1945 eines Stabsgefreiten" zusammengestellt. Marianne ist die Großmutter mütterlicherseits des Projektinhabers; ihre Tochter Helga (*07.05.1940) ist seine Mutter.

| Datei | Inhalt |
|---|---|
| `kriegstagebuch.pdf` | Gescannte Rohvorlage der von Wilhelm 1989 erstellten Zusammenstellung |
| `kriegstagebuch-1939.txt` bis `kriegstagebuch-1945.txt` | OCR-erfasster Text, jahrweise aufgeteilt; textlich getreue Wiedergabe des PDFs |

Die Textdateien sind chronologisch aufgebaut und die Quelle der Wahrheit. Alles unter `data/chapter-XX/letters.jsonl` wird daraus abgeleitet — siehe `parser/README.md` für die Pipeline und für die Schritte nach einer Korrektur an den `.txt`-Dateien (Tippfehler, Zusammenführen oder Aufteilen von Briefen). `data/chapter-XX/chronology.jsonl` ist dagegen handgepflegt und wird nicht regeneriert.

Jeder Brief beginnt mit einer Kopfzeile im Muster:

```
von Wilhelm, <Ort>, den <Datum>
von Marianne, <Ort>, den <Datum>
```

Eingeschobene Passagen in Klammern sind spätere Anmerkungen Wilhelms (1989), die den militärischen Kontext erläutern oder Lücken zwischen den Briefen schließen. Besonders 1942/43 und ab April 1945 fehlen Teile der Korrespondenz – Wilhelm hat die Lücken dort durch erzählende Überleitungen geschlossen. Zeilen, die mit `#####` beginnen, sind Kommentare des Projekts zu unsicheren OCR-Rekonstruktionen und gehören nicht zur Originalquelle. Die Marke `>>>>>` zeigt den Stand der manuellen Korrekturlesung an und wird vom Parser ignoriert.

## Hauptpersonen

**Kernfamilie**
- **Wilhelm Kellermann** – Stabsgefreiter (ab 01.05.1945 Uffz.) in der 8. Batterie/Artillerie-Regiment 256 (später 2./AR 844, schwere 15‑cm‑Haubitzen); Zugmaschinenfahrer, zuletzt Rechnungsführer und Fourier bei einer V‑2‑Raketeneinheit. Kaufmann aus Chemnitz, vor dem Krieg bei der Firma Trompetter & Geck in Stettin ausgebildet.
- **Marianne Kellermann, geb. Klingberg** – lebt während des Krieges in Chemnitz-Glösa, zeitweise auch in der Admiral-Scheer-Straße; schreibt nahezu täglich und nummeriert ihre Briefe.
- **Helga** (*07.05.1940), **Stefan** (*24.02.1943) und **Günter** (*11.08.1944) – die drei Kinder, die während Wilhelms Abwesenheit geboren werden.

**Familie und nähere Verwandte**
- **Arthur Klingberg** – Mariannes Vater, stirbt nach längerer Krankheit am 31.12.1942 an Herzschlag.
- **Heinz Klingberg** – Mariannes Bruder, Panzersoldat (1. Panzerarmee, später bei Guderian). Seine Einsätze in Polen, Frankreich, Russland und Ostpreußen bilden in den Briefen den parallelen roten Faden zu Wilhelms Schicksal – Marianne bangt um beide Männer zugleich; erhält im Februar 1944 das EK.
- **Wolfgang** – Schwager in der Wehrmacht, mit seiner Einheit von Witebsk bis Norditalien im Einsatz, mehrfach im Lazarett (u. a. Padua).

**Engste Kameraden der 2./AR 844**
- **Heinz Auer** (Textilvertreter aus Glauchau) – Wilhelms wichtigster Vertrauter über alle Jahre hinweg; teilt in fast jeder Garnison das Quartier.
- **Herbert Behr** (Altstoffhändler aus Chemnitz) – enger Freund und ständiger Begleiter; über Frau Behr läuft auch ein Teil der Nachrichten zwischen den Familien.
- **Hans Findewirth** (Fleischermeister aus Chemnitz) – Begleiter auf Versorgungs- und Munitionsfahrten, als Koch geschätzt.
- **Alfred Winkler** (Kaufmann aus Berlin) – Gefährte auf Märschen und bei Ausflügen durch die besetzten Länder.

**Vorgesetzte**
- **Hptm. Barthel** – sprunghafter, gefürchteter erster Chef: „Zehnmal wurde etwas befohlen und wieder umgestoßen."
- **Hptm. Baumann** – Batteriechef ab 1940, nach Barthel als spürbare Erleichterung empfunden; am 20.10.1941 schwer verwundet, stirbt später im Heimatlazarett (Todesnachricht erreicht die Truppe im Januar 1942).
- **Oblt. Witzel** – Kompaniechef 1943, dessen Rückkehr aus dem Urlaub in den Briefen als Wendepunkt zu ordentlicher Versorgung und besserem Klima beschrieben wird.
- **Schirrm. Ackermann** (Chemnitz) – zuverlässiger Schirrmeister und Wilhelms Informationsquelle in der Kompanie.

## Kapitelübersicht

Wilhelms Weg lässt sich in sieben Kapitel gliedern. Datumsangaben orientieren sich an den Briefen.

### 1. Einberufung und Sitzkrieg (Juli 1939 – Mai 1940)

Am 18. Juli 1939 wird Wilhelm zur Kurzausbildung bei der 8. Batterie des Artillerie-Regiments 256 in der Chemnitzer Kaserne Planitzstraße einberufen. Mit dem Polenfeldzug rollt seine Batterie Anfang September als dritte Welle aus, kommt aber nur bis Kostelitz bei Königgrätz – ohne einen Schuss abzugeben.

Der Krieg bleibt in dieser ersten Phase abstrakt; die Briefe aus Kostelitz und aus der neuen Garnison in Oggersheim handeln vor allem von Langeweile, Regen und vertagten Urlaubshoffnungen. Über Köln-Wahn und das katholische Westfalen-Dorf Nottuln kommt die Abteilung im Frühjahr 1940 an die niederländische Grenze bei Weseke. Marianne schreibt parallel aus Glösa; im Herbst 1939 teilt sie Wilhelm mit, dass sie schwanger ist.

Beide hoffen in diesen Monaten, dass „Weihnachten doch noch alles vorbei" sei, und jeder Urlaub, der angekündigt und dann wieder verschoben wird, ist in den Briefen eine kleine Enttäuschung mehr. Den Heiligen Abend 1939 verbringt Wilhelm noch in Nottuln; im Januar 1940 (08.–21.01.) bekommt er endlich seinen ersten zweiwöchigen Heimaturlaub nach Chemnitz.

### 2. Westfeldzug und Besatzungszeit in Frankreich (Mai 1940 – Januar 1941)

Am 10. Mai 1940 überschreitet die Batterie bei Elten als Heeresartillerie der 1. Panzerarmee die niederländische Grenze; nach fünf Tagen über Arnheim und Wageningen kapitulieren bei Utrecht die Holländer, wobei die Batterie bis 10 km vor die Stadt vorstößt. Drei Tage vorher, am 7. Mai, ist in Chemnitz die Tochter Helga geboren worden – Wilhelm erfährt es erst während des Vormarsches und kommt während des ganzen Westfeldzuges nicht auf Urlaub.

Es folgen die Flandernschlacht um Dünkirchen, der Durchbruch bei Péronne, eine Parade auf der Place de la Concorde und der Vorstoß über Orléans bis zur Loire bei Angers. Die Briefe aus diesen Wochen sind von den raschen Siegen getragen; Marianne spricht von einer „wundervoll großen ereignisreichen Zeit" und ist stolz, dass Wilhelm dabei ist. Wilhelm selbst schreibt sachlich, bricht aber immer wieder angesichts zerstörter flämischer Städte und französischer Flüchtlinge in ein betroffenes „Das ist das Furchtbare" ein.

Aus der Kampftruppe wird im Sommer eine Besatzung: erst Parthenay und Sillé-le-Guillaume, ab November Küstenschutz in Cherbourg. Im September 1940 bekommt Wilhelm seinen zweiten Heimaturlaub und sieht zum ersten Mal seine vier Monate alte Tochter Helga; am 03. Oktober ist er wieder bei der Batterie in Frankreich. Im Dezember 1940 hört er noch ein Konzert der Dresdner Philharmoniker; Weihnachten selbst wird mit einer Feier in der Baracke begangen, während Marianne mit Helga in Glösa allein bleibt.

### 3. Rumänien, Bulgarien und Balkanfeldzug (Januar – Juni 1941)

Im Januar 1941 geht es per Bahn quer durch Deutschland nach Constanța an der Dobrudscha, wo die Batterie in verlassenen deutschen Siedlerhäusern wartet, ohne zu wissen, wofür. Anfang März führt der Marsch über Silistra und den neblig-kalten Vribiga-Paß (Varbitsa) nach Kotel in Bulgarien – dort werden die Soldaten von der Bevölkerung freundlich empfangen, Zigeunerkapellen spielen auf der Straße, Schülerinnen der Oberklassen sprechen Französisch. Wilhelm schreibt von einer „gewissen Abenteuerstimmung" – jeder in der Batterie wolle dabei sein, wenn es losgehe.

Am 6. April beginnt der Balkanfeldzug; die Abteilung bleibt zunächst auf bulgarischem Boden und überschreitet erst am 11. April die jugoslawische Grenze, kommt aber kaum zum Schuss. Wenige Tage später steht sie an der Donau bei Smederevo, und der Feldzug ist vorbei.

Im Mai Rückverlegung in eine Kaserne in Gleiwitz – nahe genug an Chemnitz, dass Marianne Wilhelm einmal besuchen kann, fern genug, dass der reguläre Urlaub weiter verweigert wird. Anfang Juni rückt die Abteilung in den polnischen Wald aus.

### 4. Ostfeldzug: Vormarsch durch Ukraine und Kaukasus (Juni 1941 – Februar 1943)

Am 22. Juni 1941, um 03:13 Uhr, eröffnet die Artillerie am Bug bei Sokal das Feuer auf die sowjetischen Stellungen. Der Kriegsausbruch trifft Marianne hart – „so bange um Dich ist mir bei all den anderen Feldzügen nicht gewesen", schreibt sie wenige Tage später.

Als Teil der Panzergruppe Kleist – im Sommer 1941 bei der 11. Panzer-Division, der „Gespensterdivision", ab dem 30. September bei der 16. Panzer-Division – rollt die Abteilung in immer schnellerem Tempo durch Galizien und die Ukraine: Dubno, Ostrog, Berditschew, Uman, Kriwoi Rog, über den Dnjepr bei Saporoshje, nach Osten bis vor Rostow. Im Herbst versinkt alles im Schlamm; die Abteilung wird dünner, Fahrzeuge bleiben stecken, Hauptmann Baumann wird am 20. Oktober schwer verwundet und stirbt später im Heimatlazarett. Aus dem geplanten Sommerkrieg wird ein Winter in ukrainischen Bauernhütten mit Läusen, Hunger und russischen Nachtbombern, in dem Wilhelm sich und seine Kameraden als „halbe Russen" beschreibt.

Seine Briefe werden nüchterner und kürzer, ihr Refrain ist das ewige Warten auf das Ende und den Urlaub. Im Februar 1942 wird er zur Erholung nach Stalino abkommandiert, und Anfang Mai, seit Beginn des Russlandfeldzuges ohne Heimaturlaub, fährt er endlich wieder nach Chemnitz. Es folgen Wochen in Görlitz beim Heimatkommando und in Jägerndorf im Sudetenland, wo Marianne ihn mit Helga jeweils besuchen kann, bevor er Ende Juli allein per Bahntransport nach Osten zurückfährt.

Seine Abteilung hat schon ohne ihn am Don angegriffen; er holt sie südlich von Rostow ein. Mit einer bespannten Division zieht die Batterie bei über 30 Grad Hitze ans Kuban, nach Krasnodar und über Krymskaja in Richtung Noworossijsk und Tuapse, wo sie in urwaldartigen Bergen Bunker und Baumsperren beschießt – Gelände, in dem Munition nur noch mit Maultieren nach oben geschafft werden kann. Die Fahrzeuge verschleißen schneller als die Mannschaften; Mitte Oktober bringt ein Motorschaden Wilhelms Zugmaschine per Bahn zurück in die Heereswerkstatt nach Rostow.

Den Winter 1942/43 verbringt Wilhelm in einem ruhigen Quartier bei Eisenbahnern in Rostow, während wenige hundert Kilometer weiter östlich Stalingrad fällt. In dieser Zeit werden die Briefe auf beiden Seiten leiser und schwerer: Marianne fürchtet, Wilhelm sei abgestumpft oder seinen Kameraden näher als ihr und dem Kind; Wilhelm bestätigt, dass alles, was er draußen erlebt habe, ihn „hart und abweisend" gemacht habe, und dass es ihm schwerfalle, Trostworte zu finden. Am 31. Dezember 1942 stirbt sein Schwiegervater Arthur Klingberg.

### 5. Rückzug, Verwundung und Genesung (Februar – Oktober 1943)

Anfang Februar 1943 setzt sich die Werkstatt vor der herannahenden Front aus Rostow ab. Wilhelms Brief vom 8. Februar 1943 aus Stalino – „Seit gestern sind wir unterwegs … aus dem Werk abgefahren" – markiert den Übergang vom Vormarsch zum Rückzug. Über Dnjepropetrowsk, Simferopol und die Krim folgt er seiner Abteilung zum Kuban-Brückenkopf, wo die Truppe am Meer sitzt, Stör und Kaviar isst und wartet. Am 24. Februar 1943 wird sein Sohn Stefan geboren – wie schon der Tod des Schwiegervaters erfährt er es über Umwege, die Post ist längst unzuverlässig geworden.

Am 19. Mai 1943 rutscht auf einem Fahrzeug eine Maschinenpistole vom Ständer; beim Aufschlag löst sich ein Schuß, der Lauf liegt an Wilhelms Oberschenkel, und die Kugel geht ca. 20 cm durch das Bein und bringt ihn aus dem Krieg heraus. Über Temrjuk und Kertsch, per Lazarettschiff, Zug und schließlich Kriegslazarett in Cherson und Winniza wird er zurück ins Reich geschleust. Mitte Juli kommt er zur Genesungskompanie nach Chemnitz, ist dort im Hotel „Krone" einquartiert und verbringt bis Mitte Oktober „dreizehn Sonntage" zu Hause – nach den Zwischenstationen in Görlitz und Jägerndorf im Vorjahr die erste längere Zeit wieder am Heimatort, und in den Briefen Mariannes die erste spürbare Erleichterung seit dem Beginn des Russlandfeldzuges.

Als er im Oktober wieder ausgemustert werden soll, wirbt ihn ein Offizier als Zugmaschinenfahrer für eine neue, streng geheime Einheit an: die V‑2‑Raketentruppe.

### 6. Bei der V‑2‑Raketentruppe – Pommern und Westen (Oktober 1943 – März 1945)

Am 15. Oktober 1943 trifft Wilhelm in Pommern ein – erst Greifswald und Peenemünde, dann Schneidemühl und ab Mitte November das kleine Daber in Hinterpommern, wo die neue Batterie aufgestellt wird. Der Ton der Briefe wird vorsichtiger: Ortsnamen werden getarnt, Post von Frontkameraden wird geöffnet. Wilhelm arbeitet in der Zahlmeisterei, fährt nachts Raketen aus Peenemünde, beobachtet Probestarts auf der Greifswalder Oie und steht einmal als Ehrenposten vor Albert Speer, als dieser den Raketenforschern Orden verleiht.

Beide Briefschreiber setzen in dieser Zeit erkennbar Hoffnung in die neue Waffe – Marianne glaubt, sie werde die Terrorangriffe beenden, und Wilhelm ist stolz darauf, dass seine Einheit „in aller Munde" ist. Marianne besucht ihn mit den Kindern in Daber; der dritte Sohn Günter kommt am 11. August 1944 zur Welt – Wilhelm kann nicht heimfahren und wird wenige Tage später zu einem Übungsschießen nach Peenemünde kommandiert.

Ende Oktober 1944 verlegt die Einheit in die Gegend nördlich von Münster – zurück in jene westfälische Landschaft, in der Wilhelm 1939 als Rekrut gelegen hatte: „der Kreis hat sich geschlossen". Von Feuerstellungen in Feldern, die tagsüber unter alliierten Bomberströmen liegen, gehen die V‑2‑Raketen auf Antwerpen. Zur „Beschaffung" fährt die Zahlmeisterei wiederholt in das evakuierte Arnheim und holt Bettlaken, Ofenrohr und Geschirr; Wilhelm bringt zwei Ölgemälde mit.

Anfang 1945 zieht die Zahlmeisterei in eine Villa im Haager Vorort Scheveningen, von dessen Mole die Raketen auf London starten. Die Stimmung kippt in diesen Monaten spürbar: Marianne schreibt im September 1944, sie sei „2 Tage völlig niedergeschlagen" gewesen und habe sich mit den Kindern schon den Bolschewisten ausgeliefert gesehen, ringt sich danach aber wieder zu Hoffnung durch. Die Briefe an Marianne werden in diesen Wochen von Sorge um Chemnitz dominiert, das die schweren Angriffe vom 14. Februar und 5. März 1945 trifft. Wilhelms letzter Brief aus Holland datiert vom 26. März 1945 und wird per Kurier mitgegeben, als die V‑2‑Division bereits aus dem Land gezogen wird.

### 7. Rückzug, Gefangenschaft und Heimkehr (März – Mai 1945)

Auch in den letzten Briefen aus Holland redet Wilhelm sich und Marianne noch einmal Mut zu: Man dürfe die Ereignisse „nicht nach dem Verlust dieser oder jener Stadt messen", die gerechte Sache werde siegen – zugleich bittet er Marianne, sich zu überlegen, was sie tun würde, wenn wirklich die Russen kämen.

Nach dem britischen Rheinübergang bei Wesel wird die V‑2‑Division in der Nacht zum 24. März 1945 aus Holland gezogen; das schwere Gerät soll in der Lüneburger Heide gesprengt worden sein. An der Elbe bei Lenzen wird die Einheit behelfsmäßig zu einer Haubitz-Batterie umgestellt und gegen die auf Berlin vorstoßende Rote Armee bei Fehrbellin eingesetzt.

Am 1. Mai erfährt die Truppe, dass Hitler tot ist; Wilhelm wird zum Unteroffizier befördert und schlägt sich zum amerikanischen Brückenkopf bei Dömitz durch. Als klar wird, dass der Brückenkopf abends an die Russen übergeben wird, schwimmt er mit Hilfe von Autoschläuchen durch die kalte Elbe. Nach drei Tagen und Nächten ohne Dach und Essen auf einem Sportplatz bei Herford und einer geglückten Flucht aus einem Güterzug bei Krefeld wandert er drei Wochen zu Fuß – über Sauerland, Westerwald, Vogelsberg, Rhön und Thüringer Raum, mit einem kleinen KdF‑Atlas und einem noch kleineren Kompass – quer durch das zerfallene Deutschland.

Am 29. Mai 1945, gegen 20 Uhr, steht er mit verdreckten Füßen wieder vor der Wohnungstür in der Stiftstraße 39 in Chemnitz.
