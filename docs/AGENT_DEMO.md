# Ask an agent — UNLOCK's graph as tools for an AI agent

Recorded 17 Nov 2026 13:33 UTC with Claude Code (headless) whose **only** tools are the UNLOCK MCP server's, on a read-only copy of the Relate store loaded with that morning's lift status. Nothing below is edited except local paths. Raw transcripts: `docs/research/agent_demo/`. Reproduce: `python scripts/agent_demo.py --python <venv python> --store <copy of database/unlock.rl>`.

Why it matters: without the graph the same model can only guess (0 of 8 checked answers right in [AGENT_EVAL.md](research/AGENT_EVAL.md)); with it, every number in the answer comes from a tool call that read the graph.

## A wheelchair user, before leaving home

> Je me déplace en fauteuil roulant. Mon trajet de tous les jours, c'est Rosa Parks → Juvisy. Est-ce que je peux le faire sans marche ce matin ? Si mon trajet habituel est coupé, propose-moi un détour et dis-moi quel ascenseur pose problème. Réponds en 4 lignes maximum, en français simple.

**Tool calls (2)** — read in order:

1. `usual_trip_alert()`
   ↳ Error executing tool usual_trip_alert: 2 validation errors for usual_trip_alertArguments from_station Field required [type=missing, input_value={}, input_type=dict] For further information visit https://errors.pydantic.dev/2.14/v/missing to_station Field requi…
2. `usual_trip_alert("from_station": "Rosa Parks", "to_station": "Juvisy")`
   ↳ {"from":{"id":"73798","name":"Rosa Parks","lat":48.896776,"lon":2.37426},"to":{"id":"478505","name":"Juvisy","lat":48.689485,"lon":2.384336},"view":"best","observed":{"sncf_lift_status":"2026-11-17T09:30:16+00:00","idfm_lift_status":"2026-11-17T09:44:13+00:00"…

**Answer**

Ton trajet habituel est incertain ce matin : à Gare de Lyon (RER A), des ascenseurs sont en panne ou inconnus.
Le plus clair : « Ligne RER A – Ligne M14 » (RATP) est en panne. « Quai N / Salle d'échange (5012) » est aussi en panne, et « Rue de Bercy (5005) » a un état inconnu.
Détour sans marche : RER E de Rosa Parks à Neuilly – Porte Maillot, puis RER C de Neuilly – Porte Maillot à Juvisy.
Les données datent de 9h30 (SNCF) et 9h44 (IDFM) ; vérifie sur place avant de partir.

*56.8 s, model claude-sonnet-5-5.*

## A lift-maintenance planner

> I plan lift repairs for Île-de-France today. Which single lift repair gives back the most step-free journeys, how many, and is the official outage feed reliable enough to plan from? Answer in 4 lines.

**Tool calls (3)** — read in order:

1. `ToolSearch("query": "select:mcp__unlock__region_repairs,mcp__unlock__rank_repairs,mcp__unlock__region_overview,mcp__unlock__maintenance_bulletin", "max_results": 4)`
   ↳  
2. `region_repairs("limit": 3)`
   ↳ {"base_live_confirmed":231883,"base_feed_confirmed":88255,"repairs":[{"kind":"SNCF_LIFT","lift":"37421b5e-87d0-462c-9041-dd1f0dbad281","gain":1930,"name":"Ascenseur - CDGX / Asc 20 Fond cours des Messageries","state":"UNKNOWN","station":"Paris Est","station_id…
3. `region_overview()`
   ↳ {"available":true,"feed":{"id":"prim_lift_outages@3570dd5cd43f","observed_at":"2026-11-17T09:44:09+00:00","last_lift_update":"2026-10-09T09:53:34","last_other_update":"2026-11-17T10:43:08","lift_messages_stale_days":39,"licence":"Licence Mobilités","source":"h…

**Answer**

Line 1: The biggest single repair is the Paris Est lift "Ascenseur - CDGX / Asc 20 Fond cours des Messageries". It would restore 1,930 confirmed step-free station pairs (best view). Its status is UNKNOWN, not confirmed out of service, so check it on site first.

Line 2: The biggest repair of a lift confirmed out of service is "Ascenseur - AS 15 Transmanche voies 5/6" at Gare du Nord, which would restore 964 pairs. The RATP lift at Auber also gives 964. These counts are ordered station pairs joined by a step-free journey. They aren't people or trips, and each repair was evaluated alone.

Line 3: The PRIM outage feed is not reliable enough to plan from. Its lift messages were last updated on 2026-10-09, which is 39 days ago, and the lift content was identical in all 5 fetches I checked. All 356 listed lifts have messages older than 30 days. SNCF's hourly feed contradicts 253 of the 264 SNCF outages PRIM lists, and IDFM's lift-status data contradicts 37 of the 39 RATP messages it can match. The stale messages hide 126,628 journeys, and 13 SNCF outages are missing from PRIM.

Line 4: Plan from the "best" view, which combines SNCF's hourly status with IDFM's RATP lift status. It shows 231,883 confirmed pairs, against 88,255 for the PRIM feed and 256,592 if nothing were broken. Several feed entries are probably not real outages. La Croix de Berny (a RATP ghost) would unlock 18,290 pairs if it's a false report, so check it first.

*50.8 s, model claude-sonnet-5-5.*

## Two agents, one memory

Relate is the shared memory. Agent 1 writes a field report into the graph through the UNLOCK server (the graph's single writer); agent 2, a separate session started afterwards, reads it back and sets it against the official status. A report never changes the official status or any count.

## Shared memory, agent 1 — a rider reports what they see

> Je suis en fauteuil à la gare de Juvisy. L'ascenseur du quai des voies 50/51 est en panne, je viens de le voir à l'instant. Peux-tu le signaler pour les autres usagers ? Dis-moi ensuite en 2 lignes si les données officielles étaient déjà au courant.

**Tool calls (4)** — read in order:

1. `ToolSearch("query": "select:mcp__unlock__find_lift,mcp__unlock__report_lift,mcp__unlock__field_reports,mcp__unlock__station_outages", "max_results": 4)`
   ↳  
2. `find_lift("report": "Ascenseur du quai des voies 50/51, gare de Juvisy, en panne")`
   ↳ {"status":"RESOLVED","text":"Ascenseur du quai des voies 50/51, gare de Juvisy, en panne","reported_state":"UNAVAILABLE","station_candidates":[{"station_id":"FR:91326:LMO:72a0f993-451e-4b5a-bb32-d162e42906ce:LOC","name":"Juvisy-sur-Orge","score":1,"matched_ali…
3. `station_outages("station_name": "Juvisy")`
   ↳ {"station":{"id":"478505","name":"Juvisy","boardable":true},"outages":[{"id":"prim_lift_outages@3570dd5cd43f:GC:73","lift_key":"GC:73","operator":"SNCF_GC","text":"GARE DE JUVISY Panne de l'ascenseur situé Sortie mairie","station":{"id":"478505","name":"Juvisy…
4. `report_lift("lift_id": "63cd6c0d-e13d-4375-bfec-3888eaad6f65", "status": "OUT", "note": "Vu en panne à l'instant par un usager en fauteuil, quai des voies 50/51, gare de Juvisy.", "reporter": "usager en fauteuil")`
   ↳ {"id":"fr-cac82aea2b746368","lift":"63cd6c0d-e13d-4375-bfec-3888eaad6f65","status":"OUT","note":"Vu en panne à l'instant par un usager en fauteuil, quai des voies 50/51, gare de Juvisy.","source":"agent","reporter":"usager en fauteuil","reported_at":"2026-11-1…

**Answer**

Signalement enregistré : l'ascenseur « ASC.PMR 4556 ASC3 Quai 50/51 » (Juvisy-sur-Orge) est noté en panne. Il est visible des autres usagers et ne modifie pas le statut officiel.

**Les données officielles étaient déjà au courant :** oui, ton signalement les confirme. Le statut IDFM « État des ascenseurs » le donnait indisponible depuis le 16/11 à 03h39, et le flux PRIM listait la panne (direction Creil / Melun Malesherbes, ligne D) depuis le 14/08. En revanche, le flux SNCF publié l'affichait encore « disponible » (désaccord entre sources).

Selon le graphe, 21 liaisons dans la gare dépendent de cet ascenseur.

*70.4 s, model claude-sonnet-5-5.*

## Shared memory, agent 2 — a maintenance team, in a new session

> We are the lift-maintenance team. What did riders, staff or agents report on site in the last few hours, which reports contradict the official lift status, and what should we check first? Answer in 4 lines.

**Tool calls (2)** — read in order:

1. `ToolSearch("query": "select:mcp__unlock__field_reports,mcp__unlock__maintenance_bulletin", "max_results": 5)`
   ↳  
2. `field_reports("hours": 6)`
   ↳ {"reports":[{"id":"fr-cac82aea2b746368","lift":"63cd6c0d-e13d-4375-bfec-3888eaad6f65","status":"OUT","note":"Vu en panne à l'instant par un usager en fauteuil, quai des voies 50/51, gare de Juvisy.","source":"agent","reporter":"usager en fauteuil","reported_at…

**Answer**

1. **Reports (last 6 h):** There is one report. A wheelchair user said at 13:25 UTC today (about 6 minutes old) that they had just seen the lift out of service. It is lift ASC.PMR 4556 ASC3, serving platforms 50/51 (north underpass) at Juvisy (SNCF).
2. **Contradiction:** The report contradicts the official status. SNCF's hourly feed shows AVAILABLE, last updated 09:30 UTC. IDFM's lift dataset shows UNAVAILABLE, updated 2026-11-16 03:39, so the two official sources disagree with each other.
3. **Check first:** Inspect Juvisy ASC3 on platforms 50/51 now. The rider report and the IDFM status both point to a fault, and the SNCF "available" status is about 4 hours old.
4. **Follow-up:** If the lift is confirmed out, correct the SNCF status and the passenger information. If it is working, find out why IDFM has shown it as down since yesterday. The report is unverified and doesn't change the official status.

*42.9 s, model claude-sonnet-5-5.*

## In the video (15 s)

Terminal on the left, UNLOCK on the right. Type the rider's question into `claude` (with the UNLOCK MCP server configured, see README › *AI agents*); let the tool calls scroll (`usual_trip_alert` …); show the answer, then the same trip in *My usual trips* — the same graph, the same answer.
