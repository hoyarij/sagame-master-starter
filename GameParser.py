import datetime

from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.common.keys import Keys
from selenium.common import exceptions
from selenium.webdriver.common.by import By

import pymysql.cursors
import configparser
import time
import sys
import os
import threading


class WaitReadyState:

    def __call__(self, driver):
        state = driver.execute_script("return document.readyState")
        if state == "complete":
            return True
        else:
            return False


class WaitSaGameLoad:

    def __call__(self, driver):
        try:
            state = driver.execute_script("return window.user.appUsername")
            if state != "":
                return True
            else:
                return False
        except exceptions.JavascriptException:
            return False


class WaitMultiBetTable:

    def __init__(self, min_size):
        self.min = min_size

    def __call__(self, driver):
        try:
            state = driver.execute_script(
                f"return GameLayerManager.Instance.sceneLayer."
                f"$children[0].tableList.$children[{self.min}]._host.records"
            )

            if isinstance(state, list):
                return True
            else:
                return False

        except exceptions.JavascriptException:
            return False


class WaitBetHost:

    def __call__(self, driver):
        try:
            state = driver.execute_script(
                "return window.user._hosts.length"
            )

            if int(state) > 0:
                return True
            else:
                return False

        except exceptions.JavascriptException:
            return False
        except ValueError:
            return False


class GP:
    _CONF_DB_KEY = "DB"
    _CONF_SITE_KEY = "SITE"
    _CONF_SERVICE_KEY = "SERVICE"
    _DEFAULT_CONF_DB = ["db_host", "db_port", "db_user", "db_pwd", "db_name"]
    _DEFAULT_CONF_SITE = ["site_url", "site_id_selector", "site_pwd_selector", "site_id", "site_pwd",
                          "site_game_selector"]
    _DEFAULT_CONF_SERVICE = ['default_timeout', "default_delay", "scan_speed",
                             "table_min_size"]

    def __init__(self, setting_path, driver_path):
        self._config = configparser.ConfigParser()
        self._config.read(setting_path, encoding="utf8")
        self._check_config()

        self._site_conf = self._config[GP._CONF_SITE_KEY]
        self._db_conf = self._config[GP._CONF_DB_KEY]
        self._service_conf = self._config[GP._CONF_SERVICE_KEY]

        self._default_delay = int(self._service_conf["default_delay"])
        self._default_timeout = int(self._service_conf["default_timeout"])

        self.conn = pymysql.connect(host=self._config["DB"]["DB_HOST"],
                                    user=self._config["DB"]["DB_USER"],
                                    password=self._config["DB"]["DB_PWD"] if self._config["DB"][
                                                                                 "DB_PWD"] != ";" else None,
                                    db=self._config["DB"]["DB_NAME"],
                                    charset="utf8",
                                    port=int(self._config["DB"]["DB_PORT"]),
                                    cursorclass=pymysql.cursors.DictCursor)

        self.driver = webdriver.Chrome(driver_path)
        self.driver.implicitly_wait(self._default_timeout)

        self.last_tables = {}
        self.last_update = 0.0

    def __del__(self):
        try:
            self.timer.cancel()
        except:
            pass

    def _login(self):
        self.driver.get(self._site_conf["site_url"])

        WebDriverWait(self.driver, self._default_timeout).until(WaitReadyState())
        WebDriverWait(self.driver, self._default_timeout).until(
            ec.element_to_be_clickable((By.CSS_SELECTOR, self._site_conf["site_id_selector"]))
        )

        id_input = self.driver.find_element_by_css_selector(self._site_conf["site_id_selector"])
        id_input.send_keys(self._site_conf["site_id"])
        pwd_input = self.driver.find_element_by_css_selector(self._site_conf["site_pwd_selector"])
        pwd_input.send_keys(self._site_conf["site_pwd"])
        pwd_input.send_keys(Keys.ENTER)
        time.sleep(self._default_delay)

    def _start_sa_game(self):
        window_handle = self.driver.window_handles.copy()
        self.driver.find_element_by_css_selector(self._site_conf["site_game_selector"]).click()

        WebDriverWait(self.driver, self._default_timeout).until(
            ec.new_window_is_opened(window_handle)
        )

        self.driver.close()

        self.driver.switch_to.window(self.driver.window_handles[-1])

    def _wait_sa_load(self):
        WebDriverWait(self.driver, self._default_timeout).until(
            WaitSaGameLoad()
        )
        time.sleep(self._default_delay)

    def _switch_multi_bet(self):
        WebDriverWait(self.driver, self._default_timeout).until(
            WaitBetHost()
        )

        self.driver.execute_script("GameLayerManager.Instance.showMultiBet()")

        time.sleep(self._default_delay)

        self.driver.execute_script(
            "GameLayerManager.Instance.sceneLayer.$children[0]."
            "ChangePanel({currentTarget: GameLayerManager.Instance.sceneLayer.$children[0].tabList.getChildAt(1)})"
        )

    def _wait_multi_bet(self):
        WebDriverWait(self.driver, self._default_timeout).until(
            WaitMultiBetTable(self._service_conf["table_min_size"])
        )
        time.sleep(self._default_delay)

    def parse_table(self):
        index = self.driver.execute_script(
            "return window.user._hosts.length"
        )
        while True:
            for i in range(index):
                records = self.driver.execute_script(
                    f"return window.user._hosts[{i}].records"
                )
                host_id = self.driver.execute_script(
                    f"return window.user._hosts[{i}]._hostID"
                )

                connected = self.driver.execute_script(
                    "return window.user._net._socket._connected"
                )

                if not connected:
                    raise Exception("연결 끊김")

                if records == self.last_tables.get(f"{host_id}"):
                    continue

                if not records:
                    continue

                for record in records:
                    #print(record)
                    if record["__class__"] != "BaccRecord": continue
                    if record["_playerWin"] is True or record["_playerWin"] == 1 or record["_playerWin"] == '1':
                        winner = 'P'
                    elif record["_bankerWin"] is True or record["_bankerWin"] == 1 or record["_bankerWin"] == '1':
                        winner = 'B'
                    elif record["_tie"] is True or record["_tie"] == 1 or record["_bankerWin"] == '1':
                        winner = 'T'
                    self._insert_data(
                        [record["_gameID"], record["_result"], host_id, winner]
                    )

                self.last_tables[f"{host_id}"] = records
            time.sleep(float(self._service_conf["scan_speed"]))
            self.last_update = time.time()
            self.driver.find_element_by_tag_name("canvas").click()
            time1 = datetime.datetime.now().strftime("%H:%M:%S")
            print(f"{time1} : 여기까지 옴")
            # sid = self.driver.page_source
            # print('여기까지 옴2')
            # print(f'session정보 : {sid}')
            # print(f'session정보 : \n{sid},\ntag 이름 : {sid.tag_name}\ntext 내용 : {sid.text}')
            # print(self.last_tables)

    def _insert_data(self, data):
        try:
            with self.conn.cursor() as cursor:
                sql = "insert ignore into games(game_id, result_id, host_id, winner)" \
                      " VALUES(%s, %s, %s, %s) on duplicate key update game_id=game_id"
                cursor.execute(sql, data)

            self.conn.commit()
        except Exception:
            pass

    def _check_config(self):

        if set(GP._DEFAULT_CONF_DB) != set((dict(self._config.items(GP._CONF_DB_KEY)).keys())):
            raise Exception("필요한 설정 항목이 없습니다.")
        if '' in dict(self._config.items(GP._CONF_DB_KEY)).values():
            raise Exception("비어있는 설정이 있습니다.")

        if set(GP._DEFAULT_CONF_SITE) != set((dict(self._config.items(GP._CONF_SITE_KEY)).keys())):
            raise Exception("필요한 설정 항목이 없습니다.")
        if '' in dict(self._config.items(GP._CONF_SITE_KEY)).values():
            raise Exception("비어있는 설정이 있습니다.")

        if set(GP._DEFAULT_CONF_SERVICE) != set((dict(self._config.items(GP._CONF_SERVICE_KEY)).keys())):
            raise Exception("필요한 설정 항목이 없습니다.")
        if '' in dict(self._config.items(GP._CONF_SERVICE_KEY)).values():
            raise Exception("비어있는 설정이 있습니다.")

    def _health_checker(self):
        if (time.time() - self.last_update) > 30:
            raise TimeoutError("응답 없음")

        self.timer = threading.Timer(5, self._health_checker)
        self.timer.daemon = True
        self.timer.start()

    def setup(self):
        self._login()
        self._start_sa_game()
        self._wait_sa_load()
        self._switch_multi_bet()
        self._wait_multi_bet()
        self.last_update = time.time()
        self._health_checker()

    def release_all(self):
        try:
            self.driver.quit()
        finally:
            print("웹 드라이버 종료")

        try:
            self.conn.close()
        finally:
            print("DB 드라이버 종료")

        try:
            if sys.platform == "win32":
                os.system("taskkill /f /im chromedriver.exe /t")

            time.sleep(3)
        finally:
            time1 = datetime.datetime.now().strftime("%H:%M:%S")
            print(f"{time1} : 잔여 프로세스 정리")
