import datetime
from agentapp.model_select import get_model, getTrainingModel, getResponseModel
import json
import logging 
import csv
from flask import current_app
import pandas as pd

# [START build_service]
from google.cloud import datastore
from google.cloud import storage
import google

class tickets_learner(object):

    def __init__(self):
        self.client = datastore.Client()
        self.storage_client = storage.Client()
    # [END build_service]
    
    def extractTrainingData(self, cust_id):   
        logging.info ('extractTrainingData : ')
        next_page_token = 0
        token = None        
        from agentapp.IntentExtractor import IntentExtractor
        intenteng = IntentExtractor()
        while next_page_token != None:             
            ticket_logs, next_page_token = get_model().list('tickets', cursor=token, cust_id='')
            token = next_page_token
            for ticket_log in ticket_logs: 
                tickets_data = ticket_log["json_data"] 
                tickets_data_json = json.loads(tickets_data)
                for ticket_data in tickets_data_json['tickets']: 
                    description = ticket_data['description']
                    subject = ticket_data['subject']
                    tags = ', '.join(ticket_data['tags']) 
                    #print (str(subject + ' . ' + description + ' . ' + tags))
                    predicted = intenteng.getPredictedIntent(str(subject + ' . ' + description + ' . ' + tags) , cust_id)  
                    if len(predicted) < 1: 
                        predicted = ['Default']
                    getTrainingModel().create(tags, str(subject + ' . ' + description), '', 'true', '', resp_category=predicted[0], cust_id=cust_id)
    
    def getTrainingData(self, cust_id):   
        logging.info ('getTrainingData : ')
        ticket_data = []
        next_page_token = 0
        token = None
        while next_page_token != None:             
            ticket_logs, next_page_token = getTrainingModel().list_all(cursor=token, cust_id=cust_id)
            token = next_page_token
            ticket_data.append(ticket_logs)
        return ticket_data 
    
    def import_trainingdata(self, cust_id): 
        logging.info ('import_trainingdata : ')
        with open(current_app.config['TRAIN_SET_PATH'], 'r', encoding='windows-1252') as f:
            reader = csv.reader(f)
            train_list = list(reader)
        rid = 100
        while rid < 200: 
            for linestm in train_list:
                getTrainingModel().create(linestm[0].strip(), linestm[1].strip(), '', 'true', resp_category=linestm[2].strip(), id=rid, cust_id=cust_id)
                rid += 1
            
    def import_responsedata(self, cust_id): 
        logging.info ('import_responsedata : ')
        with open(current_app.config['CANNED_RESP_PATH'], 'r', encoding='windows-1252') as f:
            reader = csv.reader(f)
            train_list = list(reader)
        rid = 100
        for linestm in train_list:
            getResponseModel().create(linestm[0].strip(), linestm[0].strip(), linestm[1].strip(), linestm[2].strip(), id=rid, cust_id=cust_id)
            rid += 1
            
    def get_response_mapping(self, response, cust_id):
        logging.info ('get_response_mapping : ')
        ds_response = getResponseModel().list(cust_id=cust_id)
        print ( 'ds_response : '+str(ds_response)) 
        
        for resp in ds_response: 
            if (resp != None) and (len(resp) > 0) :
                return resp[0]
        return None
    
    def format_output(self, predicted_intent): 
        logging.info ('format_output : ')
        comments_struct = []    
        with open(current_app.config['CANNED_RESP_PATH'], 'r', encoding='windows-1252') as f:
            reader = csv.reader(f)
            resp_list = list(reader)
        resp_dict = {rows[0].strip() : rows[1] for rows in resp_list}
        y_predict_dic = sorted(predicted_intent.items(), key=lambda x: x[1], reverse=True)
        i = 0
        for ss in y_predict_dic:
            comments_struct.append({'id': list(resp_dict.keys()).index(ss[0].strip()), 'name' : ss[0], 'comment': resp_dict.get(ss[0].strip(), ''), 'prob': int(ss[1]*100)})
            if (i >= 4):
                break
            i+=1
        return comments_struct
    
    def format_output_ds(self, predicted_intent, cust_id): 
        logging.info ('format_output_ds : ')
        tickets_learn = tickets_learner()
        comments_struct = []  
        df_intent = pd.DataFrame(list(predicted_intent.items()), columns=['Resp_Class', 'Resp_Prob'])
        df_intent = df_intent.sort_values(['Resp_Prob'], ascending=[False])
        df_intent['Comment'] = 'NA'
        ds_response = getResponseModel().list(cust_id=cust_id) 
        i = 0
        for index, row in df_intent.iterrows():
            for resp_list in ds_response: 
                if (resp_list != None) and (len(resp_list) > 0) :
                    for resp_item in resp_list:
                        if resp_item['resp_name'] == row['Resp_Class']: 
                            comments_struct.append({'id': resp_item['id'], 'name' : resp_item['resp_name'], 'comment': resp_item['response_text'], 'prob': int(row['Resp_Prob']*100)}) 
            if (i >= 4):
                break
            i+=1        
        return comments_struct  

    def get_bucket(self, cust_id):
        print('get_bucket:')         
        try:
            bucket = self.storage_client.get_bucket(current_app.config['STORAGE_BUCKET']) 
            m_blob = bucket.get_blob(cust_id + '_model.pkl')
            file = m_blob.download_as_string()
            return file
        except google.cloud.exceptions.NotFound:
            print('Sorry, that bucket does not exist!')        
        return None
        
    def put_bucket(self, file, cust_id):
        print('put_bucket:')
        try:
            bucket = self.storage_client.get_bucket(current_app.config['STORAGE_BUCKET'])
            filename = cust_id + '_model.pkl'
            m_blob = bucket.blob(filename)            
            m_blob.upload_from_string(file)
        except google.cloud.exceptions.NotFound:
            print('Sorry, that bucket does not exist!')        
        #print('Blob created.')
        return file
        
    def create_bucket(self):
        print('create_bucket:')
        try:
            bucket = self.storage_client.lookup_bucket(current_app.config['STORAGE_BUCKET'])
            if bucket == None: 
                bucket = self.storage_client.create_bucket(current_app.config['STORAGE_BUCKET'])
        except google.cloud.exceptions.Conflict:
            print('Sorry, that bucket was not created!')        
        logging.info('Bucket created.')
    