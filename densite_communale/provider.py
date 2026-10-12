"""Fournisseur Processing : range l'algorithme dans la boîte à outils de QGIS."""

import os

from qgis.core import QgsProcessingProvider
from qgis.PyQt.QtGui import QIcon

from .densite_algorithm import DensiteCommunaleAlgorithm

ICONE = os.path.join(os.path.dirname(__file__), "icon.svg")


class DensiteCommunaleProvider(QgsProcessingProvider):
    def id(self):
        return "densite_communale"

    def name(self):
        return "Densité communale"

    def icon(self):
        return QIcon(ICONE)

    def loadAlgorithms(self):
        self.addAlgorithm(DensiteCommunaleAlgorithm())
