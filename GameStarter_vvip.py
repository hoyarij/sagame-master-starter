import datetime
import timeit

from PyQt5 import uic
from PyQt5.QtWidgets import QMainWindow
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.common.keys import Keys
from selenium.common import exceptions
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

import pymysql.cursors
import configparser
import time
import sys
import os
import threading


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
            state = driver.execute_script(
                "return window.user._hosts.length"
            )
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
    _DEFAULT_CONF_SITE = ["site_url", "site_id_selector", "site_pwd_selector", "sagame_id", "site_id", "site_pwd",
                          "site_game_selector"]
    _DEFAULT_CONF_SERVICE = ['default_timeout', "default_delay", "scan_speed",
                             "table_min_size"]

    def __init__(self, setting_path, driver_path):
        super().__init__()
        self.setupUi(self)
        self._id = ''
        self._id2 = ''
        self._pw = ''
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
                                    password=self._config["DB"]["DB_PWD"] if self._config["DB"][
                                                                                 "DB_PWD"] != ";" else None,
                                    db=self._config["DB"]["DB_NAME"],
                                    charset="utf8",
                                    port=int(self._config["DB"]["DB_PORT"]))

        option = Options()
        self.driver = webdriver.Chrome(executable_path='./chromedriver', chrome_options=option)
        self.driver.set_window_size(1300, 950)
        # self.driver = webdriver.Chrome(driver_path)
        self.driver.implicitly_wait(self._default_timeout)

        self.last_tables = {}
        self.last_update = 0.0
        self.from_db = []
        self.start_no = ['0']
        self.table_no = []
        # self.dbtable_no = []
        self.dbtablesum = []
        self.sagamearr = []
        self.changeBP = []
        self.change = 0
        self.cntnum = 0

        self.money0 = 0
        self.money1 = 0
        self.money2 = 0
        self.wlData = []
        self.ldata = []

        self.onecnt = True
        self.attack = False
        self.ctrl = []
        self.ctrlNG = []
        self.ctrlOG = []
        self.ctrlBG = []
        self.ctrlBB = []
        self.ctrlYJ = []
        self.ctrlYK = []
        self.bet_list = []

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
        id_input.send_keys(self._id)
        pwd_input = self.driver.find_element_by_css_selector(self._site_conf["site_pwd_selector"])
        pwd_input.send_keys(self._pw)
        pwd_input.send_keys(Keys.ENTER)
        time.sleep(self._default_delay)

    def _start_sa_game(self):
        if (self.driver.find_elements_by_css_selector("#eaevent-close")):
            t = self.driver.find_elements_by_css_selector("#eaevent-close")
            for i in t:
                try:
                    i.click()
                except:
                    pass
            time.sleep(2)

        # ##################### 창닫기 - X 버튼 눌러야 없어지는 창.
        if (self.driver.find_elements_by_css_selector("#warning2021-close")):
            # print('a')
            t = self.driver.find_elements_by_css_selector("#warning2021-close")
            for i in t:
                try:
                    i.click()
                except:
                    pass
            time.sleep(2)

        # 멀티요소 셀렉터
        list = self.driver.find_elements_by_css_selector('.btn.gamestart')
        n = 1
        for data in list:
            if n == 6:
                data.find_element_by_css_selector("i").click()
            n += 1        # self.driver.find_element_by_css_selector('#div.gamenav > ul > li: nth - child(2)').click()

        # self.driver.find_element_by_css_selector('#sagame').click()     # 단일요소 셀렉터

        window_handle = self.driver.window_handles.copy()

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
})();""" % coin_index_list
        )

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
        {
        currentTarget: 
        GameLayerManager.Instance.sceneLayer.$children[0].tableList.$children[%s].$children[10].$children[15].$children[%s]
        })""" % (table, table, position))

    def betting(self, table: int, position: str, money: int, game: str, ctmoney: int):
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

        print(f"배팅 테이블 번호: {table_index + 1}")

        if table_index < 12:
            self.driver.execute_script("scrollBy(0,-600);")
        else:
            self.driver.execute_script("window.scrollTo(0,document.body.scrollHeight)")

        if not self.check_available_bet(table_index):
            print("현재 배팅 불가 테이블입니다.")
            time.sleep(1)
            return False

        if self.check_already_bet(table_index):
            print("이미 배팅한 테이블입니다.")
            time.sleep(2)
            return False

        position_dict = {"P": 0, "T": 1, "B": 2, "PP": 3, "BP": 4, "L": 5}

        if position_dict.get(position, None) is None:
            raise Exception("알 수 없는 포지션입니다.")

        position_index = position_dict[position]

        print(f"배팅 포지션 번호: {position_index + 1}")

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

        data = self.driver.execute_script(
            "try { "
            "GameLayerManager.Instance.upperLayer.$children.filter(x => x.hasOwnProperty('btnConfirm'))[0];"
            "return true "
            "} catch(e) { return false }")
        time.sleep(0.2)
        if data:
            if game == 'r' and ctmoney == 0:
                print(f'att ctmomney : {ctmoney}')
                return self.driver.execute_script(
                    "try { "
                    "GameLayerManager.Instance.upperLayer.$children.filter(x => x.hasOwnProperty('btnConfirm'))[0]._parent.doConfirmBet(); "
                    "GameLayerManager.Instance.upperLayer.$children.filter(x => x.hasOwnProperty('btnConfirm'))[0].doClose();"
                    "return true "
                    "} catch(e) { return false }")
            else:
                print(f'dont att game : {game}')
                print(f'dont att ctmomney : {ctmoney}')
                # self.driver.find_element_by_xpath("//body").send_keys(Keys.ESCAPE)
                return self.driver.execute_script(
                    "try { "
                    "GameLayerManager.Instance.upperLayer.$children.filter(x => x.hasOwnProperty('btnConfirm'))[0].doClose();"
                    "return true "
                    "} catch(e) { return false }")
                return True
        else:
            return data

    def check_available_bet(self, table: int):
        try:
            cTime = int(self.driver.execute_script(
                f"return GameLayerManager.Instance.sceneLayer.$children[0].tableList.$children[{table}].lblStatus.textLabel.text"))
            if cTime < 2:
                print("남은 배팅 시간이 너무 짧습니다.")
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
            if v['no'] == no: delnum.append(i)
        return reversed(delnum)

    def del_data(self, algo, no):
        if self.attack:
            if algo == "NG" and self.ctrlNG:
                for k in self.find_ddata(self.ctrlNG, no):  del self.ctrlNG[k]
            elif algo == "OG" and self.ctrlOG:
                for k in self.find_ddata(self.ctrlOG, no):  del self.ctrlOG[k]
            elif algo == "BG" and self.ctrlBG:
                for k in self.find_ddata(self.ctrlBG, no):  del self.ctrlBG[k]
            elif algo == "BB" and self.ctrlBB:
                for k in self.find_ddata(self.ctrlBB, no):  del self.ctrlBB[k]
            elif algo == "YJ" and self.ctrlYJ:
                for k in self.find_ddata(self.ctrlYJ, no):  del self.ctrlYJ[k]
            elif algo == "YK" and self.ctrlYK:
                for k in self.find_ddata(self.ctrlYK, no):  del self.ctrlYK[k]

            print('cancel attack')
            if not self.ctrlNG and not self.ctrlOG and not self.ctrlBG and not self.ctrlBB and \
                    not self.ctrlYJ and not self.ctrlYK:
                self.attack = False

    def from_dbdata(self):
        id = self._id2
        with self.conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(f"SELECT * FROM sub10 WHERE start = 't' AND readtable = 'f' AND id = '{id}'")
            result = cursor.fetchall()
            cursor.execute(f"SELECT * FROM sub10 WHERE start = 'f' AND readtable = 't' AND id = '{id}'")
            result1 = cursor.fetchall()

            if result:
                for i in result:
                    cursor.execute(f"UPDATE sub10 SET readtable = 't' WHERE no = '{str(i['no'])}'")
                    self.from_db.append(i)
                    print(f'from_db : {self.from_db}')
                    cursor.execute("SELECT ta FROM sub01save use index (idx_date) "
                                   "WHERE date BETWEEN DATE_ADD(now(), INTERVAL -60 minute) AND now() GROUP BY ta")
                    table_no_org = cursor.fetchall()
                    table = {}
                    for k, v in enumerate(i['tableno']):
                        if i['tableno'][k] == 't':
                            try:
                                table[str(k)] = table_no_org[k]['ta']
                                table[str(k) + 'date'] = 'f'
                                table[str(k) + 'tf'] = 'f'
                                table[str(k) + 'beBP'] = 'f'
                                table[str(k) + 'chBP'] = 'f'
                            except:
                                pass
                    self.table_no.append(table)
                    print(f'table_no : {self.table_no}')

            if result1:
                for i in result1:
                    delnum = i['no']
                    data = f"UPDATE sub10 SET readtable = 'f' WHERE no = '{str(delnum)}'"
                    print(f'스톱 : {data}')
                    cursor.execute(data)
                    # num = 0
                    for j, v in enumerate(self.from_db):
                        if int(delnum) == self.from_db[j]['no']:
                            print(f'remove data : {delnum}')
                            self.del_data(self.from_db[j]['sub1001'], self.from_db[j]['no'])
                            del self.from_db[j]
                            del self.table_no[j]

        self.conn.commit()
        # if not result and not result1:
        #     print("result 음슴")

    def chktable(self):
        print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") + ",  " + str(self.table_no))
        # print(self.from_db)

    def checkover_step(self):
        sql = "SELECT DATE_FORMAT(date,'%Y-%m-%d %h:%m:%s') AS date, step, ta, bp, beBP FROM "\
                "(SELECT date, step, ta, bp, beBP FROM sub01save use index (idx_datename) "\
                "WHERE date BETWEEN DATE_ADD(now(), INTERVAL -600 second) AND now() AND "\
                "name = 'NG') AS dout ORDER BY dout.date DESC"
        with self.conn.cursor(pymysql.cursors.DictCursor) as cursor:
        # print(sql)
            cursor.execute(sql)
            result = cursor.fetchall()
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
                        print(f'timepass {tname}')
                        self.table_no[i][val3] = 't'
                        p = val['sub1015']
                        b = val['sub1016']
                        bp = ''
                        if p and b:
                            bp = p + b
                        elif p:
                            bp = p
                        elif b:
                            bp = b
                        # 1,7,8,9,10,11,12, amoset
                        ctrl = {'no': val['no'], 'ta': tname, 'readTime1': '', 'readTime2': '', 'attack': 'f',
                                'attTime': '', 'attBP': '',
                                'TieTime': '',
                                'acstart': 'f', 'beBP': '', 'autoctl': 'f', 'cruse': 'f', 'ng1': 'f',
                                'sncnt': 0, 'rccnt': 0,
                                'amoset': 0, 'attmoney': 0, 'resultmoney': 0,
                                'ctmoney': ctmoney, 'cresultmoney': 0, 'cttopP': 0, 'cttopN': 0,
                                'wincnt': 0, 'losecnt': 0, 'totcnt': 0, 'lastwl': '', 'bp': bp,
                                'sub1001': val['sub1001'], 'sub1007': val['sub1007'], 'sub1008': val['sub1008'],
                                'sub1009': val['sub1009'], 'sub1010': val['sub1010'], 'sub1011': val['sub1011'],
                                'sub1012': val['sub1012'], 'sub1014': val['sub1014'], 'sub1017': val['sub1017'],
                                'sub1018': val['sub1018'], 'sub1019': val['sub1019'], 'amosetorg': val['amoset']
                                }
                        print(f'add ctrl : {ctrl}')
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

                # tablecnt = len(self.dbtable_no)
                # for tnum in range(tablecnt):
                #     sql += "ta = '" + self.dbtable_no[tnum] + "'" if tnum == len(self.dbtable_no) - 1 \
                #         else "ta = '" + self.dbtable_no[tnum] + "' OR "

                if pass1: continue
                if result:
                    for k in result:
                        # if self.cntnum % 30 == 0:
                        #      print(f're first: {k}')
                        for n, val3 in enumerate(ta):
                            if ta[str(val3)] == k["ta"]:
                                a = val3 + 'date'
                                b = val3 + 'beBP'
                                if self.table_no[i][a] == 'f':
                                    self.table_no[i][a] = k['date']
                                    self.table_no[i][b] = k['bp']
                                    print(f'add table info : {self.table_no[i]}')
                                    # datetime.datetime.strptime(self.table_no[i][a], "%Y-%m-%d %H:%M:%S")
                                elif self.table_no[i][a] < k['date']:
                                    c = val3 + 'chBP'
                                    if self.table_no[i][c] == 'f':
                                        if self.table_no[i][b] != k["bp"]:
                                            self.table_no[i][a] = k['date']
                                            self.table_no[i][c] = 't'
                                            print(f'changebp pass table {k["ta"]}')
                                            print(self.table_no[i])

                                            if int(val["sub1002"]) <= 0:
                                                d = val3 + 'tf'
                                                self.table_no[i][d] = datetime.datetime.now().strftime(
                                                    "%Y-%m-%d %H:%M:%S")
                                                print(f'step pass {k["ta"]}')
                                                print(self.table_no[i])

                                    else:
                                        if int(k["step"]) >= int(val["sub1002"]):
                                            # print(f'넘어간 번호 : {val3}')
                                            d = val3 + 'tf'
                                            # print(f'수정 번호 : {a}')
                                            if self.table_no[i][d] == 'f':
                                                self.table_no[i][d] = datetime.datetime.now().strftime(
                                                    "%Y-%m-%d %H:%M:%S")
                                                print(f'stepDB {result}')
                                                print(f'step pass {k["ta"]}')
                                                print(self.table_no[i])

    def attinfo2(self, ctrlData, result, bp):
        mon = ctrlData['amosetorg'].split('|')
        if datetime.datetime.now() < datetime.datetime.strptime(ctrlData['sub1018'], "%Y-%m-%d %H:%M") \
                and float(ctrlData['resultmoney']) < float(ctrlData['sub1014'] * 1000) \
                and self.change < int(ctrlData['sub1019']) * 1000:
            print(f'attack bp : {bp}')
            if ctrlData['sub1001'] == "NG" and result['beBP'] != result['bp'] and bp == result['bp'] and ctrlData['ng1'] == 't' \
                    or ctrlData['sub1001'] == "OG" and result['beBP'] != result['bp'] and bp != result['bp'] and \
                    ctrlData['ng1'] == 't':
                ctrlData['attack'] = 't'
                ctrlData['attTime'] = result['date']
                ctrlData['attBP'] = bp

            if ctrlData['sub1001'] == "NG" and result['beBP'] == result['bp'] and bp == result['bp'] \
                    or ctrlData['sub1001'] == "OG" and result['beBP'] == result['bp'] and bp != result['bp']:
                ctrlData['attack'] = 't'
                ctrlData['attTime'] = result['date']
                ctrlData['attBP'] = bp
            elif ctrlData['sub1001'] == "BG" and bp == result['bp'] \
                    or ctrlData['sub1001'] == "BB" and bp != result['bp']:
                ctrlData['attack'] = 't'
                ctrlData['attTime'] = result['date']
                ctrlData['attBP'] = bp
            elif ctrlData['sub1001'] == "YJ" and bp != result['bp'] \
                    or ctrlData['sub1001'] == "YK" and bp == result['bp']:
                ctrlData['attack'] = 't'
                ctrlData['attTime'] = result['date']
                ctrlData['attBP'] = bp

            if ctrlData['attack'] == 't':
                mon2 = mon[ctrlData['amoset']].split(',')
                ctrlData['attmoney'] = int(mon2[0]) * 1000

                if ctrlData['sub1017'] == 's':
                    print('simul')
                else:
                    print('real')
                data = {'ta': int(ctrlData['ta']), 'bp': ctrlData['attBP'], 'mon': int(ctrlData['attmoney']),
                        'game': ctrlData['sub1017'], 'ctmoney': int(ctrlData['ctmoney'])}

                if not self.dbtablesum:
                    self.dbtablesum.append(data)
                else:
                    cnt = 0
                    for aa in self.dbtablesum:
                        if aa['ta'] == data['ta'] and aa['bp'] == bp:
                            aa['mon'] = aa['mon'] + data['mon']
                            cnt = 1
                    if cnt == 0:
                        self.dbtablesum.append(data)
                    # self.bet_list.insert(0, [int(ctrlData['ta']), bp, ctrlData['attmoney']])
        else:
            print('Game end')
            if datetime.datetime.now() > datetime.datetime.strptime(ctrlData['sub1018'], "%Y-%m-%d %H:%M"):
                print(f'now : {datetime.datetime.now()}')
                print(datetime.datetime.strptime(ctrlData['sub1018'], "%Y-%m-%d %H:%M"))
            elif float(ctrlData['resultmoney']) >= float(ctrlData['sub1014']):
                print(f"resultmoney : {float(ctrlData['resultmoney'])}")
                print(f"setmoney : {float(ctrlData['sub1014'])}")
            elif self.change >= int(ctrlData['sub1019']):
                print(f"limitmoney : {float(ctrlData['sub1019'])}")
                print(f"totalmoney : {self.change}")

    def sqldata(self, ctrl, re):
        if ctrl[0]['sub1001'] == "NG" or ctrl[0]['sub1001'] == "OG":
            sql1 = ''
        else:
            sql1 = "SELECT DATE_FORMAT(date,'%Y-%m-%d %h:%m:%s') AS date, name, step, bp, ta FROM "\
                    "(SELECT date, name, step, bp, ta FROM sub01saveB use index (idx_datename) "\
                    "WHERE date BETWEEN DATE_ADD(now(), INTERVAL -15 second) AND now() AND "
            if ctrl[0]['sub1001'] == "BG" or ctrl[0]['sub1001'] == "BB":
                sql1 += "name = 'BG') AS dout "
            elif ctrl[0]['sub1001'] == "YJ" or ctrl[0]['sub1001'] == "YK":
                sql1 += "name = 'YJ') AS dout "

        with self.conn.cursor(pymysql.cursors.DictCursor) as cursor:
            for ctrlData in ctrl:
                attmin = 0 if ctrlData['sub1007'] == '' else int(ctrlData['sub1007'])
                attmax = 1000 if ctrlData['sub1008'] == '' else int(ctrlData['sub1008'])

                attchk = 0 if ctrlData['sub1009'] == '' else int(ctrlData['sub1009'])
                ssnum = 0 if ctrlData['sub1010'] == '' else int(ctrlData['sub1010'])
                atnum = 0 if ctrlData['sub1011'] == '' else int(ctrlData['sub1011'])
                renum = 0 if ctrlData['sub1012'] == '' else int(ctrlData['sub1012'])

                if sql1 != "":
                    cursor.execute(sql1)
                    re1 = cursor.fetchall()
                else:
                    re1 = ''

                if ctrlData['attack'] == 't':
                    sqlT = f"SELECT host_id, DATE_FORMAT(CD,'%Y-%m-%d %h:%m:%s') AS CD FROM (SELECT host_id, create_datetime AS CD FROM games1 use index (cd_idx) "\
                           f"WHERE create_datetime BETWEEN DATE_ADD(now(), INTERVAL -15 second) AND now()) AS dout WHERE "\
                           f"host_id = '{ctrlData['ta']}'"
                    # print(sqlT)
                    cursor.execute(sqlT)
                    reT = cursor.fetchall()
                    for bp in ctrlData['bp']:
                        if reT:
                            for resultT in reT:
                                if ctrlData['readTime1'] != resultT['CD'] and ctrlData['TieTime'] != resultT['CD'] and bp == ctrlData['attBP'] or \
                                        ctrlData['readTime2'] != resultT['CD'] and ctrlData['TieTime'] != resultT['CD'] and bp == ctrlData['attBP']:
                                    print('result : Tie!!!!!!!!!!!!!!!!!!!!')
                                    print('rebet')
                                    # print(resultT['CD'])
                                    ctrlData['TieTime'] = resultT['CD']
                                    data = {'ta': int(ctrlData['ta']), 'bp': ctrlData['attBP'],
                                            'mon': int(ctrlData['attmoney']), 'game': ctrlData['sub1017'],
                                            'ctmoney': int(ctrlData['ctmoney'])}
                                    self.dbtablesum.append(data)
                        if re:
                            for result in re:
                                # print(result['date'])
                                # 공격 후 결과 값
                                if bp == 'P' and ctrlData['readTime1'] != result['date'] and ctrlData['ta'] == result['ta'] or \
                                    ctrlData['attack'] == 't' and bp == 'B' and ctrlData['readTime2'] != result['date'] and ctrlData['ta'] == result['ta']:

                                    # P 나 B를 체크하고 진입
                                    if bp == 'P':
                                        ctrlData['readTime1'] = result['date']
                                    else:
                                        ctrlData['readTime2'] = result['date']

                                    mon = ctrlData['amosetorg'].split('|')

                                    if ctrlData['attBP'] == bp:  # 공격이 실행되었을때 결과값 찾기
                                        win = 't'
                                        if ctrlData['attBP'] == result['bp']:
                                            print(f'attack!!!!!!!!!!!!!!!!! : win, bp : {bp}, table : {ctrlData["ta"]}')
                                        else:
                                            win = 'f'
                                            print(f'attack!!!!!!!!!!!!!!!!! : lose, bp : {bp}, table : {ctrlData["ta"]}')
                                        ctrlData['attack'] = 'f'
                                        ctrlData['attTime'] = ''
                                        ctrlData['attBP'] = ''
                                        ctrlData['TieTime'] = ''
                                        ctrlData['readTime1'] = ''
                                        ctrlData['readTime2'] = ''

                                        mon2 = mon[ctrlData['amoset']].split(',')
                                        if mon2[1] == '': mon2[1] = 0

                                        if win == 't':
                                            attremoney = int(ctrlData['attmoney']) if result['bp'] == 'P' else int(ctrlData['attmoney']) * 0.95
                                            ctrlData['resultmoney'] = ctrlData['resultmoney'] + attremoney

                                            if ctrlData['ctmoney'] != 0:
                                                ctrlData['cresultmoney'] = ctrlData['cresultmoney'] + attremoney
                                                if ctrlData['cttopP'] < ctrlData['cresultmoney']:
                                                    ctrlData['cttopP'] = ctrlData['cresultmoney']

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
                                                if ctrlData['cttopN'] > ctrlData['cresultmoney']:
                                                    ctrlData['cttopN'] = ctrlData['cresultmoney']
                                            ctrlData['amoset'] = int(mon2[3]) - 1
                                            mon3 = mon[ctrlData['amoset']].split(',')
                                            ctrlData['attmoney'] = int(mon3[0]) * 1000
                                            ctrlData['cruse'] = 'f'
                                            ctrlData['losecnt'] = ctrlData['losecnt'] + 1
                                            ctrlData['lastwl'] = 'lose'

                                        if ctrlData['ctmoney'] > 0 >= ctrlData['ctmoney'] - ctrlData['cttopP'] + ctrlData['cttopN'] or \
                                            ctrlData['ctmoney'] < 0 <= ctrlData['ctmoney'] + ctrlData['cttopP'] - ctrlData['cttopN']:
                                            ctrlData['ctmoney'] = 0
                                            ctrlData['amoset'] = 0

                                        # query = f"INSERT INTO sub10{self.id_2} VALUES(null, '{result['date']}', '{ctrlData['ta']}', " \
                                        #         f"'{self.id_2}', '{self.id}', '{win}', '{ctrlData['resultmoney']}', '{ctrlData['attmoney']}', " \
                                        #         f"'{ctrlData['sub1017']}')"
                                        self.money0 = int(self.money0) + int(attremoney) if win == 't' else int(self.money0) - int(attremoney)
                                        data = (self._id2, result['date'], ctrlData['ta'], self._id2, self._id, win,
                                                self.money0, attremoney, ctrlData['sub1017'])
                                        # self.wlData.append([result['date'].strftime("%Y-%m-%d %H:%M:%S"), ctrlData['ta'], win, self.money0, attremoney, ctrlData['sub1017']])
                                        query = "INSERT INTO sub10%s VALUES(null, '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s')" % data
                                        # print(query)
                                        cursor.execute(query)
                                        ctrlData['totcnt'] = ctrlData['totcnt'] + 1
                                        change = self.driver.execute_script(
                                            "return GameLayerManager.Instance.sceneLayer.$children[0].lobbyFooter.lblBalance.text")
                                        print(f'{datetime.datetime.now().strftime("%H:%M:%S")}, 잔액 : {change}')

                if ctrlData['attack'] == 'f':
                    step = 0
                    if sql1 == "":  # NG일때만
                        if re:
                            for result in re:
                                step = int(result['step'])
                    else:
                        if re1:
                            for result in re1:
                                step = int(result['step'])

                    if 0 < step:
                        # attack 이전일때
                        if ctrlData['autoctl'] == 't':  # 오토컨트롤 일때 값 늘이기
                            autonum = atnum
                            attmin = attmin + autonum
                            attmax = attmax + autonum

                        if 0 < attchk <= step and ctrlData['autoctl'] == 'f':  # 오토컨트롤 체크
                            ctrlData['sncnt'] = ctrlData['sncnt'] + 1
                            if 0 < ssnum == ctrlData['sncnt']:  # 오토컨트롤 시작
                                ctrlData['autoctl'] = 't'
                                ctrlData['sncnt'] = 0
                        elif attmax <= step and ctrlData['autoctl'] == 't':  # 리턴갯수 체크
                            ctrlData['rccnt'] = ctrlData['rccnt'] + 1
                            if 0 < renum == ctrlData['rccnt']:  # 오토컨트롤 종료
                                ctrlData['autoctl'] = 'f'
                                ctrlData['rccnt'] = 0

                    # attack check
                    if sql1 == "":  # NG일때만
                        if re:
                            for result in re:
                                step = int(result['step'])
                                for bp in ctrlData['bp']:
                                    if attmin <= 1 and ctrlData['attack'] == 'f' and result['bp'] != result[
                                        'beBP']:  # 1단계 어택하기
                                        if bp == 'P' and ctrlData['readTime1'] != result['date'] and ctrlData['ta'] == result['ta'] or \
                                            bp == 'B' and ctrlData['readTime2'] != result['date'] and ctrlData['ta'] == result['ta']:
                                            if bp == 'P':
                                                ctrlData['readTime1'] = result['date']
                                            else:
                                                ctrlData['readTime2'] = result['date']
                                            ctrlData['ng1'] = 't'
                                            print(f'resultData = {result}')
                                            print(f'ctrlData = {ctrlData}')
                                            self.attinfo2(ctrlData, result, bp)
                                    elif attmin <= step + 1 <= attmax and ctrlData['attack'] == 'f':  # 나머지 단계어택하기
                                        if bp == 'P' and ctrlData['readTime1'] != result['date'] and ctrlData['ta'] == result['ta'] or \
                                            bp == 'B' and ctrlData['readTime2'] != result['date'] and ctrlData['ta'] == result['ta']:
                                            if bp == 'P':
                                                ctrlData['readTime1'] = result['date']
                                            else:
                                                ctrlData['readTime2'] = result['date']
                                            print(f'resultData = {result}')
                                            print(f'ctrlData = {ctrlData}')
                                            self.attinfo2(ctrlData, result, bp)
                    else:
                        if re1:
                            for result in re1:
                                step = int(result['step'])
                                for bp in ctrlData['bp']:
                                    if attmin <= step <= attmax and ctrlData['attack'] == 'f':  # 어택하기
                                        if bp == 'P' and ctrlData['readTime1'] != result['date'] and ctrlData['ta'] == result['ta'] or \
                                            bp == 'B' and ctrlData['readTime2'] != result['date'] and ctrlData['ta'] == result['ta']:
                                            if bp == 'P':
                                                ctrlData['readTime1'] = result['date']
                                            else:
                                                ctrlData['readTime2'] = result['date']
                                            print(f'resultData = {result}')
                                            print(f'ctrlData = {ctrlData}')
                                            self.attinfo2(ctrlData, result, bp)
        self.conn.commit()

    def attackData(self):
        sql = "SELECT DATE_FORMAT(date,'%Y-%m-%d %h:%m:%s') AS date, name, step, bp, ta, beBP FROM "\
                "(SELECT date, name, step, bp, ta, beBP FROM sub01save use index (idx_datename) "\
                "WHERE date BETWEEN DATE_ADD(now(), INTERVAL -15 second) AND now() AND "\
                "name = 'NG') AS dout"
        # sql += "name = 'NG') AS dout WHERE "
        # tablecnt = len(self.dbtable_no)
        # for tnum in range(tablecnt):
        #     sql += "ta = '" + self.dbtable_no[tnum] + "'" if tnum == len(self.dbtable_no) - 1 \
        #         else "ta = '" + self.dbtable_no[tnum] + "' OR "

        with self.conn.cursor(pymysql.cursors.DictCursor) as cursor:
            if self.cntnum % 60 == 0:
                print(f'NGsql : {sql}')
            cursor.execute(sql)
            re = cursor.fetchall()

        if self.ctrlNG:            self.sqldata(self.ctrlNG, re)
        if self.ctrlOG:            self.sqldata(self.ctrlOG, re)
        if self.ctrlBG:            self.sqldata(self.ctrlBG, re)
        if self.ctrlBB:            self.sqldata(self.ctrlBB, re)
        if self.ctrlYJ:            self.sqldata(self.ctrlYJ, re)
        if self.ctrlYK:            self.sqldata(self.ctrlYK, re)

    def insert_table(self):
        # 테이블 번호
        # table_no = 831
        # 배팅 데이터
        # bet_list = [["P", 1000]]
        numz = 0
        while True:
            start = timeit.default_timer()
            self.from_dbdata()
            if self.from_db:    self.checkover_step()
            if self.attack:     self.attackData()

            if self.cntnum % 10 == 0:
                change = self.driver.execute_script(
                    "return GameLayerManager.Instance.sceneLayer.$children[0].lobbyFooter.lblBalance.text")
                self.change = float(change.replace('KRW', '').replace('.00', '').replace(',', ''))

            # 배팅 가능한 상태인지 체크
            if len(self.dbtablesum) != 0:
                dt = []
                for aa in range(len(self.dbtablesum)):
                    # 테이블 번호, 포지션, 금액
                    data = self.dbtablesum.pop()
                    bet_result = self.betting(int(data['ta']), str(data['bp']), int(data['mon']),
                                              str(data['game']), int(data['ctmoney']))
                    print(f"배팅 성공 여부: {bet_result}")

                    if not bet_result:
                        dt.append(data)
                        print(f"배팅 재시도: {data}")
                    # time.sleep(0.5)
                    numz = 1
                if len(dt) != 0:
                    for k in dt:
                        self.dbtablesum.append(k)

            time.sleep(0.25)

            # time.sleep(float(self._service_conf["scan_speed"]))
            self.last_update = time.time()

            # 로비로 돌아가지 않도록
            if self.cntnum % 15 == 0:
                self.driver.execute_script("user.updateBalance();"
                                           "GameLayerManager.Instance.sceneLayer.$children[0].lobbyFooter.btnRefreshBalance.startProcessing(1e3);")
                self.driver.execute_script("GameLayerManager.Instance.sceneLayer.$children[0].counter = 0")

            if self.cntnum % 90 == 0:
                print(f'{datetime.datetime.now().strftime("%H:%M:%S")}, 잔액 : {change}')
                self.cntnum = 0

            self.cntnum = self.cntnum + 1

            if numz != 0:
                stop = timeit.default_timer()
                bbtime = stop - start
                print("bbtime4 : %.1f초" % bbtime)
                numz = 0

    # def insert_table(self):
    #     bet = False
    #     tableno = 0
    #     tablebet = self.driver.execute_script(
    #         f"return GameLayerManager.Instance.sceneLayer.$children[0].tableList.$children[{tableno}].$children[10].$children[15].$children[0].$touchEnabled"
    #     )
    #
    #     while True:
    #         change = self.driver.execute_script(
    #             "return GameLayerManager.Instance.sceneLayer.$children[0].lobbyFooter.lblBalance.text")
    #         print(f'잔액 : {change}')  # 잔액이 나오지를 않네요.
    #         time.sleep(5)
    #
    #         # money1 = '1000'       # 금액1
    #         # table1 = '835'      # 테이블1
    #         # bet1 = "P"          # 배팅1
    #         #
    #         # money2 = '2000'       # 금액2
    #         # table2 = '837'      # 테이블2
    #         # bet2 = "B"          # 배팅2
    #         #
    #         # self.driver.execute_script(
    #         #     "GameLayerManager.Instance.sceneLayer.$children[0].tableList.$children[0]."
    #         #     "doBet({currentTarget: GameLayerManager.Instance.sceneLayer.$children[0].tableList.$children[0].$children[10].$children[15].$children[0]})"
    #         # )
    #         #
    #         if not bet:
    #             bet = True
    #             # 배팅 숫자
    #             # 0: 플레이어, 1: 타이, 2: 뱅커, 3: 플레이어페어, 4: 뱅커페어, 5: 럭키 식스
    #             # 배팅
    #             # 테이블 배팅 아래 예제는 0번째 테이블(1번째 테이블과 동일)에 플레이어 배팅
    #             # 테이블 : 253줄 tableList.$children[1], 254줄 tableList.$children[1].
    #             # 배팅숫자 : $children[15].$children[2]})
    #             # self.driver.execute_script(
    #             #     """
    #             #     (async () => {
    #                 GameLayerManager.Instance.sceneLayer.$children[0].tableList.$children[1].doBet({
    #                 currentTarget: GameLayerManager.Instance.sceneLayer.$children[0].tableList.$children[1].
    #                 $children[10].$children[15].$children[2]})
    #                 await new Promise(resolve => setTimeout(resolve, 500));
    #                 GameLayerManager.Instance.upperLayer.$children[2]._parent.doConfirmBet();
    #             #     })()
    #             #     """
    #             # )
    #             # print('배팅')
    #             # 여기서 위의 1번과 2번을 배팅하고 싶습니다.
    #
    #         time.sleep(float(self._service_conf["scan_speed"]))
    #         self.last_update = time.time()
    #         self.driver.find_element_by_tag_name("canvas").click()  # 캔바스를 클릭이 되는게 아니라 잔액 새로고침이 클릭되도록 부탁드립니다.

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

    def setup(self, id, id2, pw):
        self._id = id
        self._id2 = id2
        self._pw = pw
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
            os.system("taskkill /f /im chromedriver.exe /t")
            self.driver.close()
            time.sleep(3)
        finally:
            time1 = datetime.datetime.now().strftime("%H:%M:%S")
            print(f"{time1} : 잔여 프로세스 정리")
