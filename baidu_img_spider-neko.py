#!/usr/bin/env python
# -*- coding: utf-8 -*-

import threading
import queue
import time
import os
import argparse

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.options import Options


def make_img_dir(root, img_key_word):
    # generates the dir for storing imgs
    img_dir = os.path.join(root, img_key_word)

    print("trying making dir {}".format(img_dir))

    try:
        os.mkdir(img_dir)
        print("done")
    except FileExistsError:
        print("failed. {} already exists".format(img_dir))

    return img_dir


def generate_url(img_key_word):
    print("generating url displaying imgs to be scratched")

    # generates the url containing images to be scratched
    url = "https://image.baidu.com/search/index?tn=baiduimage&word={}".format(img_key_word)

    print("done")

    return url


def load_imgs(url, img_num):
    print("loading imgs on {}".format(url))

    # starts a web driver
    chrome_options = Options()
    chrome_options.add_argument('--headless')  # makes the driver headless
    driver = webdriver.Chrome(options=chrome_options)

    # switches to the page displaying images
    driver.get(url)
    time.sleep(3)

    # simulates dragging pages down
    img_count = 0
    li_tags = []  # stores li tags, each of which reprs an img
    while img_count < img_num:
        ActionChains(driver).send_keys(Keys.END).perform()
        time.sleep(1)

        # gets the current html text
        html_text = driver.page_source

        # gets all li tags
        li_tags = retrieve_li_tags(html_text)

        img_count = len(li_tags)

    # waits for a moment so that the page can be loaded completely
    time.sleep(5)

    print("done")

    return li_tags


def retrieve_li_tags(html_text):
    # parses the html text
    soup = BeautifulSoup(html_text, 'html.parser')

    try:
        # finds the div tag whose id is imgid, which contains all urls and exts of the images
        div_imgid = soup.find('div', id='imgid')

        # finds all li tags from the div tags, each of which reprs an image
        li_tags = div_imgid.find_all('li')
    except:
        print("baidu_img_spider.py: error: no image scratched")
        exit(1)
    else:
        return li_tags


class ImgUrlNExtRetrievingThread(threading.Thread):
    def __init__(self, name, li_tags, img_url_ext_queue):
        super(ImgUrlNExtRetrievingThread, self).__init__()
        self.name = name
        self.li_tags = li_tags
        self.download_url_queue = img_url_ext_queue
        self.li = None

    def run(self):
        # retrieves the url and ext of each image and puts it into the queue
        # in the form of (url, ext)
        while len(self.li_tags):
            # pops a li tag
            self.li = self.li_tags.pop()

            try:
                # retrieves (url, ext) from the li tag
                self.download_url_queue.put((self.li['data-objurl'], self.li['data-ext']))
            except KeyError:
                pass


class ImgDownloadingThread(threading.Thread):
    def __init__(self, name, img_url_ext_queue, root, img_key_word, img_dir, img_num):
        super(ImgDownloadingThread, self).__init__()
        self.name = name
        self.img_url_ext_queue = img_url_ext_queue
        self.root = root
        self.img_key_word = img_key_word
        self.img_dir = img_dir
        self.img_num = img_num

        self.img_url_ext = None
        self.img_url = None
        self.img_ext = None

        self.img_content = None
        self.img_path = None

    def run(self):
        while not self.img_url_ext_queue.empty():
            # gets the url and ext of an img
            self.img_url_ext = self.img_url_ext_queue.get()

            self.download_img()

    def download_img(self):
        # gets the url
        self.img_url = self.img_url_ext[0]
        # gets the ext
        self.img_ext = self.img_url_ext[1]

        # downloads the img
        self.get_img_content()

        # generates the file path of the img
        self.get_img_path()

        # saves the img
        if self.img_content:
            self.save_img()

    def get_img_content(self):
        try:
            r = requests.get(self.img_url, timeout=10)
            r.raise_for_status()
            self.img_content = r.content
        except:
            pass

    def get_img_path(self):
        # generates the path by concatenating (dir of the imgs) + (value of count) + (ext of the img)
        self.img_path = os.path.join(self.img_dir, str(count) + ".{}".format(self.img_ext))

    def save_img(self):
        global count

        # increases count by 1
        count_lock.acquire()

        try:
            if count >= self.img_num:
                exit(0)

            with open(self.img_path, "wb") as f:
                f.write(self.img_content)
                print("a(n) {} img is saved. {} in total now".format(self.img_ext, count + 1))

                count += 1
        except:
            pass
        finally:
            count_lock.release()


def create_threads(li_tags, img_url_ext_queue, root, img_key_word, img_dir, img_num):
    # creates a thread for storing (url of the img, ext of the img) retrieved from the li tags
    img_url_ext_retrieving_thread = ImgUrlNExtRetrievingThread("img_url_ext_retrieving_thread", li_tags,
                                                               img_url_ext_queue)

    img_downloading_thread_list = []
    for i in range(6):
        img_downloading_thread = ImgDownloadingThread("img_download_thread {}".format(i + 1), img_url_ext_queue, root,
                                                      img_key_word, img_dir, img_num)
        img_downloading_thread_list.append(img_downloading_thread)

    return img_url_ext_retrieving_thread, img_downloading_thread_list


def start_threads(img_url_ext_retrieving_thread, img_downloading_thread_list):
    img_url_ext_retrieving_thread.start()

    for img_downloading_thread in img_downloading_thread_list:
        img_downloading_thread.start()


def join_threads(img_url_ext_retrieving_thread, img_downloading_thread_list):
    img_url_ext_retrieving_thread.join()

    for img_downloading_thread in img_downloading_thread_list:
        img_downloading_thread.join()


def baidu_img_spider(img_key_word, root, img_num):
    # makes a dir to store imgs
    img_dir = make_img_dir(root, img_key_word)

    # generates the url showing images
    url = generate_url(img_key_word)

    # loads images
    li_tags = load_imgs(url, img_num)

    # creates a queue for storing (url of the image, extension of the image)
    img_url_ext_queue = queue.Queue()

    print("start downloading imgs")

    # creates a thread for retrieving (url of the image, extension of the image) from each li tag
    # and some threads for downloading images using the image urls
    img_url_ext_retrieving_thread, img_downloading_thread_list = create_threads(li_tags, img_url_ext_queue, root,
                                                                                img_key_word, img_dir, img_num)
    # starts the threads
    start_threads(img_url_ext_retrieving_thread, img_downloading_thread_list)

    # joins the threads
    join_threads(img_url_ext_retrieving_thread, img_downloading_thread_list)

    global count
    print("done. {} imgs are downloaded".format(count))


if __name__ == '__main__':
    # counts how many images are saved
    count = 0
    # creates a lock to ensure that the count var is modified only by one thread at a time
    count_lock = threading.Lock()

    parser = argparse.ArgumentParser(description="baidu_img_spider - a baidu image spider")
    parser.add_argument("--key-word", "-k", action="store", required=True, help="key word of images")
    parser.add_argument("--number", "-n", action="store", default=300, type=int,
                        help="number of images to be scratched, 300 by default")
    parser.add_argument("--save-dir", "-d", action="store", default=os.getcwd(),
                        help="directory for storing images, current directory by default")

    args = parser.parse_args()

    baidu_img_spider(args.key_word, args.save_dir, args.number)
