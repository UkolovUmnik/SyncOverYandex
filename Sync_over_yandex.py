import requests
import os
from datetime import datetime, timedelta
from urllib.parse import urlencode
import time
from configobj import ConfigObj
import fnmatch
import logging
from pyzabbix import ZabbixMetric, ZabbixSender
import socket
import threading

statuses_sync=[]
threads=[]

def set_modified_to_file(file:str, modified:object)->bool:
   try:
      modified_to_write = (modified+datetime.now().astimezone().utcoffset()).timestamp()
      os.utime(file, times=(modified_to_write,  modified_to_write))
   except Exception as ex:
      logging.critical(f"Не удалось назначить файлу дату изменения")
      logging.critical(ex)
      return False   
   return True

def download_file_from_disk(file_url:str,local_file:str,modified_disk:object):
   download_response = requests.get(file_url)
   with open(local_file, 'wb') as f:
      f.write(download_response.content)
   set_modified_to_file(local_file, modified_disk)
   print(f'Загрузил {local_file}')

def get_modified_file_disk(file_dict:dict):
   return datetime.strptime(file_dict['modified'],'%Y-%m-%dT%X+00:00')

def get_list_elements_for_field(files_disk_list,field:str):
   result=[]
   for file_dict in files_disk_list:
      result.append(file_dict['name'])
   return result

def sync_folder(folder_settings:dict,folder_disk_info:dict)->bool:
   try:
      files_disk_list=folder_disk_info['_embedded']['items']
      files_local_list=os.listdir(folder_settings['local_folder'])
      for file_dict in files_disk_list:
         if fnmatch.fnmatch(file_dict['name'],folder_settings['mask']):
            local_file=folder_settings['local_folder']+'\\'+file_dict['name']
            modified_file_disk=get_modified_file_disk(file_dict)
            if os.path.isfile(local_file):
               modified_file_local=datetime.utcfromtimestamp(os.stat(local_file).st_mtime)
            if os.path.isfile(local_file)==False or modified_file_local<modified_file_disk:
               download_file_from_disk(file_dict['file'],local_file,modified_file_disk)
      if folder_settings['delete_extra_files']=='yes':
         for file in files_local_list:
            if fnmatch.fnmatch(file,folder_settings['mask'])==False:
               os.remove(folder_settings['local_folder']+'\\'+file)
   except Exception as ex:
      logging.critical(f"Не удалось синхронизировать папку")
      logging.critical(ex)
      return False
   return True
      
def get_settings(file:str)->dict:
   if os.path.isfile(file)==False:
      logging.critical(f"Не найден файл настроек {file}")
      return None
   try:
      settings = ConfigObj("config.ini")
   except Exception as ex:
      logging.critical(f"Не удалось прочитать файл настроек {file}")
      logging.critical(ex)
      return None
   return settings

def get_folder_disk_info(settings:dict,folder_settings:dict)->dict:
   try:
      result=requests.get(settings['yadisk']['base_url_info'], params={'public_key':folder_settings['public_disk_folder'], 'limit':folder_settings['limit_elements']})
      if result.status_code!=200:
         logging.critical(f"Недоступна ссылка на папку диска")        
         return
   except Exception as ex:
      logging.critical(f"Не удалось получить информацию о папке на диске")
      logging.critical(ex)
      return
   return result.json()

def create_folder(path:str)->bool:
   try:
      os.mkdir(path)
   except Exception as ex:
      logging.critical(f"Не удалось создать папку по пути {path}")
      return False
   return True
      
def send_to_zabbix(zabbix_settings:dict,status:bool):
   try:
      packet = [ZabbixMetric(zabbix_settings['host'], zabbix_settings['key'], int(status))]
      if zabbix_settings['timeout']=='':
         timeout=100
      else:
         timeout=int(zabbix_settings['timeout'])
      
      result = ZabbixSender(zabbix_server=socket.gethostbyname(zabbix_settings['server']), zabbix_port=int(zabbix_settings['port']), socket_wrapper=None, timeout=timeout).send(packet)
   except Exception as ex:
      logging.critical(f"Не удалось передать данные в Zabbix")
      logging.critical(ex)
      return None

def run_current_folder(settings:dict,folder_settings:dict):
   if os.path.exists(folder_settings['local_folder'])==False:
      if create_folder(folder_settings['local_folder'])==False:
         statuses_sync.append(False)
         return
   folder_disk_info=get_folder_disk_info(settings,folder_settings)
   if folder_disk_info==None:
      statuses_sync.append(False)
      return
   if sync_folder(folder_settings,folder_disk_info)==False:
      statuses_sync.append(False)
      return
   statuses_sync.append(True)
   logging.info(f"Папка {folder_settings['local_folder']} синхронизирована")
     
def run(settings:dict):
   if settings is None:
      statuses_sync.append(False)
      return
   for element in settings['folders']:
      folder_settings=settings['folders'][element]
      if folder_settings['enabled']=='no':
         continue
      thread = threading.Thread(target=run_current_folder, args=(settings,folder_settings,))
      threads.append(thread)
      thread.start()

def main():
   settings=get_settings('config.ini')
   while True:
      run(settings)
      for thread in threads:
         thread.join()
      status_all=True
      for status in statuses_sync:
         if status==False:
            status_all=False
      send_to_zabbix(settings['zabbix'],status_all)
      time.sleep(3600)

if __name__ == '__main__':
   logging.basicConfig(level=logging.INFO, filename="sync.log", filemode="a+", format='%(asctime)s – %(message)s')
   main()
