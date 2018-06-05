from gensim.models.word2vec import Word2Vec 
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.pipeline import Pipeline
import re 
import numpy as np
from pandas_ml import ConfusionMatrix 
from sklearn.metrics import  f1_score, precision_score, recall_score
import csv
from collections import defaultdict
from agentapp.model_select import get_model, getTrainingModel, getResponseModel
from agentapp.tickets_learner import tickets_learner
from flask import current_app
import logging
#from sklearn.naive_bayes import MultinomialNB
from sklearn.svm import SVC
from agentapp.StorageOps import StorageOps
import nltk
nltk.download('stopwords')
from nltk.tokenize import RegexpTokenizer
from nltk.corpus import stopwords
from agentapp.tickets_learner import tickets_learner
import pickle
from agentapp.TfidfVectorizer import TfidfEmbeddingVectorizer, MeanEmbeddingVectorizer

class IntentExtractor(object): 
    
    def prepareTrainingData(self, cust_id):
        logging.info("prepareTrainingData : Started " + str(cust_id))
        self.X, self.y = [], []
        
        tickets_learn = tickets_learner()
        ticket_data = tickets_learn.getTrainingData(cust_id=cust_id)
    
        xX = []
        yY = []
        for linestms in ticket_data:           
            for linestm in linestms:
                tempxX = preprocess(str(linestm['tags'] + ', ' + linestm['query'])).strip()
                if (tempxX != ''):
                    xX.append(tempxX.split())
                    yY.append(linestm['resp_category'].strip())
        self.X = xX
        self.y = yY
        
        self.X, self.y = np.array(self.X, dtype=object), np.array(self.y, dtype=object)
        logging.info ("Total Training Examples : %s" % len(self.y))
        logging.info ("prepareTrainingData : Completed " + str(cust_id))
        return
    
    def startTrainingProcess(self, cust_id):
        storageOps = StorageOps()
        logging.info("startTrainingProcess : Started " + str(cust_id))
        if len(self.y) < 1: 
            logging.info('Cant process as no Training ')
            return
        self.model = Word2Vec(self.X, size=100, window=5, min_count=1, workers=3)
        self.model.wv.index2word
        w2v = {w: vec for w, vec in zip(self.model.wv.index2word, self.model.wv.syn0)}
        '''self.etree_w2v_tfidf = Pipeline([("word2vec vectorizer", MeanEmbeddingVectorizer(w2v)), 
                        ("extra trees", ExtraTreesClassifier(n_estimators=200))])
        self.etree_w2v_tfidf = Pipeline([("word2vec vectorizer", TfidfEmbeddingVectorizer(w2v)), 
                        ("MultinomialNB", MultinomialNB())])'''
        self.etree_w2v_tfidf = Pipeline([("word2vec vectorizer", MeanEmbeddingVectorizer(w2v)), 
                        ("SVC", SVC(kernel='linear', probability=True))])
        self.etree_w2v_tfidf.fit(self.X, self.y)
        
        pickle_out = pickle.dumps(self.etree_w2v_tfidf)
        storageOps.put_bucket(pickle_out, cust_id) 
                
        logging.info ("Total Training Samples : %s" % len(self.y))
        logging.info("startTrainingProcess : Completed " + str(cust_id))
        return
        
    def getIntentForText(self, textinput, cust_id): 
        logging.info("getIntentForText : Started " + str(cust_id))
        storageOps = StorageOps()
        pickle_out = storageOps.get_bucket(cust_id)
        self.etree_w2v_tfidf = pickle.loads(pickle_out)
        self.test_X = []
        self.test_X.append(preprocess(textinput).split())
        #self.predicted = self.etree_w2v_tfidf.predict(self.test_X) 
        #print (self.test_X)
        self.predicted_prob = []
        self.y_predict_dic = {}
        try:
            self.predicted_prob = self.etree_w2v_tfidf.predict_proba(self.test_X)  
            self.y_predict_dic = dict(zip(self.etree_w2v_tfidf.classes_, self.predicted_prob[0]))
        except ValueError as err: 
            logging.error(str(err)) 
        logging.info("getIntentForText : Completed " + str(cust_id))      
        return self.y_predict_dic
        
    def getPredictedIntent(self, textinput, cust_id): 
        logging.info("getPredictedIntent : Started " + str(cust_id))
        storageOps = StorageOps()
        pickle_out = storageOps.get_bucket(cust_id)
        self.etree_w2v_tfidf = pickle.loads(pickle_out)
        self.test_X = []
        self.test_X.append(preprocess(textinput).split())
        self.predicted = []
        try:
            self.predicted = self.etree_w2v_tfidf.predict(self.test_X) 
        except ValueError as err: 
            logging.error(str(err))
        logging.info("getPredictedIntent : Completed " + str(cust_id))
        return self.predicted
    
    def startTrainLogPrediction(self, cust_id):
        logging.info ('startTrainLogPrediction : Started : ' + str(cust_id))
        traindata = getTrainingModel() 
        next_page_token = 0
        token = None 
        while next_page_token != None:             
            training_logs, next_page_token = traindata.list(cursor=token, cust_id=cust_id, feedback_flag=False, done=False)
            token = next_page_token
            for training_log in training_logs: 
                predicted = self.getPredictedIntent(str(training_log['query'] + ' . ' + training_log['tags']) , cust_id)  
                if len(predicted) < 1: 
                    predicted = ['Default']
                traindata.update(training_log['tags'], training_log['query'], training_log['response'], query_category=training_log['query_category'], 
                    done=True, id = training_log['id'], resp_category=predicted[0], cust_id=cust_id)
                print ('processing training data :', training_log['id'])
        logging.info ('startTrainLogPrediction : Completed : ' + cust_id)

    
    def prepareTestingData(self, cust_id):
        logging.info("prepareTestingData : Started " + str(cust_id))        
        self.test_X, self.test_y = [], []
        
        tickets_learn = tickets_learner()
        ticket_data = tickets_learn.getTrainingData(cust_id=cust_id)
    
        xX = []
        yY = []
        for linestms in ticket_data:           
            for linestm in linestms:
                logging.debug (str(linestm['tags'] + ', ' + linestm['query']) + " =>  " + linestm['response'])
                xX.append(preprocess(str(linestm['tags'] + ', ' + linestm['query'])).strip().split())
                yY.append(linestm['resp_category'].strip()) 
        self.test_X = xX
        self.test_y = yY
       
        self.test_X, self.test_y = np.array(self.test_X, dtype=object), np.array(self.test_y, dtype=object)
        logging.info ("Total Testing Examples : %s" % len(self.test_y))
        logging.info("prepareTestingData : Completed " + str(cust_id)) 
        return 

    def startTestingProcess(self, cust_id): 
        logging.info("startTestingProcess : Started " + str(cust_id)) 
        storageOps = StorageOps()
        pickle_out = storageOps.get_bucket(cust_id)
        self.etree_w2v_tfidf = pickle.loads(pickle_out)
        self.predicted = self.etree_w2v_tfidf.predict(self.test_X)
        for input_data, output_data in zip(self.test_X, self.predicted) :
            logging.debug (str(input_data) + "  =>  " + str(output_data))
        logging.info ("Total Predicted Testing Examples : %s" % len(self.predicted))
        logging.info("startTestingProcess : Completed " + str(cust_id))
        return 
        
    def createConfusionMatrix(self, cust_id):
        logging.info("createConfusionMatrix : Started " + str(cust_id))
        for y_value_a, y_value_p in zip(self.test_y, self.predicted): 
            logging.info ('\'' + y_value_a + '\' >> \'' + y_value_p + '\'' )
        logging.info("Mean: \n" + str(np.mean(self.test_y == self.predicted)))
        
        cm = ConfusionMatrix(self.test_y, self.predicted)
       
        logging.info("f1_score : " + str(f1_score(self.test_y, self.predicted, average="macro", labels=np.unique(self.predicted))))
        logging.info("precision_score : " + str(precision_score(self.test_y, self.predicted, average="macro", labels=np.unique(self.predicted))))
        logging.info("recall_score : " + str(recall_score(self.test_y, self.predicted, average="macro")))
        logging.info("createConfusionMatrix : Completed " + str(cust_id))
        return 

def preprocess(sentence):
    sentence = sentence.lower()
    tokenizer = RegexpTokenizer(r'\w+')
    tokens = tokenizer.tokenize(sentence)
    filtered_words = [w for w in tokens if not w in stopwords.words('english')]
    return " ".join(filtered_words)