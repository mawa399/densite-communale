"""
Densité communale — algorithme Processing pour QGIS 3.34+ et QGIS 4.

Récupère en direct les communes d'une région ou d'un département
(contours + populations légales) via l'API Géo (geo.api.gouv.fr),
calcule la densité de population sur l'ellipsoïde et produit une carte
stylée : classes au choix, communes sans donnée visibles, centroïdes en option.

Auteur : Mawa Diaw
"""

import json

from qgis.core import (
    Qgis,
    QgsBlockingNetworkRequest,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsDistanceArea,
    QgsFeature,
    QgsFeatureSink,
    QgsField,
    QgsFields,
    QgsGraduatedSymbolRenderer,
    QgsJsonUtils,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingContext,
    QgsProcessingOutputVectorLayer,
    QgsProcessingException,
    QgsProcessingLayerPostProcessorInterface,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFeatureSink,
    QgsProject,
    QgsRendererRange,
    QgsRuleBasedRenderer,
    QgsStyle,
    QgsSymbol,
    QgsVectorLayer,
    QgsClassificationJenks,
    QgsClassificationQuantile,
)
from qgis.PyQt.QtCore import QCoreApplication, QUrl
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtNetwork import QNetworkRequest

try:  # QGIS >= 3.38 / QGIS 4
    from qgis.PyQt.QtCore import QMetaType

    T_STR, T_INT, T_DBL = QMetaType.Type.QString, QMetaType.Type.Int, QMetaType.Type.Double
except (ImportError, AttributeError):  # anciennes versions
    from qgis.PyQt.QtCore import QVariant

    T_STR, T_INT, T_DBL = QVariant.String, QVariant.Int, QVariant.Double

FAST_INSERT = getattr(getattr(QgsFeatureSink, "Flag", QgsFeatureSink), "FastInsert")
API = "https://geo.api.gouv.fr"

REGIONS = [
    ("11", "Île-de-France"), ("24", "Centre-Val de Loire"), ("27", "Bourgogne-Franche-Comté"),
    ("28", "Normandie"), ("32", "Hauts-de-France"), ("44", "Grand Est"),
    ("52", "Pays de la Loire"), ("53", "Bretagne"), ("75", "Nouvelle-Aquitaine"),
    ("76", "Occitanie"), ("84", "Auvergne-Rhône-Alpes"), ("93", "Provence-Alpes-Côte d'Azur"),
    ("94", "Corse"), ("01", "Guadeloupe"), ("02", "Martinique"), ("03", "Guyane"),
    ("04", "La Réunion"), ("06", "Mayotte"),
]
DEPARTEMENTS = [
    ("01", "Ain"), ("02", "Aisne"), ("03", "Allier"), ("04", "Alpes-de-Haute-Provence"),
    ("05", "Hautes-Alpes"), ("06", "Alpes-Maritimes"), ("07", "Ardèche"), ("08", "Ardennes"),
    ("09", "Ariège"), ("10", "Aube"), ("11", "Aude"), ("12", "Aveyron"),
    ("13", "Bouches-du-Rhône"), ("14", "Calvados"), ("15", "Cantal"), ("16", "Charente"),
    ("17", "Charente-Maritime"), ("18", "Cher"), ("19", "Corrèze"), ("21", "Côte-d'Or"),
    ("22", "Côtes-d'Armor"), ("23", "Creuse"), ("24", "Dordogne"), ("25", "Doubs"),
    ("26", "Drôme"), ("27", "Eure"), ("28", "Eure-et-Loir"), ("29", "Finistère"),
    ("2A", "Corse-du-Sud"), ("2B", "Haute-Corse"), ("30", "Gard"), ("31", "Haute-Garonne"),
    ("32", "Gers"), ("33", "Gironde"), ("34", "Hérault"), ("35", "Ille-et-Vilaine"),
    ("36", "Indre"), ("37", "Indre-et-Loire"), ("38", "Isère"), ("39", "Jura"),
    ("40", "Landes"), ("41", "Loir-et-Cher"), ("42", "Loire"), ("43", "Haute-Loire"),
    ("44", "Loire-Atlantique"), ("45", "Loiret"), ("46", "Lot"), ("47", "Lot-et-Garonne"),
    ("48", "Lozère"), ("49", "Maine-et-Loire"), ("50", "Manche"), ("51", "Marne"),
    ("52", "Haute-Marne"), ("53", "Mayenne"), ("54", "Meurthe-et-Moselle"), ("55", "Meuse"),
    ("56", "Morbihan"), ("57", "Moselle"), ("58", "Nièvre"), ("59", "Nord"),
    ("60", "Oise"), ("61", "Orne"), ("62", "Pas-de-Calais"), ("63", "Puy-de-Dôme"),
    ("64", "Pyrénées-Atlantiques"), ("65", "Hautes-Pyrénées"), ("66", "Pyrénées-Orientales"),
    ("67", "Bas-Rhin"), ("68", "Haut-Rhin"), ("69", "Rhône"), ("70", "Haute-Saône"),
    ("71", "Saône-et-Loire"), ("72", "Sarthe"), ("73", "Savoie"), ("74", "Haute-Savoie"),
    ("75", "Paris"), ("76", "Seine-Maritime"), ("77", "Seine-et-Marne"), ("78", "Yvelines"),
    ("79", "Deux-Sèvres"), ("80", "Somme"), ("81", "Tarn"), ("82", "Tarn-et-Garonne"),
    ("83", "Var"), ("84", "Vaucluse"), ("85", "Vendée"), ("86", "Vienne"),
    ("87", "Haute-Vienne"), ("88", "Vosges"), ("89", "Yonne"), ("90", "Territoire de Belfort"),
    ("91", "Essonne"), ("92", "Hauts-de-Seine"), ("93", "Seine-Saint-Denis"),
    ("94", "Val-de-Marne"), ("95", "Val-d'Oise"), ("971", "Guadeloupe"),
    ("972", "Martinique"), ("973", "Guyane"), ("974", "La Réunion"), ("976", "Mayotte"),
]
# (type, code, libellé affiché)
TERRITOIRES = [("region", c, f"Région · {n}") for c, n in REGIONS] + [
    ("departement", c, f"Département · {c} {n}") for c, n in DEPARTEMENTS
]
CODES_OUTRE_MER = {"01", "02", "03", "04", "06", "971", "972", "973", "974", "976"}

METHODES = [
    "Échelle nationale (6 classes, comparable d'une région à l'autre)",
    "Seuils naturels de Jenks (6 classes, adaptés au territoire)",
    "Quantiles (6 classes de même effectif)",
]
# Échelle nationale : du rural isolé au cœur des grandes villes (hab/km²)
ECHELLE_NATIONALE = [
    (0, 50, "Moins de 50 hab/km²"),
    (50, 200, "50 – 200 hab/km²"),
    (200, 1000, "200 – 1 000 hab/km²"),
    (1000, 5000, "1 000 – 5 000 hab/km²"),
    (5000, 15000, "5 000 – 15 000 hab/km²"),
    (15000, 10 ** 7, "Plus de 15 000 hab/km²"),
]
RAMPE = "YlOrRd"
GRIS_SANS_DONNEE = QColor("#c8c8c8")

# Les post-processeurs doivent survivre à l'instance de l'algorithme (détruite avant
# le chargement des couches) : on garde une référence au niveau du module.
_POST_PROCESSEURS = []


def _get_json(url, feedback):
    """GET via le gestionnaire réseau de QGIS (respecte le proxy configuré)."""
    req = QgsBlockingNetworkRequest()
    err = req.get(QNetworkRequest(QUrl(url)), feedback=feedback)
    if err != QgsBlockingNetworkRequest.ErrorCode.NoError:
        raise QgsProcessingException(f"Échec de l'appel à l'API Géo : {req.errorMessage()}")
    return json.loads(bytes(req.reply().content()).decode("utf-8"))


class _StylePostProcessor(QgsProcessingLayerPostProcessorInterface):
    """Applique le nom et la symbologie une fois la couche chargée dans le projet."""

    def __init__(self, methode, nom):
        super().__init__()
        self.methode = methode
        self.nom = nom

    def postProcessLayer(self, layer, context, feedback):
        layer.setName(self.nom)
        layer.setRenderer(construire_rendu(layer, self.methode))
        layer.triggerRepaint()
        _zoomer_sur(layer)


def _zoomer_sur(layer):
    """Centre la carte de QGIS sur le territoire calculé (si l'interface est disponible)."""
    try:
        from qgis.utils import iface
    except ImportError:
        return
    if iface is None or iface.mapCanvas() is None:
        return
    canvas = iface.mapCanvas()
    vers_canvas = QgsCoordinateTransform(layer.crs(), canvas.mapSettings().destinationCrs(),
                                         QgsProject.instance())
    emprise = vers_canvas.transformBoundingBox(layer.extent())
    emprise.scale(1.05)
    canvas.setExtent(emprise)
    canvas.refresh()


class _PointsPostProcessor(QgsProcessingLayerPostProcessorInterface):
    def __init__(self, nom):
        super().__init__()
        self.nom = nom

    def postProcessLayer(self, layer, context, feedback):
        layer.setName(self.nom)
        sym = QgsSymbol.defaultSymbol(layer.geometryType())
        sym.setColor(QColor("#2b2b2b"))
        sym.setSize(0.9)
        sym.symbolLayer(0).setStrokeColor(QColor("white"))
        sym.symbolLayer(0).setStrokeWidth(0.1)
        layer.renderer().setSymbol(sym)
        layer.triggerRepaint()


def _symbole_polygone(couleur):
    sym = QgsSymbol.defaultSymbol(Qgis.GeometryType.Polygon)
    sym.setColor(couleur)
    sym.symbolLayer(0).setStrokeColor(QColor(255, 255, 255, 180))
    sym.symbolLayer(0).setStrokeWidth(0.08)
    return sym


def construire_rendu(layer, methode):
    """Rendu gradué sur 'densite' + règle « Sans donnée » en gris (aucun trou dans la carte)."""
    rampe = QgsStyle.defaultStyle().colorRamp(RAMPE)
    if methode == 0:
        n = len(ECHELLE_NATIONALE) - 1
        ranges = [QgsRendererRange(a, b, _symbole_polygone(rampe.color(i / n)), lib)
                  for i, (a, b, lib) in enumerate(ECHELLE_NATIONALE)]
        grad = QgsGraduatedSymbolRenderer("densite", ranges)
    else:
        grad = QgsGraduatedSymbolRenderer("densite")
        grad.setSourceSymbol(_symbole_polygone(QColor("orange")))
        grad.setSourceColorRamp(rampe)
        grad.setClassificationMethod(QgsClassificationJenks() if methode == 1 else QgsClassificationQuantile())
        grad.classificationMethod().setLabelFormat("%1 – %2 hab/km²")
        grad.classificationMethod().setLabelPrecision(0)
        grad.updateClasses(layer, 6)
        grad.updateColorRamp(rampe)

    racine = QgsRuleBasedRenderer.Rule(None)
    QgsRuleBasedRenderer.refineRuleRanges(racine, grad)  # une règle par classe
    sans = QgsRuleBasedRenderer.Rule(_symbole_polygone(GRIS_SANS_DONNEE), label="Sans donnée", elseRule=True)
    racine.appendChild(sans)
    return QgsRuleBasedRenderer(racine)


class DensiteCommunaleAlgorithm(QgsProcessingAlgorithm):
    TERRITOIRE = "TERRITOIRE"
    METHODE = "METHODE"
    AVEC_CENTROIDES = "AVEC_CENTROIDES"
    SORTIE = "SORTIE"
    CENTROIDES = "CENTROIDES"

    def tr(self, texte):
        return QCoreApplication.translate("DensiteCommunale", texte)

    def createInstance(self):
        return DensiteCommunaleAlgorithm()

    def name(self):
        return "densite_communale"

    def displayName(self):
        return self.tr("Carte de densité communale (API Géo)")

    def group(self):
        return self.tr("Démographie")

    def groupId(self):
        return "demographie"

    def shortHelpString(self):
        return self.tr(
            "<p>Télécharge les communes d'une région ou d'un département depuis l'API Géo "
            "(geo.api.gouv.fr) — contours et populations légales les plus récentes — puis "
            "calcule la densité de population (hab/km², surface ellipsoïdale).</p>"
            "<p>La carte est stylée automatiquement : classes au choix, communes sans "
            "population affichées en gris, centroïdes en option.</p>"
            "<p>Aucune donnée locale n'est nécessaire.</p>"
        )

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterEnum(
            self.TERRITOIRE, self.tr("Territoire"),
            options=[t[2] for t in TERRITOIRES], defaultValue=0))
        self.addParameter(QgsProcessingParameterEnum(
            self.METHODE, self.tr("Méthode de classification"),
            options=METHODES, defaultValue=0))
        self.addParameter(QgsProcessingParameterBoolean(
            self.AVEC_CENTROIDES, self.tr("Produire aussi les centroïdes des communes"),
            defaultValue=False))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.SORTIE, self.tr("Densité communale"), QgsProcessing.TypeVectorPolygon))
        # Les centroïdes sont une couche temporaire créée si la case est cochée
        self.addOutput(QgsProcessingOutputVectorLayer(
            self.CENTROIDES, self.tr("Centroïdes"), QgsProcessing.TypeVectorPoint))

    def processAlgorithm(self, parameters, context, feedback):
        type_terr, code, libelle = TERRITOIRES[self.parameterAsEnum(parameters, self.TERRITOIRE, context)]
        methode = self.parameterAsEnum(parameters, self.METHODE, context)
        avec_centroides = self.parameterAsBoolean(parameters, self.AVEC_CENTROIDES, context)
        nom_court = libelle.split(" · ", 1)[1]

        # 1. Téléchargement ------------------------------------------------
        filtre = "codeRegion" if type_terr == "region" else "codeDepartement"
        url = (f"{API}/communes?{filtre}={code}"
               "&fields=nom,code,codeDepartement,population"
               "&format=geojson&geometry=contour")
        feedback.pushInfo(f"Téléchargement des communes : {libelle}")
        feedback.pushDebugInfo(url)
        geojson = _get_json(url, feedback)
        entites = geojson.get("features", [])
        if not entites:
            raise QgsProcessingException("Aucune commune renvoyée par l'API pour ce territoire.")
        feedback.pushInfo(f"{len(entites)} communes reçues.")
        feedback.setProgress(30)

        # 2. Préparation des sorties ---------------------------------------
        crs_wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
        outre_mer = code in CODES_OUTRE_MER
        crs_sortie = crs_wgs84 if outre_mer else QgsCoordinateReferenceSystem("EPSG:2154")
        vers_sortie = QgsCoordinateTransform(crs_wgs84, crs_sortie, context.transformContext())

        aire = QgsDistanceArea()
        aire.setSourceCrs(crs_wgs84, context.transformContext())
        aire.setEllipsoid("EPSG:7030")

        champs = QgsFields()
        for nom, typ in [("code_insee", T_STR), ("nom", T_STR), ("code_dep", T_STR),
                         ("population", T_INT), ("surface_km2", T_DBL), ("densite", T_DBL)]:
            champs.append(QgsField(nom, typ))

        sink, dest_id = self.parameterAsSink(parameters, self.SORTIE, context, champs,
                                             Qgis.WkbType.MultiPolygon, crs_sortie)
        if sink is None:
            raise QgsProcessingException(self.invalidSinkError(parameters, self.SORTIE))

        points = []  # centroïdes, si demandés

        # 3. Calcul ------------------------------------------------------------
        sans_pop = []
        for i, f in enumerate(entites):
            if feedback.isCanceled():
                break
            p = f["properties"]
            geom = QgsJsonUtils.geometryFromGeoJson(json.dumps(f["geometry"]))
            if geom is None or geom.isEmpty():
                feedback.reportError(f"Géométrie absente : {p.get('nom')} ({p.get('code')})")
                continue
            if not geom.isMultipart():
                geom.convertToMultiType()
            km2 = aire.measureArea(geom) / 1e6
            pop = p.get("population")
            dens = round(pop / km2, 1) if pop is not None and km2 > 0 else None
            if dens is None:
                sans_pop.append(p.get("nom"))
            geom.transform(vers_sortie)

            feat = QgsFeature(champs)
            feat.setGeometry(geom)
            feat.setAttributes([p.get("code"), p.get("nom"), p.get("codeDepartement"),
                                pop, round(km2, 3), dens])
            sink.addFeature(feat, FAST_INSERT)
            if avec_centroides:
                pt = QgsFeature(feat)
                pt.setGeometry(geom.pointOnSurface())  # toujours à l'intérieur de la commune
                points.append(pt)
            feedback.setProgress(30 + 70 * i / len(entites))

        if sans_pop:
            feedback.pushWarning(f"{len(sans_pop)} commune(s) sans population (en gris) : "
                                 + ", ".join(sans_pop[:10]))

        # 4. Nom et style appliqués au chargement ------------------------------
        _POST_PROCESSEURS.clear()
        if context.willLoadLayerOnCompletion(dest_id):
            post = _StylePostProcessor(methode, f"Densité communale — {nom_court}")
            _POST_PROCESSEURS.append(post)
            context.layerToLoadOnCompletionDetails(dest_id).setPostProcessor(post)
        resultats = {self.SORTIE: dest_id}
        if avec_centroides:
            nom_pts = f"Centroïdes — {nom_court}"
            couche_pts = QgsVectorLayer(f"Point?crs={crs_sortie.authid()}", nom_pts, "memory")
            couche_pts.dataProvider().addAttributes(champs.toList())
            couche_pts.updateFields()
            couche_pts.dataProvider().addFeatures(points)
            context.temporaryLayerStore().addMapLayer(couche_pts)
            details = QgsProcessingContext.LayerDetails(nom_pts, context.project(), self.CENTROIDES)
            post_pts = _PointsPostProcessor(nom_pts)
            _POST_PROCESSEURS.append(post_pts)
            details.setPostProcessor(post_pts)
            if hasattr(details, "layerSortKey"):  # QGIS >= 3.32 : points au-dessus des polygones
                details.layerSortKey = 1
            context.addLayerToLoadOnCompletion(couche_pts.id(), details)
            resultats[self.CENTROIDES] = couche_pts.id()
        return resultats
