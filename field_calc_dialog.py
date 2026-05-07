from qgis.PyQt.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)


class FieldCalcDialog(QDialog):
    def __init__(self, has_selection=False, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Criar área")
        self.resize(520, 320)

        layout = QVBoxLayout()

        unit_row = QHBoxLayout()
        unit_row.addWidget(QLabel("Unidade"))
        self.unit_group = QButtonGroup(self)
        self.unit_group.setExclusive(True)
        self.area_ha_checkbox = QCheckBox("Área em ha")
        self.area_m2_checkbox = QCheckBox("Área em m²")
        self.area_ha_checkbox.setChecked(True)
        self.unit_group.addButton(self.area_ha_checkbox)
        self.unit_group.addButton(self.area_m2_checkbox)
        unit_row.addWidget(self.area_ha_checkbox)
        unit_row.addWidget(self.area_m2_checkbox)
        unit_row.addStretch()
        layout.addLayout(unit_row)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Nome do campo"))
        self.field_name = QLineEdit("area_ha")
        row1.addWidget(self.field_name)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Tipo"))
        self.field_type = QComboBox()
        self.field_type.addItems(["Número decimal (real)"])
        row2.addWidget(self.field_type)
        layout.addLayout(row2)

        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Comprimento"))
        self.length_spin = QSpinBox()
        self.length_spin.setMinimum(1)
        self.length_spin.setMaximum(100)
        self.length_spin.setValue(10)
        row3.addWidget(self.length_spin)

        row3.addWidget(QLabel("Precisão"))
        self.precision_spin = QSpinBox()
        self.precision_spin.setMinimum(0)
        self.precision_spin.setMaximum(15)
        self.precision_spin.setValue(3)
        row3.addWidget(self.precision_spin)
        layout.addLayout(row3)

        layout.addWidget(QLabel("Expressão"))
        self.expression_edit = QPlainTextEdit()
        self.expression_edit.setPlainText("$area/10000")
        layout.addWidget(self.expression_edit)

        self.selected_only_checkbox = QCheckBox("Apenas feições selecionadas")
        self.selected_only_checkbox.setEnabled(has_selection)
        layout.addWidget(self.selected_only_checkbox)

        buttons = QHBoxLayout()
        self.ok_button = QPushButton("Executar")
        self.cancel_button = QPushButton("Cancelar")
        buttons.addStretch()
        buttons.addWidget(self.ok_button)
        buttons.addWidget(self.cancel_button)
        layout.addLayout(buttons)

        self.setLayout(layout)

        self.area_ha_checkbox.toggled.connect(self._update_area_unit)
        self.area_m2_checkbox.toggled.connect(self._update_area_unit)
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

    def _update_area_unit(self):
        if self.area_m2_checkbox.isChecked():
            self.field_name.setText("area_m2")
            self.expression_edit.setPlainText("$area")
            return

        self.field_name.setText("area_ha")
        self.expression_edit.setPlainText("$area/10000")

    def values(self):
        unit = "m2" if self.area_m2_checkbox.isChecked() else "ha"
        return {
            "field_name": self.field_name.text().strip(),
            "unit": unit,
            "length": self.length_spin.value(),
            "precision": self.precision_spin.value(),
            "expression": self.expression_edit.toPlainText().strip(),
            "selected_only": self.selected_only_checkbox.isChecked(),
        }
