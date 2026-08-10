FROM python:3.10-slim

ARG FISHTEST_COMMIT=4358b10e7901f63be94a51500d7a75040627e016
ARG OFFICIAL_FISHTEST_COMMIT=b571c90db880f973a7eea57bd344600fe89a7e8e

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt
RUN git clone https://github.com/ianfab/fishtest.git fishtest-src \
    && git -C fishtest-src checkout --detach "${FISHTEST_COMMIT}" \
    && test "$(git -C fishtest-src rev-parse HEAD)" = "${FISHTEST_COMMIT}" \
    && git clone https://github.com/official-stockfish/fishtest.git fishtest-official \
    && git -C fishtest-official checkout --detach "${OFFICIAL_FISHTEST_COMMIT}" \
    && test "$(git -C fishtest-official rev-parse HEAD)" = "${OFFICIAL_FISHTEST_COMMIT}"

COPY requirements.txt /opt/xfishtest/requirements.txt
RUN python -m pip install --no-cache-dir -r /opt/xfishtest/requirements.txt \
    && python -m pip install --no-cache-dir --no-deps -e /opt/fishtest-src/server

COPY production.ini /opt/fishtest-src/server/production.local.ini
COPY userdb.py /opt/fishtest-src/server/fishtest/userdb.py
COPY patch_variant_views.py /opt/xfishtest/patch_variant_views.py
RUN python /opt/xfishtest/patch_variant_views.py
COPY admin.py /opt/xfishtest/admin.py
COPY test_admin_sprt.py /opt/xfishtest/test_admin_sprt.py

WORKDIR /opt/fishtest-src/server
EXPOSE 6543
CMD ["pserve", "/opt/fishtest-src/server/production.local.ini"]
