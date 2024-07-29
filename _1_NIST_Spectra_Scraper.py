#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Download all IR spectra available from NIST Chemistry WebBook.
"""
import os
import re
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
from bs4 import BeautifulSoup
from multiprocessing.pool import ThreadPool
import tqdm
from collections import OrderedDict

NIST_URL = 'http://webbook.nist.gov/cgi/cbook.cgi'
EXACT_RE = re.compile('/cgi/cbook.cgi\?GetInChI=(.*?)$')
ID_RE = re.compile('/cgi/cbook.cgi\?ID=(.*?)&')
# NOTE: Change these
JDX_PATH = 'jdx'
MOL_PATH = 'mol'

# 设置重试策略
retry_strategy = Retry(
    total=5,  # 重试次数
    backoff_factor=1,  # 每次重试之间的等待时间 (例如 1, 2, 4, 8 秒)
    status_forcelist=[429, 500, 502, 503, 504],  # 这些状态码表示需要重试
    allowed_methods=["HEAD", "GET", "OPTIONS"]  # 哪些方法允许重试
)
adapter = HTTPAdapter(max_retries=retry_strategy)


def get_mol(nist_id, session):
    """
    Download mol file for the specified NIST ID, unless already downloaded.
    """
    filepath = os.path.join(MOL_PATH, '%s.mol' % nist_id)

    # 确保目录存在
    directory = os.path.dirname(filepath)
    if not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)

    if os.path.isfile(filepath):
        print('%s: Already exists at %s' % (nist_id, filepath))
        return
    print('%s: Downloading mol' % nist_id)
    response = session.get(NIST_URL, params={'Str2File': nist_id})
    if response.text == ('NIST    12121112142D 1   1.00000     0.00000\nCopyright by the U.S. Sec. Commerce on behalf '
                         'of U.S.A. All rights reserved.\n0  0  0     0  0              1 V2000\nM  END\n'):
        print('%s: MOL not found' % nist_id)
        return
    print('Saving %s' % filepath)
    with open(filepath, 'wb') as file:
        file.write(response.content)


def get_jdx(nist_id, session, stype="IR"):
    """
    Download jdx file for the specified NIST ID, unless already downloaded.
    """
    filepath = os.path.join(JDX_PATH, '%s-%s.jdx' % (nist_id, stype))

    # 确保目录存在
    directory = os.path.dirname(filepath)
    if not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)

    if os.path.isfile(filepath):
        print('%s %s: Already exists at %s' % (nist_id, stype, filepath))
        return
    print('%s %s: Downloading' % (nist_id, stype))
    response = session.get(NIST_URL, params={'JCAMP': nist_id, 'Type': stype, 'Index': 0})
    if response.text == '##TITLE=Spectrum not found.\n##END=\n':
        print('%s %s: Spectrum not found' % (nist_id, stype))
        return
    print('Saving %s' % filepath)
    with open(filepath, 'wb') as file:
        file.write(response.content)


def search_nist_formula(session, formula, allow_other=False, allow_extra=False, match_isotopes=True, exclude_ions=False,
                        has_ir=True):
    """
    Search NIST using the specified formula query and return the matching NIST IDs.
    """
    print('Searching: %s' % formula)
    params = {'Formula': formula, 'Units': 'SI'}
    if allow_other:
        params['AllowOther'] = 'on'
    if allow_extra:
        params['AllowExtra'] = 'on'
    if match_isotopes:
        params['MatchIso'] = 'on'
    if exclude_ions:
        params['NoIon'] = 'on'
    if has_ir:
        params['cIR'] = 'on'
    response = session.get(NIST_URL, params=params)
    soup = BeautifulSoup(response.text, 'html.parser')
    ids = [re.match(ID_RE, link['href']).group(1) for link in soup('a', href=ID_RE)]
    print('Result: %s' % ids)
    return ids


def retrieve_data_from_formula(formula, session):
    ids = search_nist_formula(session, formula, allow_other=True, exclude_ions=False, has_ir=True)
    for nist_id in ids:
        get_mol(nist_id, session)
        get_jdx(nist_id, session)


def remove_duplicates(lst):
    return list(OrderedDict.fromkeys(lst))


def get_all_IR():
    """
    Search NIST for all structures with IR Spectra and download a JDX + Mol file for each.
    """
    formulas = []
    IDs = []
    with open("species.txt") as data_file:
        entries = data_file.readlines()
        for entry in entries:
            try:
                formulas.append(entry.split()[-2])
            except:
                IDs.append(entry.strip())

    # 列表去重
    formulas = remove_duplicates(formulas)
    IDs = remove_duplicates(IDs)

    # NOTE: Change threadpool as you need
    # with ThreadPool(1) as pool:
    #     list(tqdm.tqdm(pool.imap(retrieve_data_from_formula, formulas)))

    # 使用 Session
    with requests.Session() as session:
        session.headers.update({'Connection': 'keep-alive'})
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        for formula in formulas:
            retrieve_data_from_formula(formula, session)
        print("Done with formulas!")

        for nist_id in IDs:
            get_mol(nist_id, session)
            get_jdx(nist_id, session)
        print("Done Scraping Data!")


if __name__ == '__main__':
    get_all_IR()
