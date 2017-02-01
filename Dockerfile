FROM basho/riak-kv:latest

MAINTAINER Korrigan Clark <korriganclark@gmail.com>

# Install OpenJDK 8
RUN \
  apt-get update -y && \
  apt-get -f install -y && \
  apt-get install -y python-pip build-essential libssl-dev libffi-dev python-dev && \
  pip install six --upgrade && \
  pip install pyOpenSSL --upgrade && \
  pip install ipyparallel riak cloudpickle cryptography docker-py

RUN mkdir /hardtester
ADD ./hardtester.py /hardtester


