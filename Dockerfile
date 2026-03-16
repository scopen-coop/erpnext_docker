FROM python:3.11-bookworm

ARG FRAPPE_BRANCH=version-15
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
  git \
  curl \
  ca-certificates \
  cron \
  mariadb-client \
  redis-tools \
  postgresql-client \
  build-essential \
  pkg-config \
  libffi-dev \
  libssl-dev \
  libjpeg62-turbo-dev \
  zlib1g-dev \
  liblcms2-dev \
  libwebp-dev \
  libtiff6 \
  libopenjp2-7 \
  libsasl2-dev \
  libldap2-dev \
  libpq-dev \
  xvfb \
  wkhtmltopdf \
  npm \
  && rm -rf /var/lib/apt/lists/*

RUN npm install -g yarn
RUN useradd -ms /bin/bash frappe

RUN pip install --no-cache-dir frappe-bench

USER frappe
WORKDIR /home/frappe

RUN bench init --skip-redis-config-generation --frappe-branch ${FRAPPE_BRANCH} frappe-bench

WORKDIR /home/frappe/frappe-bench
ENV PATH="/home/frappe/frappe-bench/env/bin:${PATH}"
