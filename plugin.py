from .area_ha_plugin import AreaHaPlugin
from .exportar_shp_contexto import ExportarShpContexto
from .linhas_plantio_plugin import LinhasPlantioPlugin
from .pegar_coordenadas_plugin import PegarCoordenadasPlugin


class UtilidadesQgisUnificadasPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.plugins = [
            PegarCoordenadasPlugin(iface),
            AreaHaPlugin(iface),
            ExportarShpContexto(iface),
            LinhasPlantioPlugin(iface),
        ]

    def initGui(self):
        for plugin in self.plugins:
            plugin.initGui()

    def unload(self):
        for plugin in reversed(self.plugins):
            plugin.unload()
