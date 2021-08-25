# import urllib
import pymysql
# from urllib.request import urlopen
# from bs4 import BeautifulSoup

# Open database connection
db = pymysql.connect(host='hoyarij.tk', port=23306, user='hoyarij', passwd='min4658m*', db='hoyarij', charset='utf8', autocommit=True)

# prepare a cursor object using cursor() method
cursor = db.cursor()

# execute SQL query using execute() method.
cursor.execute("SELECT VERSION()")

# Fetch a single row using fetchone() method.
data = cursor.fetchone()

print("Database version : %s " % data)

# disconnect from server
db.close()
