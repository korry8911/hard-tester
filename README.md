
# High Availability Riak Decoherence Tester

This is a project whose goal is to test the consistency properties of a Riak cluster during both normal operation and in the presence of network partitions. Currently, this project is just a prototype and should be used as such. This project was influenced heavily by [Jepsen](https://github.com/jepsen-io/jepsen) and [Linearizability Checker](https://github.com/ahorn/linearizability-checker).

# Running

You will need Docker, Jupyter Notebook, as well as the following python libraries:
 - IPyParallel 5.2.0
 - Riak 2.6.2
 - Docker-Py 1.6.0

```
eval $(docker-machine env default --shell=bash)
docker pull basho/riak-kv
sudo -E jupyter notebook
```
