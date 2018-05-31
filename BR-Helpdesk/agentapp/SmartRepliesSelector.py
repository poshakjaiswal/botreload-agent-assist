from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score
import logging
from agentapp.tickets_learner import tickets_learner
from nltk.tokenize import RegexpTokenizer
import numpy as np
from nltk.corpus import stopwords
import pandas as pd 
from sklearn.metrics import pairwise_distances_argmin_min
from agentapp.model_select import get_model, getTrainingModel, getResponseModel, getCustomerModel
import re
class SmartRepliesSelector(object):

    def prepareTrainingData(self, cust_id):
        logging.info("prepareTrainingData : Started : " + str(cust_id))
        ticket_data = self.getTrainingData(cust_id=cust_id)
    
        ticket_struct = []
        for linestms in ticket_data:           
            for linestm in linestms:
                if linestm['response'].strip() != '':
                    ticket_struct.append({'id' : linestm['id'], 'query' : linestm['query'], 'response': linestm['response'], 'tags' : linestm['tags']})
        self.ticket_pd = pd.DataFrame(ticket_struct)
        logging.info ("Total Training Examples : %s" % len(self.ticket_pd))
        logging.info("prepareTrainingData : Started : " + str(cust_id))
        return 
    
    def generateNewResponse(self, cust_id):
        logging.info('generateNewResponse : Started : ' + str(cust_id))
        self.prepareTrainingData(cust_id)
        X_q = self.ticket_pd['query']
        query_clstr_itr = int (len(X_q) / 10) 
        print ('Query Cluster Size : ', query_clstr_itr)
        self.ticket_pd['query_cluster'], _, self.ticket_pd['select_tags'] = self.getKMeanClusters(cust_id, X_q, query_clstr_itr)
        self.ticket_pd['response_cluster'] = -1
        self.ticket_pd['select_response'] = np.nan
        if (query_clstr_itr > 1): 
            for x in range (0, 10): 
                query_sub = self.ticket_pd[self.ticket_pd.query_cluster == x]            
                resp_clst_itr = int(len(query_sub) / 5)
                print ('Response Cluster Size : ',resp_clst_itr)                 
                if resp_clst_itr > 1:
                    query_sub['response_cluster'], query_sub['select_response'], ___ = self.getKMeanClusters(cust_id, query_sub['response'], resp_clst_itr) 
                    for index, items in query_sub.iterrows(): 
                        self.ticket_pd.loc[(self.ticket_pd['id'] == items['id']), 'response_cluster'] = int (items['response_cluster'])
                        self.ticket_pd.loc[(self.ticket_pd['id'] == items['id']), 'select_response'] = items['select_response']
        logging.info('generateNewResponse : Completed : ', cust_id)
        return 
    
    def populateResponseData(self, cust_id): 
        logging.info ('getTrainingData : started ' + str(cust_id))
        resp_model = getResponseModel()
        next_page_token = 0
        token = None
        while next_page_token != None:             
            ticket_logs, next_page_token = resp_model().list(cursor=token, cust_id=cust_id, done=True)
            token = next_page_token
            for resp_log in resp_logs:
                resp_model.delete(resp_log['id'], cust_id)
        
        for index, item in self.ticket_pd.iterrows():             
            if item['select_response'] == 'true': 
                resp_model.create((cust_id + '_Response_' + str(index)), (cust_id + '_Response_' + str(index)), item['response'], item['select_tags'], done=True, cust_id=cust_id)
        logging.info ('getTrainingData : Completed ' + str(cust_id))
        return
    
    def getKMeanClusters(self, cust_id, X_in, true_k):
        logging.info("getKMeanClusters : " + str(cust_id))
        selected_resp = []
        selected_tags = []
        prediction = []
        vectorizer = TfidfVectorizer(stop_words='english')
        try:
            X = vectorizer.fit_transform(X_in)
        except ValueError as err: 
            logging.error("getKMeanClusters : " , err)
            return prediction, selected_resp, selected_tags
        model = KMeans(n_clusters=true_k, init='k-means++', max_iter=100, n_init=1)
        model.fit(X)  
        prediction = model.predict(X)
         
        closest, _ = pairwise_distances_argmin_min(model.cluster_centers_, X)
        
        order_centroids = model.cluster_centers_.argsort()[:, ::-1]
        terms = vectorizer.get_feature_names()
        tags_clurt = []
        for i in range(true_k):
            tags_temp = []
            for ind in order_centroids[i, :10]:
                tags_temp.append(terms[ind])
            tags_clurt.append(tags_temp)
        
        closest = closest.tolist()
        input_x = X_in.tolist()
        for i in range(len(prediction)):  
            qtags = '' 
            for resp_tags in tags_clurt[prediction[i]]:
                if resp_tags in input_x[i]:
                    qtags += resp_tags + ' '
            selected_tags.append(qtags.strip())
            if i in closest:  
                selected_resp.append('true')
            else :
                selected_resp.append('false')
        return prediction, selected_resp, selected_tags 
    
    def getTrainingData(self, cust_id):   
        logging.info ('getTrainingData : ' + str(cust_id))
        ticket_data = []
        next_page_token = 0
        token = None
        while next_page_token != None:             
            ticket_logs, next_page_token = getTrainingModel().list_all(cursor=token, cust_id=cust_id, done=False)
            token = next_page_token
            ticket_data.append(ticket_logs)
        return ticket_data 
