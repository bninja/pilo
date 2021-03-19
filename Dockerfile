FROM 552131502238.dkr.ecr.us-east-1.amazonaws.com/eventbrite/ubuntu-base:16.04-python-2.7-1078776

WORKDIR /src/

COPY . .

# In case an internal dependency is added, we will need to look in our internal codearficato repo.
# But as that is currently not true, we can look for them in pypy making things simpler. 
RUN pip install -e .[tests]

CMD ["/bin/bash", "-c", "py.test && coverage xml -o /tmp/codeartifact"]