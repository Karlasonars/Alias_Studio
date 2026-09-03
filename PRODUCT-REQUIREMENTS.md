# Alias Studio — Produkta prasību dokumentācija (PRD)

**Versija:** 1.5 · **Datums:** 2026-08-25 · **Statuss:** Vārti un higiēna ieviesti; gatavs pirmajam agentam
**Autors:** produkta komanda · **Bāzes kods:** commit `5369f34` (auditēts 2026-08-22)
**Saistītie dokumenti:** [SPECIFICATION.md](SPECIFICATION.md) (inženiertehniskā atsauce), [README.md](README.md), [VENDORED-LICENSES.md](VENDORED-LICENSES.md)

> **Kā lasīt šo dokumentu.** `SPECIFICATION.md` apraksta, **kā šodien darbojas** tas, kas jau uzbūvēts. Šis dokuments apraksta, **kas produktam jābūt**, lai to varētu izplatīt publiski.
>
> **v1.2 svarīga izmaiņa:** [6. sadaļa](#6-pašreizējā-stāvokļa-audits-kas-trūkst-līdz-izlaišanai) tagad ir revidēta pret **pirmkodu**, nevis pret specifikāciju. Kur specifikācija un kods atšķiras, **kods uzvar**, un atšķirība ir atzīmēta. Vietas, kur v1.1 kļūdījās, ir atstātas redzamas ar audita piezīmēm — nevis klusi pārrakstītas.
>
> Katrai prasībai ir stabils ID (`E4-F03`). Neizmanto numurus atkārtoti — ja prasība atkrīt, atzīmē to kā `ATCELTS` un saglabā ID.

---

## Satura rādītājs

**A daļa — Konteksts un stratēģija**
1. [Kopsavilkums](#1-kopsavilkums)
2. [Produkta vīzija un pozicionējums](#2-produkta-vīzija-un-pozicionējums)
3. [Tirgus un konkurenti](#3-tirgus-un-konkurenti)
4. [Mērķauditorija un personas](#4-mērķauditorija-un-personas)
5. [Lietotāja ceļojumi](#5-lietotāja-ceļojumi)
6. [Pašreizējā stāvokļa audits: kas trūkst līdz izlaišanai](#6-pašreizējā-stāvokļa-audits-kas-trūkst-līdz-izlaišanai)

**B daļa — Produkta prasības**

7. [Prasību sistēma un prioritātes](#7-prasību-sistēma-un-prioritātes)
8. [E1 — Uzstādīšana un pirmā palaišana](#e1--uzstādīšana-un-pirmā-palaišana)
9. [E2 — Bibliotēka, projekti un darba rinda](#e2--bibliotēka-projekti-un-darba-rinda)
10. [E3 — Ievade un avoti](#e3--ievade-un-avoti)
11. [E4 — Momentu atlase un analīze](#e4--momentu-atlase-un-analīze)
12. [E5 — Klipu pārskats un vērtējuma caurspīdīgums](#e5--klipu-pārskats-un-vērtējuma-caurspīdīgums)
13. [E6 — Klipu redaktors](#e6--klipu-redaktors)
14. [E7 — Subtitri, stils un zīmola komplekti](#e7--subtitri-stils-un-zīmola-komplekti)
15. [E8 — Kadrēšana un kompozīcija](#e8--kadrēšana-un-kompozīcija)
16. [E9 — Teksti un metadati](#e9--teksti-un-metadati)
17. [E10 — Eksports un publicēšana](#e10--eksports-un-publicēšana)
18. [E11 — Vērtības cilpa un kalibrācija](#e11--vērtības-cilpa-un-kalibrācija)
19. [E12 — Iestatījumi un profili](#e12--iestatījumi-un-profili)
20. [E13 — Veiktspēja un resursi](#e13--veiktspēja-un-resursi)
21. [E14 — Uzticamība, kļūdas un atbalsts](#e14--uzticamība-kļūdas-un-atbalsts)
22. [E15 — Atjauninājumi, privātums un telemetrija](#e15--atjauninājumi-privātums-un-telemetrija)
23. [E16 — Izplatīšana, licences un kopiena](#e16--izplatīšana-licences-un-kopiena)
24. [E17 — Iepakojuma eksperimenti](#e17--iepakojuma-eksperimenti)

**C daļa — Dizains**

24. [Dizaina principi](#24-dizaina-principi)
25. [Informācijas arhitektūra](#25-informācijas-arhitektūra)
26. [Ekrānu specifikācijas](#26-ekrānu-specifikācijas)
27. [Vizuālā valoda](#27-vizuālā-valoda)
28. [Komponentu bibliotēka](#28-komponentu-bibliotēka)
29. [Kustība un atgriezeniskā saite](#29-kustība-un-atgriezeniskā-saite)
30. [Pieejamība un lokalizācija](#30-pieejamība-un-lokalizācija)

**D daļa — Realizācija**

31. [Tehniskās prasības un arhitektūras izmaiņas](#31-tehniskās-prasības-un-arhitektūras-izmaiņas)
32. [Ne-funkcionālās prasības](#32-ne-funkcionālās-prasības)
33. [Metrikas un panākumu kritēriji](#33-metrikas-un-panākumu-kritēriji)
34. [Izlaišanas plāns](#34-izlaišanas-plāns)
35. [Riski un to mazināšana](#35-riski-un-to-mazināšana)
36. [Atklātie jautājumi](#36-atklātie-jautājumi)
37. [Pielikumi](#37-pielikumi)

---

# A daļa — Konteksts un stratēģija

## 1. Kopsavilkums

### 1.1. Problēma

Operatoram, kas ieraksta garu video regulāri — podkāstu, straumi, interviju, vebināru — katra avota stunda satur ierobežotu daudzumu izmantojamu momentu. Viņa reālā problēma nav "kā izgriezt klipus". Tā ir **cik daudz vērtības viņš izspiež no katras ierakstītās stundas** — un vai nākamnedēļ viņš to dara labāk nekā šonedēļ.

Neviens rīks tirgū uz šo neatbild. Visi apstājas vienā solī par agru.

**Mākoņa rīki** (Opus Clip, Vizard, Submagic, Klap) atrod momentus un uztaisa MP4. Vērtējums ir viens skaitlis bez pamatojuma, un — kritiski — **tas nekad neuzzina, vai bija pareizs.** Klips, kas savāca 400 000 skatījumu, un klips, kas savāca 900, rīkam izskatās vienādi. Nākamnedēļ tas pieņem tos pašus lēmumus.

**Manuāla montāža** dod pilnu kontroli un nulli sistemātiskas mācīšanās. Operators mācās, bet viņa zināšanas paliek galvā, ne rīkā.

Trūkstošais variants: **rīks ar aizvērtu cilpu.** Tas prognozē, kurš moments nostrādās; tu publicē; tas mēra, kas notika; un tā nākamais prognozējums ir labāks — konkrēti **tavai** auditorijai, ne vidējam lietotājam.

### 1.2. Risinājums

Alias Studio ir darbvirsmas lietotne, kas maksimizē klipu vērtību pa divām svirām:

**Svira 1 — atlase.** Kurus momentus no avota vispār vērts pārvērst klipos. Astoņu posmu lokāls konveijers būvē interešu līkni no septiņiem signāliem, un vērtēšana tos sver kopā ar LLM spriedumu. Šodien svari ir nostādīti pēc gaumes. **Mērķis: tie tiek nostādīti pēc tā, kas tavai auditorijai reāli nostrādāja.**

**Svira 2 — iepakojums.** Divi klipi ar identisku saturu un atšķirīgiem nosaukumiem nav vienas vērtības. Nosaukums, hook, vāka kadrs un apraksts ir tas, kas izlemj, vai kāds vispār noskatās. Šodien tie tiek ģenerēti vienreiz un pieņemti. **Mērķis: tie tiek testēti pret reāliem rezultātiem, un rīks iemācās, kas tavā nišā uzvar.**

Abas sviras balstās uz vienu mehānismu — **vērtības cilpu** ([2.7](#27-vērtības-cilpa)) — un uz vienu jau esošu bāzi: `insights/calibration.py`, 908 rindas, lielākais fails konveijerā, kas šodien apkalpo tikai Instagram un ir novietots kā papildinājums. **Tas ir produkta kodols, ne papildinājums.**

Viss pārējais — transkripcija, kadrēšana, subtitri, renderēšana — ir infrastruktūra, kas šo divu sviru darbību padara iespējamu. Tā jau darbojas un nav šī dokumenta galvenā tēma.

### 1.3. Ko šis dokuments prasa

Trīs lietas, secībā pēc svarīguma:

1. **Aizvērt vērtības cilpu.** Prognozēt → publicēt → izmērīt → pārkalibrēt. Bez tā produkts ir vēl viens klipu ģenerators ar melno kasti, un tā vienīgā diferenciācija ir cena. Tas prasa publicēšanu vai vismaz saskaņošanu ([E10](#e10--eksports-un-publicēšana)), trīs platformu metrikas ([E11](#e11--vērtības-cilpa-un-kalibrācija)) un iepakojuma eksperimentus ([E17](#e17--iepakojuma-eksperimenti)).
2. **Padarīt operatora darbplūsmu ātru pie apjoma.** Lietotājs zina, ko dara; viņam nevajag pamācības, viņam vajag mazāk klikšķu uz klipu, darba rindu, kas strādā naktī, un profilus, kas neprasa pārkonfigurēšanu. Ātrums ir vērtības reizinātājs: klips, kas neiznāca, ir vērts nulli.
3. **Padarīt to izplatāmu.** Instalatori, automātiski atjauninājumi, saprotamas kļūdu ziņas un juridiski korekta AGPL izplatīšana. Tas ir priekšnosacījums, ne mērķis.

> **Kas mainījās v1.4.** Iepriekšējās redakcijas 1. punkts bija "padarīt lietotni saprotamu bez dokumentācijas". Pēc [D-16](#374-lēmumu-žurnāls) tas vairs nav galvenais: lietotājs zina, ko dara. Vienkāršība paliek svarīga kā **ātruma**, ne kā **pieejamības** jautājums.

### 1.4. Panākumu definīcija v1.0

| Kritērijs | Mērķis |
|---|---|
| **Klipi, kas pārsniedz lietotāja paša mediānu** | ≥ 30 % pēc 6 nedēļām cilpā (bāze pie nulles kalibrācijas: 50 % pēc definīcijas → mērķis ir noturīga nobīde uz augšu) |
| **Vērtējuma korelācija ar reālo noturību** | ≥ 0,45 pēc 30 saskaņotiem klipiem; ≥ 0,60 pēc 100 |
| **Kalibrācijas pieņemšana** | ≥ 50 % lietotāju, kuriem tā tiek piedāvāta, to pieņem |
| Izmantojamu klipu skaits uz avota stundu | ≥ 6 |
| Laiks no izpildītiem vārtiem līdz pirmajam gatavajam klipam | < 25 min |
| Lietotāji, kas izpilda uzstādīšanas soli ([4.2](#42-ieejas-slieksnis-ir-dizaina-izvēle)) | ≥ 55 % no tiem, kas instalē |
| Lietotāji, kas pabeidz pirmo darbu | ≥ 85 % **no tiem, kas izpildīja vārtus** |
| Klipi, kurus lietotājs eksportē bez rediģēšanas | ≥ 40 % |
| Avārijas uz darbu | < 2 % |
| Vidējais apstrādes laiks 60 min avotam ar GPU | < 12 min |

**Pirmās trīs rindas ir jaunas v1.4 un ir svarīgākās.** Iepriekšējās redakcijas mērīja, vai lietotne strādā. Šīs mēra, vai tā **kļūst gudrāka** — kas pēc [D-16](#374-lēmumu-žurnāls) ir produkta vienīgais iemesls eksistēt. Pārējās paliek kā higiēnas robežas.

**Godīgs brīdinājums par šīm skaitļiem.** Tie ir mērķi, ne prognozes. Neviens no tiem nav pārbaudīts uz reāliem datiem, jo cilpa vēl nav aizvērta un tikai Instagram ir savienots. Pirmais reālais mērījums var parādīt, ka vērtējuma korelācija ar noturību ir 0,2 un nepakustas — tas būtu produkta pamatpieņēmuma atspēkojums, un to labāk uzzināt v1.1, ne v2.0 ([R16](#354-vērtības-cilpas-riski)).

---

## 2. Produkta vīzija un pozicionējums

### 2.1. Vīzijas formulējums

> **Alias Studio izspiež maksimālo vērtību no katras ierakstītās stundas — uz tava datora, par brīvu, un tas mācās no tā, kas tavai auditorijai reāli nostrādāja.**

Trīs vārdi šeit ir izvēlēti apzināti:

- **"vērtību"**, ne "klipus" — klipu skaits ir viegli palielināms un nekam nav vajadzīgs. Nozīme ir tam, cik no tiem kaut ko nopelna.
- **"tavai auditorijai"**, ne "auditorijai" — vidējais lietotājs neeksistē, un rīks, kas optimizē vidējam, nevienam nav optimāls.
- **"mācās"** — tas ir vienīgais vārds, ko konkurenti nevar pateikt, jo viņu cilpa nav aizvērta.

### 2.2. Trīs īpašības, kas nosaka dizainu

Šīs trīs jau ir kodētas produktā un paliek nemainīgas. Katrs jauns lēmums tiek pārbaudīts pret tām.

**1. Viss notiek lokāli.** Mediji nekad neatstāj datoru. Tīkla izsaukumi ir tikai modeļu svaru lejupielāde, izvēles LLM vērtēšanas caurlaide un izvēles atgriezeniskās saites cilpa. Ollama režīms noņem arī LLM izsaukumu.

*Produkta sekas:* nedrīkst ieviest funkciju, kas prasa obligātu kontu vai obligātu mākoņa apstrādi. Katra mākoņa funkcija ir izvēles un skaidri marķēta saskarnē.

**2. Vērtējums ir auditējams.** Klips nekad netiek pasniegts kā kails skaitlis. Tas nes līdzi apakšvērtējumus, to, kuri detektori nostrādāja, un katru pielietoto korekciju.

*Produkta sekas:* katrs skaitlis saskarnē ir noklikšķināms līdz pierādījumam. "89" nav pietiekami; "89, jo šeit trīs reizes smējās un runātājs mainījās divreiz" ir.

*Pārformulēts v1.4:* auditējamība vairs nav tikai caurspīdīguma jautājums — **tā ir kalibrācijas mehānisms.** Lai uzzinātu, *kurš* signāls prognozē tavas auditorijas uzvedību, vērtējumam vispirms jābūt sadalāmam signālos. Melnā kaste nevar mācīties saprotamā veidā; sadalīts vērtējums var. Šī īpašība ir tā, kas padara [2.7](#27-vērtības-cilpa) tehniski iespējamu.

**3. Katrs regulators ir īsts.** Iestatījums, ko konveijers nelasa, tiek uzskatīts par kļūdu, un ir tests, kas krīt, kad vesela iestatījumu grupa paliek nenolasīta.

*Produkta sekas:* nav dekoratīvu pogu, nav "coming soon" plāksnīšu, nav slīdņu, kas neko nedara. Tas attiecas arī uz jaunām funkcijām šajā dokumentā.

### 2.3. Ceturtā īpašība, ko šis dokuments pievieno

**4. Katrs lēmums tiek pārbaudīts pret rezultātu.** Rīks izsaka prognozi, tā tiek publicēta, rezultāts tiek izmērīts, un starpība atgriežas svaros. Prognoze, kas nekad netiek pārbaudīta, ir viedoklis; prognoze, kas tiek, ir modelis.

*Produkta sekas:*
- Katrs vērtējums nes līdzi **prognozi**, ne tikai reitingu — un vēlāk arī to, cik tā bija tālu no patiesības.
- Nekas nemainās automātiski. Rīks piedāvā svaru korekciju ar pierādījumu; lietotājs pieņem vai noraida. Modelis, kas klusi pārkonfigurē sevi, ir tikai jauna melnā kaste.
- Kad datu nepietiek, rīks to **saka**, nevis izliekas. Divi saskaņoti klipi nav kalibrācija.

> **Kas mainījās v1.4 ([D-16](#374-lēmumu-žurnāls)).** Iepriekšējā 4. īpašība bija *"Noklusējumi ir produkts — lietotājs, kurš nekad neatver iestatījumus, saņem 90 %."* Tā tika rakstīta iesācēja auditorijai, kas vairs nav mērķis. Operatoram noklusējumi ir sākumpunkts, ne griesti; viņš atver iestatījumus tāpēc, ka viņam ir iemesls, un rīka darbs ir dot viņam **datus tam iemeslam**, ne pasargāt no izvēles.
>
> Vienkāršība paliek prasība — bet kā **ātruma**, ne pieejamības jautājums ([1.3](#13-ko-šis-dokuments-prasa) 2. punkts). Mazāk klikšķu uz klipu, ne mazāk kontroļu.

### 2.4. Pozicionējuma paziņojums

> **Operatoriem**, kuri regulāri ieraksta garu video, zina, ko dara, un kuriem svarīgs ir rezultāts, ne process — **Alias Studio** ir bezmaksas, atvērtā pirmkoda darbvirsmas rīks, kas maksimizē vērtību no katras ierakstītās stundas pa divām svirām: **atlasi** (kuri momenti kļūst par klipiem) un **iepakojumu** (nosaukums, hook, vāks, apraksts).
>
> Atšķirībā no Opus Clip, Vizard un Submagic, kas atrod momentus un tur apstājas, Alias Studio **aizver cilpu**: tas prognozē, tu publicē, tas izmēra, un nākamais prognozējums ir kalibrēts pret tavu auditoriju. Neviens no tiem neuzzina, vai to vērtējums bija pareizs. Šis uzzina.

**Vienā teikumā, ko konkurents nevar atkārtot:** *rīks, kura vērtējums pēc trim mēnešiem ir labāks nekā pirmajā dienā, jo tas redzēja, kas tev nostrādāja.*

### 2.5. Ko mēs apzināti **nedarām**

Šis saraksts ir tikpat svarīgs kā prasību saraksts. Katrs ieraksts te ir aizsargs pret apjoma izplešanos.

| Neieviešam | Kāpēc |
|---|---|
| Vispārīgu video redaktoru ar daudziem celiņiem | Konkurence ar DaVinci un CapCut ir zaudēta pirms sākuma. Mūsu redaktors ir viena klipa precizēšanai, nevis montāžai no nulles. |
| Ierakstīšanas funkciju | Riverside to dara labi. Mēs pieņemam faila vai saites ievadi. |
| Mākoņa renderēšanu v1.0 | Pārkāpj 1. īpašību un ievieš serveru izmaksas, kuras nav ar ko segt. |
| Obligātu kontu | Pārkāpj 1. īpašību. Konts drīkst eksistēt tikai publicēšanas integrācijām. |
| AI avatārus, balss klonēšanu, teksta-uz-video | Cits produkts. |
| Mobilo lietotni | Konveijers prasa GPU un desmitiem GB. |
| Reāllaika sadarbību | Aģentūrām pietiek ar eksportējamiem profiliem un projektu mapēm ([E12](#e12--iestatījumi-un-profili)). |
| Maksas līmeņus, "pro" funkcijas, licenču atslēgas | Skatīt [2.6](#26-izplatīšanas-modelis-bezmaksas-un-atvērts). |
| Degradētu "bez AI" režīmu | Vērtējums bez LLM nav vērts auditēšanu, un trešais koda ceļš ir uzturēšanas parāds bez ieņēmumiem. Skatīt [4.2](#42-ieejas-slieksnis-ir-dizaina-izvēle) un [D-15](#374-lēmumu-žurnāls). |
| Lietotāju, kurš nevar iegūt API atslēgu vai instalēt Ollama | Leģitīms darbs, ko labi apkalpo mākoņa rīki ar pārlūka cilni. Nav mūsu lietotājs. |
| Automātisku svaru pārkalibrēšanu bez lietotāja apstiprinājuma | Pārkāpj 4. īpašību ([2.3](#23-ceturtā-īpašība-ko-šis-dokuments-pievieno)). Modelis, kas klusi maina sevi, ir jauna melnā kaste. |
| Naudas izsekošanu (RPM, zīmolu darījumi, konversijas) | [D-16](#374-lēmumu-žurnāls): mērām veiktspējas rādītājus, ne eiro. Nauda ir atkarīga no nišas, līguma un platformas; noturība ir godīgāks kopīgais mērs un nāk no API bez manuālas ievades. |
| Vidējam lietotājam optimizētus "labākos" svarus | Vidējais lietotājs neeksistē. Kalibrācija ir personīga pēc definīcijas. |

### 2.6. Izplatīšanas modelis: bezmaksas un atvērts

**Lēmums (D-09): Alias Studio ir un paliek pilnībā bezmaksas.** Nav abonementa, nav vienreizēja pirkuma, nav maksas līmeņu, nav funkciju, kas atvērtas tikai maksātājiem, nav ūdenszīmju un nav apjoma ierobežojumu. Visi saņem visu.

Tas nav tikai cenu lēmums — tas maina produkta prasības piecos konkrētos veidos.

**1. Nav licencēšanas infrastruktūras, ko būvēt.** Nav kontu sistēmas, nav atslēgu validācijas, nav entitlement pārbaužu, nav "atjaunināt uz Pro" ekrānu. Tas ir ievērojams daudzums koda, kas nekad netiek uzrakstīts, un tā ir šī lēmuma lielākā tehniskā priekšrocība. Katra funkcija šajā dokumentā tiek piegādāta visiem lietotājiem vienlaikus.

**2. Vienīgā izmaksu vieta ir izplatīšana.** Pati lietotne neko nemaksā darbināšanā — aprēķinu veic lietotāja dators. Paliek trīs reālas izmaksas, un tās ir jāsedz:

| Izmaksa | Aptuveni gadā | Vai obligāta |
|---|---|---|
| Apple Developer programma (parakstīšana + notarizācija) | ~99 USD | Jā — bez tās macOS Gatekeeper bloķē palaišanu |
| Windows koda parakstīšanas sertifikāts | ~200–400 USD | Praktiski jā — bez tā SmartScreen brīdina katru lietotāju |
| Būves CI (GitHub Actions publiskam repo) | 0 USD | Nē — publiskiem repozitorijiem bez maksas |

**Sekas [E16-F02](#e16--izplatīšana-licences-un-kopiena):** koda parakstīšana paliek `P0`, bet iegūst atkāpšanās ceļu. Ja sertifikāta nav, izlaišana joprojām notiek — ar dokumentētu, saskarnē paskaidrotu apiešanas instrukciju un skaidru brīdinājumu README. Neparakstīta izlaišana ir slikta, bet tā nav izlaišanas bloķētājs bezmaksas projektam.

**3. Ilgtspēja nāk no brīvprātīgiem avotiem.** Bezmaksas projekts bez ieņēmumiem izdzīvo tikai tad, ja uzturēšanas slogs paliek zems. Pieļaujamie atbalsta veidi, kas **nemaina produktu**:

- GitHub Sponsors vai līdzvērtīgs ziedojumu ceļš, saistīts no "Par" ekrāna.
- Kopienas ieguldījums koda, presetu un profilu veidā ([E16-F05](#e16--izplatīšana-licences-un-kopiena)).
- Nekad: reklāmas, telemetrijas monetizācija, partneru saites, saišu īsinātāji, "sponsorēti" preseti.

**4. Kopīga API atslēga netiek piedāvāta (D-10).** Bez ieņēmumiem kopīga Gemini atslēga ir tīra izmaksa bez segšanas avota, plus atbildība par ļaunprātīgu izmantošanu. Tā vietā:

- Gemini atslēgas iegūšana tiek padarīta pēc iespējas gludāka ([E1-F02](#e1--uzstādīšana-un-pirmā-palaišana)): tieša saite, soļu instrukcija, atslēgas validācija pirms pieņemšanas.
- **Ollama tiek pacelts par pilntiesīgu ceļu, nevis atkāpšanās variantu.** Tas ir vienīgais režīms, kas ir bezmaksas *un* neierobežots *un* pilnībā lokāls — tātad tas ir vienīgais režīms, kas pilnībā atbilst produkta solījumam. Tam pienākas tikpat laba onboarding pieredze kā Gemini ceļam, un pēc [D-15](#374-lēmumu-žurnāls) tas ir arī vienīgais ceļš cilvēkam, kurš negrib API atslēgu.
- **Nav trešā, "bez AI" ceļa** ([D-15](#374-lēmumu-žurnāls)). Viens no abiem augstākminētajiem ir obligāts, un tas ir līgums, ne maksa — skatīt [4.2](#42-ieejas-slieksnis-ir-dizaina-izvēle).

**5. Atbalsts ir kopienas, nevis pakalpojums.** Nav SLA, nav atbalsta e-pasta, nav garantēta atbildes laika. Tas jāpasaka skaidri, nevis jāļauj lietotājam to atklāt vilšanās ceļā. Praktiskās sekas: [E14](#e14--uzticamība-kļūdas-un-atbalsts) (kļūdu vārdnīca, diagnostikas pakete, iebūvētā palīdzība) kļūst **svarīgāka**, nevis mazāk svarīga — katra kļūda, ko lietotājs var atrisināt pats, ir kļūda, kas nekļūst par GitHub issue.

**Ko šis lēmums neatrisina.** Bezmaksas nenozīmē bez berzes. Instalācija, ~2,5 GB modeļu un uzstādīšanas solis paliek reālas izmaksas lietotājam — tikai ne naudā ([R14](#355-tirgus-riski)). Cena nav tas, kas mūs atšķir; tā ir tikai viena no lietām, kas nekad nebūs pretarguments.

### 2.7. Vērtības cilpa

Šis ir produkta kodola mehānisms. Viss [B daļā](#b-daļa--produkta-prasības) vai nu apkalpo šo cilpu, vai ir infrastruktūra, kas to padara iespējamu.

```
        ┌────────────────────────────────────────────────┐
        │                                                │
        ▼                                                │
   ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌────────┴──────┐
   │ PROGNOZE│───▶│IEPAKOJUMS───▶│PUBLICĒ- │───▶│   MĒRĪJUMS    │
   │         │    │         │    │  ŠANA   │    │               │
   │ interešu│    │ nosauk. │    │ vai     │    │ noturība      │
   │ līkne + │    │ hook    │    │ manuāla │    │ skatījumi     │
   │ rubrika │    │ vāks    │    │ saskaņo-│    │ iesaiste      │
   │ → 87    │    │ apraksts│    │ šana    │    │               │
   └─────────┘    └─────────┘    └─────────┘    └───────┬───────┘
        ▲              ▲                                 │
        │              │                                 ▼
        │              │                        ┌────────────────┐
        │              └────────────────────────│  KALIBRĀCIJA   │
        └───────────────────────────────────────│                │
                                                │ kurš signāls   │
                                                │ prognozēja?    │
                                                │ kurš nosaukumu │
                                                │ stils uzvarēja?│
                                                └────────────────┘
                                                   ↓ ieteikums
                                              lietotājs pieņem
                                                 vai noraida
```

**Katram posmam ir sava epika:**

| Posms | Epika | Stāvoklis šodien |
|---|---|---|
| Prognoze | [E4](#e4--momentu-atlase-un-analīze), [E5](#e5--klipu-pārskats-un-vērtējuma-caurspīdīgums) | Strādā; svari nostādīti pēc gaumes |
| Iepakojums | [E9](#e9--teksti-un-metadati), [E17](#e17--iepakojuma-eksperimenti) | Ģenerē vienreiz; nekad netiek testēts |
| Publicēšana | [E10](#e10--eksports-un-publicēšana) | Tikai eksports uz disku |
| Mērījums | [E11](#e11--vērtības-cilpa-un-kalibrācija) | Tikai Instagram; nav TikTok, nav YouTube |
| Kalibrācija | [E11-F03](#e11--vērtības-cilpa-un-kalibrācija) | `calibration.py` eksistē (908 rindas), bet cilpa nav aizvērta |

**Kur cilpa šodien pārtrūkst:** starp *iepakojumu* un *mērījumu*. Klips iziet kā fails; kas ar to notiek tālāk, rīks nezina, ja vien lietotājs manuāli nesasaista to ar Instagram Reel. **Tas ir vienīgais svarīgākais tehniskais darbs šajā dokumentā**, un tāpēc [E10-F03](#e10--eksports-un-publicēšana) un [E11-F02](#e11--vērtības-cilpa-un-kalibrācija) pārceļas no v1.1/v1.2 uz **v1.1 kā `P0`**.

**Divi noteikumi, kas regulē cilpu:**

**1. Cilpa nekad negriežas pati.** Kalibrācija ir ieteikums ar pierādījumu, ne automātiska darbība. Lietotājs redz "ieteikums: samazināt `dynamics` svaru no 0,25 uz 0,17 — pamatojums: 34 klipos šis kanāls korelē −0,08 ar noturību" un pieņem vai noraida. Automātiska pārkonfigurēšana pārkāptu 4. īpašību ([2.3](#23-ceturtā-īpašība-ko-šis-dokuments-pievieno)) un padarītu rīku par melno kasti, kas pati sevi maina.

**2. Cilpa saka, kad tā neko nezina.** Zem 15 saskaņotiem klipiem kalibrācija ir troksnis. Rīks to marķē kā nepietiekamu un **nerāda ieteikumus**, nevis rāda vājus ieteikumus ar mazu fontu.

## 3. Tirgus un konkurenti

### 3.1. Ainava 2026. gada vidū

Tirgus ir pilns, bet vienveidīgs: gandrīz visi spēlētāji ir mākoņa SaaS ar ikmēneša abonementu, minūšu vai kredītu kvotu, un pieaugošu funkciju sarakstu ap vienu un to pašu kodolu (transkripcija → LLM atlase → vertikāla pārkadrēšana → animēti subtitri).

| Rīks | Cena (mēn.) | Stiprā puse | Vājā puse |
|---|---|---|---|
| **Opus Clip** | $15–29 | Lielākā lietotāju bāze, nobriedis virality vērtējums, split-screen kopīga kadra runātājiem | Kredītu limiti pie apjoma; API tikai Business līmenī; plānošana aiz Pro |
| **Vizard** | $14.50–29 | REST API jau zemākajā līmenī, 4K, zīmola komplekti, komandu sadarbība | Nosliece uz vienu runātāju; vājš vairāku runātāju atbalsts |
| **Submagic** | $14–60 | Nepārspēta subtitru veidņu bibliotēka, kas atbilst trendiem; krāsas pēc runātāja | Nav split-screen; vāja garā formāta momentu atrašana; subtitru rediģēšana atdalīta no transkripta |
| **Klap** | $23–151 | 50+ valodu subtitri, formāta autodetekcija, noslīpēts 4K | Tikai viens avots; mazāk klipu uz augšupielādi |
| **Descript** | $16–50 | Uz tekstu balstīta precīza montāža; dzēs vārdu — pazūd video | Nav automātiska klipu ģenerēšana; nav natīvas publicēšanas |
| **Riverside** | $15–29 | Ieraksti un griez vienā vietā | Vāja svešu ierakstu analīze |
| **CapCut** | Bezmaksas | Bez maksas, bez ūdenszīmes | Nav AI momentu atrašanas vispār |

### 3.2. Kur ir plaisa

Trīs modeļi atkārtojas visos pārskatos un lietotāju sūdzībās:

**Plaisa A — apjoma sods.** Katrs mākoņa rīks maksā vairāk, jo vairāk strādā. Lietotājam ar 4 stundu podkāstu nedēļā tas ir tiešs sods par produktivitāti. *Lokālai apstrādei šī plaisa neeksistē: robeža ir dators, nevis rēķins.*

**Plaisa B — pēdējā jūdze.** Rīks atrod momentus un uztaisa MP4. Tālāk lietotājs pats atver citu programmu, salabo subtitrus, uzraksta aprakstu, un manuāli augšupielādē trīs platformās. Choppity to sauc par "eksports → CapCut → augšupielāde" cilpu; tas ir vairāku stundu nedēļā zudums. *Šī plaisa mums ir tuvākā uzvara — konveijera izeja jau ir 80 % ceļa.*

**Plaisa C — melnā kaste.** "Virality score: 87" bez pamatojuma. Lietotājs nevar nepiekrist, jo nav, ar ko strīdēties. Kad rīks kļūdās, vienīgā rīcība ir to ignorēt. *Šī plaisa mums jau ir aizvērta arhitektūras līmenī — tā tikai nav pietiekami redzama saskarnē.*

**Plaisa D — geimeru materiāls.** Visi rīki ir būvēti runājošai galvai. Gameplay ar mazu facecam stūrī visos dod klipu, kurā redzama tikai facecam. Alias Studio `gameplay_amount` regulators to jau atrisina daļēji; pilns split-screen to atrisinātu pilnībā ([E8](#e8--kadrēšana-un-kompozīcija)).

**Plaisa E — atvērtā cilpa.** *Šī ir svarīgākā, un v1.4 to izvirza priekšplānā.*

Neviens rīks tirgū neuzzina, vai tā vērtējums bija pareizs. Opus Clip "virality score" ir nostādīts uz vispārīga modeļa un paliek nemainīgs neatkarīgi no tā, kā tavi klipi reāli nostrādāja. Klips ar 400 000 skatījumu un klips ar 900 rīkam izskatās vienādi. Nākamnedēļ tas atkārto to pašu spriedumu.

Sekas operatoram: **rīks nekad nekļūst labāks tieši viņa nišā.** Zināšanas par to, kas viņa auditorijā strādā, uzkrājas viņa galvā, ne rīkā — un tāpēc nav ne pārnesamas, ne mērogojamas, ne pārbaudāmas.

*Kāpēc konkurenti to nedara:* mākoņa SaaS ar simttūkstošiem lietotāju optimizē vidējo modeli — personalizēta kalibrācija katram kontam ir dārga un neuzlabo viņu galveno metriku (abonementu noturību). Lokālam rīkam, kur aprēķins ir bezmaksas un dati jau ir uz lietotāja datora, izmaksu struktūra ir apgriezta. **Tā ir strukturāla priekšrocība, ne funkciju saraksta punkts.**

*Kur mēs stāvam:* `insights/calibration.py` ir 908 rindas un lielākais fails konveijerā — bāze eksistē. Bet tā apkalpo vienu platformu, un cilpa starp iepakojumu un mērījumu ir pārrauta ([2.7](#27-vērtības-cilpa)).

### 3.3. Mūsu atbilde

| Konkurentu pieņēmums | Mūsu izvēle |
|---|---|
| Abonements ar kvotu | Pilnībā bezmaksas; nekādu kvotu, nekādu līmeņu, nekādu ūdenszīmju |
| Augšupielādē mums savu materiālu | Nekas neaizceļo no datora |
| Uzticies vērtējumam | Katrs vērtējums izklājas līdz pierādījumam |
| Eksports ir gala punkts | Publicēšana un rezultātu mērīšana ir gala punkts |
| Runājoša galva ir noklusējums | Kadrējuma regulators un split-screen no podkāsta līdz gameplay |
| Slēgts pirmkods | AGPL-3.0, auditējams, forkojams |
| **Rīks nekad neuzzina, vai kļūdījās** | **Aizvērta vērtības cilpa: prognoze → publicēšana → mērījums → kalibrācija ([2.7](#27-vērtības-cilpa))** |
| Iepakojums tiek ģenerēts vienreiz un pieņemts | Nosaukumi, hooks un vāki tiek testēti pret reāliem rezultātiem ([E17](#e17--iepakojuma-eksperimenti)) |

**Godīgi par mūsu vājajām vietām.** Mēs prasām instalāciju, ~2,5 GB modeļu **un vienu no diviem uzstādīšanas soļiem — Gemini atslēgu vai Ollama** ([4.2](#42-ieejas-slieksnis-ir-dizaina-izvēle)), kur konkurents prasa cilni pārlūkā. Mums nav mobilās versijas. Pirmā palaišana ir lēna. Mūsu subtitru veidņu bibliotēka ir daudzkārt mazāka nekā Submagic. Šīs plaisas ir jāaizver ar dizainu ([E1](#e1--uzstādīšana-un-pirmā-palaišana), [E7](#e7--subtitri-stils-un-zīmola-komplekti)), nevis jāignorē.

---

## 4. Mērķauditorija un personas

**Trīs mērķpersonas un viena apzināti izslēgta.** P1 nosaka noklusējumus, P2 nosaka kadrēšanas un atlases darbu, P3 nosaka apjoma un profilu darbu. P4 (iesācējs bez API atslēgas) ir **ne-mērķis** — skatīt [4.2](#42-ieejas-slieksnis-ir-dizaina-izvēle).

> **Kopīgā iezīme ([D-16](#374-lēmumu-žurnāls)): visas trīs ir operatori, ne hobiji.** Katra no tām jau šodien skatās savas platformas statistiku, zina savu vidējo noturību un spēj pateikt, kurš klips pagājušajā mēnesī nostrādāja vislabāk. Tieši tāpēc vērtības cilpa ([2.7](#27-vērtības-cilpa)) viņiem ir izmantojama: viņiem **ir dati un ir motivācija tos lasīt**. Iesācējam nebūtu ne viena, ne otra, un kalibrācija viņam būtu tukša funkcija.
>
> Praktiskā sekas prasībām: šīm personām nav jāpaskaidro, kas ir noturība vai korelācija. Tām ir jāparāda **skaitlis, kam var uzticēties, un pierādījums zem tā**.

---

### P1 — Anna, podkāstu vadītāja

**Konteksts.** 34 gadi, ieraksta divu personu podkāstu iknedēļas, katrs 70–95 minūtes, Riverside ar diviem celiņiem, ko eksportē kā vienu 1080p failu. Publicē Instagram Reels, TikTok un YouTube Shorts. Ir MacBook Pro M2.

**Darbs, kas jāizdara.** *"Kad esmu pabeigusi ierakstu, es gribu 8–10 klipus, kuros patiešām notiek kaut kas interesants, lai man nebūtu jāpārskatās pašai savs 90 minūšu podkāsts."*

**Ko viņa dara šodien.** Maksā par mākoņa rīku, iegūst 12 klipus, izmet 7, pārtaisa subtitrus CapCut, jo noklusētie neatbilst viņas zīmolam, un raksta aprakstus manuāli.

**Kas viņu sāpina.**
- Rīks izvēlas momentus, kur kāds runā skaļi, nevis kur tiek pateikts kaut kas.
- Subtitri izskatās kā katram citam.
- Klipa robeža pārgriež teikumu uz pusēm.
- Nav veida, kā pateikt rīkam "tādus klipus, kā šis, vairāk".

**Ko viņa sagaida no Alias Studio.**
- Vērtējums, kuram var nepiekrist un redzēt, kāpēc ([E5](#e5--klipu-pārskats-un-vērtējuma-caurspīdīgums)).
- Savs subtitru stils, saglabāts vienreiz un pielietots vienmēr ([E7](#e7--subtitri-stils-un-zīmola-komplekti)).
- Robežas, kas pieķeras teikumiem — jau realizēts.
- Apraksts un hashtagi, kas ir 80 % gatavi ([E9](#e9--teksti-un-metadati)).

**Panākumu mērs.** Ceturtdienas vakars: ieraksts pabeigts 19:00, desmit klipi rindā līdz 20:30, ieplānoti līdz 21:00.

---

### P2 — Roberts, straumētājs

**Konteksts.** 22 gadi, straumē 4–6 stundas dienā, Twitch VOD eksports 1440p. Facecam ir 320×180 apakšējā labajā stūrī. Windows dators ar RTX 4070.

**Darbs, kas jāizdara.** *"Man vajag klipus, kur notika kaut kas, ne kur es kaut ko teicu."*

**Kas viņu sāpina.**
- Katrs rīks pietuvina facecam un nogriež spēli. Klips ir bezjēdzīgs.
- Momentu atlase klausās runā; viņa labākie momenti bieži ir klusi.
- Astoņu stundu VOD sadedzina visu mēneša kvotu vienā piegājienā.

**Ko viņš sagaida.**
- Īsts split-screen: spēle augšā, facecam apakšā, abas dzīvas ([E8-F04](#e8--kadrēšana-un-kompozīcija)).
- Vizuālais/darbības kanāls momentu atlasē — nāves ekrāns, killstreak, straujš kustības pieaugums ([E4-F05](#e4--momentu-atlase-un-analīze)).
- Neierobežots apjoms un rinda, kas strādā, kamēr viņš guļ ([E2](#e2--bibliotēka-projekti-un-darba-rinda)).
- Chat pīķu izmantošana kā signāls, ja pieejams chat log ([E4-F06](#e4--momentu-atlase-un-analīze)).

**Panākumu mērs.** Sešu stundu straume nakti pārstrādāta, no rīta 20 kandidāti, no kuriem viņš 10 minūtēs izvēlas 6.

---

### P3 — Ilze, satura aģentūras redaktore

**Konteksts.** 29 gadi, apkalpo 6 klientus, katram sava vizuālā identitāte. Nedēļā apstrādā 10–15 garus video. Windows darbstacija.

**Darbs, kas jāizdara.** *"Man vajag, lai katra klienta klipi izskatās kā šī klienta klipi, bez tā, ka es katru reizi pārkonfigurēju rīku."*

**Kas viņu sāpina.**
- Katrs klients prasa citu fontu, krāsu, logotipu, CTA. Rīks atceras vienu.
- Nav vietas, kur redzēt visus konkrēta klienta darbus.
- Nevar nodot kolēģim konfigurāciju.
- Klienta apstiprinājuma cikls prasa augšupielādi trešajā vietā.

**Ko viņa sagaida.**
- **Zīmola komplekti**: nosaukts iestatījumu, subtitru stila, logotipa un CTA kopums, pārslēdzams ar vienu klikšķi ([E7-F05](#e7--subtitri-stils-un-zīmola-komplekti)).
- Projekti — darbi, kas grupēti pēc klienta ([E2-F02](#e2--bibliotēka-projekti-un-darba-rinda)).
- Eksportējams profils, ko iedot kolēģim ([E12-F04](#e12--iestatījumi-un-profili)).
- Partijas eksports mapē ar sakārtotiem nosaukumiem ([E10-F02](#e10--eksports-un-publicēšana)).
- Kontaktlapa / apstiprinājuma lapa klientam ([E10-F05](#e10--eksports-un-publicēšana)).

**Panākumu mērs.** Klienta pārslēgšana aizņem vienu klikšķi, un neviens klipa fails neizskatās pēc nepareizā klienta.

---

### ~~P4 — Jānis, iesācējs~~ · **NAV MĒRĶAUDITORIJA** (D-15)

> **Atcelts v1.3.** Šī persona tika izņemta apzināti, nevis aizmirsta. Iemesls ir [4.2](#42-ieejas-slieksnis-ir-dizaina-izvēle): produkts prasa vai nu Gemini API atslēgu, vai instalētu Ollama, un tas ir līgums, ne trūkums. Cilvēks, kurš nevar izpildīt nevienu no abiem, nav lietotājs, kuru mēs apkalpojam.
>
> Personas apraksts saglabāts kā **ne-mērķa robežas definīcija**: 41 gads, uzņēmuma īpašnieks, ieraksta sevi ar telefonu vai Zoom, nezina, kas ir API atslēga, un negrib to uzzināt. Viņa darbs — *"Man vajag, lai šis video kļūst par pieciem klipiem. Nejautā man nekādus jautājumus"* — ir leģitīms darbs; to apkalpo mākoņa rīki ar pārlūka cilni, un tas ir pareizi.
>
> **Ko šī izvēle mums maksā:** zaudējam plašāko tirgus segmentu un nevaram konkurēt uz "vieglāko sākumu". **Ko iegūstam:** nav jāuztur degradēts režīms, kas ražo sliktus klipus un tomēr nes mūsu vārdu, un onboardings drīkst būt godīgs, nevis izlikties, ka rīks ir vienkāršāks, nekā ir.

### 4.2. Ieejas slieksnis ir dizaina izvēle

Alias Studio prasa vienu no diviem, pirms tas kaut ko izdara:

| Ceļš | Ko lietotājam jāizdara | Izmaksas |
|---|---|---|
| **Gemini** | Iegūt bezmaksas API atslēgu aistudio.google.com | ~2 min · bezmaksas līmenis strādā (ar limitiem; Google var izmantot bezmaksas pieprasījumus produktu uzlabošanai) · maksas līmenī ~$1,20 uz stundu avota (T-39: gemini-3.6-flash cenas) |
| **Ollama** | Instalēt Ollama un novilkt modeli | ~10 min · 0 € · pilnībā lokāli |

Tas ir **apzināts vārtu mehānisms**, ne berze, ko vajadzētu novērst. Pamatojums:

**1. Vērtējums bez LLM nav vērts auditēšanu.** Produkta 2. īpašība ([2.2](#22-trīs-īpašības-kas-nosaka-dizainu)) ir, ka vērtējums ir auditējams. Vērtējums, kas balstīts tikai uz audio enerģiju, smiekliem un runātāju maiņām, ir signāls — bet ne spriedums par to, vai moments ir *interesants*. Piegādāt to kā "klipu vērtējumu" būtu tieši tas melnās kastes solījums, ko [Plaisa C](#32-kur-ir-plaisa) nosoda konkurentos.

**2. Degradēts režīms ir uzturēšanas parāds bez ieņēmumiem.** Trešais koda ceļš, kas jātestē, jādokumentē un jāuztur, apmaiņā pret lietotājiem, kuri saņem sliktāko produkta versiju un spriež pēc tās. [R15](#352-tehniskie-riski) padara to par reālu izmaksu.

**3. Abi ceļi ir bezmaksas.** Vārti nav maksas siena. Ollama ceļš ir 0 €, neierobežots un pilnībā lokāls — tas ir vienīgais režīms, kas pilnībā izpilda produkta solījumu ([2.6](#26-izplatīšanas-modelis-bezmaksas-un-atvērts)).

**Sekas dokumentam:** vārti paliek **pirmajā ekrānā**, kā tagad. Nav "apskatīties bez uzstādīšanas" režīma, nav pusceļa stāvokļa, nav koda, kas apstrādā "lietotājs ir iekšā, bet nevar strādāt". Līgums tiek pateikts uzreiz un skaidri.

**Sekas kvalitātei:** ja vārti paliek, tiem jābūt **labiem vārtiem**. Onboardings nedrīkst tikai bloķēt — tam jāved cauri. To nosaka [E1-F02](#e1--uzstādīšana-un-pirmā-palaišana).

### 4.3. Personu ietekme uz prioritātēm

| Prasību joma | P1 Anna | P2 Roberts | P3 Ilze |
|---|---|---|---|
| Zīmola komplekti | **augsti** | vidēji | **kritiski** |
| Split-screen | zemi | **kritiski** | vidēji |
| Vizuālais momentu kanāls | vidēji | **kritiski** | vidēji |
| Darba rinda / partijas | vidēji | **augsti** | **kritiski** |
| Publicēšana / plānošana | **augsti** | vidēji | **augsti** |
| Vērtējuma caurspīdīgums | **augsti** | vidēji | vidēji |
| Vienkāršoti noklusējumi | **augsti** | vidēji | vidēji |
| CPU režīma stabilitāte | vidēji | zemi | zemi |

> **Piezīme par pēdējām divām rindām.** P4 atcelšana **nenozīmē**, ka vienkāršība un CPU atbalsts kļūst nesvarīgi. Anna ir podkāsteris, ne inženieris; viņa spēj iegūt API atslēgu, bet negrib saprast DCASE pēcapstrādi. Ieejas slieksnis filtrē pēc *gatavības uzstādīt vienu lietu*, ne pēc tehniskās izglītības. [24.6](#246-cilvēka-valoda-virsmā-žargons-dziļumā) un [E12-F01](#e12--iestatījumi-un-profili) paliek spēkā pilnā apjomā.

---

## 5. Lietotāja ceļojumi

### 5.1. Ceļojums A — pirmā palaišana (P1 Anna)

Šis ceļojums nosaka, vai lietotne dzīvo vai mirst. Pašlaik tas ir tā vājākā vieta.

*Konteksts pēc [D-15](#374-lēmumu-žurnāls):* Anna spēj iegūt API atslēgu vai instalēt Ollama — tas ir līgums, ko viņa pieņem. Bet viņa to dara **vienu reizi un negrib to atkārtot**, un ja solis 3 viņu apmulsina, viņa aizver lietotni tāpat kā jebkurš cits.

| Solis | Kas notiek šodien | Kas jānotiek |
|---|---|---|
| 1. Lejupielāde | Lokāla būve neražo Windows instalatoru (`bundle.targets` ir tikai `dmg`); CI to ražo ar `--bundles nsis` | Konfigurācija un CI sakrīt; parakstīts `.exe` un notarizēts `.dmg` |
| 2. Palaišana | uv bootstrap lejupielādē Python 3.12 un atkarības klusējot | Redzams "Sagatavo darba vidi", ar soļiem un procentiem |
| 3. **Vārti: smadzenes** | Prasa Gemini atslēgu vai palaistu Ollama; **bloķē**, ja nav ne viena, ne otra | **Vārti paliek** ([4.2](#42-ieejas-slieksnis-ir-dizaina-izvēle)), bet ved cauri: soli pa solim abiem ceļiem, ar pārbaudi un skaidru iemeslu, kāpēc tas vajadzīgs |
| 4. Aparatūras pārbaude | Nav | Parāda: "GPU atrasts: RTX 4070 · 60 min video ≈ 9 min" vai "GPU nav — ≈ 55 min. Turpināt?" |
| 5. Modeļu lejupielāde | Notiek pirmā darba laikā, iekšā progresā | Notiek onboardingā, ar kopējo izmēru (~2,5 GB) un iespēju darīt fonā |
| 6. Pirmais avots | Ievadlauks | Nomešanas zona + paraugvideo poga ("Izmēģini ar mūsu 3 min paraugu") |
| 7. Apstrāde | Posmu progresa joslas ar `fraction` (jau strādā) | Tas pats + ETA un cilvēka valodas posmu nosaukumi |
| 8. Rezultāts | Klipu saraksts | Klipu režģis, augšējais atskaņojas automātiski, "Eksportēt visus" ir redzams |

**Pieņemšanas kritērijs:** persona, kas ir gatava izpildīt 3. soli, nokļūst no instalatora līdz atskaņotam klipam, neizlasot nevienu dokumentāciju ārpus pašas lietotnes un neuzdodot nevienu jautājumu.

**Ko šis kritērijs vairs neietver:** persona, kas 3. solī atsakās. Tas ir sagaidāms rezultāts, ne neveiksme, ko dizains labotu ([D-15](#374-lēmumu-žurnāls)).

---

### 5.2. Ceļojums B — iknedēļas cikls (P1 Anna)

```
Ieraksts gatavs
   │
   ├─▶ Nomet failu Studijā            ~5 s
   │      profils "Mans podkāsts" jau aktīvs
   │
   ├─▶ Apstrāde fonā                   ~11 min (M2, 90 min avots)
   │      Anna aiziet vakariņot; sistēmas paziņojums pēc pabeigšanas
   │
   ├─▶ Pārskats: 12 kandidāti          ~8 min
   │      apskata trīs augstākos, atmet divus ar "Nerādīt līdzīgus"
   │      atzīmē 8 kā "Publicēt"
   │
   ├─▶ Redaktors 2 klipiem             ~6 min
   │      viens: nobīda sākumu par 1,5 s
   │      otrs: izslēdz vienu automātisko klusuma griezumu
   │
   ├─▶ Teksti                          ~4 min
   │      pieņem 6 nosaukumus, pārraksta 2, pieņem visus aprakstus
   │
   └─▶ Eksports                        ~3 min
          "Eksportēt 8 uz ~/Podkāsts/S03E12/", nosaukumi no veidnes
          + kopē aprakstus starpliktuvē pa vienam
```

**Kopā: ~32 minūtes** pret pašreizējām ~75 minūtēm ar mākoņa rīku plus CapCut.

**Kritiskie ceļa punkti:** solis 3 (jāspēj ātri atmest sliktos — tāpēc vajag `Atmest` un `Nerādīt līdzīgus`), un solis 6 (partijas eksports ar nosaukumu veidni ir tas, kas aiztaupa 15 minūtes).

---

### 5.3. Ceļojums C — apjoms (P3 Ilze)

```
Pirmdienas rīts: 11 faili no 6 klientiem
   │
   ├─▶ Bibliotēka → "Jauns projekts: Klients A"
   │      profils "Klients A" piesaistīts projektam
   │
   ├─▶ Ievelk 3 failus vienlaikus → visi rindā
   │      rinda rāda: 3 darbi, aptuvenais kopējais laiks 34 min
   │
   ├─▶ Atkārto 5 klientiem → 11 darbi rindā, kopā ~2 h
   │      dators strādā; Ilze dara citu darbu
   │
   ├─▶ Pēcpusdienā: pārskata katru projektu pēc kārtas
   │      klipi jau nes pareizo zīmola stilu — nekas nav jāpārkonfigurē
   │
   └─▶ Katram projektam: "Eksportēt apstiprinātos" + apstiprinājuma lapa klientam
```

**Kritiskais ceļa punkts:** rinda drīkst nekad neapstāties uz kļūdas. Viens salūzis fails atzīmē to darbu kā neizdevušos un turpina ar nākamo.

---

### 5.4. Ceļojums D — kad kaut kas salūzt

Šis ceļojums ir jāprojektē tikpat rūpīgi kā veiksmes ceļš, jo tas ir tas, kas nosaka, vai lietotājs paliek.

| Situācija | Slikta atbilde | Prasītā atbilde |
|---|---|---|
| yt-dlp neizdodas | "Pipeline exited unexpectedly" | "YouTube atteica lejupielādi. Iespējams, video ir privāts vai ar vecuma ierobežojumu. Mēģini lejupielādēt manuāli un nomest failu." + poga "Atvērt saiti pārlūkā" |
| Nepietiek diska | Python `OSError` | "Trūkst ~14 GB. Darbam vajag ~18 GB, brīvi ir 4 GB." + poga "Atbrīvot vietu" (rāda vecos darbus ar izmēriem) |
| Modeļa lejupielāde pārtrūkst | Klusa neveiksme vai bojāts fails | Automātiska atsākšana ar Range; pēc 3 mēģinājumiem — "Lejupielāde neizdodas. Pārbaudi savienojumu." + manuālas lejupielādes instrukcija |
| GPU nepietiekama atmiņa | CUDA OOM traceback | Automātiska pāreja uz `int8_float16` vai CPU, ar ierakstu žurnālā un nemanāmu paziņojumu |
| LLM atslēga nederīga | 401 no Gemini | "Gemini atslēga netika pieņemta." + poga "Labot atslēgu" + poga "Pārslēgties uz Ollama". Nav "turpināt bez vērtējuma" — tāda režīma nav ([D-15](#374-lēmumu-žurnāls)) |
| Sānvads avarē | Vispārīga kļūda | Posma nosaukums, pēdējās 20 stderr rindas, poga "Kopēt kļūdas atskaiti", poga "Atsākt no šī posma" |

**Princips:** katrai kļūdai ir *cēlonis cilvēka valodā* un *vismaz viena darbība*. Traceback pieejams aiz "Tehniskā informācija", nekad kā primārais teksts.

---

## 6. Pašreizējā stāvokļa audits: kas trūkst līdz izlaišanai

Šī sadaļa ir šī dokumenta pamatojums.

### 6.0. Audita metodika un ticamība

**v1.2 redakcijā šī sadaļa ir pārrakstīta pret pirmkodu**, nevis pret `SPECIFICATION.md`. Auditēts repozitorijs `publikclip` uz commit `5369f34` (2026-08-22), 11 011 rindu Python (bez `vendor/`), 5 284 rindas frontend, 544 rindas Rust.

Audits pārbaudīja katru v1.1 apgalvojumu pret faktisko kodu. Rezultāts: **19 no 26 nepilnībām apstiprinājās, 5 izrādījās nepareizas vai pārspīlētas, 2 izrādījās nopietnākas nekā aprakstīts**, un atradās **7 jaunas problēmas**, kuras specifikācija nepiemin.

**Kas mainījās vissvarīgāk:**

| v1.1 apgalvojums | Realitāte kodā | Sekas |
|---|---|---|
| "Progress ir JSONL konsole" | Strukturēti `progress` notikumi ar `fraction` jau eksistē; `App.tsx` renderē posmu joslas | [E1-F06](#e1--uzstādīšana-un-pirmā-palaišana) samazinās no pārbūves līdz papildinājumam |
| "Katrai kontrolei vajag paskaidrojumu" | Katram laukam **jau ir** `help`; katrai grupai **jau ir** `cost` + `cost_note` | [E12-F01](#e12--iestatījumi-un-profili) samazinās; [E12-F05](#e12--iestatījumi-un-profili) daļēji izpildīts |
| "Bez AI ir pilnvērtīgs ceļš" | **Neeksistē.** `llm_mode` ir tikai `gemini\|ollama` | [E1-F02](#e1--uzstādīšana-un-pirmā-palaišana) aug no UI izmaiņas līdz jaunai konveijera funkcijai |
| "Nav Windows instalatora" | Konfigurācijā tiešām nav, **bet CI būvē NSIS ar `--bundles nsis`** un pārbauda instalāciju | [E16-F01](#e16--izplatīšana-licences-un-kopiena) samazinās; jautājums ir konfigurācijas, ne infrastruktūras |
| "Onboarding prasa atslēgu" | **Sliktāk:** `disabled={!saved && !ollama?.running}` — tas ir ciets bloķētājs | [E1-F02](#e1--uzstādīšana-un-pirmā-palaišana) prioritāte pieaug |
| "Atomāra rakstīšana jāievieš" | `_atomic_write_json()` **jau eksistē**; `edits/store.py:save()` arī | [T10](#312-nepieciešamās-izmaiņas) pārorientējas uz kodējumu |
| "244 testi" | **223 testi** 14 failos | Precizējums |
| "`styles.css` ~3900 rindu" | **1 342 rindas**; `ClipEditor.tsx` ir 1 175 — tas ir īstais gigants | [TD3](#313-tehniskais-parāds-kas-jāatrisina-pa-ceļam) pārorientējas |

### 6.1. Kas jau ir stiprs

Šīs lietas nav jāpārtaisa un ir jāaizsargā no regresijas. Katra apstiprināta pirmkodā:

- **Astoņu posmu kontrolpunktu arhitektūra** ar `artifacts_ok` invalidēšanu un `upstream_stale` kaskādi.
- **Notikumu mugurkauls** — viens audio notikumu laika grafiks, kas apkalpo vērtēšanu, subtitrus, kameru un mūzikas kopsavilkumu. Aprēķināts vienreiz.
- **Smieklu korroborācijas atlaide** — labākais atsevišķais aizsargs pret pārliecinātu kļūdu, un konkurentiem tā nav.
- **Kadrējuma regulators** `gameplay_amount` ar nulles regresijas garantiju pie 0.0.
- **Aparatūras zondēšana, nevis uzticēšanās** — `hardware.py` ar `summary()`, `onnx_providers()`, `cpu_threads()`, `_FLOAT16_VRAM_GB = 3.5`.
- **223 testi**, ieskaitot pret-dreifēšanas testu (`test_settings.py`, 42 testi — lielākais fails).
- **Divu ceļu renderēšanas saskaņotība** starp redaktoru un analizatoru (`test_clip_edit_sync.py`, 23 testi).

**Trīs lietas, kas izrādījās stiprākas, nekā specifikācija liek domāt:**

- **Windows CI ir nopietns.** `.github/workflows/windows.yml` uz tīra `windows-latest` runner: `uv sync`, ffmpeg izšķiršana, **pilna testu komplekta izpilde**, NSIS instalatora būve, klusa instalēšana, instalētās lietotnes palaišana un dzīvības pārbaude pēc 15 sekundēm. Tas ir spēcīgāks izlaišanas vārtsargs, nekā vairumam projektu ir.
- **Iestatījumu shēma jau nes izmaksu modeli.** Katrai no 13 grupām ir `cost` (`cheap` / `moderate` / `high`) un `cost_note`, kas paskaidro, ko maiņa pārrēķinās. Tas ir tieši tas godīgums, ko [24.7](#247-gaidīšana-ir-godīga) prasa — tikai grupas, nevis kontroles līmenī.
- **Onboarding teksts ir labs.** Trīs soļi, godīgs brīdinājums par ~2,5 GB lejupielādi, Gemini izmaksu aplēse (~$0,15 uz stundu avota), skaidrs paziņojums, ka viss pārējais ir lokāls. Problēma nav tekstā — tā ir vienā `disabled` nosacījumā.

### 6.2. Nepilnības pa kategorijām

Statusa kolonna: ✅ apstiprināts kodā · ⚠️ nopietnāks nekā domāts · 🔻 pārspīlēts vai daļēji atrisināts · ❌ nepareizs.

#### Kategorija A — Lietojamība (bloķē P1, sāpina visus)

| # | Nepilnība | Pierādījums kodā | Statuss | Prasība |
|---|---|---|---|---|
| A1 | 72 kontroles vienā panelī, bez hierarhijas | `settings_schema.py`: 13 grupas, 68 punktētas atslēgas + 4 augšlīmeņa; `level` lauka **nav** | ✅ | [E12-F01](#e12--iestatījumi-un-profili) |
| A2 | Nav presetu / profilu | Nav `profiles.json`; `settings.json` ir viens globāls koks | ✅ | [E12-F02](#e12--iestatījumi-un-profili) |
| ~~A3~~ | ~~Onboarding prasa API atslēgu~~ | `Onboarding.tsx:118` — `disabled={!saved && !ollama?.running}`. **Nav nepilnība.** Vārti ir apzināta dizaina izvēle ([4.2](#42-ieejas-slieksnis-ir-dizaina-izvēle), [D-15](#374-lēmumu-žurnāls)). Atlikusī reālā nepilnība ir **A3b** zemāk | **ATCELTS** | — |
| A3b | Ollama ceļš neved cauri, tikai ziņo | Neinstalēts Ollama dod pelēku kartīti ar tekstu "Not detected. Install ollama.com and pull a model" — nav saites, nav soļu, nav `pull` palīdzības, un statuss neatsvaidzinās. Ja vārti paliek, tie nedrīkst būt akli | ✅ | [E1-F02](#e1--uzstādīšana-un-pirmā-palaišana) |
| A4 | Nav paraugvideo | Nav resursa, nav koda ceļa | ✅ | [E1-F05](#e1--uzstādīšana-un-pirmā-palaišana) |
| A5 | Progress ir JSONL konsole | **Nepareizi.** Konveijers izstaro `{event:'progress', stage, fraction, message}`; `App.tsx:96-104` uztur `stages` stāvokli ar `fraction`, un konsole ir atsevišķa. Trūkst tikai ETA, cilvēka nosaukumu un mērītu posmu īpatsvaru | ❌ | [E1-F06](#e1--uzstādīšana-un-pirmā-palaišana) |
| A6 | Nav aparatūras paziņojuma pirms darba | `hardware.summary()` eksistē, bet nekur netiek parādīts onboardingā vai Studijā | ✅ | [E13-F01](#e13--veiktspēja-un-resursi) |
| A7 | Žargons saskarnē | `settings_schema.py` etiķetes ir angliskas un tehniskas; katrai **jau ir `help`**, tāpēc darbs ir pārfrāzēšana, ne rakstīšana no nulles | 🔻 | [C daļa](#c-daļa--dizains) |

#### Kategorija B — Darbplūsma (bloķē P3, sāpina visus)

| # | Nepilnība | Pierādījums kodā | Statuss | Prasība |
|---|---|---|---|---|
| B1 | Nav darba rindas | `jobs` tabulai **jau ir** `status TEXT DEFAULT 'pending'` (pending\|running\|done\|failed) — datu modelis ir. Trūkst Rust puses vadītāja un saskarnes | 🔻 | [E2-F04](#e2--bibliotēka-projekti-un-darba-rinda) |
| B2 | Nav projektu / grupēšanas | `list_jobs(limit=50)` atgriež plakanu sarakstu | ✅ | [E2-F02](#e2--bibliotēka-projekti-un-darba-rinda) |
| B3 | Eksports pa vienam klipam | `export_clip(path, title)` — viens fails uz izsaukumu | ✅ | [E10-F02](#e10--eksports-un-publicēšana) |
| B4 | Nav publicēšanas | Nav publicēšanas moduļa | ✅ | [E10-F03](#e10--eksports-un-publicēšana) |
| B5 | Nav klipa statusa | `ClipEdit` nes nosaukumu, robežas, stilu — bet ne statusu | ✅ | [E5-F04](#e5--klipu-pārskats-un-vērtējuma-caurspīdīgums) |
| B6 | Atgriezeniskā saite tikai Instagram | `insights/` satur tikai `instagram.py` un `calibration.py` (908 rindas — lielākais fails konveijerā) | ✅ | [E11-F02](#e11--vērtības-cilpa-un-kalibrācija) |

#### Kategorija C — Satura kvalitāte (bloķē P2)

| # | Nepilnība | Pierādījums kodā | Statuss | Prasība |
|---|---|---|---|---|
| C1 | Audio/dialoga nosliece; < 20 vārdu kandidāti atmesti | `config.py:122` — `min_words: int = 20`. `CurveWeights` ir 7 kanāli, neviens no tiem nav vizuāls-darbības (`scenes` sver 0.05 un mēra tikai kadru maiņas) | ✅ | [E4-F05](#e4--momentu-atlase-un-analīze) |
| C2 | Nav īsta split-screen | `renderer.py` būvē vienu `crop@c` ceļu | ✅ | [E8-F04](#e8--kadrēšana-un-kompozīcija) |
| C3 | Subtitri var nokļūt letterbox joslā | `ass.py:38-39` — `PLAY_RES_X/Y = 1080/1920` fiksēti; `margin_v` ir konstante presetā (480–560), nesaistīta ar `content_h` | ✅ | [E7-F07](#e7--subtitri-stils-un-zīmola-komplekti) |
| C4 | Nav sejas izmēra veto | `director.py` neizmanto sejas laukumu kā vetoju | ✅ | [E8-F03](#e8--kadrēšana-un-kompozīcija) |
| C5 | Maza subtitru veidņu bibliotēka | **5 iebūvēti preseti**: `classic`, `beast`, `hormozi`, `minimal`, `karaoke`. Submagic tirgo desmitiem | ✅ | [E7-F02](#e7--subtitri-stils-un-zīmola-komplekti) |
| C6 | Nav B-roll automātikas | `edits/visuals.py` (191 rindas) **jau dara** Pexels un Gemini ieteikumus — bet tikai caur CLI `edit suggest-visuals`, nav redaktorā | 🔻 | [E6-F07](#e6--klipu-redaktors) |

#### Kategorija D — Izplatīšanas gatavība (bloķē visu izlaišanu)

| # | Nepilnība | Pierādījums kodā | Statuss | Prasība |
|---|---|---|---|---|
| D1 | Nav Windows instalatora | `tauri.conf.json` tiešām ir `"targets": ["dmg"]`, **bet** `.github/workflows/windows.yml` palaiž `npx tauri build --bundles nsis`, instalē klusi un pārbauda, ka lietotne dzīvo 15 s. Instalators eksistē — tikai ne no lokālas `npx tauri build` komandas | 🔻 | [E16-F01](#e16--izplatīšana-licences-un-kopiena) |
| D2 | Nav koda parakstīšanas | CI augšupielādē neparakstītu `.exe` artefaktu | ✅ | [E16-F02](#e16--izplatīšana-licences-un-kopiena) |
| D3 | Nav automātisko atjauninājumu | `tauri.conf.json` nesatur `plugins.updater` bloku | ✅ | [E15-F01](#e15--atjauninājumi-privātums-un-telemetrija) |
| D4 | macOS mazāk pārbaudīts | `.github/workflows/` satur **tikai** `windows.yml`. macOS ir vienīgais bundle mērķis konfigurācijā un vienīgā platforma **bez** CI — tieši pretēji | ⚠️ | [E16-F04](#e16--izplatīšana-licences-un-kopiena) |
| D5 | Nav privātuma paziņojuma | Nav faila, nav ekrāna | ✅ | [E15-F03](#e15--atjauninājumi-privātums-un-telemetrija) |
| D6 | AGPL avota piedāvājums nav saskarnē | Nav "Par" ekrāna vispār | ✅ | [E16-F03](#e16--izplatīšana-licences-un-kopiena) |
| D7 | Nav avāriju atskaišu | Nav telemetrijas koda | ✅ | [E14-F04](#e14--uzticamība-kļūdas-un-atbalsts) |

#### Kategorija E — Jaunatklātās problēmas (nav specifikācijā)

Šīs neparādās ne `SPECIFICATION.md`, ne v1.1 redakcijā. Katra atrasta pirmkoda auditā.

| # | Problēma | Pierādījums | Prioritāte | Prasība |
|---|---|---|---|---|
| ~~E1~~ | ~~"Bez AI" režīms neeksistē~~ | `config.py:334` — `llm_mode` pieļauj tikai `gemini \| ollama`. **Nav nepilnība.** Degradēts režīms tika apzināti noraidīts ([4.2](#42-ieejas-slieksnis-ir-dizaina-izvēle), [D-15](#374-lēmumu-žurnāls)): vērtējums bez LLM nav vērts auditēšanu, un trešais koda ceļš ir uzturēšanas parāds bez ieņēmumiem | **ATCELTS** | — |
| E2 | **Nav darba atcelšanas** | `main.rs` reģistrē 17 komandas; nevienas `cancel`/`abort`. Sākts darbs iet līdz galam vai avarē | `P0` | [E2-F07](#e2--bibliotēka-projekti-un-darba-rinda) |
| E3 | **34 `read_text()`/`write_text()` izsaukumi bez `encoding="utf-8"`** | Nav vendor kodā, bet gan `edits/store.py:24,32` (klipu redaktora stāvoklis!), `edits/render_clip.py` (8 vietas), `cli.py`, `candidates/stage.py`, `events/stage.py`. Tieši šī kļūdu klase reiz sabojāja `score.json` zem cp1252 — mājas noteikums to aizliedz, bet 34 vietās tas nav ievērots | `P0` | [T10](#312-nepieciešamās-izmaiņas) |
| E4 | **`api.ts` noteikums jau pārkāpts** | 6 tieši `invoke()` izsaukumi ārpus `api.ts`: `ClipEditor.tsx:373,378,382,387` (`save_clip_edits`, `run_edit_render`), `KeyModal.tsx:26,49` (`save_pexels_key`, `save_gemini_key`) | `P1` | [TD2](#313-tehniskais-parāds-kas-jāatrisina-pa-ceļam) |
| E5 | **Diviem valodām ir rakstīšanas tiesības uz `clip_edits.json`** | `edits/store.py` dokstrings: *"The app writes this file directly (Rust fs) and the pipeline reads it at render-clip time"*. Python puses `save()` ir atomāra; Rust puses rakstīšana nav pārbaudīta, un abas var rakstīt vienlaikus | `P1` | [T10](#312-nepieciešamās-izmaiņas) |
| E6 | **Tikai 1 no 6 modeļiem ir sha256-piesaistīts** | `models/specs.py` satur 6 `ModelSpec(...)` un vienu `sha256=`. Pārējie pieci tiek pieņemti bez verifikācijas — tieši tā klusā nogriešanas kļūda, ko `5d0c447` labo PANNs gadījumā | `P1` | [E1-F04](#e1--uzstādīšana-un-pirmā-palaišana) |
| E7 | **Nav `.gitattributes` — rindu beigas ir platformatkarīgas** | *Koriģēts v1.5 pēc tiešas pārbaudes.* Repozitorija **saturs vienmēr ir bijis LF**: 112 izsekotu teksta failu indeksā, nulle ar CRLF. Trūka **deklarācijas**: bez `.gitattributes` un bez `core.autocrlf` Windows darba koks nonāk CRLF, kamēr indekss paliek LF, tāpēc viens un tas pats checkout vienā platformā izskatās tīrs, bet citā — 82 modificēti faili ar 26 550 viltus rindām. Nav repozitorija defekts; ir divdomība, kas maksā tikai tad, kad diffi jāpārskata pa vienam | `P1` | [E16-F07](#e16--izplatīšana-licences-un-kopiena) |

### 6.3. Kopsavilkums

**34 reģistrētas nepilnības, no tām 31 aktīva.** Trīs ir atceltas ar saglabātu ID: **A5** (apgalvojums izrādījās nepareizs — strukturēts progress jau eksistē), **A3** un **E1** (izrādījās nevis nepilnības, bet dizaina izvēles — [D-15](#374-lēmumu-žurnāls)).

Pēc izlaišanas plāna ([37.3](#373-izsekojamība-nepilnība--prasība--versija)) aktīvās sadalās: **13 pirms beta**, **8 pirms v1.0**, **3 v1.1**, **5 v1.2**, **1 nekavējoties** (E7 repozitorija higiēna), **1 pastāvīga**.

**Trīs secinājumi pēc pirmkoda audita un v1.3 dizaina precizējuma:**

> **v1.5 piezīme par audita ticamību.** Nepilnība E7 tika pārbaudīta tieši un izrādījās pārspīlēta ([E16-F07](#e16--izplatīšana-licences-un-kopiena)). Tas ir atgādinājums, ka arī pirmkoda audits var kļūdīties, kad tas nolasa simptomu (82 modificēti faili) un pieņem cēloni. Katrs `⚠️` un `P0` šajā tabulā ir vērts vienu tiešu pārbaudi, pirms uz tā balsta darbu.

**1. Kodols ir labāks, nekā dokuments pieņēma; malas ir sliktākas.** Konveijers, 223 testi, Windows CI ar reālu instalēšanas pārbaudi un iestatījumu shēma ar izmaksu modeli ir nopietns darbs. Bet divas `P0` problēmas, kuras specifikācija nepiemin — **nav darba atcelšanas** un **34 faila operācijas bez UTF-8** — ir tādas, kuras beta lietotājs atradīs pirmajā stundā.

**2. Lielākā daļa "lietojamības nepilnību" ir mazākas, nekā izskatījās.** Trīs no septiņām A kategorijas nepilnībām izrādījās vai nu jau atrisinātas (`help` teksti, strukturēts progress), vai nemaz nebija nepilnības (vārti). Reālais lietojamības darbs koncentrējas divās vietās: **iestatījumu hierarhijā** ([E12-F01](#e12--iestatījumi-un-profili)) un **Ollama uzstādīšanas ceļā** ([E1-F02](#e1--uzstādīšana-un-pirmā-palaišana)).

**3. Sākotnējā diagnoze turas.** Produkta problēma nav modeļu kvalitāte, bet tas, kas notiek pirms un pēc konveijera. No 31 aktīvās nepilnības tikai 5 skar analīzes kvalitāti; pārējās 26 ir onboarding, darbplūsma, izplatīšana un higiēna.

Vissvarīgākais secinājums: **produkta problēma nav modeļu kvalitāte, bet gan tas, kas notiek pirms un pēc konveijera.** Konveijers ir labākā daļa; saskarne ap to ir tā, kas prasa darbu.

---

# B daļa — Produkta prasības

## 7. Prasību sistēma un prioritātes

### 7.1. Prioritāšu skala

| Līmenis | Nozīme | Lēmuma tests |
|---|---|---|
| **P0** | Bloķē v1.0 | Vai lietotne bez tā ir izplatāma svešiniekam? Ja nē — P0. |
| **P1** | Bloķē *labu* v1.0 | Vai lietotājs bez tā izvēlēsies konkurentu? Ja jā — P1. |
| **P2** | v1.1+ | Padara labāku, bet neviens neaiziet bez tā. |
| **P3** | Iespējams nākotnē | Reģistrēts, lai neaizmirstu. Nav ieplānots. |

### 7.2. Prasības formāts

Katra prasība satur:

- **ID** — `E<epika>-F<numurs>`, stabils uz visiem laikiem
- **Prioritāte**, **Persona** (kam tas visvairāk vajadzīgs)
- **Apraksts** — ko tas dara
- **Pieņemšanas kritēriji** — pārbaudāmi apgalvojumi, nevis vēlmes
- **Tehniskās piezīmes** — kur tas skar esošo kodu

### 7.3. Universālie pieņemšanas kritēriji

Šie attiecas uz **katru** prasību šajā dokumentā un netiek atkārtoti:

1. **Nav dekoratīvu kontroļu.** Katra jaunā kontrole lasa un ietekmē reālu konveijera uzvedību. `test_every_settings_group_is_read_by_the_pipeline` paliek zaļš.
2. **Četru vietu likums.** Jauns klipa vai darba iestatījums skar: datu klasi, patērētāju, posma pirkstu nospiedumu, saskarni. Pirkstu nospiedums ir tas, ko aizmirst.
3. **Priekšskatījums un renderis atrisina identiski.** Ja redaktors rāda vienu, bet renderis dod citu — funkcija ir salauzta, pat ja abas puses atsevišķi ir pareizas.
4. **UTF-8 visur, tieši.** Katrs `read_text`/`write_text` uz kontrolpunkta vai iestatījumiem norāda `encoding="utf-8"`.
5. **Zondē, neuzticies.** Aparatūras un formātu atbalsts tiek pārbaudīts izpildlaikā, nevis nolasīts no saraksta.
6. **Katrs ceļš degradējas droši.** Trūkstoša iespēja ir atkāpšanās, nevis kļūda.
7. **Tests, kas krīt.** Katra P0 prasība nes vismaz vienu testu, kas krīt bez tās.

---

## E1 — Uzstādīšana un pirmā palaišana

**Mērķis:** persona bez konteksta nokļūst līdz pirmajam klipam < 25 min, nelasot dokumentāciju.
**Kāpēc svarīgi:** šī ir vienīgā vieta, kur zaudē 100 % lietotāju uzreiz.

---

**E1-F01 · Vienota sagatavošanas plūsma** · `P0` · visi

Aizstāj klusējošo `uv` bootstrap ar redzamu, soļotu sagatavošanas ekrānu, kas darbojas pirmajā palaišanā.

Soļi, katrs ar savu statusu un procentiem:
1. Python vides sagatavošana (uv sync)
2. Aparatūras noteikšana
3. Nepieciešamo modeļu lejupielāde
4. ffmpeg pārbaude

*Pieņemšanas kritēriji:*
- Ekrāns parādās < 3 s pēc lietotnes palaišanas, nekad tukšs logs.
- Katrs solis rāda savu stāvokli: gaida / notiek (%) / pabeigts / neizdevās.
- Neveiksmīgs solis rāda cēloni cilvēka valodā un atkārtošanas pogu, un neļauj plūsmai turpināties klusi.
- Ja process tiek pārtraukts, nākamā palaišana atsāk no pēdējā pabeigtā soļa, nevis no nulles.
- Kopējais lejupielādes apjoms tiek parādīts **pirms** lejupielādes sākuma.

*Tehniskās piezīmes:* prasa, lai Rust slānis pakļautu bootstrap progresu kā Tauri notikumus, ne tikai gaidītu `uv` iziešanu.

---

**E1-F02 · Vārti, kas ved cauri** · `P0` · P1, P2, P3

> **Pārrakstīts v1.3 ([D-15](#374-lēmumu-žurnāls)).** v1.1 un v1.2 uzskatīja `Onboarding.tsx:118` `disabled={!saved && !ollama?.running}` par kļūdu, kas jānoņem, un pieprasīja trešo "bez AI" režīmu. **Abi pieņēmumi ir atsaukti.** Vārti ir dizaina izvēle ([4.2](#42-ieejas-slieksnis-ir-dizaina-izvēle)); `llm_mode` paliek `gemini | ollama`; `disabled` nosacījums paliek.
>
> Prasība tāpēc maina virzienu pilnībā: **no vārtu noņemšanas uz vārtu izmaksu samazināšanu.** Ja lietotnē nevar iekļūt bez uzstādīšanas, tad uzstādīšanai jābūt tik gludai, cik iespējams, un iemeslam — pateiktam uzreiz.

Onboardings prasa vienu no diviem un neļauj turpināt bez tā. Divas izvēles, vienlīdz redzamas:

| Izvēle | Ko tas nozīmē lietotājam | Cik ilgi |
|---|---|---|
| **Ollama (lokāli)** | Bez maksas, bez limitiem, nekas neaizceļo no datora | ~10 min pirmoreiz |
| **Gemini** | Precīzāks humora un vizuālais spriedums (T2 caurlaide) | ~2 min · bezmaksas līmenis ar limitiem · maksas līmenī ~$1,20 uz stundu avota |

*Pieņemšanas kritēriji — iemesls:*
- Pirms izvēles onboardings **vienā teikumā pasaka, kāpēc tas vajadzīgs**: bez modeļa, kas spriež par saturu, vērtējums nav vērtējums. Ne atvainošanās, ne slēpšana — līgums.
- Skaidri pateikts, ka **abi ceļi ir bezmaksas** un ka tas nav maksas siena.
- Skaidri pateikts, ka izvēli var mainīt vēlāk un ka viss pārējais — transkripcija, smiekli, kadrēšana, renderēšana — ir lokāls abos gadījumos. *(Onboarding to jau saka; teksts saglabājams.)*

*Pieņemšanas kritēriji — Ollama ceļš (šis ir tas, kur berze ir lielākā):*
- Nosaka, vai Ollama ir instalēts un palaists. Šodien tas notiek (`check_ollama`), bet neinstalēts Ollama dod tikai pelēku kartīti ar tekstu.
- Ja **nav instalēts**: tieša lejupielādes saite platformai un skaidrs solis pa solim, nevis "Not detected".
- Ja **instalēts, bet nav modeļa**: nosauc ieteicamo modeli un tā izmēru; ja iespējams, palaiž `ollama pull` no lietotnes ar progresu.
- Ja **modelis ir, bet nav piemērots** (tikai embed modeļi): to pasaka atsevišķi, nevis rāda kā gatavu.
- Statuss atsvaidzinās automātiski — lietotājs, kurš instalē Ollama blakus logā, neatgriežas pie sasalušas kartītes.

*Pieņemšanas kritēriji — Gemini ceļš:*
- Tieša saite uz atslēgas iegūšanu plus soļu instrukcija lietotnē (nevis pieņēmums, ka lietotājs zina, kas ir Google AI Studio).
- Atslēga tiek **pārbaudīta ar vienu lētu izsaukumu** pirms pieņemšanas; nederīga atslēga tiek noraidīta uzreiz, ne pirmā darba vidū.
- Izmaksu aplēse redzama pirms atslēgas ievadīšanas. *(Onboarding to jau dara.)*
- Nekur netiek piedāvāta kopīga vai iebūvēta API atslēga ([D-10](#374-lēmumu-žurnāls)).

*Pieņemšanas kritēriji — pēc vārtiem:*
- Izvēli var mainīt jebkurā laikā bez pārstartēšanas.
- Ollama režīmā pārskata ekrāns skaidri norāda, ka T2 vizuālā caurlaide netika izpildīta — kā **trūkstošs ievaddats**, ne kā nulle ([2.2. 2. īpašība](#22-trīs-īpašības-kas-nosaka-dizainu)). Konveijers to jau dara; saskarnei tas jāparāda.

*Kas tiek apzināti **nedarīts**:*
- Nav `llm_mode="none"`. Nav degradēta režīma. Nav "apskatīties bez uzstādīšanas".
- `Onboarding.tsx` `disabled` nosacījums **paliek**.

---

**E1-F03 · Aparatūras profila noteikšana un godīgs paziņojums** · `P0` · visi

Pēc noteikšanas parādīt vienu teikumu par to, ko sagaidīt.

*Pieņemšanas kritēriji:*
- Rāda GPU nosaukumu un VRAM, vai skaidri norāda, ka GPU nav.
- Rāda aplēsi: "60 minūšu video ≈ N minūtes" balstoties uz noteikto profilu.
- Bez GPU rāda brīdinājumu ar reālu skaitli un iespēju turpināt, nevis bloķē.
- Aplēse tiek precizēta pēc pirmā reālā darba (mēra faktisko realtime koeficientu un saglabā).
- Ja `PUBLIKCLIP_DEVICE` piespiež ierīci, saskarne to parāda, lai piespiešana nav neredzama.

*Tehniskās piezīmes:* balstās uz esošo `hardware.py`; jāpievieno noturīga `hardware_profile.json` ar mērīto koeficientu.

---

**E1-F04 · Modeļu pārvaldnieks** · `P1` · P3

Ekrāns, kas rāda katru modeli: nosaukums, ko tas dara cilvēka valodā, izmērs, statuss, darbība.

*Pieņemšanas kritēriji:*
- Rāda kopējo aizņemto vietu un ļauj dzēst atsevišķu modeli.
- Izvēles modeļi (jrgillick smieklu speciālists) skaidri marķēti kā izvēles ar to izmaksu.
- Lejupielādes atsākas ar HTTP Range un tiek pārbaudītas pret piesaistīto sha256.
- **Visi seši modeļi `models/specs.py` iegūst piesaistītu sha256** — pašlaik tikai PANNs kontrolpunktam tāds ir (E6 nepilnība). Pārējie pieci tiek pieņemti neverificēti, kas ir tieši tā klusā nogriešanas kļūda, kuras dēļ PANNs vispār tika piesaistīts.
- Bojāts vai nepilnīgs fails tiek atpazīts un pārlejupielādēts automātiski, nevis izmantots.
- Sagaidāmie izmēri parādīti saskarnē (PANNs kontrolpunkts ir ~312 MB; 514 MB atbilde ir bojātā).
- Kopējais lejupielādes apjoms saskarnē ir **~2,5 GB** — skaitlis, ko onboarding jau nosauc, un tas ir jāsaglabā sinhronizēts ar `specs.py`, nevis jāieraksta cietkodēts tekstā.

---

**E1-F05 · Paraugvideo** · `P1` · P1, P3

Iebūvēts vai pēc pieprasījuma lejupielādējams 3 minūšu paraugs ar zināmu labu rezultātu.

*Pieņemšanas kritēriji:*
- Apstrāde ar paraugu pabeidzas < 4 min pat bez GPU.
- Ražo vismaz 2 klipus, kas demonstrē subtitrus, pārkadrēšanu un vērtējuma izklājumu.
- Pieejams no tukšās Studijas stāvokļa un no palīdzības izvēlnes.
- Paraugs ir brīvi licencēts un tā izcelsme dokumentēta.

---

**E1-F06 · Progresa modelis ar reālu ETA** · `P1` · visi

> **Audita piezīme (v1.2).** v1.1 apgalvoja, ka progress ir neapstrādāta JSONL konsole. **Tas ir nepareizi.** Konveijers jau izstaro `{event:'progress', stage, fraction, message}`, un `App.tsx` uztur `stages` stāvokli ar `fraction` katram posmam. Konsole ir atsevišķa plūsma, ne progresa saskarne.
>
> Tāpēc šī prasība krīt no `P0` uz `P1` un no pārbūves uz papildinājumu: trūkst **ETA**, **cilvēka valodas posmu nosaukumu** un **mērītu posmu īpatsvaru**. Notikumu protokols paliek, kāds ir.

*Pieņemšanas kritēriji:*
- Rāda pašreizējo posmu ar nosaukumu cilvēka valodā ("Atpazīst runu", nevis "asr").
- Rāda posma progresu procentos, kur posms to var ziņot.
- Rāda kopējo atlikušo laiku, balstoties uz mērītiem posmu īpatsvariem un aparatūras profilu; aplēse tiek atsvaidzināta, nevis sasalusi.
- Neapstrādātā konsole paliek pieejama aiz "Sīkāk" un satur stderr pilnībā.
- Progress nekad neapstājas bez teksta paskaidrojuma > 30 s (garie posmi ziņo starpstāvokļus).

*Tehniskās piezīmes:* prasa, lai katrs posms ziņotu `progress` notikumus, ne tikai `stage_start`/`stage_end`. Posmi bez dabīga progresa (LLM partijas) ziņo pabeigto vienību skaitu.

---

**E1-F07 · Diska vietas pārbaude pirms darba** · `P0` · visi

*Pieņemšanas kritēriji:*
- Pirms darba sākuma aplēš nepieciešamo vietu no avota ilguma un izšķirtspējas.
- Ja brīvās vietas trūkst, bloķē sākumu ar konkrētu skaitli ("vajag ~18 GB, brīvi 4 GB") un piedāvā tīrīšanas ekrānu.
- Tīrīšanas ekrāns rāda vecos darbus ar izmēriem un ļauj dzēst starprezultātus, saglabājot gatavos klipus.

---

## E2 — Bibliotēka, projekti un darba rinda

**Mērķis:** lietotne pārvalda daudzus darbus, nevis vienu.
**Kāpēc svarīgi:** P2 un P3 pašlaik nevar to lietot vispār.

---

**E2-F01 · Bibliotēkas ekrāns** · `P0` · P3

Jauns pamatekrāns, kas aizstāj plakano darbu sarakstu.

*Pieņemšanas kritēriji:*
- Rāda katru darbu ar sīktēlu, avota nosaukumu, datumu, klipu skaitu, statusu, aizņemto vietu.
- Meklēšana pēc nosaukuma un filtrēšana pēc statusa un projekta.
- Kārtošana pēc datuma, ilguma, klipu skaita.
- Darbu var pārdēvēt (patlaban tas ir tikai `YYYYMMDD-HHMMSS-<hex>`).
- Darbu var dzēst ar apstiprinājumu, kas nosauc atbrīvojamo vietu.
- Bojāts vai nepilnīgs darbs tiek parādīts ar tā stāvokli, nevis paslēpts.

---

**E2-F02 · Projekti** · `P1` · P3

Nosaukta darbu grupa ar piesaistītu profilu un eksporta mērķi.

*Pieņemšanas kritēriji:*
- Darbu var piešķirt projektam pie izveides vai vēlāk.
- Projekta izvēle pirms darba palaišanas automātiski pielieto tā profilu ([E12-F02](#e12--iestatījumi-un-profili)).
- Projektam ir noklusētā eksporta mape un failu nosaukuma veidne.
- Projekta dzēšana nedzēš darbus; tie kļūst nepiešķirti.
- Projekti glabājas `PUBLIKCLIP_HOME/projects.json` un ir eksportējami.

---

**E2-F03 · Vairāku avotu ievade vienā darbībā** · `P1` · P3

*Pieņemšanas kritēriji:*
- Var nomest vairākus failus vai ielīmēt vairākas saites; katrs kļūst par atsevišķu darbu rindā.
- Var nomest mapi; atpazītie video faili tiek pievienoti, pārējie klusi izlaisti ar kopsavilkumu.
- Pirms apstiprināšanas rāda sarakstu ar aplēsto kopējo laiku un vietu.

---

**E2-F04 · Darba rinda** · `P0` · P2, P3

*Pieņemšanas kritēriji:*
- Rinda izpilda darbus secīgi (viens vienlaikus — GPU ir viena).
- Rindu var pārkārtot ar vilkšanu, apturēt, atsākt; atsevišķu darbu var atcelt.
- Darba neveiksme apturēto darbu marķē un **turpina ar nākamo**; rinda nekad neapstājas pilnībā uz vienas kļūdas.
- Rinda pārdzīvo lietotnes restartēšanu: pēc restarta neizpildītie darbi ir joprojām rindā.
- Rāda kopējo aplēsto laiku līdz rindas beigām.
- Izvēles opcija: "Neļaut datoram aizmigt, kamēr rinda strādā".

*Tehniskās piezīmes (precizētas v1.2):* **datu modelis jau eksistē** — `jobs` tabulai ir `status TEXT NOT NULL DEFAULT 'pending'` ar vērtībām `pending|running|done|failed`, un `create_job()` jaunu darbu ieraksta kā `pending`. Trūkst tikai (a) Rust puses vadītāja, kas palaiž nākamo `pending` darbu pēc iepriekšējā iziešanas, un (b) saskarnes. Tas ir mazāks darbs, nekā v1.1 pieņēma.

---

**E2-F07 · Darba atcelšana** · `P0` · visi

> **Jauna prasība v1.2** (nepilnība E2). `main.rs` reģistrē 17 Tauri komandas; nevienas atcelšanas. Sākts darbs iet līdz galam vai avarē. Apstrādes ekrānā [26.2](#262-apstrādes-skats) **atcelšanas pogas nav vispār** — to vajag uzbūvēt, ne pieslēgt. *(Labojums 2026-08-27: agrāk šeit rakstīja, ka poga eksistē bez aizmugures. `app/src/` nebija ne `cancel`, ne `stop`, ne `abort`. Audita apgalvojums bija nepārbaudīts, un `AGENT-WORKPLAN.md` to mantoja no šejienes — sk. T-07.)*

*Pieņemšanas kritēriji:*
- Jauna Tauri komanda `cancel_job`, kas nogalina sānvada procesu tīri.
- Atcelšana **saglabā kontrolpunktus** — atsākšana no pēdējā pabeigtā posma darbojas ([E14-F02](#e14--uzticamība-kļūdas-un-atbalsts)).
- Nepabeigtie starprezultāti (daļēji uzrakstīts video, pagaidu faili) tiek notīrīti; atomāri rakstītie kontrolpunkti paliek.
- Darbs iegūst statusu `cancelled`, kas ir atšķirams no `failed` bibliotēkā.
- Atcelšana rindā atceļ tikai aktīvo darbu; pārējie turpina ([E2-F04](#e2--bibliotēka-projekti-un-darba-rinda)).
- Atcelšana notiek < 3 s no klikšķa.

---

**E2-F05 · Fona darbs un paziņojumi** · `P1` · P1, P3

*Pieņemšanas kritēriji:*
- Apstrāde turpinās, kad lietotājs pāriet uz citu ekrānu vai minimizē logu.
- Sistēmas paziņojums, kad darbs vai rinda pabeigta; noklikšķināms uz rezultātu.
- Uzdevumjoslas/doka ikona rāda progresu, kur OS to atbalsta.
- Paziņojumus var izslēgt.

---

**E2-F06 · Vietas pārvaldība** · `P1` · visi

*Pieņemšanas kritēriji:*
- Iestatījums: "Dzēst starprezultātus pēc darba pabeigšanas" (audio WAV, CFR kopija, iegultie kadri), saglabājot kontrolpunktus un klipus.
- Bibliotēka rāda katra darba izmēru sadalījumā: mediji / starprezultāti / klipi.
- Brīdinājums, kad `PUBLIKCLIP_HOME` pārsniedz lietotāja noteiktu slieksni.
- Starprezultātu dzēšana korekti atzīmē attiecīgos posmus kā atkārtoti izpildāmus, nevis sabojā atsākšanu.

---

## E3 — Ievade un avoti

**Mērķis:** pieņemt to, kas lietotājam ir, nevis to, kas mums ērti.

---

**E3-F01 · Paplašināts avotu atbalsts** · `P1` · visi

*Pieņemšanas kritēriji:*
- Vietējie faili: mp4, mov, mkv, webm, avi, m4v; audio: mp3, wav, m4a (audio ražo klipus ar statisku vai viļņa fonu).
- Saites: YouTube, Twitch VOD un klipi, Vimeo — caur pārvaldīto yt-dlp.
- Neatbalstīts formāts dod nosauktu kļūdu ar ieteikto darbību, nevis vispārīgu neveiksmi.
- Ļoti gari avoti (> 4 h) tiek pieņemti ar brīdinājumu par laiku un vietu, nevis atteikti.

---

**E3-F02 · Vairāku celiņu un vairāku failu avoti** · `P2` · P1

*Pieņemšanas kritēriji:*
- Var pievienot atsevišķu augstas kvalitātes audio failu, kas aizstāj video audio celiņu analīzei un izejai.
- Var pievienot vairākus sinhronus video celiņus (piem., divi runātāji atsevišķi), kas kļūst par split-screen ievadi ([E8-F04](#e8--kadrēšana-un-kompozīcija)).
- Sinhronizācijas nobīdi var norādīt manuāli, ja automātiskā neizdodas.

---

**E3-F03 · Chat žurnāla ievade** · `P2` · P2

*Pieņemšanas kritēriji:*
- Var pievienot Twitch/YouTube chat eksportu (JSON vai `.txt` ar laika zīmogiem).
- Chat ziņojumu blīvums un emote pīķi kļūst par interešu līknes kanālu ([E4-F06](#e4--momentu-atlase-un-analīze)).
- Bez chat faila kanāls ir nulle un tiek izmests no svērtās summas, nevis velk to lejā (kā jau dara `heatmap`).

---

**E3-F04 · Avota priekšskatīšana pirms apstrādes** · `P2` · visi

*Pieņemšanas kritēriji:*
- Pirms darba sākuma rāda ilgumu, izšķirtspēju, kadru ātrumu, audio kanālus.
- Brīdina par zināmām problēmām: nav audio, mono ar ļoti zemu līmeni, mainīgs kadru ātrums, vertikāls avots (kur pārkadrēšana ir bezjēdzīga).

---

## E4 — Momentu atlase un analīze

**Mērķis:** atrast momentus, kas patiešām ir labi, arī tad, kad neviens nerunā.
**Kāpēc svarīgi:** tā ir produkta kodola vērtība un pašreizējā lielākā satura nepilnība.

---

**E4-F01 · Klipu skaita un garuma vadība saprotamā valodā** · `P0` · P1

*Pieņemšanas kritēriji:*
- Studijā redzamas trīs vienkāršas izvēles: cik klipu (auto / 5 / 10 / 15), garums (< 30 s / 30–60 s / 60–90 s / jaukts), platforma (TikTok / Reels / Shorts / visi).
- Katra izvēle kartējas uz esošajiem `Settings.clips` laukiem un platformas svaru matricu — nekādas jaunas paralēlas loģikas.
- "Auto" nozīmē: skaits izriet no atrasto kvalitatīvo momentu skaita, nevis fiksēts.
- Ja avotā nav pietiekami daudz labu momentu, lietotne to pasaka ("Atradām 6 klipus virs sliekšņa"), nevis piepilda līdz skaitlim ar vājiem.

---

**E4-F02 · Interešu līknes vizualizācija** · `P1` · P1, P2

*Pieņemšanas kritēriji:*
- Pārskata ekrānā redzama avota laika ass ar interešu līkni un atzīmētiem izvēlētajiem logiem.
- Uzvirzoties rāda, kuri kanāli šajā punktā deva ieguldījumu.
- Klikšķis uz līknes atskaņo avotu no tās vietas.
- Kanālus var atsevišķi ieslēgt/izslēgt vizualizācijā, lai lietotājs redz, kas ko dara.

---

**E4-F03 · Manuāla momenta pievienošana** · `P1` · P2, P3

*Pieņemšanas kritēriji:*
- Lietotājs var atzīmēt jebkuru avota diapazonu un pievienot to kā klipu.
- Manuāli pievienots klips iziet pilnu kameras un renderēšanas ceļu, nevis kļūst par otrās šķiras izvadi.
- Manuāls klips ir marķēts pārskatā un netiek pārrakstīts, ja darbs tiek atkārtoti palaists.

---

**E4-F04 · Kandidātu pārskats pirms dārgā posma** · `P2` · P3

*Pieņemšanas kritēriji:*
- Izvēles režīms: pēc `candidates` posma apstāties un parādīt ~35 kandidātus ar to bezmaksas signālu vērtējumiem.
- Lietotājs izvēlas, kuriem tērēt LLM un kameras aprēķinu.
- Šī izvēle tiek ierakstīta kontrolpunktā, tā ka atsākšana to ievēro.
- Noklusējumā izslēgts — parastā darbplūsmā to neredz neviens.

---

**E4-F05 · Vizuālās darbības kanāls** · `P1` · P2

Jauns interešu kanāls, kas nolasa attēlu, nevis skaņu. Aizver Kategorijas C1 nepilnību.

*Pieņemšanas kritēriji:*
- Kanāls mēra kadru starpības enerģiju, ainu maiņas blīvumu un kustības apjomu ar lētu, uz ffmpeg balstītu ceļu (nevis pilnu CV modeli).
- Kanālam ir savs svars `Settings.curve` un tas parādās vizualizācijā.
- Kandidātu logi vairs netiek automātiski atmesti par < 20 vārdiem, ja vizuālās darbības kanāls šajā logā ir spēcīgs.
- Uz gameplay parauga kanāls uzrāda pīķus vietās, kuras cilvēks-vērtētājs marķējis kā darbības momentus (≥ 60 % sakritība mērījuma testā).
- Noklusētais svars ir zems podkāsta profilā un augsts gameplay profilā.

*Tehniskās piezīmes:* jāsader ar esošo `fast_scene_detect` ceļu, lai nedublētu darbu; `curves.json` iegūst jaunu sēriju.

---

**E4-F06 · Chat blīvuma kanāls** · `P2` · P2

*Pieņemšanas kritēriji:*
- Aktīvs tikai tad, kad pievienots chat žurnāls ([E3-F03](#e3--ievade-un-avoti)).
- Mēra ziņojumu likmes pieaugumu pret slīdošu vidējo, nevis absolūto skaitu.
- Emote spami un "LULW/OMEGALUL" klases marķieri tiek svērti atsevišķi.

---

**E4-F07 · Klipa ģimenes un dublikātu novēršana** · `P1` · P1

*Pieņemšanas kritēriji:*
- Kandidāti, kas pārklājas vairāk par slieksni, tiek sagrupēti; rādīts labākais, pārējie pieejami kā "citas šī momenta versijas".
- Alternatīvo versiju izvēle nemaina pārējo klipu vērtējumus.
- "Nerādīt līdzīgus" no viena klipa noņem tā ģimeni no saraksta.

---

**E4-F08 · Iestatījumu profili momentu atlasei** · `P0` · visi

*Pieņemšanas kritēriji:*
- Trīs iebūvēti līknes svaru komplekti: **Podkāsts / saruna**, **Gameplay / straume**, **Prezentācija / vebinārs**.
- Profila izvēle nomaina `Settings.curve`, `Settings.clips` un kameras noklusējumus vienā darbībā.
- Profila izvēle ir redzama Studijā, nevis apslēpta iestatījumos.
- Katrs profils ir pierādīts uz reāla parauga un dokumentēts ar to, kāpēc tā svari atšķiras.
- **Profils ir kalibrācijas sākumpunkts, ne galapunkts** ([2.7](#27-vērtības-cilpa)): iebūvētie svari ir labākais minējums, pirms par lietotāju kaut kas zināms. Kad dati parādās, [E11-F03](#e11--vērtības-cilpa-un-kalibrācija) tos pārraksta.

---

**E4-F09 · Kalibrēta ranžēšana** · `P1` · P1

> **Jauna prasība v1.4** ([D-16](#374-lēmumu-žurnāls)). Šeit atlases svira faktiski nostrādā: vērtējums pārstāj būt rubrikas rezultāts un kļūst par prognozi.

*Pieņemšanas kritēriji:*
- Kad lietotājam ir pieņemta kalibrācija ([E11-F03](#e11--vērtības-cilpa-un-kalibrācija)), kandidātu ranžēšana izmanto **kalibrētos svarus**, ne noklusējuma profilu.
- Kalibrētais vērtējums ir skaidri marķēts saskarnē kā tāds, ar norādi, uz cik klipiem tas balstās.
- Nekalibrēts vērtējums paliek pilnvērtīgs — jauns lietotājs neredz degradētu produktu, tikai nepersonalizētu.
- Kalibrācijas pielietošana ir **jauns darba iestatījums**, kas tiek uzņemts darba momentuzņēmumā; vecs darbs nekad netiek pārranžēts ar jaunākiem svariem ([§6 2. noteikums](#31-tehniskās-prasības-un-arhitektūras-izmaiņas)).
- Ranžēšanas maiņa ir atgriezeniska: lietotājs var salīdzināt "pirms un pēc kalibrācijas" secību uz tā paša darba.
- Kalibrācijas svari ir iekļauti `scoring` posma pirkstu nospiedumā — citādi tie klusi neko nedarītu.

---

## E5 — Klipu pārskats un vērtējuma caurspīdīgums

**Mērķis:** lietotājs 10 minūtēs izlemj par 15 klipiem un saprot, kāpēc katrs ir tur, kur ir.

---

**E5-F01 · Klipu režģis** · `P0` · visi

*Pieņemšanas kritēriji:*
- Vertikāli sīktēli režģī, katrs ar ilgumu, vērtējumu, nosaukumu, statusu.
- Uzvirzīšanās atskaņo klusu priekšskatījumu; klikšķis atver pilnu atskaņotāju.
- Kārtošana pēc vērtējuma, laika avotā, ilguma.
- Filtri: statuss, garums, "ir rediģēts".
- Darbojas ar 30 klipiem bez manāmas aiztures.

---

**E5-F02 · Vērtējuma izklājums** · `P0` · P1

Padara jau esošo provenienci redzamu. Pēc [D-16](#374-lēmumu-žurnāls) tam ir divi uzdevumi: **caurspīdīgums** (lietotājs var nepiekrist) un **kalibrācija** (lietotājs redz, kurš signāls viņu maldināja). Otrais ir jaunais.

*Pieņemšanas kritēriji:*
- Kopvērtējums izklājas apakšvērtējumos ar to svariem un ieguldījumu.
- Rāda, kuri detektori nostrādāja un kad (smiekli 0:12, 0:34; runātāja maiņa 0:21).
- Rāda katru pielietoto korekciju ar iemeslu — īpaši humora korroborācijas atlaidi ("LLM vērtēja humoru 8/10; smiekli netika atklāti → −40 %").
- Ja režīms ir Ollama vai "Bez AI", trūkstošie ieguldījumi ir marķēti kā **trūkstoši**, nevis kā nulle.
- Katrs laika zīmogs izklājumā ir noklikšķināms un pārlec uz to vietu klipā.
- **Ja lietotājam ir kalibrācija**, katrs kanāls rāda arī savu personīgo prognozējošo spēku: *"`dynamics` — tavā vēsturē korelē −0,08"*. Tas ir tas, kas pārvērš izklājumu no paskaidrojuma par rīku.
- **Ja klips ir publicēts un izmērīts**, izklājums iegūst otro kolonnu ar reālo rezultātu ([E11-F05](#e11--vērtības-cilpa-un-kalibrācija)).

---

**E5-F03 · Klipa pilnais skats** · `P0` · visi

*Pieņemšanas kritēriji:*
- Atskaņotājs ar 9:16 priekšskatījumu, transkriptu blakus, sinhronizētu ar atskaņošanu.
- Redzams nosaukums, apraksts, hashtagi, hooks; katrs rediģējams uz vietas.
- Pogas: Apstiprināt, Atmest, Rediģēt, Eksportēt, Ģenerēt no jauna.
- Klaviatūras navigācija starp klipiem (`J`/`K` vai bultas).

---

**E5-F04 · Klipa statuss** · `P0` · P3

*Pieņemšanas kritēriji:*
- Katram klipam ir statuss: **Jauns / Apstiprināts / Atmests / Eksportēts / Publicēts**.
- Statuss glabājas darba direktorijā un pārdzīvo lietotnes restartu un darba atsākšanu.
- Partijas darbības: apstiprināt visus virs vērtējuma sliekšņa; atmest visus zem.
- Atmesti klipi pēc noklusējuma paslēpti, bet atgūstami.

---

**E5-F05 · Restilizācija bez atkārtotas analīzes** · `P1` · P1

*Pieņemšanas kritēriji:*
- Subtitru stila vai zīmola komplekta maiņa atkārtoti renderē tikai `render` posmu.
- Skaidri parādīts, ko maiņa pārrenderēs un cik ilgi tas prasīs, **pirms** apstiprināšanas.
- Klipi ar strukturālām izmaiņām tiek atzīmēti kā aizsargāti un netiek pārrakstīti; saskarne to nosauc, nevis klusē.
- Pirkstu nospiedumu loģika paliek tāda, kā aprakstīts specifikācijas §5 — bez izņēmumiem.

---

**E5-F06 · Salīdzinājums pirms/pēc** · `P2` · P1

*Pieņemšanas kritēriji:*
- Pārslēdzams skats, kas rāda oriģinālo kadrējumu blakus pārkadrētajam.
- Palīdz saprast, ko kadrēšana faktiski nogrieza.

---

## E6 — Klipu redaktors

**Mērķis:** salabot to vienu lietu, kas nav kārtībā, 60 sekundēs. Nevis montēt no nulles.

---

**E6-F01 · Vienota laika ass** · `P0` · P1

Pārbūvēta laika ass, kas vienā vietā rāda visu, kas klipā notiek.

*Pieņemšanas kritēriji:*
- Slāņi: audio viļņa forma, transkripta vārdi, atklātie notikumi, klusuma griezumi, punch-in, pārklājumi.
- Sākuma un beigu rokturi ar pieķeršanos teikumu robežām, ko var atslēgt ar modifikatora taustiņu.
- Katrs automātiski atklātais klusuma griezums ir atsevišķi pārslēdzams tieši uz laika ass.
- Tālummaiņa un ritināšana; klaviatūras kadru soļošana (`,` / `.`).
- Vilkšana atjaunina lokālo stāvokli nepārtraukti un saglabā **vienreiz** pie atlaišanas — kā jau nosaka mājas noteikumi.

---

**E6-F02 · Dzīvs priekšskatījums** · `P0` · visi

*Pieņemšanas kritēriji:*
- Priekšskatījums rāda kadrējumu, subtitrus un pārklājumus tā, kā tie parādīsies izvadē.
- Priekšskatījuma un renderēšanas skaitļi tiek atrisināti caur vienu un to pašu kodu (`resolve_pacing()` modelis paplašināts uz kadrējumu un subtitriem).
- Ir automātisks tests, kas salīdzina priekšskatījuma atrisinātās vērtības ar renderētajām un krīt, ja tās atšķiras.
- Priekšskatījums atsvaidzinās < 300 ms pēc iestatījuma maiņas.

---

**E6-F03 · Klusuma un tempa vadība** · `P1` · P1

*Pieņemšanas kritēriji:*
- Viens slīdnis "Temps": Bez izmaiņām → Maigs → Ciešs → Agresīvs, kartēts uz `PacingSettings`.
- Rāda, cik sekundes tiks izgrieztas un kāds būs gala ilgums, pirms pielietošanas.
- Atsevišķu griezumu var izslēgt uz laika ass, un skaitļi uzreiz atjaunojas.
- Aizsargātie notikumi (smiekli, elpa) netiek grieztas neatkarīgi no agresivitātes.

---

**E6-F04 · Subtitru rediģēšana uz vietas** · `P0` · P1

*Pieņemšanas kritēriji:*
- Transkripta vārdu var labot; labojums nonāk ASS failā un renderī.
- Vārdu grupēšanu rindās var mainīt (cik vārdu vienlaikus).
- Atsevišķu vārdu var izcelt (krāsa/izmērs) neatkarīgi no preseta.
- Laika zīmogu var manuāli nobīdīt, ja izlīdzināšana kļūdījās.
- Labojumi glabājas `clip_edits.json` un pārdzīvo restilizāciju.

---

**E6-F05 · Kadrējuma manuālā vadība** · `P1` · P2

*Pieņemšanas kritēriji:*
- Kadrējuma režīmu (`cut`/`pan`/`locked`) un `gameplay_amount` var mainīt vienam klipam ar dzīvu priekšskatījumu.
- Var manuāli pievienot fiksētu kadra pozīciju konkrētam laika diapazonam, kas pārraksta automātisko trajektoriju.
- Manuāls pārraksts tiek respektēts atkārtotā renderēšanā un ir marķēts uz laika ass.
- Salīdzinājums pret ceptajā trajektorijā esošo notiek tā, kā apraksta specifikācijas §7 3. mehānisms — nesalīdzina pret darba regulatoru.

---

**E6-F06 · Audio vadība** · `P2` · P1

*Pieņemšanas kritēriji:*
- Vienkāršota skaļuma izvēle: "Platformas standarts" / "Skaļāks" / "Pielāgots (LUFS)". Žargons tikai trešajā.
- Iespēja pievienot fona mūziku no vietējā faila ar automātisku ducking zem runas.
- Mūzikas kopsavilkums, ko konveijers jau ģenerē, tiek parādīts kā ieteikums, nevis paslēpts.

---

**E6-F07 · Pārklājumi un B-roll** · `P2` · P1, P3

*Pieņemšanas kritēriji:*
- Attēlu un video pārklājumus var novietot uz laika ass ar pozīciju, izmēru, ilgumu, ieejas/izejas efektu.
- Pexels meklēšana un LLM ieteikumi (jau esoši CLI līmenī) ir pieejami no redaktora.
- Logotipa pārklājums no zīmola komplekta tiek pielietots automātiski, ja komplektā tāds ir.
- Pārklājumu var piesaistīt vārdam transkriptā, nevis tikai absolūtam laikam.

---

**E6-F08 · Atsaukšana un versijas** · `P1` · visi

*Pieņemšanas kritēriji:*
- Atsaukt/atcelt atsaukšanu darbojas visām redaktora darbībām, vismaz 20 soļu dziļumā.
- "Atgriezt sākotnējo" atjauno klipu tā automātiskajā stāvoklī ar apstiprinājumu.
- Renderētās versijas tiek saglabātas ar laika zīmogu; iepriekšējo var atgūt, kamēr darbs nav dzēsts.

---

**E6-F09 · Kadra malu aizpildījums izvēlams pirms darba sākuma** · `P1` · visi

> **Jauna prasība** (nepilnība E6, atrasta testēšanā). `camera.letterbox_fill`
> eksistē kopš pirmās versijas ar noklusējumu `"black"`, un abi renderēšanas
> ceļi to jau atrisina pareizi. Bet tas dzīvo ⚙ Iestatījumos, kur neviens to
> nemeklē pirms darba, un studijas panelī — tajā, uz kura lietotājs skatās
> pirms CUT IT — tā nav. Rezultāts: lietotājs izvēlas gameplay kadrējumu,
> sagaida darbu, un pēc tam pārrenderē **katru klipu atsevišķi**, lai uzliktu
> izplūdinātās malas. Prasība nav pievienot iestatījumu — tā ir novietot
> esošo tur, kur lēmums tiek pieņemts.
>
> *Trešais gadījums, kad "trūkstoša funkcija" izrādījās nosūtīta funkcija bez
> sasniedzama ceļa — sk. arī `hardware.summary()` bez izsaucēja un
> `jobs.pending` bez lasītāja.*

*Pieņemšanas kritēriji:*
- Studijas panelī ir grupa **malas: melnas | izplūdinātas**, kas parādās tikai pie gameplay kadrējuma — pie podcast izgriezums ir tieši 9:16, joslu nav, un tukša vadīkla būtu §5.2 pārkāpums.
- Izvēle iet pa to pašu ķēdi, ko pārējās paneļa vadīklas, ar karogu uz `run`, `resume` un `jobs create`, lai rindā ielikšana nevar atšķirties no palaišanas.
- Darba līmeņa vērtība ir **noklusējums, ne aizvietotājs**: klips bez skaidri uzstādītas vērtības to manto; klips, kuram lietotājs redaktorā vērtību ir uzstādījis, to patur arī tad, kad noklusējums mainās — arī tad, ja uzstādītā vērtība sakrīt ar veco noklusējumu.
- Aizpildījuma maiņa **nepārdzen kameras posmu**. Tā ir tikai renderēšanas vērtība, un līdz šim tās maiņa maksāja minūtes ASD darba par kaut ko, ko `camera/` nemaz nelasa.
- Renderēšanas kontrolpunkts noveco tikai tad, ja noklusējums tiešām attiecas vismaz uz vienu klipu. Darbs, kura visiem klipiem aizpildījums ir uzstādīts skaidri, netiek pārrenderēts.
- Esošie kontrolpunkti uz diska paliek derīgi — funkcijas ierašanās viena pati nedrīkst likt pārrēķināt nevienu jau pabeigtu darbu.

---

## E7 — Subtitri, stils un zīmola komplekti

**Mērķis:** klips izskatās pēc lietotāja zīmola, nevis pēc mūsu noklusējuma.
**Kāpēc svarīgi:** tā ir Submagic vienīgā, bet ļoti spēcīgā, priekšrocība.

---

**E7-F01 · Subtitru priekšskatījums reāllaikā** · `P0` · P1

*Pieņemšanas kritēriji:*
- Stila maiņa parādās priekšskatījumā < 300 ms, bez pilnas pārrenderēšanas.
- Priekšskatījums izmanto to pašu fontu un izkārtojumu, ko ASS renderis.
- Ja fontam trūkst rakstzīmju vai emoji, tas tiek noteikts zondējot un parādīts brīdinājums.

---

**E7-F02 · Paplašināta presetu bibliotēka** · `P1` · P1, P3

> **Audita piezīme (v1.2).** Bāze ir **5 preseti**: `classic`, `beast`, `hormozi`, `minimal`, `karaoke` (`captions/ass.py:85`). Tie jau aptver galvenos virzienus, un `Preset` datu klase nes 15 laukus. Darbs ir paplašināšana un priekšskatījumu pievienošana, ne sistēmas būvēšana.

*Pieņemšanas kritēriji:*
- Vismaz 12 iebūvēti preseti — esošie 5 saglabājas nemainīgi (to maiņa invalidētu esošo lietotāju renderus), pievienoti vismaz 7 jauni.
- Katram presetam ir statiska priekšskatījuma bilde presetu izvēlnē — nevis tikai nosaukums.
- Preseti glabājas datu formātā, nevis kodā, tā ka kopiena var tos veidot un dalīties ([E16-F05](#e16--izplatīšana-licences-un-kopiena)).
- Katra preseta fonts ir vai nu iekļauts ar saderīgu licenci, vai lejupielādēts un attiecināts.

---

**E7-F03 · Presetu redaktors** · `P1` · P3

*Pieņemšanas kritēriji:*
- Visus 15 stila laukus var rediģēt saskarnē ar dzīvu priekšskatījumu.
- Pielāgotu presetu var saglabāt ar nosaukumu, dublēt, dzēst.
- Saglabāta preseta rediģēšana korekti invalidē renderi tiem darbiem, kas to lieto (kā jau dara `caption_style` pirkstu nospiedums).
- Presetu var eksportēt un importēt kā vienu failu.

---

**E7-F04 · Valodas un tulkojumi** · `P2` · P1

*Pieņemšanas kritēriji:*
- Automātiska avota valodas noteikšana; ASR tiek konfigurēts atbilstoši.
- Izvēles subtitru tulkojums uz citu valodu ar oriģināla saglabāšanu.
- Atbalstītas rakstzīmju kopas, kas prasa citu fontu (kirilica, CJK), tiek atklātas un fonts izvēlēts atbilstoši.

---

**E7-F05 · Zīmola komplekti** · `P1` · P3

Nosaukts vizuālās identitātes kopums.

*Pieņemšanas kritēriji:*
- Komplekts satur: subtitru presetu, krāsu paleti, logotipu ar pozīciju un caurspīdīgumu, noklusēto CTA tekstu, hashtagu kopu, nosaukuma stilu.
- Komplektu var piesaistīt projektam; projekta darbi to lieto automātiski.
- Komplektu var pārslēgt esošam darbam un pārrenderēt tikai `render` posmu.
- Komplektu var eksportēt kā vienu failu un importēt citā mašīnā.
- Vismaz 3 komplekti var eksistēt vienlaikus bez konfliktiem.

---

**E7-F06 · Emoji un ikonas subtitros** · `P2` · P1

*Pieņemšanas kritēriji:*
- Emoji atbalsts tiek zondēts (fonta iespēja), nevis pieņemts.
- Automātisks emoji ieteikums pēc atslēgvārda, ko var pilnībā izslēgt.
- Ja fonts emoji neatbalsta, notiek atkāpšanās uz iegultu emoji attēlu, nevis kvadrāts.

---

**E7-F07 · Drošā zona subtitriem** · `P0` · P2

Aizver Kategorijas C3 nepilnību.

*Pieņemšanas kritēriji:*
- Subtitru novietojums tiek ierobežots uz redzamo joslu, ņemot vērā faktisko `content_w`/`content_h` un letterbox joslas.
- Pie `gameplay_amount = 1.0` apakšā piesaistīts presets nekad nenokļūst melnajā vai izplūdinātajā joslā.
- Priekšskatījums rāda drošās zonas robežas, kad lietotājs pārvieto subtitrus.
- Papildu drošās zonas platformu saskarnēm (TikTok apakšējais UI, Reels labā mala) ir pārslēdzamas un redzamas priekšskatījumā.
- Tests fiksē novietojumu vairākiem `gameplay_amount` līmeņiem un krīt, ja subtitri iziet ārpus redzamā laukuma.

---

## E8 — Kadrēšana un kompozīcija

**Mērķis:** klips rāda to, kas svarīgs, arī kad tas nav seja.

---

**E8-F01 · Kadrējuma regulators saskarnē** · `P0` · P2

*Pieņemšanas kritēriji:*
- `gameplay_amount` parādās kā vizuāls slīdnis ar priekšskatījuma miniatūrām abos galos, nevis kā skaitlis.
- Trīs iepriekš iestatīti punkti ar cilvēka nosaukumiem: **Seja tuvplānā** (0.0) · **Sabalansēts** (0.5) · **Viss kadrs** (1.0).
- Vērtība `0.0` tiek apstrādāta kā derīga visur (`is not None`, nevis `if x:`) — arī jaunajā saskarnes kodā.

---

**E8-F02 · Kadrējuma priekšskatījums uz avota** · `P1` · P2

*Pieņemšanas kritēriji:*
- Rāda kadrējuma taisnstūri virs avota kadra ar animāciju pa trajektoriju.
- Rāda griezumus un punch-in kā atzīmes uz laika ass.
- Priekšskatījuma ģeometrija tiek aprēķināta ar to pašu `_resolve_content_box()`, ko lieto renderis.

---

**E8-F03 · Sejas izmēra veto** · `P1` · P2

Aizver Kategorijas C4 nepilnību, nepārkāpjot nulles regresijas garantiju.

*Pieņemšanas kritēriji:*
- Sejas, kas mazākas par konfigurējamu īpatsvaru no kadra, tiek deprioritizētas kā kadrējuma mērķis.
- Funkcija ir **izslēgta pie `gameplay_amount = 0.0`**, lai esošā izvade nemainītos — nulles regresijas garantija paliek spēkā.
- Slieksnis ir pieejams `Settings.camera` un iekļauts `camera` posma pirkstu nospiedumā.
- Tests apliecina, ka pie 0.0 izvades trajektorija ir bitu ziņā identiska iepriekšējai.

---

**E8-F04 · Īsts split-screen** · `P2` · P2

Aizver Kategorijas C2 nepilnību. Lielākais atsevišķais tehniskais darbs šajā dokumentā.

*Pieņemšanas kritēriji:*
- Izkārtojumi: augšā/apakšā, apakšējais stūra ielogs, blakus.
- Reģionus var definēt automātiski (facecam noteikšana) vai manuāli, velkot kadru uz avota.
- Abi reģioni ir dzīvi vienlaicīgi — ne stop kadrs, ne pārslēgšana.
- Atsevišķu avota celiņu gadījumā ([E3-F02](#e3--ievade-un-avoti)) katrs celiņš var aizņemt savu reģionu.
- Renderēšanas veiktspēja: ne vairāk kā 1,6× no viena reģiona renderēšanas laika.
- Izkārtojums glabājas `ClipEdit` un ir iekļauts `render` pirkstu nospiedumā.

*Tehniskās piezīmes:* prasa jaunu `-filter_complex` grafu ar diviem crop ceļiem un overlay; nevar tikt būvēts ar esošo `sendcmd → crop@c` ķēdi. Jāplāno kā atsevišķs renderēšanas ceļš, nevis kā parametrs esošajam.

---

**E8-F05 · Papildu formāta attiecības** · `P2` · P3

*Pieņemšanas kritēriji:*
- Papildus 9:16 atbalstīti 1:1 un 4:5.
- Formāta maiņa pārrenderē tikai `render` posmu, izmantojot to pašu trajektoriju.
- Subtitru drošā zona tiek pārrēķināta katram formātam.

---

**E8-F06 · Punch-in vadība saprotamā valodā** · `P1` · P1

*Pieņemšanas kritēriji:*
- `Settings.retention` piecas kontroles apkopotas vienā slīdnī: Izslēgts / Maigi / Vidēji / Enerģiski, ar detalizētu režīmu aiz "Precīzāk".
- Punch-in vietas ir redzamas laika asī un atsevišķi izslēdzamas.

---

## E9 — Teksti un metadati

**Mērķis:** lietotājs nekad neatver tukšu apraksta lauku.

---

**E9-F01 · Nosaukumu varianti** · `P0` · P1

*Pieņemšanas kritēriji:*
- Vismaz 5 varianti uz klipu, atšķirīgos stilos (jautājums, apgalvojums, saraksts, citāts, provokācija). **Pašreizējais noklusējums ir `TitleSettings.variants = 3`** — tas ceļas uz 5.
- Ierobežojumi (garums, stils) tiek **piespiesti uz modeļa atbildes**, ne tikai pieprasīti promptā — kā jau dara esošais dzinējs.
- Var ģenerēt no jauna ar norādi ("īsāks", "mazāk clickbait").
- Bez LLM režīmā tiek piedāvāts citāts no transkripta kā atkāpšanās, nevis tukšums.

---

**E9-F02 · Apraksti un hashtagi** · `P0` · P1

*Pieņemšanas kritēriji:*
- Apraksts respektē platformas garuma limitu un rāda atlikušās rakstzīmes.
- Hashtagi tiek ģenerēti no satura, nevis no vispārīga saraksta; skaits konfigurējams.
- CTA no zīmola komplekta tiek pievienots automātiski.
- Viena poga nokopē pilnu publicēšanas paketi (nosaukums + apraksts + hashtagi) starpliktuvē platformas formātā.

---

**E9-F03 · Hooks** · `P1` · P1

*Pieņemšanas kritēriji:*
- Alternatīvi klipa atvērumi tiek ranžēti pret esošo.
- Izvēlēts hook var nobīdīt klipa sākumu vai tikt pievienots kā teksta pārklājums pirmajās sekundēs.
- Rāda pamatojumu, kāpēc ieteiktais hook ranžēts augstāk.

---

**E9-F04 · Nosaukumu veidnes failiem** · `P1` · P3

*Pieņemšanas kritēriji:*
- Veidne ar mainīgajiem: `{projekts}`, `{darbs}`, `{indekss}`, `{vērtējums}`, `{nosaukums}`, `{datums}`, `{platforma}`.
- Priekšskatījums rāda gala failu nosaukumus pirms eksporta.
- Nederīgas rakstzīmes failu sistēmai tiek aizvietotas automātiski.

---

**E9-F05 · Vāka kadrs** · `P2` · P1

*Pieņemšanas kritēriji:*
- Ieteikti 3 vāka kadri no klipa (asums, sejas redzamība, kustības trūkums).
- Var izvēlēties jebkuru kadru manuāli un uzlikt teksta pārklājumu.
- Vāks tiek eksportēts kā atsevišķs attēls blakus video failam.

---

## E10 — Eksports un publicēšana

**Mērķis:** aizvērt Plaisu B. Šī epika ir mūsu konkurences uzvara.

---

**E10-F01 · Eksporta iestatījumi** · `P0` · visi

*Pieņemšanas kritēriji:*
- Platformas preseti: TikTok, Reels, Shorts, X, LinkedIn — katrs ar savu izšķirtspēju, bitreitu, maksimālo ilgumu, audio mērķi.
- Kvalitātes izvēle: Ātrs / Sabalansēts / Maksimāls, ar redzamu aptuveno faila izmēru.
- Aparatūras kodēšana kā izvēle, izslēgta pēc noklusējuma, ar paskaidrojumu, kāpēc izvade var atšķirties.
- Katrs eksports tiek pārbaudīts (straumes klāt, ilgums saprātīgs) pirms ziņošanas par pabeigtu.

---

**E10-F02 · Partijas eksports** · `P0` · P3

*Pieņemšanas kritēriji:*
- Eksportēt visus apstiprinātos klipus vienā darbībā uz izvēlētu mapi.
- Nosaukumi no veidnes ([E9-F04](#e9--teksti-un-metadati)).
- Izvēles apakšmapes pēc platformas.
- Blakus katram video izvēles `.txt` ar nosaukumu, aprakstu un hashtagiem.
- Progress ar iespēju atcelt; atcelšana neatstāj daļējus failus.

---

**E10-F03 · Tieša publicēšana** · `P0` · P1, P3

> **Pacelts uz `P0` un v1.1 v1.4 redakcijā** ([D-16](#374-lēmumu-žurnāls)). Publicēšana vairs nav ērtība — tā ir vienīgais uzticamais veids, kā saistīt izeju ar rezultātu. Manuālā saskaņošana ([E11-F04](#e11--vērtības-cilpa-un-kalibrācija)) paliek kā atkāpšanās, bet tā ir darbietilpīga un tāpēc reti tiek darīta konsekventi — un nekonsekventi dati ir sliktāki par to trūkumu.

*Pieņemšanas kritēriji:*
- Atbalstītas platformas v1.0: YouTube Shorts, TikTok, Instagram Reels — caur to oficiālajām API ar lietotāja paša akreditācijas datiem.
- Autorizācija ir izvēles un skaidri paskaidrota: ko lietotne drīkst darīt, ko nedrīkst.
- Publicēšana aizpilda nosaukumu, aprakstu, hashtagus no **aktīvā iepakojuma varianta** ([E17-F01](#e17--iepakojuma-eksperimenti)).
- Publicēšana atgriež platformas media ID un to **automātiski saista** ar klipu un variantu — tas ir tas, kas aizver cilpu bez manuāla darba.
- Neveiksme rāda platformas atgriezto iemeslu cilvēka valodā un saglabā klipu eksportam.
- Publicēšanas atslēgas glabājas OS akreditācijas glabātuvē, nevis atklātā tekstā.
- Ja platformas API nav pieejama vai maina noteikumus, lietotne degradējas uz eksportu, nevis salūzt.

---

**E10-F04 · Plānošana** · `P2` · P1, P3

*Pieņemšanas kritēriji:*
- Klipam var norādīt publicēšanas laiku; lietotne to izdara, ja tā ir palaista.
- Ja lietotne nav palaista plānotajā laikā, publicēšana notiek nākamajā palaišanā ar apstiprinājumu, nevis klusi izlaista.
- Kalendāra skats ar ieplānotajiem klipiem.

---

**E10-F05 · Apstiprinājuma lapa** · `P2` · P3

*Pieņemšanas kritēriji:*
- Ģenerē pašpietiekamu HTML lapu ar klipiem, nosaukumiem un aprakstiem, ko var nosūtīt klientam.
- Lapa strādā bez interneta un bez mūsu servera — video iegulti vai blakus mapē.
- Klients var atzīmēt apstiprinājumu; rezultāts atgriežams kā fails, ko importēt.

---

**E10-F06 · Projekta faila eksports montāžai** · `P3` · P3

*Pieņemšanas kritēriji:*
- Eksports uz EDL/XML/`.fcpxml`, lai klipu varētu pabeigt profesionālā redaktorā.
- Iekļauj griezumu punktus un subtitru celiņu kā atsevišķu failu.

---

## E11 — Vērtības cilpa un kalibrācija

**Mērķis:** kalibrēt vērtējumu pret realitāti, nevis pret gaumi.
**Kāpēc svarīgi:** pēc [D-16](#374-lēmumu-žurnāls) **šī ir produkta kodola epika**, ne papildinājums. Bez tās Alias Studio ir vēl viens klipu ģenerators, kura vienīgā diferenciācija ir cena. Ar to tas ir vienīgais rīks tirgū, kas kļūst labāks tieši tavā nišā ([Plaisa E](#32-kur-ir-plaisa)).

**Kas mainījās v1.4:** visa epika pārcēlās uz **v1.1**, un E11-F02 un E11-F03 kļuva `P0`. Iepriekš tā bija v1.2 "diferenciācijas" darbs.

**Mērījuma vienība ([D-16](#374-lēmumu-žurnāls)): veiktspējas rādītāji, ne nauda.** Noturība, skatījumi un iesaiste nāk no platformu API automātiski, ir salīdzināmi starp klipiem un nav atkarīgi no nišas RPM vai zīmolu līgumiem. Naudas izsekošana tika apzināti noraidīta: tā prasa manuālu ievadi, ir nekonsekventa starp platformām, un noturība ir godīgāks kopīgais mērs. Kas grib eiro, tos izrēķina pats no skatījumiem un sava RPM.

**Primārā metrika ir noturība, ne skatījumi.** Skatījumus nosaka platformas izplatīšana, kas ir troksnis; noturība mēra, vai klips bija labs. Ranžēšanā noturība sver vairāk.

---

**E11-F01 · Instagram cilpa (esošā)** · `P1` · P1

*Pieņemšanas kritēriji:*
- Saglabā esošo funkcionalitāti pilnībā.
- Autorizācijas plūsma nes skaidru paskaidrojumu par Meta izstrādātāja lomas prasību — tas ir konfigurācijas jautājums, nevis kļūda, un saskarnei tas jāpasaka.
- Kļūda "Insufficient Developer Role" rāda četru soļu risinājumu tieši saskarnē, ne tikai dokumentācijā.

---

**E11-F02 · TikTok un YouTube metrikas** · `P0` · P1, P2, P3

Bez trim platformām cilpa aptver mazāko daļu no operatora izvades. Instagram vien nav pietiekami daudz datu, lai kalibrācija konverģētu saprātīgā laikā.

*Pieņemšanas kritēriji:*
- Saskaņotu klipu **noturība** (primārā), skatījumi un iesaiste tiek ievākti tāpat kā Instagram Reels metrikas.
- Kur platforma dod noturības līkni, nevis vienu skaitli, tā tiek saglabāta pilnībā — noturības kritums pirmajās 3 sekundēs ir atsevišķs, ļoti informatīvs signāls par **hook** kvalitāti ([E17](#e17--iepakojuma-eksperimenti)).
- Metriku nosaukumu maiņa API pusē tiek apstrādāta ar to pašu "kāpņu" pieeju, ko lieto `_drop_named_field()`.
- Metrikas tiek normalizētas starp platformām, pirms tās nonāk kalibrācijā — TikTok un Reels noturība nav viens un tas pats skaitlis, un to sajaukšana saindētu modeli.
- Manuāla saistīšana ir pieejama, kad automātiskā neizdodas; noraidīts pāris nekad netiek ieteikts atkārtoti.
- Katras platformas API nepieejamība degradē uz manuālu ievadi ([E11-F04](#e11--vērtības-cilpa-un-kalibrācija)), nevis bloķē cilpu.

---

**E11-F03 · Kalibrācijas atskaite** · `P0` · P1

Cilpas noslēdzošais posms. Šī ir vieta, kur produkts pierāda, ka ir mācījies.

*Pieņemšanas kritēriji:*
- Rāda prognozēto vērtējumu pret reālo noturību izkliedes diagrammā ar korelācijas rādītāju.
- Identificē, **kuras vērtējuma komponentes prognozē vislabāk šim lietotājam**, ar katra kanāla atsevišķu korelāciju.
- Piedāvā svaru korekciju kā ieteikumu ar konkrētu pamatojumu: *"`dynamics` 0,25 → 0,17 — 34 klipos šis kanāls korelē −0,08 ar noturību"*.
- **Nekad nemaina svarus automātiski** ([2.7](#27-vērtības-cilpa) 1. noteikums). Pieņemšana ir viens klikšķis; noraidīšana arī.
- Pieņemtā korekcija tiek reģistrēta ar datumu un ir atsaucama; lietotājs var redzēt, kā viņa profils mainījies laikā.
- **Zem 15 saskaņotiem klipiem ieteikumi netiek rādīti vispār** — atskaite saka, cik klipu vēl vajag, un cik ir. Vāji ieteikumi ar mazu fontu ir sliktāki par to trūkumu.
- Atskaite atsevišķi brīdina, ja korelācija ir nenozīmīga (plaši ticamības intervāli) — arī pie pietiekama klipu skaita.

---

**E11-F05 · Prognoze pret rezultātu uz klipa** · `P1` · P1

*Pieņemšanas kritēriji:*
- Katrs publicēts un saskaņots klips rāda savu prognozēto vērtējumu **blakus** reālajam rezultātam.
- Lielākās kļūdas abos virzienos ir atsevišķi izceļamas: "prognozēja augstu, nostrādāja slikti" un otrādi. Tieši šie klipi māca visvairāk.
- Klipa vērtējuma izklājums ([26.4](#264-vērtējuma-izklājums)) pēc mērījuma iegūst otro kolonnu: kurš signāls šoreiz maldināja.

---

**E11-F06 · Personīgais bāzlīmenis** · `P1` · P1, P3

Bez bāzlīmeņa "87" nav nozīmes. Ar to "87, tava mediāna ir 62" ir.

*Pieņemšanas kritēriji:*
- Rīks rēķina lietotāja paša mediāno noturību un skatījumus pa platformām un pa laika periodiem.
- Klipa rezultāts vienmēr tiek rādīts attiecībā pret šo bāzlīmeni, ne absolūti.
- Bāzlīmenis tiek rēķināts slīdošā logā (pēdējie ~50 klipi), lai auditorijas augšana nesabojātu salīdzinājumu.
- Projekta / zīmola komplekta līmenī bāzlīmeņi ir atsevišķi — P3 klientiem tie nav salīdzināmi.

---

**E11-F04 · Vietējā vēsture bez platformām** · `P1` · visi

Atkāpšanās ceļš, kas notur cilpu dzīvu, kad API nav pieejama vai lietotājs to nevēlas.

*Pieņemšanas kritēriji:*
- Lietotājs var manuāli ievadīt klipa rezultātu (skatījumi, noturība, patīk), ja platformas integrācijas nav.
- Ievade ir ātra: viena rinda uz klipu, ielīmējama no platformas paneļa, ne forma ar desmit laukiem.
- Manuālie dati barojas tajā pašā kalibrācijā un ir marķēti kā manuāli.
- CSV imports lietotājam, kuram jau ir sava izklājlapa — P3 tāda parasti ir.

---

## E12 — Iestatījumi un profili

**Mērķis:** dziļums paliek, bet vairs nav ieejas maksa.

---

**E12-F01 · Trīs līmeņu iestatījumu hierarhija** · `P0` · P1, P3

Pārstrukturē 72 kontroles, nevis noņem tās.

| Līmenis | Ko satur | Kur atrodas |
|---|---|---|
| **Ātrais** | 6–8 kontroles: profils, klipu skaits, garums, platforma, subtitru presets, kadrējums | Studijā, vienmēr redzams |
| **Standarta** | ~25 kontroles: vērtēšanas līdzsvars, temps, punch-in, audio, teksti | Iestatījumi, atvērts pēc noklusējuma |
| **Padziļinātais** | Atlikušie ~40: līknes svari, detektoru sliekšņi, ainu noteikšana, kodētājs | Iestatījumi, aiz "Padziļinātie iestatījumi", ar brīdinājumu |

> **Audita piezīme (v1.2).** Šī prasība ir mazāka, nekā v1.1 pieņēma. `settings_schema.py` **jau nes** `help` tekstu katram no 68 laukiem, un katrai no 13 grupām **jau ir** `cost` (`cheap`/`moderate`/`high`) ar `cost_note`, kas paskaidro, ko maiņa pārrēķinās. Trūkst tikai `level` lauka un frontenda, kas to ievēro. Paskaidrojumi ir jāpārfrāzē cilvēka valodā, ne jāraksta no nulles.

*Pieņemšanas kritēriji:*
- Katra kontrole eksistē tieši vienā līmenī; nekas nedublējas.
- Katrai kontrolei jau ir `help` — tas tiek **pārskatīts pret [24.6](#246-cilvēka-valoda-virsmā-žargons-dziļumā)**, nevis rakstīts no jauna: `quick` līmeņa teksti bez žargona, `advanced` drīkst būt tehniski.
- `validate_schema()` divvirzienu pārbaude paliek spēkā un tiek papildināta ar pārbaudi, ka katrai kontrolei ir piešķirts līmenis un nepārtukšs `help`.
- Meklēšana pa iestatījumiem atrod kontroli neatkarīgi no līmeņa.
- Padziļinātā līmeņa atvēršana rāda "Šie iestatījumi var pasliktināt rezultātu" un pogu "Atjaunot noklusējumus".

---

**E12-F02 · Profili** · `P0` · P3

*Pieņemšanas kritēriji:*
- Profils satur pilnu `Settings` koku plus zīmola komplekta atsauci.
- Trīs iebūvēti profili ([E4-F08](#e4--momentu-atlase-un-analīze)) nav rediģējami, bet ir dublējami.
- Aktīvais profils redzams Studijā; maiņa neietekmē jau izveidotos darbus (momentuzņēmums paliek spēkā — specifikācijas 2. noteikums).
- Profila maiņa rāda diff pret iepriekšējo, ja lietotājs to lūdz.

---

**E12-F03 · Salīdzināšana ar noklusējumu** · `P1` · P3

*Pieņemšanas kritēriji:*
- Katra kontrole, kas atšķiras no noklusējuma, ir vizuāli atzīmēta.
- Ekrāna augšā rādīts "N iestatījumi mainīti" ar sarakstu un iespēju atgriezt pa vienam.

---

**E12-F04 · Profilu eksports un imports** · `P1` · P3

*Pieņemšanas kritēriji:*
- Profils eksportējams kā viens fails, kas satur arī zīmola komplektu un subtitru presetus.
- Imports nekad neaizstāj esošo profilu klusi; konflikts prasa pārdēvēšanu.
- Imports no citas versijas ir iecietīgs: nezināmas atslēgas tiek izmestas, trūkstošās paliek pie noklusējuma — tāpat kā `_build`.

---

**E12-F05 · Iestatījumu ietekmes rādītājs** · `P2` · P3

> **Audita piezīme (v1.2).** Daļēji izpildīts. Katra grupa jau nes `cost` un `cost_note` — piemēram, `clips` grupa ir `COST_EXPENSIVE` ar piezīmi *"Changing these re-picks candidate moments and rescores them."* Trūkst tikai (a) precizitātes līdz kontroles, nevis grupas līmenim, un (b) laika aplēses.

*Pieņemšanas kritēriji:*
- Mainot iestatījumu esošam darbam, saskarne rāda, kuri posmi tiks izpildīti atkārtoti un cik aptuveni ilgi.
- Esošais `cost` / `cost_note` grupas līmenī tiek saglabāts kā rupjā atbilde; kontroles līmeņa `affects` to precizē.
- Balstās uz reālo pirkstu nospiedumu loģiku, nevis uz atsevišķu sarakstu, ko var aizmirst atjaunināt.

---

## E13 — Veiktspēja un resursi

---

**E13-F01 · Aparatūras profils un aplēses** · `P0` · visi

*Pieņemšanas kritēriji:*
- Aplēses balstās uz mērītu realtime koeficientu, kas tiek atjaunināts pēc katra darba.
- Aplēse pirms darba ir ±30 % robežās pēc trešā darba uz tās pašas mašīnas.
- Aplēse tiek rādīta gan darba sākumā, gan rindā.

---

**E13-F02 · Degradācija bez GPU** · `P1` · P1

*Pieņemšanas kritēriji:*
- Pilns konveijers pabeidzas uz CPU-only mašīnas ar 8 GB RAM 60 minūšu avotam.
- Precizitāte tiek automātiski pazemināta pēc pieejamās VRAM (esošā `_FLOAT16_VRAM_GB` loģika).
- CUDA OOM tiek noķerts un noved pie automātiskas atkāpšanās, nevis darba neveiksmes.
- Nekur netiek prasīta CUDA kā priekšnosacījums.

---

**E13-F03 · Veiktspējas budžeti** · `P1` · visi

Mērķi 60 minūšu 1080p avotam:

| Aparatūra | Mērķis | Pieļaujams |
|---|---|---|
| RTX 4070 / M3 Pro | < 9 min | 12 min |
| RTX 3050 Ti (4 GB) | < 14 min | 20 min |
| CPU-only, 8 kodoli | < 55 min | 75 min |

*Pieņemšanas kritēriji:*
- Automatizēts veiktspējas tests, kas mēra katru posmu un krīt, ja regresija pārsniedz 20 %.
- Rezultāti tiek publicēti repozitorijā katrai izlaišanai.

---

**E13-F04 · Atmiņas robežas** · `P1` · visi

*Pieņemšanas kritēriji:*
- Maksimālais RSS nepārsniedz 6 GB uz 90 minūšu avota.
- Modeļi tiek atbrīvoti pirms nākamā ielādes (jau dara ASR posms; jāattiecina uz visiem).
- Ilgi avoti tiek apstrādāti straumējoši tur, kur iespējams, nevis pilnībā atmiņā.

---

**E13-F05 · Resursu vadība rindā** · `P2` · P2

*Pieņemšanas kritēriji:*
- Iestatījums: "Ierobežot CPU izmantojumu uz N kodoliem", lai dators paliktu lietojams.
- Iestatījums: "Strādāt tikai naktī" ar laika logu.

---

## E14 — Uzticamība, kļūdas un atbalsts

---

**E14-F01 · Kļūdu vārdnīca** · `P0` · visi

*Pieņemšanas kritēriji:*
- Katrai zināmajai kļūdu klasei ir ieraksts ar: cilvēka valodas cēloni, vismaz vienu darbību, izvēles saiti uz dokumentāciju.
- Vārdnīca aptver vismaz visas kļūdas no specifikācijas §20 tabulas.
- Nezināma kļūda dod vispārīgu ziņu **plus** posma nosaukumu, pēdējās stderr rindas un kopēšanas pogu.
- Neviena kļūda saskarnē nesākas ar Python traceback.

---

**E14-F02 · Atsākšana no posma** · `P0` · visi

*Pieņemšanas kritēriji:*
- Neizdevies darbs var tikt atsākts no neizdevušās posma, izmantojot esošos kontrolpunktus.
- Saskarne rāda, kuri posmi ir pabeigti un kurš neizdevās.
- Atsākšana ievēro invalidēšanas kaskādi — atkārtoti izpildīts posms invalidē visus pēc tā.

---

**E14-F03 · Diagnostikas pakete** · `P1` · visi

*Pieņemšanas kritēriji:*
- Viena poga savāc: versiju, OS, aparatūras profilu, pēdējos žurnālus, iestatījumu koku, posmu statusus.
- Personu identificējoša informācija (failu ceļi, avota nosaukumi, API atslēgas) tiek noņemta vai maskēta pēc noklusējuma.
- Rezultāts ir viens zip fails, ko lietotājs var apskatīt pirms nosūtīšanas.

---

**E14-F04 · Avāriju atskaites** · `P1` · komanda

*Pieņemšanas kritēriji:*
- Izvēles (opt-in), izslēgts pēc noklusējuma, ar skaidru paskaidrojumu, kas tiek sūtīts.
- Atskaite satur steku un versiju, nekad — mediju saturu, ceļus vai atslēgas.
- Lietotājs var apskatīt atskaites saturu pirms nosūtīšanas.

---

**E14-F05 · Iebūvēta palīdzība** · `P1` · visi

*Pieņemšanas kritēriji:*
- Katram ekrānam ir kontekstuāla palīdzība ar 3–5 biežākajiem jautājumiem.
- Glosārijs tehniskajiem terminiem, sasaistīts no vietām, kur tie parādās.
- Darbojas bez interneta.

---

**E14-F06 · Datu integritāte** · `P0` · visi

*Pieņemšanas kritēriji:*
- Diska un datubāzes nesakritības gadījumā disks uzvar — kā jau nosaka arhitektūra.
- Iestatījumu un `clip_edits.json` rakstīšana ir atomāra (raksta pagaidu failā, pēc tam pārsauc), lai avārija rakstīšanas laikā nesabojā darbu.
- Bojāts JSON kontrolpunkts tiek atklāts un uzskatīts par trūkstošu, nevis avarē konveijeru.

---

## E15 — Atjauninājumi, privātums un telemetrija

---

**E15-F01 · Automātiskie atjauninājumi** · `P0` · visi

*Pieņemšanas kritēriji:*
- Tauri updater ar parakstītiem atjauninājumiem un publisku atslēgu, kas iekļauta būvē.
- Pārbaude palaišanas laikā, izslēdzama.
- Rāda izmaiņu sarakstu pirms instalēšanas.
- Atjauninājums nekad nedzēš lietotāja darbus, iestatījumus, presetus vai profilus.
- Atjauninājums, kas maina iestatījumu shēmu, migrē esošo konfigurāciju vai to iecietīgi ignorē — nekad neavarē.

---

**E15-F02 · Versiju saderība** · `P0` · visi

*Pieņemšanas kritēriji:*
- Darbs, kas izveidots vecākā versijā, atveras jaunākā vai skaidri paziņo, ka to nevar.
- Kontrolpunkta shēmas versijas maiņa noved pie tā posma atkārtotas izpildes, nevis avārijas.
- Trūkstoša pirkstu nospieduma atslēga nozīmē "nemainīts", nevis "novecojis" — kā jau nosaka `fingerprint_ok`.

---

**E15-F03 · Privātuma paziņojums** · `P0` · visi

*Pieņemšanas kritēriji:*
- Onboardingā un iestatījumos redzams paziņojums, kas nosauc **katru** tīkla izsaukumu, ko lietotne veic, un kad.
- Skaidri norādīts, ka mediji nekad netiek augšupielādēti.
- Skaidri norādīts, kas tiek sūtīts LLM sniedzējam Gemini režīmā (teksta fragmenti un T2 kadri) un ka Ollama režīms to novērš.
- Paziņojums ir daļa no repozitorija un versionēts kopā ar kodu.

---

**E15-F04 · Telemetrija** · `P2` · komanda

*Pieņemšanas kritēriji:*
- Izvēles (opt-in), izslēgta pēc noklusējuma.
- Vāc tikai: versiju, OS, aparatūras klasi, posmu ilgumus, kļūdu klases. Nekad — saturu, nosaukumus, ceļus.
- Lietotājs var apskatīt tieši to, kas tiek sūtīts, un izslēgt jebkurā laikā.
- Izslēgta telemetrija nesūta neko, ieskaitot "esmu izslēgts" signālu.

---

## E16 — Izplatīšana, licences un kopiena

---

**E16-F01 · Instalatori abām platformām** · `P0` · visi

> **Audita piezīme (v1.2).** Situācija ir labāka, nekā v1.1 pieņēma. `tauri.conf.json` tiešām satur `"targets": ["dmg"]`, **bet** `.github/workflows/windows.yml` apiet to ar `npx tauri build --bundles nsis`, pēc tam instalē klusi (`/S`), palaiž instalēto lietotni un pārbauda, ka tā dzīvo pēc 15 sekundēm. Windows instalators **eksistē un tiek pārbaudīts katrā push**. Problēma ir tikai tā, ka lokāla `npx tauri build` to neražo — konfigurācija un CI nesakrīt.

*Pieņemšanas kritēriji:*
- `tauri.conf.json` `bundle.targets` ietver `nsis` un `dmg`, tā ka lokāla būve un CI būve ražo vienu un to pašu. CI `--bundles` karogs kļūst lieks un tiek noņemts.
- Windows instalators uzstāda, atjaunina un pilnībā atinstalē, atstājot `PUBLIKCLIP_HOME` pēc lietotāja izvēles.
- macOS `.dmg` ir universāls (Apple Silicon + Intel) vai izplatīts kā divi skaidri marķēti faili.
- Instalatora izmērs < 150 MB (modeļi tiek lejupielādēti atsevišķi).
- Būve tiek veikta ar `npx tauri build`, nekad ar `cargo build --release` — pēdējais dod bināru, kas joprojām rāda uz dev serveri.

---

**E16-F02 · Koda parakstīšana** · `P0` · visi

*Pieņemšanas kritēriji:*
- Windows: parakstīts ar derīgu sertifikātu; SmartScreen brīdinājums nerodas parastam lietotājam.
- macOS: parakstīts un notarizēts; Gatekeeper atļauj palaišanu bez labās peles trika.
- Parakstīšana notiek CI vidē, atslēgas nekad nav repozitorijā.

*Atkāpšanās ceļš (bezmaksas projekta dēļ — [2.6](#26-izplatīšanas-modelis-bezmaksas-un-atvērts)):* ja sertifikāta finansējuma nav, izlaišana notiek neparakstīta, ar šādiem obligātajiem nosacījumiem:
- README un lejupielādes lapa brīdina par gaidāmo SmartScreen / Gatekeeper ekrānu **pirms** lejupielādes, ar ekrānuzņēmumu un precīzu apiešanas soļu aprakstu.
- Katrai izlaišanai tiek publicēta SHA-256 kontrolsumma, lai lietotājs var pārliecināties par faila autentiskumu.
- Prioritāte: **macOS notarizācija pirmā** (99 USD, un bez tās Gatekeeper faktiski bloķē palaišanu), Windows sertifikāts otrais (dārgāks, un tur brīdinājums ir apietams).

---

**E16-F03 · AGPL atbilstība saskarnē** · `P0` · juridiski

*Pieņemšanas kritēriji:*
- "Par" ekrāns satur licences tekstu, saiti uz pilnu pirmkodu un tieši to versiju, kas atbilst instalētajai būvei.
- Trešo pušu attiecinājumi ([VENDORED-LICENSES.md](VENDORED-LICENSES.md)) ir pieejami no saskarnes.
- Izmaiņas pret augšupējo publikclip ir nosauktas — AGPL prasa modifikāciju norādīšanu.
- Katra izlaišana publicē avota arhīvu tieši tai versijai, ne tikai `main` zaru.
- Ja lietotne kādreiz kļūst par tīkla pakalpojumu, pirmkoda piedāvājums attiecas arī uz to — AGPL §13.

---

**E16-F04 · macOS validācija** · `P0` · visi

> **Audita piezīme (v1.2).** Nepilnība ir nopietnāka, nekā v1.1 aprakstīja, un ironiska: `.github/workflows/` satur **tikai `windows.yml`**. macOS ir vienlaikus vienīgais bundle mērķis konfigurācijā **un** vienīgā platforma bez jebkādas automatizētas pārbaudes. Windows, kas nav bundle mērķis, ir vienīgā, kas tiek testēta.

*Pieņemšanas kritēriji:*
- **`macos.yml` CI darbplūsma**, kas atspoguļo `windows.yml`: `uv sync`, ffmpeg izšķiršana, pilns testu komplekts, `.dmg` būve, montēšana, lietotnes palaišana un dzīvības pārbaude.
- Pilns darbs no gala līdz galam izpildīts un dokumentēts uz Apple Silicon.
- MPS paātrinājums izmantots, kur pieejams; kur nē — dokumentēts, kāpēc.
- Zināmās macOS atšķirības (ffmpeg izšķiršana, fontu ceļi, atļaujas) pārbaudītas.

---

**E16-F05 · Kopienas paplašinājumi** · `P2` · kopiena

*Pieņemšanas kritēriji:*
- Subtitru preseti, profili un zīmola komplekti ir datu faili ar dokumentētu shēmu.
- Importēšana notiek caur failu, nevis caur mūsu serveri — nav infrastruktūras izmaksu.
- Shēmai ir versija, un imports no nesaderīgas versijas kļūdās skaidri.

---

**E16-F06 · Dokumentācija izlaišanai** · `P1` · visi

*Pieņemšanas kritēriji:*
- README ar reāliem ekrānuzņēmumiem, prasībām un instalācijas soļiem.
- Ātrā sākuma ceļvedis 5 soļos.
- Biežāko problēmu saraksts, kas atspoguļo specifikācijas §20 tabulu.
- Šis PRD un `SPECIFICATION.md` paliek repozitorijā kā izstrādes atsauce.

---

**E16-F07 · Repozitorija higiēna: rindu beigas** · `P0` · izstrāde

> **Jauna prasība v1.2, koriģēta v1.5** (nepilnība E7).
>
> **Sākotnējais apgalvojums bija pārspīlēts.** v1.2 un v1.3 apgalvoja, ka CRLF "padara repozitoriju nelasāmu". Tieša pārbaude to atspēkoja: `git ls-files --eol` rāda **112 teksta failus ar LF indeksā un nevienu ar CRLF**. Krātuves saturs vienmēr ir bijis tīrs.
>
> Reālā problēma ir mazāka un citāda: bez `.gitattributes` un bez `core.autocrlf` **darba koks** uz Windows nonāk CRLF, kamēr indekss paliek LF. Tāpēc tas pats checkout uz Windows izskatās tīrs, bet nolasīts no Linux — 82 modificēti faili. Tā ir divdomība, ne bojājums, un tā maksā tikai tad, kad diffi jāpārskata pa vienam — kas tieši tagad sākas.
>
> **Prioritāte tāpēc `P1`, ne `P0`.** Izpildīšana joprojām aizņem piecas minūtes un noņem veselu neskaidrību klasi.

*Pieņemšanas kritēriji:*
- `.gitattributes` fails saknē ar `* text=auto eol=lf` un tiešiem noteikumiem binārajiem tipiem (`*.png`, `*.onnx`, `*.pth`, `*.ttf`, `*.ico`, `*.icns` → `binary`).
- Vienreizēja normalizācija (`git add --renormalize .`). Praksē tā skāra **vienu failu** (`captions/fonts/OFL-Anton.txt`), jo pārējais indekss jau bija LF — tāpēc atsevišķs commit nebija vajadzīgs un tas iekļauts kopā ar `.gitattributes`.
- Pēc tam `git status` uz tīras darba kopijas ir tukšs gan Windows, gan macOS, gan Linux.
- CI pārbaude, kas krīt, ja kāds fails ienāk ar CRLF (`guards.yml`).
- `vendor/` koks tiek normalizēts kopā ar pārējo — augšupējais kods paliek saturiski neskarts.

---

## E17 — Iepakojuma eksperimenti

**Mērķis:** noskaidrot, kāds nosaukums, hook un vāks strādā **šai** auditorijai, un pēc tam to izmantot.
**Kāpēc svarīgi:** tā ir [D-16](#374-lēmumu-žurnāls) otrā svira. Divi klipi ar identisku saturu un atšķirīgiem nosaukumiem nav vienas vērtības, un šodien rīks nosaukumu uzģenerē vienreiz un nekad neuzzina, vai tas bija labs.
**Jauna epika v1.4.** Neviens no šiem elementiem PRD līdz šim neeksistēja.

> **Kāpēc iepakojums pirms atlases uzlabojumiem.** Iepakojuma eksperiments dod signālu **ātrāk** nekā atlases kalibrācija: mainot vienu nosaukumu, viss pārējais paliek nemainīgs, tāpēc cēloņsakarība ir daudz tīrāka. Atlases kalibrācija prasa desmitiem klipu, pirms trokšņa fons noskaidrojas. Iepakojums ir tas, kur cilpa pierāda sevi vispirms.

---

**E17-F01 · Iepakojums kā atsevišķa vienība** · `P1` · P1, P3

Pirms var testēt, iepakojumam jābūt lietai, ko var nosaukt un salīdzināt.

*Pieņemšanas kritēriji:*
- Ievieš `Packaging` vienību: nosaukums, hook, vāka kadrs, apraksts, hashtagi — kā viens komplekts ar savu ID.
- Klipam var būt vairāki iepakojumi; viens ir aktīvs.
- Iepakojums glabājas `clip_edits.json` blakus esošajiem laukiem un ir iekļauts `render` pirkstu nospiedumā, ja tas ietekmē izvadi (vāks, hook pārklājums).
- Iepakojumu var kopēt no viena klipa uz citu kā izejas punktu.

---

**E17-F02 · Variantu ģenerēšana ar nodomu** · `P1` · P1

*Pieņemšanas kritēriji:*
- Ģenerē 2–4 iepakojuma variantus, kas **atšķiras pēc nosauktas ass**, ne nejauši: jautājums pret apgalvojumu, konkrēts skaitlis pret vispārīgu solījumu, ziņkāre pret skaidrību.
- Katrs variants nes savu asi kā metadatus — bez tā rezultāts nav interpretējams un kalibrācija nevar mācīties.
- Vāka kadru varianti nāk no [E9-F05](#e9--teksti-un-metadati) ieteikumiem un arī nes asi (seja pret darbību, tuvs pret plašu).
- Lietotājs var rediģēt jebkuru variantu vai pievienot savu.

---

**E17-F03 · Eksperimenta izpilde** · `P1` · P1, P3

*Pieņemšanas kritēriji:*
- Lietotājs izvēlas, kuri varianti tiek publicēti un kur; rīks reģistrē, kurš variants aizgāja uz kuru platformu un kad.
- **Publicēšanas laiks tiek reģistrēts kā mainīgais**, jo tas ietekmē rezultātu vismaz tikpat, cik nosaukums. Bez tā katrs salīdzinājums ir piesārņots.
- Divi varianti vienā platformā vienam saturam tiek marķēti kā riskants eksperiments (algoritms var to uztvert kā dublikātu) — rīks to pasaka, bet neaizliedz.
- Ieteicamais noklusējuma modelis: **viens variants uz platformu**, salīdzinājums starp platformām un laikā, nevis A/B vienā kanālā.

---

**E17-F04 · Rezultātu attiecinājums** · `P0` · P1

Bez šī E17 ir tikai variantu ģenerators.

*Pieņemšanas kritēriji:*
- Katrs izmērītais rezultāts ([E11-F02](#e11--vērtības-cilpa-un-kalibrācija)) tiek piesaistīts konkrētajam iepakojuma variantam, ne tikai klipam.
- **Noturība pirmajās 3 sekundēs tiek attiecināta uz hook un vāku**; kopējā noturība — uz saturu. Šis dalījums ir tas, kas padara eksperimentu interpretējamu.
- Rezultāti tiek grupēti pēc ass ([E17-F02](#e17--iepakojuma-eksperimenti)), ne pēc atsevišķa nosaukuma teksta.
- Attiecinājums degradējas graciozi: ja platforma nedod noturības līkni, variants tiek vērtēts pēc skatījumiem ar zemāku svaru un tas ir marķēts.

---

**E17-F05 · Iemācītais iepakojuma profils** · `P1` · P1, P3

*Pieņemšanas kritēriji:*
- Pēc pietiekamiem datiem rīks pasaka, kura ass uzvar: *"Tavā kanālā jautājuma nosaukumi tur 3 s noturību par 11 % labāk nekā apgalvojumi (n=28)"*.
- Secinājums tiek piedāvāts kā **noklusējuma maiņa** `TitleSettings` un `hooks` iestatījumos, ar pieņemt/noraidīt izvēli — tāpat kā svaru kalibrācija.
- Profils ir piesaistīts zīmola komplektam ([E7-F05](#e7--subtitri-stils-un-zīmola-komplekti)), ne globāls — P3 klientiem tas atšķiras.
- Nekas nemainās automātiski.

---

**E17-F06 · Statistiskais godīgums** · `P0` · visi

Šī prasība eksistē, lai produkts nemelotu ar skaitļiem. Tā ir tikpat svarīga kā pati funkcija.

*Pieņemšanas kritēriji:*
- Katrs secinājums nes līdzi `n` un ticamības intervālu. "Jautājumi uzvar" bez `n=4` ir dezinformācija.
- Zem noteikta sliekšņa secinājumi netiek rādīti — tiek rādīts, cik datu vēl vajag.
- Rīks **skaidri nošķir korelāciju no cēloņsakarības** saskarnes tekstā, un nekad neapgalvo, ka variants "izraisīja" rezultātu.
- Zināmie piesārņotāji tiek nosaukti: publicēšanas laiks, platformas algoritma izmaiņas, auditorijas augšana, sezonalitāte.
- Ir tests, kas ar sintētiskiem datiem apliecina: ar troksni bez signāla rīks **neatrod** uzvarētāju.

---

# C daļa — Dizains

## 24. Dizaina principi

Septiņi principi. Katrs ir lēmuma tests, nevis vēlme.

---

### 24.1. Noklusējums ir produkts

Lietotājs, kurš nekad neatver iestatījumus, saņem 90 % no maksimālā rezultāta.

*Tests:* vai šo ekrānu var pabeigt, neko nemainot? Ja nē — nepareizs noklusējums.

---

### 24.2. Progresīvā atklāsme, nevis slēpšana

Sarežģītība netiek noņemta, tikai sakārtota slāņos. Ikviens regulators paliek sasniedzams; tikai ne visi vienlaikus.

*Tests:* vai kāda funkcija ir kļuvusi neiespējama, nevis tikai tālāka? Ja jā — nepareizi paslēpts.

---

### 24.3. Katrs skaitlis ir noklikšķināms līdz pierādījumam

Vērtējums, ilgums, "3 griezumi" — katrs ved uz to, kas to radīja.

*Tests:* vai lietotājs var nepiekrist šim skaitlim uz pierādījuma pamata? Ja nē — tā ir melnā kaste.

---

### 24.4. Priekšskatījums ir līgums

Tas, ko lietotājs redz redaktorā, ir tas, ko viņš saņem failā. Ja abas puses atšķiras, funkcija ir salauzta, pat ja katra atsevišķi ir pareiza.

*Tests:* vai priekšskatījums un renderis atrisina caur vienu un to pašu kodu? Ja nē — tie dreifēs.

---

### 24.5. Kļūda ir dizaina virsma

Katra kļūda saņem tikpat daudz dizaina uzmanības kā veiksmes ceļš: cēlonis cilvēka valodā, vismaz viena darbība, tehniskā informācija aiz atvēruma.

*Tests:* vai P1 Anna — podkāsteris, ne inženieris — saprot, kas notika un ko darīt? Ja nē — pārrakstīt.

---

### 24.6. Cilvēka valoda virsmā, žargons dziļumā

"Skaļums: platformas standarts" virspusē; "LUFS mērķis: −14" padziļinātajos iestatījumos. Abi ir pieejami; tikai viens ir noklusējums.

*Tests:* vai šo vārdu zinātu cilvēks, kurš nav montējis video? Ja nē — tas nepieder virsmai.

---

### 24.7. Gaidīšana ir godīga

Progresa josla, kas melo, ir sliktāka par tādu, kuras nav. Rādām reālu posmu, reālu procentu un reālu aplēsi, kas mainās.

*Tests:* vai aplēse kļūst precīzāka, tuvojoties beigām? Ja nē — tā ir dekorācija.

---

## 25. Informācijas arhitektūra

### 25.1. Pašreizējā struktūra

```
boot → onboarding → studio ⇄ review / loop / settings
```

Sešas skatvietas, ko maršrutē viens `useState` `App.tsx`. Problēmas: nav vietas, kur redzēt daudzus darbus; iestatījumi ir viens plakans blāķis; klipu redaktors ir modālis virs pārskata; nav projektu jēdziena.

### 25.2. Mērķa struktūra

```
┌──────────────────────────────────────────────────────────────┐
│  Sānjosla (vienmēr redzama)                                  │
│                                                              │
│  ▸ Studija            jauns darbs                            │
│  ▸ Bibliotēka         visi darbi un projekti                 │
│  ▸ Rinda        (2)   aktīvie un gaidošie darbi              │
│  ▸ Rezultāti          publicēto klipu metrikas               │
│  ─────────────────                                           │
│  Profils: Podkāsts ▾  aktīvais profils, pārslēdzams          │
│  ⚙ Iestatījumi                                               │
│  ? Palīdzība                                                 │
└──────────────────────────────────────────────────────────────┘
```

**Četras galvenās vietas** sānjoslā (nevis seši ekrāni, ko maršrutē modāļi):

| Vieta | Atbild uz jautājumu |
|---|---|
| **Studija** | "Es gribu apstrādāt šo video." |
| **Bibliotēka** | "Kur ir tas darbs no pagājušās nedēļas?" |
| **Rinda** | "Cik tālu tas ir?" |
| **Rezultāti** | "Vai tas, ko es publicēju, nostrādāja?" |

**Ligzdotie skati** (nevis atsevišķas vietas):

```
Bibliotēka
  └─ Darbs
       ├─ Pārskats (klipu režģis)          ← noklusējums
       ├─ Analīze (interešu līkne, kandidāti)
       └─ Klips
            ├─ Skats (atskaņotājs + vērtējuma izklājums)
            └─ Redaktors (pilnekrāna, ne modālis)
```

**Iestatījumi** kā atsevišķa vieta ar trim līmeņiem ([E12-F01](#e12--iestatījumi-un-profili)), nevis viens saraksts.

### 25.3. Navigācijas noteikumi

1. **Klipu redaktors ir pilnekrāna skats, nevis modālis.** Modālis virs saraksta liek justies pagaidu; redaktors ir vieta, kur pavada minūtes.
2. **Atgriešanās vienmēr ved uz vietu, no kuras nāca**, ar saglabātu ritināšanas pozīciju un filtriem.
3. **Rinda ir sasniedzama no jebkuras vietas** ar skaitītāju sānjoslā — lietotājs nekad nezaudē redzamību uz to, kas notiek fonā.
4. **Nav dziļāku par trim līmeņiem** ceļu.
5. **Katrai vietai ir jēgpilns tukšais stāvoklis** ar vienu skaidru darbību.

### 25.4. Klaviatūras karte

| Taustiņš | Darbība | Kur |
|---|---|---|
| `Cmd/Ctrl + N` | Jauns darbs | globāli |
| `Cmd/Ctrl + ,` | Iestatījumi | globāli |
| `Cmd/Ctrl + K` | Ātrā komandu josla | globāli |
| `J` / `K` vai `↑` / `↓` | Nākamais / iepriekšējais klips | Pārskats |
| `Space` | Atskaņot / apturēt | atskaņotājs |
| `,` / `.` | Kadrs atpakaļ / uz priekšu | redaktors |
| `A` | Apstiprināt klipu | Pārskats, Skats |
| `X` | Atmest klipu | Pārskats, Skats |
| `E` | Atvērt redaktorā | Pārskats, Skats |
| `I` / `O` | Iestatīt sākumu / beigas | redaktors |
| `Cmd/Ctrl + Z` / `Shift+Z` | Atsaukt / atcelt atsaukšanu | redaktors |
| `Esc` | Atpakaļ | visur |

*Pieņemšanas kritērijs:* visu pārskata un apstiprināšanas darbplūsmu var izpildīt bez peles.

---

## 26. Ekrānu specifikācijas

### 26.1. Studija

**Mērķis:** no nulles līdz sāktam darbam < 15 sekundēs.

```
┌───────────────────────────────────────────────────────────────┐
│                                                               │
│                    ┌─────────────────────┐                    │
│                    │                     │                    │
│                    │   Nomet video šeit  │                    │
│                    │         vai         │                    │
│                    │   [Izvēlies failu]  │                    │
│                    │                     │                    │
│                    └─────────────────────┘                    │
│                                                               │
│      ┌─────────────────────────────────────────────┐          │
│      │  Ielīmē YouTube vai Twitch saiti…           │          │
│      └─────────────────────────────────────────────┘          │
│                                                               │
│  ──────────────────────────────────────────────────────────   │
│                                                               │
│   Profils    [ Podkāsts ▾ ]      Klipi     [ Auto ▾ ]         │
│   Garums     [ 30–60 s ▾ ]       Platforma [ Visas ▾ ]        │
│   Subtitri   [ Tīrs ▾ ]          Kadrējums [ ●───── ]         │
│                                                               │
│                     ┌───────────────────┐                     │
│                     │   Taisi klipus    │                     │
│                     └───────────────────┘                     │
│                                                               │
│   RTX 4070 · 60 min video ≈ 9 min · brīvi 340 GB              │
└───────────────────────────────────────────────────────────────┘
```

**Prasības:**

- Nomešanas zona pieņem failus visā logā, ne tikai taisnstūrī.
- Sešas ātrās kontroles, ne vairāk. Katra kartējas uz reāliem `Settings` laukiem.
- Aparatūras rinda apakšā ir vienmēr redzama — tā ir godīguma paziņojums no [24.7](#247-gaidīšana-ir-godīga).
- Tukšais stāvoklis pirmajā palaišanā piedāvā paraugvideo ([E1-F05](#e1--uzstādīšana-un-pirmā-palaišana)).
- Saites ielīmēšana rāda video nosaukumu un ilgumu pirms sākšanas.

---

### 26.2. Apstrādes skats

**Mērķis:** lietotājs zina, kas notiek, un tic, ka tas beigsies.

```
┌───────────────────────────────────────────────────────────────┐
│  Podkāsts S03E12.mp4 · 1:27:14                     [Atcelt]   │
│                                                               │
│  ████████████████████░░░░░░░░░░░░░░░░  54 %                    │
│  Atlicis ≈ 5 min                                              │
│                                                               │
│  ✓ Sagatavo video              1:12                           │
│  ✓ Atpazīst runu               4:31                           │
│  ✓ Atšķir runātājus            0:48                           │
│  ● Meklē reakcijas             1:20 ▓▓▓▓▓▓░░░░  61 %          │
│  ○ Izvēlas momentus                                           │
│  ○ Vērtē klipus                                               │
│  ○ Kadrē                                                      │
│  ○ Renderē                                                    │
│                                                               │
│  ▸ Sīkāk                                                      │
└───────────────────────────────────────────────────────────────┘
```

**Prasības:**

- Posmu nosaukumi cilvēka valodā; iekšējie nosaukumi (`asr`, `diarize`) neparādās virsmā.
- Pabeigtie posmi rāda faktisko laiku — tas veido uzticību aplēsei.
- "Sīkāk" atklāj neapstrādāto konsoli ar pilnu stderr.
- Atcelšana ir tūlītēja un tīra: nepabeigtie faili tiek notīrīti, kontrolpunkti paliek atsākšanai.
- Ja posms neziņo progresu > 30 s, tas rāda starpstāvokli ("Apstrādā 2340 no 5100 logiem").

---

### 26.3. Pārskats

**Mērķis:** izlemt par 15 klipiem 10 minūtēs.

```
┌───────────────────────────────────────────────────────────────┐
│  ← Bibliotēka   Podkāsts S03E12   12 klipi · 8 apstiprināti   │
│                                                               │
│  [Visi] [Jauni 4] [Apstiprināti 8] [Atmesti 0]   Kārtot ▾     │
│  ─────────────────────────────────────────────────────────    │
│                                                               │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐                 │
│  │      │ │      │ │      │ │      │ │      │                 │
│  │  ▶   │ │  ▶   │ │  ▶   │ │  ▶   │ │  ▶   │                 │
│  │      │ │      │ │      │ │      │ │      │                 │
│  │  92  │ │  87  │ │  84  │ │  81  │ │  78  │                 │
│  └──────┘ └──────┘ └──────┘ └──────┘ └──────┘                 │
│   0:42 ✓   0:38 ✓   0:51 ✓   0:29 ✓   0:47                    │
│   "Kāpēc…" "Trīs…"  "Neviens" "Es…"    "Tas…"                 │
│                                                               │
│  ──────────────────────────────────────────────────────────   │
│  ▸ Analīze — interešu līkne un kandidāti                      │
│                                                               │
│  [Apstiprināt visus > 80]   [Eksportēt apstiprinātos (8)]     │
└───────────────────────────────────────────────────────────────┘
```

**Prasības:**

- Uzvirzīšanās atskaņo klusu cilpu no klipa spēcīgākā punkta, nevis no sākuma.
- Vērtējuma nozīmīte ir noklikšķināma un atver izklājumu ([26.4](#264-vērtējuma-izklājums)).
- Statusa atzīme ir tieši uz kartes, ne izvēlnē.
- Partijas darbības apakšā ir vienmēr redzamas; skaitlis atjaunojas dzīvi.
- 30 klipi ritinās bez aiztures (virtualizēts saraksts).
- Ģimenes klipi ([E4-F07](#e4--momentu-atlase-un-analīze)) rāda mazu "+2 versijas" nozīmīti.

---

### 26.4. Vērtējuma izklājums

**Mērķis:** lietotājs var nepiekrist uz pierādījuma pamata. Šis ir mūsu diferenciācijas vizuālais izpausme.

```
┌───────────────────────────────────────────────────────────────┐
│  Vērtējums 87                                          [×]    │
│                                                               │
│  Saturs (AI)          8.2 / 10   ████████░░   ×0.40   → 32.8  │
│  Reakcijas            9.1 / 10   █████████░   ×0.25   → 22.8  │
│  Enerģija             7.4 / 10   ███████░░░   ×0.15   → 11.1  │
│  Vizuālais (AI)       7.9 / 10   ███████░░░   ×0.20   → 15.8  │
│                                                    ───────    │
│                                                       82.5    │
│  Korekcijas                                                   │
│  + Platformas svars (Reels)                           +4.5    │
│                                                    ───────    │
│                                                        87     │
│                                                               │
│  ── Kas nostrādāja ─────────────────────────────────────      │
│  Smiekli        0:12  0:34  0:51      (PANNs, 2 detektori)    │
│  Runātāja maiņa 0:08  0:21  0:44                              │
│  Enerģijas pīķis 0:33                                         │
│                                                               │
│  ── Kāpēc nav vairāk ───────────────────────────────────      │
│  Nav vizuālas darbības šajā logā (kanāls 0.0)                 │
└───────────────────────────────────────────────────────────────┘
```

**Prasības:**

- Katrs laika zīmogs ir noklikšķināms un pārlec uz to vietu atskaņotājā.
- Katra korekcija rāda savu iemeslu. Humora korroborācijas atlaide tiek nosaukta tieši: *"LLM vērtēja humoru 8/10; smiekli netika atklāti → −40 %"*.
- Trūkstošs ieguldījums (Ollama režīmā T2 vizuālā caurlaide netiek izpildīta) tiek rādīts kā **"nav mērīts"** ar pelēku joslu, nevis kā `0.0`.
- Sadaļa "Kāpēc nav vairāk" nosauc, kas šim klipam pietrūka — tas ir tas, kas ļauj lietotājam mācīties, ko rīks meklē.

---

### 26.5. Klipu redaktors

**Mērķis:** salabot vienu lietu 60 sekundēs.

```
┌───────────────────────────────────────────────────────────────┐
│  ← Pārskats   Klips 3   0:51             [Atsaukt] [Renderēt] │
│  ┌─────────────────────┬───────────────────────────────────┐  │
│  │                     │  Kadrējums                        │  │
│  │                     │  ○ Seja ●──── Viss kadrs          │  │
│  │     9:16            │  Režīms  [ Griezt ▾ ]             │  │
│  │  priekšskatījums    │  ──────────────────────────────   │  │
│  │                     │  Subtitri                         │  │
│  │   ┌─────────────┐   │  Presets [ Tīrs ▾ ]  [Rediģēt]    │  │
│  │   │ subtitri    │   │  ──────────────────────────────   │  │
│  │   └─────────────┘   │  Temps                            │  │
│  │  ····drošā zona···· │  ○ Nemainīt ● Maigs ○ Ciešs       │  │
│  │                     │  Izgriež 4.2 s → 0:47             │  │
│  └─────────────────────┴───────────────────────────────────┘  │
│                                                               │
│  ⏱ 0:00        0:15        0:30        0:45        0:51       │
│  ▂▃▅▇▅▃▂▁▂▃▅▇▇▅▃▂▁▁▂▃▅▇▅▃▂▁▂▃▅▇▅▃▂▁▂▃▅▇▇▅▃▂▁▂▃▅  audio      │
│  │  kāpēc  es  domāju  ka  tas  nav  taisnība  jo  │  vārdi   │
│  │    ☺           ☺              ☺                 │  notikumi│
│  │  ✂         ✂             ✂                      │  griezumi│
│  │  ▲                    ▲                         │  punch   │
│  [◀]                                            [▶]           │
└───────────────────────────────────────────────────────────────┘
```

**Prasības:**

- Priekšskatījums ir vienmēr redzams un atsvaidzinās < 300 ms pēc jebkuras izmaiņas.
- Drošā zona ir vizuāli iezīmēta priekšskatījumā.
- Katrs `✂` uz griezumu celiņa ir atsevišķi noklikšķināms, lai to izslēgtu; izslēgtais paliek redzams pelēks.
- Tempa izvēle rāda konkrētu rezultātu ("Izgriež 4.2 s → 0:47") pirms pielietošanas.
- Vilkšana atjaunina lokālo stāvokli `onMove`, saglabā vienreiz `onUp` — obligāts modelis katram jaunam slīdnim.
- "Renderēt" rāda, cik ilgi tas prasīs, pirms sākuma.

---

### 26.6. Bibliotēka

```
┌───────────────────────────────────────────────────────────────┐
│  Bibliotēka                          [Meklēt…]  [+ Projekts]  │
│                                                               │
│  Projekti:  [Visi] [Klients A 12] [Klients B 8] [Mans 24]     │
│  ─────────────────────────────────────────────────────────    │
│                                                               │
│  ┌────┐ Podkāsts S03E12          12 klipi · 8 ✓    4.2 GB     │
│  │▓▓▓▓│ vakar 19:42 · 1:27:14                      [⋯]        │
│  └────┘                                                       │
│  ┌────┐ Straume 08-19             6 klipi · 6 ✓    8.1 GB     │
│  │▓▓▓▓│ 19. aug · 5:12:03                          [⋯]        │
│  └────┘                                                       │
│  ┌────┐ Intervija ar Anniņu       neizdevās posmā "Kadrē"     │
│  │▓▓▓▓│ 18. aug · 0:48:19         [Atsākt]         [⋯]        │
│  └────┘                                                       │
│                                                               │
│  Aizņemts 61 GB no 340 GB brīvi        [Atbrīvot vietu]       │
└───────────────────────────────────────────────────────────────┘
```

**Prasības:**

- Neizdevies darbs ir redzams ar posma nosaukumu un atsākšanas pogu — nekad nepazūd.
- Izmērs uz katra darba ir redzams, jo tas ir tas, kas liek lietotājam tīrīt.
- Projekta cilnes ar skaitītājiem; "Visi" vienmēr pirmais.
- `⋯` izvēlne: pārdēvēt, pārvietot uz projektu, atvērt mapi, dublēt iestatījumus jaunam darbam, dzēst.

---

### 26.7. Rinda

```
┌───────────────────────────────────────────────────────────────┐
│  Rinda                        [Apturēt visu]  ≈ 1 h 47 min    │
│                                                               │
│  ● Klients A — ep14.mp4        Renderē      82 %   ≈ 2 min    │
│  ○ Klients A — ep15.mp4        Gaida             ≈ 11 min  ⋮  │
│  ○ Klients B — vebinārs.mp4    Gaida             ≈ 24 min  ⋮  │
│  ✗ Klients C — bojāts.mp4      Neizdevās: nav audio  [Sīkāk]  │
│  ○ Straume 08-21.mp4           Gaida             ≈ 70 min  ⋮  │
│                                                               │
│  ☑ Neļaut datoram aizmigt      ☑ Paziņot, kad pabeigts        │
└───────────────────────────────────────────────────────────────┘
```

**Prasības:**

- Neizdevies darbs paliek sarakstā ar iemeslu un netraucē pārējiem.
- Vilkšana pārkārto gaidošos.
- Kopējā aplēse atjaunojas pēc katra pabeigtā darba.

---

### 26.8. Iestatījumi

```
┌───────────────────────────────────────────────────────────────┐
│  Iestatījumi          [Meklēt iestatījumu…]   3 mainīti ▾     │
│  ┌─────────────┬───────────────────────────────────────────┐  │
│  │ Profili     │  Klipi                                    │  │
│  │ Klipi     ● │                                           │  │
│  │ Subtitri    │  Cik klipu           [ Auto        ▾ ]    │  │
│  │ Kadrējums   │  Mērķa garums        [ 45 s        ⊸ ] •  │  │
│  │ Skaņa       │  Minimālais garums   [ 20 s        ⊸ ]    │  │
│  │ Teksti      │  Maksimālais garums  [ 90 s        ⊸ ]    │  │
│  │ Eksports    │                                           │  │
│  │ ─────────── │  ▸ Padziļinātie iestatījumi (9)           │  │
│  │ Vērtēšana   │                                           │  │
│  │ Veiktspēja  │                                           │  │
│  │ Privātums   │                                           │  │
│  │ Par         │                                           │  │
│  └─────────────┴───────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────┘
```

**Prasības:**

- `•` atzīme pie katras kontroles, kas atšķiras no noklusējuma.
- "3 mainīti" ir noklikšķināms saraksts ar atgriešanu pa vienam.
- Meklēšana atrod kontroli arī padziļinātajā līmenī un to izceļ.
- Katra kontrole rāda paskaidrojumu uzvirzoties, ne tikai nosaukumu.
- Panelis joprojām tiek ģenerēts no `settings_schema.py` — līmenis ir jauns lauks shēmā, nevis atsevišķs saraksts saskarnē.

---

## 27. Vizuālā valoda

### 27.1. Pamatnostādne

Rīks video veidotājiem. Tas nozīmē: **tumšs pēc noklusējuma**, jo tāda ir katra montāžas programma un tāds ir konteksts, kurā skatās video; **zema piesātinājuma saskarne**, lai saturs, nevis hroms, būtu spilgtākais ekrānā; **viena akcenta krāsa**, ko nelieto nekur, kur tā nenozīmē darbību.

### 27.2. Krāsu marķieri

Definēti kā CSS pielāgotās īpašības uz saknes elementa — kā jau dara esošā tēmu sistēma.

**Virsmas (tumšā tēma)**

| Marķieris | Vērtība | Lietojums |
|---|---|---|
| `--bg-base` | `#0D0F12` | lietotnes fons |
| `--bg-raised` | `#15181D` | kartes, paneļi |
| `--bg-overlay` | `#1D2128` | modāļi, izvēlnes |
| `--bg-inset` | `#0A0C0E` | ievadlauki, laika ass |
| `--border` | `#262B33` | atdalītāji |
| `--border-strong` | `#39404A` | fokusētas malas |

**Teksts**

| Marķieris | Vērtība | Kontrasts pret `--bg-base` |
|---|---|---|
| `--text-primary` | `#E8EBEF` | 14.8:1 |
| `--text-secondary` | `#9BA3AF` | 6.9:1 |
| `--text-muted` | `#6B7280` | 4.6:1 |

**Akcenti**

| Marķieris | Vērtība | Nozīme |
|---|---|---|
| `--accent` | `#4F8CFF` | primārā darbība, aktīvais stāvoklis |
| `--accent-hover` | `#6B9EFF` | uzvirzīšanās |
| `--success` | `#3DD68C` | apstiprināts, pabeigts |
| `--warning` | `#F0B429` | brīdinājums, degradēts režīms |
| `--danger` | `#F0616D` | kļūda, dzēšana |

**Vērtējuma skala** — nepārtraukta, nevis diskrēta:

| Diapazons | Krāsa | Marķieris |
|---|---|---|
| 90–100 | `#3DD68C` | `--score-excellent` |
| 75–89 | `#8FD14F` | `--score-good` |
| 60–74 | `#F0B429` | `--score-fair` |
| < 60 | `#8B95A3` | `--score-weak` |

**Kanālu krāsas** interešu līknei un izklājumam — atšķiramas arī daltonisma gadījumā (pārbaudītas pret protanopiju un deuteranopiju):

`heatmap` `#F0616D` · `dynamics` `#F0B429` · `events` `#3DD68C` · `turns` `#4F8CFF` · `arousal` `#B57BFF` · `scenes` `#4FD1D9` · `lexical` `#FF9F5A` · `visual` `#E85AC8`

**Gaišā tēma** definē tos pašus marķierus ar apgrieztām lomām. Neviena krāsa netiek definēta tikai vienā tēmā.

### 27.3. Tipogrāfija

| Loma | Fonts | Izmērs / augstums | Svars |
|---|---|---|---|
| Ekrāna virsraksts | Inter | 24 / 32 | 600 |
| Sadaļas virsraksts | Inter | 17 / 24 | 600 |
| Pamatteksts | Inter | 14 / 20 | 400 |
| Sekundārais | Inter | 13 / 18 | 400 |
| Etiķete | Inter | 12 / 16 | 500 |
| Skaitlis / laiks | JetBrains Mono | 13 / 18 | 500 |
| Vērtējuma nozīmīte | Inter | 20 / 24 | 700 |

**Noteikumi:**
- Visi laiki, ilgumi, izmēri un koordinātas — monospace. Skaitlis, kas maināms, nedrīkst lēkāt.
- Sistēmas fonta atkāpšanās ir obligāta katrā kaudzē.
- Nekad vairāk par trim izmēriem vienā skatā.

### 27.4. Atstarpes un ģeometrija

Bāzes vienība **4 px**. Atļautie soļi: 4, 8, 12, 16, 24, 32, 48, 64.

| Elements | Rādiuss |
|---|---|
| Ievadlauks, poga | 6 px |
| Karte, panelis | 10 px |
| Modālis | 14 px |
| Video sīktēls | 8 px |
| Nozīmīte | pilnas noapaļošanas |

**Ēnas** tikai slāņa nošķiršanai, nekad dekorācijai: `0 1px 3px rgba(0,0,0,.4)` paceltiem elementiem, `0 8px 32px rgba(0,0,0,.5)` modāļiem.

### 27.5. Režģis

- **Sānjosla:** 220 px fiksēta; sabrūk uz 56 px ikonu joslu zem 1100 px.
- **Saturs:** elastīgs, maksimālais lasāmais platums 1280 px centrēts.
- **Klipu režģis:** `repeat(auto-fill, minmax(180px, 1fr))`, 16 px atstarpe.
- **Redaktors:** priekšskatījums un panelis 60/40, laika ass pilnā platumā apakšā.
- **Minimālais loga izmērs:** 1024 × 700. *Pašlaik `tauri.conf.json` nosaka `minWidth: 900, minHeight: 620` pie noklusētā 1200 × 800 — sānjosla un redaktora 60/40 dalījums pie 900 px nesader, tāpēc minimums ceļas.*

---

## 28. Komponentu bibliotēka

Komponenti, kas jāizveido vai jāpārbūvē. Katrs ir atkārtoti lietojams; neviens nav vienreizējs.

| Komponents | Kur lietots | Kritiskā prasība |
|---|---|---|
| `ClipCard` | Pārskats, Bibliotēka | Kluss priekšskatījums uzvirzoties; nepārslogo GPU ar 30 kartēm |
| `ScoreBadge` | Visur, kur ir vērtējums | Krāsa no skalas; vienmēr noklikšķināma |
| `ScoreBreakdown` | Klipa skats | Katrs laika zīmogs pārlec; trūkstošie ieguldījumi ≠ nulle |
| `StageProgress` | Apstrāde, Rinda | Godīgs ETA; nekad nesasalst bez teksta |
| `Timeline` | Redaktors | Vairāki slāņi; vilkšana saglabā `onUp` |
| `PreviewPlayer` | Redaktors, Klipa skats | Atrisina identiski renderim |
| `SettingControl` | Iestatījumi | Ģenerēts no shēmas; rāda diff pret noklusējumu |
| `PresetPicker` | Studija, Redaktors | Vizuāls priekšskatījums, ne tikai nosaukums |
| `FramingSlider` | Studija, Redaktors | Miniatūras abos galos; `0.0` ir derīgs |
| `DropZone` | Studija | Pieņem visu logu |
| `ErrorPanel` | Visur | Cēlonis + darbība + tehniskais aiz atvēruma |
| `EmptyState` | Katra vieta | Tieši viena skaidra darbība |
| `QueueRow` | Rinda | Vilkšanas pārkārtošana; neveiksme nebloķē |
| `InterestCurve` | Analīze | Kanāli atsevišķi pārslēdzami |
| `BrandKitCard` | Iestatījumi | Priekšskatījums ar reālu subtitru paraugu |
| `ConfirmDialog` | Dzēšana, pārrakstīšana | Nosauc konkrētās sekas, ne "Vai esat pārliecināts?" |

**Stāvokļu prasība:** katram interaktīvajam komponentam ir definēti visi seši stāvokļi — noklusējums, uzvirzīšanās, fokuss, aktīvs, atspējots, ielāde. Nav izlaišanas.

---

## 29. Kustība un atgriezeniskā saite

### 29.1. Ilgumi

| Kustība | Ilgums | Līkne |
|---|---|---|
| Uzvirzīšanās | 120 ms | `ease-out` |
| Modāļa atvēršana | 200 ms | `cubic-bezier(.16,1,.3,1)` |
| Skata pāreja | 240 ms | `cubic-bezier(.16,1,.3,1)` |
| Paneļa izvēršana | 180 ms | `ease-in-out` |
| Progresa atjaunināšana | 400 ms | `linear` |

### 29.2. Noteikumi

1. **Neko neanimēt, kas notiek biežāk par 10 reizēm sekundē.** Progresa josla interpolē; skaitlis atjaunojas soļos.
2. **Vilkšana ir tūlītēja.** Nekādas pārejas uz elementu, ko lietotājs velk.
3. **`prefers-reduced-motion` izslēdz visu, izņemot krāsu pārejas.**
4. **Nav nekāda dekoratīva loading spinner tur, kur var rādīt reālu progresu.**
5. **Skeleta stāvokļi, nevis tukši ekrāni**, ielādējot bibliotēku vai klipu režģi.

### 29.3. Atgriezeniskā saite darbībām

| Darbība | Atbilde |
|---|---|
| Klips apstiprināts | Karte iegūst zaļu malu, statuss mainās; nav modāļa |
| Eksports sākts | Uzpeldošs paziņojums ar progresu, ne bloķējošs dialogs |
| Eksports pabeigts | Paziņojums ar pogu "Atvērt mapi" |
| Iestatījums mainīts | Diff atzīme parādās uzreiz; nav "Saglabāt" pogas |
| Darbība neizdevās | Kļūdas panelis vietā, kur darbība sākās, nevis globāls banner |
| Neatgriezeniska darbība | Apstiprinājums, kas nosauc sekas ("Dzēsīs 12 klipus un 4.2 GB") |

---

## 30. Pieejamība un lokalizācija

### 30.1. Pieejamības prasības

| # | Prasība | Līmenis |
|---|---|---|
| A11Y-1 | Kontrasts ≥ 4.5:1 tekstam, ≥ 3:1 saskarnes elementiem | `P0` |
| A11Y-2 | Katra darbība sasniedzama ar tastatūru; loģiska tab secība | `P0` |
| A11Y-3 | Redzams fokusa indikators visur, ≥ 2 px, kontrasts ≥ 3:1 | `P0` |
| A11Y-4 | Krāsa nekad nav vienīgais informācijas nesējs (statuss nes arī ikonu un tekstu) | `P0` |
| A11Y-5 | ARIA etiķetes ikonu pogām; `aria-live` progresam un kļūdām | `P1` |
| A11Y-6 | `prefers-reduced-motion` respektēts | `P1` |
| A11Y-7 | Saskarne lietojama pie 200 % mērogojuma bez horizontālas ritināšanas | `P1` |
| A11Y-8 | Video priekšskatījumi nekad neatskaņo skaņu automātiski | `P0` |
| A11Y-9 | Gaišā tēma ir pilnvērtīga, nevis otrās šķiras | `P1` |

### 30.2. Lokalizācija

*Pieņemšanas kritēriji:*
- Viss saskarnes teksts ir resursu failos, nevis kodā, jau no v1.0 — pat ja sākotnēji ir tikai angļu valoda.
- Izkārtojumi iztur 40 % teksta pagarinājumu bez pārplūdes.
- Datumi, laiki un skaitļi tiek formatēti pēc lokāles.
- Valodas: angļu (v1.0), latviešu un vēl divas pēc pieprasījuma (v1.1).
- Subtitru valoda ir neatkarīga no saskarnes valodas.

---

# D daļa — Realizācija

## 31. Tehniskās prasības un arhitektūras izmaiņas

Šī sadaļa nosaka, kas jāmaina esošajā arhitektūrā, lai B un C daļas prasības būtu realizējamas. Tā nav dizaina specifikācija — tā ir saraksts ar vietām, kur pašreizējā struktūra ir šķērslis.

### 31.1. Kas paliek nemainīgs

Šīs izvēles ir pareizas un netiek pārskatītas:

- **Trīs procesi, viens kontroles virziens** (React → Rust → Python).
- **Rust slānis bez produkta loģikas.** Viss, ko gribētos unit-testēt, paliek Python.
- **Frontend bez produkta loģikas.** Tas renderē to, ko sānvads ziņo.
- **Artefakti uz diska ir patiesības avots.** SQLite tikai reģistrē, kam vajadzētu eksistēt.
- **Astoņu posmu kontrolpunktu ķēde** ar trim invalidēšanas noteikumiem.

### 31.2. Nepieciešamās izmaiņas

---

**T1 · Darba rindas vadītājs** — bloķē [E2-F04](#e2--bibliotēka-projekti-un-darba-rinda)

Pašlaik Rust slānis palaiž vienu sānvadu uz `run_job` izsaukumu. Vajag noturīgu rindu.

*Prasības:*
- Rindas stāvoklis SQLite, ne atmiņā — tam jāpārdzīvo lietotnes restarts.
- Rust puses vadītājs palaiž nākamo darbu pēc iepriekšējā iziešanas, neatkarīgi no iziešanas koda.
- Viens darbs vienlaikus (GPU ir viena resursa vienība); paralēlisms ir nākotnes jautājums, nevis v1.0.
- Atcelšana nogalina procesu tīri un atstāj kontrolpunktus neskartus.
- Jauni Tauri notikumi: `queue_changed`, `job_started`, `job_finished`, `job_failed`.

---

**T2 · Progresa protokola papildinājums** — bloķē [E1-F06](#e1--uzstādīšana-un-pirmā-palaišana)

> **Pārskatīts v1.2.** v1.1 pieprasīja jaunu protokolu. **Tas jau eksistē:** konveijers izstaro `{event:'progress', stage, fraction, message}`, un `App.tsx:96-104` to patērē per-posma progresa joslām. Nav ko pārbūvēt.

*Atlikušās prasības:*
- Posmu īpatsvari kopējā laikā tiek mērīti un glabāti `hardware_profile.json`; ETA rēķinās no tiem, nevis no fiksētiem skaitļiem.
- Posmu nosaukumu kartējums uz cilvēka valodu (`asr` → "Atpazīst runu") dzīvo **vienā vietā**, ne izkaisīts pa komponentiem.
- Posmi, kas šobrīd ziņo `fraction: -1` (nezināms), tiek pārskatīti — kur iespējams, tie ziņo pabeigto vienību skaitu.
- Neviens posms nedrīkst klusēt ilgāk par 30 s.

---

**T3 · Priekšskatījuma renderēšanas ceļš** — bloķē [E6-F02](#e6--klipu-redaktors), [E7-F01](#e7--subtitri-stils-un-zīmola-komplekti)

Šodien redaktora priekšskatījums ir aptuvenojums, ko zīmē frontend. Tam jākļūst par to pašu, ko redzēs izvadē.

*Prasības:*
- Zema izšķirtspējas (360 px) ffmpeg priekšskatījums ar identisku filtru grafu, ģenerēts pēc pieprasījuma un kešots.
- Atsvaidzināšanās < 300 ms; ilgākā gadījumā rāda iepriekšējo ar ielādes indikatoru, nevis tukšumu.
- **Vienotā atrisināšana:** `resolve_pacing()` modelis tiek paplašināts uz `resolve_framing()`, `resolve_caption_style()`, `resolve_audio()`. Katra vērtība, ko redz gan priekšskatījums, gan renderis, tiek atrisināta tieši vienā funkcijā.
- Tests, kas izsauc abas puses ar tiem pašiem ievaddatiem un krīt uz jebkuras atšķirības.

---

**T4 · Iestatījumu shēmas paplašinājums** — bloķē [E12-F01](#e12--iestatījumi-un-profili)

*Prasības:*
- `settings_schema.py` katram ierakstam iegūst `level` (`quick` / `standard` / `advanced`), `help` (viens teikums) un `affects` (posmu saraksts).
- `validate_schema()` divvirzienu pārbaude tiek papildināta: katrai kontrolei jābūt līmenim un palīdzības tekstam.
- `affects` tiek izmantots [E12-F05](#e12--iestatījumi-un-profili) ietekmes rādītājam un **atvasināts no pirkstu nospiedumu loģikas**, nevis uzturēts kā atsevišķs saraksts, ko var aizmirst.

---

**T5 · Profilu un zīmola komplektu slānis** — bloķē [E12-F02](#e12--iestatījumi-un-profili), [E7-F05](#e7--subtitri-stils-un-zīmola-komplekti)

Pašreizējais trīs slāņu iestatījumu modelis (globālie → darba momentuzņēmums → klipa pārraksti) iegūst ceturto.

```
Iebūvētie noklusējumi
   └─ Profils (nosaukts Settings koks + zīmola komplekta atsauce)   ← jauns
        └─ Darba momentuzņēmums (nemainīgs pēc izveides)
             └─ Klipa pārraksti (clip_edits.json)
```

*Prasības:*
- Profils **sēj** darba momentuzņēmumu; profila maiņa vēlāk neietekmē esošos darbus (2. noteikums paliek spēkā).
- Zīmola komplekts ir atsevišķa vienība, uz kuru profils atsaucas — tā ka viens komplekts var kalpot vairākiem profiliem.
- `profiles.json` un `brand_kits.json` `PUBLIKCLIP_HOME`; abi ar shēmas versiju un iecietīgu deserializāciju, kā `_build`.

---

**T6 · Split-screen renderēšanas ceļš** — bloķē [E8-F04](#e8--kadrēšana-un-kompozīcija)

Pašreizējais grafs `sendcmd → crop@c → scale/pad → setsar → subtitles → loudnorm` nevar būt parametrizēts uz diviem dzīviem reģioniem.

*Prasības:*
- Jauns `-filter_complex` ceļš ar diviem neatkarīgiem crop atzariem un overlay kompozīciju.
- Trajektorijas formāts paplašināts uz vairākiem reģioniem: `regions: [{id, frames, content_w, content_h}]`; viena reģiona gadījums paliek pilnībā saderīgs ar esošo.
- Atsevišķs kods, nevis nosacījumi esošajā funkcijā — abi ceļi tiek testēti neatkarīgi.
- Renderēšanas laiks ≤ 1,6× no viena reģiona.

---

**T7 · Vizuālās darbības kanāls** — bloķē [E4-F05](#e4--momentu-atlase-un-analīze)

*Prasības:*
- Aprēķināts `ingest` vai `candidates` posmā ar ffmpeg statistiku, nevis atsevišķu CV modeli — nedrīkst pievienot GB atkarības.
- Jauna sērija `curves.json`; jauns svars `Settings.curve`; jauna krāsa vizualizācijā.
- < 20 vārdu atmešanas noteikums kļūst nosacīts: atmet tikai tad, ja arī vizuālās darbības kanāls ir vājš.
- Mērījuma tests uz marķēta gameplay parauga ar ≥ 60 % sakritību.

---

**T8 · Subtitru drošā zona** — bloķē [E7-F07](#e7--subtitri-stils-un-zīmola-komplekti)

*Prasības:*
- `captions/ass.py` vairs nelieto fiksētu `MarginV` 1080×1920 kanvā; novietojums tiek rēķināts no faktiskā `content_w`/`content_h` un letterbox joslu augstuma.
- Drošās zonas robežas tiek atgrieztas redaktoram, lai priekšskatījums tās rādītu.
- Platformu UI drošās zonas ir dati, nevis konstantes kodā.
- Parametrizēts tests pār `gameplay_amount ∈ {0, 0.25, 0.5, 0.75, 1.0}`, kas krīt, ja subtitri iziet ārpus redzamā laukuma.

---

**T9 · Publicēšanas integrāciju slānis** — bloķē [E10-F03](#e10--eksports-un-publicēšana)

*Prasības:*
- Viena saskarne (`Publisher`) ar realizācijām katrai platformai — tāpat kā `llm.py` divi backendi aiz vienas saskarnes.
- Akreditācijas dati OS glabātuvē (Keychain / Credential Manager), nekad failā atklātā tekstā.
- Katrai platformai atsevišķi noteiktas kļūdu klases; nezināma kļūda degradējas uz eksportu.
- Platformas API izmaiņas nedrīkst avarēt lietotni — tas pats "kāpņu" modelis, ko lieto Instagram metrikām.

---

**T10 · Kodējums un rakstīšanas īpašumtiesības** — bloķē [E14-F06](#e14--uzticamība-kļūdas-un-atbalsts)

> **Pārorientēts v1.2.** Atomiskums **jau ir atrisināts**: `jobs/queue.py:157` `_atomic_write_json()` raksta pagaidu failā un pārsauc; `edits/store.py:31-33` dara to pašu; `config.py:428,451` arī. Īstās problēmas ir citas divas.

*Prasība A — kodējums (nepilnība E3, `P0`):*
- **34 `read_text()` / `write_text()` izsaukumi ārpus `vendor/` neuzdod `encoding="utf-8"`.** Vissvarīgākie: `edits/store.py:24,32` (klipu redaktora stāvoklis), `edits/render_clip.py` (8 vietas, ieskaitot trajektorijas un `sendcmd` failu), `cli.py:233,238,266,270`, `candidates/stage.py:220`, `events/stage.py:167`.
- Mājas noteikums to jau aizliedz, un `PYTHONUTF8=1` `quiet_command` to maskē darbvirsmas lietotnē — bet ne CLI lietošanā un ne tad, ja vide to nepārmanto.
- Katrs izsaukums iegūst tiešu `encoding="utf-8"`.
- **Lint noteikums vai tests**, kas krīt, ja jauns bez-kodējuma teksta izsaukums parādās ārpus `vendor/`. Bez tā skaits atkal aug.

*Prasība B — divi rakstītāji (nepilnība E5, `P1`):*
- `edits/store.py` dokstrings apstiprina: *"The app writes this file directly (Rust fs) and the pipeline reads it at render-clip time."* Diviem procesiem divās valodās ir rakstīšanas tiesības uz `clip_edits.json`.
- Rust puses rakstīšanai jābūt tikpat atomārai (pagaidu fails + pārsaukšana) un UTF-8, vai — labāk — tai jāiet caur `save_clip_edits` sānvada izsaukumu, atstājot vienu rakstītāju.
- Tests, kas simulē vienlaicīgu rakstīšanu un apliecina, ka fails paliek derīgs.

*Prasība C — jau izpildītais paliek:*
- Bojāts JSON tiek uzskatīts par trūkstošu un noved pie posma atkārtotas izpildes, nevis avārijas (`edits/store.py:load()` to jau dara ar `except (json.JSONDecodeError, OSError)`).

---

**T11 · Būves un izplatīšanas konveijers** — bloķē [E16](#e16--izplatīšana-licences-un-kopiena)

*Prasības:*
- `bundle.targets` ietver `nsis` un `dmg`.
- CI būvē abas platformas, paraksta, notarizē un publicē izlaišanu ar avota arhīvu.
- `prepare-resources.mjs` izslēgšanas saraksts paliek spēkā — īpaši `wav2vec2_checkpoints`, kas ir 700+ MB un nekad nedrīkst nokļūt paketē.
- Tauri updater atslēgas glabājas CI noslēpumos.
- Būves artefakta izmērs tiek pārbaudīts pret slieksni; pārsniegums bloķē izlaišanu.

---

**T12 · Testu paplašinājums**

Pašreizējie 244 testi paliek. Jāpievieno:

| Testu grupa | Ko pārbauda | Kāpēc |
|---|---|---|
| `test_preview_parity.py` | Priekšskatījums un renderis dod identiskas atrisinātās vērtības | 4. dizaina princips |
| `test_queue_persistence.py` | Rinda pārdzīvo restartu; kļūda nebloķē | T1 |
| `test_caption_safe_area.py` | Subtitri paliek redzamajā joslā pie visiem `gameplay_amount` | T8 |
| `test_profiles.py` | Profila sēšana; darba momentuzņēmuma neaizskaramība | T5 |
| `test_visual_channel.py` | Vizuālā kanāla korelācija ar marķētu paraugu | T7 |
| `test_splitscreen_render.py` | Divu reģionu grafs; viena reģiona regresija | T6 |
| `test_atomic_writes.py` | Pārtraukta rakstīšana neatstāj bojātu failu | T10 |
| `test_error_catalog.py` | Katrai zināmajai kļūdu klasei ir ieraksts ar darbību | E14-F01 |
| `test_schema_levels.py` | Katrai kontrolei ir līmenis un palīdzība | T4 |
| `test_text_encoding.py` | Neviens `read_text`/`write_text` ārpus `vendor/` nav bez `encoding="utf-8"` | T10-A |
| `test_cancel.py` | Atcelšana nogalina procesu, saglabā kontrolpunktus, notīra starprezultātus | E2-F07 |
| `test_model_specs.py` | Katram `ModelSpec` ir piesaistīts sha256 | E1-F04 |

Pret-dreifēšanas tests `test_every_settings_group_is_read_by_the_pipeline` paliek zaļš visā darba gaitā. Tas ir rupjš, un tas ir tā jēga.

### 31.3. Tehniskais parāds, kas jāatrisina pa ceļam

| # | Parāds | Kur | Kad |
|---|---|---|---|
| TD1 | `App.tsx` (229 rindas) maršrutē 6 skatus ar vienu `useState<View>`; ligzdoti skati (Bibliotēka → Darbs → Klips → Redaktors) tajā neietilpst | frontend | Pirms C daļas |
| TD2 | **`api.ts` noteikums jau pārkāpts** (nepilnība E4): 6 tieši `invoke()` izsaukumi `ClipEditor.tsx:373,378,382,387` un `KeyModal.tsx:26,49`. `api.ts` ir 65 rindas un aptver 11 no 17 Tauri komandām. `types.ts` (338 rindas) kontrakts nav izpildīts izpildlaikā | frontend | v1.0 |
| TD3 | **Precizēts v1.2:** `styles.css` ir 1 342 rindas — pieņemami. Īstais gigants ir **`ClipEditor.tsx` ar 1 175 rindām** vienā komponentē, kas jau tagad ir 22 % no frontenda. [E6](#e6--klipu-redaktors) tam pievieno laika asi, dzīvu priekšskatījumu un subtitru rediģēšanu — bez sadalīšanas tas kļūst neuzturams | frontend | Pirms [E6](#e6--klipu-redaktors) |
| TD4 | `main.rs` (544 rindas) reģistrē 17 komandas plakanā `generate_handler!`; aug lineāri ar funkcijām | Rust | v1.1 |
| TD5 | Vendored kods `vendor/` nav atzīmēts ar augšupējām commit versijām | pipeline | v1.0 (licences dēļ) |
| TD6 | **Jauns:** `insights/calibration.py` ir 908 rindas — lielākais fails konveijerā, lielāks par `cli.py`. [E11-F02](#e11--vērtības-cilpa-un-kalibrācija) tam pievieno divas platformas | pipeline | Pirms [E11-F02](#e11--vērtības-cilpa-un-kalibrācija) |
| TD7 | **Jauns:** `.gitattributes` trūkst; skatīt [E16-F07](#e16--izplatīšana-licences-un-kopiena). Tas bloķē jebkuru kopienas ieguldījumu | repo | Nekavējoties |

---

## 32. Ne-funkcionālās prasības

| ID | Kategorija | Prasība | Mērīšana |
|---|---|---|---|
| NFR-1 | Veiktspēja | Lietotnes palaišana līdz interaktīvai < 3 s | Automatizēts mērījums CI |
| NFR-2 | Veiktspēja | Saskarnes atbilde uz darbību < 100 ms | Manuāls audits katrā izlaišanā |
| NFR-3 | Veiktspēja | Priekšskatījuma atsvaidze < 300 ms | Automatizēts |
| NFR-4 | Veiktspēja | Konveijera budžeti pēc [E13-F03](#e13--veiktspēja-un-resursi) | Veiktspējas testu komplekts |
| NFR-5 | Resursi | Maks. RSS < 6 GB uz 90 min avota | Veiktspējas testi |
| NFR-6 | Resursi | Instalatora izmērs < 150 MB | Būves pārbaude |
| NFR-7 | Uzticamība | Avārijas uz darbu < 2 % | Avāriju atskaites |
| NFR-8 | Uzticamība | Neviens darbs nezaudē datus pēc avārijas | Kaosa tests: nogalināt procesu katrā posmā |
| NFR-9 | Uzticamība | Rinda turpina pēc viena darba neveiksmes | `test_queue_persistence.py` |
| NFR-10 | Drošība | Akreditācijas dati OS glabātuvē, ne failā | Kods + audits |
| NFR-11 | Drošība | Nav tīkla izsaukumu, kas nav privātuma paziņojumā | Tīkla audits izlaišanas kandidātam |
| NFR-12 | Privātums | Mediji nekad neatstāj mašīnu | Arhitektūras invariants + audits |
| NFR-13 | Savietojamība | Windows 10 22H2+, macOS 13+ | Testēšanas matrica |
| NFR-14 | Savietojamība | Darbojas bez GPU | [E13-F02](#e13--veiktspēja-un-resursi) |
| NFR-15 | Uzturamība | Testu pārklājums konveijerā ≥ 70 % | pytest-cov CI |
| NFR-16 | Uzturamība | Nulle dekoratīvu iestatījumu | Pret-dreifēšanas tests |
| NFR-17 | Pieejamība | WCAG 2.1 AA saskarnei | Audits + automatizēts kontrasts |
| NFR-18 | Licences | AGPL atbilstība pilnā apjomā | Juridisks pārskats pirms izlaišanas |

---

## 33. Metrikas un panākumu kritēriji

### 33.1. Ziemeļzvaigzne

> **Nomainīta v1.4** ([D-16](#374-lēmumu-žurnāls)). Iepriekšējā bija *"nedēļā publicēto klipu skaits uz aktīvo lietotāju"*. Tā mērīja **caurlaidību** — cik daudz rīks izlaiž cauri. Bet klipu skaits ir triviāli palielināms, pazeminot slieksni, un rīks, kas ražo divreiz vairāk divreiz vājāku klipu, izskatītos pēc uzlabojuma. Tā ir tieši nepareizā stimulācija produktam, kura mērķis ir maksimizēt vērtību.

**Noturības svērta izvade uz avota stundu, un tās izmaiņa laikā.**

```
                 Σ (klipa noturība × klipa skatījumi)
    vērtība  =  ──────────────────────────────────────
                        avota stundas
```

Šī metrika krīt, ja **jebkura** produkta daļa ir slikta, un — atšķirībā no iepriekšējās — to nevar apspēlēt ar apjomu:

| Ja tas ir slikts… | …metrika krīt tā |
|---|---|
| Atlase izvēlas nepareizos momentus | Noturība uz klipu krīt |
| Iepakojums ir vājš | Skatījumi krīt, 3 s noturība krīt |
| Redaktors ir neveikls vai eksports sāpīgs | Klipi neiznāk → skaitītājs krīt |
| Slieksnis pazemināts, lai ražotu vairāk | Vidējā noturība krīt → summa neaug |
| Cilpa nemācās | Metrika ir plakana laikā — **un tas ir īstais neveiksmes signāls** |

**Kritiskā daļa ir pēdējā rinda: "un tās izmaiņa laikā".** Absolūtais līmenis ir atkarīgs no nišas, auditorijas lieluma un platformas — starp lietotājiem tas nav salīdzināms. **Slīpums ir.** Produkts, kas strādā, dod lietotājam augošu līkni pār viņa paša bāzlīmeni ([E11-F06](#e11--vērtības-cilpa-un-kalibrācija)).

**Godīgi par šīs metrikas trūkumiem:**
- Tā prasa aizvērtu cilpu — līdz v1.1 to nav ar ko mērīt vispār.
- Platformas algoritma izmaiņas to izkustina neatkarīgi no mums.
- Tā ir slēpta aiz izvēles telemetrijas ([33.6](#336-kā-to-mērīt-nepārkāpjot-privātumu)), tāpēc mūsu redzamība uz to būs daļēja un nosliekta.

Neviens no tiem nav iemesls atgriezties pie klipu skaitīšanas. Slikti izmērīta pareizā metrika ir noderīgāka par precīzi izmērītu nepareizo.

### 33.2. Aktivācija

Pēc [D-15](#374-lēmumu-žurnāls) aktivācijas piltuvei ir divi atsevišķi posmi, un tos nedrīkst jaukt: **vārti** (vai lietotājs izpilda uzstādīšanas soli) un **produkts** (vai viņš pēc tam tiek līdz klipam). Metrika, kas tos apvieno, slēpj, kurš no diviem ir salūzis.

| Metrika | Mērķis v1.0 | Ko tā mēra |
|---|---|---|
| Instalēšana → izpildīti vārti | ≥ 55 % | Cik pieņem līgumu. **Zems skaitlis nav neveiksme** — tā ir mērķauditorijas šaurība ([4.2](#42-ieejas-slieksnis-ir-dizaina-izvēle)) |
| No tiem: Gemini vs Ollama sadalījums | informatīva | Kurš ceļš reāli tiek lietots; nosaka, kur ieguldīt |
| **Vārti → pabeigts pirmais darbs** | **≥ 85 %** | **Šī ir īstā produkta metrika.** Kas iekļuva, tam jātiek cauri |
| Vārti → pirmais eksportēts klips | ≥ 70 % | Vai rezultāts ir tā vērts |
| Laiks no vārtiem līdz pirmajam klipam (mediāna) | < 25 min | Uzstādīšanas laiks netiek skaitīts |
| Atmešana vārtos **Ollama ceļā** | < 40 % | Ja tas ir augsts, [E1-F02](#e1--uzstādīšana-un-pirmā-palaišana) nestrādā |
| Lietotāji, kas atver iestatījumus 1. sesijā | < 30 % | Apgriezta metrika: **zemāks ir labāk**, jo pierāda, ka noklusējumi darbojas ([24.1](#241-noklusējums-ir-produkts)) |

**Kāpēc "instalēšana → pabeigts darbs" vairs nav galvenā metrika.** Ar apzinātiem vārtiem tā mēra divas lietas vienlaikus un padara neiespējamu atšķirt "mūsu auditorija ir šaura" (pieņemts) no "mūsu produkts ir salauzts" (nav pieņemts). Sadalījums to atrisina.

### 33.3. Kvalitāte un cilpas veselība

**Cilpas metrikas (jaunas v1.4) — šīs ir svarīgākās:**

| Metrika | Mērķis | Ko tā atklāj, ja krīt |
|---|---|---|
| Publicēto klipu īpatsvars, kas saskaņoti ar rezultātu | ≥ 80 % | Cilpa ir pārrauta — attiecinājums nestrādā |
| Vērtējuma ↔ noturības korelācija (mediāna pār lietotājiem) | ≥ 0,45 pie n=30 | Prognoze ir troksnis; produkta pamatpieņēmums kļūdains ([R16](#354-vērtības-cilpas-riski)) |
| Korelācijas pieaugums pēc pieņemtas kalibrācijas | ≥ +0,10 | Kalibrācija nemācās neko noderīgu |
| Lietotāji, kas pieņem piedāvāto kalibrāciju | ≥ 50 % | Ieteikumi nav pārliecinoši vai nav saprotami |
| Iepakojuma eksperimenti ar statistiski derīgu rezultātu | ≥ 40 % | [E17](#e17--iepakojuma-eksperimenti) ģenerē troksni, ne zināšanas |
| Klipi virs lietotāja mediānas pēc 6 nedēļām | ≥ 30 % | Cilpa griežas, bet neko neuzlabo |

**Darbplūsmas metrikas (paliek no v1.3):**

| Metrika | Mērķis |
|---|---|
| Klipi, kas eksportēti bez rediģēšanas | ≥ 40 % |
| Klipi, kas atmesti uzreiz | < 25 % |
| Vidējais rediģēšanas laiks uz klipu | < 90 s |
| Restilizācijas, kas zaudē redaktora darbu | 0 |

### 33.4. Uzticamība

| Metrika | Mērķis |
|---|---|
| Darbu pabeigšanas rādītājs | ≥ 95 % |
| Avārijas uz sesiju | < 2 % |
| Kļūdas ar darbojošos risinājumu saskarnē | ≥ 90 % |
| Vidējais laiks līdz atkopšanai pēc neveiksmes | < 2 min |

### 33.5. Noturība

| Metrika | Mērķis |
|---|---|
| Nedēļas noturība (4. nedēļa) | ≥ 40 % |
| Darbi uz aktīvo lietotāju nedēļā | ≥ 2 |
| Lietotāji ar > 1 profilu (P3 signāls) | ≥ 15 % |
| **Lietotāji ar aktīvu cilpu (≥ 15 saskaņotu klipu)** | **≥ 35 % pēc 8 nedēļām** |

Pēdējā rinda ir arī **labākā noturības prognoze**, kāda mums ir: lietotājs ar kalibrētu profilu un vēsturi ir ieguldījis kaut ko, ko konkurents nevar pārnest. Cilpa ir gan produkta vērtība, gan tā vienīgais dabiskais noturēšanas mehānisms — bez abonementa un bez slēgtiem datiem.

### 33.6. Kā to mērīt, nepārkāpjot privātumu

Visas metrikas tiek vāktas **tikai** ar izvēles telemetriju ([E15-F04](#e15--atjauninājumi-privātums-un-telemetrija)), kas ir izslēgta pēc noklusējuma. Tas nozīmē, ka skaitļi būs nepilnīgi un noslieces skarti.

Papildu avoti, kas nav telemetrija:
- Kopienas atgriezeniskā saite (GitHub issues, Discord).
- Strukturētas lietojamības sesijas ar 5–8 lietotājiem pirms katras lielās izlaišanas — tas ir vērtīgāks par jebkuru dashboard šajā mērogā.
- Vietējā statistika, ko lietotājs var apskatīt pats un brīvprātīgi kopīgot.

**Nepieņemamais kompromiss:** metrikas nedrīkst kļūt par iemeslu ieslēgt telemetriju pēc noklusējuma. Produkta 1. īpašība ir svarīgāka par dashboard.

---

## 34. Izlaišanas plāns

### 34.1. Pārskats

| Versija | Fokuss | Saturs | Ilgums |
|---|---|---|---|
| **v0.9 Beta** | Neatliekamie labojumi | Instalatori, kļūdu apstrāde, atcelšana, rinda, higiēna | 4–6 nedēļas |
| **v1.0** | Publiska izlaišana | Darbplūsma pie apjoma: bibliotēka, profili, partijas eksports, redaktors | 8–10 nedēļas |
| **v1.1** | **Cilpa aizveras** | **Publicēšana, 3 platformu metrikas, kalibrācija, iepakojuma eksperimenti** | 8–10 nedēļas |
| **v1.2** | Satura kvalitāte | Split-screen, vizuālais kanāls, zīmola komplekti, presetu bibliotēka | 8–10 nedēļas |
| **v2.0** | Paplašināšana | Lokalizācija, kopienas paplašinājumi, jaunas platformas | atvērts |

> **Pārkārtots v1.4** ([D-16](#374-lēmumu-žurnāls)). Iepriekš v1.1 bija "konkurences paritāte" (zīmola komplekti, presetu bibliotēka), un kalibrācija bija v1.2 papildinājums. Tas bija nepareizā secība: **paritāte konkurentiem, kuri visi ir atvērtā cilpā, nav mērķis, kas ir šī produkta vērtā.** Cilpa pārceļas uz priekšu; noslīpēšana atpakaļ.
>
> Praktiskais arguments ir arī laika ziņā: kalibrācijai vajag **datus**, un dati uzkrājas kalendārā, ne sprintos. Katra nedēļa, kamēr cilpa nav aizvērta, ir nedēļa, kurā neviena lietotāja vēsture neaug. Ja cilpa aizveras v1.1, tad v1.2 laikā jau ir ar ko strādāt; ja tā aizveras v1.2, tad pirmie reālie kalibrācijas rezultāti parādās tikai v1.3 laikā.
>
> **Risks, ko šī secība pieņem:** v1.1 izlaidīsies bez zīmola komplektiem un ar 5 subtitru presetiem, kas ir tieša neizdevība pret Submagic P3 acīs. Tas ir apzināti — skatīt [R18](#354-vērtības-cilpas-riski).

---

### 34.2. v0.9 Beta — "tas neapkauno"

**Mērķis:** slēgtā beta 20–30 lietotājiem, kas var ziņot par problēmām.

| Prasība | Kāpēc tagad |
|---|---|
| [E16-F01](#e16--izplatīšana-licences-un-kopiena) Instalatori | Bez Windows instalatora nav ko izplatīt |
| [E16-F02](#e16--izplatīšana-licences-un-kopiena) Koda parakstīšana | SmartScreen brīdinājums nogalina uzticību |
| [E1-F01](#e1--uzstādīšana-un-pirmā-palaišana) Sagatavošanas plūsma | Pirmā palaišana šobrīd izskatās pēc kļūmes |
| [E1-F02](#e1--uzstādīšana-un-pirmā-palaišana) Vārti, kas ved cauri | Vārti paliek (D-15), bet Ollama ceļš šobrīd tikai ziņo "Not detected" (nepilnība A3b) |
| [E2-F07](#e2--bibliotēka-projekti-un-darba-rinda) Darba atcelšana | Nav veida apturēt sāktu darbu (nepilnība E2) |
| [T10-A](#312-nepieciešamās-izmaiņas) Kodējuma labojums | 34 faila operācijas bez UTF-8 (nepilnība E3) |
| [E16-F07](#e16--izplatīšana-licences-un-kopiena) `.gitattributes` | Bez tā katrs beta ieguldījums ir nelasāms diff (nepilnība E7) |
| [E1-F04](#e1--uzstādīšana-un-pirmā-palaišana) Modeļu sha256 | 5 no 6 modeļiem neverificēti (nepilnība E6) |
| [E1-F03](#e1--uzstādīšana-un-pirmā-palaišana) Aparatūras paziņojums | Godīgums par gaidīšanu |
| [E1-F06](#e1--uzstādīšana-un-pirmā-palaišana) Progresa modelis | JSONL konsole nav progress |
| [E1-F07](#e1--uzstādīšana-un-pirmā-palaišana) Diska pārbaude | Biežākā beta neveiksme |
| [E14-F01](#e14--uzticamība-kļūdas-un-atbalsts) Kļūdu vārdnīca | Beta bez tā nedod izmantojamu atgriezenisko saiti |
| [E14-F02](#e14--uzticamība-kļūdas-un-atbalsts) Atsākšana no posma | Atkopšana bez pilnas pārstrādes |
| [E14-F03](#e14--uzticamība-kļūdas-un-atbalsts) Diagnostikas pakete | Bez tās beta atskaites ir bezjēdzīgas |
| [E2-F04](#e2--bibliotēka-projekti-un-darba-rinda) Darba rinda | T1 |
| [E15-F01](#e15--atjauninājumi-privātums-un-telemetrija) Auto-atjauninājumi | Bez tā beta labojumi nesasniedz lietotājus |
| [E15-F03](#e15--atjauninājumi-privātums-un-telemetrija) Privātuma paziņojums | Juridiski un uzticības ziņā obligāts |
| [E16-F04](#e16--izplatīšana-licences-un-kopiena) macOS validācija | Puse platformas nepārbaudīta |
| [E16-F03](#e16--izplatīšana-licences-un-kopiena) AGPL saskarnē | Izplatīšana bez tā ir pārkāpums |

**Izejas kritēriji:** 20 beta lietotāji pabeidz vismaz vienu darbu; avārijas < 5 %; nulle datu zuduma incidentu.

---

### 34.3. v1.0 — "publiskā izlaišana"

**Mērķis:** jebkurš var lejupielādēt un lietot.

| Prasība | Grupa |
|---|---|
| [E12-F01](#e12--iestatījumi-un-profili) Trīs līmeņu iestatījumi | Lietojamība |
| [E12-F02](#e12--iestatījumi-un-profili) Profili | Lietojamība |
| [E4-F08](#e4--momentu-atlase-un-analīze) Trīs iebūvēti profili | Lietojamība |
| [E4-F01](#e4--momentu-atlase-un-analīze) Vienkāršota klipu vadība | Lietojamība |
| [E2-F01](#e2--bibliotēka-projekti-un-darba-rinda) Bibliotēka | Darbplūsma |
| [E5-F01](#e5--klipu-pārskats-un-vērtējuma-caurspīdīgums) Klipu režģis | Darbplūsma |
| [E5-F02](#e5--klipu-pārskats-un-vērtējuma-caurspīdīgums) Vērtējuma izklājums | Diferenciācija |
| [E5-F03](#e5--klipu-pārskats-un-vērtējuma-caurspīdīgums) Klipa pilnais skats | Darbplūsma |
| [E5-F04](#e5--klipu-pārskats-un-vērtējuma-caurspīdīgums) Klipa statuss | Darbplūsma |
| [E6-F01](#e6--klipu-redaktors) Vienota laika ass | Redaktors |
| [E6-F02](#e6--klipu-redaktors) Dzīvs priekšskatījums | Redaktors |
| [E6-F04](#e6--klipu-redaktors) Subtitru rediģēšana | Redaktors |
| [E7-F01](#e7--subtitri-stils-un-zīmola-komplekti) Subtitru priekšskatījums | Stils |
| [E7-F07](#e7--subtitri-stils-un-zīmola-komplekti) Drošā zona | Kvalitāte |
| [E8-F01](#e8--kadrēšana-un-kompozīcija) Kadrējuma regulators saskarnē | Kadrēšana |
| [E9-F01](#e9--teksti-un-metadati), [E9-F02](#e9--teksti-un-metadati) Nosaukumi un apraksti | Teksti |
| [E10-F01](#e10--eksports-un-publicēšana) Eksporta iestatījumi | Eksports |
| [E10-F02](#e10--eksports-un-publicēšana) Partijas eksports | Eksports |
| [E13-F01](#e13--veiktspēja-un-resursi), [E13-F02](#e13--veiktspēja-un-resursi) Aparatūra | Veiktspēja |
| [E14-F06](#e14--uzticamība-kļūdas-un-atbalsts) Datu integritāte | Uzticamība |
| [E15-F02](#e15--atjauninājumi-privātums-un-telemetrija) Versiju saderība | Uzturēšana |
| Visa [C daļa](#c-daļa--dizains) | Dizains |

**Izejas kritēriji:** aktivācijas metrikas ([33.2](#332-aktivācija)) sasniegtas piecu jaunu lietotāju testā; nulle P0 kļūdu; visi jaunie testi zaļi.

---

### 34.4. v1.1 — "cilpa aizveras"

**Šī ir produkta izlaišana, kas nosaka, vai tas ir kaut kas cits, ne tikai lēts Opus Clip.** Katra prasība te apkalpo [vērtības cilpu](#27-vērtības-cilpa); nekas cits šajā versijā neieiet.

**Bloks 1 — izeja tiek saistīta ar rezultātu:**

| Prasība | Cilpas posms |
|---|---|
| [E10-F03](#e10--eksports-un-publicēšana) Tieša publicēšana `P0` | Publicēšana → automātisks media ID |
| [E11-F02](#e11--vērtības-cilpa-un-kalibrācija) TikTok/YouTube metrikas `P0` | Mērījums pār trim platformām |
| [E11-F04](#e11--vērtības-cilpa-un-kalibrācija) Manuāla ievade un CSV | Mērījums bez API |
| [E11-F01](#e11--vērtības-cilpa-un-kalibrācija) Instagram pilnveidota | Mērījums |

**Bloks 2 — mērījums kļūst par zināšanām:**

| Prasība | Cilpas posms |
|---|---|
| [E11-F03](#e11--vērtības-cilpa-un-kalibrācija) Kalibrācijas atskaite `P0` | Kalibrācija |
| [E11-F06](#e11--vērtības-cilpa-un-kalibrācija) Personīgais bāzlīmenis | Kalibrācija |
| [E11-F05](#e11--vērtības-cilpa-un-kalibrācija) Prognoze pret rezultātu | Kalibrācija |
| [E4-F09](#e4--momentu-atlase-un-analīze) Kalibrēta ranžēšana | Prognoze ← kalibrācija |

**Bloks 3 — iepakojuma svira:**

| Prasība | Cilpas posms |
|---|---|
| [E17-F04](#e17--iepakojuma-eksperimenti) Rezultātu attiecinājums `P0` | Iepakojums → mērījums |
| [E17-F06](#e17--iepakojuma-eksperimenti) Statistiskais godīgums `P0` | Visi |
| [E17-F01](#e17--iepakojuma-eksperimenti) Iepakojums kā vienība | Iepakojums |
| [E17-F02](#e17--iepakojuma-eksperimenti) Variantu ģenerēšana | Iepakojums |
| [E17-F03](#e17--iepakojuma-eksperimenti) Eksperimenta izpilde | Iepakojums |
| [E17-F05](#e17--iepakojuma-eksperimenti) Iemācītais profils | Kalibrācija |
| [E9-F05](#e9--teksti-un-metadati) Vāka kadrs | Iepakojums |

**Bloks 4 — minimums, kas cilpu padara lietojamu apjomā:**

| Prasība | Kāpēc te, ne v1.2 |
|---|---|
| [E2-F02](#e2--bibliotēka-projekti-un-darba-rinda) Projekti | Bāzlīmeņi ir per-projekts ([E11-F06](#e11--vērtības-cilpa-un-kalibrācija)) — bez projektiem P3 dati sajaucas |
| [E12-F04](#e12--iestatījumi-un-profili) Profilu eksports | Kalibrētais profils ir tas, ko vērts eksportēt |
| [E10-F04](#e10--eksports-un-publicēšana) Plānošana | Publicēšanas laiks ir eksperimenta mainīgais ([E17-F03](#e17--iepakojuma-eksperimenti)) |

**Izejas kritēriji:** vismaz 10 beta lietotājiem cilpa ir aizvērta ar ≥ 15 saskaņotiem klipiem; vismaz vienam no viņiem kalibrācija uzrāda statistiski derīgu korelāciju; **nulle gadījumu, kur rīks rāda secinājumu ar nepietiekamu `n`**.

---

### 34.5. v1.2 — "satura kvalitāte"

Tas, kas tika atlikts, lai cilpa aizvērtos ātrāk. Tagad ar to atšķirību, ka **katru šo funkciju var izmērīt** — vai split-screen klipi tur noturību labāk, vai vizuālais kanāls atrod momentus, kas nostrādā.

| Prasība | Ko tas atrisina |
|---|---|
| [E8-F04](#e8--kadrēšana-un-kompozīcija) Īsts split-screen | Plaisa D |
| [E4-F05](#e4--momentu-atlase-un-analīze) Vizuālās darbības kanāls | Plaisa C1 — un jauns kanāls, ko kalibrācija var svērt |
| [E4-F06](#e4--momentu-atlase-un-analīze) Chat kanāls | Straumētājiem unikāls signāls |
| [E3-F03](#e3--ievade-un-avoti) Chat ievade | ↑ |
| [E8-F03](#e8--kadrēšana-un-kompozīcija) Sejas izmēra veto | Kadrēšanas kvalitāte |
| [E7-F02](#e7--subtitri-stils-un-zīmola-komplekti) Presetu bibliotēka | Submagic paritāte |
| [E7-F03](#e7--subtitri-stils-un-zīmola-komplekti) Presetu redaktors | P3 |
| [E7-F05](#e7--subtitri-stils-un-zīmola-komplekti) Zīmola komplekti | P3 |
| [E2-F03](#e2--bibliotēka-projekti-un-darba-rinda) Vairāku avotu ievade | P3 |
| [E6-F03](#e6--klipu-redaktors) Tempa vadība | P1 |
| [E6-F07](#e6--klipu-redaktors) B-roll un pārklājumi | Redaktora dziļums |
| [E4-F02](#e4--momentu-atlase-un-analīze) Interešu līknes vizualizācija | Caurspīdīgums |
| [E4-F03](#e4--momentu-atlase-un-analīze) Manuāls moments | P2, P3 |
| [E9-F04](#e9--teksti-un-metadati) Nosaukumu veidnes | P3 |

**Jauns izejas kritērijs, ko cilpa padara iespējamu:** katrai šīs versijas satura funkcijai ir mērījums, kas apliecina, ka tā uzlaboja noturību — vai godīgs ieraksts, ka neuzlaboja.

---

### 34.6. Kas paliek ārpus plāna

`P3` prasības ([E10-F06](#e10--eksports-un-publicēšana) EDL eksports, mākoņa sinhronizācija, komandu sadarbība) ir reģistrētas, bet nav ieplānotas. Tās tiek pārskatītas pēc v1.2, balstoties uz reālu lietotāju pieprasījumu, nevis uz pieņēmumu.

---

## 35. Riski un to mazināšana

### 35.1. Produkta riski

**R1 · Sarežģītība atgriežas.** ⬤⬤⬤ augsta varbūtība

Katra jauna funkcija grib savu kontroli, un pēc gada iestatījumu panelis atkal ir 120 kontroļu blāķis.

*Mazināšana:* līmeņa lauks ir obligāts shēmā, un `test_schema_levels.py` krīt bez tā. Katra jauna kontrole pēc noklusējuma nokļūst `advanced` līmenī; pārvietošana uz `quick` prasa skaidru pamatojumu commit ziņojumā. Ātrā līmeņa kontroļu skaitam ir griesti — 8.

**R2 · Noklusējumi ir slikti kādai auditorijai.** ⬤⬤ vidēja

Trīs profili nevar apkalpot visus. Gameplay profils, kas labs FPS spēlēm, var būt slikts stratēģijas spēlēm.

*Mazināšana:* profili ir dati, ne kods — lietotāji un kopiena tos var veidot un dalīties ([E16-F05](#e16--izplatīšana-licences-un-kopiena)). Katrs iebūvētais profils tiek pierādīts uz reāla parauga, un tas paraugs paliek repozitorijā.

**R3 · Publicēšanas API mainās vai aizveras.** ⬤⬤⬤ augsta

Meta jau ir pierādījusi, ka tā maina metriku nosaukumus un atsakās saglabāt `http://` redirect URI. TikTok API piekļuve ir ierobežota.

*Mazināšana:* katra integrācija degradējas uz eksportu, nekad neavarē. Publicēšana nekad nav vienīgais ceļš uz failu. Metriku "kāpņu" modelis ([E11-F02](#e11--vērtības-cilpa-un-kalibrācija)) tiek attiecināts uz visām platformām.

**R4 · Split-screen izrādās nesamērīgi dārgs.** ⬤⬤ vidēja

Divi dzīvi crop ceļi ar overlay var pārsniegt 1,6× budžetu, un facecam izolēšana no spēles laukuma var būt neuzticama.

*Mazināšana:* funkcija ir v1.2, nevis v1.0. Manuālā reģionu definēšana ir pirmā, automātiskā — otrā. Ja automātika nedarbojas, manuālais ceļš tomēr dod vērtību.

---

### 35.2. Tehniskie riski

**R5 · CUDA atkarību slazds atkārtojas.** ⬤⬤⬤ augsta

Specifikācijas §12 dokumentē, ka `uv run` pārsinhronizējas no `pyproject.toml` katrā palaišanā, un ka instalētajai lietotnei ir sava kopija. Tas jau ir noķēris cilvēkus.

*Mazināšana:* CI pārbaude, kas apstiprina, ka instalētās būves `pyproject.toml` satur pareizo indeksu; palaišanas laika zonde, kas ziņo, ja torch ir CPU būve uz mašīnas ar CUDA, un to parāda saskarnē.

**R6 · Priekšskatījuma un renderēšanas dreifs.** ⬤⬤⬤ augsta

Tas jau ir noticis trīs reizes šajā kodā (specifikācijas §5 un §7). Katra jauna funkcija ar priekšskatījumu ir jauna dreifēšanas iespēja.

*Mazināšana:* `test_preview_parity.py` ir obligāts vārtsargs. Katra jauna `ClipEdit` lauka pievienošana pievieno rindu šim testam. Vienotā atrisināšana (T3) ir arhitektūras, ne disciplīnas jautājums.

**R7 · Pirkstu nospiedums aizmirsts.** ⬤⬤⬤ augsta

Specifikācija to nosauc par "to, ko cilvēki aizmirst", un tas padara iestatījumu klusi neefektīvu.

*Mazināšana:* četru vietu likums ir universālais pieņemšanas kritērijs ([7.3](#73-universālie-pieņemšanas-kritēriji)). Papildus: tests, kas katram `ClipEdit` laukam pārbauda, vai tas parādās vismaz vienā posma pirkstu nospiedumā.

**R8 · macOS paliek otrās šķiras.** ⬤⬤ vidēja

Specifikācija atzīst, ka Windows ir validētā platforma.

*Mazināšana:* [E16-F04](#e16--izplatīšana-licences-un-kopiena) ir v0.9 P0 prasība, nevis vēlāka. CI būvē abas platformas no pirmās dienas.

**R9 · Modeļu lejupielādes avoti pazūd.** ⬤⬤ vidēja

Svari nāk no HuggingFace un tiešiem URL. Viens noņemts fails nozīmē salauztu instalāciju.

*Mazināšana:* piesaistīti sha256; vairāki spoguļi katram modelim; iespēja lietotājam norādīt lokālu failu; skaidra kļūda ar manuālas lejupielādes instrukciju.

---

### 35.3. Juridiskie un licences riski

**R10 · AGPL neatbilstība izplatot.** ⬤⬤ vidēja, ⬤⬤⬤ augsta ietekme

AGPL prasa, lai avots pavadītu izplatīšanu, lai modifikācijas būtu nosauktas, un — §13 — lai tīkla lietošana skaitītos kā izplatīšana.

*Mazināšana:* [E16-F03](#e16--izplatīšana-licences-un-kopiena) ir P0. Katra izlaišana publicē avota arhīvu tieši tai versijai. Ja produkts kādreiz iegūst mākoņa komponenti, §13 attiecas — tas ir dokumentēts lēmums, nevis pārsteigums.

**R11 · Fontu licences subtitru presetos.** ⬤⬤ vidēja

Presetu bibliotēkas paplašināšana ir vilinājums iekļaut fontus, kuru licences neatļauj izplatīšanu.

*Mazināšana:* katram presetam obligāts licences lauks; CI pārbaude, kas noraida presetu bez tā; noklusējuma komplektā tikai OFL vai līdzvērtīgi fonti.

**R12 · Vendored kods bez versiju izsekojamības.** ⬤⬤ vidēja

`vendor/` satur četru augšupējo projektu kopijas. Bez versiju atzīmēm nav iespējams pierādīt, kas tika ņemts.

*Mazināšana:* TD5 — katrai vendored direktorijai pievienot augšupējo commit hash un datumu; `VENDORED-LICENSES.md` paliek autoritatīvais saraksts.

---

### 35.4. Vērtības cilpas riski

Šie ir jauni v1.4 un ir **produkta eksistenciālākie riski**, jo tie apdraud pamatpieņēmumu, ne realizāciju.

**R16 · Vērtējums nekorelē ar rezultātu, un kalibrācija to nelabo.** ⬤⬤ vidēja varbūtība, ⬤⬤⬤⬤ kritiska ietekme

Iespējams, ka klipa panākumus nosaka galvenokārt lietas, kuras rīks neredz: platformas algoritms, publicēšanas laiks, kanāla momentums, sezonalitāte, veiksme. Ja tā, korelācija paliks ap 0,2 neatkarīgi no tā, cik svarus mēs pārkalibrējam, un **produkta galvenais solījums ir tukšs**.

*Mazināšana:*
- **Uzzināt to agri un lēti.** Tāpēc [E11-F02](#e11--vērtības-cilpa-un-kalibrācija) un [E11-F03](#e11--vērtības-cilpa-un-kalibrācija) ir v1.1 `P0`, ne v1.2. Ar 10 beta lietotājiem un 15 klipiem katram atbilde ir pēc dažām nedēļām, ne pēc gada.
- **Definēts atmešanas slieksnis pirms mērīšanas:** ja pēc 100 saskaņotiem klipiem pār visiem beta lietotājiem mediānā korelācija paliek < 0,25 un kalibrācija to neuzlabo par ≥ 0,10, atlases svira tiek atzīta par nesekmīgu un dokuments tiek pārrakstīts. Slieksnis tiek fiksēts **tagad**, lai vēlāk nebūtu vilinājuma to pielāgot rezultātam.
- **Iepakojuma svira ir daļēji neatkarīga.** Pat ja atlase nekalibrējas, hook un vāka ietekme uz 3 s noturību ir daudz tiešāka cēloņsakarība ([E17](#e17--iepakojuma-eksperimenti)). Divas sviras nozīmē, ka viena neveiksme nav produkta beigas.
- Godīgs ieraksts publiski, ja tā notiek. Rīks, kas pasaka "mēs mēģinājām un tas nestrādāja", ir uzticamāks par to, kas klusē.

**R17 · Aukstais starts padara cilpu neredzamu pirmajiem lietotājiem.** ⬤⬤⬤ augsta varbūtība, ⬤⬤ vidēja ietekme

Kalibrācija prasa ≥ 15 saskaņotus klipus. Lietotājam ar diviem darbiem nedēļā tas ir **vismaz mēnesis**, pirms viņš redz jebkādu vērtību no galvenās funkcijas. Vairums atmet pirms tam.

*Mazināšana:*
- Cilpas progress ir **redzams no pirmās dienas**: "8 no 15 klipiem līdz pirmajai kalibrācijai". Progresa josla uz vērtību ir pati par sevi noturēšanas mehānisms.
- [E17](#e17--iepakojuma-eksperimenti) dod ātrāku signālu nekā atlases kalibrācija — iepakojuma ass rezultāti parādās pie mazāka `n`, jo mainīgais ir tīrāks.
- Produkts ir noderīgs arī bez cilpas. Klipu ģenerators, kas strādā lokāli un bez limitiem, ir pietiekams iemesls to lietot pirmo mēnesi.
- **Nekad neaizpildīt tukšumu ar viltus ieteikumiem.** [E17-F06](#e17--iepakojuma-eksperimenti) to aizliedz tieši. Tukša atskaite ar godīgu skaitītāju ir labāka par pārliecinošu troksni.

**R18 · v1.1 izlaižas bez tā, ko P3 sagaida.** ⬤⬤⬤ augsta varbūtība, ⬤⬤ vidēja ietekme

Cilpas prioritizēšana nozīmē, ka zīmola komplekti un paplašinātā presetu bibliotēka pārceļas uz v1.2. Aģentūras redaktore, kas salīdzina ar Submagic, redzēs 5 presetus un nevienu zīmola komplektu.

*Mazināšana:* tas ir **apzināts kompromiss**, ne pārraudzība ([D-16](#374-lēmumu-žurnāls)). Paritāte ar atvērtas cilpas konkurentiem nav mērķis, kas šo produktu attaisno; ja mēs izvēlamies paritāti pirmo, mēs esam lēts Submagic ar sliktāku presetu bibliotēku. Projekti un profilu eksports paliek v1.1 kā P3 minimums.

**R19 · Kalibrācija pārpielāgojas pagātnei.** ⬤⬤ vidēja varbūtība, ⬤⬤ vidēja ietekme

Svari, kas nostādīti uz pēdējiem 30 klipiem, var kodēt tā brīža algoritmu, tēmu vai sezonu, un pēc tam aktīvi kaitēt.

*Mazināšana:* slīdošs logs, ne visa vēsture ([E11-F06](#e11--vērtības-cilpa-un-kalibrācija)); ticamības intervāli redzami ([E17-F06](#e17--iepakojuma-eksperimenti)); katra pieņemtā korekcija ir atsaucama ar datumu; kalibrācija tiek pārrēķināta periodiski un lietotājs redz, kad tā ir "novecojusi".

---

### 35.5. Tirgus riski

**R13 · Konkurents izlaiž lokālu versiju.** ⬤ zema, ⬤⬤⬤ augsta ietekme

*Mazināšana:* mūsu priekšrocība nav tikai lokalitāte — tā ir lokalitāte **plus** auditējams vērtējums **plus** AGPL. Pēdējo mākoņa uzņēmums nevar atkārtot bez sava biznesa modeļa graušanas.

**R14 · Ieejas slieksnis ir par augstu tirgum.** ⬤⬤⬤ augsta

Pārlūka cilne ir vieglāka par instalāciju, ~2,5 GB modeļu un uzstādīšanas soli. Pēc [D-15](#374-lēmumu-žurnāls) šis slieksnis ir apzināti izvēlēts, kas nozīmē, ka risks ir **pieņemts, nevis mazināts** — bet tas joprojām jāmēra.

*Mazināšana:* būt godīgiem par to no pirmās sekundes ([E1-F03](#e1--uzstādīšana-un-pirmā-palaišana)); paraugvideo, kas dod vērtību pirms pilnas apņemšanās ([E1-F05](#e1--uzstādīšana-un-pirmā-palaišana)); mērķēt uz lietotājiem, kuriem apjoms padara instalāciju izdevīgu. Šis nav produkts cilvēkam ar vienu video gadā, un mēģinājums par tādu kļūt sabojātu to lietotājam, kam tas ir domāts. Bezmaksas cena šo berzi nenoņem — tā tikai noņem vienu pretargumentu no diviem.

**R15 · Uzturētāja izdegšana.** ⬤⬤⬤ augsta, ⬤⬤⬤ augsta ietekme

Šis ir bezmaksas projekta galvenais eksistenciālais risks, un tas ir lielāks par jebkuru tehnisko risku šajā sarakstā. Bez ieņēmumiem nav ne komandas, ne pienākuma, ne budžeta. Pieprasījums pēc atbalsta aug lineāri ar lietotāju skaitu; pieejamais laiks nemainās.

*Mazināšana:*
- **Katra kļūda, ko lietotājs var atrisināt pats, ir issue, kas nekad netiek atvērta.** Tāpēc [E14-F01](#e14--uzticamība-kļūdas-un-atbalsts) (kļūdu vārdnīca) un [E14-F05](#e14--uzticamība-kļūdas-un-atbalsts) (iebūvētā palīdzība) ir ilgtspējas funkcijas, nevis tikai lietojamības.
- Skaidri publicēts atbalsta apjoms: kopienas atbalsts, bez SLA, bez garantēta atbildes laika. To pasaka repozitorijs un "Par" ekrāns.
- Issue veidnes, kas prasa diagnostikas paketi ([E14-F03](#e14--uzticamība-kļūdas-un-atbalsts)) — nepilnīga atskaite maksā vairāk laika nekā pati kļūda.
- Apjoma disciplīna: [2.5](#25-ko-mēs-apzināti-nedarām) saraksts ir uzturētāja aizsardzība, ne tikai produkta fokuss.
- Kopienas ieguldījuma ceļš ([E16-F05](#e16--izplatīšana-licences-un-kopiena)) — preseti un profili ir dati, ko var pievienot bez uzturētāja iesaistes.

---

## 36. Atklātie jautājumi

| # | Jautājums | Kas jāizlemj | Kad |
|---|---|---|---|
| ~~Q1~~ | ~~Monetizācija~~ | **ATBILDĒTS 2026-08-22:** pilnībā bezmaksas, bez maksas līmeņiem. Skatīt [2.6](#26-izplatīšanas-modelis-bezmaksas-un-atvērts) un D-09. | ✓ |
| ~~Q2~~ | ~~Kopīga Gemini atslēga~~ | **ATBILDĒTS 2026-08-22:** nē. Bez ieņēmumiem tā ir tīra izmaksa un atbildība. Ollama tiek pacelts par galveno ceļu. D-10. | ✓ |
| Q9 | Kā finansēt koda parakstīšanas sertifikātus? | ~300–500 USD gadā abām platformām. Ziedojumi, personīgi segts, vai neparakstīta izlaišana ar dokumentētu apiešanu ([E16-F02](#e16--izplatīšana-licences-un-kopiena)). | Pirms v0.9 |
| Q10 | Kurš Ollama modelis ir ieteicamais noklusējums? | Ollama kļuva par galveno ceļu (D-10), tāpēc konkrēts ieteikums ar zināmu kvalitāti ir vajadzīgs, nevis "auto-izvēlas instalēto". | Pirms v0.9 |
| Q3 | Cik dziļš var būt redaktors, nekļūstot par montāžas programmu? | [2.5](#25-ko-mēs-apzināti-nedarām) velk līniju, bet B-roll un pārklājumi to spiež. | v1.2 plānošanā |
| Q4 | Vai atbalstīt Linux? | Tehniski iespējams; trīskāršo testēšanas matricu. | Pēc v1.0, pēc pieprasījuma |
| Q5 | Kā apstrādāt satura moderāciju eksportā? | Vai lietotne brīdina par potenciāli problemātisku saturu? Vai tas vispār ir mūsu darbs? | Pirms [E10-F03](#e10--eksports-un-publicēšana) |
| Q6 | Kur beidzas Ollama atbalsts? | Modeļu kvalitāte ļoti atšķiras; vai piesaistīt konkrētiem modeļiem? | v1.1 |
| Q7 | Vai profili var mācīties no lietotāja izvēlēm automātiski? | Jaudīgs, bet pārkāpj "svari nemainās bez apstiprinājuma" principu. | v1.2 |
| Q8 | Vai kopienas presetu apmaiņai vajag centralizētu vietu? | Faila imports ir bez izmaksām; reģistrs prasa infrastruktūru. | v2.0 |

---

## 37. Pielikumi

### 37.1. Glosārijs

Termini, kas parādās kodā un šajā dokumentā. Saskarnē lietotājs redz labās kolonnas valodu ([24.6](#246-cilvēka-valoda-virsmā-žargons-dziļumā)).

| Termins | Nozīme | Kā to sauc saskarnē |
|---|---|---|
| ASR | Automātiska runas atpazīšana | "Atpazīst runu" |
| Diarizācija | Runātāju nošķiršana laikā | "Atšķir runātājus" |
| ASD | Aktīvā runātāja noteikšana | (nav virsmā) |
| Kandidātu logs | Potenciāls klipa diapazons pirms vērtēšanas | "Kandidāts" |
| Interešu līkne | Svērtā signālu summa pa avota laiku | "Interese" |
| T1 / T2 | LLM teksta / vīzijas caurlaide | "Satura vērtējums" / "Vizuālais vērtējums" |
| Punch-in | Īslaicīgs pietuvinājums | "Pietuvinājums" |
| Deadzone | Slieksnis, zem kura kadrs nekustas | "Kadra stabilitāte" |
| `gameplay_amount` | Kadrējuma platuma regulators 0–1 | "Kadrējums: seja ↔ viss kadrs" |
| Letterbox | Melnas vai izplūdinātas joslas | "Malas" |
| LUFS | Skaļuma mērvienība | "Skaļums" |
| Kontrolpunkts | Posma saglabātais rezultāts | "Saglabāts posms" |
| Pirkstu nospiedums | Iestatījumu kopums, kas nosaka, vai kešs derīgs | (nav virsmā) |
| Restilizācija | Atkārtota renderēšana ar jaunu stilu | "Mainīt stilu" |
| Dead space | Klusums, ko var izgriezt | "Klusums" |
| DCASE | Audio notikumu pēcapstrādes standarts | (nav virsmā) |

### 37.2. Prasību kopsavilkums pa prioritātēm

| Prioritāte | Skaits | Epikas |
|---|---|---|
| **P0** | 42 | E1 (4), E2 (3), E4 (2), E5 (4), E6 (2), E7 (2), E8 (1), E9 (2), E10 (2), E12 (2), E13 (2), E14 (3), E15 (3), E16 (5), plus A11Y-1…4 |
| **P1** | 42 | Sadalīti pār visām epikām |
| **P2** | 19 | Galvenokārt E3, E6, E10, E11 |
| **P3** | 1 | E10-F06 |

Kopā **104 numurētas prasības** 17 epikās, plus 18 ne-funkcionālās ([32](#32-ne-funkcionālās-prasības)) un 9 pieejamības ([30.1](#301-pieejamības-prasības)).

*v1.4 izmaiņas skaitā:* +9 jaunas — [E17](#e17--iepakojuma-eksperimenti) (6), [E11-F05](#e11--vērtības-cilpa-un-kalibrācija), [E11-F06](#e11--vērtības-cilpa-un-kalibrācija), [E4-F09](#e4--momentu-atlase-un-analīze). Pacelti uz `P0`: [E10-F03](#e10--eksports-un-publicēšana), [E11-F02](#e11--vērtības-cilpa-un-kalibrācija), [E11-F03](#e11--vērtības-cilpa-un-kalibrācija).

### 37.3. Izsekojamība: nepilnība → prasība → versija

| Nepilnība | Prasība | Versija |
|---|---|---|
| A1 iestatījumu blāķis | E12-F01 | v1.0 |
| A2 nav profilu | E12-F02 | v1.0 |
| ~~A3 onboarding prasa atslēgu~~ | — | **ATCELTS** — dizaina izvēle, ne nepilnība (D-15) |
| A3b Ollama ceļš neved cauri | E1-F02 | v0.9 |
| A4 nav parauga | E1-F05 | v1.0 |
| ~~A5 JSONL progress~~ | ~~E1-F06~~ | **ATCELTS** — apgalvojums nepareizs; strukturēts progress jau eksistē. ETA daļa pāriet uz E1-F06 (`P1`, v1.0) |
| A6 nav aparatūras paziņojuma | E1-F03, E13-F01 | v0.9 |
| A7 žargons | C daļa | v1.0 |
| B1 nav rindas | E2-F04 | v0.9 |
| B2 nav projektu | E2-F02 | v1.1 |
| B3 eksports pa vienam | E10-F02 | v1.0 |
| B4 nav publicēšanas | E10-F03 | v1.1 |
| B5 nav klipa statusa | E5-F04 | v1.0 |
| B6 tikai Instagram | E11-F02 | v1.2 |
| C1 audio nosliece | E4-F05 | v1.2 |
| C2 nav split-screen | E8-F04 | v1.2 |
| C3 subtitri letterbox joslā | E7-F07 | v1.0 |
| C4 nav sejas veto | E8-F03 | v1.2 |
| C5 maza presetu bibliotēka | E7-F02 | v1.1 |
| C6 nav B-roll | E6-F07 | v1.2 |
| D1 nav Windows instalatora | E16-F01 | v0.9 |
| D2 nav parakstīšanas | E16-F02 | v0.9 |
| D3 nav auto-atjauninājumu | E15-F01 | v0.9 |
| D4 macOS nepārbaudīts | E16-F04 | v0.9 |
| D5 nav privātuma paziņojuma | E15-F03 | v0.9 |
| D6 AGPL nav saskarnē | E16-F03 | v0.9 |
| D7 nav avāriju atskaišu | E14-F04 | v1.0 |
| ~~**E1 nav "bez AI" režīma**~~ | — | **ATCELTS** — apzināti noraidīts (D-15) |
| **E2 nav darba atcelšanas** | E2-F07 | v0.9 |
| **E3 34 faila operācijas bez UTF-8** | T10-A | v0.9 |
| **E4 `api.ts` noteikums pārkāpts** | TD2 | v1.0 |
| **E5 divi rakstītāji uz `clip_edits.json`** | T10-B | v1.0 |
| **E6 5 no 6 modeļiem bez sha256** | E1-F04 | v0.9 |
| E7 nav `.gitattributes` | E16-F07 | **IZDARĪTS** 2026-08-25 (commit `95f493d`); prioritāte koriģēta `P0` → `P1` |

### 37.4. Lēmumu žurnāls

Lēmumi, kas pieņemti, rakstot šo dokumentu, un to pamatojums. Papildināms turpmāk.

| # | Lēmums | Pamatojums |
|---|---|---|
| D-01 | Paliek darbvirsmas lietotne; nav mākoņa apstrādes v1.0 | Lokalitāte ir produkta 1. īpašība un galvenā diferenciācija. Mākonis to grautu un ievestu izmaksas bez ieņēmumiem. |
| D-02 | 72 kontroles tiek pārkārtotas, nevis samazinātas | "Katrs regulators ir īsts" ir mājas noteikums. Noņemšana pārkāptu to; slāņošana nē. |
| D-03 | Klipu redaktors ir pilnekrāna skats, ne modālis | Tur pavada minūtes, ne sekundes. |
| D-04 | Split-screen ir v1.2, ne v1.0 | Prasa jaunu renderēšanas ceļu (T6). Nedrīkst bloķēt izlaišanu. |
| D-05 | Telemetrija paliek izslēgta pēc noklusējuma | Privātums ir svarīgāks par metriku pilnīgumu. |
| D-06 | Publicēšana v1.1, ne v1.0 | API riski (R3) ir pārāk augsti pirmajai izlaišanai; eksports vien jau aizver lielāko daļu Plaisas B. |
| D-07 | Sejas izmēra veto ir izslēgts pie `gameplay_amount = 0.0` | Saglabā specifikācijā solīto nulles regresijas garantiju. |
| D-08 | macOS validācija ir v0.9 P0 | Atlikšana padarītu to par pastāvīgi otrās šķiras platformu. |
| D-09 | Produkts ir pilnībā bezmaksas, bez maksas līmeņiem | Lietotāja lēmums (2026-08-22). Novērš visu licencēšanas infrastruktūru; padara AGPL atbilstību triviālu; pārceļ vienīgās izmaksas uz parakstīšanu. Skatīt [2.6](#26-izplatīšanas-modelis-bezmaksas-un-atvērts). |
| D-10 | Netiek piedāvāta kopīga API atslēga; Ollama kļūst par galveno LLM ceļu | Bez ieņēmumiem kopīga atslēga ir nesegta izmaksa un ļaunprātīgas izmantošanas atbildība. Ollama ir vienīgais režīms, kas ir bezmaksas, neierobežots un lokāls vienlaikus. |
| D-11 | Koda parakstīšana saglabā `P0`, bet iegūst dokumentētu atkāpšanās ceļu | Bezmaksas projekts nedrīkst bloķēt izlaišanu uz izdevumu, kuram nav budžeta. macOS notarizācija ir prioritāra pār Windows sertifikātu. |
| D-12 | Nepilnību saraksts pārrakstīts pret pirmkodu; A5 atcelta | Pirmkoda audits (2026-08-22) atrada, ka 5 no 26 apgalvojumiem bija pārspīlēti vai nepareizi, un 7 reālas problēmas nebija reģistrētas. Plānošana uz nepareizas bāzes ir sliktāka par plānošanas trūkumu. |
| D-13 | Esošie 5 subtitru preseti netiek mainīti, tikai papildināti | Preseta maiņa invalidē renderi katram, kas to lieto. Jauni preseti ir aditīvi. |
| D-14 | `.gitattributes` ir "nekavējoties", nevis v0.9 | Higiēnas, ne izlaišanas jautājums, un maksā piecas minūtes. *Koriģēts v1.5: pamatojums bija pārspīlēts — indekss jau bija LF, tāpēc runa ir par platformu divdomību, ne par 26 000 viltus rindām katrā commit. Lēmums paliek; iemesls ir vājāks.* |
| **D-16** | **Produkta mērķis ir maksimizēt klipu vērtību pa divām svirām — atlase un iepakojums; mēra veiktspējas rādītājus, ne naudu; vērtības cilpa pārceļas uz v1.1** | Īpašnieka lēmums (2026-08-22). Produkts ir operatoriem, kuri zina, ko dara; viņu problēma nav "kā izgriezt klipus", bet "cik vērtības no ierakstītās stundas". Sekas: jauna vīzija ([2.1](#21-vīzijas-formulējums)), jauna 4. īpašība ([2.3](#23-ceturtā-īpašība-ko-šis-dokuments-pievieno)), jauna [2.7](#27-vērtības-cilpa), jauna epika [E17](#e17--iepakojuma-eksperimenti), [E11](#e11--vērtības-cilpa-un-kalibrācija) paplašināta un pacelta uz v1.1 `P0`, jauna [E4-F09](#e4--momentu-atlase-un-analīze), nomainīta ziemeļzvaigzne ([33.1](#331-ziemeļzvaigzne)), pārkārtots ceļvedis, jauni riski R16–R19. Nauda noraidīta kā mērs: atkarīga no nišas un līgumiem, prasa manuālu ievadi; noturība nāk no API un ir salīdzināma. |
| **D-15** | **Gemini atslēgas vai Ollama prasība paliek pirmajā ekrānā; nav "bez AI" režīma; P4 persona atcelta** | Īpašnieka lēmums (2026-08-22). Vārti nav berze, ko labot — tie ir līgums: vērtējums bez LLM nav vērts auditēšanu, un tas ir pretrunā ar produkta 2. īpašību. Degradēts trešais ceļš būtu uzturēšanas parāds bez ieņēmumiem ([R15](#352-tehniskie-riski)) apmaiņā pret lietotājiem, kuri spriež par produktu pēc tā sliktākās versijas. Abi ceļi ir bezmaksas, tāpēc tā nav maksas siena. Sekas: nepilnības A3 un E1 atceltas, [E1-F02](#e1--uzstādīšana-un-pirmā-palaišana) pārrakstīta no vārtu noņemšanas uz to izmaksu samazināšanu, P4 izņemts no mērķauditorijas ([4.2](#42-ieejas-slieksnis-ir-dizaina-izvēle)). |

### 37.5. Atsauces

- [SPECIFICATION.md](SPECIFICATION.md) — inženiertehniskā atsauce, commit `3dc43c1`
- [VENDORED-LICENSES.md](VENDORED-LICENSES.md) — trešo pušu kods un attiecinājumi
- [publikclip](https://github.com/Blueturboguy07/publikclip) — augšupējais projekts, AGPL-3.0

**Tirgus izpēte:**

- [AI clipping tools compared — Whipscribe](https://whipscribe.com/tools/clipping)
- [12 Best Opus Clip Alternatives for 2026 — Choppity](https://www.choppity.com/blog/best-opus-clip-alternatives/)
- [Submagic vs Vizard vs OpusClip — Nextclip](https://www.nextclip.pro/blog/submagic-vs-vizard-vs-opusclip)
- [Vizard vs Opus Clip vs Ssemble — Ssemble](https://www.ssemble.com/blog/vizard-vs-opus-clip-vs-ssemble)

---

## Dokumenta beigas

**Versija 1.5 · 2026-08-25**

Šis dokuments ir dzīvs. Katra prasība, kas tiek realizēta, tiek atzīmēta; katra, kas atkrīt, tiek marķēta `ATCELTS` ar iemeslu, saglabājot ID. Lēmumu žurnāls ([37.4](#374-lēmumu-žurnāls)) tiek papildināts, nevis pārrakstīts.

### Izmaiņu vēsture

| Versija | Datums | Izmaiņas |
|---|---|---|
| 1.0 | 2026-08-22 | Sākotnējā redakcija, rakstīta pret `SPECIFICATION.md` (commit `3dc43c1`) |
| 1.1 | 2026-08-22 | Q1 un Q2 atbildēti. Pievienota [2.6](#26-izplatīšanas-modelis-bezmaksas-un-atvērts) (bezmaksas modelis), D-09…D-11, R15 (uzturētāja izdegšana), Q9–Q10. Pārstrādāts [E1-F02](#e1--uzstādīšana-un-pirmā-palaišana) (Ollama kļūst par galveno LLM ceļu) un [E16-F02](#e16--izplatīšana-licences-un-kopiena) (parakstīšanas atkāpšanās ceļš). |
| 1.5 | 2026-08-25 | **Nepilnība E7 koriģēta pēc tiešas pārbaudes** — indekss vienmēr bijis LF (112 failu, 0 CRLF); problēma bija platformu divdomība, ne bojāts repozitorijs. `P0` → `P1`, izdarīts commit `95f493d`. Pievienota piezīme par audita ticamību [6.3](#63-kopsavilkums). Repozitorijā pievienoti `CLAUDE.md`, `AGENT-WORKPLAN.md`, `test_house_rules.py`, `ruff.toml`. |
| 1.4 | 2026-08-22 | **Pārpozicionēšana uz vērtības maksimizēšanu** (D-16). Jauna vīzija, jauna 4. īpašība ("katrs lēmums tiek pārbaudīts pret rezultātu"), jauna [2.7](#27-vērtības-cilpa) vērtības cilpa, jauna [Plaisa E](#32-kur-ir-plaisa), jauna epika [E17](#e17--iepakojuma-eksperimenti) (6 prasības), [E11](#e11--vērtības-cilpa-un-kalibrācija) pārdēvēta un paplašināta (+2 prasības, F02/F03 → `P0`), jauna [E4-F09](#e4--momentu-atlase-un-analīze), [E10-F03](#e10--eksports-un-publicēšana) → `P0`. Nomainīta ziemeļzvaigzne uz noturības svērtu izvadi uz avota stundu; pārkārtots ceļvedis (v1.1 = cilpa, v1.2 = satura kvalitāte); jauni riski R16–R19 ar definētu atmešanas slieksni. |
| 1.3 | 2026-08-22 | **Ieejas slieksnis apstiprināts kā dizains** (D-15). Pievienota [4.2](#42-ieejas-slieksnis-ir-dizaina-izvēle); P4 persona atcelta; [E1-F02](#e1--uzstādīšana-un-pirmā-palaišana) pārrakstīta no "vārtu noņemšanas" uz "vārtiem, kas ved cauri"; nepilnības A3 un E1 atceltas, pievienota A3b (Ollama ceļš neved cauri); [33.2](#332-aktivācija) sadalīta vārtu un produkta metrikās; R14 pārformulēts kā pieņemts risks. |
| 1.2 | 2026-08-22 | **Revīzija pret pirmkodu** (commit `5369f34`). Pievienota [6.0](#60-audita-metodika-un-ticamība) (audita metodika), [Kategorija E](#kategorija-e--jaunatklātās-problēmas-nav-specifikācijā) ar 7 jaunām nepilnībām, [E2-F07](#e2--bibliotēka-projekti-un-darba-rinda) (atcelšana), [E16-F07](#e16--izplatīšana-licences-un-kopiena) (`.gitattributes`), D-12…D-14, 4 jauni testi, TD6–TD7. Koriģēti: [E1-F02](#e1--uzstādīšana-un-pirmā-palaišana), [E1-F04](#e1--uzstādīšana-un-pirmā-palaišana), [E1-F06](#e1--uzstādīšana-un-pirmā-palaišana) (`P0`→`P1`), [E7-F02](#e7--subtitri-stils-un-zīmola-komplekti), [E9-F01](#e9--teksti-un-metadati), [E12-F01](#e12--iestatījumi-un-profili), [E12-F05](#e12--iestatījumi-un-profili), [E16-F01](#e16--izplatīšana-licences-un-kopiena), [E16-F04](#e16--izplatīšana-licences-un-kopiena), [T2](#312-nepieciešamās-izmaiņas), [T10](#312-nepieciešamās-izmaiņas), TD1–TD5. Nepilnība A5 atcelta kā nepareiza. |

### Ko šī redakcija joprojām nav pārbaudījusi

Audits pārbaudīja struktūru, konfigurāciju un konkrētus apgalvojumus, bet **nepalaida konveijeru un neizpildīja testus**. Neapstiprināts paliek:

- **[E13-F03](#e13--veiktspēja-un-resursi) veiktspējas budžeti** — skaitļi nāk no specifikācijas mērījumiem uz RTX 3050 Ti, ne no jauna mērījuma.
- **[33.3](#333-kvalitāte-un-cilpas-veselība) kvalitātes metrikas** — nav datu par to, cik klipu reāls lietotājs eksportē bez rediģēšanas.
- **`test_render.py` `@pytest.mark.slow`** ceļš un reāla ffmpeg izšķiršana uz šīs mašīnas.
- **Renderēšanas filtru grafa faktiskā uzvedība** pie `gameplay_amount = 1.0` — [E7-F07](#e7--subtitri-stils-un-zīmola-komplekti) subtitru pozīcija ir izsecināta no `ass.py` konstantēm, ne novērota izvadē.

**Nākamais solis, secībā:**

1. **`.gitattributes` un normalizācija** ([E16-F07](#e16--izplatīšana-licences-un-kopiena)) — piecas minūtes, un bez tā katrs turpmākais commit rada vēl 26 000 viltus rindu izmaiņu.
2. **Ollama uzstādīšanas ceļš** ([E1-F02](#e1--uzstādīšana-un-pirmā-palaišana)) — vārti paliek, tāpēc tie nedrīkst būt akli. Šobrīd neinstalēts Ollama dod pelēku kartīti bez saites un bez soļiem; tas ir vienīgais bezmaksas ceļš iekšā, un tam jāstrādā.
3. Apstiprināt v0.9 Beta apjomu ([34.2](#342-v09-beta--tas-neapkauno)), kas tagad satur 20 prasības, nevis 15.
4. Atbildēt uz Q9 (parakstīšanas finansējums) un Q10 (Ollama noklusējuma modelis).

**Un viens solis, kas nav steidzams, bet ir svarīgākais:**

5. **Sākt vākt datus, pirms cilpa ir gatava.** [R16](#354-vērtības-cilpas-riski) — vai vērtējums vispār korelē ar rezultātu — ir produkta lielākais atklātais jautājums, un uz to var sākt atbildēt jau tagad, bez neviena jauna koda: ņem 30 klipus, kurus jau esi publicējis, pieraksti to Alias Studio vērtējumu un reālo noturību, un aprēķini korelāciju. Ja tā ir 0,4, [D-16](#374-lēmumu-žurnāls) pamatpieņēmums turas un v1.1 ir vērts būvēt. Ja tā ir 0,05, to labāk uzzināt tagad nekā pēc desmit nedēļu darba.

   Tas ir viens vakars ar izklājlapu, un tas ir lētākais veids, kā pārbaudīt visdārgāko pieņēmumu šajā dokumentā.



