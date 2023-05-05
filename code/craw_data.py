import requests
import os
import pandas as pd
import json
from datetime import date, datetime, timedelta
import time
import random
import os.path
from os import path
import traceback

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

from urllib.parse import urlparse, parse_qs, urlencode, urlunparse


def main():
    start_date = date(2023, 4, 1)
    end_date = date(2023, 5, 1)
    craw_data(start_date, end_date)


def find_requests(driver, company_selector=None, luzi_selector=None, data_selector=None):
    company_url = None
    luzi_url = None
    data_url = None

    for log_entry in driver.get_log('performance'):
        try:
            log_data = json.loads(log_entry['message'])
            request_url = log_data['message']['params']['request']['url']

            if company_selector and company_selector in request_url:
                company_url = request_url
            elif luzi_selector and luzi_selector in request_url:
                luzi_url = request_url
            elif data_selector and data_selector in request_url:
                data_url = request_url

            if company_url and luzi_url and data_url:
                break

        except (json.JSONDecodeError, KeyError, requests.exceptions.RequestException):
            pass

    return company_url, luzi_url, data_url


def setup_webdriver():
    caps = DesiredCapabilities.CHROME
    caps['goog:loggingPrefs'] = {'performance': 'ALL'}

    chrome_options = Options()
    chrome_options.add_argument('--enable-logging')
    chrome_options.add_argument('--v=1')
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--disable-gpu')

    wd = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options,
                          desired_capabilities=caps)

    return wd


def load_website(driver, url):
    driver.get(url)  # 打开要爬的网址
    driver.implicitly_wait(10)  # 每0.5秒进行一次操作 如果一直失败超过10秒则报错


def close_homepage_banner(driver):
    driver.find_element(By.XPATH, '//*[@id="gkClose"]').click()  # 关掉首页黄色通知


def open_dropdown_menu(driver):
    driver.find_element(By.XPATH, '//*[@id="psListShowBtn"]').click()  # 点开下拉菜单


def select_company(driver, company_name):
    driver.find_element(By.XPATH, f"//li[contains(., '{company_name}')]").click()  # 点击公司名


def select_datamonitor(driver):
    driver.find_element(By.XPATH, '//*[@id="monitordata"]').click()


def create_replacement_dict(first_string, provided_dict):
    first_url = urlparse(first_string)
    first_query_params = parse_qs(first_url.query)
    replacement_dict = {}

    for key, value in provided_dict.items():
        if key != 'pscode' and key != 'outputcode' and key != 'day':
            replacement_dict[key] = first_query_params[key][0]
        else:
            replacement_dict[key] = provided_dict[key]

    return replacement_dict


def replace_query_params_with_dict(url_string, replacement_dict):
    # Parse URL and extract query parameters
    url = urlparse(url_string)
    query_params = parse_qs(url.query)

    # Replace query parameters in the URL with values from the dictionary
    for key in replacement_dict:
        query_params[key] = replacement_dict[key]

    # Construct the modified URL
    modified_query = urlencode(query_params, doseq=True)
    modified_url = urlunparse((url.scheme, url.netloc, url.path, url.params, modified_query, url.fragment))

    return modified_url


def craw_data(start_date, end_date=None):
    try:
        headers = {
            'User-Agent': 'Mozilla'
                          '/5.0 (Macintosh; Intel Mac OS X 10_14) ''AppleWebKit'
                          '/605.1.15 (KHTML, like Gecko) ''Version/12.0 Safari/605.1.15',
        'Connections':'close'}

        file_path = './data/'
        if not end_date:
            end_date = datetime.now().date()
        delta = timedelta(days=1)

        df_code = pd.read_csv(os.path.join(file_path, 'luzi_code.csv'))
        ps_code_list = df_code['ps_code'].unique()

        url = 'https://ljgk.envsc.cn/'

        company_name = '温州龙湾伟明环保能源有限公司'
        select_company_url = 'GetPSList.ashx'
        select_luzi_url = 'GetBurnList.ashx'
        select_data_url = 'GetMonitorDataList.ashx'

        provided_dict = {
            'pscode': 'pscode',
            'outputcode': 'outputcode',
            'day': 'day',
            'SystemType': 'NewSystemType',
            'sgn': 'NewSgnValue',
            'ts': 'NewTsValue',
            'tc': 'NewTcValue'
        }

        wd = setup_webdriver()
        load_website(wd, url)
        close_homepage_banner(wd)
        open_dropdown_menu(wd)
        time.sleep(5)
        select_company(wd, company_name)
        select_datamonitor(wd)

        company_url, _, data_url = find_requests(wd, select_company_url, select_luzi_url, select_data_url)

        # 全公司信息
        company_html = requests.get(company_url, headers=headers)
        all_company = pd.json_normalize(company_html.json())
        wd.close()

        current_date = start_date
        while current_date < end_date:
            current_date_str = current_date.strftime('%Y%m%d')

            for ps in ps_code_list:
                # 获取公司名称
                company_name = all_company[all_company['ps_code'] == ps]['ps_name'].tolist()[0]
                company_folder = os.path.join(file_path, company_name)

                csv_file = os.path.join(company_folder, f"{current_date_str}.csv")
                if not path.exists(csv_file):
                    mp_code_list = df_code[df_code['ps_code'] == ps]['mp_code'].unique()
                    df_final = pd.DataFrame()
                    for mp in mp_code_list:
                        provided_dict['pscode'] = ps
                        provided_dict['outputcode'] = mp
                        provided_dict['day'] = current_date_str

                        replacement_dict = create_replacement_dict(data_url, provided_dict)
                        real_data_url = replace_query_params_with_dict(data_url, replacement_dict)
                        # 开始爬取数据
                        time.sleep(random.uniform(5, 10))
                        temp_data = requests.get(real_data_url, headers=headers).json()
                        df_data = pd.DataFrame()
                        for i in range(len(temp_data)):
                            test = pd.json_normalize(temp_data[i])
                            df_data = pd.concat([df_data, test]).reset_index(drop=True)

                        df_final = pd.concat([df_final, df_data]).reset_index(drop=True)
                        # Save df_data to a CSV file in a folder named with company_name
                    # if not df_final.empty:
                    os.makedirs(company_folder, exist_ok=True)
                    df_final.to_csv(csv_file, index=False, encoding='utf_8_sig')
                    # print(f'{company_name} - {current_date} - Finished')
                    time.sleep(random.uniform(5, 10))
            print(f'{current_date} - Finished')
            current_date += delta
        return
    except Exception as e:
        traceback.print_exc()
        return


if __name__ == '__main__':
    start_time = time.time()
    main()
    end_time = time.time()
    elapsed_time = end_time - start_time
    if elapsed_time > 5 * 60 * 60:  # 5 hours in seconds
        raise SystemExit('Program exceeded 5 hours of running time')
