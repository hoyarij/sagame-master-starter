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

from GameParser import GP
from GameStarter import GS

import os
import sys
import signal
import traceback
import psutil
import ctypes


class Runner:

    def __init__(self, runtime_path):
        self.runtime_path = runtime_path

        if sys.platform == "win32":
            self.gs = GS(os.path.join(self.runtime_path, "setting.conf"),
                         os.path.join(self.runtime_path, "chromedriver.exe"))
        else:
            self.gs = GS(os.path.join(self.runtime_path, "setting.conf"),
                         os.path.join(self.runtime_path, "chromedriver"))

    def run(self):
        self.gs.setup()
        self.gs.insert_table()


def check_mariadb():
    try:
        service = psutil.win_service_get("mysql")
    except:
        return None
    else:
        return service


def check_admin():
    try:
        is_admin = os.getuid() == 0
    except AttributeError:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0

    return is_admin


if __name__ == '__main__':

    ctypes.windll.kernel32.SetConsoleMode(ctypes.windll.kernel32.GetStdHandle(-10), 128)

    try:
        run_path = os.path.dirname(os.path.abspath(__file__))

        # if sys.platform == "win32":
            # if not check_admin():
            #     raise Exception("관리자 모드로 실행해주세요.")

            # mariadb = check_mariadb()

            # if mariadb is None:
            #     if os.path.exists("./mariadb/bin"):
            #         os.system(f"{os.path.join(run_path, 'mariadb/bin/mysql_install_db.exe')}")
            #         os.system(f"{os.path.join(run_path, 'mariadb/bin/mysqld.exe')} --initialize-insecure")
            #         os.system(f"{os.path.join(run_path, 'mariadb/bin/mysqld.exe')} --install")
            #         os.system("net stop mysql")
            #         import configparser
            #
            #         tem_conf = configparser.ConfigParser()
            #         tem_conf.read(f"{os.path.join(run_path, 'mariadb/data/my.ini')}")
            #         tem_conf.set("mysqld", "innodb_autoinc_lock_mode", "0")
            #         with open(f"{os.path.join(run_path, 'mariadb/data/my.ini')}", 'w') as f:
            #             tem_conf.write(f)
            #         os.system("net start mysql")
            #         import subprocess
            #
            #         with open("./DB.txt", "r", encoding="utf8") as f:
            #             p = subprocess.Popen([f"{os.path.join(run_path, 'mariadb/bin/mysql.exe')}", "-uroot"],
            #                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            #             p.communicate(f.read().encode())
            #             p.communicate()
            #             p.terminate()
            #     else:
            #         raise Exception("mariadb 폴더가 존재하지 않습니다.")
            # else:
            #     if mariadb.status() != "running":
            #         os.system("net start mysql")

        r = Runner(run_path)


        def unhandled_error(s, f):
            print("처리되지 않은 예외", s, f)
            r.gs.release_all()
            sys.exit(0)


        signal.signal(signal.SIGINT, unhandled_error)

        while True:
            try:
                r.run()
            except KeyboardInterrupt or SystemError or SystemExit:
                r.gs.release_all()
                sys.exit(0)
            except Exception:
                traceback.print_exc()

                r.gs.release_all()

                r = Runner(run_path)
    except:
        traceback.print_exc()
        input()
        sys.exit(0)
