"""Densité communale — plugin QGIS."""


def classFactory(iface):  # appelé par QGIS au chargement du plugin
    from .plugin import DensiteCommunalePlugin

    return DensiteCommunalePlugin(iface)
