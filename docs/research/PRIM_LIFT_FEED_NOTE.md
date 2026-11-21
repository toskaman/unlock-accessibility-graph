# Note to IDFM / PRIM support — lift messages no longer updated

*Prepared by UNLOCK for the entrant and **sent by e-mail** to PRIM / Île-de-France Mobilités (contact-prim@iledefrance-mobilites.fr); a report on the contradictory lift statuses was also e-mailed to SNCF Gares & Connexions. No reply is recorded here yet (19 Nov 2026).*

Bonjour,

En réutilisant l'API « Calculateur Île-de-France Mobilités – Messages Info Trafic »
(`/marketplace/v2/navitia/line_reports/line_reports`), nous observons le 16/11/2026 à 20h13, 23h33 et 00h14 (heure de Paris), avec un contenu ascenseurs
identique à l'octet près à chaque fois :

- 1 047 perturbations actives portant le tag « Ascenseur » (356 ascenseurs distincts d'après le champ
  `reference`) ;
- aucune n'a de `updated_at` postérieur au **09/10/2026 09:53**, alors que les autres perturbations de la même
  réponse sont mises à jour le jour même ;
- 26 messages annoncent dans leur texte une date de fin déjà passée (ex. « jusqu'au 2026-06-30 ») ;
- pour les ascenseurs Gares & Connexions, le jeu SNCF « État de fonctionnement des équipements
  d'élévatique en gare » (mis à jour toutes les heures) indique en fonctionnement 235 des 264 ascenseurs
  listés en panne par l'API ; 7 ascenseurs hors service côté SNCF n'apparaissent pas dans l'API.

L'API « Messages Info Trafic – requête globale » (`disruptions_bulk`) ne contient, elle, aucun message
ascenseur.

Pourriez-vous nous confirmer si la diffusion des pannes d'ascenseurs dans l'API Navitia est interrompue
depuis le 9 octobre, et quelle source est recommandée pour l'état des ascenseurs RATP ?

Méthode et données : https://github.com/toskaman/unlock-accessibility-graph (docs/research/NETWORK_DISCOVERY.md).

Cordialement,
