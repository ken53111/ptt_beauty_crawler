#!/usr/bin/env python
#-*- coding: utf-8 -*-

import requests
import re
import sys
import os
import argparse
from bs4 import BeautifulSoup
from datetime import datetime

ptt_url = "https://www.ptt.cc/bbs/Beauty/index.html"
ptt_host = "https://www.ptt.cc"
ptt_from = ""
save_directory = "tmp"
start_time = ""
end_time = ""
like_restriction = 7

CHUNK_SIZE = 32768
page_count = 10

def get_ptt_from() :
    global ptt_from
    regx = re.compile(ptt_host + "(.+)")
    regx_result = regx.findall(ptt_url)
    ptt_from = regx_result[0]
    print ptt_from

def need_over_18_confirm(dom) :
    if dom.find("我同意，我已年滿十八歲") != -1 :
        get_ptt_from()
        return True
    else :
        return False

def get_article_list(session) :
    response = session.get(ptt_url)
    
    dom = response.text
    
    if need_over_18_confirm(dom) :
        soup = BeautifulSoup(dom, "html5lib")
        forms = soup.find_all('form')
    
        action = forms[0].get('action')
        
        #Over 18 confirm
        response = session.post(ptt_host + action, {"yes": "yes", "from": ptt_from})
        
        dom = response.text
    
    return dom

def get_articles(dom) :
    soup = BeautifulSoup(dom, "html5lib")
    divs = soup.find_all('div', "r-ent")
    articles = []
    
    for div in divs :
        likes = 0
        span = div.find('span')
        if span != None :
            if span.get_text() == u'爆' :
                likes = 100
            else :
                try :
                    likes = int(span.get_text())
                except :
                    print "Failed to get like count"
                
        a = div.find('a')
        if a != None :
            if likes >= like_restriction :
                articles.append({'topic': a.get_text(), 'link': a["href"]})
            
    return articles

def save_html(article_name, html, directory) :
    f = open(os.path.join(directory, article_name) + ".html", "w")
    f.write(html.decode("utf-8"))
    f.close()
    
def create_directory(folder_name) :
    directory = os.path.join(save_directory, folder_name)
    if not os.path.exists(directory) :
        os.makedirs(directory)
    return directory

def get_picture_name_from_url(url) :
    file_name_start = url.rfind("/") + 1
    return url[file_name_start:]    
    

def request_picture_and_save(picture_url_list, directory) :
    #headers  = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36"}
    for url in picture_url_list :
        print "Downloading: " + url
        try :
            response = requests.get(url)
        except :
            print "Failed to download image: " + url

        if response.status_code == 200 :
            f = open(os.path.join(directory, get_picture_name_from_url(url)), "wb")
            f.write(response.content)
            f.close()

def save_picture(html, directory) :
    soup = BeautifulSoup(html, "html5lib")
    a_list = soup.find_all('a')
    picture_url_list = []
    
    regx = re.compile(".+\.jpg")
    
    for a in a_list :
        regx_result = regx.findall(a['href'])
        if regx_result != [] :
            print "Picture : " + regx_result[0]
            picture_url_list.append(regx_result[0])
            
    request_picture_and_save(picture_url_list, directory)
        
    
    
def save_article(session, a, time_range_dictionary) :
    topic = re.sub(r"[?\\/:<>|\. ]", "", a['topic'])
    
    response = session.get(ptt_host + a['link'])
    html = response.text
    
    if html.find("404 - Not Found.") == -1 :
        date = get_article_time(html)
        
        if is_article_in_range(date, time_range_dictionary) :
            directory = create_directory(topic)
            save_html(topic, html, directory)
            save_picture(html, directory)
    
def get_article_time(html) :
    soup = BeautifulSoup(html, "html5lib")
    span = soup.find_all('span', 'article-meta-value')
    regx = re.compile("[:a-zA-Z0-9]+")
    
    if span != [] :
        time_string = span[-1].get_text()
        regx_result = regx.findall(time_string)
        if regx_result != [] :
            try :
                date_object = datetime.strptime(time_string, "%a %b %d %H:%M:%S %Y")
                return date_object
            except :
                return None
        
def time_range(time_start, time_end) :
    time_format = "%Y/%m/%d"
    date_start = datetime.strptime(time_start, time_format)
    date_start = date_start.replace(hour = 0, minute = 0, second = 0)
    date_end = datetime.strptime(time_end, time_format)
    date_end = date_end.replace(hour = 23, minute = 59, second = 59)
    
    return {'start': date_start, 'end': date_end}

def is_article_in_range(date, time_range_dictionary) :
    if date != None :
        if (date > time_range_dictionary['start']) and (date < time_range_dictionary['end']) :
            return True
    return False

def get_prev_page(dom) :
    soup = BeautifulSoup(dom, "html5lib")
    a = soup.find(name="a", text="‹ 上頁")
    
    return ptt_host + a['href']

def parse_arguments() :
    parser = argparse.ArgumentParser(description='Download web pages and images from ptt.')
    parser.add_argument("-d", "--save_directory", nargs = 1, help = "Directory you want to save data(default: ./tmp)")
    parser.add_argument("-u", "--url", nargs = 1, help = "Url which contents articles")
    parser.add_argument("-s", "--start_day", nargs = 1, help = "Article posted between start_day and end_day would be downloaded")
    parser.add_argument("-e", "--end_day", nargs = 1, help = "Article posted between start_day and end_day would be downloaded")
    parser.add_argument("-c", "--page_count", nargs = 1, type = int, help = "How many pages you want to traverse")
    parser.add_argument("-l", "--like_restriction", nargs = 1, type = int, help = "Number of likes")
    args = parser.parse_args()
    return vars(args)

def init_arguments(args) :
    global ptt_url, start_time, end_time, page_count, save_directory, like_restriction
    
    if args['url'] != None :
        ptt_url = args['url'][0]

    if args['save_directory'] != None :
        save_directory = args['save_directory'][0]
        
    if args['start_day'] != None :
        start_time = args['start_day'][0]
    else :
        start_time = datetime.now().strftime("%Y/%m/%d")        
        
    if args['end_day'] != None :
        end_time = args['end_day'][0]
    else :
        end_time = datetime.now().strftime("%Y/%m/%d")
        
    if args['page_count'] != None :
        page_count = args['page_count'][0]
    
    if args['like_restriction'] != None :
        like_restriction = args['like_restriction'][0]

def main() :
    reload(sys)
    sys.setdefaultencoding('utf-8')
    
    init_arguments(parse_arguments())
    
    session = requests.Session()
    traversed_page = 0
    
    dom = get_article_list(session)
    
    while traversed_page < page_count :
        articles = get_articles(dom)
        
        time_range_dictionary = time_range(start_time, end_time)
    
        for a in  articles:
            try :
                print a['topic'] + ": " + a['link']
            except :
                print "Failed to print topic"
            save_article(session, a, time_range_dictionary)
        
        dom = session.get(get_prev_page(dom)).text
        traversed_page += 1       

if __name__ == "__main__" :
    main()