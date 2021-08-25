# siu77777 // tu889955
# GameLayerManager.Instance.showMultiBet()
# 멀티배팅 화면 띄우기
# GameLayerManager.Instance.sceneLayer.$children[0]
# .ChangePanel({currentTarget: GameLayerManager.Instance.sceneLayer.$children[0].tabList.getChildAt(1)})
# 게임 종류 선택 0: 모든 1: 바카라 2: 스페셜 3: 라이브
# SceneMultiBet
# GameLayerManager.Instance.sceneLayer.$children[0].tableList.$children[$1]._host.records
# window.user._hosts[0].records 동일
# 테이블 기록 $ <- 테이블 번호
# GameLayerManager.Instance.sceneLayer.$children[0].refreshView()
# 테이블 새로고침
# GameLayerManager.Instance.sceneLayer.$children[0].lobbyFooter.btnRefreshBalance
# GameLayerManager.Instance.sceneLayer.$children[0]
# .lobbyFooter.onBtnTap({currentTarget: GameLayerManager
# .Instance.sceneLayer.$children[0].lobbyFooter.btnRefreshBalance})
from PyQt5 import uic
from PyQt5.QtCore import QThread
from PyQt5.QtWidgets import QMainWindow, QApplication

from GameStarter import GS

import os
import sys
import signal
import traceback
import ctypes

form_class = uic.loadUiType('main.ui')[0]


class Runner(QMainWindow, form_class):

    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.url_text = ''
        self.id_text = ''
        self.id2_text = ''
        self.pw_text = ''

        if os.path.isfile("./info.txt"):
            with open('./info.txt', 'r') as file:
                try:
                    s = file.read().split(',')
                    self.id.setText(s[0])
                    self.id_2.setText(s[1])
                    self.pw.setText(s[2])
                except:
                    pass

        self.run_btn.clicked.connect(self.run_btn_clicked)

    def run_btn_clicked(self):
        self.url_text = self.url.currentText()
        self.id_text = self.id.text()
        self.id2_text = self.id_2.text()
        self.pw_text = self.pw.text()
        data = self.id_text + "," + self.id2_text + "," + self.pw_text
        with open('./info.txt', 'w') as file:
            file.write(data)

        self.run1()

    def run1(self):
        try:
            window.hide()
            run_path = os.path.dirname(os.path.abspath(__file__))
            self.gs = GS(os.path.join(run_path, "setting.conf"),
                         os.path.join(run_path, "chromedriver.exe"))
            self.gs.show()
            th1 = Thread1(self)
            th1.id(self.gs, self.url_text, self.id_text, self.id2_text, self.pw_text)
            th1.start()
        except Exception as ex:
            print(ex)


class Thread1(QThread):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.url_text = ''
        self.id_text = ''
        self.id2_text = ''
        self.pw_text = ''
        self.gs = object

    def id(self, gs, url, id, id2, pw):
        self.gs = gs
        self.url_text = url
        self.id_text = id
        self.id2_text = id2
        self.pw_text = pw

    def run(self):
        self.gs.setup(self.url_text, self.id_text, self.id2_text, self.pw_text)
        self.gs.insert_table()


def check_admin():
    try:
        is_admin = os.getuid() == 0
    except AttributeError:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0

    return is_admin


def except_hook(cls, exception, traceback):
    sys.__excepthook__(cls, exception, traceback)


if __name__ == '__main__':
    import sys
    sys.excepthook = except_hook

    app = QApplication(sys.argv)
    window = Runner()
    window.show()
    app.exec_()
