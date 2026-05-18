Projektpitch: Smart Sökning på Blocket
Problemet: Blocket har miljontals annonser. Att hitta de relevanta är tidskrävande, och bedrägerier är ett växande problem — särskilt på elektronik och fordon där köpsumman är hög.
Vår lösning: Ett intelligent lager ovanpå Blockets API som kombinerar kontinuerlig scanning, flerlagrad bedrägeridetektion, naturlig sökning och AI-drivna förklaringar — så att användaren snabbt hittar trovärdiga annonser och slipper riskerna.
Det som gör oss annorlunda:

Egen databas med historik — vi sparar prisförändringar och annonsmönster över tid. Det låter oss upptäcka saker som återpublicerade bluffannonser och prisanomalier som realtids-API:t inte kan visa.
Tre-lagers trovärdighetsbedömning — regelbaserade signaler (snabbt), anomalidetektion via Isolation Forest (hittar det vi inte tänkte på), och LLM-analys för djupa förklaringar. Varje annons får ett trovärdighetsindex 1-10 med transparent motivering.
Hybrid retrieval för sökning — SQL för strukturerade filter, vektorsökning för semantik. Användaren kan skriva "pålitlig pendlarbil under 80k" och få faktiskt relevanta resultat.
Förklarbar AI — varje flaggning kommer med en konkret motivering. Inget "AI-svart-låda".

Kategorier vi fokuserar på: Elektronik och Fordon. Två kategorier på djupet med kategorispecifik logik, snarare än sex på ytan.

Teknisk arkitektur
┌────────────────────────────────────────────────────────────┐
│                     BLOCKET API                             │
└────────────────────────┬───────────────────────────────────┘
                         ↓
┌────────────────────────────────────────────────────────────┐
│  SYNC WORKER (APScheduler, var 30:e sek)                   │
│  - Hämtar nya annonser                                      │
│  - Upptäcker återpublicering                                │
│  - Sparar prishistorik                                      │
└────────────────────────┬───────────────────────────────────┘
                         ↓
┌────────────────────────────────────────────────────────────┐
│  POSTGRESQL + pgvector                                      │
│  - Strukturerad annonsdata                                  │
│  - Embeddings för semantisk sökning                         │
│  - Prishistorik per modell/kategori                         │
└──────────┬─────────────────────────────────────┬───────────┘
           ↓                                     ↓
┌──────────────────────────┐         ┌─────────────────────────┐
│  ML-LAGER                │         │  LLM-LAGER (Claude API) │
│  - Prisuppskattning      │         │  - Per-annons förklaring│
│    (LightGBM regression) │         │  - Naturlig sökning     │
│  - Anomaly detection     │         │  - Chat per annons      │
│    (Isolation Forest)    │         │  - Sökresultatssamm.    │
│  - Similarity search     │         └─────────────────────────┘
│    (sentence-transformers│
│     + cosine)            │
└──────────┬───────────────┘
           ↓
┌────────────────────────────────────────────────────────────┐
│  SCORING ENGINE                                             │
│  Kombinerar alla signaler → Trovärdighetsindex 1-10        │
│  + motivering per annons                                    │
└────────────────────────┬───────────────────────────────────┘
                         ↓
┌────────────────────────────────────────────────────────────┐
│  FASTAPI BACKEND                                            │
│  - REST endpoints för sökning, bevakning, analys           │
│  - WebSocket för realtidsuppdateringar                      │
└────────────────────────┬───────────────────────────────────┘
                         ↓
┌────────────────────────────────────────────────────────────┐
│  REACT FRONTEND                                             │
│  - Sökgränssnitt med live-uppdaterande resultat            │
│  - Trovärdighetsbadgar (grön/gul/röd)                       │
│  - Misstänkta annonser-sektion                              │
│  - Chat-panel per annons                                    │
└────────────────────────────────────────────────────────────┘

Tekniska val och motiveringar
Backend:

Python 3.11+ — krav från hackathonet
FastAPI — ni känner det väl från StockSense, snabbt att utveckla, bra för WebSockets
PostgreSQL + pgvector — strukturerad data + vektorlagring i samma databas, slipper separat vektor-DB
SQLAlchemy — ert standardval, era preferenser för Pydantic-mönster funkar direkt
APScheduler — samma scheduler som Crona-sync i StockSense
blocket_api (pip-paket från utmaningen) — wrapper runt Blockets API

ML-stack:

scikit-learn — Isolation Forest, kalibrering, evaluation
LightGBM — prisuppskattningsmodell
sentence-transformers med KBLab/sentence-bert-swedish-cased — svenska embeddings
NumPy/Pandas — feature engineering

AI-integration:

Anthropic Python SDK — Claude API för analys och chat
Strukturerad JSON-output via system prompt
Cachelagring i databas för att inte LLM-anropa samma annons igen

Frontend:

React 19 + TypeScript — ert standardval
Tailwind CSS — snabb styling
WebSocket (native) — live-uppdateringar
Recharts — prishistorik och statistikgrafer

Infrastruktur:

Docker Compose — postgres + backend + frontend i en command
Lokal körning under demo (ingen deploy behövs, men ni kan om ni vill)


Vad varje AI/ML-komponent gör
KomponentTeknikVad den löserRegelbaserad detectorPython-reglerSnabba uppenbara flaggor (tomma beskrivningar, saknade bilder, urgency-ord)PrisuppskattningLightGBM regression"Förväntat pris ±X" → flagga om annonserat pris avviker kraftigtAnomaly detectionIsolation ForestHittar konstiga annonser utan att vi behövde definiera "konstig"Similarity searchsentence-transformers + cosineHittar bluffmönster — annonser som liknar tidigare flaggadeTrovärdighetsindexViktad kombinationSammanslagen poäng 1-10 med motiveringSemantisk sökningpgvector + LLM rerankNaturligt språk → relevanta annonserPer-annons analysClaude APIDjup förklaring på begäran, fångar nyanser regler missarChat per annonsClaude APIAnvändare kan fråga om enskilda annonser
Viktigt för demot: Allt ovanstående är inom reglerna. Vi använder LLM som "chat" (enkel prompt-respons), inga agenter, inga tool-calls.

Arbetsfördelning
Antar 4 personer och ~8h hackathon. Justera om ni är 3.
Person A: Data & Infrastruktur
Ansvar: Att data flödar in och kan queryas.
Tidsbudget:

0:00-1:30 — Sätt upp PostgreSQL + pgvector i Docker, definiera schema, SQLAlchemy-modeller
1:30-3:00 — Bygg sync worker (APScheduler) som hämtar från blocket_api, detekterar nya annonser, sparar prishistorik
3:00-4:30 — Repost-detektion (jämför nya annonser mot nyligen försvunna), text-deduplikering
4:30-6:00 — Embedding-pipeline: kör sentence-transformers på alla beskrivningar, spara i pgvector
6:00-8:00 — Stötta upp andra, datakvalitet, demo-prep

Output: En databas med flera hundra annonser klara att analysera, med embeddings.
Person B: ML & Scoring
Ansvar: Trovärdighetsindexet och allt under huven.
Tidsbudget:

0:00-1:30 — Feature engineering: bygg pipeline som extraherar features från annonser (pris-z-score, längd, etc)
1:30-3:00 — Regelbaserad detector v1 + prisuppskattningsmodell (LightGBM på insamlad data)
3:00-4:30 — Isolation Forest för anomaly detection, kalibrera tröskelvärden
4:30-6:00 — Similarity-based scam-detection (cosine similarity mot historiskt flaggade)
6:00-7:30 — Scoring engine som kombinerar allt till index 1-10 med motivering
7:30-8:00 — Demo-prep, hitta bra exempel att visa

Output: En score_listing(listing) → {score, reasons[], flags[]} som backend kan anropa.
Person C: API & LLM-integration
Ansvar: FastAPI backend och Claude-integration.
Tidsbudget:

0:00-1:30 — Sätt upp FastAPI-projekt, basic endpoints (lista annonser, hämta enskild)
1:30-3:00 — Sökendpoint med hybrid retrieval (SQL filter + vector search)
3:00-4:30 — Claude-integration: per-annons-analys med strukturerad JSON-output, caching i DB
4:30-6:00 — WebSocket för live-uppdateringar när nya annonser kommer in
6:00-7:30 — Chat-endpoint per annons + sökresultatssammanfattning
7:30-8:00 — Demo-prep, integration-testing

Output: Fullständigt API som frontend kan konsumera.
Person D: Frontend & Demo-experience
Ansvar: Det juryn ser.
Tidsbudget:

0:00-1:30 — Sätt upp React-projekt, basic layout, design system (deep teal som StockSense?)
1:30-3:00 — Sökgränssnitt med kategorifilter och kontinuerligt uppdaterad resultatlista
3:00-4:30 — Trovärdighetsbadge-komponent (grön/gul/röd + nummer + tooltip med motivering)
4:30-6:00 — Misstänkta annonser-sektion, prishistorik-graf, WebSocket-integration för live-uppdateringar
6:00-7:30 — Chat-panel per annons, sökresultatssammanfattning
7:30-8:00 — Polish, demo-flow, slides

Output: Ett UI som ser professionellt ut och är roligt att demoa.

Kritiska beroenden mellan team
A's databas-schema  →  B behöver det för att läsa data
A's embeddings      →  C behöver för semantisk sökning
B's scoring-funktion →  C behöver för att inkludera i API
C's endpoints       →  D behöver för frontend
Strategi: Definiera kontrakt (Pydantic-scheman + endpoint-signaturer) under första halvtimmen tillsammans, så alla kan jobba parallellt mot stubbar.

Risker och fallback-planer
RiskFallbackblocket_api fungerar inte / rate-limitedCacha 500 annonser tidigt, kör resten av demot på cachad dataLightGBM-modell inte hinner tränasAnvänd bara regler + Isolation Forest (kräver ingen träning)Claude API ger problemPer-annons-analys blir cachad statisk text under demotWebSocket-strulFalla tillbaka till polling var 10:e sekundpgvector installation krånglarAnvänd in-memory FAISS istället

Demo-flow (5 min)

0:00-0:30 — Problem-pitch: "Blocket har bedrägeriproblem, vi visar hur AI kan hjälpa"
0:30-1:30 — Live-sökning: skriv naturlig query, visa hybrid retrieval i action
1:30-2:30 — Klicka på en flaggad annons → visa trovärdighetsindex 2/10 → klicka "förklara" → Claude-genererad förklaring som refererar till SHAP-liknande features
2:30-3:30 — Visa kontinuerlig scanning live: en ny annons kommer in via WebSocket, visa hur den bedöms i realtid
3:30-4:30 — Chat med annons: ställ en fråga som "är priset rimligt?" → Claude svarar med er prisstatistik som kontext
4:30-5:00 — Arkitektur-slide + begränsningar + frågor


Sista råd
Innan ni börjar koda — gör tre saker tillsammans:

Definiera Pydantic-scheman för Listing, Score, SearchQuery — det är ert kontrakt
Bestäm Git-flow: feature branches eller trunk-based? Hackathon = trunk-based med korta commits
Bestäm "minimal viable demo" — vad MÅSTE fungera 30 min innan demot? Bygg det först, polera sen

Och kom ihåg: Ni har gjort liknande projekt förut (StockSense). Mycket av detta är samma mönster i en ny domän. Stressa inte.
Lycka till! Vill du att jag dyker djupare i något specifikt — t.ex. exakta Pydantic-scheman, scoring-engine-logiken, eller demo-slidesen?