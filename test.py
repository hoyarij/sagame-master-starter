import datetime


import pymysql.cursors
import configparser
import time
import sys
import os
import threading


class GS:
    _CONF_DB_KEY = "DB"
    _CONF_SITE_KEY = "SITE"
    _CONF_SERVICE_KEY = "SERVICE"
    _DEFAULT_CONF_DB = ["db_host", "db_port", "db_user", "db_pwd", "db_name"]
    _DEFAULT_CONF_SITE = ["site_url", "site_id_selector", "site_pwd_selector", "site_id", "site_pwd",
                          "site_game_selector"]
    _DEFAULT_CONF_SERVICE = ['default_timeout', "default_delay", "scan_speed",
                             "table_min_size"]

    def __init__(self):
        self.dbcon = {'host':"hoyarij.tk",
                      'port':33306,
                      'user':"hoyarij",
                      'password':"min4658m*",
                      'database':"sagame",
                      'charset':"utf8"
                      }

        self.last_tables = {}
        self.last_update = 0.0
        self.from_db = []
        self.start_no = ['0']
        self.table_no = []
        self.sagamearr = []

        self.attack = False
        self.addTableNG = []
        self.ctrlNG = []
        self.addTableOG = []
        self.ctrlOG = []
        self.addTableBG = []
        self.ctrlBG = []
        self.addTableBB = []
        self.ctrlBB = []
        self.addTableYJ = []
        self.ctrlYJ = []
        self.addTableYK = []
        self.ctrlYK = []

    def find_ddata(self, data, no):
        delnum = []
        for i, v in enumerate(data):
            if v['no'] == no:
                delnum.append(i)
        return reversed(delnum)

    def del_data(self, algo, no):
        if self.attack:
            if algo == "NG" and self.addTableNG:
                for j in self.find_ddata(self.addTableNG, no):
                    del self.addTableNG[j]
            elif algo == "OG" and self.addTableOG:
                for j in self.find_ddata(self.addTableOG, no):
                    del self.addTableOG[j]
            elif algo == "BG" and self.addTableBG:
                for j in self.find_ddata(self.addTableBG, no):
                    del self.addTableBG[j]
            elif algo == "BB" and self.addTableBB:
                for j in self.find_ddata(self.addTableBB, no):
                    del self.addTableBB[j]
            elif algo == "YJ" and self.addTableYJ:
                for j in self.find_ddata(self.addTableYJ, no):
                    del self.addTableYJ[j]
            elif algo == "YK" and self.addTableYK:
                for j in self.find_ddata(self.addTableYK, no):
                    del self.addTableYK[j]

            if not self.addTableNG and not self.addTableOG and not self.addTableBG and not self.addTableBB and \
                    not self.addTableYJ and not self.addTableYK:
                print('cancel attack')
                self.attack = False

    def from_dbdata(self):
        # id = self._site_conf["site_id"]
        id = 'hoyarij'
        conn = pymysql.connect(host="hoyarij.tk",
                               user="hoyarij",
                               password="min4658m*",
                               db="sagame",
                               charset="utf8",
                               port=33306,
                               cursorclass=pymysql.cursors.DictCursor)
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM sub10 WHERE start = 't' AND readtable = 'f' AND id = '" + id + "'")
            result = cursor.fetchall()
            cursor.execute("SELECT * FROM sub10 WHERE start = 'f' AND readtable = 't' AND id = '" + id + "'")
            result1 = cursor.fetchall()
            if result:
                for i in result:
                    data = "UPDATE sub10 SET readtable = 't' WHERE no = '" + str(i['no']) + "'"
                    i['readtable'] = 't'
                    # print(data)
                    cursor.execute(data)
                    conn.commit()
                    self.from_db.append(i)
                    cursor.execute("SELECT ta FROM sub01save use index (idx_date) "
                                   "WHERE date BETWEEN DATE_ADD(now(), INTERVAL -60 minute) AND now() GROUP BY ta")
                    table_no_org = cursor.fetchall()
                    table = {}
                    for k, v in enumerate(i['tableno']):
                        if i['tableno'][k] == 't':
                            try:
                                table[str(k)] = table_no_org[k]['ta']
                                table[str(k) + 'tf'] = 'f'
                            except:
                                pass
                    self.table_no.append(table)

            if result1:
                for i in result1:
                    delnum = i['no']
                    data = "UPDATE sub10 SET readtable = 'f' WHERE no = '" + str(delnum) + "'"
                    print(data)
                    cursor.execute(data)
                    conn.commit()
                    # num = 0
                    for j, v in enumerate(self.from_db):
                        if int(delnum) == self.from_db[j]['no']:
                            print(f'remove data : {delnum}')
                            self.del_data(self.from_db[j]['sub1001'], self.from_db[j]['no'])
                            del self.from_db[j]
                            del self.table_no[j]

            # if not result and not result1:
            #     print("result 음슴")
            cursor.close()

    def chktable(self):
        print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") + ",  " + str(self.table_no))
        # print(self.from_db)

    def checkover_step(self):
        for i, val in enumerate(self.from_db):
            sql = "SELECT date, step, ta FROM "
            sql += "(SELECT date, step, ta FROM sub01save use index (idx_datename) "
            sql += "WHERE date BETWEEN DATE_ADD(now(), INTERVAL -5 second) AND now() AND "
            sql += "name = '" + val["sub1001"] + "') AS dout WHERE "

            pass1 = True
            ta = self.table_no[i]
            tanum = len(ta) - 2
            for n, val3 in enumerate(ta):
                if n % 2 == 0:
                    tname = ta[str(val3)]
                    tn = val3 + 'tf'
                    ttf = ta[tn]
                elif n % 2 == 1 and ttf != 'f' and ttf != 't':
                    # 시간 비교함수 활용
                    aftertime = 0 if val['sub1004'] == '' else int(val['sub1004'])
                    if datetime.datetime.strptime(ttf, "%Y-%m-%d %H:%M:%S") + datetime.timedelta(minutes=aftertime) < datetime.datetime.now():
                        print('timepass')
                        self.table_no[i][tn] = 't'
                        tmp = val.copy()
                        del tmp['sub1002']
                        del tmp['sub1003']
                        del tmp['sub1004']
                        del tmp['sub1005']
                        del tmp['sub1006']
                        del tmp['tableno']
                        del tmp['start']
                        del tmp['endchk']
                        del tmp['readtable']
                        tmp['ta'] = tname
                        ctrl = {'readTime': '', 'attack': 'f', 'attTime': '', 'autoctl': 'f', 'sensNum': 0, 'returnctlNum': 0,
                                'count':0, 'amoset':0,'attmoney':0,'resultmoney':0, 'cruse':'f',
                                'loseTowin':0, 'bp':'', 'ta': tname}
                        if val['sub1001'] == "NG":
                            self.addTableNG.append(tmp)
                            self.ctrlNG.append(ctrl)
                        elif val['sub1001'] == "OG":
                            self.addTableOG.append(tmp)
                            self.ctrlOG.append(ctrl)
                        elif val['sub1001'] == "BG":
                            self.addTableBG.append(tmp)
                            self.ctrlBG.append(ctrl)
                        elif val['sub1001'] == "BB":
                            self.addTableBB.append(tmp)
                            self.ctrlBB.append(ctrl)
                        elif val['sub1001'] == "YJ":
                            self.addTableYJ.append(tmp)
                            self.ctrlYJ.append(ctrl)
                        elif val['sub1001'] == "YK":
                            self.addTableYK.append(tmp)
                            self.ctrlYK.append(ctrl)
                        self.attack = True

                if n % 2 == 1 and ttf == 'f':
                    pass1 = False
                if n % 2 == 0 and tanum == n:
                    sql += "ta = '" + tname + "'"
                elif n % 2 == 0 and tanum != n:
                    sql += "ta = '" + tname + "' OR "

            if pass1:
                # print('pass')
                continue
            conn = pymysql.connect(host="hoyarij.tk",
                                   user="hoyarij",
                                   password="min4658m*",
                                   db="sagame",
                                   charset="utf8",
                                   port=33306,
                                   cursorclass=pymysql.cursors.DictCursor)
            with conn.cursor() as cursor:
                # print(sql)
                cursor.execute(sql)
                result = cursor.fetchall()
                if result:
                    for k in result:
                        if int(k["step"]) >= int(val["sub1002"]):
                            for n, val3 in enumerate(ta):
                                if ta[str(val3)] == k["ta"]:
                                    # print(f'넘어간 번호 : {val3}')
                                    a = val3 + 'tf'
                                    # print(f'수정 번호 : {a}')
                                    if self.table_no[i][a] == 'f':
                                        self.table_no[i][a] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                        print(f'resultDB{result}')

    def sqldata(self, data, ctrl):
        na = data[0]['sub1001']
        if na == "NG" or na == "BG" or na == "YJ":
            sql = "SELECT date, name, step, bp, ta, mwin1, close1 FROM "
            sql += "(SELECT date, name, step, bp, ta, mwin1, close1 FROM sub01save use index (idx_datename) "
        else:
            sql = "SELECT date, name, step, bp, ta, close2, mwin2 FROM "
            sql += "(SELECT date, name, step, bp, ta, close2, mwin2 FROM sub01save use index (idx_datename) "
        sql += "WHERE date BETWEEN DATE_ADD(now(), INTERVAL -5 second) AND now() AND "
        sql += "name = '" + na + "') AS dout WHERE "
        tanum = len(ctrl) - 1
        for n, val in enumerate(ctrl):
            if tanum == n:
                sql += "ta = '" + val['ta'] + "'"
            elif tanum != n:
                sql += "ta = '" + val['ta'] + "' OR "
        conn = pymysql.connect(host="hoyarij.tk",
                               user="hoyarij",
                               password="min4658m*",
                               db="sagame",
                               charset="utf8",
                               port=33306,
                               cursorclass=pymysql.cursors.DictCursor)
        with conn.cursor() as cursor:
            print(sql)
            cursor.execute(sql)
            re = cursor.fetchall()
            try:
                # print(f'att_data = {data}')
                print(f'att_result = {re}')
                for i, v in enumerate(data):
                    for ctrlData in ctrl:
                        #             print(v['ta'])
                        #             print(ctrlData['ta'])
                        if v['ta'] != ctrlData['ta']:
                            continue
                        for result in re:
                            if ctrlData['readTime'] != result['date'] and v['ta'] == result['ta']:
                                ctrlData['readTime'] = result['date']
                                step = int(result['step'])
                                attmin = 0 if v['sub1007'] == '' else int(v['sub1007'])
                                attmax = 1000 if v['sub1008'] == '' else int(v['sub1008'])

                                attchk = 0 if v['sub1009'] == '' else int(v['sub1009'])
                                ssnum = 0 if v['sub1010'] == '' else int(v['sub1010'])
                                atnum = 0 if v['sub1011'] == '' else int(v['sub1011'])
                                renum = 0 if v['sub1012'] == '' else int(v['sub1012'])
                                mon = v['amoset'].split('|')

                                p = v['sub1015']
                                b = v['sub1016']
                                if ctrlData['attack'] == 't':  # 공격이 실행되었을때 결과값 찾기
                                    win = 't'
                                    r = result['name']
                                    if r == 'NG' or r == 'BG' or r == 'YJ':
                                        if p and p == result['bp']:
                                            print('win')
                                        elif p and p != result['bp']:
                                            win = 'f'
                                            print('lose')
                                        if b and b == result['bp']:
                                            print('win')
                                        elif b and b != result['bp']:
                                            win = 'f'
                                            print('lose')
                                    elif r == 'OG' or r == 'BB' or r == 'YK':
                                        if p and p == result['bp']:
                                            win = 'f'
                                            print('lose')
                                        elif p and p != result['bp']:
                                            print('win')
                                        if b and b == result['bp']:
                                            win = 'f'
                                            print('lose')
                                        elif b and b != result['bp']:
                                            print('win')
                                    ctrlData['attack'] = 'f'
                                    ctrlData['attTime'] = ''
                                    ctrlData['count'] = ctrlData['count'] + 1

                                    if win == 't':
                                        ctrlData['resultmoney'] = ctrlData['resultmoney'] + int(ctrlData['attmoney']) if \
                                        result['bp'] == 'P' else \
                                            ctrlData['resultmoney'] + ctrlData['attmoney'] * 0.95
                                        if ctrlData['loseTowin'] == 1 and 1 < int(mon[ctrlData['amoset']][2]):  # 크루즈 공략
                                            print('cruse')
                                        else:
                                            ctrlData['amoset'] = int(mon[ctrlData['amoset']][4]) - 1
                                        ctrlData['loseTowin'] = 0
                                    else:
                                        ctrlData['resultmoney'] = ctrlData['resultmoney'] - int(ctrlData['attmoney'])
                                        ctrlData['amoset'] = int(mon[ctrlData['amoset']][6]) - 1
                                        ctrlData['loseTowin'] = 1

                                    ctrlData['attmoney'] = int(mon[ctrlData['amoset']][0]) * 1000

                                #                              1,0,1,2|2,0,1,3|4,0,1,4|8,0,1,5|16,2,1,5|

                                #                     tarmoney 구하기
                                if ctrlData['autoctl'] == 't':  # 오토컨트롤 일때 값 늘이기
                                    autonum = atnum
                                    attmin = attmin + autonum
                                    attmax = attmax + autonum
                                # print(attmin)
                                # print(attmax)
                                if 0 < attchk and attchk <= step and ctrlData['autoctl'] == 'f':  # 오토컨트롤 체크
                                    ctrlData['sensNum'] = ctrlData['sensNum'] + 1
                                    if 0 < ssnum and ssnum == ctrlData['sensNum']:  # 오토컨트롤 시작
                                        ctrlData['autoctl'] = 't'
                                        ctrlData['sensNum'] = 0
                                elif attmax <= step and ctrlData['autoctl'] == 't':  # 리턴갯수 체크
                                    ctrlData['returnctlNum'] = ctrlData['returnctlNum'] + 1
                                    if 0 < renum and renum == ctrlData['returnctlNum']:  # 오토컨트롤 종료
                                        ctrlData['autoctl'] = 'f'
                                        ctrlData['returnctlNum'] = 0

                                if attmin <= int(result['step']) <= attmax and ctrlData['attack'] != 't':  # 어택하기
                                    ctrlData['attack'] = 't'
                                    ctrlData['attTime'] = result['date']
                                    if datetime.datetime.strptime(v['sub1018'],
                                                                  "%Y-%m-%d %H:%M") < datetime.datetime.now() or int(
                                            v['sub1020']) < ctrlData['count'] \
                                            or ctrlData['resultmoney'] < int(v['sub1014']):
                                        #                         or totalmoney < int(v['sub1019']) :

                                        if p:
                                            ctrlData['bp'] = p
                                        elif b:
                                            ctrlData['bp'] = b
                                        if p and b:
                                            ctrlData['bp'] = p + b

                                        if mon[ctrlData['amoset']] == '1,0,1,2':
                                            ctrlData['attmoney'] = int(mon[ctrlData['amoset']][0]) * 1000

                                        if v['sub1017'] == 's':
                                            print('simul')
                                        else:
                                            print('real')

                        print(ctrlData)
            except Exception as err:
                print(f'err : {err}')
                pass

            # if result:
            #     for i, v in enumerate(data):
            #         if result


    def attackData(self):
        if self.addTableNG:
            self.sqldata(self.addTableNG, self.ctrlNG)
            # print(sql)
        if self.addTableOG:
            self.sqldata(self.addTableOG, self.ctrlOG)
        if self.addTableBG:
            self.sqldata(self.addTableBG, self.ctrlBG)
        if self.addTableBB:
            self.sqldata(self.addTableBB, self.ctrlBB)
        if self.addTableYJ:
            self.sqldata(self.addTableYJ, self.ctrlYJ)
        if self.addTableYK:
            self.sqldata(self.addTableYK, self.ctrlYK)

    def parse_db(self):
        # print()
        self.from_dbdata()
        if self.from_db:
            self.chktable()
            self.checkover_step()
        if self.attack:
            self.attackData()


if __name__ == '__main__':
    gp = GS()
    while True:
        gp.parse_db()
        time.sleep(2)
