import os
import re
import shutil
import unicodedata

from qgis.PyQt.QtCore import QSettings
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsProcessingUtils,
    QgsProject,
    QgsVectorFileWriter,
    QgsWkbTypes,
)
from qgis.gui import QgsProjectionSelectionDialog
from qgis.utils import iface


PASTA_MODELOS = r"H:\.shortcut-targets-by-id\1gJjLOcoLG91vR2YcoU27K5wUNRkzJQtD\10 - DOCUMENTOS\QGIS\Modelos"
PASTA_PROJETOS_PADRAO = r"H:\.shortcut-targets-by-id\1IExiNMqrbm1S113Lgktk-atPw7dpIxi6\02 - PROJETOS\MRS\Projetos"
SETTINGS_KEY = "feratools/exportar"
CRS_SAIDA_PADRAO = "EPSG:31983"


def limpar_nome_arquivo(nome):
    nome = unicodedata.normalize("NFKD", nome).encode("ASCII", "ignore").decode("ASCII")
    nome = nome.replace(" ", "_")
    nome = re.sub(r"[^A-Za-z0-9_\-]", "", nome)
    return nome


def obter_prefixo_geometria(layer):
    if not layer:
        return None

    if layer.geometryType() == QgsWkbTypes.PointGeometry:
        return "PT_"
    if layer.geometryType() == QgsWkbTypes.LineGeometry:
        return "PL_"
    if layer.geometryType() == QgsWkbTypes.PolygonGeometry:
        return "POL_"
    return None


def detectar_formato(layer):
    if not layer:
        return "Desconhecido"

    source = (layer.source() or "").lower()

    if source.endswith(".shp"):
        return "Shapefile"
    if ".gpkg" in source:
        return "GeoPackage"
    if source.endswith(".geojson") or source.endswith(".json"):
        return "GeoJSON"
    if layer.providerType() == "memory":
        return "Memoria temporaria"
    if source.endswith(".kml"):
        return "KML"
    if source.endswith(".dxf"):
        return "DXF"
    return f"Outro ({layer.providerType()})"


def listar_estilos_qml(pasta_modelos):
    estilos = []

    if not os.path.isdir(pasta_modelos):
        return estilos

    try:
        for arquivo in sorted(os.listdir(pasta_modelos)):
            if arquivo.lower().endswith(".qml"):
                estilos.append(arquivo)
    except Exception:
        pass

    return estilos


def copiar_estilo_para_saida(caminho_estilo_origem, caminho_shp_saida):
    if not caminho_estilo_origem or not os.path.isfile(caminho_estilo_origem):
        return None

    base_saida = os.path.splitext(caminho_shp_saida)[0]
    caminho_qml_saida = base_saida + ".qml"
    shutil.copy2(caminho_estilo_origem, caminho_qml_saida)
    return caminho_qml_saida


def arquivos_do_conjunto_shapefile(caminho_shp):
    base_saida = os.path.splitext(caminho_shp)[0]
    extensoes = [
        ".shp", ".shx", ".dbf", ".prj", ".cpg", ".qpj", ".qix",
        ".sbn", ".sbx", ".idm", ".ind", ".ain", ".aih", ".ixs",
        ".mxs", ".xml", ".fix", ".atx", ".qml",
    ]

    arquivos = []
    for ext in extensoes:
        caminho = base_saida + ext
        if os.path.exists(caminho):
            arquivos.append(caminho)

    return arquivos


def existe_conjunto_shapefile(caminho_shp):
    return len(arquivos_do_conjunto_shapefile(caminho_shp)) > 0


def excluir_conjunto_shapefile(caminho_shp):
    arquivos = arquivos_do_conjunto_shapefile(caminho_shp)
    erros = []

    for arquivo in arquivos:
        try:
            os.remove(arquivo)
        except Exception as e:
            erros.append(f"{arquivo} -> {str(e)}")

    return erros


class ExportarDialog(QDialog):
    def __init__(self, layer, parent=None):
        super().__init__(parent)
        self.layer = layer
        self.crs_selecionado = None
        self.settings = QSettings()
        self.pasta_modelos = self._load_estilos_folder()

        self.setWindowTitle("Exportar camada para Shapefile")
        self.setMinimumWidth(650)

        layout = QVBoxLayout()
        layout.addWidget(QLabel(f"Camada vetorial: {self.layer.name()}"))

        self.lbl_formato = QLabel("")
        layout.addWidget(self.lbl_formato)

        layout.addWidget(QLabel("Nome do arquivo:"))
        self.nome_edit = QLineEdit()
        self.nome_edit.textChanged.connect(self.atualizar_estado_salvar)
        layout.addWidget(self.nome_edit)

        layout.addWidget(QLabel("Pasta de destino:"))
        pasta_layout = QHBoxLayout()
        self.pasta_edit = QLineEdit(self._load_destino_folder())
        self.pasta_edit.textChanged.connect(self.atualizar_estado_salvar)
        btn_pasta = QPushButton("...")
        btn_pasta.setFixedWidth(32)
        btn_pasta.clicked.connect(self.selecionar_pasta)
        pasta_layout.addWidget(self.pasta_edit)
        pasta_layout.addWidget(btn_pasta)
        layout.addLayout(pasta_layout)

        layout.addWidget(QLabel("SRC / CRS de saida:"))
        crs_layout = QHBoxLayout()
        self.crs_edit = QLineEdit()
        self.crs_edit.setReadOnly(True)
        btn_crs = QPushButton("...")
        btn_crs.setFixedWidth(32)
        btn_crs.clicked.connect(self.selecionar_crs)
        crs_layout.addWidget(self.crs_edit)
        crs_layout.addWidget(btn_crs)
        layout.addLayout(crs_layout)

        layout.addWidget(QLabel("Estilo (.qml) opcional:"))
        estilo_layout = QHBoxLayout()
        self.cmb_estilos = QComboBox()
        self.cmb_estilos.addItem("(Nenhum)", "")
        estilo_layout.addWidget(self.cmb_estilos)
        btn_modelos = QPushButton("...")
        btn_modelos.setFixedWidth(32)
        btn_modelos.clicked.connect(self.selecionar_pasta_estilos)
        estilo_layout.addWidget(btn_modelos)
        layout.addLayout(estilo_layout)

        self.lbl_pasta_modelos = QLabel("")
        layout.addWidget(self.lbl_pasta_modelos)
        self.carregar_estilos()

        self.chk_adicionar = QCheckBox("Adicionar camada exportada ao QGIS")
        self.chk_adicionar.setChecked(True)
        layout.addWidget(self.chk_adicionar)

        self.chk_temporario = QCheckBox("Salvar arquivo temporÃ¡rio")
        self.chk_temporario.toggled.connect(self.atualizar_estado_salvar)
        layout.addWidget(self.chk_temporario)

        botoes_layout = QHBoxLayout()
        self.btn_ok = QPushButton("Salvar")
        btn_cancelar = QPushButton("Cancelar")
        self.btn_ok.clicked.connect(self.salvar_shapefile)
        btn_cancelar.clicked.connect(self.reject)
        botoes_layout.addWidget(self.btn_ok)
        botoes_layout.addWidget(btn_cancelar)
        layout.addLayout(botoes_layout)

        self.setLayout(layout)
        self.atualizar_interface()

    def carregar_estilos(self):
        self.cmb_estilos.clear()
        self.cmb_estilos.addItem("(Nenhum)", "")

        estilos = listar_estilos_qml(self.pasta_modelos)
        for estilo in estilos:
            caminho_completo = os.path.join(self.pasta_modelos, estilo)
            self.cmb_estilos.addItem(estilo, caminho_completo)
        self._atualizar_label_pasta_modelos()

    def selecionar_pasta_estilos(self):
        pasta_atual = self.pasta_modelos if os.path.isdir(self.pasta_modelos) else PASTA_MODELOS
        pasta = QFileDialog.getExistingDirectory(
            self,
            "Selecionar pasta de estilos",
            pasta_atual,
        )

        if pasta:
            self.pasta_modelos = pasta
            self.settings.setValue(f"{SETTINGS_KEY}/pasta_modelos", pasta)
            self.carregar_estilos()

    def _load_estilos_folder(self):
        pasta = self.settings.value(f"{SETTINGS_KEY}/pasta_modelos", PASTA_MODELOS)
        return pasta if pasta else PASTA_MODELOS

    def _load_destino_folder(self):
        return ""

    def _atualizar_label_pasta_modelos(self):
        if os.path.isdir(self.pasta_modelos):
            texto = f"Pasta de estilos: {self.pasta_modelos}"
        else:
            texto = f"Pasta de estilos: {self.pasta_modelos} (nÃ£o encontrada)"
        self.lbl_pasta_modelos.setText(texto)

    def selecionar_pasta(self):
        pasta_atual = self.pasta_edit.text().strip()
        if not pasta_atual or not os.path.isdir(pasta_atual):
            pasta_atual = PASTA_PROJETOS_PADRAO

        pasta = QFileDialog.getExistingDirectory(
            self,
            "Selecionar pasta de destino",
            pasta_atual,
        )

        if pasta:
            self.pasta_edit.setText(pasta)

    def selecionar_crs(self):
        dialog = QgsProjectionSelectionDialog(self)

        if self.crs_selecionado and self.crs_selecionado.isValid():
            dialog.setCrs(self.crs_selecionado)
        elif self.layer and self.layer.crs().isValid():
            dialog.setCrs(self.layer.crs())

        if dialog.exec():
            self.crs_selecionado = dialog.crs()
            self.atualizar_texto_crs()
            self.atualizar_estado_salvar()

    def atualizar_texto_crs(self):
        if self.crs_selecionado and self.crs_selecionado.isValid():
            authid = self.crs_selecionado.authid()
            descricao = self.crs_selecionado.description()
            self.crs_edit.setText(f"{authid} - {descricao}")
        else:
            self.crs_edit.setText("")

    def atualizar_interface(self):
        formato = detectar_formato(self.layer)
        self.lbl_formato.setText(f"Formato atual: {formato}")

        self.nome_edit.setText("")

        crs_padrao = QgsCoordinateReferenceSystem(CRS_SAIDA_PADRAO)
        self.crs_selecionado = crs_padrao if crs_padrao.isValid() else None
        self.atualizar_texto_crs()
        self.atualizar_estado_salvar()

    def _nome_arquivo_valido(self):
        prefixo = obter_prefixo_geometria(self.layer)
        nome_digitado = self.nome_edit.text().strip()
        if nome_digitado.lower().endswith(".shp"):
            nome_digitado = nome_digitado[:-4]

        nome_arquivo = limpar_nome_arquivo(nome_digitado)
        if prefixo and nome_arquivo.startswith(prefixo):
            nome_arquivo = nome_arquivo[len(prefixo):]
        return bool(nome_arquivo)

    def atualizar_estado_salvar(self):
        if not hasattr(self, "btn_ok"):
            return

        pasta = self.pasta_edit.text().strip()
        destino_ok = self.chk_temporario.isChecked() or os.path.isdir(pasta)
        self.btn_ok.setEnabled(self._nome_arquivo_valido() and destino_ok)

    def salvar_shapefile(self):
        if not self.layer or not self.layer.isValid():
            QMessageBox.warning(self, "Aviso", "A camada selecionada Ã© invÃ¡lida.")
            return

        prefixo = obter_prefixo_geometria(self.layer)
        if not prefixo:
            QMessageBox.warning(
                self,
                "Aviso",
                "A camada selecionada nÃ£o Ã© de ponto, linha ou polÃ­gono.",
            )
            return

        nome_digitado = self.nome_edit.text().strip()
        if nome_digitado.lower().endswith(".shp"):
            nome_digitado = nome_digitado[:-4]

        nome_arquivo = limpar_nome_arquivo(nome_digitado)
        if nome_arquivo.startswith(prefixo):
            nome_arquivo = nome_arquivo[len(prefixo):]
        pasta = self.pasta_edit.text().strip()
        crs_saida = self.crs_selecionado
        caminho_estilo = self.cmb_estilos.currentData()
        adicionar_qgis = self.chk_adicionar.isChecked()
        salvar_temporario = self.chk_temporario.isChecked()

        if not nome_arquivo:
            QMessageBox.warning(self, "Aviso", "Informe um nome para o arquivo.")
            return

        if not salvar_temporario and not pasta:
            QMessageBox.warning(self, "Aviso", "Selecione uma pasta de destino.")
            return

        if not salvar_temporario and not os.path.isdir(pasta):
            QMessageBox.warning(
                self,
                "Aviso",
                "A pasta de destino nÃ£o existe ou nÃ£o estÃ¡ acessÃ­vel.",
            )
            return

        if not crs_saida or not crs_saida.isValid():
            QMessageBox.warning(self, "Aviso", "Selecione um SRC vÃ¡lido.")
            return

        if not self.layer.crs().isValid():
            QMessageBox.warning(
                self,
                "Aviso",
                "A camada de origem nÃ£o possui SRC vÃ¡lido. Defina o SRC da camada antes de exportar.",
            )
            return

        nome_arquivo = f"{prefixo}{nome_arquivo}.shp"
        if salvar_temporario:
            caminho_saida = QgsProcessingUtils.generateTempFilename(nome_arquivo)
        else:
            caminho_saida = os.path.join(pasta, nome_arquivo)

        if existe_conjunto_shapefile(caminho_saida):
            resposta = QMessageBox.question(
                self,
                "Arquivo jÃ¡ existe",
                "JÃ¡ existe um arquivo com esse nome na pasta de destino.\n\nDeseja substituir o arquivo existente?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )

            if resposta == QMessageBox.No:
                return

            erros_exclusao = excluir_conjunto_shapefile(caminho_saida)
            if erros_exclusao:
                QMessageBox.critical(
                    self,
                    "Erro",
                    "NÃ£o foi possÃ­vel substituir o arquivo existente.\n\n" + "\n".join(erros_exclusao),
                )
                return

        opcoes = QgsVectorFileWriter.SaveVectorOptions()
        opcoes.driverName = "ESRI Shapefile"
        opcoes.fileEncoding = "UTF-8"

        if self.layer.crs() != crs_saida:
            opcoes.ct = QgsCoordinateTransform(
                self.layer.crs(),
                crs_saida,
                QgsProject.instance(),
            )

        resultado = QgsVectorFileWriter.writeAsVectorFormatV3(
            self.layer,
            caminho_saida,
            QgsProject.instance().transformContext(),
            opcoes,
        )

        erro = resultado[0]
        novo_arquivo = resultado[1] if len(resultado) > 1 else ""
        mensagem = resultado[3] if len(resultado) > 3 else ""

        if erro == QgsVectorFileWriter.NoError:
            caminho_mostrar = novo_arquivo or caminho_saida

            caminho_qml_saida = None
            if caminho_estilo:
                try:
                    caminho_qml_saida = copiar_estilo_para_saida(caminho_estilo, caminho_mostrar)
                except Exception as e:
                    QMessageBox.warning(
                        self,
                        "Aviso",
                        "O shapefile foi salvo, mas nÃ£o foi possÃ­vel copiar o estilo.\n\n"
                        f"Detalhe: {str(e)}",
                    )

            if adicionar_qgis:
                if caminho_estilo and os.path.isfile(caminho_estilo):
                    nome_camada = os.path.splitext(os.path.basename(caminho_estilo))[0]
                else:
                    nome_camada = os.path.splitext(os.path.basename(caminho_mostrar))[0]

                camada_adicionada = iface.addVectorLayer(caminho_mostrar, nome_camada, "ogr")

                if not camada_adicionada:
                    QMessageBox.warning(
                        self,
                        "Aviso",
                        "O shapefile foi salvo, mas nÃ£o foi possÃ­vel adicionÃ¡-lo ao QGIS.",
                    )
                else:
                    estilo_para_carregar = caminho_qml_saida or caminho_estilo
                    if estilo_para_carregar and os.path.isfile(estilo_para_carregar):
                        camada_adicionada.loadNamedStyle(estilo_para_carregar)
                        camada_adicionada.triggerRepaint()

            self.accept()
        else:
            QMessageBox.critical(
                self,
                "Erro",
                f"Falha ao exportar o arquivo:\n{mensagem or 'Erro nÃ£o detalhado pelo QGIS.'}",
            )
