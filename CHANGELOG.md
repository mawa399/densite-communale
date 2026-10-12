# Historique des versions

Le format suit [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/) et le projet respecte le [versionnage sémantique](https://semver.org/lang/fr/).

## [0.1.0] — 2026-10-12

Première version publique.

### Ajouté

- Carte de densité des communes d'une région ou d'un département, à partir de l'API Géo (contours et populations légales INSEE).
- Liste déroulante de 18 régions et 101 départements, outre-mer compris.
- Trois classifications : échelle nationale (6 classes fixes), seuils naturels de Jenks, quantiles.
- Style automatique (dégradé jaune → rouge), communes sans population en gris, zoom sur le territoire.
- Centroïdes des communes en option (point toujours à l'intérieur de la commune), affichés au-dessus de la carte.
- Bouton dans la barre d'outils, entrée dans le menu *Extensions* et algorithme dans la boîte à outils de traitements.
- Compatibilité QGIS 3.34+ et QGIS 4.

[0.1.0]: https://github.com/mawa399/densite-communale/releases/tag/v0.1.0
