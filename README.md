
# High Availability Riak Decoherence Tester

This is a project whose goal is to test the consistency properties of a Riak cluster during both normal operation and in the presence of network partitions. Currently, this project is just a prototype and should be used as such. This project was influenced heavily by [Jepsen](https://github.com/jepsen-io/jepsen) and [Linearizability Checker](https://github.com/ahorn/linearizability-checker).

# Running

You will need Docker, Jupyter Notebook, as well as the following python libraries:
 - IPyParallel 5.2.0
 - Riak 2.6.2
 - Docker-Py 1.6.0

Clone this repo: `git clone https://github.com/korry8911/hard-tester.git`

Move into repo: `cd ./hard-tester`

Set docker enviroment (assuming docker-machine VM named default): `eval $(docker-machine env default --shell=bash)`

Build target docker container: `docker build -t hardtester .`

Launch Juypter notebook: `sudo -E jupyter notebook`

Open `test_runner.ipynb` and run the test, cell by cell
