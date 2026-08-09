FROM python:3.10-slim

ARG FISHTEST_COMMIT=4358b10e7901f63be94a51500d7a75040627e016

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt
RUN git clone https://github.com/ianfab/fishtest.git fishtest-src \
    && git -C fishtest-src checkout --detach "${FISHTEST_COMMIT}" \
    && test "$(git -C fishtest-src rev-parse HEAD)" = "${FISHTEST_COMMIT}"

COPY requirements.txt /opt/xfishtest/requirements.txt
RUN python -m pip install --no-cache-dir -r /opt/xfishtest/requirements.txt \
    && python -m pip install --no-cache-dir --no-deps -e /opt/fishtest-src/server

COPY production.ini /opt/fishtest-src/server/production.local.ini
COPY userdb.py /opt/fishtest-src/server/fishtest/userdb.py
COPY admin.py /opt/xfishtest/admin.py
COPY test_admin_sprt.py /opt/xfishtest/test_admin_sprt.py

WORKDIR /opt/fishtest-src/server
EXPOSE 6543
CMD ["pserve", "/opt/fishtest-src/server/production.local.ini"]
