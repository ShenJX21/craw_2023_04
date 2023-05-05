import requests
import os
import re
import pandas as pd
import json
# from datetime import datetime, timedelta
import time
import random

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

file_path = './data/'
luzi_path = os.path.join(file_path, 'luzi_code.csv')

headers = {
    'User-Agent': 'Mozilla'
                  '/5.0 (Macintosh; Intel Mac OS X 10_14) ''AppleWebKit'
                  '/605.1.15 (KHTML, like Gecko) ''Version/12.0 Safari/605.1.15'}


def main():
    craw_company_luzi()


def find_requests(driver, select=None, select_company=None, select_luzi=None):
    company_url = None
    luzi_url = None

    for log_entry in driver.get_log('performance'):
        try:
            log_data = json.loads(log_entry['message'])
            request_url = log_data['message']['params']['request']['url']

            if select:
                if select_company and select_company in request_url:
                    company_url = request_url
                elif select_luzi and select_luzi in request_url:
                    luzi_url = request_url

                if company_url and luzi_url:
                    break
            else:
                response = requests.get(request_url)
                response_json = response.json()
                if '二氧化硫' in str(response_json):
                    company_url = luzi_url = request_url
                    break
        except (json.JSONDecodeError, KeyError, requests.exceptions.RequestException):
            pass

    return company_url, luzi_url


def craw_company_luzi():
    url = 'https://ljgk.envsc.cn/'

    caps = DesiredCapabilities.CHROME
    caps['goog:loggingPrefs'] = {'performance': 'ALL'}

    chrome_options = Options()
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--enable-logging')
    chrome_options.add_argument('--v=1')
    wd = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options,
                          desired_capabilities=caps)
    wd.get(url)  # 打开要爬的网址
    wd.implicitly_wait(10)  # 每0.5秒进行一次操作 如果一直失败超过10秒则报错
    # 先模拟点击网页
    wd.find_element(By.XPATH, '//*[@id="gkClose"]').click()  # 关掉首页黄色通知
    wd.find_element(By.XPATH, '//*[@id="psListShowBtn"]').click()  # 点开下拉菜单
    # 找到所有公司信息和相应公司的炉子信息
    company_name = '温州龙湾伟明环保能源有限公司'
    wd.find_element(By.XPATH, f"//li[contains(., '{company_name}')]").click()
    select_company_url = 'GetPSList.ashx'
    select_luzi_url = 'GetBurnList.ashx'
    company_url, luzi_url = find_requests(wd, select=True, select_company=select_company_url,
                                          select_luzi=select_luzi_url)
    wd.close() # 关闭网页

    # 全公司信息
    company_html = requests.get(company_url)
    all_company = pd.json_normalize(company_html.json())
    # all_company.to_csv(os.path.join(file_path, 'company_information.csv'), index=False, encoding='utf_8_sig')
    # 炉子信息
    # 所有的id
    code_list = all_company['ps_code'].tolist()
    # 已有的不用爬取
    all_luzi = pd.read_csv(luzi_path)
    existing_code_list = all_luzi['ps_code'].unique()
    new_list = sorted(list(set(code_list) - set(existing_code_list)))
    
    counter = 0
    for co in new_list:
        try:
            old_code_match = re.search(r"pscode=(?P<code>.*?)&", luzi_url)
            old_code_str = old_code_match.group(1)
            new_url = luzi_url.replace(old_code_str, co)

            luzi_html = requests.get(new_url, headers=headers)
            luzi_code = pd.json_normalize(luzi_html.json())
            luzi_code.to_csv(luzi_path, index=False, encoding='utf_8_sig', header=False,
                             mode='a')
            random_time = random.uniform(10, 20)  # 每一次成功爬取都随机休息5到10秒
            time.sleep(random_time)

            counter += 1
            if counter % 30 == 0:  # 每爬取30个休息30-50秒
                extended_sleep_time = random.uniform(30, 50)
                time.sleep(extended_sleep_time)

        except Exception as e:
            print(f"Error occurred for {co}: {e}")
            return
       


if __name__ == '__main__':
    main()
