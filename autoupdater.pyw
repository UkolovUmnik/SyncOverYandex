import requests
import os
from datetime import datetime
import git
from configobj import ConfigObj

def update():
   pass

def main():
   file_last_update='last_update_date.txt'
   repo_url = ConfigObj(".git/config")['remote "origin"']['url']
   remote_repo=repo_url[repo_url.find(':')+1:].replace('.git','')
   download_response = requests.get("https://api.github.com/repos/"+remote_repo)
   pushed_at=download_response.json()['pushed_at']
   last_push_date=datetime.strptime(pushed_at,"%Y-%m-%dT%H:%M:%SZ")
   date_local=datetime.strptime('1970-01-01T00:00:00Z',"%Y-%m-%dT%H:%M:%SZ")
   if os.path.isfile(file_last_update):
      with open(file_last_update, encoding='utf-8') as f:        
         date_local=datetime.strptime(f.read(),"%Y-%m-%dT%H:%M:%SZ")
   if last_push_date>date_local:
      g = git.cmd.Git(os.path.dirname(os.path.realpath(__file__)))
      g.pull()
   with open(file_last_update, mode='w+', encoding='utf-8') as f:
      f.write(last_push_date.strftime("%Y-%m-%dT%H:%M:%SZ"))

main()
   
