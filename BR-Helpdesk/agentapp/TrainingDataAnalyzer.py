import datetime
from agentapp.model_select import get_model, getTrainingModel, getResponseModel, getCustomerModel
import json
import logging 
import csv
from flask import current_app
import pandas as pd

# [START build_service]
from google.cloud import datastore
from google.cloud import storage
import google
from nltk.tokenize import RegexpTokenizer
import numpy as np
from nltk.corpus import stopwords

class TrainingDataAnalyzer(object):
    
    def __init__(self):
        self.client = datastore.Client()
        self.storage_client = storage.Client()
    
    def copyOldTrainingLog(self):
        logging.info ('copyOldTrainingLog : Starting')        
        trainlog = get_model()
        next_page_token = 0
        token = None
        while next_page_token != None:
            ticket_logs, next_page_token = trainlog.list('tickets', cursor=token, cust_id='', done=True)
            token = next_page_token
            for ticket_log in ticket_logs:
                trainlog.create(ticket_log['type'], ticket_log['json_data'], created=ticket_log['created'], done=True, cust_id='default')
                trainlog.delete(id=ticket_log['id'], cust_id='')
                print ('Copying Ticket data: ' , ticket_log['id'])
        print ('copyOldTrainingLog: Completed ')

    def extractTicketData_default(self, src_cust_id='default'):   
        logging.info ('extractTicketData_default : Started ')
        trainlog = get_model()
        traindata = getTrainingModel() 

        next_page_token = 0
        token = None        
        cust_list, next_page_token2 = getCustomerModel().list(done=True)
        while next_page_token != None:             
            ticket_logs, next_page_token = trainlog.list('tickets', cursor=token, cust_id=src_cust_id, done=True)
            token = next_page_token
            for ticket_log in ticket_logs: 
                tickets_data = ticket_log["json_data"] 
                tickets_data_json = json.loads(tickets_data)
                for ticket_data in tickets_data_json['tickets']: 
                    description = ticket_data['description']
                    subject = ticket_data['subject']
                    tags = ', '.join(ticket_data['tags']) 
                    url = ticket_data['url']             
                    for cust_id_x in cust_list:
                        if cust_id_x['cust_name'] in url:
                            traindata.create(tags, str(subject + ' . ' + description), '', done=False, cust_id=cust_id_x['cust_name'])                            
                            trainlog.delete(ticket_log['id'], cust_id=src_cust_id)
                            print('Creating for Ticket Id : ' , ticket_data['id'], src_cust_id)                            
        logging.info ('extractTicketData_default : Completed ')
    
    def extractTicketData_cust(self, cust_id):   
        logging.info ('extractTicketData_cust : Started')
        trainlog = get_model()
        traindata = getTrainingModel() 

        next_page_token = 0
        token = None        
        cust_list, next_page_token2 = getCustomerModel().list(done=True)
        while next_page_token != None:             
            ticket_logs, next_page_token = trainlog.list('tickets', cursor=token, cust_id=cust_id, done=True)
            token = next_page_token
            for ticket_log in ticket_logs: 
                tickets_data = ticket_log["json_data"] 
                tickets_data_json = json.loads(tickets_data)
                for ticket_data in tickets_data_json['tickets']: 
                    description = ticket_data['description']
                    subject = ticket_data['subject']
                    tags = ', '.join(ticket_data['tags']) 
                    url = ticket_data['url']             
                    traindata.create(tags, str(subject + ' . ' + description), '', done=False, cust_id=cust_id)
                    trainlog.delete(ticket_log['id'], cust_id=cust_id)
                    print('Creating for Ticket Id : ' , ticket_data['id'], cust_id)
        logging.info ('extractTicketData_cust : Completed')
        
    def extractIntentData_default(self, src_cust_id='default'):   
        logging.info ('extractIntentData_default : Started')
        trainlog = get_model()
        traindata = getTrainingModel() 

        next_page_token = 0
        token = None        
        cust_list, next_page_token2 = getCustomerModel().list(done=True)
        while next_page_token != None:             
            intent_logs, next_page_token = trainlog.list('intent', cursor=token, cust_id=src_cust_id, done=True)
            token = next_page_token
            for intent_log in intent_logs: 
                intents_data = intent_log["json_data"] 
                intents_data_json = json.loads(intents_data)
                description = intents_data_json['description']
                subject = intents_data_json['subject']
                tags = ', '.join(intents_data_json['requester']['tags']) 
                cust_id = intents_data_json['currentAccount']['subdomain'] 
                response = ''
                if len(intents_data_json['comments']) > 0:
                    response = intents_data_json['comments'][0]['value']
                    response = preprocess (response)
                for cust_id_x in cust_list:
                    if cust_id_x['cust_name'] == cust_id:
                        traindata.create(tags, str(subject + ' . ' + description), response, done=False, cust_id=cust_id)
                        trainlog.delete(intent_log['id'], cust_id=src_cust_id)
                        print('Creating for Intent : ' , intents_data_json['id'], cust_id)
        logging.info ('extractIntentData_default : Completed')
    
    def extractIntentData_cust(self, cust_id):   
        logging.info ('extractIntentData_cust : Started')
        trainlog = get_model()
        traindata = getTrainingModel() 

        next_page_token = 0
        token = None        
        cust_list, next_page_token2 = getCustomerModel().list(done=True)
        while next_page_token != None:             
            intent_logs, next_page_token = trainlog.list('intent', cursor=token, cust_id=cust_id, done=True)
            token = next_page_token
            for intent_log in intent_logs: 
                intents_data = intent_log["json_data"] 
                intents_data_json = json.loads(intents_data)
                description = intents_data_json['description']
                subject = intents_data_json['subject']
                tags = ', '.join(intents_data_json['requester']['tags']) 
                response = ''
                if len(intents_data_json['comments']) > 0:
                    response = intents_data_json['comments'][0]['value']
                    response = preprocess (response)
                traindata.create(tags, str(subject + ' . ' + description), response, done=False, cust_id=cust_id)
                trainlog.delete(intent_log['id'], cust_id=cust_id)
                print('Creating for Intent : ' , intents_data_json['id'], cust_id)
        logging.info ('extractIntentData_cust : Completed')  
    
    def extractTicketData_new(self, cust_id):   
        logging.info ('extractTrainingData : Started')
        trainlog = get_model()
        traindata = getTrainingModel() 

        next_page_token = 0
        token = None        
        while next_page_token != None:             
            ticket_logs, next_page_token = trainlog.list('tickets', cursor=token, cust_id=cust_id, done=True)
            token = next_page_token
            for ticket_log in ticket_logs: 
                tickets_data = ticket_log["json_data"] 
                tickets_data_json = json.loads(tickets_data)
                for ticket_data in tickets_data_json['upload_ticket_data']: 
                    comments = ''
                    for comment_data in tickets_data_json['upload_comment_data']:
                        if (comment_data['id'] == ticket_data['id']):
                            try:
                                comments = comment_data['comments'][1]['plain_body']
                            except IndexError as err: 
                                logging.debug('')
                    comments = preprocess (comments)
                    description = ticket_data['description']
                    subject = ticket_data['subject']                    
                    tags = ', '.join(ticket_data['tags']) 
                    traindata.create(tags, str(subject + ' . ' + description), comments, done=False, resp_category=predicted[0], cust_id=cust_id)
                    trainlog.delete(ticket_log['id'], cust_id=cust_id)
                    print('Creating for Tickets : ' , intents_data_json['id'], cust_id)
        logging.info ('extractTrainingData : Completed ')
        
    def applyPrediction(self, cust_id):
        logging.info ('applyPrediction : Started')
        trainlog = get_model()
        traindata = getTrainingModel() 

        next_page_token = 0
        token = None 
        from agentapp.IntentExtractor import IntentExtractor
        intenteng = IntentExtractor()
        while next_page_token != None:             
            training_logs, next_page_token = getTrainingModel().list_all(cursor=token, cust_id=cust_id, done=False)
            token = next_page_token
            for training_log in training_logs: 
                predicted = intenteng.getPredictedIntent(str(training_log['query'] + ' . ' + training_log['tags']) , cust_id)  
                if len(predicted) < 1: 
                    predicted = ['Default']
                traindata.update(training_log['tags'], training_log['query'], training_log['response'], query_category=training_log['query_category'], 
                    done=True, id = training_log['id'], resp_category=predicted[0], cust_id=cust_id)
                print ('processing training data :', training_log['id'])
        logging.info ('applyPrediction : Completed')

def preprocess(sentence):
    sentence = sentence.lower()
    tokenizer = RegexpTokenizer(r'\w+')
    tokens = tokenizer.tokenize(sentence)
    filtered_words = [w for w in tokens if not w in stopwords.words('english')]
    return " ".join(filtered_words)