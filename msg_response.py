# -*- encoding: utf-8 -*-

import os.path
import json, re, numpy, jieba
import jieba.analyse
import mysql.connector, gensim
from sklearn.externals import joblib
from collections import OrderedDict

class TextMining:
    def __init__(self,file_name):
        self.keyword_dict = None
        self.file_name = file_name
        self.key_dict = self.get_keyword_dict()
    def get_keyword_dict(self,refresh=False):
        if self.keyword_dict == None or refresh == True:
            if os.path.isfile(self.file_name):
                with open(self.file_name,'r') as infile:
                    keyword_file = json.load(infile, object_pairs_hook=OrderedDict)
                self.keyword_dict = keyword_file
            else:
                print self.file_name+" doesn't exist"
                return 
        return self.keyword_dict
    def _make_ML_X(self,msg_list,print_out=False):
        #key_dict = self.get_keyword_dict()
        ML_X = []
        for msg in msg_list:
            tmp = []
            has_url = 1 if len(re.findall("(?P<url>https?://[^\s]+)", msg))>0 else 0
            msg_len = len(msg)
            tmp.append(has_url)
            tmp.append(msg_len)
            if print_out:
                print 'has_url : ',has_url
                print 'msg_len : ',msg_len
            for k in self.key_dict:
                message_jieba = jieba.analyse.extract_tags(msg,0)
                match = list(set(message_jieba).intersection(self.key_dict[k]))
                if print_out:
                    print 'match '+k+' : ',','.join(match)
                tmp.append(len(match))
            ML_X.append(tmp)
        return ML_X


class Msg_response():

    def __init__(self):
        self.origin_data, self.gov_data = self.connect_sql()
        self.clf = joblib.load('./archive/classifier_lg_model.pkl')
        self.tf_idf = None
        self.dictionary = None
        self.sims = None

    def connect_sql(self):#連結資料庫

        try:
            cnx = mysql.connector.connect(user='root', password='rumor5566',
                                      host='140.118.109.32',
                                      port='6603',
                                      database='ml')
            gov_data = []
            origin_data = []
            cursor = cnx.cursor()
            query = ("SELECT content,original FROM data")#選取資料庫欄位
            cursor.execute(query)
            for content,original in cursor:
                gov_data.append(content)  #政府澄清文
                origin_data.append(original)  #謠言原文
            cursor.close()
            cnx.close()
            print("Connecting MySQL Successful!!!")
            return origin_data, gov_data
        except:
            print("Connecting MySQL fail!!!")
            return 0

    def setup(self):  #jieba setup
        jieba.set_dictionary("./archive/dict.txt.big")
        jieba.analyse.set_stop_words("./archive/stop_words.txt")
        jieba.analyse.set_idf_path('./archive/idf.txt.big')
        print(" jieba setup OK !!")

    def data_prepare(self):  #compare text prepare  gov_original_message preprocessing
        seg_list2=[]
        for index in range(len(self.origin_data)):
            seg_list = jieba.analyse.extract_tags(self.origin_data[index], 100)	#取得前100個keyword 並去掉stopword
            seg_list2.append(seg_list)#斷詞加入list
        self.dictionary = gensim.corpora.Dictionary(seg_list2)
        corpus = [self.dictionary.doc2bow(gen_doc) for gen_doc in seg_list2]
        self.tf_idf = gensim.models.TfidfModel(corpus)
        self.sims = gensim.similarities.Similarity('./json_data/', self.tf_idf[corpus], num_features = len(self.dictionary))


    def msg_predict(self, msg):   #define message information type

        #msg 放預分割字串 
        text_min = TextMining('archive/keyword_2.json')
        # Transforming string to numerical feature vector
        msg_feature_vector = text_min._make_ML_X([msg])

        # Loading trained machine learning model
        #clf = joblib.load('archive/classifier_lg_model.pkl')

        # Predicting the class of feature vector
        msg_class = self.clf.predict(msg_feature_vector)

        # 0 : chat 
        # 1 : objective information 
        # 2 : subjective information
        return int(msg_class[0])


    def compare(self, original_data): #original_data需放入欲比對的字串

        #doc = jieba.analyse.extract_tags(original_data, 100)
        doc_bow = self.dictionary.doc2bow(jieba.analyse.extract_tags(original_data, 100))
        doc_tf_idf = self.tf_idf[doc_bow]
        result = numpy.argmax(self.sims[doc_tf_idf])
        return result, self.sims[doc_tf_idf][result] * 100  #回傳匹配結果
