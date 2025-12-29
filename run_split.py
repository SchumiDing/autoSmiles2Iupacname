from run import *
import time
import os
import json
import sys
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFileDialog,
)

class chem_draw_worker_split(chem_draw_worker):
    def __init__(self):
        super().__init__()
        self.p_img = None
        self.pre_img = None
        self.post_img = None
        self.cap = 5
        self.inert_gases = {
            "He": ["Helium",
                   "helium",
                   "Helio",
                   "helio"],
            "Ne": ["Neon",
                   "neon",
                   "Neio",
                   "neio"],
            "Ar": ["Argon",
                   "argon",
                   "Argio",
                   "argio"],
            "Kr": ["Krypton",
                   "krypton",
                   "Kryptio",
                   "kryptio"],
            "Xe": ["Xenon",
                   "xenon",
                   "Xenio",
                   "xenio"],
            "Rn": ["Radon",
                   "radon",
                   "Radonio",
                   "radonio"],
        }
        self.placeholder = "[Chemical_bond]"
    
    def find_inert_gas(self, smiles: str) -> str:
        for gas, names in self.inert_gases.items():
            if gas not in smiles and gas.lower() not in smiles.lower():
                return gas
        # impossible to have all inert gases in the same molecule
        
    def draw_chem_split(self, org_smiles: str) -> None:
        """
        Draw the given chemical formula.
        """
        inert_gas = self.find_inert_gas(org_smiles)
        
        new_smiles = org_smiles.replace("*", f"[{inert_gas}]")
        
        iupac_name = self.draw_chem(new_smiles)
        
        for possible_name in self.inert_gases[inert_gas]:
            iupac_name = iupac_name.replace(possible_name, self.placeholder)
        
        return iupac_name
        


def wait_until_space_up():
    """
    Block until the space bar is released (if currently pressed).
    Uses Quartz key state so it does not require sudo (only normal Accessibility).
    """
    while not is_space_pressed():
        time.sleep(0.01)

class App(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Auto IU2 SM")
        self.resize(360, 180)

        self.smiles_file = ""

        layout = QVBoxLayout()
        self.prompt = QLabel("请输入包含断键的 smiles 文件路径。按下提交后切换回 ChemDraw，创建空白文档并按空格开始。")
        self.input = QLineEdit()
        self.browse_btn = QPushButton("浏览...")
        self.submit_button = QPushButton("提交")
        layout.addWidget(self.prompt)
        layout.addWidget(self.input)
        layout.addWidget(self.browse_btn)
        layout.addWidget(self.submit_button)
        self.setLayout(layout)

        self.browse_btn.clicked.connect(self.browse_file)
        self.submit_button.clicked.connect(self.submit)

    def browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择 smiles 文件", "", "Text Files (*.txt);;All Files (*)")
        if file_path:
            self.input.setText(file_path)

    def submit(self):
        self.smiles_file = self.input.text().strip()
        if not self.smiles_file:
            self.prompt.setText(f"请输入 smiles 文件路径。按下submit后切换回 ChemDraw，创建空白文档并按空格开始，结果将写入 {self.smiles_file}.json")
            return
        if not os.path.exists(self.smiles_file):
            self.prompt.setText(f"文件不存在: {self.smiles_file}")
            return

        # self.prompt.setText(
        #     f"请切换回 ChemDraw，空白文档按空格开始，结果将写入 {self.smiles_file}.json"
        # )

        try:
            self.run_pipeline(self.smiles_file)
            self.prompt.setText(f"结果已保存至 {self.smiles_file}.json")
        except Exception as exc:
            self.prompt.setText(f"出错: {exc}")

    def run_pipeline(self, smiles_file):
        wait_until_space_up()
        cdw = chem_draw_worker_split()
        with open(smiles_file, "r") as f:
            smiles_list = [line.strip() for line in f if line.strip()]

        data = []
        for smiles in smiles_list:
            data.append({
                "smiles": smiles,
                "iupac_name": cdw.draw_chem_split(smiles)
            })

        output_path = f"{smiles_file}.json"
        with open(output_path, "w") as f:
            json.dump(data, f, indent=4)


if __name__ == "__main__":
    qt_app = QApplication(sys.argv)
    window = App()
    window.show()
    sys.exit(qt_app.exec())