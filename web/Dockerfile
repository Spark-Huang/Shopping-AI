#FROM node:18-alpine

FROM ubuntu:22.04

RUN apt update
RUN apt install -y \
    apt-transport-https \
    curl \
    software-properties-common

RUN curl -sL https://deb.nodesource.com/setup_21.x | bash -
RUN apt install -y nodejs

WORKDIR /app

COPY . .
RUN rm -rf /app/public/images && ln -s /app/shared/images /app/public/images

RUN npm install

CMD ["npm", "run", "start"]
