import docker
import re
import os
import ipyparallel as ipp
import random
import time
import errno
import os
import signal
import sys
import subprocess
import warnings
import string
import riak

def start_blockade(num_nodes, repo_path):
    #"/Users/basho/Desktop/basho/pypsen/blockade.yml"
    text_file = open(repo_path+'/blockade.yml', "w")
    text_file.close()
    text_file = open(repo_path+'/blockade.yml', "w")
    text_file.write('containers:')
    for i in range(1,num_nodes+1):
        temp_node_name = 'node'+str(i)
        text_file.write(str('\n    '+temp_node_name+': \n        image: hardtester \n        hostname: '+temp_node_name+' \n        name: '+temp_node_name+' \n\n'))
    text_file.close()
    os.system("(cd "+repo_path+" && blockade up)")
    time.sleep(10)
    
def stop_blockade(repo_path):
    os.system("(cd "+repo_path+" && blockade destroy)")
    os.system("(cd "+repo_path+" && docker rm -f `docker ps --no-trunc -aq`)")

def stop_cluster():
    proc = subprocess.Popen(["ipcluster stop"], shell=True, stdin=None, stdout=None, stderr=None, close_fds=True)
    
def start_cluster_controller():
    proc = subprocess.Popen(["sudo ipcontroller --ip=$(ipconfig getifaddr en0)"], shell=True, stdin=None, stdout=None, stderr=None, close_fds=True)
    
def start_cluster_engines(docker_client, jup_sec_path='~/.ipython/profile_default/security/'):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        os.system("sudo chmod -R a+rwX "+jup_sec_path)
        for item in docker_client.containers():
            node = item['Names'][0][1:]
            print 'Starting engine on '+node
            print os.system("docker cp "+jup_sec_path+"ipcontroller-engine.json "+node+":/ipcontroller-engine.json")
            job = docker_client.exec_create(node, 'sudo ipengine --file=/ipcontroller-engine.json')
            docker_client.exec_start(job['Id'], detach=True)

def stop_cluster_engines(docker_client):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for item in docker_client.containers():
            node = item['Names'][0][1:]
            job = docker_client.exec_create(node, 'ipengine stop')
            print docker_client.exec_start(job['Id'])

def riak_cluster(docker_client):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        client = docker_client
        nodes = []
        for item in client.containers():
            nodes.append({'name': item['Names'][0][1:],
                          'ip': item['NetworkSettings']['Networks']['bridge']['IPAddress']})
        print nodes
        jobs = []

        for i in range(0,len(nodes)):

            if i < len(nodes)-1:
                jobs.append(client.exec_create(nodes[i]['name'],"riak-admin cluster join riak@"+nodes[len(nodes)-1]['ip']))
            else:
                jobs.append(client.exec_create(nodes[i]['name'],"sleep 3"))
                jobs.append(client.exec_create(nodes[i]['name'],"riak-admin cluster plan"))
                jobs.append(client.exec_create(nodes[i]['name'],"sleep 3"))
                jobs.append(client.exec_create(nodes[i]['name'],"riak-admin cluster commit"))
                jobs.append(client.exec_create(nodes[i]['name'],"sleep 3"))
                jobs.append(client.exec_create(nodes[i]['name'],"riak-admin member-status"))

        for job in jobs:
            print client.exec_start(job['Id'])
    return nodes

def get_riak_nodes(docker_client):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        nodes = []
        for item in docker_client.containers():
            nodes.append({'name': item['Names'][0][1:],
                          'ip': item['NetworkSettings']['Networks']['bridge']['IPAddress']})
        print nodes
    return nodes

def exec_op(host, target, op, bucket, key, value_field, timeout):
    client = riak.RiakClient(host=target['ip'], http_port=8098)
    bucket = client.bucket(bucket)
    result = {}
    result['host'] = host['name']
    result['target'] = target['name']
    
    if op['type'] == 'read':
        try:
            result['type'] = 'read'
            result['invoke_timestamp'] = int(round(time.time() * 1000))
            out = bucket.get(key, timeout=timeout)
            result['compl_timestamp'] = int(round(time.time() * 1000))
            if out.data[value_field] != None:
                result['output'] = str(out.data[value_field])
                result['success'] = 'ok'
            else:
                result['output'] = 'read failed'
                result['success'] = 'fail'
        except Exception as e:
            print e
            result['compl_timestamp'] = int(round(time.time() * 1000))
            result['output'] = 'read timed out'
            result['success'] = 'timeout'
        
    elif op['type'] == 'write':
        result['type'] = 'write'
        result['input'] = str(op['value'])
        new_val = {value_field: op['value']}
        new_obj = bucket.new(key, data=new_val)
        try:
            result['invoke_timestamp'] = int(round(time.time() * 1000))
            new_obj.store(timeout=timeout)
            result['compl_timestamp'] = int(round(time.time() * 1000))
            result['output'] = str(op['value'])
            result['success'] = 'ok'
        except Exception as e:
            print e
            result['compl_timestamp'] = int(round(time.time() * 1000))
            result['output'] = 'write timed out'
            result['success'] = 'timeout'
        
    elif op['type'] == 'cas':
        result['type'] = 'cas'
        result['input'] = '[' + str(op['swap_on_val']) + ' ' + str(op['swap_to_val']) + ']'
        try:
            result['invoke_timestamp'] = int(round(time.time() * 1000))
            out = bucket.get(key, timeout=timeout)
            if out.data[value_field] != None:
                if out.data[value_field] == op['swap_on_val']:
                    new_val = {value_field: op['swap_to_val']}
                    new_obj = bucket.new(key, data=new_val)
                    try:
                        new_obj.store(timeout=timeout)
                        result['compl_timestamp'] = int(round(time.time() * 1000))
                        result['output'] = '[' + str(op['swap_on_val']) + ' ' + str(op['swap_to_val']) + ']'
                        result['success'] = 'ok'
                    except Exception as e:
                        print e
                        result['compl_timestamp'] = int(round(time.time() * 1000))
                        result['output'] = 'cas timed out'
                        result['success'] = 'timeout'
                else:
                    result['compl_timestamp'] = int(round(time.time() * 1000))
                    result['output'] = 'no swap'
                    result['success'] = 'fail'
            else:
                result['compl_timestamp'] = int(round(time.time() * 1000))
                result['output'] = 'swap read failed '
                result['success'] = 'fail'
        except Exception as e:
            print e
            result['compl_timestamp'] = int(round(time.time() * 1000))
            result['output'] = 'cas timed out'
            result['success'] = 'timeout'
            
    elif op['type'] == 'sleep':
        result['type'] = 'sleep'
        result['invoke_timestamp'] = int(round(time.time() * 1000))
        time.sleep(op['sleep_val'])
        result['compl_timestamp'] = int(round(time.time() * 1000))
        result['output'] = 'sleep val: '+ str(op['sleep_val'])
        result['success'] = 'ok'
    else:
        result['output'] = 'bad op type'
        
    return result

def start_parallel_executor():
    rc = ipp.Client()
    dview = rc[:]
    dview.use_cloudpickle()
    return dview

def run_test(run_cmds, bucket_name, key_name, value_field, timeout):
    results= []
    for cmd in run_cmds:
        time.sleep(random.random()*1)
        res = exec_op(cmd['host'], cmd['target'], cmd['op'], bucket_name, key_name, value_field, timeout)
        results.append(res)
    return results

def gen_cmds(nodes, node, num_cmds):
    #start with a write to avoid read failures
    host = node
    target_list = nodes
    cmds = [{'host': host, 'target': host, 'op': {'type': 'write', 'value': int(random.random()*10)}}]
    for x in range(1,num_cmds):
        
        new_op = {}
        new_cmd = {}
        new_target = random.choice(target_list)
        selector = random.randint(1,4)
        
        #Read
        if selector == 1:
            new_op = {'type': 'read'}
            new_cmd = {'host': host, 'target': new_target, 'op': new_op}

        #Write
        elif selector == 2:
            new_op = {'type': 'write', 'value': int(random.random()*10)}
            new_cmd = {'host': host, 'target': new_target, 'op': new_op}
            
        #CAS
        elif selector == 3:
            new_op = {'type': 'cas', 'swap_on_val': int(random.random()*10), 'swap_to_val': int(random.random()*10)}
            new_cmd = {'host': host, 'target': new_target, 'op': new_op}

        #Sleep
        elif selector == 4:
            new_op = {'type': 'sleep', 'sleep_val':random.random()*3}
            new_cmd = {'host': host, 'target': new_target, 'op': new_op}

        else:
            print 'bad selector'
        cmds.append(new_cmd)
    return cmds

def start_consitency_test(parallel_executor, nodes, num_commands, bucket_name, key_name, value_field, timeout, repo_path):
    parallel_results = parallel_executor.map(lambda node: run_test(gen_cmds(nodes, node, num_commands), bucket_name, key_name, value_field, timeout), nodes)
    nemisis_up = False
    node_names = ["node"+str(i) for i in range(1,len(nodes)+1)]
    nemisis_results = []
    while not parallel_results.done():
        result = {}
        result['host'] = 'nemisis'
        if nemisis_up:
            time.sleep(5)
            result['invoke_timestamp'] = int(round(time.time() * 1000))
            os.system("(cd "+repo_path+" && blockade join)")
            result['compl_timestamp'] = int(round(time.time() * 1000))
            result['type'] = 'join'
            result['success'] = 'ok'
            result['output'] = 'blockade join'
            nemisis_up = False

        else:
            rand_nodes = random.sample(set(node_names), random.randint(1,len(node_names)))
            cmd = ''
            for node in rand_nodes:
                cmd = cmd + node + ','
            cmd = cmd[:-1]
            result['invoke_timestamp'] = int(round(time.time() * 1000))
            os.system("(cd "+repo_path+" && blockade partition "+cmd+")")
            result['compl_timestamp'] = int(round(time.time() * 1000))
            result['type'] = 'partition'
            result['success'] = 'ok'

            out = '"Cut off {'
            partA = list(set(node_names)-set(rand_nodes))
            for node in node_names:
                cmd = ':'+node+' #{:'
                if node in rand_nodes:
                    for other_node in partA:
                        cmd = cmd+other_node+' '
                if node in partA:
                    for other_node in rand_nodes:
                        cmd = cmd+other_node+' '
                cmd = cmd.strip()+'}, '
                out = out + cmd
            out = out.strip()[:-1]+'}"'
            result['output'] = out
            nemisis_up = True

        nemisis_results.append(result)
    if nemisis_up:
        result['invoke_timestamp'] = int(round(time.time() * 1000))
        os.system("(cd "+repo_path+" && blockade join)")
        result['compl_timestamp'] = int(round(time.time() * 1000))
        result['type'] = 'join'
        result['success'] = 'ok'
        result['output'] = 'blockade join'
        nemisis_up = False
        nemisis_results.append(result)

    pr = parallel_results.result()
    pr.append(nemisis_results)
    return pr

def make_causal_history(raw_history):
    history = [item for sublist in raw_history for item in sublist]
    causal_history = sorted(history, key=lambda k: k['invoke_timestamp'])
    print 'History length: '+ str(len(causal_history))
    num_timeouts = [item for item in causal_history if item['success'] == 'timeout']
    print 'Timeouts: '+ str(len(num_timeouts))
    return causal_history

def make_jepsen_log(a_causal_history, repo_path):
    new_history = []
    for item in a_causal_history:
        
        if item['type'] != 'sleep':
        
            #parse invoke op
            invoke_output = 'INFO  jepsen.util - '
            if item['host'] != 'nemisis':
                invoke_output = invoke_output + re.findall(r'\d+', item['host'])[0] + '     '
                invoke_output = invoke_output + ':invoke '
                invoke_output = invoke_output + ':'+ item['type']
                if item['type'] == 'read':
                    invoke_output = invoke_output + '    nil'
                if item['type'] == 'write':
                    invoke_output = invoke_output + '    ' + item['input'] + ''
                if item['type'] == 'cas':
                    invoke_output = invoke_output + '    ' + item['input'] + ''          
            
            else:
                if item['type'] == 'partition':
                    invoke_output = invoke_output + ':nemesis    :info    :start    nil'
                if item['type'] == 'join':
                    invoke_output = invoke_output + ':nemesis    :info    :stop    nil'
            new_history.append({'output':invoke_output, 'timestamp':item['invoke_timestamp']})
                
            #parse completion op
            compl_output = 'INFO  jepsen.util - '  
            if item['host'] != 'nemisis':
                compl_output = compl_output + re.findall(r'\d+', item['host'])[0] + '     '
                
                if item['success'] == 'timeout':
                    compl_output = compl_output + ':info   '
                    compl_output = compl_output + ':'+ item['type']
                    compl_output = compl_output + '   :timed-out'
                else: 
                    compl_output = compl_output + ':' + item['success'] + '   '
                    compl_output = compl_output + ':'+ item['type']
                    if item['type'] == 'cas':
                        compl_output = compl_output + '   ' + item['input'] + ''
                        
                    if item['type'] == 'write':
                        compl_output = compl_output +  '   ' + item['input']  + ''
                        
                    if item['type'] == 'read' and item['success'] == 'ok':
                        compl_output = compl_output +  '   ' + item['output']  + ''
                        
                    if item['type'] == 'read' and item['success'] != 'ok':
                        compl_output = compl_output + '   nil'
                        
            else:
                if item['type'] == 'partition':
                    compl_output = compl_output + ':nemesis    :info    :start    '+item['output']
                if item['type'] == 'join':
                    compl_output = compl_output + ':nemesis    :info    :stop    "fully connected"'
                
            
            new_history.append({'output':compl_output, 'timestamp':item['compl_timestamp']})
    text_file = open(repo_path+"/linearizability-checker/logs/test_0.log", "w")
    for item in sorted(new_history, key=lambda k: k['timestamp']):
        #print(item['output']+'\n')
        text_file.write(item['output']+'\n')
    text_file.close()
    
def run_linearizability_checker(repo_path):
    proc = subprocess.Popen(["(cd "+repo_path+"/linearizability-checker && make lin-checker)"], shell=True,
             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True)
    try:
        a = str(proc.communicate()[1])
        value = re.search('fail', a)
        if value.group(0) == 'fail':
            print 'Fail: history is not linearizable :('
            return 0
        else:
            print 'Pass: history is linearizable :)'
            return 1
    
    except:
        print 'Pass: history is linearizable :)'
        return 1