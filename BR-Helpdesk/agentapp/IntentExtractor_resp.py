from gensim.models.word2vec import Word2Vec 
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.pipeline import Pipeline
from agentapp.UtilityClass import UtilityClass
from agentapp.UtilityClass_spacy import UtilityClass_spacy
import re 
import numpy as np
from pandas_ml import ConfusionMatrix 
from sklearn.metrics import  f1_score, precision_score, recall_score
import csv
from collections import defaultdict
from agentapp.model_select import get_model, getTrainingModel, getResponseModel, getCustomerModel
from agentapp.tickets_learner import tickets_learner
from flask import current_app
import logging
#from sklearn.naive_bayes import MultinomialNB
from sklearn.svm import SVC
from sklearn.linear_model import LogisticRegression
import nltk
nltk.download('stopwords')
from nltk.tokenize import RegexpTokenizer
from nltk.corpus import stopwords
from agentapp.tickets_learner import tickets_learner
import pickle
from agentapp.TfidfVectorizer import TfidfEmbeddingVectorizer, MeanEmbeddingVectorizer
import pandas as pd
class IntentExtractor_resp(object): 
    def __init__(self):
        self.utilclass = UtilityClass()
        self.utilspace = UtilityClass_spacy()

    def prepareTrainingData(self, cust_id):
        logging.info("prepareTrainingData : Started " + str(cust_id))
        self.X, self.y = [], []        
        tickets_learn = tickets_learner()
        ticket_data = tickets_learn.getResponseData(cust_id=cust_id)
        lang = getCustomerModel().getLanguage(cust_id)
        xX = []
        yY = []
        for linestms in ticket_data:           
            for linestm in linestms:
                tempxX = linestm['tags'].strip()
                if (tempxX != ''):
                    strx = str(linestm['tags']).strip()
                    strx = self.utilspace.preprocessText(strx, lang=lang, ner=True)
                    strx = str(self.utilclass.cleanData(strx, lang=lang, lowercase=True, remove_stops=True, tag_remove=True))               
                    xX.append(strx.strip().split())
                    yY.append(str(linestm['res_category']).strip())
        self.X = xX
        self.y = yY
        
        self.X, self.y = np.array(self.X, dtype=object), np.array(self.y, dtype=object)
        logging.info ("Total Training Examples : %s" % len(self.y))
        logging.info("prepareTrainingData : Completed " + str(cust_id))
        return
            
    def startTrainingProcess(self, cust_id):
        logging.info("startTrainingProcess : Started " + str(cust_id))
        if len(self.y) < 1: 
            logging.info('Cant process as no Training ')
            return
        self.model = Word2Vec(self.X, size=100, window=5, min_count=1, workers=3)
        self.model.wv.index2word
        w2v = {w: vec for w, vec in zip(self.model.wv.index2word, self.model.wv.syn0)}
        #self.etree_w2v_tfidf = Pipeline([("word2vec vectorizer", MeanEmbeddingVectorizer(w2v)), 
        #                ("extra trees", ExtraTreesClassifier(n_estimators=200))])
        #self.etree_w2v_tfidf = Pipeline([("word2vec vectorizer", TfidfEmbeddingVectorizer(w2v)), 
        #                ("MultinomialNB", MultinomialNB())])
        #self.etree_w2v_tfidf = Pipeline([("word2vec vectorizer", MeanEmbeddingVectorizer(w2v)), 
        #               ("SVC", LogisticRegression(random_state=0))]) 
        self.etree_w2v_tfidf = Pipeline([("word2vec vectorizer", MeanEmbeddingVectorizer(w2v)), 
                       ("SVC", SVC(kernel='linear', probability=True))])
        self.etree_w2v_tfidf.fit(self.X, self.y)
        
        logging.info ("Total Training Samples : %s" % len(self.y))
        logging.info("startTrainingProcess : Completed " + str(cust_id))
        return
        
    def getPredictedIntent(self, textinput, cust_id): 
        logging.info("getPredictedIntent : Started " + str(cust_id))
        if len(self.y) < 1: 
            logging.info('Cant process as no Training ')
            return
        self.test_X = []
        lang = getCustomerModel().getLanguage(cust_id)
        strx = self.utilclass.cleanData(textinput, lang=lang, lowercase=True, remove_stops=True, tag_remove=True)
        #strx = self.utilspace.preprocessText(strx)
        self.test_X.append(strx.strip().split())
        self.predicted = []
        try:
            self.predicted = self.etree_w2v_tfidf.predict(self.test_X) 
        except ValueError as err: 
            logging.error('getPredictedIntent : ' +  str(err))
        logging.info("getPredictedIntent : Completed " + str(cust_id))
        return self.predicted
    
    def getPredictedIntent_list(self, X_in, cust_id): 
        logging.info("getPredictedIntent_list : Started " + str(cust_id))
        
        self.lang = getCustomerModel().getLanguage(cust_id)
        X_in = X_in.apply(lambda x : self.utilclass.cleanData(x, lang=lang, lowercase=True, remove_stops=True, tag_remove=True).strip().split())
        X_list = X_in.tolist()
        predicted_list= []
        try:
            predicted_list = self.etree_w2v_tfidf.predict(X_list) 
        except ValueError as err: 
            logging.error('getPredictedIntent_list : ' + str(err))            
        predict_df = pd.Series(predicted_list)
        logging.info("getPredictedIntent_list : Completed " + str(cust_id))
        return predict_df
    
    def startTrainLogPrediction(self, cust_id):
        logging.info("startTrainLogPrediction : Started " + str(cust_id))
        if len(self.y) < 1: 
            logging.info('Cant process as no Training ')
            return
        traindata = getTrainingModel() 
        next_page_token = 0
        token = None 
        while next_page_token != None:             
            training_logs, next_page_token = traindata.list(cursor=token, feedback_flag=False, cust_id=cust_id)
            token = next_page_token
            for training_log in training_logs: 
                strx = training_log['tags']  + ' . ' + training_log['query'] 
                predicted = self.getPredictedIntent(strx, cust_id)  
                if len(predicted) < 1: 
                    predicted = ['Default']
                traindata.update(training_log['tags'], training_log['query'], training_log['response'], query_category=training_log['query_category'], 
                    done=True, id = training_log['id'], resp_category=predicted[0], cust_id=cust_id)
                print ('processing training data :', training_log['id'])

        logging.info("startTrainLogPrediction : Completed " + str(cust_id))