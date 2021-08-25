import configparser
import datetime
import itertools
import logging
import os
import random
import threading
import time
import timeit
from logging import handlers

import chromedriver_autoinstaller as ca
import pymysql.cursors
from PyQt5 import uic, QtGui
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QMainWindow, QTableWidgetItem, QAbstractItemView
from selenium import webdriver
from selenium.common import exceptions
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait


class WaitReadyState:

    def __call__(self, driver):
        state = driver.execute_script("return document.readyState")
        return True if state == "complete" else False


class WaitSaGameLoad:

    def __call__(self, driver):
        try:
            state = driver.execute_script("return window.user.appUsername")
            return True if state != "" else False
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
            return True if isinstance(state, list) else False
        except exceptions.JavascriptException:
            return False


class WaitBetHost:
    def __call__(self, driver):
        try:
            state = driver.execute_script("return window.user._hosts.length")
            return True if int(state) > 0 else False
        except exceptions.JavascriptException:
            return False
        except ValueError:
            return False


form_class = uic.loadUiType('main1.ui')[0]


class GS(QMainWindow, form_class):
    _CONF_DB_KEY = "DB"
    _CONF_SITE_KEY = "SITE"
    _CONF_SERVICE_KEY = "SERVICE"
    _DEFAULT_CONF_DB = ["db_host", "db_port", "db_user", "db_pwd", "db_name"]
    _DEFAULT_CONF_SITE = ["site_url", "site_id_selector", "site_pwd_selector", "sagame_id", "site_id", "site_pwd", "site_game_selector"]
    _DEFAULT_CONF_SERVICE = ['default_timeout', "default_delay", "scan_speed", "table_min_size"]

    def __init__(self, setting_path, driver_path):
        super().__init__()
        self.setupUi(self)
        self._url, self._id, self._id2, self._pw = '', '', '', ''
        self._config = configparser.ConfigParser()
        self._config.read(setting_path, encoding="utf8")
        self._check_config()

        self._site_conf = self._config[GS._CONF_SITE_KEY]
        self._db_conf = self._config[GS._CONF_DB_KEY]
        self._service_conf = self._config[GS._CONF_SERVICE_KEY]

        self._default_delay = int(self._service_conf["default_delay"])
        self._default_timeout = int(self._service_conf["default_timeout"])

        self.conn = pymysql.connect(host=self._config["DB"]["DB_HOST"],
                                    user=self._config["DB"]["DB_USER"],
                                    password=self._config["DB"]["DB_PWD"] if self._config["DB"]["DB_PWD"] != ";" else None,
                                    db=self._config["DB"]["DB_NAME"],
                                    charset="utf8",
                                    port=int(self._config["DB"]["DB_PORT"]))

        self.cossql = "SELECT DATE_FORMAT(date,'%Y-%m-%d %H:%i:%s') AS date, step, ta, bp, beBP FROM " \
                      "(SELECT date, step, ta, bp, beBP FROM sub01save use index (idx_datename) " \
                      "WHERE date BETWEEN DATE_ADD(now(), INTERVAL -1200 second) AND now() AND " \
                      "name = 'NG') AS dout ORDER BY dout.date DESC"

        self.cossql1 = "SELECT DATE_FORMAT(date,'%Y-%m-%d %H:%i:%s') AS date, step, ta, bp, beBP FROM " \
                       "(SELECT date, step, ta, bp, beBP FROM sub01save use index (idx_datename) " \
                       "WHERE date BETWEEN DATE_ADD(now(), INTERVAL -25 second) AND now() AND " \
                       "name = 'NG') AS dout ORDER BY dout.date DESC"

        self.sqldatasql = "SELECT DATE_FORMAT(date,'%Y-%m-%d %H:%i:%s') AS date, name, step, bp, ta FROM " \
                          "(SELECT date, name, step, bp, ta FROM sub01saveB use index (idx_datename) " \
                          "WHERE date BETWEEN DATE_ADD(now(), INTERVAL -25 second) AND now() AND " \
                          "name = '{}') AS dout "

        self.sqlT = "SELECT host_id AS ta, DATE_FORMAT(CD,'%Y-%m-%d %H:%i:%s') AS CD FROM " \
                    "(SELECT host_id, create_datetime AS CD FROM games1 use index (cd_idx) " \
                    "WHERE create_datetime BETWEEN DATE_ADD(now(), INTERVAL -25 second) AND now()) AS dout "

        self.insertquery = "INSERT INTO sub10%s VALUES(null, '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s')"

        self.attDatasql = "SELECT DATE_FORMAT(date,'%Y-%m-%d %H:%i:%s') AS date, name, step, bp, ta, beBP FROM " \
                          "(SELECT date, name, step, bp, ta, beBP FROM sub01save use index (idx_datename) " \
                          "WHERE date BETWEEN DATE_ADD(now(), INTERVAL -25 second) AND now() AND " \
                          "name = 'NG') AS dout"

        self.attSaveData = 'UPDATE sub10save SET ' \
                           'NG = "%s", OG = "%s", BG = "%s", BB = "%s", YJ = "%s", YK = "%s" ' \
                           'WHERE id = "%s" AND driving = "%s"'

        option = Options()
        option.add_argument("disable-gpu")  # 가속 사용 x
        option.add_argument("lang=ko_KR")  # 가짜 플러그인 탑재
        option.add_argument('user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.3163.100 Safari/537.36')  # user-agent 이름 설정

        path = ca.install()
        self.driver = webdriver.Chrome(path, chrome_options=option)
        self.driver.set_window_size(1300, 950)
        # self.driver = webdriver.Chrome(driver_path)
        self.driver.implicitly_wait(self._default_timeout)

        self.driving = ''
        self.last_tables = {}
        self.last_update = 0.0
        self.start_no = ['0']
        self.from_db, self.table_no = [], []
        self.table_noCnt, self.ctrlCnt = 0, 0
        self.cosFirst = True
        self.dbtablesum, self.dt, self.sagamearr, self.changeBP = [], [], [], []
        self.change, self.cntnum, self.delaycnt, self.dispno = 0, 0, 0, 0
        self.nobetcnt, self.overcnt = [], []

        self.money0, self.money1, self.money2 = 0, 0, 0
        self.wlData, self.ldata = [], []

        self.onecnt, self.ctrldata, self.attack = True, True, False
        self.ctrlNG, self.ctrlOG, self.ctrlBG, self.ctrlBB, self.ctrlYJ, self.ctrlYK = [], [], [], [], [], []
        self.bet_list, self.dispdata= [], []

        formatter = logging.Formatter('%(asctime)s %(message)s')
        # self.logger1 = 매수 로그 남기기
        fh1 = handlers.TimedRotatingFileHandler(filename='infodata/1infoStart.txt', when='midnight', interval=1, encoding='utf-8')
        fh1.setFormatter(formatter)
        fh1.suffix = '%m-%d.txt'
        fh1.setLevel(logging.INFO)
        self.logger1 = logging.getLogger("my1")
        self.logger1.setLevel(logging.INFO)
        self.logger1.addHandler(fh1)
        self.logger1.propagate = False
        self.logger1.info("===================start====================")
        # self.logger2 = 편입, 이탈 로그 남기기
        fh2 = handlers.TimedRotatingFileHandler(filename='infodata/2infoAttack.txt', when='midnight', interval=1, encoding='utf-8')
        fh2.setFormatter(formatter)
        fh2.suffix = '%m-%d.txt'
        fh2.setLevel(logging.INFO)
        self.logger2 = logging.getLogger("my2")
        self.logger2.setLevel(logging.INFO)
        self.logger2.addHandler(fh2)
        self.logger2.propagate = False
        self.logger2.info("===================start====================")

        # # self.logger3 = 미체결 취소 로그 남기기
        fh3 = handlers.TimedRotatingFileHandler(filename='infodata/3infoCheck.txt', when='midnight', interval=1, encoding='utf-8')
        fh3.setFormatter(formatter)
        fh3.setLevel(logging.INFO)
        self.logger3 = logging.getLogger("my3")
        self.logger3.setLevel(logging.INFO)
        self.logger3.addHandler(fh3)
        self.logger3.propagate = False
        self.logger3.info("==================================start====================================")

        # # self.logger4 = 시간체크
        fh4 = handlers.TimedRotatingFileHandler(filename='infodata/4timeCheck.txt', when='midnight', interval=1, encoding='utf-8')
        fh4.setFormatter(formatter)
        fh4.setLevel(logging.INFO)
        self.logger4 = logging.getLogger("my4")
        self.logger4.setLevel(logging.INFO)
        self.logger4.addHandler(fh4)
        self.logger4.propagate = False
        self.logger4.info("==================================start====================================")

        # # self.logger5 = 기타 잡다
        fh5 = handlers.TimedRotatingFileHandler(filename='infodata/5otherCheck.txt', when='midnight', interval=1, encoding='utf-8')
        fh5.setFormatter(formatter)
        fh5.setLevel(logging.INFO)
        self.logger5 = logging.getLogger("my5")
        self.logger5.setLevel(logging.INFO)
        self.logger5.addHandler(fh5)
        self.logger5.propagate = False
        self.logger5.info("==================================start====================================")

        self.disponly = ["", "", "", "", "", "", "", "", "", "", ""]
        timer1 = QTimer(self)
        timer1.start(1000)
        timer1.timeout.connect(self.disp)

    def __del__(self):
        try:
            self.timer.cancel()
        except:
            pass

    def disp(self):
        self.dataDisplay(self.disponly, 0)

    def _login(self):
        if 'COIN' in self._url:
            self.driver.get("https://55qwe.com")
            self._login_55qwe()
        elif '007' in self._url:
            self.driver.get("http://vvip8888.com")
            self._login_vvip()
        elif 'THEON' in self._url:
            self.driver.get("http://www.vkvk11.com")
            self._login_vkvk()

    def _idchk(self):
        WebDriverWait(self.driver, self._default_timeout).until(WaitReadyState())
        WebDriverWait(self.driver, self._default_timeout).until(
            ec.element_to_be_clickable((By.CSS_SELECTOR, self._site_conf["site_id_selector"]))
        )

        id_input = self.driver.find_element_by_css_selector(self._site_conf["site_id_selector"])
        id_input.send_keys(self._id)
        time.sleep(random.uniform(0.5, 1.0))
        pwd_input = self.driver.find_element_by_css_selector(self._site_conf["site_pwd_selector"])
        pwd_input.send_keys(self._pw)
        time.sleep(random.uniform(0.5, 1.0))
        pwd_input.send_keys(Keys.ENTER)

        WebDriverWait(self.driver, self._default_timeout).until(WaitReadyState())

    def _page_pass(self):

        # ##################### 창닫기 - 오늘 하루 클릭했을 때 그냥 닫히는 창
        # try:
        #     t1 = self.driver.find_elements_by_tag_name('input')
        #     for i in t1:
        #         i.click()
        # except:
        #     print(i)
        #     pass
        # time.sleep(random.uniform(0.5, 1.0))

        # self.driver.find_element_by_css_selector('#sagame').click()     # 단일요소 셀렉터

        # 멀티요소 셀렉터
        if 'COIN' in self._url:
            self.driver.find_elements_by_css_selector('.snip1554')[2].click()
        elif '007' in self._url:
            self.driver.find_elements_by_css_selector('.btn.gamestart')[5].find_element_by_css_selector("i").click()
        elif 'THEON' in self._url:
            self.driver.find_elements_by_css_selector('.card_org')[1].click()

        window_handle = self.driver.window_handles.copy()
        time.sleep(random.uniform(1.0, 2.0))
        WebDriverWait(self.driver, self._default_timeout).until(ec.new_window_is_opened(window_handle))

        self.driver.close()
        self.driver.switch_to.window(self.driver.window_handles[-1])

    def _login_55qwe(self):
        # SITE_ID = 881zhwoddl
        # SITE_PWD = rk660024
        self._idchk()

        if self.driver.find_elements_by_css_selector("#main_pop_notice_new11"):
            try:
                self.driver.find_element_by_xpath(u'//input[@name="nomore"]').click()
            except:
                pass
        time.sleep(random.uniform(0.5, 1.0))

        self._page_pass()

    def _login_vvip(self):
        # SITE_ID = aaaa5588
        # SITE_PWD = Qydrkdy7823

        self._idchk()

        # ##################### 창닫기 - X 버튼 눌러야 없어지는 창.
        try:
            t = self.driver.find_elements_by_css_selector("#warning2021-close")
            for i in t:
                i.click()
        except:
            print(i)
            pass
        time.sleep(random.uniform(0.5, 1.0))

        self._page_pass()

    def _login_vkvk(self):
        # SITE_ID = skflskfl
        # SITE_PWD = Qjrrkdy2589

        WebDriverWait(self.driver, self._default_timeout).until(WaitReadyState())

        # ##################### 창닫기 - 오늘 하루 클릭했을 때 그냥 닫히는 창
        # try:
        #     t1 = self.driver.find_elements_by_tag_name('input')
        #     for i in t1:
        #         i.click()
        # except:
        #     print(i)
        #     pass
        # time.sleep(random.uniform(0.5, 1.0))
        time.sleep(random.uniform(0.5, 1.0))
        self.driver.execute_script("document.getElementsByName('fp')[0].setAttribute('type','text')")
        time.sleep(random.uniform(0.5, 1.0))
        self.driver.execute_script("document.getElementsByName('fp')[1].setAttribute('type','text')")
        time.sleep(random.uniform(0.5, 1.0))

        WebDriverWait(self.driver, self._default_timeout).until(
            ec.element_to_be_clickable((By.LINK_TEXT, 'LOGIN'))
        )

        id_input = self.driver.find_elements_by_css_selector(self._site_conf["site_id_selector"])
        id_input[1].send_keys(self._id)
        time.sleep(random.uniform(0.5, 1.0))
        pwd_input = self.driver.find_elements_by_css_selector(self._site_conf["site_pwd_selector"])
        pwd_input[1].send_keys(self._pw)
        # pwd_input.send_keys(Keys.ENTER)
        time.sleep(random.uniform(0.5, 1.0))

        try:
            self.driver.find_element_by_css_selector("input.close1").click()
            # self.driver.find_element_by_css_selector("input.close2").click()
        except:
            pass

        self.driver.find_element_by_link_text('LOGIN').click()

        WebDriverWait(self.driver, self._default_timeout).until(WaitReadyState())

        self._page_pass()

    def _wait_sa_load(self):
        WebDriverWait(self.driver, self._default_timeout).until(WaitSaGameLoad())
        time.sleep(self._default_delay)

    def _switch_multi_bet(self):
        WebDriverWait(self.driver, self._default_timeout).until(WaitBetHost())
        self.driver.execute_script("GameLayerManager.Instance.showMultiBet()")
        time.sleep(self._default_delay)
        self.driver.execute_script(
            "GameLayerManager.Instance.sceneLayer.$children[0]."
            "ChangePanel({currentTarget: GameLayerManager.Instance.sceneLayer.$children[0].tabList.getChildAt(1)})"
        )

    def _wait_multi_bet(self):
        WebDriverWait(self.driver, self._default_timeout).until(WaitMultiBetTable(self._service_conf["table_min_size"]))
        time.sleep(self._default_delay)

    def bet(self, table: int, money: int, position: int):
        pass

    def set_chip_group(self, coin_index_list: tuple):
        if len(coin_index_list) != 5:
            raise Exception("꼭 5개의 칩을 선택해주세요.")
        self.driver.execute_async_script(
            """var done = arguments[0];
            (async () => {
            var i = new ChipSettingPanel(GameLayerManager.Instance.sceneLayer.$children[0]);
            var n = ChipSettingPanel.getNumOfRow(user.customeChips(GameType.BACCARAT).length, 5);
            var s = 144 + 60 * (n - 1) + 76;
            i.setPanelHeight(s);
            i.scene = "multibacc";
            GameLayerManager.Instance.upperLayer.addChild(i);
            await new Promise(resolve => setTimeout(resolve, 500));
            for (let chip of GameLayerManager.Instance.upperLayer.$children[0].$children[3].$children[0].$children[2].$children[0].$children) {
                if (chip.selected) {
                    GameLayerManager.Instance.upperLayer.$children[0].selectChip({currentTarget: chip})
                }
            }

            GameLayerManager.Instance.upperLayer.$children[0].selectChip({currentTarget: GameLayerManager.Instance.upperLayer.$children[0].$children[3].$children[0].$children[2].$children[0].$children[%s]});
            GameLayerManager.Instance.upperLayer.$children[0].selectChip({currentTarget: GameLayerManager.Instance.upperLayer.$children[0].$children[3].$children[0].$children[2].$children[0].$children[%s]});
            GameLayerManager.Instance.upperLayer.$children[0].selectChip({currentTarget: GameLayerManager.Instance.upperLayer.$children[0].$children[3].$children[0].$children[2].$children[0].$children[%s]});
            GameLayerManager.Instance.upperLayer.$children[0].selectChip({currentTarget: GameLayerManager.Instance.upperLayer.$children[0].$children[3].$children[0].$children[2].$children[0].$children[%s]});
            GameLayerManager.Instance.upperLayer.$children[0].selectChip({currentTarget: GameLayerManager.Instance.upperLayer.$children[0].$children[3].$children[0].$children[2].$children[0].$children[%s]});

            await new Promise(resolve => setTimeout(resolve, 500));
            GameLayerManager.Instance.upperLayer.$children[0].doSetChip()
            await new Promise(resolve => setTimeout(resolve, 500));
            done()
            })();""" % coin_index_list)

    def set_chip(self, index: int):
        self.driver.execute_script("""(() => {
        GameLayerManager.Instance.sceneLayer.$children[0].selectedChip = GameLayerManager.Instance.sceneLayer.$children[0].chipList.$children[%s]
        GameLayerManager.Instance.sceneLayer.$children[0].chipList.$children.forEach(x => x.isSelected(false))
        SceneGame.curChipIdx = 0
        GameLayerManager.Instance.sceneLayer.$children[0].selectedChip.isSelected(true)
        GlobalData.currentChips = GameLayerManager.Instance.sceneLayer.$children[0].currentChipArray[Number(GameLayerManager.Instance.sceneLayer.$children[0].selectedChip.data)]
        })();""" % index)

    def change_limit(self, index: int):
        self.driver.execute_script("""(() => {
        GameLayerManager.Instance.sceneLayer.$children[0].selectedChip = GameLayerManager.Instance.sceneLayer.$children[0].chipList.$children[%s]
        GameLayerManager.Instance.sceneLayer.$children[0].chipList.$children.forEach(x => x.isSelected(false))
        SceneGame.curChipIdx = 0
        GameLayerManager.Instance.sceneLayer.$children[0].selectedChip.isSelected(true)
        GlobalData.currentChips = GameLayerManager.Instance.sceneLayer.$children[0].currentChipArray[Number(GameLayerManager.Instance.sceneLayer.$children[0].selectedChip.data)]
        })();""" % index)

    def set_money(self, table: int, position: int):
        self.driver.execute_script("""GameLayerManager.Instance.sceneLayer.$children[0].tableList.$children[%s].doBet(
        {currentTarget: 
        GameLayerManager.Instance.sceneLayer.$children[0].tableList.$children[%s].$children[10].$children[15].$children[%s]
        })""" % (table, table, position))

    def betting(self, table: int, position: str, money: int, game: str, ctmoney: int):
        start1 = timeit.default_timer()
        start = timeit.default_timer()
        num = [0.05, 0.1] if self.delaycnt >= 2 else [0.04, 0.07] if self.delaycnt >= 4 else [0.05, 0.15]
        """
        베팅 함수
        :param table: 테이블 번호 ex) 831, 832
        :param position: P: 플레이어, T: 타이, B: 뱅커, PP: 플레이어페어, BP: 뱅커페어, L: 럭키식스
        :param money: 금액
        :param game: 리얼, 시뮬
        :return: 성공시 True 실패시 False or Exception
        """
        table_index = self.driver.execute_script(
            f"return GameLayerManager.Instance.sceneLayer.$children[0].tableList.$children.findIndex(x => x._host._hostID == {table})")
        if table_index < 0:
            raise Exception("테이블을 찾을 수 없습니다.")

        time.sleep(random.uniform(num[0], num[1]))
        self.logger4.info(f"-- check1 : [%.1f초 table : {table}" % (timeit.default_timer() - start))
        start = timeit.default_timer()
        self.logger2.info(f"배팅 테이블 번호: {table_index + 1}")

        if table_index < 12:
            self.driver.execute_script("scrollBy(0,-600);")
        else:
            self.driver.execute_script("window.scrollTo(0,document.body.scrollHeight)")

        time.sleep(random.uniform(num[0], num[1]))
        self.logger4.info("-- check2 : [%.1f초" % (timeit.default_timer() - start))
        start = timeit.default_timer()

        re = True
        ovnum = 7
        if self.nobetcnt:  # 배팅 안되는 카운트 설정
            w, c = [i for i, v in enumerate(self.nobetcnt) if table == v['ta']], \
                   [v['cnt'] for i, v in enumerate(self.nobetcnt) if table == v['ta']]
            where, cnt = w[0] if w else 0, c[0] if c else 0

            self.logger5.info(f'[{table}, {cnt}, {where} : table, cnt, where')
            if ovnum < cnt:  # 7번 배팅 실패하면 12초 지나면 테이블 다시 체크
                if self.overcnt:
                    w1 = [k for k, w in enumerate(self.overcnt) if table == w['ta']]
                    where1 = w1[0] if w1 else -1
                    if where1 == -1:
                        self.logger2.info("현재 배팅 불가 테이블입니다. 12 초 간격 추가-1")
                        self.logger5.info(f"[{table} 현재 배팅 불가 테이블입니다. 12 초 간격 추가-1 ")
                        self.overcnt.append({'ta': table, 'time': datetime.datetime.now()})
                        re = False
                    else:
                        # 12초 지나서 체크
                        if self.overcnt[where1]['time'] + datetime.timedelta(seconds=12) < datetime.datetime.now():
                            tablebet = self.driver.execute_script(
                                f"return GameLayerManager.Instance.sceneLayer.$children[0].tableList.$children[{table_index}].$children[10].$children[15].$children[0].$touchEnabled"
                            )
                            time.sleep(random.uniform(num[0], num[1]))
                            if tablebet:
                                if not self.check_available_bet(table_index):  # 여전히 배팅불가면 시간 다시 넣음
                                    self.logger2.info("현재 배팅 불가 테이블입니다. 12 초 간격 추가2")
                                    self.logger5.info(f"[{table} 현재 배팅 불가 테이블입니다. 12 초 간격 추가2")
                                    self.overcnt[where1]['time'] = datetime.datetime.now()
                                    re = False
                                else:  # 배팅 성공이면 지움
                                    self.logger2.info(f"배팅 가능 테이블로 변경")
                                    self.logger5.info(f"[{table} 배팅 가능 테이블로 변경")
                                    del self.overcnt[where1]
                                    del self.nobetcnt[where]
                            else:
                                return False
                        else:
                            self.logger2.info("현재 배팅 불가 테이블입니다. 12 초 안됨")
                            self.logger5.info(f"[{table} 현재 배팅 불가 테이블입니다. 12 초 안됨")
                            re = False
                else:
                    self.logger2.info("현재 배팅 불가 테이블입니다. 12 초 간격 추가1")
                    self.logger5.info(f"[{table} 현재 배팅 불가 테이블입니다. 12 초 간격 추가1")
                    self.overcnt.append({'ta': table, 'time': datetime.datetime.now()})
                    re = False

            else:  # 10번 아래일때
                if not self.check_available_bet(table_index):  # 배팅 실패하면 하나씩 추가
                    if cnt == 0:
                        self.logger2.info(f"현재 배팅 불가 테이블입니다. 처음")
                        self.logger5.info(f"[{table} 현재 배팅 불가 테이블입니다. 처음")
                        self.nobetcnt.append({'ta': table, 'cnt': 1})
                    else:
                        self.nobetcnt[where]['cnt'] = cnt + 1
                        self.logger2.info(f"현재 배팅 불가 테이블입니다. cnt : {cnt}")
                        self.logger5.info(f"[{table} 현재 배팅 불가 테이블입니다. cnt : {cnt}")
                    re = False
                else:  # 배팅 성공하면 삭제
                    if cnt != 0:
                        del self.nobetcnt[where]
                        self.logger2.info(f"배팅 가능 테이블로 변경")
                        self.logger5.info(f"[{table} 배팅 가능 테이블로 변경")
        else:  # 값이 없을 때 배팅 실패하면 추가
            cnt = 1
            if not self.check_available_bet(table_index):
                self.logger2.info(f"현재 배팅 불가 테이블입니다. 처음")
                self.logger5.info(f"[{table} 현재 배팅 불가 테이블입니다. 처음 값이 아예 없음")
                self.nobetcnt.append({'ta': table, 'cnt': cnt})
                re = False

        # print(f'배팅가능여부 : {tablebet}')

        time.sleep(random.uniform(num[0], num[1]))
        self.logger4.info(f"-- check3 : [%.1f초, cntover : {cnt}" % (timeit.default_timer() - start)) if ovnum < cnt \
            else self.logger4.info("-- check3 : [%.1f초" % (timeit.default_timer() - start))
        if not re: return re
        start = timeit.default_timer()
        if self.check_already_bet(table_index):
            self.logger2.info("이미 배팅한 테이블입니다.")
            return False

        time.sleep(random.uniform(num[0], num[1]))
        self.logger4.info("-- check4 : [%.1f초" % (timeit.default_timer() - start))
        start = timeit.default_timer()
        position_dict = {"P": 0, "T": 1, "B": 2, "PP": 3, "BP": 4, "L": 5}

        if position_dict.get(position, None) is None:
            raise Exception("알 수 없는 포지션입니다.")

        position_index = position_dict[position]

        self.logger2.info(f"배팅 포지션 번호: {position_index + 1}")

        coins = [1000, 5000, 10000, 100000, 1000000]

        result = {x: 0 for x in coins}
        value = money

        for coin in reversed(coins):
            coin_count = value // coin
            value -= coin * coin_count
            if value == 100:
                value += coin
                coin_count -= 1
            result[coin] = coin_count

        if value != 0:
            raise Exception("배팅 할 수 없는 금액입니다.")

        result = {k: v for k, v in result.items() if v != 0}

        coin_groups = [list(result.keys())[i:i + 5] for i in range(0, len(result.keys()), 5)]
        self.logger4.info("-- check5 : [%.1f초" % (timeit.default_timer() - start))
        start = timeit.default_timer()

        for coin_group in coin_groups:
            for coin in coins:
                if coin not in coin_group:
                    if len(coin_group) != 5:
                        coin_group.append(coin)
                    else:
                        break
            coin_group = sorted(coin_group)

            # self.set_chip_group(tuple((coins.index(x) for x in coin_group if x in coins)))
            for index, coin in enumerate(coin_group):
                if result.get(coin, False):
                    self.set_chip(index)
                    for _ in range(result[coin]):
                        self.set_money(table_index, position_index)

        time.sleep(random.uniform(num[0], num[1]))
        self.logger4.info("-- check6 : [%.1f초" % (timeit.default_timer() - start))
        start = timeit.default_timer()
        data = self.driver.execute_script(
            "try { "
            "GameLayerManager.Instance.upperLayer.$children.filter(x => x.hasOwnProperty('btnConfirm'))[0];"
            "return true "
            "} catch(e) { return false }")
        m = [0.2, 0.4] if self.delaycnt >= 2 else [0.1, 0.3] if self.delaycnt >= 4 else [0.3, 0.5]
        time.sleep(random.uniform(m[0], m[1]))
        self.logger4.info("-- check7 : [%.1f초" % (timeit.default_timer() - start))
        start = timeit.default_timer()
        self.delaycnt += 1
        if data:
            if game == 'r' and ctmoney == 0:
                self.logger2.info(f'att ctmomney : {ctmoney}')
                re = self.driver.execute_script(
                    "try { "
                    "GameLayerManager.Instance.upperLayer.$children.filter(x => x.hasOwnProperty('btnConfirm'))[0]._parent.doConfirmBet(); "
                    "GameLayerManager.Instance.upperLayer.$children.filter(x => x.hasOwnProperty('btnConfirm'))[0].doClose();"
                    "return true "
                    "} catch(e) { return false }")
                self.logger4.info("-- check8-1 : [%.1f초" % (timeit.default_timer() - start))
                self.logger4.info(f"-- checkTotal : [%.1f초 delaycnt : {self.delaycnt}" % (timeit.default_timer() - start1))
                return re
            else:
                self.logger2.info(f'dont att game : {game}')
                self.logger2.info(f'dont att ctmomney : {ctmoney}')
                # self.driver.find_element_by_xpath("//body").send_keys(Keys.ESCAPE)
                re = self.driver.execute_script(
                    "try { "
                    "GameLayerManager.Instance.upperLayer.$children.filter(x => x.hasOwnProperty('btnConfirm'))[0].doClose();"
                    "return true "
                    "} catch(e) { return false }")
                self.logger4.info("-- check8-2 : [%.1f초" % (timeit.default_timer() - start))
                self.logger4.info(f"-- checkTotal : [%.1f초 delaycnt : {self.delaycnt}" % (timeit.default_timer() - start1))
                return re
        return data

    def check_available_bet(self, table: int):
        try:
            cTime = int(self.driver.execute_script(
                f"return GameLayerManager.Instance.sceneLayer.$children[0].tableList.$children[{table}].lblStatus.textLabel.text"))
            if cTime < 2:
                self.logger2.info("남은 배팅 시간이 너무 짧습니다.")
                return False
        except Exception:
            return False
        else:
            return True

    def check_already_bet(self, table: int):
        bet_count = self.driver.execute_script(f"return window.user._hosts[{table}].bets.length")
        return True if bet_count != 0 else False

    def find_ddata(self, data, no):
        delnum = []
        for i, v in enumerate(data):
            if v['no'] == no:
                delnum.append(i)
                self.ctrlCnt -= 1
        return reversed(delnum)

    def del_data(self, algo, no):
        if self.attack:
            if algo == "NG" and self.ctrlNG:
                for k in self.find_ddata(self.ctrlNG, no): del self.ctrlNG[k]
            elif algo == "OG" and self.ctrlOG:
                for k in self.find_ddata(self.ctrlOG, no): del self.ctrlOG[k]
            elif algo == "BG" and self.ctrlBG:
                for k in self.find_ddata(self.ctrlBG, no): del self.ctrlBG[k]
            elif algo == "BB" and self.ctrlBB:
                for k in self.find_ddata(self.ctrlBB, no): del self.ctrlBB[k]
            elif algo == "YJ" and self.ctrlYJ:
                for k in self.find_ddata(self.ctrlYJ, no): del self.ctrlYJ[k]
            elif algo == "YK" and self.ctrlYK:
                for k in self.find_ddata(self.ctrlYK, no): del self.ctrlYK[k]

            self.logger1.info(f'cancel attack no : {no}')
            if not self.ctrlNG and not self.ctrlOG and not self.ctrlBG and not self.ctrlBB and \
                    not self.ctrlYJ and not self.ctrlYK:
                self.attack = False

    def from_dbdata(self):
        id = self._id2
        with self.conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(f"SELECT * FROM sub10 WHERE start = 't' AND id = '{id}'")
            result = cursor.fetchall()
            cursor.execute(f"SELECT * FROM sub10 WHERE start = 'f' AND id = '{id}'")
            result1 = cursor.fetchall()

        if result:
            self.logger1.info(f'from_dbdata result')
            for i in result:
                # print(data)
                noData = True
                for z in self.from_db:
                    if z['no'] == i['no']:
                        noData = False
                if noData:
                    print(f'start : {i}')
                    i['readtable'] = 't'
                    self.cosFirst = True
                    # cursor.execute(f"UPDATE sub10 SET readtable = 't' WHERE no = '{str(i['no'])}'")
                    self.from_db.append(i)
                    self.logger1.info(f'from_db : {self.from_db}')
                    with self.conn.cursor(pymysql.cursors.DictCursor) as cursor1:
                        cursor1.execute("SELECT ta FROM sub01save use index (idx_date) "
                                        "WHERE date BETWEEN DATE_ADD(now(), INTERVAL -60 minute) AND now() GROUP BY ta")
                        table_no_org = cursor1.fetchall()
                    table = {}
                    for k, v in enumerate(i['tableno']):
                        if i['tableno'][k] == 't':
                            try:
                                n = k+1
                                table[str(n)] = table_no_org[k]['ta']
                                table[str(n) + 'date'] = 'f'
                                table[str(n) + 'tf'] = 'f'
                                table[str(n) + 'beBP'] = 'f'
                                table[str(n) + 'chBP'] = 'f'
                                self.table_noCnt += 1
                            except:
                                pass
                    self.table_no.append(table)
                    self.logger1.info(f'table_no : {self.table_no}')
                    self.ctrldata = True

        if result1:
            self.logger1.info(f'from_dbdata result1')
            for i in result1:
                inData = False
                for z in self.from_db:
                    if z['no'] == i['no']:
                        inData = True
                if inData:
                    delnum = i['no']
                    # data = f"UPDATE sub10 SET start = 'f' WHERE no = '{str(delnum)}'"
                    print(f'스톱 : {i["no"]}')
                    # with self.conn.cursor(pymysql.cursors.DictCursor) as cursor1:
                    #     cursor1.execute(data)
                    # self.conn.commit()
                    # num = 0
                    index = [j for j, v in enumerate(self.from_db) if int(delnum) == self.from_db[j]['no']][0]
                    self.logger1.info(f'remove data : {delnum}')
                    self.del_data(self.from_db[index]['sub1001'], self.from_db[index]['no'])
                    del self.from_db[index]
                    ta = self.table_no[index]
                    for n, val3 in enumerate(ta):
                        if n % 5 == 0:
                            self.table_noCnt -= 1
                    del self.table_no[index]
                    self.logger1.info(f'남은 from_db : {self.from_db}')

        self.conn.commit()
        # if not result and not result1:
        #     print("result 음슴")

    def chktable(self):
        self.logger1.info(f'{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}, {str(self.table_no)}')
        # print(self.from_db)

    def checkover_step(self):
        self.logger1.info('checkover_step')
        with self.conn.cursor(pymysql.cursors.DictCursor) as cursor2:
            if self.cosFirst:
                cursor2.execute(self.cossql)
                self.cosFirst = False
            else:
                cursor2.execute(self.cossql1)
            result2 = cursor2.fetchall()
            self.logger2.info(result2)
        for i, val in enumerate(self.from_db):
            pass1 = True
            ta = self.table_no[i]
            for n, val3 in enumerate(ta):
                if n % 5 == 0:
                    tname = ta[str(val3)]
                    d = val3 + 'tf'
                    ttf = ta[d]
                elif n % 5 == 2 and ttf != 'f' and ttf != 't':
                    aftertime = 0 if val['sub1004'] == '' else int(val['sub1004'])
                    tpass = False
                    # 시간 비교함수 활용
                    if val['sub1003'] == 'c' and datetime.datetime.strptime(ttf, "%Y-%m-%d %H:%M:%S") + \
                            datetime.timedelta(minutes=aftertime) < datetime.datetime.now():
                        tpass = True
                        ctmoney = 0
                    elif val['sub1003'] == 's':
                        tpass = True
                        ctmoney = int(aftertime) * 1000
                    if tpass:
                        print(f'--timepass {tname}')
                        self.table_no[i][val3] = 't'
                        p, b = val['sub1015'], val['sub1016']
                        if p and b:
                            bp = p + b
                        elif p:
                            bp = p
                        elif b:
                            bp = b
                        # 1,7,8,9,10,11,12, amoset
                        ctrl = {"no": val["no"], "ta": tname, "readTime1": "", "readTime2": "", "attack": "f",
                                "attNo": 0, "attTime": "", "attBP": "", "TieTime": "",
                                "acstart": "f", "beBP": "", "autoctl": "f", "cruse": "f", "ng1": "f",
                                "sncnt": 0, "rccnt": 0, "step": 0,
                                "amoset": 0, "attmoney": 0, "resultmoney": 0,
                                "ctmoney": ctmoney, "cresultmoney": 0, "cttopP": 0, "cttopN": 0,
                                "wincnt": 0, "losecnt": 0, "totcnt": 0, "lastwl": "", "bp": bp,
                                "sub1001": val["sub1001"], "sub1007": val["sub1007"], "sub1008": val["sub1008"],
                                "sub1009": val["sub1009"], "sub1010": val["sub1010"], "sub1011": val["sub1011"],
                                "sub1012": val["sub1012"], "sub1014": val["sub1014"], "sub1017": val["sub1017"],
                                "sub1018": val["sub1018"], "sub1019": val["sub1019"], "amosetorg": val["amoset"]
                                }
                        self.logger1.info(f'add ctrl : {ctrl}')
                        self.ctrlCnt += 1
                        if val['sub1001'] == "NG":
                            self.ctrlNG.append(ctrl)
                        elif val['sub1001'] == "OG":
                            self.ctrlOG.append(ctrl)
                        elif val['sub1001'] == "BG":
                            self.ctrlBG.append(ctrl)
                        elif val['sub1001'] == "BB":
                            self.ctrlBB.append(ctrl)
                        elif val['sub1001'] == "YJ":
                            self.ctrlYJ.append(ctrl)
                        elif val['sub1001'] == "YK":
                            self.ctrlYK.append(ctrl)
                        self.attack = True
                        # print(self.table_no)

                if n % 5 == 2 and ttf == 'f':
                    pass1 = False

            if pass1: continue
            if result2:
                for k in result2:
                    for n, val3 in enumerate(ta):
                        if ta[str(val3)] == k["ta"]:
                            a, b = val3 + 'date', val3 + 'beBP'
                            if self.table_no[i][a] == 'f':
                                self.table_no[i][a] = k['date']
                                self.table_no[i][b] = k['bp']
                                self.logger1.info(f'add table info : {self.table_no[i]}')
                                # datetime.datetime.strptime(self.table_no[i][a], "%Y-%m-%d %H:%M:%S")
                            elif self.table_no[i][a] < k['date']:
                                c = val3 + 'chBP'
                                if self.table_no[i][c] == 'f':
                                    if self.table_no[i][b] != k["bp"]:
                                        self.table_no[i][a] = k['date']
                                        self.table_no[i][c] = 't'
                                        info = f'--changebp pass table {k["ta"]}'
                                        print(info)
                                        self.logger1.info(info)
                                        self.logger1.info(self.table_no[i])

                                        if int(val["sub1002"]) <= 0:
                                            d = val3 + 'tf'
                                            self.table_no[i][d] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                            info2 = f'--step pass {k["ta"]}'
                                            print(info2)
                                            self.logger1.info(info2)
                                            self.logger1.info(self.table_no[i])

                                else:
                                    if int(k["step"]) >= int(val["sub1002"]):
                                        # print(f'넘어간 번호 : {val3}')
                                        d = val3 + 'tf'
                                        # print(f'수정 번호 : {a}')
                                        if self.table_no[i][d] == 'f':
                                            self.table_no[i][d] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                            self.logger1.info(f'stepDB {result2}')
                                            info2 = f'--step pass {k["ta"]}'
                                            print(info2)
                                            self.logger1.info(info2)
                                            self.logger1.info(self.table_no[i])
        self.conn.commit()

    def attinfo2(self, ctrlData, result, bp, step):
        if bp == 'P':
            ctrlData['readTime1'] = result['date']
        else:
            ctrlData['readTime2'] = result['date']
        if datetime.datetime.now() < datetime.datetime.strptime(ctrlData['sub1018'], "%Y-%m-%d %H:%M") \
                and float(ctrlData['resultmoney']) < float(ctrlData['sub1014'] * 1000) \
                and self.change < int(ctrlData['sub1019']) * 1000:
            self.logger3.info(f'attack bp : {bp}')
            if ctrlData['sub1001'] == "NG" and result['beBP'] != result['bp'] and bp == result['bp'] and ctrlData['ng1'] == 't' \
                    or ctrlData['sub1001'] == "OG" and result['beBP'] != result['bp'] and bp != result['bp'] and ctrlData['ng1'] == 't' \
                    or ctrlData['sub1001'] == "NG" and result['beBP'] == result['bp'] and bp == result['bp'] \
                    or ctrlData['sub1001'] == "OG" and result['beBP'] == result['bp'] and bp != result['bp'] \
                    or ctrlData['sub1001'] == "BG" and bp == result['bp'] \
                    or ctrlData['sub1001'] == "BB" and bp != result['bp'] \
                    or ctrlData['sub1001'] == "YJ" and bp != result['bp'] \
                    or ctrlData['sub1001'] == "YK" and bp == result['bp']:
                ctrlData['attack'] = 't'
                ctrlData['attTime'] = result['date']
                ctrlData['attBP'] = bp
                ctrlData['step'] = step
                self.dispno = self.dispno + 1
                ctrlData['attno'] = self.dispno

            if ctrlData['attack'] == 't':
                mon = ctrlData['amosetorg'].split('|')
                mon2 = mon[ctrlData['amoset']].split(',')
                ctrlData['attmoney'] = int(mon2[0]) * 1000
                info = ' simul' if ctrlData['sub1017'] == 's' else ' real '
                if self.driving == '': self.driving = ctrlData['sub1017']
                actxt = ", autoControl : True" if ctrlData['autoctl'] == 't' else ""

                table = next(iter({i for a1 in self.table_no for i, y in a1.items() if y in str(ctrlData['ta'])}))
                di = [self.dispno, info, result['date'][-8:], table, ctrlData['sub1001'], step, bp, mon2[0], "", "", ""]
                self.disponly = di
                self.dispdata.append(di)
                self.dataDisplay(di, 0)

                dataz = f"#####{di[1]}attack #####, ta : {ctrlData['ta']}, Name : {di[4]}, " \
                        f"bp : {di[6]}, aTTmoney : {mon2[0]}, step : {step}{actxt}"
                print(dataz)
                self.logger2.info(dataz)
                self.logger3.info(dataz)

                self._attack(ctrlData, bp)
        else:
            print('$$$$$$$$$$$$$$$$$Game end$$$$$$$$$$$$$$$$$$$$$$$')
            if datetime.datetime.now() > datetime.datetime.strptime(ctrlData['sub1018'], "%Y-%m-%d %H:%M"):
                self.logger3.info(f'now : {datetime.datetime.now()}')
                self.logger3.info(datetime.datetime.strptime(ctrlData['sub1018'], "%Y-%m-%d %H:%M"))
            elif float(ctrlData['resultmoney']) >= float(ctrlData['sub1014']):
                self.logger3.info(f"resultmoney : {float(ctrlData['resultmoney'])}")
                self.logger3.info(f"setmoney : {float(ctrlData['sub1014'])}")
            elif self.change >= int(ctrlData['sub1019']):
                self.logger3.info(f"limitmoney : {float(ctrlData['sub1019'])}")
                self.logger3.info(f"totalmoney : {self.change}")

    def _attack(self, ctrlData, bp):
        data = {'ta': int(ctrlData['ta']), 'bp': ctrlData['attBP'], 'mon': int(ctrlData['attmoney']),
                'game': ctrlData['sub1017'], 'ctmoney': int(ctrlData['ctmoney'])}

        if not self.dbtablesum:
            self.dbtablesum.append(data)
            # self.delaycnt += 1
        else:
            d = [[i, data['mon']] for i, aa in enumerate(self.dbtablesum) if aa['ta'] == data['ta'] and aa['bp'] == bp]
            if d:
                self.dbtablesum[d[0][0]]['mon'] += d[0][1]
                # self.delaycnt -= 1
                print(f"####!  sum  data  !####, ta : {ctrlData['ta']}, bp : {ctrlData['attBP']}, mon : {self.dbtablesum[d[0][0]]['mon']}")
                self.logger2.info(f"####!  sum  data  !####, ta : {ctrlData['ta']}, bp : {ctrlData['attBP']}, mon : {self.dbtablesum[d[0][0]]['mon']}")
            else:
                self.dbtablesum.insert(0, data)
                # self.delaycnt += 1

    def _autoCtrl(self, result, ctrlData):
        step = int(result['step'])
        # attack 이전일때
        attmin = 0 if ctrlData['sub1007'] == '' else int(ctrlData['sub1007'])
        attmax = 1000 if ctrlData['sub1008'] == '' else int(ctrlData['sub1008'])
        attchk = 0 if ctrlData['sub1009'] == '' else int(ctrlData['sub1009'])
        ssnum = 0 if ctrlData['sub1010'] == '' else int(ctrlData['sub1010'])
        atnum = 0 if ctrlData['sub1011'] == '' else int(ctrlData['sub1011'])
        renum = 0 if ctrlData['sub1012'] == '' else int(ctrlData['sub1012'])

        if ctrlData['autoctl'] == 't':  # 오토컨트롤 일때 값 늘이기
            autonum = atnum
            attmin = attmin + autonum
            attmax = attmax + autonum

        if 0 < attchk <= step and ctrlData['autoctl'] == 'f':  # 오토컨트롤 체크
            ctrlData['sncnt'] = ctrlData['sncnt'] + 1
            if 0 < ssnum == ctrlData['sncnt']:  # 오토컨트롤 시작
                ctrlData['autoctl'] = 't'
                ctrlData['sncnt'] = 0
                self.logger3.info(f'오토 컨트롤 시작, ta : {result["ta"]}')
        elif attmax <= step and ctrlData['autoctl'] == 't':  # 리턴갯수 체크
            ctrlData['rccnt'] = ctrlData['rccnt'] + 1
            if 0 < renum == ctrlData['rccnt']:  # 오토컨트롤 종료
                ctrlData['autoctl'] = 'f'
                ctrlData['rccnt'] = 0
                self.logger3.info(f'오토 컨트롤 종료, ta : {result["ta"]}')
        return [step, attmin, attmax]

    def sqldata(self, ctrl, re, re1, reT):
        if reT:
            for ctrlData, resultT in itertools.product(ctrl, reT):
                if ctrlData['attack'] == 't' and int(ctrlData['ta']) == resultT['ta']:
                    for bp in ctrlData['bp']:
                        if ctrlData['readTime1'] != resultT['CD'] and ctrlData['TieTime'] != resultT['CD'] and bp == ctrlData['attBP'] or \
                                ctrlData['readTime2'] != resultT['CD'] and ctrlData['TieTime'] != resultT['CD'] and bp == ctrlData['attBP']:
                            print(f"!!!! Tie !!!! !!rebet!!, ta : {ctrlData['ta']}, Name : {ctrlData['sub1001']}, bp : {ctrlData['attBP']}, aTTmoney : {ctrlData['attmoney']}")
                            ctrlData['TieTime'] = resultT['CD']
                            self._attack(ctrlData, bp)

        for ctrlData, result in itertools.product(ctrl, re):
            if ctrlData['attack'] == 't' and ctrlData['ta'] == result['ta']:
                for bp in ctrlData['bp']:
                    # 공격 후 결과 값
                    if bp == 'P' and ctrlData['readTime1'] != result['date'] and ctrlData['attBP'] == bp \
                            or bp == 'B' and ctrlData['readTime2'] != result['date'] and ctrlData['attBP'] == bp:

                        mon = ctrlData['amosetorg'].split('|')
                        win, info = 't' if ctrlData['attBP'] == result['bp'] else 'f', \
                                    'win ' if ctrlData['attBP'] == result['bp'] else 'lose'
                        self.logger2.info(f'!!!! result !!!! : {info}, ta : {ctrlData["ta"]}, Name : {ctrlData["sub1001"]}, bp : {bp}, aTTmoney : {ctrlData["attmoney"]}')
                        print(f'!!!! result !!!! : {info}, ta : {ctrlData["ta"]}, Name : {ctrlData["sub1001"]}, bp : {bp}, aTTmoney : {ctrlData["attmoney"]}')
                        ctrlData['attack'] = 'f'
                        ctrlData['attTime'], ctrlData['attBP'], ctrlData['TieTime'], ctrlData['readTime1'], ctrlData['readTime2'] = '', '', '', '', ''

                        mon2 = mon[ctrlData['amoset']].split(',')
                        if mon2[1] == '': mon2[1] = 0

                        if win == 't':
                            attremoney = int(ctrlData['attmoney']) if result['bp'] == 'P' else int(ctrlData['attmoney']) * 0.95
                            ctrlData['resultmoney'] = ctrlData['resultmoney'] + attremoney

                            if ctrlData['ctmoney'] != 0:
                                ctrlData['cresultmoney'] = ctrlData['cresultmoney'] + attremoney
                                if ctrlData['cttopP'] < ctrlData['cresultmoney']: ctrlData['cttopP'] = ctrlData['cresultmoney']

                            if 0 < int(mon2[1]) and ctrlData['cruse'] == 'f':
                                ctrlData['attmoney'] = int(mon2[0]) * int(mon2[1]) * 1000
                                ctrlData['cruse'] = 't'
                            elif ctrlData['cruse'] == 't' or 0 >= int(mon2[1]):
                                ctrlData['amoset'] = int(mon2[2]) - 1
                                mon3 = mon[ctrlData['amoset']].split(',')
                                ctrlData['attmoney'] = int(mon3[0]) * 1000
                                ctrlData['cruse'] = 'f'
                            ctrlData['wincnt'] = ctrlData['wincnt'] + 1
                            ctrlData['lastwl'] = 'win'
                        else:
                            attremoney = int(ctrlData['attmoney'])
                            ctrlData['resultmoney'] = ctrlData['resultmoney'] - attremoney
                            if ctrlData['ctmoney'] != 0:
                                ctrlData['cresultmoney'] = ctrlData['cresultmoney'] - attremoney
                                if ctrlData['cttopN'] > ctrlData['cresultmoney']: ctrlData['cttopN'] = ctrlData['cresultmoney']
                            ctrlData['amoset'] = int(mon2[3]) - 1
                            mon3 = mon[ctrlData['amoset']].split(',')
                            ctrlData['attmoney'] = int(mon3[0]) * 1000
                            ctrlData['cruse'] = 'f'
                            ctrlData['losecnt'] = ctrlData['losecnt'] + 1
                            ctrlData['lastwl'] = 'lose'

                        if ctrlData['ctmoney'] > 0 >= ctrlData['ctmoney'] - ctrlData['cttopP'] + ctrlData['cttopN'] or \
                                ctrlData['ctmoney'] < 0 <= ctrlData['ctmoney'] + ctrlData['cttopP'] - ctrlData['cttopN']:
                            ctrlData['ctmoney'], ctrlData['amoset'] = 0, 0

                        self.money0 = int(self.money0) + int(attremoney) if win == 't' else int(self.money0) - int(attremoney)
                        # self.wlData.append([result['date'].strftime("%Y-%m-%d %H:%M:%S"), ctrlData['ta'], win, self.money0, attremoney, ctrlData['sub1017']])

                        ctrlData['totcnt'] = ctrlData['totcnt'] + 1
                        if ctrlData['sub1017'] == 's':
                            pinfo = f'--{datetime.datetime.now().strftime("%H:%M:%S")}, 시뮬 전체 잔액 : {self.money0}, 테이블 잔액 : {ctrlData["resultmoney"]}, ta : {ctrlData["ta"]}'
                            total = self.money0 / 1000
                        else:
                            change = self.driver.execute_script(
                                "return GameLayerManager.Instance.sceneLayer.$children[0].lobbyFooter.lblBalance.text")
                            # with self.conn.cursor(pymysql.cursors.DictCursor) as cursor:
                            #     cursor.execute(self.insertquery % (self._id2, result['date'], ctrlData['ta'], self._id2, self._id, win, self.money0, attremoney, ctrlData['sub1017']))
                            # self.conn.commit()
                            # time.sleep(random.uniform(0.05, 0.1))
                            pinfo = f'--{datetime.datetime.now().strftime("%H:%M:%S")}, 리얼 전체 잔액 : {change},  테이블 잔액 : {ctrlData["resultmoney"]}, ta : {ctrlData["ta"]}'
                            total = change / 1000
                        print(pinfo)
                        self.logger2.info(pinfo)
                        i = [k for k, v in enumerate(self.dispdata) if v[0] == ctrlData['attno']][0]
                        self.dispdata[i][8] = info
                        self.dispdata[i][9] = str(ctrlData['attmoney'] / 1000)
                        self.dispdata[i][10] = str(total)
                        self.disponly = self.dispdata[i]
                        self.dataDisplay(self.disponly, 1)
                        # self.delaycnt += 0.25

            # re는 ng와 og만 attack check.
            if ctrlData['attack'] == 'f' and ctrlData['ta'] == result['ta'] and ctrlData['sub1001'] == "NG" \
                    or ctrlData['attack'] == 'f' and ctrlData['ta'] == result['ta'] and ctrlData['sub1001'] == "OG":

                reData = self._autoCtrl(result, ctrlData)
                step = reData[0] + 1
                attmin, attmax = reData[1], reData[2]

                # attack check
                for bp in ctrlData['bp']:
                    if attmin <= 1 and ctrlData['attack'] == 'f' and result['bp'] != result['beBP']:  # 1단계 어택하기
                        if bp == 'P' and ctrlData['readTime1'] != result['date'] or \
                                bp == 'B' and ctrlData['readTime2'] != result['date']:
                            ctrlData['ng1'] = 't'
                            self.logger3.info(f'resultDataNG1 = {result}')
                            self.logger3.info(f'ctrlDataNG1 = {ctrlData}')
                            self.attinfo2(ctrlData, result, bp, 1)
                    elif attmin <= step <= attmax and ctrlData['attack'] == 'f':  # 나머지 단계어택하기
                        if bp == 'P' and ctrlData['readTime1'] != result['date'] or \
                                bp == 'B' and ctrlData['readTime2'] != result['date']:
                            self.logger3.info(f'resultDataNG2 = {result}')
                            self.logger3.info(f'ctrlDataNG2 = {ctrlData}')
                            self.attinfo2(ctrlData, result, bp, step)

        for ctrlData, result in itertools.product(ctrl, re1):  # re1의 attack f 모아서 확인
            if ctrlData['attack'] == 'f' and ctrlData['ta'] == result['ta'] and ctrlData['sub1001'] == "BG" \
                    or ctrlData['attack'] == 'f' and ctrlData['ta'] == result['ta'] and ctrlData['sub1001'] == "BB" \
                    or ctrlData['attack'] == 'f' and ctrlData['ta'] == result['ta'] and ctrlData['sub1001'] == "YJ" \
                    or ctrlData['attack'] == 'f' and ctrlData['ta'] == result['ta'] and ctrlData['sub1001'] == "YK":
                reData = self._autoCtrl(result, ctrlData)
                step = reData[0]
                attmin, attmax = reData[1], reData[2]

                # attack check
                for bp in ctrlData['bp']:
                    if attmin <= step <= attmax and ctrlData['attack'] == 'f':  # 어택하기
                        if bp == 'P' and ctrlData['readTime1'] != result['date'] or \
                                bp == 'B' and ctrlData['readTime2'] != result['date']:
                            self.logger3.info(f'resultDataOt = {result}')
                            self.logger3.info(f'ctrlDataOt = {ctrlData}')
                            self.attinfo2(ctrlData, result, bp, step)

    def attackData(self):
        with self.conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(self.attDatasql)
            re = cursor.fetchall()
            re1, re2 = '', ''
            if self.ctrlBG or self.ctrlBB:
                cursor.execute(self.sqldatasql.format('BG'))
                re1 = cursor.fetchall()
            if self.ctrlYJ or self.ctrlYK:
                cursor.execute(self.sqldatasql.format('YJ'))
                re2 = cursor.fetchall()
            cursor.execute(self.sqlT)
            sqlT = cursor.fetchall()
        self.conn.commit()
        if re or sqlT:
            if self.ctrlNG:
                self.sqldata(self.ctrlNG, re, "", sqlT)
            if self.ctrlOG:
                self.sqldata(self.ctrlOG, re, "", sqlT)
            if re1 or sqlT:
                if self.ctrlBG:
                    self.sqldata(self.ctrlBG, re, re1, sqlT)
                if self.ctrlBB:
                    self.sqldata(self.ctrlBB, re, re1, sqlT)
            if re2 or sqlT:
                if self.ctrlYJ:
                    self.sqldata(self.ctrlYJ, re, re2, sqlT)
                if self.ctrlYK:
                    self.sqldata(self.ctrlYK, re, re2, sqlT)
            with self.conn.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute(self.attSaveData %
                               (self.ctrlNG, self.ctrlOG, self.ctrlBG, self.ctrlBB, self.ctrlYJ, self.ctrlYK,
                                self._id2, self.driving))
            self.conn.commit()

    # 화면 띄우기
    def dataDisplay(self, data, cnt):

        self.csHistory.setRowCount(1)
        rowPosition = self.csHistory.rowCount()

        for i in range(0, 11):
            item = QTableWidgetItem(str(data[i]))
            item.setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)
            if rowPosition % 2 == 1:
                item.setBackground(QtGui.QColor(250, 250, 250))

            self.csHistory.setItem(0, i, item)

        self.csHistory.resizeColumnToContents(0)
        self.csHistory.resizeRowsToContents()
        self.csHistory.setEditTriggers(QAbstractItemView.NoEditTriggers)  # edit 금지 모드

    #     else self.logger2.info(f', 코드 : {data[2]}, 종목명 : {data[3]}, 금액 : {data[5]}, 조건식 : {data[0]}')

    def insert_table(self):
        # 테이블 번호
        # table_no = 831
        # 배팅 데이터
        # bet_list = [["P", 1000]]
        numz = 0
        while 1:
            start = timeit.default_timer()
            self.from_dbdata()
            # self.logger4.info("from_dbdata : [%.2f초" % (timeit.default_timer() - start))

            # start1 = timeit.default_timer()
            if self.from_db and self.ctrlCnt < self.table_noCnt:    self.checkover_step()
            # self.logger4.info("checkover_step : [%.2f초" % (timeit.default_timer() - start1))

            # start2 = timeit.default_timer()
            if self.attack:     self.attackData()
            # self.logger4.info("attackData : [%.2f초" % (timeit.default_timer() - start2))

            if self.cntnum % 5 == 0:
                change = self.driver.execute_script(
                    "return GameLayerManager.Instance.sceneLayer.$children[0].lobbyFooter.lblBalance.text")
                self.change = float(change.replace('KRW', '').replace('.00', '').replace(',', ''))
                time.sleep(random.uniform(0.05, 0.15))

            # start3 = timeit.default_timer()
            # 배팅 가능한 상태인지 체크
            attnum = len(self.dbtablesum)
            if self.dbtablesum:
                for a in range(attnum):
                    # 테이블 번호, 포지션, 금액
                    data = self.dbtablesum.pop()
                    bet_result = self.betting(int(data['ta']), str(data['bp']), int(data['mon']),
                                              str(data['game']), int(data['ctmoney']))
                    self.logger2.info(f"배팅 성공 여부: {bet_result}")

                    if not bet_result:
                        self.dt.insert(0, data)
                        self.logger2.info(f"배팅 재시도: {data}")
                    # time.sleep(0.5)
                    numz = 1
                if self.dt:
                    l = len(self.dt)
                    for k in range(l):
                        self.dbtablesum.insert(0, self.dt.pop())

            # self.logger4.info(f"betting : [%.2f초, attnum : {attnum}, delaycnt : {self.delaycnt}" % (timeit.default_timer() - start3))
            self.last_update = time.time()

            # 로비로 돌아가지 않도록
            if self.cntnum % 15 == 0:
                self.driver.execute_script("user.updateBalance();"
                                           "GameLayerManager.Instance.sceneLayer.$children[0].lobbyFooter.btnRefreshBalance.startProcessing(1e3);")
                time.sleep(random.uniform(0.05, 0.1))
                self.driver.execute_script("GameLayerManager.Instance.sceneLayer.$children[0].counter = 0")
                time.sleep(random.uniform(0.05, 0.1))
                self.logger5.info('발란스 클릭')

            if self.cntnum % 45 == 0:
                print(f'--{datetime.datetime.now().strftime("%H:%M:%S")}, 잔액 : {change}')
                self.cntnum = 0

            if self.delaycnt == 0:
                time.sleep(random.uniform(0.7, 1.3))
                time.sleep(random.uniform(0.7, 1.3))
                self.from_dbdata()
                time.sleep(random.uniform(0.7, 1.3))
            elif 0 < self.delaycnt <= 2:
                self.from_dbdata()
                time.sleep(random.uniform(0.7, 1.3))
                time.sleep(random.uniform(0.7, 1.3))
            elif 2 < self.delaycnt <= 4:
                self.from_dbdata()
                time.sleep(random.uniform(0.7, 1.3))

            self.delaycnt = 0
            self.cntnum += 1

            self.logger4.info("-- bbtime4 : [%.1f초" % (timeit.default_timer() - start))
            self.logger4.info("===============================================================")
            if numz != 0:
                print("-- bbtime4 : [%.1f초" % (timeit.default_timer() - start))
                numz = 0

    def _check_config(self):
        if set(GS._DEFAULT_CONF_DB) != set((dict(self._config.items(GS._CONF_DB_KEY)).keys())):
            raise Exception("필요한 설정 항목이 없습니다.")
        if '' in dict(self._config.items(GS._CONF_DB_KEY)).values():
            raise Exception("비어있는 설정이 있습니다.")

        if set(GS._DEFAULT_CONF_SITE) != set((dict(self._config.items(GS._CONF_SITE_KEY)).keys())):
            raise Exception("필요한 설정 항목이 없습니다.")
        if '' in dict(self._config.items(GS._CONF_SITE_KEY)).values():
            raise Exception("비어있는 설정이 있습니다.")

        if set(GS._DEFAULT_CONF_SERVICE) != set((dict(self._config.items(GS._CONF_SERVICE_KEY)).keys())):
            raise Exception("필요한 설정 항목이 없습니다.")
        if '' in dict(self._config.items(GS._CONF_SERVICE_KEY)).values():
            raise Exception("비어있는 설정이 있습니다.")

    def _health_checker(self):
        if (time.time() - self.last_update) > 30:
            raise TimeoutError("응답 없음")

        self.timer = threading.Timer(5, self._health_checker)
        self.timer.daemon = True
        self.timer.start()

    def setup(self, url, id, id2, pw):
        self._url, self._id, self._id2, self._pw = url, id, id2, pw
        self._login()
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
            os.system("taskkill /f /im chromedriver.exe /t")
            self.driver.close()
            time.sleep(3)
        finally:
            time1 = datetime.datetime.now().strftime("%H:%M:%S")
            print(f"{time1} : 잔여 프로세스 정리")
