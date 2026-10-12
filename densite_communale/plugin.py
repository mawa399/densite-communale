"""Plugin QGIS « Densité communale » : bouton, menu et boîte à outils Processing."""

import os

from qgis import processing
from qgis.core import QgsApplication
from qgis.PyQt.QtGui import QIcon

try:  # Qt6 (QGIS 4)
    from qgis.PyQt.QtGui import QAction
except ImportError:  # Qt5 (QGIS 3)
    from qgis.PyQt.QtWidgets import QAction

from .provider import DensiteCommunaleProvider

ICONE = os.path.join(os.path.dirname(__file__), "icon.svg")
ALGORITHME = "densite_communale:densite_communale"


class DensiteCommunalePlugin:
    def __init__(self, iface):
        self.iface = iface
        self.provider = None
        self.action = None

    def initProcessing(self):
        self.provider = DensiteCommunaleProvider()
        QgsApplication.processingRegistry().addProvider(self.provider)

    def initGui(self):
        self.initProcessing()
        self.action = QAction(QIcon(ICONE), "Carte de densité communale…", self.iface.mainWindow())
        self.action.setToolTip("Générer la carte de densité des communes d'une région ou d'un département")
        self.action.triggered.connect(self.ouvrir)
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu("Densité communale", self.action)

    def unload(self):
        if self.action:
            self.iface.removeToolBarIcon(self.action)
            self.iface.removePluginMenu("Densité communale", self.action)
        if self.provider:
            QgsApplication.processingRegistry().removeProvider(self.provider)

    def ouvrir(self):
        processing.execAlgorithmDialog(ALGORITHME)
